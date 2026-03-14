"""Tests for api/routes/team_routes.py."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.dependencies import get_postgres, get_settings_dep
from auth.middleware import get_current_user
from auth.models import CurrentUser

ORG_ID = "test-org-id"
TEAM_ID = "test-team-id"
USER_ID = "test-user-id"

FAKE_USER = CurrentUser(
    user_id=USER_ID,
    email="user@test.com",
    display_name="Test User",
    org_id=ORG_ID,
    role="member",
)

FAKE_TEAM = {
    "team_id": TEAM_ID,
    "org_id": ORG_ID,
    "name": "Engineering",
    "created_at": "2024-01-01 00:00:00",
}


def make_app(postgres, current_user=FAKE_USER):
    application = create_app()
    application.dependency_overrides[get_postgres] = lambda: postgres
    application.dependency_overrides[get_settings_dep] = lambda: MagicMock()
    application.dependency_overrides[get_current_user] = lambda: current_user
    return application


# ---------------------------------------------------------------------------
# POST /orgs/{org_id}/teams — create_team
# ---------------------------------------------------------------------------

class TestCreateTeam:
    def test_creates_team_for_member(self):
        postgres = MagicMock()
        postgres.create_team.return_value = FAKE_TEAM
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.post(
                f"/orgs/{ORG_ID}/teams",
                json={"name": "Engineering"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["team_id"] == TEAM_ID
        assert data["name"] == "Engineering"
        assert data["org_id"] == ORG_ID

    def test_returns_403_when_not_member(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value=None):
            resp = client.post(
                f"/orgs/{ORG_ID}/teams",
                json={"name": "Engineering"},
            )

        assert resp.status_code == 403

    def test_missing_name_returns_422(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(f"/orgs/{ORG_ID}/teams", json={})
        assert resp.status_code == 422

    def test_empty_name_returns_422(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(f"/orgs/{ORG_ID}/teams", json={"name": ""})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /orgs/{org_id}/teams — list_teams
# ---------------------------------------------------------------------------

class TestListTeams:
    def test_returns_list_of_teams(self):
        postgres = MagicMock()
        postgres.list_teams.return_value = [FAKE_TEAM]
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.get(f"/orgs/{ORG_ID}/teams")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["team_id"] == TEAM_ID

    def test_returns_empty_list_when_no_teams(self):
        postgres = MagicMock()
        postgres.list_teams.return_value = []
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.get(f"/orgs/{ORG_ID}/teams")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_403_when_not_member(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value=None):
            resp = client.get(f"/orgs/{ORG_ID}/teams")

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /orgs/{org_id}/teams/{team_id}/members — add_team_member
# ---------------------------------------------------------------------------

class TestAddTeamMember:
    def test_adds_member_successfully(self):
        postgres = MagicMock()
        postgres.get_team.return_value = FAKE_TEAM
        postgres.add_team_member.return_value = {"role": "member"}
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.post(
                f"/orgs/{ORG_ID}/teams/{TEAM_ID}/members",
                json={"user_id": "other-user-id", "role": "member"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "added"
        assert data["team_id"] == TEAM_ID
        assert data["user_id"] == "other-user-id"
        assert data["role"] == "member"

    def test_returns_403_when_not_org_member(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value=None):
            resp = client.post(
                f"/orgs/{ORG_ID}/teams/{TEAM_ID}/members",
                json={"user_id": "uid", "role": "member"},
            )

        assert resp.status_code == 403

    def test_returns_404_when_team_not_found(self):
        postgres = MagicMock()
        postgres.get_team.return_value = None
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.post(
                f"/orgs/{ORG_ID}/teams/no-such-team/members",
                json={"user_id": "uid", "role": "member"},
            )

        assert resp.status_code == 404

    def test_returns_404_when_team_belongs_to_other_org(self):
        postgres = MagicMock()
        postgres.get_team.return_value = dict(FAKE_TEAM, org_id="other-org")
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.team_routes.get_org_membership", return_value={"role": "member"}):
            resp = client.post(
                f"/orgs/{ORG_ID}/teams/{TEAM_ID}/members",
                json={"user_id": "uid", "role": "member"},
            )

        assert resp.status_code == 404

    def test_invalid_role_returns_422(self):
        postgres = MagicMock()
        app = make_app(postgres)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            f"/orgs/{ORG_ID}/teams/{TEAM_ID}/members",
            json={"user_id": "uid", "role": "invalid_role"},
        )
        assert resp.status_code == 422
