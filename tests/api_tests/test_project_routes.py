"""Tests for api/routes/project_routes.py."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.dependencies import get_postgres, get_redis, get_qdrant, get_pipeline_config, get_settings_dep
from auth.middleware import get_current_user
from auth.models import CurrentUser

ORG_ID = "test-org-id"
PROJECT_ID = "test-project-id"

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
    "team_id": None,
    "name": "Test Project",
    "slug": "test-project",
    "github_repo_url": "https://github.com/org/repo.git",
    "default_branch": "main",
    "collection_group": None,
    "jira_base_url": None,
    "jira_email": None,
    "jira_api_token_encrypted": None,
    "github_token_encrypted": None,
    "created_at": "2024-01-01 00:00:00",
    "updated_at": "2024-01-01 00:00:00",
}


@pytest.fixture
def mock_postgres():
    m = MagicMock()
    m.get_org_membership.return_value = {"role": "member"}
    return m


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.credential_encryption_key = ""
    s.qdrant_url = "http://localhost:6333"
    s.embedding_dim = 384
    s.clone_base_dir = "/tmp/repos"
    return s


@pytest.fixture
def app(mock_postgres, mock_settings):
    application = create_app()
    application.dependency_overrides[get_postgres] = lambda: mock_postgres
    application.dependency_overrides[get_redis] = lambda: None
    application.dependency_overrides[get_qdrant] = lambda: MagicMock()
    application.dependency_overrides[get_pipeline_config] = lambda: MagicMock()
    application.dependency_overrides[get_settings_dep] = lambda: mock_settings
    application.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return application


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /orgs/{org_id}/projects — create
# ---------------------------------------------------------------------------

class TestCreateProject:
    def test_creates_project_successfully(self, client, mock_postgres):
        mock_postgres.get_org_membership.return_value = {"role": "member"}
        mock_postgres.create_project.return_value = FAKE_PROJECT

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.post(
                f"/orgs/{ORG_ID}/projects",
                json={
                    "name": "Test Project",
                    "slug": "test-project",
                    "github_repo_url": "https://github.com/org/repo.git",
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Project"
        assert data["slug"] == "test-project"

    def test_returns_403_when_not_member(self, client):
        with patch("api.routes.project_routes.get_org_membership", return_value=None):
            resp = client.post(
                f"/orgs/{ORG_ID}/projects",
                json={
                    "name": "Test Project",
                    "slug": "test-project",
                    "github_repo_url": "https://github.com/org/repo.git",
                },
            )

        assert resp.status_code == 403

    def test_invalid_slug_returns_422(self, client):
        resp = client.post(
            f"/orgs/{ORG_ID}/projects",
            json={
                "name": "Test Project",
                "slug": "INVALID SLUG!",  # violates pattern
                "github_repo_url": "https://github.com/org/repo.git",
            },
        )
        assert resp.status_code == 422

    def test_missing_required_fields_returns_422(self, client):
        resp = client.post(f"/orgs/{ORG_ID}/projects", json={"name": "Only Name"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /orgs/{org_id}/projects — list
# ---------------------------------------------------------------------------

class TestListProjects:
    def test_returns_list_of_projects(self, client, mock_postgres):
        mock_postgres.list_projects.return_value = [FAKE_PROJECT]

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.get(f"/orgs/{ORG_ID}/projects")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["project_id"] == PROJECT_ID

    def test_returns_empty_list_when_no_projects(self, client, mock_postgres):
        mock_postgres.list_projects.return_value = []

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.get(f"/orgs/{ORG_ID}/projects")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_403_when_not_member(self, client):
        with patch("api.routes.project_routes.get_org_membership", return_value=None):
            resp = client.get(f"/orgs/{ORG_ID}/projects")

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /orgs/{org_id}/projects/{project_id} — get
# ---------------------------------------------------------------------------

class TestGetProject:
    def test_returns_project_when_found(self, client, mock_postgres):
        mock_postgres.get_project.return_value = FAKE_PROJECT

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.get(f"/orgs/{ORG_ID}/projects/{PROJECT_ID}")

        assert resp.status_code == 200
        assert resp.json()["project_id"] == PROJECT_ID

    def test_returns_404_when_project_not_found(self, client, mock_postgres):
        mock_postgres.get_project.return_value = None

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.get(f"/orgs/{ORG_ID}/projects/no-such-project")

        assert resp.status_code == 404

    def test_returns_404_when_project_belongs_to_other_org(self, client, mock_postgres):
        project = dict(FAKE_PROJECT, org_id="other-org-id")
        mock_postgres.get_project.return_value = project

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.get(f"/orgs/{ORG_ID}/projects/{PROJECT_ID}")

        assert resp.status_code == 404

    def test_returns_403_when_not_member(self, client):
        with patch("api.routes.project_routes.get_org_membership", return_value=None):
            resp = client.get(f"/orgs/{ORG_ID}/projects/{PROJECT_ID}")

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /orgs/{org_id}/projects/{project_id} — update
# ---------------------------------------------------------------------------

class TestUpdateProject:
    def test_updates_project_successfully(self, client, mock_postgres):
        updated = dict(FAKE_PROJECT, name="Updated Name")
        mock_postgres.get_project.return_value = FAKE_PROJECT
        mock_postgres.update_project.return_value = updated

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.put(
                f"/orgs/{ORG_ID}/projects/{PROJECT_ID}",
                json={"name": "Updated Name"},
            )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_no_updates_returns_existing_project(self, client, mock_postgres):
        mock_postgres.get_project.return_value = FAKE_PROJECT

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.put(
                f"/orgs/{ORG_ID}/projects/{PROJECT_ID}",
                json={},  # all fields None → no updates
            )

        assert resp.status_code == 200

    def test_returns_404_when_project_not_found(self, client, mock_postgres):
        mock_postgres.get_project.return_value = None

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.put(
                f"/orgs/{ORG_ID}/projects/no-such",
                json={"name": "X"},
            )

        assert resp.status_code == 404

    def test_returns_403_when_not_member(self, client):
        with patch("api.routes.project_routes.get_org_membership", return_value=None):
            resp = client.put(
                f"/orgs/{ORG_ID}/projects/{PROJECT_ID}",
                json={"name": "X"},
            )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /orgs/{org_id}/projects/{project_id} — delete
# ---------------------------------------------------------------------------

class TestDeleteProject:
    def test_deletes_project_successfully(self, client, mock_postgres):
        mock_postgres.get_project.return_value = FAKE_PROJECT
        mock_postgres.delete_project.return_value = None

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}), \
             patch("api.routes.project_routes.get_qdrant_for_project") as mock_qdrant:
            mock_qdrant.return_value = MagicMock()
            resp = client.delete(f"/orgs/{ORG_ID}/projects/{PROJECT_ID}")

        assert resp.status_code == 204

    def test_returns_404_when_project_not_found(self, client, mock_postgres):
        mock_postgres.get_project.return_value = None

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.delete(f"/orgs/{ORG_ID}/projects/no-such")

        assert resp.status_code == 404

    def test_returns_403_when_not_member(self, client):
        with patch("api.routes.project_routes.get_org_membership", return_value=None):
            resp = client.delete(f"/orgs/{ORG_ID}/projects/{PROJECT_ID}")

        assert resp.status_code == 403

    def test_continues_if_qdrant_delete_fails(self, client, mock_postgres):
        """Qdrant failures are swallowed; project is still deleted."""
        mock_postgres.get_project.return_value = FAKE_PROJECT
        mock_postgres.delete_project.return_value = None

        with patch("api.routes.project_routes.get_org_membership", return_value={"role": "member"}), \
             patch("api.routes.project_routes.get_qdrant_for_project", side_effect=Exception("qdrant down")):
            resp = client.delete(f"/orgs/{ORG_ID}/projects/{PROJECT_ID}")

        assert resp.status_code == 204
        mock_postgres.delete_project.assert_called_once()
