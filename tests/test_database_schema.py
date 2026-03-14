import os
import pathlib

import psycopg2
import pytest

from storage.migrations import apply_schema, get_schema_sql

PROJECT_ROOT = pathlib.Path(__file__).parent.parent

_TEST_CONN = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:changeme@localhost:5432/code_context",
)


def postgres_available():
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


# ---------------------------------------------------------------------------
# Layer 1: SQL structure validation (no DB required)
# ---------------------------------------------------------------------------


def test_schema_sql_file_exists():
    schema_path = PROJECT_ROOT / "storage" / "schema.sql"
    assert schema_path.exists(), f"schema.sql not found at {schema_path}"


def test_get_schema_sql_returns_string():
    sql = get_schema_sql()
    assert isinstance(sql, str)
    assert len(sql) > 0


def test_schema_contains_symbols_table():
    sql = get_schema_sql()
    assert "CREATE TABLE IF NOT EXISTS symbols" in sql


def test_schema_contains_files_table():
    sql = get_schema_sql()
    assert "CREATE TABLE IF NOT EXISTS files" in sql


def test_schema_contains_graph_edges_table():
    sql = get_schema_sql()
    assert "CREATE TABLE IF NOT EXISTS graph_edges" in sql


def test_schema_contains_git_metadata_table():
    sql = get_schema_sql()
    assert "CREATE TABLE IF NOT EXISTS git_metadata" in sql


def test_schema_symbols_columns():
    sql = get_schema_sql()
    for column in ("symbol_id", "name", "type", "file_path", "repo", "start_line", "end_line"):
        assert column in sql, f"Expected column '{column}' not found in schema SQL"


def test_schema_files_columns():
    sql = get_schema_sql()
    for column in ("file_id", "file_path", "repo", "last_modified", "commit_count"):
        assert column in sql, f"Expected column '{column}' not found in schema SQL"


def test_schema_graph_edges_columns():
    sql = get_schema_sql()
    for column in ("from_symbol", "to_symbol", "relation_type"):
        assert column in sql, f"Expected column '{column}' not found in schema SQL"


def test_schema_has_indexes():
    sql = get_schema_sql()
    assert "idx_symbols_repo" in sql
    assert "idx_graph_from" in sql


def test_schema_uses_if_not_exists():
    sql = get_schema_sql()
    assert "IF NOT EXISTS" in sql


# ---------------------------------------------------------------------------
# Layer 2: Postgres integration tests (skipped if DB unavailable)
# ---------------------------------------------------------------------------

_ALL_TABLES = {"symbols", "files", "graph_edges", "git_metadata"}


@skip_no_postgres
def test_apply_schema_creates_tables():
    apply_schema(_TEST_CONN)
    conn = psycopg2.connect(_TEST_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s)
                """,
                (list(_ALL_TABLES),),
            )
            found = {row[0] for row in cur.fetchall()}
        assert found == _ALL_TABLES, f"Missing tables: {_ALL_TABLES - found}"
    finally:
        conn.close()


@skip_no_postgres
def test_crud_symbols():
    apply_schema(_TEST_CONN)
    conn = psycopg2.connect(_TEST_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO symbols (symbol_id, name, type, file_path, repo, start_line, end_line)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                ("test-sym-001", "my_function", "function", "src/main.py", "my-repo", 10, 25),
            )
            conn.commit()

            cur.execute(
                "SELECT symbol_id, name, type, file_path, repo, start_line, end_line "
                "FROM symbols WHERE symbol_id = %s",
                ("test-sym-001",),
            )
            row = cur.fetchone()
            assert row is not None, "Inserted symbol row not found"
            symbol_id, name, sym_type, file_path, repo, start_line, end_line = row
            assert symbol_id == "test-sym-001"
            assert name == "my_function"
            assert sym_type == "function"
            assert file_path == "src/main.py"
            assert repo == "my-repo"
            assert start_line == 10
            assert end_line == 25

            cur.execute("DELETE FROM symbols WHERE symbol_id = %s", ("test-sym-001",))
            conn.commit()
    finally:
        conn.close()


@skip_no_postgres
def test_crud_graph_edges():
    apply_schema(_TEST_CONN)
    conn = psycopg2.connect(_TEST_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO graph_edges (from_symbol, to_symbol, relation_type)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                ("sym-a", "sym-b", "calls"),
            )
            edge_id = cur.fetchone()[0]
            conn.commit()

            cur.execute(
                "SELECT from_symbol, to_symbol, relation_type FROM graph_edges WHERE id = %s",
                (edge_id,),
            )
            row = cur.fetchone()
            assert row is not None, "Inserted graph_edge row not found"
            from_symbol, to_symbol, relation_type = row
            assert from_symbol == "sym-a"
            assert to_symbol == "sym-b"
            assert relation_type == "calls"

            cur.execute("DELETE FROM graph_edges WHERE id = %s", (edge_id,))
            conn.commit()
    finally:
        conn.close()
