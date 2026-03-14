"""Tests for storage/migrations.py."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch, mock_open

import pytest

from storage.migrations import (
    apply_multi_tenant_migration,
    apply_schema,
    get_schema_sql,
    _MULTI_TENANT_MIGRATION_SQL,
    SCHEMA_PATH,
)


# ---------------------------------------------------------------------------
# get_schema_sql
# ---------------------------------------------------------------------------

class TestGetSchemaSql:
    def test_returns_string(self):
        sql = get_schema_sql()
        assert isinstance(sql, str)

    def test_returns_non_empty_string(self):
        sql = get_schema_sql()
        assert len(sql) > 0

    def test_schema_path_exists(self):
        assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"

    def test_reads_from_schema_path(self):
        fake_sql = "CREATE TABLE test (id SERIAL PRIMARY KEY);"
        with patch.object(Path, "read_text", return_value=fake_sql):
            result = get_schema_sql()
        assert result == fake_sql


# ---------------------------------------------------------------------------
# apply_schema
# ---------------------------------------------------------------------------

class TestApplySchema:
    def _make_conn_mock(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_executes_schema_sql(self):
        mock_conn, mock_cursor = self._make_conn_mock()
        fake_sql = "CREATE TABLE foo (id INT);"

        with patch("storage.migrations.get_schema_sql", return_value=fake_sql), \
             patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            apply_schema("postgresql://localhost/testdb")

        mock_cursor.execute.assert_called_once_with(fake_sql)

    def test_commits_after_execution(self):
        mock_conn, _ = self._make_conn_mock()

        with patch("storage.migrations.get_schema_sql", return_value="SELECT 1;"), \
             patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            apply_schema("postgresql://localhost/testdb")

        mock_conn.commit.assert_called_once()

    def test_closes_connection_in_finally(self):
        mock_conn, _ = self._make_conn_mock()

        with patch("storage.migrations.get_schema_sql", return_value="SELECT 1;"), \
             patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            apply_schema("postgresql://localhost/testdb")

        mock_conn.close.assert_called_once()

    def test_closes_connection_on_execute_failure(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("syntax error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("storage.migrations.get_schema_sql", return_value="INVALID SQL;"), \
             patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            with pytest.raises(Exception, match="syntax error"):
                apply_schema("postgresql://localhost/testdb")

        mock_conn.close.assert_called_once()

    def test_does_not_commit_on_failure(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("storage.migrations.get_schema_sql", return_value="INVALID;"), \
             patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            with pytest.raises(Exception):
                apply_schema("postgresql://localhost/testdb")

        mock_conn.commit.assert_not_called()

    def test_uses_provided_conn_string(self):
        mock_conn, _ = self._make_conn_mock()
        conn_string = "postgresql://user:pass@host:5432/db"

        with patch("storage.migrations.get_schema_sql", return_value="SELECT 1;"), \
             patch("storage.migrations.psycopg2.connect", return_value=mock_conn) as mock_connect:
            apply_schema(conn_string)

        mock_connect.assert_called_once_with(conn_string)


# ---------------------------------------------------------------------------
# apply_multi_tenant_migration
# ---------------------------------------------------------------------------

class TestApplyMultiTenantMigration:
    def _make_conn_mock(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_executes_multi_tenant_sql(self):
        mock_conn, mock_cursor = self._make_conn_mock()

        with patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            apply_multi_tenant_migration("postgresql://localhost/testdb")

        mock_cursor.execute.assert_called_once_with(_MULTI_TENANT_MIGRATION_SQL)

    def test_commits_after_execution(self):
        mock_conn, _ = self._make_conn_mock()

        with patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            apply_multi_tenant_migration("postgresql://localhost/testdb")

        mock_conn.commit.assert_called_once()

    def test_closes_connection_in_finally(self):
        mock_conn, _ = self._make_conn_mock()

        with patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            apply_multi_tenant_migration("postgresql://localhost/testdb")

        mock_conn.close.assert_called_once()

    def test_closes_connection_on_execute_failure(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("column already exists")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            with pytest.raises(Exception):
                apply_multi_tenant_migration("postgresql://localhost/testdb")

        mock_conn.close.assert_called_once()

    def test_does_not_commit_on_failure(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("db error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("storage.migrations.psycopg2.connect", return_value=mock_conn):
            with pytest.raises(Exception):
                apply_multi_tenant_migration("postgresql://localhost/testdb")

        mock_conn.commit.assert_not_called()

    def test_uses_provided_conn_string(self):
        mock_conn, _ = self._make_conn_mock()
        conn_string = "postgresql://user:pass@host:5432/db"

        with patch("storage.migrations.psycopg2.connect", return_value=mock_conn) as mock_connect:
            apply_multi_tenant_migration(conn_string)

        mock_connect.assert_called_once_with(conn_string)

    def test_migration_sql_contains_add_column_if_not_exists(self):
        assert "ADD COLUMN IF NOT EXISTS" in _MULTI_TENANT_MIGRATION_SQL

    def test_migration_sql_covers_all_tables(self):
        for table in ("symbols", "files", "graph_edges", "git_metadata"):
            assert table in _MULTI_TENANT_MIGRATION_SQL

    def test_migration_sql_adds_org_id_and_project_id(self):
        assert "org_id" in _MULTI_TENANT_MIGRATION_SQL
        assert "project_id" in _MULTI_TENANT_MIGRATION_SQL
