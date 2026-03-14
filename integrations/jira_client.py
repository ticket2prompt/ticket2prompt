"""Jira API client."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


class JiraClientError(Exception):
    """Raised when the Jira API returns an error or a network failure occurs."""


@dataclass
class JiraTicketData:
    ticket_id: str
    title: str
    description: str
    acceptance_criteria: str
    status: str
    priority: str
    labels: list[str]
    comments: list[str] = field(default_factory=list)


class JiraClient:
    """HTTP client for the Jira Cloud REST API v3.

    Uses basic auth (email + API token) as required by Jira Cloud.
    """

    _PAGE_SIZE = 50  # comments fetched per paginated request

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            auth=(email, api_token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_ticket(self, ticket_id: str) -> JiraTicketData:
        """Fetch a single Jira ticket and return its structured data.

        Raises:
            JiraClientError: on HTTP errors (4xx/5xx) or network failures.
        """
        url = f"{self._base_url}/rest/api/3/issue/{ticket_id}"
        data = self._get_json(url)

        key: str = data["key"]
        fields: dict = data["fields"]

        title: str = fields.get("summary", "")
        description_doc = fields.get("description")
        status: str = fields.get("status", {}).get("name", "")
        priority: str = fields.get("priority", {}).get("name", "")
        labels: list[str] = fields.get("labels", [])

        description, acceptance_criteria = _parse_description(description_doc)

        return JiraTicketData(
            ticket_id=key,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria,
            status=status,
            priority=priority,
            labels=labels,
        )

    def get_comments(self, ticket_id: str) -> list[str]:
        """Fetch all comments for a ticket, paginating as needed.

        Raises:
            JiraClientError: on HTTP errors or network failures.
        """
        url = f"{self._base_url}/rest/api/3/issue/{ticket_id}/comment"
        comments: list[str] = []
        start_at = 0

        while True:
            data = self._get_json(url, params={"startAt": start_at, "maxResults": self._PAGE_SIZE})
            page: list[dict] = data.get("comments", [])

            for comment in page:
                text = _extract_plain_text(comment.get("body"))
                if text:
                    comments.append(text)

            total: int = data.get("total", 0)
            start_at += len(page)

            if start_at >= total or not page:
                break

        return comments

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_json(self, url: str, params: dict | None = None) -> dict:
        """Perform a GET request and return the parsed JSON body.

        Raises:
            JiraClientError: on HTTP errors or network failures.
        """
        try:
            response = self._http.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise JiraClientError(
                f"Jira API error {exc.response.status_code} for {url}: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise JiraClientError(
                f"Network error reaching Jira ({url}): {exc}"
            ) from exc

        return response.json()


# ---------------------------------------------------------------------------
# Document parsing helpers
# ---------------------------------------------------------------------------


def _extract_plain_text(doc: dict | None) -> str:
    """Recursively extract plain text from an Atlassian Document Format node."""
    if not doc:
        return ""
    if doc.get("type") == "text":
        return doc.get("text", "")

    parts: list[str] = []
    for child in doc.get("content", []):
        parts.append(_extract_plain_text(child))
    return " ".join(filter(None, parts))


def _parse_description(doc: dict | None) -> tuple[str, str]:
    """Split a Jira ADF description into (description, acceptance_criteria).

    Scans the top-level content nodes for a heading whose text contains
    "acceptance criteria" (case-insensitive). Everything before that heading
    is the description; everything after is acceptance criteria.

    Returns:
        A (description, acceptance_criteria) tuple. Both are empty strings if
        the document is None or empty.
    """
    if not doc:
        return "", ""

    top_nodes: list[dict] = doc.get("content", [])
    ac_heading_index: int | None = None

    for i, node in enumerate(top_nodes):
        if node.get("type") == "heading":
            heading_text = _extract_plain_text(node).lower()
            if "acceptance criteria" in heading_text:
                ac_heading_index = i
                break

    if ac_heading_index is None:
        # No AC heading found — everything is description
        desc_nodes = top_nodes
        ac_nodes: list[dict] = []
    else:
        desc_nodes = top_nodes[:ac_heading_index]
        ac_nodes = top_nodes[ac_heading_index + 1 :]  # skip the heading itself

    description = " ".join(
        filter(None, (_extract_plain_text(n) for n in desc_nodes))
    )
    acceptance_criteria = " ".join(
        filter(None, (_extract_plain_text(n) for n in ac_nodes))
    )
    return description, acceptance_criteria
