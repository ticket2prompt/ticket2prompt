"""Tests for auth/postgres_auth.py CRUD operations."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import auth.postgres_auth as pg_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_postgres(fetchone=None, fetchall=None):
    """Return a minimal fake PostgresClient.

    The cursor context manager yields a mock cursor whose fetchone/fetchall
    return the supplied values.
    """
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []

    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    postgres = MagicMock()
    postgres._get_conn.return_value = conn
    return postgres, conn, cursor


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class TestCreateUser:
    def test_returns_user_dict(self):
        import uuid
        user_id = uuid.uuid4()
        postgres, conn, cursor = make_postgres(
            fetchone=(user_id, "alice@example.com", "Alice")
        )

        result = pg_auth.create_user(postgres, "alice@example.com", "hash123", "Alice")

        assert result["user_id"] == str(user_id)
        assert result["email"] == "alice@example.com"
        assert result["display_name"] == "Alice"
        conn.commit.assert_called_once()

    def test_rolls_back_on_error(self):
        postgres, conn, cursor = make_postgres()
        cursor.execute.side_effect = Exception("db error")

        with pytest.raises(Exception, match="db error"):
            pg_auth.create_user(postgres, "bad@example.com", "hash", "Bad")

        conn.rollback.assert_called_once()

    def test_releases_connection(self):
        import uuid
        postgres, conn, cursor = make_postgres(
            fetchone=(uuid.uuid4(), "x@x.com", "X")
        )
        pg_auth.create_user(postgres, "x@x.com", "h", "X")
        postgres._put_conn.assert_called_once_with(conn)

    def test_releases_connection_on_error(self):
        postgres, conn, cursor = make_postgres()
        cursor.execute.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            pg_auth.create_user(postgres, "x@x.com", "h", "X")

        postgres._put_conn.assert_called_once_with(conn)


class TestGetUserByEmail:
    def test_returns_user_when_found(self):
        row = {"user_id": "uid1", "email": "bob@example.com",
               "password_hash": "h", "display_name": "Bob", "created_at": "2024-01-01"}
        postgres, conn, cursor = make_postgres(fetchone=row)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_user_by_email(postgres, "bob@example.com")

        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_user_by_email(postgres, "nobody@example.com")

        assert result is None

    def test_releases_connection(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            pg_auth.get_user_by_email(postgres, "x@x.com")

        postgres._put_conn.assert_called_once_with(conn)


class TestGetUserById:
    def test_returns_user_when_found(self):
        row = {"user_id": "uid1", "email": "carol@example.com",
               "password_hash": "h", "display_name": "Carol", "created_at": "2024-01-01"}
        postgres, conn, cursor = make_postgres(fetchone=row)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_user_by_id(postgres, "uid1")

        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_user_by_id(postgres, "no-such-id")

        assert result is None

    def test_releases_connection(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            pg_auth.get_user_by_id(postgres, "uid1")

        postgres._put_conn.assert_called_once_with(conn)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

class TestCreateOrg:
    def test_returns_org_dict(self):
        import uuid
        org_id = uuid.uuid4()
        postgres, conn, cursor = make_postgres(
            fetchone=(org_id, "Acme Corp", "acme-corp")
        )

        result = pg_auth.create_org(postgres, "Acme Corp", "acme-corp")

        assert result["org_id"] == str(org_id)
        assert result["name"] == "Acme Corp"
        assert result["slug"] == "acme-corp"
        conn.commit.assert_called_once()

    def test_rolls_back_on_error(self):
        postgres, conn, cursor = make_postgres()
        cursor.execute.side_effect = Exception("unique violation")

        with pytest.raises(Exception):
            pg_auth.create_org(postgres, "Dup", "dup-slug")

        conn.rollback.assert_called_once()

    def test_releases_connection(self):
        import uuid
        postgres, conn, cursor = make_postgres(
            fetchone=(uuid.uuid4(), "My Org", "my-org")
        )
        pg_auth.create_org(postgres, "My Org", "my-org")
        postgres._put_conn.assert_called_once_with(conn)


class TestGetOrg:
    def test_returns_org_when_found(self):
        row = {"org_id": "org1", "name": "Acme", "slug": "acme", "created_at": "2024-01-01"}
        postgres, conn, cursor = make_postgres(fetchone=row)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_org(postgres, "org1")

        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_org(postgres, "no-such-org")

        assert result is None

    def test_releases_connection(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            pg_auth.get_org(postgres, "org1")

        postgres._put_conn.assert_called_once_with(conn)


# ---------------------------------------------------------------------------
# Organization memberships
# ---------------------------------------------------------------------------

class TestAddOrgMember:
    def test_returns_membership_dict(self):
        import uuid
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        postgres, conn, cursor = make_postgres(
            fetchone=(user_id, org_id, "member")
        )

        result = pg_auth.add_org_member(postgres, str(user_id), str(org_id), "member")

        assert result["user_id"] == str(user_id)
        assert result["org_id"] == str(org_id)
        assert result["role"] == "member"
        conn.commit.assert_called_once()

    def test_rolls_back_on_error(self):
        postgres, conn, cursor = make_postgres()
        cursor.execute.side_effect = Exception("duplicate key")

        with pytest.raises(Exception):
            pg_auth.add_org_member(postgres, "uid", "oid", "member")

        conn.rollback.assert_called_once()

    def test_releases_connection(self):
        import uuid
        postgres, conn, cursor = make_postgres(
            fetchone=(uuid.uuid4(), uuid.uuid4(), "org_admin")
        )
        pg_auth.add_org_member(postgres, "uid", "oid", "org_admin")
        postgres._put_conn.assert_called_once_with(conn)


class TestGetOrgMembership:
    def test_returns_membership_when_found(self):
        row = {"user_id": "uid1", "org_id": "org1", "role": "member", "joined_at": "2024-01-01"}
        postgres, conn, cursor = make_postgres(fetchone=row)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_org_membership(postgres, "uid1", "org1")

        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_org_membership(postgres, "uid1", "org1")

        assert result is None

    def test_releases_connection(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            pg_auth.get_org_membership(postgres, "uid1", "org1")

        postgres._put_conn.assert_called_once_with(conn)


class TestListOrgsForUser:
    def test_returns_list_of_orgs(self):
        rows = [
            {"org_id": "org1", "name": "Org One", "slug": "org-one", "role": "member", "joined_at": "2024-01-01"},
            {"org_id": "org2", "name": "Org Two", "slug": "org-two", "role": "org_admin", "joined_at": "2024-02-01"},
        ]
        postgres, conn, cursor = make_postgres(fetchall=rows)
        cursor.fetchall.return_value = rows

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.list_orgs_for_user(postgres, "uid1")

        assert len(result) == 2
        assert result[0]["name"] == "Org One"
        assert result[1]["role"] == "org_admin"

    def test_returns_empty_list_when_no_orgs(self):
        postgres, conn, cursor = make_postgres(fetchall=[])
        cursor.fetchall.return_value = []

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.list_orgs_for_user(postgres, "uid-with-no-orgs")

        assert result == []

    def test_releases_connection(self):
        postgres, conn, cursor = make_postgres(fetchall=[])
        cursor.fetchall.return_value = []

        with patch("psycopg2.extras.RealDictCursor"):
            pg_auth.list_orgs_for_user(postgres, "uid1")

        postgres._put_conn.assert_called_once_with(conn)


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

class TestCreateApiKey:
    def test_returns_api_key_dict_without_expiry(self):
        import uuid
        key_id = uuid.uuid4()
        org_id = uuid.uuid4()
        postgres, conn, cursor = make_postgres(
            fetchone=(key_id, org_id, "ttp_abcd", "My API Key", True, None)
        )

        result = pg_auth.create_api_key(
            postgres, str(org_id), "sha256hash", "ttp_abcd", "My API Key", None
        )

        assert result["key_id"] == str(key_id)
        assert result["org_id"] == str(org_id)
        assert result["key_prefix"] == "ttp_abcd"
        assert result["description"] == "My API Key"
        assert result["is_active"] is True
        assert result["expires_at"] is None
        conn.commit.assert_called_once()

    def test_returns_api_key_dict_with_expiry(self):
        import uuid
        key_id = uuid.uuid4()
        org_id = uuid.uuid4()
        expires = datetime(2026, 1, 1, tzinfo=timezone.utc)
        postgres, conn, cursor = make_postgres(
            fetchone=(key_id, org_id, "ttp_abcd", "Expiring Key", True, expires)
        )

        result = pg_auth.create_api_key(
            postgres, str(org_id), "sha256hash", "ttp_abcd", "Expiring Key", expires
        )

        assert result["expires_at"] == expires.isoformat()

    def test_rolls_back_on_error(self):
        postgres, conn, cursor = make_postgres()
        cursor.execute.side_effect = Exception("db error")

        with pytest.raises(Exception):
            pg_auth.create_api_key(postgres, "org1", "hash", "prefix", "desc", None)

        conn.rollback.assert_called_once()

    def test_releases_connection(self):
        import uuid
        postgres, conn, cursor = make_postgres(
            fetchone=(uuid.uuid4(), uuid.uuid4(), "ttp_", "desc", True, None)
        )
        pg_auth.create_api_key(postgres, "org1", "hash", "prefix", "desc", None)
        postgres._put_conn.assert_called_once_with(conn)


class TestGetApiKeyByHash:
    def test_returns_key_when_found(self):
        row = {
            "key_id": "key1", "org_id": "org1", "key_prefix": "ttp_abc",
            "description": "Test key", "is_active": True, "expires_at": None,
        }
        postgres, conn, cursor = make_postgres(fetchone=row)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_api_key_by_hash(postgres, "sha256hash")

        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            result = pg_auth.get_api_key_by_hash(postgres, "no-such-hash")

        assert result is None

    def test_releases_connection(self):
        postgres, conn, cursor = make_postgres(fetchone=None)

        with patch("psycopg2.extras.RealDictCursor"):
            pg_auth.get_api_key_by_hash(postgres, "hash")

        postgres._put_conn.assert_called_once_with(conn)
