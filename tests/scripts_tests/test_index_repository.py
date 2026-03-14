"""Tests for scripts/index_repository.py — written first (TDD)."""

import logging
import sys
from dataclasses import dataclass, field
from unittest.mock import MagicMock, call, mock_open, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — lightweight stand-ins for dataclasses defined in other modules
# ---------------------------------------------------------------------------

@dataclass
class _ChangeSet:
    changes: list
    from_commit: str
    to_commit: str

    @property
    def added(self):
        return [c for c in self.changes if getattr(c, 'change_type', None) == 'added']

    @property
    def modified(self):
        return [c for c in self.changes if getattr(c, 'change_type', None) == 'modified']

    @property
    def deleted(self):
        return [c for c in self.changes if getattr(c, 'change_type', None) == 'deleted']


@dataclass
class _ModuleIndexResult:
    module_name: str
    files_indexed: int
    symbols_indexed: int
    edges_created: int
    errors: list = field(default_factory=list)


@dataclass
class _MonorepoIndexResult:
    modules_detected: int
    module_results: list = field(default_factory=list)
    cross_module_edges: int = 0
    total_errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_parse_args_required_repo(self):
        """parse_args raises SystemExit when --repo is missing."""
        from scripts.index_repository import parse_args

        with pytest.raises(SystemExit):
            parse_args([])

    def test_parse_args_defaults(self):
        """parse_args sets sensible defaults for optional arguments."""
        from scripts.index_repository import parse_args

        ns = parse_args(["--repo", "https://github.com/org/repo.git"])

        assert ns.repo == "https://github.com/org/repo.git"
        assert ns.branch is None
        assert ns.target_dir is None
        assert ns.incremental is False
        assert ns.from_commit is None
        assert ns.dry_run is False
        assert ns.log_level == "INFO"

    def test_parse_args_all_options(self):
        """parse_args correctly captures every flag."""
        from scripts.index_repository import parse_args

        ns = parse_args([
            "--repo", "https://github.com/org/repo.git",
            "--branch", "main",
            "--target-dir", "/tmp/myrepo",
            "--incremental",
            "--from-commit", "abc123",
            "--dry-run",
            "--log-level", "DEBUG",
        ])

        assert ns.repo == "https://github.com/org/repo.git"
        assert ns.branch == "main"
        assert ns.target_dir == "/tmp/myrepo"
        assert ns.incremental is True
        assert ns.from_commit == "abc123"
        assert ns.dry_run is True
        assert ns.log_level == "DEBUG"


# ---------------------------------------------------------------------------
# extract_repo_name
# ---------------------------------------------------------------------------

class TestExtractRepoName:
    def test_extract_repo_name(self):
        """extract_repo_name handles a variety of URL formats."""
        from scripts.index_repository import extract_repo_name

        cases = [
            ("https://github.com/org/repo.git", "org/repo"),
            ("https://github.com/org/repo",     "org/repo"),
            ("git@github.com:org/repo.git",     "org/repo"),
            ("https://github.com/myorg/my-service.git", "myorg/my-service"),
        ]
        for url, expected in cases:
            assert extract_repo_name(url) == expected, f"Failed for {url!r}"


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------

class TestSetupLogging:
    def test_setup_logging_configures_root_logger(self):
        """setup_logging sets the root logger to the given level."""
        from scripts.index_repository import setup_logging

        setup_logging("DEBUG")
        assert logging.getLogger().level == logging.DEBUG

        # Reset so other tests aren't affected
        setup_logging("WARNING")


# ---------------------------------------------------------------------------
# run_full_index
# ---------------------------------------------------------------------------

