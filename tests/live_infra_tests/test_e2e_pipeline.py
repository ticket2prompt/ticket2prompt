"""End-to-end pipeline integration test with real infrastructure."""

import os
import tempfile

import pytest

pytestmark = pytest.mark.integration


def _create_test_repo(base_dir):
    """Create a minimal git repo with Python source files."""
    import git

    repo_dir = os.path.join(base_dir, "test-repo")
    os.makedirs(repo_dir)

    src_dir = os.path.join(repo_dir, "src")
    os.makedirs(src_dir)

    with open(os.path.join(src_dir, "calculator.py"), "w") as f:
        f.write(
            '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Subtract b from a."""
    return a - b


class Calculator:
    """Simple calculator class."""

    def multiply(self, a: int, b: int) -> int:
        return a * b
'''
        )

    with open(os.path.join(src_dir, "utils.py"), "w") as f:
        f.write(
            '''
from src.calculator import add


def sum_list(numbers: list) -> int:
    """Sum a list of numbers using add."""
    result = 0
    for n in numbers:
        result = add(result, n)
    return result
'''
        )

    # Initialize git repo
    repo = git.Repo.init(repo_dir)
    repo.index.add(
        [os.path.join("src", "calculator.py"), os.path.join("src", "utils.py")]
    )
    repo.index.commit("Initial commit")

    return repo_dir


class TestE2EPipeline:
    def test_index_small_repo_and_verify(self, postgres_client, qdrant_store):
        """Index a small test repo and verify data is persisted in Postgres and Qdrant."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = _create_test_repo(tmpdir)
            repo_name = "test/e2e-repo"

            from indexing.monorepo_indexer import MonorepoIndexer

            indexer = MonorepoIndexer(postgres_client, qdrant_store, cache=None)
            result = indexer.index_repository(repo_path, repo_name)

            # Verify indexing result
            assert result.modules_detected >= 1
            total_files = sum(m.files_indexed for m in result.module_results)
            total_symbols = sum(m.symbols_indexed for m in result.module_results)
            assert total_files >= 2  # calculator.py and utils.py
            assert total_symbols >= 3  # add, subtract, Calculator at minimum

            # Verify symbols in Postgres
            symbols = postgres_client.get_symbols_by_repo(repo_name)
            assert len(symbols) >= 3
            symbol_names = {s["name"] for s in symbols}
            assert "add" in symbol_names
            assert "subtract" in symbol_names
            assert "Calculator" in symbol_names

            # Verify points in Qdrant
            info = qdrant_store.get_collection_info()
            assert info["points_count"] >= 3
