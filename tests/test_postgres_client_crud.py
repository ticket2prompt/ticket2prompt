"""Comprehensive unit tests for PostgresClient covering all uncovered methods.

All tests use MagicMock to avoid requiring a real PostgreSQL instance.
"""

from unittest.mock import MagicMock, call, patch

import psycopg2.pool
import pytest

from storage.postgres import PostgresClient


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _make_client() -> PostgresClient:
    """Return a PostgresClient with a mocked pool attached."""
    client = PostgresClient.__new__(PostgresClient)
    client._conn_string = "postgresql://test:test@localhost:5432/testdb"
    client._min_conn = 1
    client._max_conn = 10
    client._pool = None

    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_pool.getconn.return_value = mock_conn
    client._pool = mock_pool

    # Attach for easy access in tests
    client._mock_pool = mock_pool
    client._mock_conn = mock_conn
    client._mock_cursor = mock_cursor

    return client


def _make_symbol_dict(
    symbol_id: str = "sym-1",
    name: str = "my_func",
    sym_type: str = "function",
    file_path: str = "src/main.py",
    repo: str = "my-repo",
    start_line: int = 1,
    end_line: int = 10,
    module: str = None,
) -> dict:
    return {
        "symbol_id": symbol_id,
        "name": name,
        "type": sym_type,
        "file_path": file_path,
        "repo": repo,
        "start_line": start_line,
        "end_line": end_line,
        "module": module,
    }


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestConnect:
    def test_connect_initializes_pool(self):
        """connect() must create a SimpleConnectionPool with the stored config."""
        client = PostgresClient("postgresql://u:p@h:5432/db", min_conn=2, max_conn=8)
        mock_pool = MagicMock()
        with patch("psycopg2.pool.SimpleConnectionPool", return_value=mock_pool) as mock_cls:
            client.connect()
            mock_cls.assert_called_once_with(2, 8, "postgresql://u:p@h:5432/db")
            assert client._pool is mock_pool

    def test_connect_logs_debug(self, caplog):
        """connect() should log a debug message after initialising the pool."""
        import logging

        client = PostgresClient("postgresql://u:p@h:5432/db")
        with patch("psycopg2.pool.SimpleConnectionPool", return_value=MagicMock()):
            with caplog.at_level(logging.DEBUG, logger="storage.postgres"):
                client.connect()
        assert "pool initialized" in caplog.text.lower()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestInternalHelpers:
    def test_get_conn_raises_when_pool_is_none(self):
        client = PostgresClient("postgresql://x")
        client._pool = None
        with pytest.raises(RuntimeError, match="connect()"):
            client._get_conn()

    def test_get_conn_returns_from_pool(self):
        client = _make_client()
        conn = client._get_conn()
        client._mock_pool.getconn.assert_called_once()
        assert conn is client._mock_conn

    def test_put_conn_returns_to_pool(self):
        client = _make_client()
        dummy_conn = MagicMock()
        client._put_conn(dummy_conn)
        client._mock_pool.putconn.assert_called_once_with(dummy_conn)

    def test_put_conn_noop_when_pool_is_none(self):
        """_put_conn must not raise when pool has been closed."""
        client = PostgresClient.__new__(PostgresClient)
        client._pool = None
        # Should not raise
        client._put_conn(MagicMock())

    def test_symbol_to_dict_passthrough_for_dict(self):
        client = PostgresClient.__new__(PostgresClient)
        d = {"symbol_id": "x"}
        assert client._symbol_to_dict(d) is d

    def test_symbol_to_dict_converts_dataclass(self):
        from dataclasses import dataclass

        @dataclass
        class FakeSym:
            symbol_id: str = "x"
            name: str = "f"

        client = PostgresClient.__new__(PostgresClient)
        result = client._symbol_to_dict(FakeSym())
        assert result == {"symbol_id": "x", "name": "f"}

    def test_edge_to_tuple_from_dict(self):
        client = PostgresClient.__new__(PostgresClient)
        edge = {"from_symbol": "a", "to_symbol": "b", "relation_type": "calls"}
        assert client._edge_to_tuple(edge) == ("a", "b", "calls")

    def test_edge_to_tuple_from_object(self):
        client = PostgresClient.__new__(PostgresClient)

        class FakeEdge:
            from_symbol = "a"
            to_symbol = "b"
            relation_type = "calls"

        assert client._edge_to_tuple(FakeEdge()) == ("a", "b", "calls")


