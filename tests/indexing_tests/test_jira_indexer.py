"""Tests for indexing/jira_indexer.py."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from indexing.jira_indexer import JiraEmbeddingInput, JiraIndexer, JiraSyncResult
from integrations.jira_client import JiraTicketData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ticket(
    ticket_id="PROJ-1",
    title="Fix the bug",
    description="Something is broken",
    acceptance_criteria="It works",
    status="Open",
    priority="High",
    labels=None,
):
    return JiraTicketData(
        ticket_id=ticket_id,
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        status=status,
        priority=priority,
        labels=labels or [],
    )


def _make_indexer(jira=None, postgres=None, qdrant=None):
    return JiraIndexer(
        jira_client=jira or MagicMock(),
        postgres=postgres or MagicMock(),
        qdrant=qdrant or MagicMock(),
        org_id="org-1",
        project_id="proj-1",
    )


# ---------------------------------------------------------------------------
# JiraSyncResult dataclass
# ---------------------------------------------------------------------------

class TestJiraSyncResult:
    def test_defaults(self):
        r = JiraSyncResult()
        assert r.tickets_synced == 0
        assert r.embeddings_created == 0
        assert r.errors == []

    def test_errors_list_is_independent(self):
        r1 = JiraSyncResult()
        r2 = JiraSyncResult()
        r1.errors.append("oops")
        assert r2.errors == []


# ---------------------------------------------------------------------------
# JiraEmbeddingInput dataclass
# ---------------------------------------------------------------------------

class TestJiraEmbeddingInput:
    def test_fields(self):
        obj = JiraEmbeddingInput(symbol_id="abc", embedding=[0.1, 0.2])
        assert obj.symbol_id == "abc"
        assert obj.embedding == [0.1, 0.2]

    def test_default_embedding(self):
        obj = JiraEmbeddingInput(symbol_id="abc")
        assert obj.embedding == []


# ---------------------------------------------------------------------------
# JiraIndexer.sync_tickets — success path
# ---------------------------------------------------------------------------

class TestSyncTicketsSuccess:
    def test_returns_sync_result(self):
        ticket = _make_ticket()
        indexer = _make_indexer()
        indexer._fetch_tickets = MagicMock(return_value=[ticket])

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10],
        ):
            result = indexer.sync_tickets("PROJ")

        assert isinstance(result, JiraSyncResult)

    def test_tickets_synced_count(self):
        tickets = [_make_ticket("PROJ-1"), _make_ticket("PROJ-2")]
        indexer = _make_indexer()
        indexer._fetch_tickets = MagicMock(return_value=tickets)

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10] * 6,  # 2 tickets × 3 fields = 6 embeddings
        ):
            result = indexer.sync_tickets("PROJ")

        assert result.tickets_synced == 2
        assert result.errors == []

    def test_calls_postgres_upsert_for_each_ticket(self):
        mock_postgres = MagicMock()
        tickets = [_make_ticket("PROJ-1"), _make_ticket("PROJ-2")]
        indexer = _make_indexer(postgres=mock_postgres)
        indexer._fetch_tickets = MagicMock(return_value=tickets)

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10] * 6,
        ):
            indexer.sync_tickets("PROJ")

        assert mock_postgres.upsert_jira_ticket.call_count == 2

    def test_calls_qdrant_ensure_collection_and_upsert(self):
        mock_qdrant = MagicMock()
        ticket = _make_ticket()
        indexer = _make_indexer(qdrant=mock_qdrant)
        indexer._fetch_tickets = MagicMock(return_value=[ticket])

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10] * 3,
        ):
            indexer.sync_tickets("PROJ")

        mock_qdrant.ensure_collection.assert_called_once()
        mock_qdrant.upsert_embeddings.assert_called_once()

    def test_embeddings_created_count(self):
        ticket = _make_ticket(title="Title", description="Desc", acceptance_criteria="AC")
        indexer = _make_indexer()
        indexer._fetch_tickets = MagicMock(return_value=[ticket])

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10] * 3,
        ):
            result = indexer.sync_tickets("PROJ")

        # All three fields are non-empty
        assert result.embeddings_created == 3

    def test_skips_empty_fields(self):
        ticket = _make_ticket(title="Title", description="", acceptance_criteria="")
        indexer = _make_indexer()
        indexer._fetch_tickets = MagicMock(return_value=[ticket])

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10],
        ):
            result = indexer.sync_tickets("PROJ")

        # Only title is non-empty after stripping the prefix
        assert result.embeddings_created == 1

    def test_no_tickets_returns_zero_counts(self):
        indexer = _make_indexer()
        indexer._fetch_tickets = MagicMock(return_value=[])

        result = indexer.sync_tickets("PROJ")

        assert result.tickets_synced == 0
        assert result.embeddings_created == 0
        assert result.errors == []

    def test_uses_project_id_and_org_id_in_postgres_call(self):
        mock_postgres = MagicMock()
        ticket = _make_ticket()
        indexer = JiraIndexer(
            jira_client=MagicMock(),
            postgres=mock_postgres,
            qdrant=MagicMock(),
            org_id="my-org",
            project_id="my-proj",
        )
        indexer._fetch_tickets = MagicMock(return_value=[ticket])

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10] * 3,
        ):
            indexer.sync_tickets("PROJ")

        call_kwargs = mock_postgres.upsert_jira_ticket.call_args[1]
        assert call_kwargs["org_id"] == "my-org"
        assert call_kwargs["project_id"] == "my-proj"


# ---------------------------------------------------------------------------
# JiraIndexer.sync_tickets — error paths
# ---------------------------------------------------------------------------

class TestSyncTicketsErrors:
    def test_jira_fetch_failure_returns_error_result(self):
        indexer = _make_indexer()
        indexer._fetch_tickets = MagicMock(side_effect=RuntimeError("Jira down"))

        result = indexer.sync_tickets("PROJ")

        assert result.tickets_synced == 0
        assert len(result.errors) == 1
        assert "Jira fetch failed" in result.errors[0]

    def test_postgres_upsert_failure_records_error_and_continues(self):
        mock_postgres = MagicMock()
        mock_postgres.upsert_jira_ticket.side_effect = Exception("DB error")
        tickets = [_make_ticket("PROJ-1"), _make_ticket("PROJ-2")]
        mock_postgres2 = MagicMock()  # second ticket succeeds if postgres recovered
        indexer = _make_indexer(postgres=mock_postgres)
        indexer._fetch_tickets = MagicMock(return_value=tickets)

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[],
        ):
            result = indexer.sync_tickets("PROJ")

        # Both tickets fail, both recorded in errors
        assert result.tickets_synced == 0
        assert len(result.errors) == 2
        assert all("Failed to index ticket" in e for e in result.errors)

    def test_embedding_failure_recorded_in_errors(self):
        ticket = _make_ticket()
        indexer = _make_indexer()
        indexer._fetch_tickets = MagicMock(return_value=[ticket])

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            side_effect=RuntimeError("Embedding model unavailable"),
        ):
            result = indexer.sync_tickets("PROJ")

        # Ticket is synced to postgres before embedding failure
        assert result.tickets_synced == 1
        assert any("Failed to generate/store embeddings" in e for e in result.errors)
        assert result.embeddings_created == 0

    def test_qdrant_upsert_failure_recorded(self):
        mock_qdrant = MagicMock()
        mock_qdrant.upsert_embeddings.side_effect = RuntimeError("Qdrant error")
        ticket = _make_ticket()
        indexer = _make_indexer(qdrant=mock_qdrant)
        indexer._fetch_tickets = MagicMock(return_value=[ticket])

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10] * 3,
        ):
            result = indexer.sync_tickets("PROJ")

        assert result.embeddings_created == 0
        assert any("Failed to generate/store embeddings" in e for e in result.errors)

    def test_partial_success_continues_after_per_ticket_error(self):
        mock_postgres = MagicMock()
        # First call raises, second succeeds
        mock_postgres.upsert_jira_ticket.side_effect = [Exception("oops"), None]
        tickets = [_make_ticket("PROJ-1"), _make_ticket("PROJ-2")]
        indexer = _make_indexer(postgres=mock_postgres)
        indexer._fetch_tickets = MagicMock(return_value=tickets)

        with patch(
            "indexing.jira_indexer.generate_embeddings_from_texts",
            return_value=[[0.1] * 10] * 3,
        ):
            result = indexer.sync_tickets("PROJ")

        assert result.tickets_synced == 1
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# JiraIndexer._fetch_tickets
# ---------------------------------------------------------------------------

class TestFetchTickets:
    def _search_response(self, issues):
        return {"issues": issues}

    def _make_issue(self, key="PROJ-1", summary="Title", status="Open", priority="High", labels=None):
        return {
            "key": key,
            "fields": {
                "summary": summary,
                "description": None,
                "status": {"name": status},
                "priority": {"name": priority},
                "labels": labels or [],
            },
        }

    def test_builds_correct_jql_without_since(self):
        mock_jira = MagicMock()
        mock_jira._base_url = "https://example.atlassian.net"
        mock_jira._get_json.return_value = self._search_response([])
        indexer = _make_indexer(jira=mock_jira)

        indexer._fetch_tickets("PROJ")

        call_kwargs = mock_jira._get_json.call_args[1]
        jql = call_kwargs["params"]["jql"]
        assert "project = PROJ" in jql
        assert "ORDER BY updated DESC" in jql
        assert "updated >=" not in jql

    def test_builds_jql_with_since(self):
        mock_jira = MagicMock()
        mock_jira._base_url = "https://example.atlassian.net"
        mock_jira._get_json.return_value = self._search_response([])
        indexer = _make_indexer(jira=mock_jira)

        since = datetime(2024, 1, 15)
        indexer._fetch_tickets("PROJ", since=since)

        call_kwargs = mock_jira._get_json.call_args[1]
        jql = call_kwargs["params"]["jql"]
        assert "updated >= '2024-01-15'" in jql

    def test_parses_issues_into_ticket_data(self):
        mock_jira = MagicMock()
        mock_jira._base_url = "https://example.atlassian.net"
        mock_jira._get_json.return_value = self._search_response([
            self._make_issue("PROJ-1", "Bug fix", "In Progress", "Medium", ["backend"]),
        ])
        indexer = _make_indexer(jira=mock_jira)

        tickets = indexer._fetch_tickets("PROJ")

        assert len(tickets) == 1
        t = tickets[0]
        assert t.ticket_id == "PROJ-1"
        assert t.title == "Bug fix"
        assert t.status == "In Progress"
        assert t.priority == "Medium"
        assert t.labels == ["backend"]

    def test_returns_multiple_tickets(self):
        mock_jira = MagicMock()
        mock_jira._base_url = "https://example.atlassian.net"
        issues = [self._make_issue(f"PROJ-{i}") for i in range(5)]
        mock_jira._get_json.return_value = self._search_response(issues)
        indexer = _make_indexer(jira=mock_jira)

        tickets = indexer._fetch_tickets("PROJ")

        assert len(tickets) == 5

    def test_raises_on_jira_api_failure(self):
        mock_jira = MagicMock()
        mock_jira._base_url = "https://example.atlassian.net"
        mock_jira._get_json.side_effect = Exception("Network error")
        indexer = _make_indexer(jira=mock_jira)

        with pytest.raises(Exception, match="Network error"):
            indexer._fetch_tickets("PROJ")

    def test_returns_empty_list_when_no_issues(self):
        mock_jira = MagicMock()
        mock_jira._base_url = "https://example.atlassian.net"
        mock_jira._get_json.return_value = self._search_response([])
        indexer = _make_indexer(jira=mock_jira)

        tickets = indexer._fetch_tickets("PROJ")

        assert tickets == []
