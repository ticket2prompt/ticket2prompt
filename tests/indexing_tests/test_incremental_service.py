"""Tests for the incremental indexing service."""

from unittest.mock import MagicMock, patch

import pytest

from git_analysis.change_detector import ChangeSet, FileChange, ChangeType
from git_analysis.commit_analyzer import IncrementalIndexResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_change_set(*change_types: ChangeType) -> ChangeSet:
    """Build a ChangeSet with one FileChange per provided ChangeType."""
    changes = [
        FileChange(file_path=f"file_{i}.py", change_type=ct)
        for i, ct in enumerate(change_types)
    ]
    return ChangeSet(changes=changes, from_commit="abc123", to_commit="def456")


def _empty_change_set() -> ChangeSet:
    return ChangeSet(changes=[], from_commit="abc123", to_commit="def456")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunIncrementalFromWebhook:
    """Tests for run_incremental_from_webhook."""

    @patch("indexing.incremental_service.CommitAnalyzer")
    @patch("indexing.incremental_service.detect_changes")
    @patch("indexing.incremental_service.clone_repo")
    @patch("indexing.incremental_service.RedisCache")
    @patch("indexing.incremental_service.QdrantVectorStore")
    @patch("indexing.incremental_service.PostgresClient")
    def test_run_incremental_from_webhook_success(
        self,
        mock_postgres_cls,
        mock_qdrant_cls,
        mock_redis_cls,
        mock_clone_repo,
        mock_detect_changes,
        mock_analyzer_cls,
    ):
        """All dependencies are called with correct arguments; result is returned."""
        # Arrange
        expected_result = IncrementalIndexResult(
            files_processed=2, symbols_added=5, symbols_deleted=1
        )
        change_set = _make_change_set(ChangeType.ADDED, ChangeType.MODIFIED)
        mock_detect_changes.return_value = change_set

        mock_analyzer = MagicMock()
        mock_analyzer.process_changes.return_value = expected_result
        mock_analyzer_cls.return_value = mock_analyzer

        mock_postgres = MagicMock()
        mock_postgres_cls.return_value = mock_postgres
        mock_qdrant = MagicMock()
        mock_qdrant_cls.return_value = mock_qdrant
        mock_cache = MagicMock()
        mock_redis_cls.return_value = mock_cache

        mock_settings = MagicMock()
        mock_settings.clone_base_dir = "/tmp/repos"
        mock_settings.postgres_url = "postgresql://localhost/test"
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_collection_name = "code_symbols"
        mock_settings.embedding_dim = 384
        mock_settings.redis_url = "redis://localhost:6379"

        from indexing.incremental_service import run_incremental_from_webhook

        # Act
        result = run_incremental_from_webhook(
            repo_clone_url="https://github.com/org/repo.git",
            repo_full_name="org/repo",
            before_sha="abc12345",
            after_sha="def45678",
            settings=mock_settings,
        )

        # Assert: clone was called with correct args
        mock_clone_repo.assert_called_once_with(
            "https://github.com/org/repo.git",
            "/tmp/repos/org/repo",
        )

        # Assert: detect_changes was called with correct repo path and SHAs
        mock_detect_changes.assert_called_once_with(
            "/tmp/repos/org/repo", "abc12345", "def45678"
        )

        # Assert: CommitAnalyzer.process_changes was called
        mock_analyzer.process_changes.assert_called_once_with(
            change_set, "/tmp/repos/org/repo", "org/repo"
        )

        # Assert: result is the one returned by process_changes
        assert result is expected_result

        # Assert: storage clients were connected and closed
        mock_postgres.connect.assert_called_once()
        mock_qdrant.connect.assert_called_once()
        mock_qdrant.ensure_collection.assert_called_once()
        mock_qdrant.close.assert_called_once()
        mock_postgres.close.assert_called_once()

    @patch("indexing.incremental_service.CommitAnalyzer")
    @patch("indexing.incremental_service.detect_changes")
    @patch("indexing.incremental_service.clone_repo")
    @patch("indexing.incremental_service.RedisCache")
    @patch("indexing.incremental_service.QdrantVectorStore")
    @patch("indexing.incremental_service.PostgresClient")
    def test_run_incremental_from_webhook_no_changes(
        self,
        mock_postgres_cls,
        mock_qdrant_cls,
        mock_redis_cls,
        mock_clone_repo,
        mock_detect_changes,
        mock_analyzer_cls,
    ):
        """When detect_changes returns no changes, CommitAnalyzer is NOT called."""
        mock_detect_changes.return_value = _empty_change_set()

        mock_settings = MagicMock()
        mock_settings.clone_base_dir = "/tmp/repos"
        mock_settings.postgres_url = "postgresql://localhost/test"
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_collection_name = "code_symbols"
        mock_settings.embedding_dim = 384
        mock_settings.redis_url = "redis://localhost:6379"

        from indexing.incremental_service import run_incremental_from_webhook

        result = run_incremental_from_webhook(
            repo_clone_url="https://github.com/org/repo.git",
            repo_full_name="org/repo",
            before_sha="abc12345",
            after_sha="def45678",
            settings=mock_settings,
        )

        # CommitAnalyzer should not be instantiated or called
        mock_analyzer_cls.assert_not_called()

        # Result should be a default (empty) IncrementalIndexResult
        assert isinstance(result, IncrementalIndexResult)
        assert result.files_processed == 0
        assert result.symbols_added == 0

    @patch("indexing.incremental_service.CommitAnalyzer")
    @patch("indexing.incremental_service.detect_changes")
    @patch("indexing.incremental_service.clone_repo")
    @patch("indexing.incremental_service.RedisCache")
    @patch("indexing.incremental_service.QdrantVectorStore")
    @patch("indexing.incremental_service.PostgresClient")
    def test_run_incremental_from_webhook_redis_unavailable(
        self,
        mock_postgres_cls,
        mock_qdrant_cls,
        mock_redis_cls,
        mock_clone_repo,
        mock_detect_changes,
        mock_analyzer_cls,
    ):
        """When Redis.connect raises, indexing still proceeds with cache=None."""
        change_set = _make_change_set(ChangeType.MODIFIED)
        mock_detect_changes.return_value = change_set

        expected_result = IncrementalIndexResult(files_processed=1)
        mock_analyzer = MagicMock()
        mock_analyzer.process_changes.return_value = expected_result
        mock_analyzer_cls.return_value = mock_analyzer

        # Redis connect raises
        mock_cache = MagicMock()
        mock_cache.connect.side_effect = ConnectionRefusedError("Redis down")
        mock_redis_cls.return_value = mock_cache

        mock_settings = MagicMock()
        mock_settings.clone_base_dir = "/tmp/repos"
        mock_settings.postgres_url = "postgresql://localhost/test"
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_collection_name = "code_symbols"
        mock_settings.embedding_dim = 384
        mock_settings.redis_url = "redis://localhost:6379"

        from indexing.incremental_service import run_incremental_from_webhook

        result = run_incremental_from_webhook(
            repo_clone_url="https://github.com/org/repo.git",
            repo_full_name="org/repo",
            before_sha="abc12345",
            after_sha="def45678",
            settings=mock_settings,
        )

        # process_changes must still be called
        mock_analyzer.process_changes.assert_called_once()

        # CommitAnalyzer should have been created with cache=None
        args, kwargs = mock_analyzer_cls.call_args
        postgres_arg, qdrant_arg, cache_arg = args
        assert cache_arg is None

        # Result should be from process_changes
        assert result is expected_result
