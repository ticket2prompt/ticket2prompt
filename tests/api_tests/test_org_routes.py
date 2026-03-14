"""Tests for api/routes/org_routes.py."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.dependencies import get_postgres, get_settings_dep
from auth.middleware import get_current_user, require_org_admin
from auth.models import CurrentUser

ORG_ID = "test-org-id"
USER_ID = "test-user-id"

FAKE_ADMIN_USER = CurrentUser(
    user_id=USER_ID,
    email="admin@test.com",
    display_name="Admin User",
    org_id=ORG_ID,
    role="org_admin",
)

FAKE_ORG = {
    "org_id": ORG_ID,
    "name": "Test Org",
    "slug": "test-org",
    "created_at": "2024-01-01 00:00:00",
}


def make_app(postgres, current_user=FAKE_ADMIN_USER):
    application = create_app()
    application.dependency_overrides[get_postgres] = lambda: postgres
    application.dependency_overrides[get_settings_dep] = lambda: MagicMock()
    application.dependency_overrides[get_current_user] = lambda: current_user
    application.dependency_overrides[require_org_admin] = lambda: current_user
    return application


# ---------------------------------------------------------------------------
# POST /orgs — create_org
# ---------------------------------------------------------------------------

class TestCreateOrg:
    def test_creates_org_successfully(self):
        postgres = MagicMock()
        postgres.create_org.return_value = FAKE_ORG
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.org_routes.add_org_member", return_value={"role": "org_admin"}):
            resp = client.post("/orgs", json={"name": "Test Org", "slug": "test-org"})

        assert resp.status_code == 201
        data = resp.json()
        assert data["org_id"] == ORG_ID
        assert data["name"] == "Test Org"
        assert data["slug"] == "test-org"

    def test_invalid_slug_returns_422(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/orgs", json={"name": "Test Org", "slug": "INVALID SLUG"})
        assert resp.status_code == 422

    def test_missing_fields_returns_422(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/orgs", json={"name": "Only Name"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /orgs — list_orgs
# ---------------------------------------------------------------------------

class TestListOrgs:
    def test_returns_user_orgs(self):
        postgres = MagicMock()
        postgres.list_orgs_for_user.return_value = [FAKE_ORG]
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/orgs")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["org_id"] == ORG_ID

    def test_returns_empty_list_when_no_orgs(self):
        postgres = MagicMock()
        postgres.list_orgs_for_user.return_value = []
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/orgs")

        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /orgs/{org_id} — get_org
# ---------------------------------------------------------------------------

class TestGetOrg:
    def test_returns_org_when_member(self):
        postgres = MagicMock()
        postgres.get_org.return_value = FAKE_ORG
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("auth.postgres_auth.get_org_membership", return_value={"role": "member"}):
            resp = client.get(f"/orgs/{ORG_ID}")

        assert resp.status_code == 200
        assert resp.json()["org_id"] == ORG_ID

    def test_returns_403_when_not_member(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("auth.postgres_auth.get_org_membership", return_value=None):
            resp = client.get(f"/orgs/{ORG_ID}")

        assert resp.status_code == 403

    def test_returns_404_when_org_not_found(self):
        postgres = MagicMock()
        postgres.get_org.return_value = None
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("auth.postgres_auth.get_org_membership", return_value={"role": "member"}):
            resp = client.get("/orgs/no-such-org")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /orgs/{org_id}/members — add_member
# ---------------------------------------------------------------------------

class TestAddMember:
    def test_admin_can_add_member(self):
        postgres = MagicMock()
        target_user = {
            "user_id": "other-user-id",
            "email": "other@test.com",
            "display_name": "Other User",
        }
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.org_routes.get_user_by_email", return_value=target_user), \
             patch("api.routes.org_routes.add_org_member", return_value={"role": "member"}):
            resp = client.post(
                f"/orgs/{ORG_ID}/members",
                json={"email": "other@test.com", "role": "member"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "other-user-id"
        assert data["role"] == "member"

    def test_wrong_org_returns_403(self):
        """Admin of org-A cannot add members to org-B."""
        postgres = MagicMock()
        different_org_admin = CurrentUser(
            user_id=USER_ID, email="a@b.com", display_name="A",
            org_id="different-org-id", role="org_admin",
        )
        app = make_app(postgres, current_user=different_org_admin)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            f"/orgs/{ORG_ID}/members",
            json={"email": "other@test.com", "role": "member"},
        )

        assert resp.status_code == 403

    def test_target_user_not_found_returns_404(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.org_routes.get_user_by_email", return_value=None):
            resp = client.post(
                f"/orgs/{ORG_ID}/members",
                json={"email": "ghost@test.com", "role": "member"},
            )

        assert resp.status_code == 404

    def test_invalid_role_returns_422(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            f"/orgs/{ORG_ID}/members",
            json={"email": "u@u.com", "role": "super_admin"},  # invalid role
        )
        assert resp.status_code == 422