class TestRunFullIndex:
    """Unit-test that run_full_index delegates to MonorepoIndexer."""

    def _make_monorepo_result(self, files=3, symbols=10) -> _MonorepoIndexResult:
        module = _ModuleIndexResult(
            module_name="root",
            files_indexed=files,
            symbols_indexed=symbols,
            edges_created=2,
        )
        return _MonorepoIndexResult(
            modules_detected=1,
            module_results=[module],
            cross_module_edges=0,
        )

    def test_run_full_index_delegates_to_monorepo_indexer(self):
        """run_full_index cleans storage then delegates to MonorepoIndexer."""
        from scripts.index_repository import run_full_index

        monorepo_result = self._make_monorepo_result(files=3, symbols=10)

        postgres = MagicMock()
        qdrant = MagicMock()
        settings = MagicMock()
        settings.redis_url = "redis://localhost:6379"

        mock_indexer = MagicMock()
        mock_indexer.index_repository.return_value = monorepo_result
        mock_indexer_cls = MagicMock(return_value=mock_indexer)

        mock_cache = MagicMock()
        mock_redis_cls = MagicMock(return_value=mock_cache)

        with patch("scripts.index_repository.RedisCache", mock_redis_cls), \
             patch("indexing.monorepo_indexer.MonorepoIndexer", mock_indexer_cls):
            # Patch at the import site inside run_full_index
            with patch("builtins.__import__", wraps=__import__) as mock_import:
                import indexing.monorepo_indexer as _mi_mod
                orig_cls = _mi_mod.MonorepoIndexer
                _mi_mod.MonorepoIndexer = mock_indexer_cls
                try:
                    result = run_full_index(
                        repo_path="/tmp/repo",
                        repo_name="org/repo",
                        postgres=postgres,
                        qdrant=qdrant,
                        settings=settings,
                    )
                finally:
                    _mi_mod.MonorepoIndexer = orig_cls

        # Storage cleaned first
        postgres.delete_edges_by_repo.assert_called_once_with("org/repo")
        postgres.delete_symbols_by_repo.assert_called_once_with("org/repo")
        qdrant.delete_by_repo.assert_called_once_with("org/repo")

        # Returns a summary dict with expected keys
        assert isinstance(result, dict)
        assert "files_processed" in result
        assert "symbols_extracted" in result
        assert "embeddings_generated" in result
        assert "modules_detected" in result
        assert result["files_processed"] == 3
        assert result["symbols_extracted"] == 10
        assert result["embeddings_generated"] == 10
        assert result["modules_detected"] == 1

    def test_run_full_index_uses_monorepo_indexer(self):
        """run_full_index instantiates MonorepoIndexer and calls index_repository."""
        from scripts.index_repository import run_full_index

        monorepo_result = self._make_monorepo_result(files=5, symbols=20)

        postgres = MagicMock()
        qdrant = MagicMock()
        settings = MagicMock()
        settings.redis_url = "redis://localhost:6379"

        mock_indexer = MagicMock()
        mock_indexer.index_repository.return_value = monorepo_result

        mock_cache = MagicMock()

        with patch("scripts.index_repository.RedisCache", return_value=mock_cache):
            import indexing.monorepo_indexer as _mi_mod
            orig_cls = _mi_mod.MonorepoIndexer
            _mi_mod.MonorepoIndexer = MagicMock(return_value=mock_indexer)
            try:
                result = run_full_index(
                    repo_path="/tmp/repo",
                    repo_name="org/repo",
                    postgres=postgres,
                    qdrant=qdrant,
                    settings=settings,
                )
            finally:
                _mi_mod.MonorepoIndexer = orig_cls

        mock_indexer.index_repository.assert_called_once_with("/tmp/repo", "org/repo")
        assert result["files_processed"] == 5
        assert result["symbols_extracted"] == 20


# ---------------------------------------------------------------------------
# run_incremental_index
# ---------------------------------------------------------------------------

class TestRunIncrementalIndex:
    @patch("scripts.index_repository.CommitAnalyzer")
    @patch("scripts.index_repository.detect_changes")
    def test_run_incremental_index(self, mock_detect_changes, mock_commit_analyzer_cls):
        """run_incremental_index detects changes and delegates to CommitAnalyzer."""
        from scripts.index_repository import run_incremental_index

        change_set = _ChangeSet(changes=[], from_commit="abc", to_commit="def")
        mock_detect_changes.return_value = change_set

        analyzer_instance = MagicMock()
        analyzer_instance.process_changes.return_value = {"processed": 3}
        mock_commit_analyzer_cls.return_value = analyzer_instance

        postgres = MagicMock()
        qdrant = MagicMock()
        cache = MagicMock()

        result = run_incremental_index(
            repo_path="/tmp/repo",
            repo_name="org/repo",
            from_commit="abc",
            to_commit="def",
            postgres=postgres,
            qdrant=qdrant,
            cache=cache,
        )

        mock_detect_changes.assert_called_once_with("/tmp/repo", "abc", "def")
        mock_commit_analyzer_cls.assert_called_once_with(postgres, qdrant, cache)
        analyzer_instance.process_changes.assert_called_once_with(
            change_set, "/tmp/repo", "org/repo"
        )
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------

class TestDryRun:
    @patch("scripts.index_repository.filter_files")
    def test_dry_run_skips_storage_writes(self, mock_filter):
        """In dry-run mode, no data is written to postgres or qdrant."""
        from scripts.index_repository import run_full_index

        mock_filter.return_value = ["file_0.py", "file_1.py"]

        postgres = MagicMock()
        qdrant = MagicMock()
        settings = MagicMock()

        result = run_full_index(
            repo_path="/tmp/repo",
            repo_name="org/repo",
            postgres=postgres,
            qdrant=qdrant,
            settings=settings,
            dry_run=True,
        )

        # No writes in dry-run mode
        postgres.delete_edges_by_repo.assert_not_called()
        postgres.delete_symbols_by_repo.assert_not_called()
        qdrant.delete_by_repo.assert_not_called()
        postgres.upsert_symbols_batch.assert_not_called()
        qdrant.upsert_embeddings.assert_not_called()
        postgres.insert_edges.assert_not_called()

        # Returns a summary dict
        assert isinstance(result, dict)
        assert "files_processed" in result
        assert result["files_processed"] == 2


# ---------------------------------------------------------------------------
# main — end-to-end with patches
# ---------------------------------------------------------------------------