# ---------------------------------------------------------------------------
# Symbols – read operations
# ---------------------------------------------------------------------------


class TestGetSymbol:
    def test_returns_dict_when_found(self):
        client = _make_client()
        expected = {"symbol_id": "sym-1", "name": "foo", "type": "function"}
        client._mock_cursor.fetchone.return_value = expected

        result = client.get_symbol("sym-1")

        client._mock_cursor.execute.assert_called_once()
        assert result == dict(expected)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None

        result = client.get_symbol("missing")

        assert result is None

    def test_releases_connection_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        client.get_symbol("sym-1")
        client._mock_pool.putconn.assert_called_once_with(client._mock_conn)

    def test_releases_connection_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("db error")
        with pytest.raises(Exception, match="db error"):
            client.get_symbol("sym-1")
        client._mock_pool.putconn.assert_called_once_with(client._mock_conn)


class TestGetSymbolsByRepo:
    def test_returns_list_of_dicts(self):
        client = _make_client()
        rows = [
            {"symbol_id": "s1", "name": "func_a"},
            {"symbol_id": "s2", "name": "func_b"},
        ]
        client._mock_cursor.fetchall.return_value = rows

        result = client.get_symbols_by_repo("my-repo", "org1", "proj1")

        client._mock_cursor.execute.assert_called_once()
        assert result == [dict(r) for r in rows]

    def test_returns_empty_list_when_no_symbols(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        result = client.get_symbols_by_repo("empty-repo", "org1", "proj1")
        assert result == []

    def test_passes_correct_params(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.get_symbols_by_repo("repo-x", "org-a", "proj-b")
        call_args = client._mock_cursor.execute.call_args
        assert call_args[0][1] == ("repo-x", "org-a", "proj-b")


class TestGetSymbolsByFile:
    def test_returns_symbols_for_file(self):
        client = _make_client()
        rows = [{"symbol_id": "s1", "file_path": "src/a.py"}]
        client._mock_cursor.fetchall.return_value = rows

        result = client.get_symbols_by_file("src/a.py", "org1", "proj1")

        assert result == [dict(r) for r in rows]

    def test_passes_correct_params(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.get_symbols_by_file("src/a.py", "org-x", "proj-y")
        call_args = client._mock_cursor.execute.call_args
        assert call_args[0][1] == ("src/a.py", "org-x", "proj-y")


class TestSearchSymbolsByName:
    def test_returns_matching_symbols(self):
        client = _make_client()
        rows = [{"symbol_id": "s1", "name": "my_handler"}]
        client._mock_cursor.fetchall.return_value = rows

        result = client.search_symbols_by_name("org1", "proj1", "handler")

        assert result == [dict(r) for r in rows]

    def test_wraps_pattern_in_percent_wildcards(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.search_symbols_by_name("org1", "proj1", "foo")
        call_args = client._mock_cursor.execute.call_args
        params = call_args[0][1]
        assert params == ("org1", "proj1", "%foo%")

    def test_returns_empty_when_no_match(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        result = client.search_symbols_by_name("org1", "proj1", "zzz")
        assert result == []


# ---------------------------------------------------------------------------
# Symbols – write / delete operations
# ---------------------------------------------------------------------------


class TestUpsertSymbol:
    def test_executes_insert_sql(self):
        client = _make_client()
        sym = _make_symbol_dict()
        client.upsert_symbol(sym, org_id="org1", project_id="proj1")
        client._mock_cursor.execute.assert_called_once()
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO symbols" in sql

    def test_commits_on_success(self):
        client = _make_client()
        client.upsert_symbol(_make_symbol_dict(), org_id="org1", project_id="proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_and_reraise_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("constraint")
        with pytest.raises(Exception, match="constraint"):
            client.upsert_symbol(_make_symbol_dict(), org_id="org1", project_id="proj1")
        client._mock_conn.rollback.assert_called_once()

    def test_defaults_module_to_none(self):
        client = _make_client()
        sym = _make_symbol_dict()
        sym.pop("module", None)
        client.upsert_symbol(sym, org_id="org1", project_id="proj1")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params["module"] is None


class TestDeleteSymbolsByRepo:
    def test_executes_delete_sql(self):
        client = _make_client()
        client.delete_symbols_by_repo("my-repo", "org1", "proj1")
        client._mock_cursor.execute.assert_called_once()
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM symbols" in sql

    def test_commits_on_success(self):
        client = _make_client()
        client.delete_symbols_by_repo("my-repo", "org1", "proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("db error")
        with pytest.raises(Exception):
            client.delete_symbols_by_repo("my-repo", "org1", "proj1")
        client._mock_conn.rollback.assert_called_once()

    def test_passes_correct_params(self):
        client = _make_client()
        client.delete_symbols_by_repo("repo-x", "org-a", "proj-b")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("repo-x", "org-a", "proj-b")


class TestDeleteSymbolsByFile:
    def test_returns_deleted_symbol_ids(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = [("sym-1",), ("sym-2",)]
        result = client.delete_symbols_by_file("src/a.py", "my-repo", "org1", "proj1")
        assert result == ["sym-1", "sym-2"]

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.delete_symbols_by_file("src/a.py", "my-repo", "org1", "proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("db error")
        with pytest.raises(Exception):
            client.delete_symbols_by_file("src/a.py", "my-repo", "org1", "proj1")
        client._mock_conn.rollback.assert_called_once()


class TestGetSymbolsByModule:
    def test_returns_symbols_for_module(self):
        client = _make_client()
        rows = [{"symbol_id": "s1", "module": "payments"}]
        client._mock_cursor.fetchall.return_value = rows

        result = client.get_symbols_by_module("my-repo", "payments", "org1", "proj1")

        assert result == [dict(r) for r in rows]

    def test_passes_correct_params(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.get_symbols_by_module("repo-x", "mod-y", "org-a", "proj-b")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("repo-x", "mod-y", "org-a", "proj-b")


class TestDeleteSymbolsByModule:
    def test_returns_deleted_ids(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = [("sym-a",), ("sym-b",)]
        result = client.delete_symbols_by_module("my-repo", "payments", "org1", "proj1")
        assert result == ["sym-a", "sym-b"]

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.delete_symbols_by_module("my-repo", "payments", "org1", "proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("fail")
        with pytest.raises(Exception):
            client.delete_symbols_by_module("my-repo", "payments", "org1", "proj1")
        client._mock_conn.rollback.assert_called_once()


class TestDeleteEdgesBySymbols:
    def test_noop_for_empty_list(self):
        client = _make_client()
        client.delete_edges_by_symbols([])
        client._mock_cursor.execute.assert_not_called()

    def test_executes_delete_with_symbol_ids(self):
        client = _make_client()
        client.delete_edges_by_symbols(["sym-1", "sym-2"])
        client._mock_cursor.execute.assert_called_once()
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == (["sym-1", "sym-2"], ["sym-1", "sym-2"])

    def test_commits_on_success(self):
        client = _make_client()
        client.delete_edges_by_symbols(["sym-1"])
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("db fail")
        with pytest.raises(Exception):
            client.delete_edges_by_symbols(["sym-1"])
        client._mock_conn.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Batch upsert
# ---------------------------------------------------------------------------


class TestUpsertSymbolsBatch:
    def test_noop_for_empty_list(self):
        client = _make_client()
        client.upsert_symbols_batch([], "org1", "proj1")
        client._mock_cursor.execute.assert_not_called()

    def test_calls_execute_values(self):
        client = _make_client()
        symbols = [_make_symbol_dict(symbol_id=f"sym-{i}") for i in range(3)]
        with patch("psycopg2.extras.execute_values") as mock_ev:
            client.upsert_symbols_batch(symbols, "org1", "proj1")
            mock_ev.assert_called_once()
            rows_arg = mock_ev.call_args[0][2]
            assert len(rows_arg) == 3

    def test_commits_on_success(self):
        client = _make_client()
        symbols = [_make_symbol_dict()]
        with patch("psycopg2.extras.execute_values"):
            client.upsert_symbols_batch(symbols, "org1", "proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        symbols = [_make_symbol_dict()]
        with patch("psycopg2.extras.execute_values", side_effect=Exception("batch fail")):
            with pytest.raises(Exception, match="batch fail"):
                client.upsert_symbols_batch(symbols, "org1", "proj1")
        client._mock_conn.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


class TestUpsertFile:
    def test_executes_insert_sql(self):
        client = _make_client()
        client.upsert_file("src/a.py", "my-repo", "org1", "proj1", commit_count=5)
        client._mock_cursor.execute.assert_called_once()
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO files" in sql

    def test_commits_on_success(self):
        client = _make_client()
        client.upsert_file("src/a.py", "my-repo", "org1", "proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("db fail")
        with pytest.raises(Exception):
            client.upsert_file("src/a.py", "my-repo", "org1", "proj1")
        client._mock_conn.rollback.assert_called_once()

    def test_passes_all_params(self):
        client = _make_client()
        client.upsert_file("src/a.py", "repo-x", "org-a", "proj-b", last_modified="2024-01-01", commit_count=7)
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("src/a.py", "repo-x", "org-a", "proj-b", "2024-01-01", 7)


class TestGetFilesByRepo:
    def test_returns_file_dicts(self):
        client = _make_client()
        rows = [{"file_id": 1, "file_path": "src/a.py", "repo": "my-repo"}]
        client._mock_cursor.fetchall.return_value = rows

        result = client.get_files_by_repo("my-repo", "org1", "proj1")

        assert result == [dict(r) for r in rows]

    def test_returns_empty_list_when_none(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        result = client.get_files_by_repo("empty-repo", "org1", "proj1")
        assert result == []


class TestGetFileMetadata:
    def test_returns_dict_when_found(self):
        client = _make_client()
        row = {"file_id": 1, "file_path": "src/a.py", "repo": "my-repo", "last_modified": None, "commit_count": 0}
        client._mock_cursor.fetchone.return_value = row

        result = client.get_file_metadata("src/a.py", "my-repo", "org1", "proj1")

        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.get_file_metadata("missing.py", "my-repo", "org1", "proj1")
        assert result is None

    def test_passes_correct_params(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        client.get_file_metadata("src/a.py", "repo-x", "org-a", "proj-b")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("src/a.py", "repo-x", "org-a", "proj-b")


# ---------------------------------------------------------------------------
# Graph edges
# ---------------------------------------------------------------------------


class TestInsertEdges:
    def test_noop_for_empty_list(self):
        client = _make_client()
        client.insert_edges([], "org1", "proj1")
        client._mock_cursor.execute.assert_not_called()

    def test_calls_execute_values(self):
        client = _make_client()
        edges = [{"from_symbol": "a", "to_symbol": "b", "relation_type": "calls"}]
        with patch("psycopg2.extras.execute_values") as mock_ev:
            client.insert_edges(edges, "org1", "proj1")
            mock_ev.assert_called_once()
            rows_arg = mock_ev.call_args[0][2]
            assert len(rows_arg) == 1
            assert rows_arg[0] == ("a", "b", "calls", "org1", "proj1")

    def test_commits_on_success(self):
        client = _make_client()
        edges = [{"from_symbol": "a", "to_symbol": "b", "relation_type": "calls"}]
        with patch("psycopg2.extras.execute_values"):
            client.insert_edges(edges, "org1", "proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        edges = [{"from_symbol": "a", "to_symbol": "b", "relation_type": "calls"}]
        with patch("psycopg2.extras.execute_values", side_effect=Exception("edge fail")):
            with pytest.raises(Exception, match="edge fail"):
                client.insert_edges(edges, "org1", "proj1")
        client._mock_conn.rollback.assert_called_once()


class TestGetEdgesFrom:
    def test_returns_edges(self):
        client = _make_client()
        rows = [{"id": 1, "from_symbol": "a", "to_symbol": "b", "relation_type": "calls"}]
        client._mock_cursor.fetchall.return_value = rows

        result = client.get_edges_from("a", "org1", "proj1")

        assert result == [dict(r) for r in rows]

    def test_passes_correct_params(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.get_edges_from("sym-x", "org-a", "proj-b")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("sym-x", "org-a", "proj-b")

    def test_returns_empty_list_when_none(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        result = client.get_edges_from("sym-x", "org1", "proj1")
        assert result == []


class TestGetEdgesTo:
    def test_returns_edges(self):
        client = _make_client()
        rows = [{"id": 2, "from_symbol": "a", "to_symbol": "b", "relation_type": "calls"}]
        client._mock_cursor.fetchall.return_value = rows

        result = client.get_edges_to("b", "org1", "proj1")

        assert result == [dict(r) for r in rows]

    def test_passes_correct_params(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.get_edges_to("sym-y", "org-a", "proj-b")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("sym-y", "org-a", "proj-b")


class TestDeleteEdgesByRepo:
    def test_executes_delete_sql(self):
        client = _make_client()
        client.delete_edges_by_repo("my-repo", "org1", "proj1")
        client._mock_cursor.execute.assert_called_once()
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM graph_edges" in sql

    def test_commits_on_success(self):
        client = _make_client()
        client.delete_edges_by_repo("my-repo", "org1", "proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("delete fail")
        with pytest.raises(Exception):
            client.delete_edges_by_repo("my-repo", "org1", "proj1")
        client._mock_conn.rollback.assert_called_once()

    def test_passes_all_params(self):
        client = _make_client()
        client.delete_edges_by_repo("repo-x", "org-a", "proj-b")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("org-a", "proj-b", "repo-x", "org-a", "proj-b", "repo-x", "org-a", "proj-b")


# ---------------------------------------------------------------------------
# Git metadata
# ---------------------------------------------------------------------------


class TestUpsertGitMetadata:
    def test_executes_insert_sql(self):
        client = _make_client()
        client.upsert_git_metadata("src/a.py", "my-repo", "org1", "proj1", last_commit_hash="abc", commit_frequency=5)
        client._mock_cursor.execute.assert_called_once()
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO git_metadata" in sql

    def test_commits_on_success(self):
        client = _make_client()
        client.upsert_git_metadata("src/a.py", "my-repo", "org1", "proj1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("meta fail")
        with pytest.raises(Exception):
            client.upsert_git_metadata("src/a.py", "my-repo", "org1", "proj1")
        client._mock_conn.rollback.assert_called_once()

    def test_passes_all_params(self):
        client = _make_client()
        client.upsert_git_metadata(
            "src/a.py", "repo-x", "org-a", "proj-b",
            last_commit_hash="abc", last_commit_author="alice",
            commit_frequency=3, recent_pr="PR-1"
        )
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("src/a.py", "repo-x", "org-a", "proj-b", "abc", "alice", 3, "PR-1")


class TestGetGitMetadata:
    def test_returns_dict_when_found(self):
        client = _make_client()
        row = {
            "id": 1, "file_path": "src/a.py", "repo": "my-repo",
            "last_commit_hash": "abc", "last_commit_author": "alice",
            "commit_frequency": 5, "recent_pr": "PR-1"
        }
        client._mock_cursor.fetchone.return_value = row
        result = client.get_git_metadata("src/a.py", "my-repo", "org1", "proj1")
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.get_git_metadata("missing.py", "my-repo", "org1", "proj1")
        assert result is None

    def test_passes_correct_params(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        client.get_git_metadata("src/a.py", "repo-x", "org-a", "proj-b")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("src/a.py", "repo-x", "org-a", "proj-b")


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


class TestCreateOrg:
    def test_returns_org_dict(self):
        client = _make_client()
        row = {"org_id": "org-1", "name": "Acme", "slug": "acme"}
        client._mock_cursor.fetchone.return_value = row

        result = client.create_org("Acme", "acme")

        assert result == dict(row)

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"org_id": "1", "name": "X", "slug": "x"}
        client.create_org("X", "x")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("unique violation")
        with pytest.raises(Exception):
            client.create_org("X", "x")
        client._mock_conn.rollback.assert_called_once()

    def test_executes_insert_with_returning(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"org_id": "1", "name": "X", "slug": "x"}
        client.create_org("X", "x")
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO organizations" in sql
        assert "RETURNING" in sql


class TestGetOrg:
    def test_returns_dict_when_found(self):
        client = _make_client()
        row = {"org_id": "org-1", "name": "Acme"}
        client._mock_cursor.fetchone.return_value = row
        result = client.get_org("org-1")
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.get_org("missing-org")
        assert result is None


class TestGetOrgBySlug:
    def test_returns_dict_when_found(self):
        client = _make_client()
        row = {"org_id": "org-1", "name": "Acme", "slug": "acme"}
        client._mock_cursor.fetchone.return_value = row
        result = client.get_org_by_slug("acme")
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.get_org_by_slug("no-such-slug")
        assert result is None

    def test_passes_slug_as_param(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        client.get_org_by_slug("my-org")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("my-org",)


class TestListOrgsForUser:
    def test_returns_orgs(self):
        client = _make_client()
        rows = [{"org_id": "org-1"}, {"org_id": "org-2"}]
        client._mock_cursor.fetchall.return_value = rows
        result = client.list_orgs_for_user("user-1")
        assert result == [dict(r) for r in rows]

    def test_returns_empty_list_when_none(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        result = client.list_orgs_for_user("user-no-orgs")
        assert result == []

    def test_passes_user_id_as_param(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.list_orgs_for_user("user-x")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("user-x",)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


class TestCreateTeam:
    def test_returns_team_dict(self):
        client = _make_client()
        row = {"team_id": "team-1", "org_id": "org-1", "name": "Engineering"}
        client._mock_cursor.fetchone.return_value = row
        result = client.create_team("org-1", "Engineering")
        assert result == dict(row)

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"team_id": "1", "org_id": "o", "name": "T"}
        client.create_team("org-1", "T")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("fail")
        with pytest.raises(Exception):
            client.create_team("org-1", "T")
        client._mock_conn.rollback.assert_called_once()


class TestListTeams:
    def test_returns_all_teams_for_org(self):
        client = _make_client()
        rows = [{"team_id": "t1"}, {"team_id": "t2"}]
        client._mock_cursor.fetchall.return_value = rows
        result = client.list_teams("org-1")
        assert result == [dict(r) for r in rows]

    def test_returns_empty_list_when_no_teams(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        result = client.list_teams("org-no-teams")
        assert result == []


class TestGetTeam:
    def test_returns_team_when_found(self):
        client = _make_client()
        row = {"team_id": "t1", "name": "Eng"}
        client._mock_cursor.fetchone.return_value = row
        result = client.get_team("t1")
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.get_team("missing-team")
        assert result is None


class TestAddTeamMember:
    def test_returns_membership_dict(self):
        client = _make_client()
        row = {"user_id": "u1", "team_id": "t1", "role": "member"}
        client._mock_cursor.fetchone.return_value = row
        result = client.add_team_member("u1", "t1")
        assert result == dict(row)

    def test_uses_provided_role(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"user_id": "u1", "team_id": "t1", "role": "admin"}
        client.add_team_member("u1", "t1", role="admin")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("u1", "t1", "admin")

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"user_id": "u1", "team_id": "t1", "role": "member"}
        client.add_team_member("u1", "t1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("fail")
        with pytest.raises(Exception):
            client.add_team_member("u1", "t1")
        client._mock_conn.rollback.assert_called_once()


class TestGetTeamMembership:
    def test_returns_membership_when_found(self):
        client = _make_client()
        row = {"user_id": "u1", "team_id": "t1", "role": "member"}
        client._mock_cursor.fetchone.return_value = row
        result = client.get_team_membership("u1", "t1")
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.get_team_membership("u1", "t-missing")
        assert result is None

    def test_passes_correct_params(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        client.get_team_membership("user-x", "team-y")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("user-x", "team-y")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class TestCreateProject:
    def test_returns_project_dict(self):
        client = _make_client()
        row = {"project_id": "proj-1", "name": "MyProject", "slug": "my-project"}
        client._mock_cursor.fetchone.return_value = row

        result = client.create_project(
            org_id="org-1",
            name="MyProject",
            slug="my-project",
            github_repo_url="https://github.com/org/repo",
        )

        assert result == dict(row)

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"project_id": "p1"}
        client.create_project("org-1", "P", "p", "https://github.com/x/y")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("fail")
        with pytest.raises(Exception):
            client.create_project("org-1", "P", "p", "https://github.com/x/y")
        client._mock_conn.rollback.assert_called_once()

    def test_passes_all_optional_params(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"project_id": "p1"}
        client.create_project(
            org_id="org-1", name="P", slug="p", github_repo_url="https://github.com/x/y",
            team_id="team-1", github_token_encrypted="enc-token",
            jira_base_url="https://jira.example.com", jira_email="user@example.com",
            jira_api_token_encrypted="enc-jira", default_branch="develop",
            collection_group="group-x"
        )
        params = client._mock_cursor.execute.call_args[0][1]
        assert params[4] == "team-1"
        assert params[5] == "enc-token"
        assert params[9] == "develop"
        assert params[10] == "group-x"


class TestGetProject:
    def test_returns_project_when_found(self):
        client = _make_client()
        row = {"project_id": "proj-1", "name": "MyProject"}
        client._mock_cursor.fetchone.return_value = row
        result = client.get_project("proj-1")
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.get_project("missing-proj")
        assert result is None


class TestListProjects:
    def test_returns_all_projects_for_org(self):
        client = _make_client()
        rows = [{"project_id": "p1"}, {"project_id": "p2"}]
        client._mock_cursor.fetchall.return_value = rows
        result = client.list_projects("org-1")
        assert result == [dict(r) for r in rows]

    def test_returns_empty_list_when_no_projects(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        result = client.list_projects("org-empty")
        assert result == []


class TestUpdateProject:
    def test_returns_updated_project(self):
        client = _make_client()
        row = {"project_id": "proj-1", "name": "NewName"}
        client._mock_cursor.fetchone.return_value = row
        result = client.update_project("proj-1", name="NewName")
        assert result == dict(row)

    def test_returns_none_when_project_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.update_project("missing", name="X")
        assert result is None

    def test_calls_get_project_when_no_kwargs(self):
        """update_project with no kwargs must delegate to get_project."""
        client = _make_client()
        row = {"project_id": "proj-1"}
        client._mock_cursor.fetchone.return_value = row

        # Calling with no kwargs should call get_project internally
        result = client.update_project("proj-1")

        # get_project will call execute with SELECT
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "SELECT" in sql

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"project_id": "p1"}
        client.update_project("p1", name="X")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("fail")
        with pytest.raises(Exception):
            client.update_project("p1", name="X")
        client._mock_conn.rollback.assert_called_once()

    def test_builds_set_clause_dynamically(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"project_id": "p1"}
        client.update_project("p1", name="X", default_branch="dev")
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "name = %s" in sql
        assert "default_branch = %s" in sql


class TestGetProjectByRepoUrl:
    def test_returns_project_when_found(self):
        client = _make_client()
        row = {"project_id": "proj-1", "github_repo_url": "https://github.com/org/repo"}
        client._mock_cursor.fetchone.return_value = row
        result = client.get_project_by_repo_url("https://github.com/org/repo")
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        result = client.get_project_by_repo_url("https://github.com/x/y")
        assert result is None

    def test_passes_url_as_param(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = None
        url = "https://github.com/org/repo"
        client.get_project_by_repo_url(url)
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == (url,)


class TestDeleteProject:
    def test_returns_true_when_project_deleted(self):
        client = _make_client()
        client._mock_cursor.rowcount = 1
        result = client.delete_project("proj-1", "org-1")
        assert result is True

    def test_returns_false_when_project_not_found(self):
        client = _make_client()
        client._mock_cursor.rowcount = 0
        result = client.delete_project("missing-proj", "org-1")
        assert result is False

    def test_executes_multiple_deletes_in_order(self):
        client = _make_client()
        client._mock_cursor.rowcount = 1
        client.delete_project("proj-1", "org-1")

        calls = client._mock_cursor.execute.call_args_list
        # Should delete from child tables before projects
        sqls = [c[0][0] for c in calls]
        assert any("jira_tickets" in s for s in sqls)
        assert any("git_metadata" in s for s in sqls)
        assert any("graph_edges" in s for s in sqls)
        assert any("files" in s for s in sqls)
        assert any("symbols" in s for s in sqls)
        assert any("projects" in s for s in sqls)
        # projects table must come last
        project_delete_idx = next(i for i, s in enumerate(sqls) if "DELETE FROM projects" in s)
        assert project_delete_idx == len(sqls) - 1

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.rowcount = 1
        client.delete_project("proj-1", "org-1")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("delete fail")
        with pytest.raises(Exception):
            client.delete_project("proj-1", "org-1")
        client._mock_conn.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Jira Tickets
# ---------------------------------------------------------------------------


class TestUpsertJiraTicket:
    def test_returns_ticket_dict(self):
        client = _make_client()
        row = {"ticket_id": 1, "ticket_key": "PROJ-1", "title": "Fix bug"}
        client._mock_cursor.fetchone.return_value = row

        result = client.upsert_jira_ticket(
            org_id="org-1",
            project_id="proj-1",
            ticket_key="PROJ-1",
            title="Fix bug",
        )

        assert result == dict(row)

    def test_commits_on_success(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"ticket_id": 1}
        client.upsert_jira_ticket("org-1", "proj-1", "PROJ-1", "Fix bug")
        client._mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        client = _make_client()
        client._mock_cursor.execute.side_effect = Exception("db fail")
        with pytest.raises(Exception):
            client.upsert_jira_ticket("org-1", "proj-1", "PROJ-1", "Fix bug")
        client._mock_conn.rollback.assert_called_once()

    def test_wraps_labels_in_json(self):
        """labels list must be serialized with psycopg2.extras.Json."""
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"ticket_id": 1}
        import psycopg2.extras as _extras

        with patch.object(_extras, "Json", wraps=_extras.Json) as mock_json:
            client.upsert_jira_ticket(
                "org-1", "proj-1", "PROJ-1", "Fix bug",
                labels=["backend", "urgent"]
            )
            mock_json.assert_called()

    def test_wraps_components_in_json(self):
        """components list must be serialized with psycopg2.extras.Json."""
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"ticket_id": 1}
        import psycopg2.extras as _extras

        with patch.object(_extras, "Json", wraps=_extras.Json) as mock_json:
            client.upsert_jira_ticket(
                "org-1", "proj-1", "PROJ-1", "Fix bug",
                components=["api", "db"]
            )
            mock_json.assert_called()

    def test_none_labels_and_components_not_wrapped(self):
        """None labels/components must be passed as None, not Json(None)."""
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"ticket_id": 1}
        client.upsert_jira_ticket("org-1", "proj-1", "PROJ-1", "Fix bug")
        params = client._mock_cursor.execute.call_args[0][1]
        # labels at index 8, components at index 9
        assert params[8] is None
        assert params[9] is None

    def test_executes_upsert_sql(self):
        client = _make_client()
        client._mock_cursor.fetchone.return_value = {"ticket_id": 1}
        client.upsert_jira_ticket("org-1", "proj-1", "PROJ-1", "Fix bug")
        sql = client._mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO jira_tickets" in sql
        assert "ON CONFLICT" in sql


class TestGetJiraTicketsByProject:
    def test_returns_tickets(self):
        client = _make_client()
        rows = [{"ticket_key": "PROJ-1"}, {"ticket_key": "PROJ-2"}]
        client._mock_cursor.fetchall.return_value = rows

        result = client.get_jira_tickets_by_project("proj-1")

        assert result == [dict(r) for r in rows]

    def test_default_limit_is_100(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.get_jira_tickets_by_project("proj-1")
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("proj-1", 100)

    def test_respects_custom_limit(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        client.get_jira_tickets_by_project("proj-1", limit=10)
        params = client._mock_cursor.execute.call_args[0][1]
        assert params == ("proj-1", 10)

    def test_returns_empty_when_no_tickets(self):
        client = _make_client()
        client._mock_cursor.fetchall.return_value = []
        result = client.get_jira_tickets_by_project("proj-no-tickets")
        assert result == []
