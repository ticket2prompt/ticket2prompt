"""Tests for api/routes/auth_routes.py."""

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

FAKE_MEMBER_USER = CurrentUser(
    user_id=USER_ID,
    email="member@test.com",
    display_name="Member User",
    org_id=ORG_ID,
    role="member",
)


@pytest.fixture
def mock_postgres():
    return MagicMock()


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.jwt_secret = "test-secret-key-that-is-long-enough-for-hmac"
    s.jwt_expiry_hours = 24
    return s


def make_app(mock_postgres, mock_settings, current_user=FAKE_ADMIN_USER):
    application = create_app()
    application.dependency_overrides[get_postgres] = lambda: mock_postgres
    application.dependency_overrides[get_settings_dep] = lambda: mock_settings
    application.dependency_overrides[get_current_user] = lambda: current_user
    application.dependency_overrides[require_org_admin] = lambda: current_user
    return application


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

class TestRegister:
    def _payload(self, **overrides):
        base = {
            "email": "new@example.com",
            "password": "secret123",
            "display_name": "New User",
            "org_name": "New Org",
            "org_slug": "new-org",
        }
        base.update(overrides)
        return base

    def test_register_creates_user_and_org(self, mock_postgres, mock_settings):
        mock_postgres_instance = mock_postgres
        app = make_app(mock_postgres_instance, mock_settings)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.auth_routes.get_user_by_email", return_value=None), \
             patch("api.routes.auth_routes.create_user", return_value={"user_id": USER_ID, "email": "new@example.com", "display_name": "New User"}), \
             patch("api.routes.auth_routes.create_org", return_value={"org_id": ORG_ID, "name": "New Org", "slug": "new-org"}), \
             patch("api.routes.auth_routes.add_org_member", return_value={"user_id": USER_ID, "org_id": ORG_ID, "role": "org_admin"}), \
             patch("api.routes.auth_routes.create_access_token", return_value=("token123", 86400)):
            resp = client.post("/auth/register", json=self._payload())

        assert resp.status_code == 201
        data = resp.json()
        assert data["access_token"] == "token123"
        assert data["token_type"] == "bearer"

    def test_register_returns_409_if_email_taken(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings)
        client = TestClient(app, raise_server_exceptions=False)

        existing_user = {"user_id": "existing", "email": "new@example.com"}
        with patch("api.routes.auth_routes.get_user_by_email", return_value=existing_user):
            resp = client.post("/auth/register", json=self._payload())

        assert resp.status_code == 409

    def test_register_missing_fields_returns_422(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/auth/register", json={"email": "only@example.com"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_valid_credentials_return_token(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings)
        client = TestClient(app, raise_server_exceptions=False)

        user = {
            "user_id": USER_ID,
            "email": "user@example.com",
            "password_hash": "$2b$12$xxxxxx",
            "is_active": True,
        }
        orgs = [{"org_id": ORG_ID, "name": "My Org", "role": "member"}]

        with patch("api.routes.auth_routes.get_user_by_email", return_value=user), \
             patch("api.routes.auth_routes.verify_password", return_value=True), \
             patch("api.routes.auth_routes.create_access_token", return_value=("jwt-token", 86400)):
            mock_postgres.list_orgs_for_user.return_value = orgs
            resp = client.post("/auth/login", json={"email": "user@example.com", "password": "pass"})

        assert resp.status_code == 200
        assert resp.json()["access_token"] == "jwt-token"

    def test_invalid_password_returns_401(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings)
        client = TestClient(app, raise_server_exceptions=False)

        user = {
            "user_id": USER_ID,
            "email": "user@example.com",
            "password_hash": "hash",
        }
        with patch("api.routes.auth_routes.get_user_by_email", return_value=user), \
             patch("api.routes.auth_routes.verify_password", return_value=False):
            resp = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong"})

        assert resp.status_code == 401

    def test_unknown_user_returns_401(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.auth_routes.get_user_by_email", return_value=None):
            resp = client.post("/auth/login", json={"email": "ghost@example.com", "password": "x"})

        assert resp.status_code == 401

    def test_no_org_membership_returns_403(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings)
        client = TestClient(app, raise_server_exceptions=False)

        user = {"user_id": USER_ID, "email": "u@u.com", "password_hash": "h"}
        with patch("api.routes.auth_routes.get_user_by_email", return_value=user), \
             patch("api.routes.auth_routes.verify_password", return_value=True):
            mock_postgres.list_orgs_for_user.return_value = []
            resp = client.post("/auth/login", json={"email": "u@u.com", "password": "pass"})

        assert resp.status_code == 403

    def test_disabled_account_returns_403(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings)
        client = TestClient(app, raise_server_exceptions=False)

        user = {
            "user_id": USER_ID,
            "email": "u@u.com",
            "password_hash": "h",
            "is_active": False,
        }
        with patch("api.routes.auth_routes.get_user_by_email", return_value=user), \
             patch("api.routes.auth_routes.verify_password", return_value=True):
            resp = client.post("/auth/login", json={"email": "u@u.com", "password": "pass"})

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

class TestMe:
    def test_returns_current_user(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings, current_user=FAKE_MEMBER_USER)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/auth/me")

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == USER_ID
        assert data["role"] == "member"


# ---------------------------------------------------------------------------
# POST /auth/api-keys
# ---------------------------------------------------------------------------

class TestCreateApiKey:
    def test_org_admin_can_create_key(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings, current_user=FAKE_ADMIN_USER)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.auth_routes.create_api_key") as mock_create, \
             patch("api.routes.auth_routes.generate_api_key", return_value=("ttp_rawkey", "sha256hash", "ttp_raw")):
            mock_create.return_value = {
                "key_id": "key1",
                "org_id": ORG_ID,
                "key_prefix": "ttp_raw",
                "description": "CI Key",
                "is_active": True,
                "expires_at": None,
            }
            resp = client.post("/auth/api-keys", json={"description": "CI Key"})

        assert resp.status_code == 201
        data = resp.json()
        assert data["key"] == "ttp_rawkey"
        assert data["key_prefix"] == "ttp_raw"
        assert data["description"] == "CI Key"

    def test_api_key_with_expiry(self, mock_postgres, mock_settings):
        app = make_app(mock_postgres, mock_settings, current_user=FAKE_ADMIN_USER)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routes.auth_routes.create_api_key") as mock_create, \
             patch("api.routes.auth_routes.generate_api_key", return_value=("ttp_rawkey", "sha256hash", "ttp_raw")):
            mock_create.return_value = {
                "key_id": "key1",
                "org_id": ORG_ID,
                "key_prefix": "ttp_raw",
                "description": "Expiring",
                "is_active": True,
                "expires_at": None,
            }
            resp = client.post(
                "/auth/api-keys",
                json={"description": "Expiring", "expires_in_days": 30},
            )

        assert resp.status_code == 201
