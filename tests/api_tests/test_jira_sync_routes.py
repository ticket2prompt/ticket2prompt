"""Tests for api/routes/jira_sync_routes.py."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.dependencies import get_postgres, get_redis, get_settings_dep
from auth.middleware import get_current_user, require_project_access
from auth.models import CurrentUser

ORG_ID = "test-org-id"
PROJECT_ID = "test-project-id"
JOB_ID = "celery-job-id-abc"

FAKE_USER = CurrentUser(
    user_id="test-user-id",
    email="user@test.com",
    display_name="Test User",
    org_id=ORG_ID,
    role="member",
)

FAKE_PROJECT = {
    "project_id": PROJECT_ID,
    "org_id": ORG_ID,
    "name": "Test Project",
    "slug": "test-project",
    "github_repo_url": "https://github.com/org/repo.git",
    "default_branch": "main",
}


def make_app(postgres=None, redis=None, current_user=FAKE_USER, project=FAKE_PROJECT):
    application = create_app()
    application.dependency_overrides[get_postgres] = lambda: postgres or MagicMock()
    application.dependency_overrides[get_redis] = lambda: redis
    application.dependency_overrides[get_settings_dep] = lambda: MagicMock()
    application.dependency_overrides[get_current_user] = lambda: current_user
    application.dependency_overrides[require_project_access] = lambda: project
    return application


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/jira/sync — trigger_jira_sync
# ---------------------------------------------------------------------------

class TestTriggerJiraSync:
    def test_returns_202_with_job_id(self):
        mock_task = MagicMock()
        mock_task.id = JOB_ID
        app = make_app()
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.jira_sync_routes.sync_jira_tickets") as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = client.post(f"/projects/{PROJECT_ID}/jira/sync")

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "sync_started"
        assert data["job_id"] == JOB_ID

    def test_stores_status_in_cache(self):
        mock_task = MagicMock()
        mock_task.id = JOB_ID
        mock_cache = MagicMock()
        mock_cache.set.return_value = None
        app = make_app(redis=mock_cache)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.jira_sync_routes.sync_jira_tickets") as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = client.post(f"/projects/{PROJECT_ID}/jira/sync")

        assert resp.status_code == 202
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        # Verify the cached value includes project_id and status
        cached_value = call_args[0][1]
        assert cached_value["status"] == "in_progress"
        assert cached_value["project_id"] == PROJECT_ID

    def test_works_without_cache(self):
        """When cache is None, sync should still succeed."""
        mock_task = MagicMock()
        mock_task.id = JOB_ID
        app = make_app(redis=None)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.jira_sync_routes.sync_jira_tickets") as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = client.post(f"/projects/{PROJECT_ID}/jira/sync")

        assert resp.status_code == 202
        assert resp.json()["job_id"] == JOB_ID

    def test_calls_celery_with_project_id(self):
        mock_task = MagicMock()
        mock_task.id = JOB_ID
        app = make_app()
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.jira_sync_routes.sync_jira_tickets") as mock_celery:
            mock_celery.delay.return_value = mock_task
            client.post(f"/projects/{PROJECT_ID}/jira/sync")

        mock_celery.delay.assert_called_once_with(PROJECT_ID)


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/jira/sync/{job_id} — get_sync_status
# ---------------------------------------------------------------------------

class TestGetSyncStatus:
    def test_returns_cached_status(self):
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"status": "in_progress", "project_id": PROJECT_ID}
        app = make_app(redis=mock_cache)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(f"/projects/{PROJECT_ID}/jira/sync/{JOB_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["project_id"] == PROJECT_ID

    def test_returns_unknown_when_not_in_cache(self):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        app = make_app(redis=mock_cache)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(f"/projects/{PROJECT_ID}/jira/sync/{JOB_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unknown"
        assert data["job_id"] == JOB_ID

    def test_returns_unknown_when_cache_unavailable(self):
        app = make_app(redis=None)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(f"/projects/{PROJECT_ID}/jira/sync/{JOB_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unknown"
        assert data["job_id"] == JOB_ID

    def test_uses_scoped_key_for_cache_lookup(self):
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"status": "completed"}
        app = make_app(redis=mock_cache)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(f"/projects/{PROJECT_ID}/jira/sync/{JOB_ID}")

        assert resp.status_code == 200
        mock_cache.get.assert_called_once()
        # Verify the key includes the org_id and job_id
        call_key = mock_cache.get.call_args[0][0]
        assert ORG_ID in call_key
        assert JOB_ID in call_key
