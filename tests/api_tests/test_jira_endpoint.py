"""Tests for POST /projects/{project_id}/ticket endpoint."""

from unittest.mock import patch, MagicMock

from prompts import GeneratedPrompt

PROJECT_URL = "/projects/test-project-id/ticket"


def _make_ticket_payload(**overrides):
    base = {
        "title": "Fix payment retry",
        "description": "Add exponential backoff for Stripe 5xx errors",
    }
    base.update(overrides)
    return base


def _mock_pipeline_result():
    return {
        "generated_prompt": GeneratedPrompt(
            prompt_text="Implement payment retry logic...",
            token_count=150,
            files_referenced=["payments/retry.py", "payments/gateway.py"],
            symbols_referenced=["retry_payment", "StripeGateway"],
        )
    }


def _patch_qdrant():
    """Return a context manager that mocks get_qdrant_for_project."""
    mock_qdrant_instance = MagicMock()
    mock_qdrant_instance.connect.return_value = None
    mock_qdrant_instance.close.return_value = None
    return patch(
        "api.routes.jira_routes.get_qdrant_for_project",
        return_value=mock_qdrant_instance,
    )


@patch("api.routes.jira_routes.run_pipeline")
def test_process_ticket_valid_request_returns_200(mock_run, client, mock_redis):
    mock_run.return_value = _mock_pipeline_result()
    with _patch_qdrant():
        response = client.post(PROJECT_URL, json=_make_ticket_payload())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "ticket_id" in data
    assert data["prompt_text"] == "Implement payment retry logic..."
    assert data["token_count"] == 150


@patch("api.routes.jira_routes.run_pipeline")
def test_process_ticket_missing_title_returns_422(mock_run, client):
    payload = _make_ticket_payload()
    del payload["title"]
    with _patch_qdrant():
        response = client.post(PROJECT_URL, json=payload)
    assert response.status_code == 422


@patch("api.routes.jira_routes.run_pipeline")
def test_process_ticket_empty_title_returns_422(mock_run, client):
    with _patch_qdrant():
        response = client.post(PROJECT_URL, json=_make_ticket_payload(title=""))
    assert response.status_code == 422


@patch("api.routes.jira_routes.run_pipeline")
def test_process_ticket_caches_result(mock_run, client, mock_redis):
    mock_run.return_value = _mock_pipeline_result()
    with _patch_qdrant():
        response = client.post(PROJECT_URL, json=_make_ticket_payload())
    assert response.status_code == 200
    ticket_id = response.json()["ticket_id"]
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    expected_key = f"test-org-id:prompt:test-project-id:{ticket_id}"
    assert call_args[0][0] == expected_key


@patch("api.routes.jira_routes.run_pipeline")
def test_process_ticket_pipeline_error_returns_500(mock_run, client):
    mock_run.side_effect = RuntimeError("Pipeline exploded")
    with _patch_qdrant():
        response = client.post(PROJECT_URL, json=_make_ticket_payload())
    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "pipeline_error"


@patch("api.routes.jira_routes.run_pipeline")
def test_process_ticket_returns_all_prompt_fields(mock_run, client):
    mock_run.return_value = _mock_pipeline_result()
    with _patch_qdrant():
        response = client.post(PROJECT_URL, json=_make_ticket_payload())
    data = response.json()
    assert data["files_referenced"] == ["payments/retry.py", "payments/gateway.py"]
    assert data["symbols_referenced"] == ["retry_payment", "StripeGateway"]


@patch("api.routes.jira_routes.run_pipeline")
def test_process_ticket_with_optional_fields(mock_run, client):
    mock_run.return_value = _mock_pipeline_result()
    payload = {
        "title": "Simple fix",
        "description": "Fix a thing",
    }
    with _patch_qdrant():
        response = client.post(PROJECT_URL, json=payload)
    assert response.status_code == 200
