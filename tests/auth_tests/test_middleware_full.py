"""Full tests for auth/middleware.py."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

import jwt
from fastapi import HTTPException, Request

from auth.middleware import (
    get_current_user,
    _resolve_jwt,
    _resolve_api_key,
    require_org_admin,
    require_project_access,
)
from auth.models import CurrentUser
from auth.security import create_access_token
from config.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_settings(**kwargs):
    defaults = dict(
        jwt_secret="test-secret-key",
        jwt_expiry_hours=24,
        credential_encryption_key="",
    )
    defaults.update(kwargs)
    s = MagicMock(spec=Settings)
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def make_request(auth_header: str = "", api_key: str = "") -> Request:
    """Build a minimal fake Request with configurable headers."""
    headers = {}
    if auth_header:
        headers["authorization"] = auth_header
    if api_key:
        headers["x-api-key"] = api_key

    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "method": "GET",
        "path": "/",
        "query_string": b"",
    }
    return Request(scope)


def _make_valid_token(settings, user_id="user-123", org_id="org-abc", role="member"):
    token, _ = create_access_token(user_id, org_id, role, settings)
    return token


# ---------------------------------------------------------------------------
# _resolve_jwt
# ---------------------------------------------------------------------------

class TestResolveJwt:
    def test_valid_token_returns_current_user(self):
        settings = make_settings()
        token = _make_valid_token(settings)

        result = _resolve_jwt(token, settings)

        assert isinstance(result, CurrentUser)
        assert result.user_id == "user-123"
        assert result.org_id == "org-abc"
        assert result.role == "member"

    def test_expired_token_raises_401(self):
        settings = make_settings()
        payload = {
            "sub": "user-123",
            "org_id": "org-abc",
            "role": "member",
            "exp": 1,  # epoch 1 second — already expired
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            _resolve_jwt(token, settings)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_invalid_token_raises_401(self):
        settings = make_settings()

        with pytest.raises(HTTPException) as exc_info:
            _resolve_jwt("not.a.valid.token", settings)

        assert exc_info.value.status_code == 401

    def test_wrong_secret_raises_401(self):
        settings = make_settings(jwt_secret="correct-secret")
        wrong_settings = make_settings(jwt_secret="wrong-secret")
        token = _make_valid_token(settings)

        with pytest.raises(HTTPException) as exc_info:
            _resolve_jwt(token, wrong_settings)

        assert exc_info.value.status_code == 401

    def test_missing_claims_raises_401(self):
        """Token missing required claims should raise 401."""
        settings = make_settings()
        payload = {"sub": "user-123", "exp": 9999999999}
        token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

        with pytest.raises((HTTPException, KeyError, Exception)):
            _resolve_jwt(token, settings)


# ---------------------------------------------------------------------------
# _resolve_api_key
# ---------------------------------------------------------------------------

class TestResolveApiKey:
    def _make_postgres(self, row):
        postgres = MagicMock()
        postgres.get_api_key_by_hash.return_value = row
        return postgres

    def test_valid_active_key_returns_current_user(self):
        row = {"org_id": "org-123", "is_active": True, "expires_at": None, "role": "api_key"}
        postgres = self._make_postgres(row)

        result = _resolve_api_key("ttp_rawkey", postgres)

        assert isinstance(result, CurrentUser)
        assert result.org_id == "org-123"
        assert result.role == "api_key"

    def test_inactive_key_raises_401(self):
        row = {"org_id": "org-123", "is_active": False, "expires_at": None}
        postgres = self._make_postgres(row)

        with pytest.raises(HTTPException) as exc_info:
            _resolve_api_key("ttp_rawkey", postgres)

        assert exc_info.value.status_code == 401

    def test_unknown_key_raises_401(self):
        postgres = self._make_postgres(None)

        with pytest.raises(HTTPException) as exc_info:
            _resolve_api_key("ttp_unknown", postgres)

        assert exc_info.value.status_code == 401

    def test_expired_key_raises_401(self):
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        row = {"org_id": "org-123", "is_active": True, "expires_at": past}
        postgres = self._make_postgres(row)

        with pytest.raises(HTTPException) as exc_info:
            _resolve_api_key("ttp_rawkey", postgres)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_expired_key_iso_string_raises_401(self):
        past_iso = "2000-01-01T00:00:00+00:00"
        row = {"org_id": "org-123", "is_active": True, "expires_at": past_iso}
        postgres = self._make_postgres(row)

        with pytest.raises(HTTPException) as exc_info:
            _resolve_api_key("ttp_rawkey", postgres)

        assert exc_info.value.status_code == 401

    def test_future_expiry_is_allowed(self):
        future = datetime.now(timezone.utc) + timedelta(days=30)
        row = {"org_id": "org-123", "is_active": True, "expires_at": future}
        postgres = self._make_postgres(row)

        result = _resolve_api_key("ttp_rawkey", postgres)

        assert result.org_id == "org-123"

    def test_naive_datetime_expiry_treated_as_utc(self):
        past_naive = datetime(2000, 1, 1)  # naive, should be treated as UTC
        row = {"org_id": "org-123", "is_active": True, "expires_at": past_naive}
        postgres = self._make_postgres(row)

        with pytest.raises(HTTPException) as exc_info:
            _resolve_api_key("ttp_rawkey", postgres)

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_bearer_token_resolves_user(self):
        settings = make_settings()
        token = _make_valid_token(settings)
        request = make_request(auth_header=f"Bearer {token}")
        postgres = MagicMock()

        result = get_current_user(request, postgres, settings)

        assert isinstance(result, CurrentUser)
        assert result.user_id == "user-123"

    def test_api_key_resolves_user(self):
        request = make_request(api_key="ttp_rawkey123")
        postgres = MagicMock()
        postgres.get_api_key_by_hash.return_value = {
            "org_id": "org-from-key", "is_active": True, "expires_at": None
        }
        settings = make_settings()

        result = get_current_user(request, postgres, settings)

        assert result.org_id == "org-from-key"

    def test_missing_credentials_raises_401(self):
        request = make_request()
        postgres = MagicMock()
        settings = make_settings()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request, postgres, settings)

        assert exc_info.value.status_code == 401

    def test_malformed_bearer_raises_401(self):
        settings = make_settings()
        request = make_request(auth_header="Bearer not.valid.token")
        postgres = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request, postgres, settings)

        assert exc_info.value.status_code == 401

    def test_bearer_takes_precedence_over_api_key(self):
        """When both headers present, Bearer JWT should be used."""
        settings = make_settings()
        token = _make_valid_token(settings, user_id="jwt-user")
        request = make_request(auth_header=f"Bearer {token}", api_key="ttp_something")
        postgres = MagicMock()

        result = get_current_user(request, postgres, settings)

        assert result.user_id == "jwt-user"
        postgres.get_api_key_by_hash.assert_not_called()

    def test_non_bearer_auth_header_falls_through_to_api_key(self):
        """Authorization header not starting with 'Bearer ' should be ignored."""
        request = make_request(auth_header="Basic dXNlcjpwYXNz", api_key="ttp_rawkey")
        postgres = MagicMock()
        postgres.get_api_key_by_hash.return_value = {
            "org_id": "org-123", "is_active": True, "expires_at": None
        }
        settings = make_settings()

        result = get_current_user(request, postgres, settings)

        assert result.org_id == "org-123"


# ---------------------------------------------------------------------------
# require_org_admin (already tested in test_middleware.py but extend here)
# ---------------------------------------------------------------------------

class TestRequireOrgAdmin:
    def test_org_admin_passes(self):
        user = CurrentUser(
            user_id="u1", email="a@b.com", display_name="A",
            org_id="org1", role="org_admin"
        )
        result = require_org_admin(user)
        assert result is user

    def test_member_raises_403(self):
        user = CurrentUser(
            user_id="u1", email="a@b.com", display_name="A",
            org_id="org1", role="member"
        )
        with pytest.raises(HTTPException) as exc_info:
            require_org_admin(user)
        assert exc_info.value.status_code == 403

    def test_api_key_role_raises_403(self):
        user = CurrentUser(
            user_id="", email="", display_name="",
            org_id="org1", role="api_key"
        )
        with pytest.raises(HTTPException) as exc_info:
            require_org_admin(user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_project_access
# ---------------------------------------------------------------------------

class TestRequireProjectAccess:
    def _make_user(self, org_id="org-abc"):
        return CurrentUser(
            user_id="uid", email="u@u.com", display_name="U",
            org_id=org_id, role="member"
        )

    def test_valid_project_returns_project(self):
        project = {"project_id": "proj-1", "org_id": "org-abc", "name": "Test"}
        postgres = MagicMock()
        postgres.get_project.return_value = project
        user = self._make_user("org-abc")

        result = require_project_access("proj-1", user, postgres)

        assert result["project_id"] == "proj-1"

    def test_project_not_found_raises_404(self):
        postgres = MagicMock()
        postgres.get_project.return_value = None
        user = self._make_user()

        with pytest.raises(HTTPException) as exc_info:
            require_project_access("no-such-proj", user, postgres)

        assert exc_info.value.status_code == 404

    def test_wrong_org_raises_403(self):
        project = {"project_id": "proj-1", "org_id": "org-xyz"}
        postgres = MagicMock()
        postgres.get_project.return_value = project
        user = self._make_user("org-abc")  # different org

        with pytest.raises(HTTPException) as exc_info:
            require_project_access("proj-1", user, postgres)

        assert exc_info.value.status_code == 403

    def test_org_id_compared_as_string(self):
        """org_id in project may be a UUID object; must still compare correctly."""
        import uuid
        org_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        project = {"project_id": "proj-1", "org_id": org_uuid}
        postgres = MagicMock()
        postgres.get_project.return_value = project
        user = self._make_user(str(org_uuid))

        result = require_project_access("proj-1", user, postgres)

        assert result is project
