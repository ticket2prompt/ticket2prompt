"""Jira ticket history indexer.

Fetches tickets from Jira, stores metadata in Postgres, and generates
embeddings for semantic search over historical tickets.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from indexing.embedding_pipeline import generate_embeddings_from_texts
from integrations.jira_client import JiraClient, JiraTicketData, _parse_description
from storage.postgres import PostgresClient
from storage.qdrant_client import QdrantVectorStore

logger = logging.getLogger(__name__)


@dataclass
class JiraSyncResult:
    """Result of a Jira ticket sync operation."""
    tickets_synced: int = 0
    embeddings_created: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class JiraEmbeddingInput:
    """Wraps text for embedding with a stable ID."""
    symbol_id: str  # reuse the Qdrant point ID pattern
    embedding: list[float] = field(default_factory=list)


class JiraIndexer:
    """Indexes Jira tickets into Postgres and Qdrant for historical context."""

    def __init__(
        self,
        jira_client: JiraClient,
        postgres: PostgresClient,
        qdrant: QdrantVectorStore,
        org_id: str,
        project_id: str,
    ) -> None:
        self._jira = jira_client
        self._postgres = postgres
        self._qdrant = qdrant
        self._org_id = org_id
        self._project_id = project_id

    def sync_tickets(self, project_key: str, since: Optional[datetime] = None) -> JiraSyncResult:
        """Fetch tickets from Jira and index them.

        Args:
            project_key: The Jira project key (e.g., "PROJ").
            since: Only fetch tickets updated after this timestamp.

        Returns:
            JiraSyncResult with counts and errors.
        """
        result = JiraSyncResult()

        try:
            tickets = self._fetch_tickets(project_key, since)
        except Exception as e:
            logger.error("Failed to fetch tickets from Jira: %s", e)
            result.errors.append(f"Jira fetch failed: {e}")
            return result

        all_texts = []
        all_payloads = []
        all_ids = []

        for ticket in tickets:
            try:
                # Store in Postgres
                self._postgres.upsert_jira_ticket(
                    org_id=self._org_id,
                    project_id=self._project_id,
                    ticket_key=ticket.ticket_id,
                    title=ticket.title,
                    description=ticket.description,
                    acceptance_criteria=ticket.acceptance_criteria,
                    status=ticket.status,
                    priority=ticket.priority,
                    labels=ticket.labels,
                )

                # Prepare embeddings for each non-empty text field
                fields_to_embed = [
                    ("title", f"jira ticket: {ticket.title}"),
                    ("description", f"jira description: {ticket.description[:500]}"),
                    ("acceptance_criteria", f"acceptance criteria: {ticket.acceptance_criteria[:500]}"),
                ]

                for field_name, text in fields_to_embed:
                    if not text.split(":", 1)[-1].strip():
                        continue

                    point_id = f"jira:{self._project_id}:{ticket.ticket_id}:{field_name}"
                    all_texts.append(text)
                    all_ids.append(point_id)
                    all_payloads.append({
                        "content_type": "jira_ticket",
                        "project_id": self._project_id,
                        "org_id": self._org_id,
                        "ticket_key": ticket.ticket_id,
                        "title": ticket.title,
                        "status": ticket.status,
                        "priority": ticket.priority,
                        "labels": ticket.labels,
                        "embedded_field": field_name,
                    })

                result.tickets_synced += 1

            except Exception as e:
                msg = f"Failed to index ticket {ticket.ticket_id}: {e}"
                logger.error(msg)
                result.errors.append(msg)

        # Batch generate embeddings and upsert to Qdrant
        if all_texts:
            try:
                embeddings = generate_embeddings_from_texts(all_texts)

                embedding_objs = [
                    JiraEmbeddingInput(symbol_id=point_id, embedding=emb)
                    for point_id, emb in zip(all_ids, embeddings)
                ]

                self._qdrant.ensure_collection()
                self._qdrant.upsert_embeddings(embedding_objs, all_payloads)
                result.embeddings_created = len(embedding_objs)

            except Exception as e:
                msg = f"Failed to generate/store embeddings: {e}"
                logger.error(msg)
                result.errors.append(msg)

        logger.info(
            "Jira sync complete: %d tickets, %d embeddings, %d errors",
            result.tickets_synced, result.embeddings_created, len(result.errors),
        )
        return result

    def _fetch_tickets(self, project_key: str, since: Optional[datetime] = None) -> list[JiraTicketData]:
        """Fetch tickets from Jira using search API with JQL."""
        jql = f"project = {project_key}"
        if since:
            jql += f" AND updated >= '{since.strftime('%Y-%m-%d')}'"
        jql += " ORDER BY updated DESC"

        tickets = []
        try:
            search_results = self._jira._get_json(
                f"{self._jira._base_url}/rest/api/3/search",
                params={
                    "jql": jql,
                    "maxResults": 100,
                    "fields": "summary,description,status,priority,labels,comment",
                },
            )

            for issue in search_results.get("issues", []):
                key = issue["key"]
                issue_fields = issue["fields"]

                description_doc = issue_fields.get("description")
                desc, ac = _parse_description(description_doc)

                ticket = JiraTicketData(
                    ticket_id=key,
                    title=issue_fields.get("summary", ""),
                    description=desc,
                    acceptance_criteria=ac,
                    status=issue_fields.get("status", {}).get("name", ""),
                    priority=issue_fields.get("priority", {}).get("name", ""),
                    labels=issue_fields.get("labels", []),
                )
                tickets.append(ticket)

        except Exception as e:
            logger.error("Jira search failed: %s", e)
            raise

        return tickets
