"""Tests for the Jira API client.

All tests mock httpx.Client — no real Jira instance required.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from integrations.jira_client import JiraClient, JiraClientError, JiraTicketData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_URL = "https://myorg.atlassian.net"
EMAIL = "dev@example.com"
TOKEN = "secret-token"


def _make_client() -> JiraClient:
    return JiraClient(base_url=BASE_URL, email=EMAIL, api_token=TOKEN)


def _make_ticket_response(
    *,
    summary: str = "Fix payment retry logic",
    description_text: str = "Add exponential backoff for Stripe 5xx errors.",
    acceptance_criteria_text: str = "Given a 503, retry with backoff up to 3 times.",
    status: str = "In Progress",
    priority: str = "High",
    labels: list[str] | None = None,
) -> dict:
    """Build a minimal Jira REST v3 issue response."""
    if labels is None:
        labels = ["backend", "payments"]

    return {
        "key": "PAY-123",
        "fields": {
            "summary": summary,
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description_text}],
                    },
                    {
                        "type": "heading",
                        "attrs": {"level": 2},
                        "content": [
                            {"type": "text", "text": "Acceptance Criteria"}
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": acceptance_criteria_text}
                        ],
                    },
                ],
            },
            "status": {"name": status},
            "priority": {"name": priority},
            "labels": labels,
        },
    }


def _make_comments_page(
    bodies: list[str], *, start_at: int = 0, total: int | None = None
) -> dict:
    """Build a Jira paginated comment response."""
    comments = [
        {
            "body": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body}],
                    }
                ],
            }
        }
        for body in bodies
    ]
    return {
        "startAt": start_at,
        "maxResults": len(bodies),
        "total": total if total is not None else len(bodies),
        "comments": comments,
    }


def _mock_response(json_data: dict, *, status_code: int = 200) -> MagicMock:
    """Return a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# test_get_ticket_success
# ---------------------------------------------------------------------------


def test_get_ticket_success():
    """get_ticket maps all Jira fields onto JiraTicketData correctly."""
    client = _make_client()
    mock_http = MagicMock()
    mock_http.get.return_value = _mock_response(_make_ticket_response())
    client._http = mock_http

    result = client.get_ticket("PAY-123")

    assert isinstance(result, JiraTicketData)
    assert result.ticket_id == "PAY-123"
    assert result.title == "Fix payment retry logic"
    assert "exponential backoff" in result.description
    assert "retry with backoff" in result.acceptance_criteria
    assert result.status == "In Progress"
    assert result.priority == "High"
    assert result.labels == ["backend", "payments"]


def test_get_ticket_empty_labels():
    """get_ticket returns empty list when the ticket has no labels."""
    client = _make_client()
    mock_http = MagicMock()
    mock_http.get.return_value = _mock_response(
        _make_ticket_response(labels=[])
    )
    client._http = mock_http

    result = client.get_ticket("PAY-123")

    assert result.labels == []


def test_get_ticket_no_acceptance_criteria():
    """get_ticket returns empty string when acceptance criteria heading is absent."""
    client = _make_client()
    ticket_data = _make_ticket_response()
    # Strip the heading + following paragraph
    ticket_data["fields"]["description"]["content"] = [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Just a description."}],
        }
    ]
    mock_http = MagicMock()
    mock_http.get.return_value = _mock_response(ticket_data)
    client._http = mock_http

    result = client.get_ticket("PAY-123")

    assert result.acceptance_criteria == ""


def test_get_ticket_null_description():
    """get_ticket handles a null description field gracefully."""
    client = _make_client()
    ticket_data = _make_ticket_response()
    ticket_data["fields"]["description"] = None
    mock_http = MagicMock()
    mock_http.get.return_value = _mock_response(ticket_data)
    client._http = mock_http

    result = client.get_ticket("PAY-123")

    assert result.description == ""
    assert result.acceptance_criteria == ""


# ---------------------------------------------------------------------------
# test_get_ticket_not_found
# ---------------------------------------------------------------------------


def test_get_ticket_not_found():
    """A 404 response raises JiraClientError."""
    client = _make_client()
    mock_http = MagicMock()
    mock_http.get.return_value = _mock_response({}, status_code=404)
    client._http = mock_http

    with pytest.raises(JiraClientError, match="404"):
        client.get_ticket("PAY-999")


# ---------------------------------------------------------------------------
# test_get_ticket_unauthorized
# ---------------------------------------------------------------------------


def test_get_ticket_unauthorized():
    """A 401 response raises JiraClientError."""
    client = _make_client()
    mock_http = MagicMock()
    mock_http.get.return_value = _mock_response({}, status_code=401)
    client._http = mock_http

    with pytest.raises(JiraClientError, match="401"):
        client.get_ticket("PAY-123")


# ---------------------------------------------------------------------------
# test_get_comments_success (paginated — 2 pages)
# ---------------------------------------------------------------------------


def test_get_comments_success_paginated():
    """get_comments collects all comments across multiple pages."""
    client = _make_client()
    mock_http = MagicMock()

    page1 = _make_comments_page(
        ["First comment", "Second comment"], start_at=0, total=3
    )
    page2 = _make_comments_page(["Third comment"], start_at=2, total=3)

    mock_http.get.side_effect = [
        _mock_response(page1),
        _mock_response(page2),
    ]
    client._http = mock_http

    comments = client.get_comments("PAY-123")

    assert comments == ["First comment", "Second comment", "Third comment"]
    assert mock_http.get.call_count == 2


# ---------------------------------------------------------------------------
# test_get_comments_empty
# ---------------------------------------------------------------------------


def test_get_comments_empty():
    """get_comments returns an empty list when the ticket has no comments."""
    client = _make_client()
    mock_http = MagicMock()
    mock_http.get.return_value = _mock_response(
        _make_comments_page([], total=0)
    )
    client._http = mock_http

    comments = client.get_comments("PAY-123")

    assert comments == []
    assert mock_http.get.call_count == 1


# ---------------------------------------------------------------------------
# test_network_error
# ---------------------------------------------------------------------------


def test_network_error_raises_jira_client_error():
    """A network-level ConnectError is wrapped as JiraClientError."""
    client = _make_client()
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.ConnectError("Connection refused")
    client._http = mock_http

    with pytest.raises(JiraClientError, match="Connection refused"):
        client.get_ticket("PAY-123")


def test_network_error_on_comments_raises_jira_client_error():
    """A network-level error during get_comments is wrapped as JiraClientError."""
    client = _make_client()
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.ConnectError("timeout")
    client._http = mock_http

    with pytest.raises(JiraClientError):
        client.get_comments("PAY-123")
