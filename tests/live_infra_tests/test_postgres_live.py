"""Integration tests for PostgresClient against real PostgreSQL."""

import pytest

pytestmark = pytest.mark.integration


class TestSymbolOperations:
    def test_upsert_and_get_symbol(self, postgres_client):
        symbol = {
            "symbol_id": "test::func_a",
            "name": "func_a",
            "type": "function",
            "file_path": "src/module.py",
            "repo": "test-repo",
            "start_line": 10,
            "end_line": 20,
            "module": "core",
        }
        postgres_client.upsert_symbol(symbol)
        result = postgres_client.get_symbol("test::func_a")

        assert result is not None
        assert result["name"] == "func_a"
        assert result["type"] == "function"
        assert result["file_path"] == "src/module.py"
        assert result["repo"] == "test-repo"
        assert result["module"] == "core"

    def test_upsert_symbols_batch(self, postgres_client):
        symbols = [
            {
                "symbol_id": f"batch::sym_{i}",
                "name": f"sym_{i}",
                "type": "function",
                "file_path": "src/a.py",
                "repo": "batch-repo",
                "start_line": i,
                "end_line": i + 5,
            }
            for i in range(10)
        ]
        postgres_client.upsert_symbols_batch(symbols)
        results = postgres_client.get_symbols_by_repo("batch-repo")
        assert len(results) == 10

    def test_delete_symbols_by_file(self, postgres_client):
        symbols = [
            {
                "symbol_id": "del::a",
                "name": "a",
                "type": "function",
                "file_path": "src/delete_me.py",
                "repo": "del-repo",
                "start_line": 1,
                "end_line": 5,
            },
            {
                "symbol_id": "del::b",
                "name": "b",
                "type": "class",
                "file_path": "src/keep_me.py",
                "repo": "del-repo",
                "start_line": 1,
                "end_line": 5,
            },
        ]
        postgres_client.upsert_symbols_batch(symbols)
        deleted = postgres_client.delete_symbols_by_file("src/delete_me.py", "del-repo")
        assert "del::a" in deleted
        assert postgres_client.get_symbol("del::b") is not None

    def test_get_symbols_by_module(self, postgres_client):
        symbols = [
            {
                "symbol_id": "mod::a",
                "name": "a",
                "type": "function",
                "file_path": "src/a.py",
                "repo": "mod-repo",
                "start_line": 1,
                "end_line": 5,
                "module": "api",
            },
            {
                "symbol_id": "mod::b",
                "name": "b",
                "type": "function",
                "file_path": "src/b.py",
                "repo": "mod-repo",
                "start_line": 1,
                "end_line": 5,
                "module": "core",
            },
        ]
        postgres_client.upsert_symbols_batch(symbols)
        api_syms = postgres_client.get_symbols_by_module("mod-repo", "api")
        assert len(api_syms) == 1
        assert api_syms[0]["name"] == "a"

    def test_search_symbols_by_name(self, postgres_client):
        symbols = [
            {
                "symbol_id": "search::calculate_total",
                "name": "calculate_total",
                "type": "function",
                "file_path": "src/a.py",
                "repo": "search-repo",
                "start_line": 1,
                "end_line": 5,
            },
            {
                "symbol_id": "search::get_user",
                "name": "get_user",
                "type": "function",
                "file_path": "src/b.py",
                "repo": "search-repo",
                "start_line": 1,
                "end_line": 5,
            },
        ]
        postgres_client.upsert_symbols_batch(symbols)
        results = postgres_client.search_symbols_by_name("search-repo", "calculate")
        assert len(results) == 1
        assert results[0]["name"] == "calculate_total"


class TestEdgeOperations:
    def test_insert_and_get_edges(self, postgres_client):
        # Insert the symbols that edges reference first (FK-like consistency)
        symbols = [
            {
                "symbol_id": "edge::caller",
                "name": "caller",
                "type": "function",
                "file_path": "src/a.py",
                "repo": "edge-repo",
                "start_line": 1,
                "end_line": 5,
            },
            {
                "symbol_id": "edge::callee",
                "name": "callee",
                "type": "function",
                "file_path": "src/b.py",
                "repo": "edge-repo",
                "start_line": 1,
                "end_line": 5,
            },
        ]
        postgres_client.upsert_symbols_batch(symbols)

        edges = [
            {"from_symbol": "edge::caller", "to_symbol": "edge::callee", "relation_type": "calls"}
        ]
        postgres_client.insert_edges(edges)

        from_edges = postgres_client.get_edges_from("edge::caller")
        assert len(from_edges) == 1
        assert from_edges[0]["to_symbol"] == "edge::callee"

        to_edges = postgres_client.get_edges_to("edge::callee")
        assert len(to_edges) == 1


class TestGitMetadata:
    def test_upsert_and_get_git_metadata(self, postgres_client):
        postgres_client.upsert_git_metadata(
            file_path="src/a.py",
            repo="meta-repo",
            last_commit_hash="abc123",
            last_commit_author="dev@example.com",
            commit_frequency=42,
        )
        result = postgres_client.get_git_metadata("src/a.py", "meta-repo")
        assert result is not None
        assert result["last_commit_hash"] == "abc123"
        assert result["commit_frequency"] == 42
