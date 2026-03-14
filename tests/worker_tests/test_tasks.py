"""Tests for Celery task definitions.

Tasks are run eagerly (task_always_eager=True) so no broker or worker is needed.
All heavy dependencies (postgres, qdrant, redis, indexers) are mocked.

Patching strategy: the task functions use lazy imports inside the function body
(e.g. `from config.settings import Settings`). We patch those at their canonical
module paths so the lazy import picks up the mock at call time.
"""

import sys
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

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


@dataclass
class _IncrementalResult:
    files_processed: int
    symbols_added: int
    symbols_deleted: int
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _eager_celery():
    """Force Celery to run tasks synchronously in-process (no broker needed)."""
    from workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest.fixture()
def mock_settings():
    settings = MagicMock()
    settings.postgres_url = "postgresql://localhost/db"
    settings.qdrant_url = "http://localhost:6333"
    settings.qdrant_collection_name = "code_symbols"
    settings.embedding_dim = 384
    settings.redis_url = "redis://localhost:6379"
    settings.clone_base_dir = "/tmp/repos"
    return settings


@pytest.fixture()
def mock_postgres():
    return MagicMock()


@pytest.fixture()
def mock_qdrant():
    return MagicMock()


@pytest.fixture()
def mock_cache():
    return MagicMock()


@pytest.fixture()
def monorepo_result():
    module_result = _ModuleIndexResult(
        module_name="root", files_indexed=5, symbols_indexed=20, edges_created=3,
    )
    return _MonorepoIndexResult(
        modules_detected=2,
        module_results=[module_result],
        cross_module_edges=3,
    )


# ---------------------------------------------------------------------------
# Tests: index_repository_full
# ---------------------------------------------------------------------------

class TestIndexRepositoryFull:
    """Tests for the index_repository_full Celery task.

    Because the task uses lazy imports inside its body, we patch at the
    canonical module/class locations rather than at 'workers.tasks.*'.
    """

    def test_index_repository_full_success(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache, monorepo_result
    ):
        """Task returns expected summary dict on success."""
        from workers.tasks import index_repository_full

        mock_indexer = MagicMock()
        mock_indexer.index_repository.return_value = monorepo_result
        mock_postgres.get_project.return_value = {"project_id": "proj-1", "org_id": "org-1"}

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("indexing.repo_cloner.clone_repo"), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache), \
             patch("indexing.monorepo_indexer.MonorepoIndexer", return_value=mock_indexer):

            result = index_repository_full.apply(
                args=["https://github.com/org/repo.git", "repo", "main"]
            ).get()

        assert result["status"] == "completed"
        assert result["repo_url"] == "https://github.com/org/repo.git"
        assert result["files_indexed"] == 5
        assert result["symbols_indexed"] == 20
        assert result["modules_detected"] == 2
        assert result["cross_module_edges"] == 3

    def test_index_repository_full_cleans_previous_data(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache, monorepo_result
    ):
        """Task calls delete_edges_by_repo, delete_symbols_by_repo, and delete_by_project."""
        from workers.tasks import index_repository_full

        mock_indexer = MagicMock()
        mock_indexer.index_repository.return_value = monorepo_result
        mock_postgres.get_project.return_value = {"project_id": "proj-1", "org_id": "org-1"}

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("indexing.repo_cloner.clone_repo"), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache), \
             patch("indexing.monorepo_indexer.MonorepoIndexer", return_value=mock_indexer):

            index_repository_full.apply(
                args=["https://github.com/org/repo.git", "repo", "main"]
            ).get()

        mock_postgres.delete_edges_by_repo.assert_called_once_with("repo", "", "")
        mock_postgres.delete_symbols_by_repo.assert_called_once_with("repo", "", "")
        mock_qdrant.delete_by_project.assert_called_once_with("")

    def test_index_repository_full_caches_summary(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache, monorepo_result
    ):
        """Completed task writes a summary with status=completed into Redis cache."""
        from workers.tasks import index_repository_full

        mock_indexer = MagicMock()
        mock_indexer.index_repository.return_value = monorepo_result
        mock_postgres.get_project.return_value = {"project_id": "proj-1", "org_id": "org-1"}

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("indexing.repo_cloner.clone_repo"), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache), \
             patch("indexing.monorepo_indexer.MonorepoIndexer", return_value=mock_indexer):

            index_repository_full.apply(
                args=["https://github.com/org/repo.git", "repo", "main"]
            ).get()

        mock_cache.set.assert_called()
        # The final call should have status=completed
        stored_value = mock_cache.set.call_args[0][1]
        assert stored_value["status"] == "completed"

    def test_index_repository_full_proceeds_without_redis(
        self, mock_settings, mock_postgres, mock_qdrant, monorepo_result
    ):
        """Task completes successfully even when Redis is unavailable."""
        from workers.tasks import index_repository_full

        mock_indexer = MagicMock()
        mock_indexer.index_repository.return_value = monorepo_result
        mock_postgres.get_project.return_value = {"project_id": "proj-1", "org_id": "org-1"}

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("indexing.repo_cloner.clone_repo"), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", side_effect=Exception("Redis down")), \
             patch("indexing.monorepo_indexer.MonorepoIndexer", return_value=mock_indexer):

            result = index_repository_full.apply(
                args=["https://github.com/org/repo.git", "repo", "main"]
            ).get()

        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Tests: index_repository_incremental
# ---------------------------------------------------------------------------

class TestIndexRepositoryIncremental:
    """Tests for the index_repository_incremental Celery task.

    The task lazily imports run_incremental_from_webhook, so we inject a mock
    module via sys.modules before calling apply().
    """

    def test_index_repository_incremental_success(self):
        """Task returns expected summary dict on success."""
        from workers.tasks import index_repository_incremental

        incremental_result = _IncrementalResult(
            files_processed=3,
            symbols_added=12,
            symbols_deleted=2,
            errors=[],
        )

        mock_incremental_module = MagicMock()
        mock_incremental_module.run_incremental_from_webhook.return_value = incremental_result

        with patch.dict(sys.modules, {"indexing.incremental_service": mock_incremental_module}):
            result = index_repository_incremental.apply(
                args=[
                    "https://github.com/org/repo.git",
                    "org/repo",
                    "abc123",
                    "def456",
                ]
            ).get()

        assert result["status"] == "completed"
        assert result["files_processed"] == 3
        assert result["symbols_added"] == 12
        assert result["symbols_deleted"] == 2
        assert result["errors"] == []

    def test_index_repository_incremental_calls_service_with_correct_args(self):
        """Task passes all arguments correctly to run_incremental_from_webhook."""
        from workers.tasks import index_repository_incremental

        incremental_result = _IncrementalResult(
            files_processed=1, symbols_added=5, symbols_deleted=0, errors=[],
        )

        mock_incremental_module = MagicMock()
        mock_incremental_module.run_incremental_from_webhook.return_value = incremental_result

        with patch.dict(sys.modules, {"indexing.incremental_service": mock_incremental_module}):
            index_repository_incremental.apply(
                args=[
                    "https://github.com/org/repo.git",
                    "org/repo",
                    "sha_before",
                    "sha_after",
                ]
            ).get()

        mock_incremental_module.run_incremental_from_webhook.assert_called_once_with(
            repo_clone_url="https://github.com/org/repo.git",
            repo_full_name="org/repo",
            before_sha="sha_before",
            after_sha="sha_after",
        )
