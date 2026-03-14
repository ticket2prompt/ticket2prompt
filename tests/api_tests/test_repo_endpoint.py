"""Tests for POST /projects/{project_id}/index endpoint."""

from unittest.mock import MagicMock, patch

INDEX_URL = "/projects/test-project-id/index"


def test_index_repo_valid_request_returns_202(client):
    mock_task = MagicMock()
    mock_task.id = "fake-task-id"
    with patch("api.routes.repo_routes.index_repository_full") as mock_celery_task:
        mock_celery_task.delay.return_value = mock_task
        response = client.post(INDEX_URL)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "indexing_started"
    assert "job_id" in data
    assert data["repo_url"] == "https://github.com/org/repo.git"


def test_index_repo_sets_cache_status(client, mock_redis):
    mock_task = MagicMock()
    mock_task.id = "fake-task-id-123"
    with patch("api.routes.repo_routes.index_repository_full") as mock_celery_task:
        mock_celery_task.delay.return_value = mock_task
        response = client.post(INDEX_URL)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert job_id == "fake-task-id-123"
    mock_redis.set.assert_called()
    call_args = mock_redis.set.call_args_list[0]
    expected_key = f"test-org-id:indexing:{job_id}"
    assert call_args[0][0] == expected_key
    assert call_args[0][1]["status"] == "in_progress"


def test_index_repo_default_branch_is_main(client):
    mock_task = MagicMock()
    mock_task.id = "fake-task-id"
    with patch("api.routes.repo_routes.index_repository_full") as mock_celery_task:
        mock_celery_task.delay.return_value = mock_task
        response = client.post(INDEX_URL)
    assert response.status_code == 202


def test_index_repo_dispatches_celery_task_with_correct_args(client):
    """POST /projects/{project_id}/index should dispatch index_repository_full.delay with 5 args."""
    mock_task = MagicMock()
    mock_task.id = "celery-task-abc"
    with patch("api.routes.repo_routes.index_repository_full") as mock_celery_task:
        mock_celery_task.delay.return_value = mock_task
        response = client.post(INDEX_URL)
    assert response.status_code == 202
    mock_celery_task.delay.assert_called_once_with(
        "https://github.com/org/repo.git",
        "org/repo",
        "main",
        "test-project-id",
        "test-org-id",
    )


def test_get_index_status_returns_cached_status(client, mock_redis):
    """GET /projects/{project_id}/index/{job_id} should return cached status when present."""
    mock_redis.get.return_value = {"status": "completed", "files_indexed": 10}
    response = client.get(f"{INDEX_URL}/some-job-id")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["files_indexed"] == 10


def test_get_index_status_returns_unknown_when_not_cached(client, mock_redis):
    """GET /projects/{project_id}/index/{job_id} returns unknown status when cache has no entry."""
    mock_redis.get.return_value = None
    response = client.get(f"{INDEX_URL}/missing-job-id")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unknown"
    assert data["job_id"] == "missing-job-id"


def test_get_index_status_checks_correct_cache_key(client, mock_redis):
    """GET /projects/{project_id}/index/{job_id} should look up the scoped cache key."""
    mock_redis.get.return_value = None
    client.get(f"{INDEX_URL}/my-job-id")
    mock_redis.get.assert_called_once_with("test-org-id:indexing:my-job-id")
