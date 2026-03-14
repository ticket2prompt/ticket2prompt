"""Tests for GET /projects/{project_id}/prompt/{ticket_id} endpoint."""

PROJECT_BASE = "/projects/test-project-id/prompt"


def test_get_prompt_found_returns_200(client, mock_redis):
    cached_data = {
        "prompt_text": "Do the thing...",
        "token_count": 100,
        "files_referenced": ["src/main.py"],
        "symbols_referenced": ["main"],
    }
    mock_redis.get.return_value = cached_data
    response = client.get(f"{PROJECT_BASE}/test-ticket-123")
    assert response.status_code == 200
    data = response.json()
    assert data["ticket_id"] == "test-ticket-123"
    assert data["prompt_text"] == "Do the thing..."
    assert data["token_count"] == 100


def test_get_prompt_not_found_returns_404(client, mock_redis):
    mock_redis.get.return_value = None
    response = client.get(f"{PROJECT_BASE}/nonexistent-id")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "ticket_not_found"


def test_get_prompt_response_matches_cached_data(client, mock_redis):
    cached_data = {
        "prompt_text": "Implement feature X...",
        "token_count": 250,
        "files_referenced": ["a.py", "b.py"],
        "symbols_referenced": ["foo", "bar", "baz"],
    }
    mock_redis.get.return_value = cached_data
    response = client.get(f"{PROJECT_BASE}/abc-def")
    data = response.json()
    assert data["files_referenced"] == ["a.py", "b.py"]
    assert data["symbols_referenced"] == ["foo", "bar", "baz"]


def test_get_prompt_checks_correct_cache_key(client, mock_redis):
    mock_redis.get.return_value = None
    client.get(f"{PROJECT_BASE}/my-ticket-id")
    mock_redis.get.assert_called_once_with(
        "test-org-id:prompt:test-project-id:my-ticket-id"
    )


def test_get_prompt_cache_error_returns_500(client, mock_redis):
    mock_redis.get.side_effect = Exception("Redis down")
    response = client.get(f"{PROJECT_BASE}/some-id")
    assert response.status_code == 500
