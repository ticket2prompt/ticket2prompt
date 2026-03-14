"""Tests for the PostgreSQL client.

Unit tests (no DB required): use mocks to verify constructor and lifecycle behavior.
Integration tests: skipped when PostgreSQL is unavailable.
"""

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from indexing.graph_builder import GraphEdge
from indexing.symbol_extractor import Symbol
from storage.migrations import apply_schema
from storage.postgres import PostgresClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_CONN = "postgresql://divya:Kdr@1224@localhost:5432/code_context"


def postgres_available() -> bool:
    try:
        conn = psycopg2.connect(_TEST_CONN)
        conn.close()
        return True
    except Exception:
        return False


skip_no_postgres = pytest.mark.skipif(
    not postgres_available(),
    reason="PostgreSQL not available",
)


def _unique_repo() -> str:
    """Return a unique repo name to isolate test data."""
    return f"test-repo-{uuid.uuid4().hex[:8]}"


def _make_symbol(
    repo: str,
    name: str = "my_func",
    file_path: str = "src/main.py",
    sym_type: str = "function",
    start_line: int = 1,
    end_line: int = 10,
) -> Symbol:
    symbol_id = f"{repo}-{name}-{sym_type}"[:64]
    return Symbol(
        symbol_id=symbol_id,
        name=name,
        type=sym_type,
        file_path=file_path,
        repo=repo,
        start_line=start_line,
        end_line=end_line,
        language="python",
        source=f"def {name}(): pass",
    )


# ---------------------------------------------------------------------------
# Unit tests (no DB)
# ---------------------------------------------------------------------------


def test_postgres_client_init_stores_config():
    """Constructor must store the connection string for later use."""
    client = PostgresClient("postgresql://user:pass@host:5432/db", min_conn=2, max_conn=5)
    assert client._conn_string == "postgresql://user:pass@host:5432/db"
    assert client._pool is None


def test_close_closes_pool():
    """close() must call closeall() on the underlying pool."""
    client = PostgresClient(_TEST_CONN)
    mock_pool = MagicMock()
    client._pool = mock_pool

    client.close()

    mock_pool.closeall.assert_called_once()


def test_context_manager_calls_close():
    """__exit__ must delegate to close() so the pool is cleaned up."""
    client = PostgresClient(_TEST_CONN)
    mock_pool = MagicMock()
    client._pool = mock_pool

    with client:
        pass  # __enter__ and __exit__ exercised

    mock_pool.closeall.assert_called_once()


# ---------------------------------------------------------------------------
# Integration tests (require PostgreSQL)
# ---------------------------------------------------------------------------


@skip_no_postgres
def test_upsert_and_get_symbol_roundtrip():
    """Inserted symbol must be retrievable with identical field values."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()
    symbol = _make_symbol(repo)

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbol(symbol)
            result = client.get_symbol(symbol.symbol_id)

            assert result is not None
            assert result["symbol_id"] == symbol.symbol_id
            assert result["name"] == symbol.name
            assert result["type"] == symbol.type
            assert result["file_path"] == symbol.file_path
            assert result["repo"] == symbol.repo
            assert result["start_line"] == symbol.start_line
            assert result["end_line"] == symbol.end_line
        finally:
            client.delete_symbols_by_repo(repo)


@skip_no_postgres
def test_upsert_symbol_updates_on_conflict():
    """Upserting a symbol with the same PK must update the existing row."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()
    symbol = _make_symbol(repo, start_line=1, end_line=10)

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbol(symbol)

            updated_symbol = Symbol(
                symbol_id=symbol.symbol_id,
                name=symbol.name,
                type=symbol.type,
                file_path=symbol.file_path,
                repo=symbol.repo,
                start_line=99,
                end_line=200,
                language=symbol.language,
                source=symbol.source,
            )
            client.upsert_symbol(updated_symbol)

            result = client.get_symbol(symbol.symbol_id)
            assert result is not None
            assert result["start_line"] == 99
            assert result["end_line"] == 200
        finally:
            client.delete_symbols_by_repo(repo)