class TestMain:
    @patch("scripts.index_repository.run_full_index")
    @patch("scripts.index_repository.clone_repo")
    @patch("scripts.index_repository.RedisCache")
    @patch("scripts.index_repository.QdrantVectorStore")
    @patch("scripts.index_repository.PostgresClient")
    @patch("scripts.index_repository.Settings")
    def test_main_full_index(
        self,
        mock_settings_cls,
        mock_pg_cls,
        mock_qdrant_cls,
        mock_redis_cls,
        mock_clone,
        mock_run_full,
    ):
        """main() wires up Settings, clients, clone, and run_full_index."""
        from scripts.index_repository import main

        # Settings
        settings = MagicMock()
        settings.postgres_url = "postgresql://localhost/db"
        settings.qdrant_url = "http://localhost:6333"
        settings.redis_url = "redis://localhost:6379"
        settings.qdrant_collection_name = "code_symbols"
        settings.embedding_dim = 384
        settings.clone_base_dir = "/tmp/repos"
        settings.log_level = "INFO"
        mock_settings_cls.return_value = settings

        # Clients
        pg = MagicMock()
        mock_pg_cls.return_value = pg
        qdrant = MagicMock()
        mock_qdrant_cls.return_value = qdrant

        # Cloned repo
        repo = MagicMock()
        repo.head.commit.hexsha = "deadbeef"
        mock_clone.return_value = repo

        # Full index result
        mock_run_full.return_value = {
            "files_processed": 5,
            "symbols_extracted": 20,
            "embeddings_generated": 20,
        }

        main(["--repo", "https://github.com/org/repo.git"])

        # Settings instantiated
        mock_settings_cls.assert_called_once()

        # Postgres and Qdrant connected
        pg.connect.assert_called_once()
        qdrant.connect.assert_called_once()
        qdrant.ensure_collection.assert_called_once()

        # Repo cloned
        mock_clone.assert_called_once()

        # Full index executed
        mock_run_full.assert_called_once()

        # Connections closed
        pg.close.assert_called_once()
        qdrant.close.assert_called_once()

    @patch("scripts.index_repository.run_incremental_index")
    @patch("scripts.index_repository.clone_repo")
    @patch("scripts.index_repository.RedisCache")
    @patch("scripts.index_repository.QdrantVectorStore")
    @patch("scripts.index_repository.PostgresClient")
    @patch("scripts.index_repository.Settings")
    def test_main_incremental_index(
        self,
        mock_settings_cls,
        mock_pg_cls,
        mock_qdrant_cls,
        mock_redis_cls,
        mock_clone,
        mock_run_incremental,
    ):
        """main() with --incremental calls run_incremental_index."""
        from scripts.index_repository import main

        settings = MagicMock()
        settings.postgres_url = "postgresql://localhost/db"
        settings.qdrant_url = "http://localhost:6333"
        settings.redis_url = "redis://localhost:6379"
        settings.qdrant_collection_name = "code_symbols"
        settings.embedding_dim = 384
        settings.clone_base_dir = "/tmp/repos"
        settings.log_level = "INFO"
        mock_settings_cls.return_value = settings

        pg = MagicMock()
        mock_pg_cls.return_value = pg
        qdrant = MagicMock()
        mock_qdrant_cls.return_value = qdrant
        cache = MagicMock()
        mock_redis_cls.return_value = cache

        repo = MagicMock()
        repo.head.commit.hexsha = "deadbeef"
        mock_clone.return_value = repo

        mock_run_incremental.return_value = {"processed": 3}

        main([
            "--repo", "https://github.com/org/repo.git",
            "--incremental",
            "--from-commit", "abc123",
        ])

        mock_run_incremental.assert_called_once()

        # Cache connected and closed for incremental mode
        cache.connect.assert_called_once()
        cache.close.assert_called_once()

    @patch("scripts.index_repository.run_full_index")
    @patch("scripts.index_repository.clone_repo")
    @patch("scripts.index_repository.RedisCache")
    @patch("scripts.index_repository.QdrantVectorStore")
    @patch("scripts.index_repository.PostgresClient")
    @patch("scripts.index_repository.Settings")
    def test_main_branch_checkout(
        self,
        mock_settings_cls,
        mock_pg_cls,
        mock_qdrant_cls,
        mock_redis_cls,
        mock_clone,
        mock_run_full,
    ):
        """main() checks out the specified branch after cloning."""
        from scripts.index_repository import main

        settings = MagicMock()
        settings.postgres_url = "postgresql://localhost/db"
        settings.qdrant_url = "http://localhost:6333"
        settings.redis_url = "redis://localhost:6379"
        settings.qdrant_collection_name = "code_symbols"
        settings.embedding_dim = 384
        settings.clone_base_dir = "/tmp/repos"
        settings.log_level = "INFO"
        mock_settings_cls.return_value = settings

        mock_pg_cls.return_value = MagicMock()
        mock_qdrant_cls.return_value = MagicMock()

        repo = MagicMock()
        repo.head.commit.hexsha = "deadbeef"
        mock_clone.return_value = repo
        mock_run_full.return_value = {}

        main(["--repo", "https://github.com/org/repo.git", "--branch", "develop"])

        repo.git.checkout.assert_called_once_with("develop")