@skip_no_postgres
def test_batch_upsert_symbols():
    """Batch-inserting multiple symbols must persist all of them."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()
    symbols = [
        _make_symbol(repo, name=f"func_{i}", file_path=f"src/mod_{i}.py")
        for i in range(5)
    ]

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbols_batch(symbols)
            results = client.get_symbols_by_repo(repo)
            assert len(results) == 5
        finally:
            client.delete_symbols_by_repo(repo)


@skip_no_postgres
def test_get_symbols_by_repo():
    """get_symbols_by_repo must return only symbols belonging to the requested repo."""
    apply_schema(_TEST_CONN)
    repo_a = _unique_repo()
    repo_b = _unique_repo()

    sym_a = _make_symbol(repo_a, name="func_a")
    sym_b1 = _make_symbol(repo_b, name="func_b1")
    sym_b2 = _make_symbol(repo_b, name="func_b2")

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbols_batch([sym_a, sym_b1, sym_b2])

            results_a = client.get_symbols_by_repo(repo_a)
            results_b = client.get_symbols_by_repo(repo_b)

            assert len(results_a) == 1
            assert results_a[0]["repo"] == repo_a

            assert len(results_b) == 2
            assert all(r["repo"] == repo_b for r in results_b)
        finally:
            client.delete_symbols_by_repo(repo_a)
            client.delete_symbols_by_repo(repo_b)


@skip_no_postgres
def test_get_symbols_by_file():
    """get_symbols_by_file must filter by file_path regardless of repo."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()
    target_file = f"src/{repo}_target.py"

    sym_in_file = _make_symbol(repo, name="in_file_func", file_path=target_file)
    sym_other_file = _make_symbol(repo, name="other_func", file_path="src/other.py")

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbols_batch([sym_in_file, sym_other_file])

            results = client.get_symbols_by_file(target_file)
            assert len(results) == 1
            assert results[0]["file_path"] == target_file
        finally:
            client.delete_symbols_by_repo(repo)


@skip_no_postgres
def test_delete_symbols_by_repo():
    """delete_symbols_by_repo must remove all symbols for that repo and none for others."""
    apply_schema(_TEST_CONN)
    repo_keep = _unique_repo()
    repo_delete = _unique_repo()

    sym_keep = _make_symbol(repo_keep, name="keeper")
    sym_delete = _make_symbol(repo_delete, name="goner")

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbols_batch([sym_keep, sym_delete])

            client.delete_symbols_by_repo(repo_delete)

            assert client.get_symbols_by_repo(repo_delete) == []
            assert len(client.get_symbols_by_repo(repo_keep)) == 1
        finally:
            client.delete_symbols_by_repo(repo_keep)


@skip_no_postgres
def test_insert_and_get_edges():
    """Inserted GraphEdge objects must be retrievable via get_edges_from / get_edges_to."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()

    sym_a = _make_symbol(repo, name="caller")
    sym_b = _make_symbol(repo, name="callee")

    edge = GraphEdge(
        from_symbol=sym_a.symbol_id,
        to_symbol=sym_b.symbol_id,
        relation_type="calls",
    )

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbols_batch([sym_a, sym_b])
            client.insert_edges([edge])

            from_edges = client.get_edges_from(sym_a.symbol_id)
            assert len(from_edges) >= 1
            assert any(
                e["from_symbol"] == sym_a.symbol_id and e["to_symbol"] == sym_b.symbol_id
                for e in from_edges
            )

            to_edges = client.get_edges_to(sym_b.symbol_id)
            assert len(to_edges) >= 1
            assert any(
                e["from_symbol"] == sym_a.symbol_id and e["to_symbol"] == sym_b.symbol_id
                for e in to_edges
            )
        finally:
            client.delete_edges_by_repo(repo)
            client.delete_symbols_by_repo(repo)


@skip_no_postgres
def test_upsert_and_get_file():
    """upsert_file / get_files_by_repo must roundtrip file records correctly."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()
    file_path = f"src/{repo}_module.py"

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_file(file_path, repo, commit_count=7)

            results = client.get_files_by_repo(repo)
            assert len(results) == 1
            assert results[0]["file_path"] == file_path
            assert results[0]["repo"] == repo
            assert results[0]["commit_count"] == 7
        finally:
            # Clean up: delete the inserted file row directly
            conn = psycopg2.connect(_TEST_CONN)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM files WHERE file_path = %s AND repo = %s",
                        (file_path, repo),
                    )
                conn.commit()
            finally:
                conn.close()


@skip_no_postgres
def test_upsert_and_get_git_metadata():
    """upsert_git_metadata / get_git_metadata must roundtrip metadata correctly."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()
    file_path = f"src/{repo}_main.py"

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_git_metadata(
                file_path=file_path,
                repo=repo,
                last_commit_hash="abc123",
                last_commit_author="alice",
                commit_frequency=42,
                recent_pr="PR-99",
            )

            result = client.get_git_metadata(file_path, repo)
            assert result is not None
            assert result["file_path"] == file_path
            assert result["repo"] == repo
            assert result["last_commit_hash"] == "abc123"
            assert result["last_commit_author"] == "alice"
            assert result["commit_frequency"] == 42
            assert result["recent_pr"] == "PR-99"
        finally:
            conn = psycopg2.connect(_TEST_CONN)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM git_metadata WHERE file_path = %s AND repo = %s",
                        (file_path, repo),
                    )
                conn.commit()
            finally:
                conn.close()


# ---------------------------------------------------------------------------
# Unit tests for module-aware methods (no DB)
# ---------------------------------------------------------------------------


class TestModuleOperations:
    def test_upsert_symbol_with_module(self):
        """upsert_symbol includes module column in the INSERT statement."""
        client = PostgresClient(_TEST_CONN)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        client._pool = mock_pool

        symbol_dict = {
            "symbol_id": "repo-func-function",
            "name": "my_func",
            "type": "function",
            "file_path": "src/payments.py",
            "repo": "my-repo",
            "start_line": 1,
            "end_line": 10,
            "module": "payments",
        }
        client.upsert_symbol(symbol_dict, org_id="test-org", project_id="test-project")

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "module" in sql
        assert "%(module)s" in sql

    def test_upsert_symbol_without_module_defaults_to_none(self):
        """upsert_symbol sets module to None when not provided."""
        client = PostgresClient(_TEST_CONN)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        client._pool = mock_pool

        symbol_dict = {
            "symbol_id": "repo-func-function",
            "name": "my_func",
            "type": "function",
            "file_path": "src/main.py",
            "repo": "my-repo",
            "start_line": 1,
            "end_line": 10,
            # module intentionally omitted
        }
        client.upsert_symbol(symbol_dict, org_id="test-org", project_id="test-project")

        call_args = mock_cursor.execute.call_args
        passed_dict = call_args[0][1]
        assert passed_dict["module"] is None

    def test_get_symbols_by_module(self):
        """get_symbols_by_module issues a query filtered by repo and module."""
        client = PostgresClient(_TEST_CONN)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        client._pool = mock_pool

        result = client.get_symbols_by_module("my-repo", "payments", org_id="test-org", project_id="test-project")

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "module" in sql
        assert params == ("my-repo", "payments", "test-org", "test-project")
        assert result == []

    def test_delete_symbols_by_module(self):
        """delete_symbols_by_module issues a DELETE filtered by repo and module."""
        client = PostgresClient(_TEST_CONN)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("sym-1",), ("sym-2",)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        client._pool = mock_pool

        deleted_ids = client.delete_symbols_by_module("my-repo", "payments", org_id="test-org", project_id="test-project")

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "DELETE" in sql
        assert "module" in sql
        assert params == ("my-repo", "payments", "test-org", "test-project")
        assert deleted_ids == ["sym-1", "sym-2"]


@skip_no_postgres
def test_get_and_delete_symbols_by_module():
    """get_symbols_by_module and delete_symbols_by_module work end-to-end."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()

    sym_payments_1 = Symbol(
        symbol_id=f"{repo}-pay-func",
        name="charge_card",
        type="function",
        file_path="src/payments.py",
        repo=repo,
        start_line=1,
        end_line=10,
        language="python",
        source="def charge_card(): pass",
    )
    sym_payments_2 = Symbol(
        symbol_id=f"{repo}-pay-class",
        name="PaymentGateway",
        type="class",
        file_path="src/gateway.py",
        repo=repo,
        start_line=1,
        end_line=50,
        language="python",
        source="class PaymentGateway: pass",
    )
    sym_other = Symbol(
        symbol_id=f"{repo}-other-func",
        name="send_email",
        type="function",
        file_path="src/email.py",
        repo=repo,
        start_line=1,
        end_line=5,
        language="python",
        source="def send_email(): pass",
    )

    pay_dict_1 = {**sym_payments_1.__dict__, "module": "payments"}
    pay_dict_2 = {**sym_payments_2.__dict__, "module": "payments"}
    other_dict = {**sym_other.__dict__, "module": "email"}

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbols_batch([pay_dict_1, pay_dict_2, other_dict])

            results = client.get_symbols_by_module(repo, "payments")
            assert len(results) == 2
            assert all(r["module"] == "payments" for r in results)

            deleted_ids = client.delete_symbols_by_module(repo, "payments")
            assert len(deleted_ids) == 2
            assert set(deleted_ids) == {sym_payments_1.symbol_id, sym_payments_2.symbol_id}

            remaining = client.get_symbols_by_repo(repo)
            assert len(remaining) == 1
            assert remaining[0]["module"] == "email"
        finally:
            client.delete_symbols_by_repo(repo)


@skip_no_postgres
def test_delete_edges_by_repo():
    """delete_edges_by_repo must remove all edges whose symbols belong to that repo."""
    apply_schema(_TEST_CONN)
    repo = _unique_repo()

    sym_a = _make_symbol(repo, name="src_sym")
    sym_b = _make_symbol(repo, name="dst_sym")
    edge = GraphEdge(
        from_symbol=sym_a.symbol_id,
        to_symbol=sym_b.symbol_id,
        relation_type="calls",
    )

    with PostgresClient(_TEST_CONN) as client:
        client.connect()
        try:
            client.upsert_symbols_batch([sym_a, sym_b])
            client.insert_edges([edge])

            # Confirm edge exists before deletion
            assert len(client.get_edges_from(sym_a.symbol_id)) >= 1

            client.delete_edges_by_repo(repo)

            # After deletion, no edges should remain for this symbol
            assert client.get_edges_from(sym_a.symbol_id) == []
            assert client.get_edges_to(sym_b.symbol_id) == []
        finally:
            client.delete_symbols_by_repo(repo)
