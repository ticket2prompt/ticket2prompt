"""Additional Celery task tests for uncovered lines (128-150, 194-196, 202-270).

Covers:
- index_repository_full error paths: max-retry exhaustion and retrying state
- index_repository_incremental error path (lines 194-196)
- sync_jira_tickets task (lines 202-270)
"""

import sys
from dataclasses import dataclass, field
from unittest.mock import MagicMock, call, patch

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


@dataclass
class _JiraSyncResult:
    tickets_synced: int = 0
    embeddings_created: int = 0
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _eager_celery():
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
    settings.embedding_dim = 384
    settings.redis_url = "redis://localhost:6379"
    settings.clone_base_dir = "/tmp/repos"
    settings.credential_encryption_key = "test-key"
    return settings


@pytest.fixture()
def mock_postgres():
    pg = MagicMock()
    pg.get_project.return_value = {
        "project_id": "proj-1",
        "org_id": "org-1",
        "slug": "myproject",
        "jira_base_url": "https://example.atlassian.net",
        "jira_email": "user@example.com",
        "jira_api_token_encrypted": "encrypted-token",
    }
    return pg


@pytest.fixture()
def mock_qdrant():
    return MagicMock()


@pytest.fixture()
def mock_cache():
    return MagicMock()


@pytest.fixture()
def monorepo_result():
    mod = _ModuleIndexResult(module_name="root", files_indexed=3, symbols_indexed=10, edges_created=1)
    return _MonorepoIndexResult(modules_detected=1, module_results=[mod], cross_module_edges=0)


# ---------------------------------------------------------------------------
# index_repository_full — error/retry paths (lines 128-150)
# ---------------------------------------------------------------------------

class TestIndexRepositoryFullErrorPaths:
    def _base_patches(self, mock_settings, mock_postgres, mock_qdrant, mock_cache):
        return {
            "config.settings.Settings": mock_settings,
            "storage.postgres.PostgresClient": mock_postgres,
            "storage.qdrant_client.get_qdrant_for_project": mock_qdrant,
            "storage.redis_cache.RedisCache": mock_cache,
        }

    def test_project_not_found_raises_value_error(self, mock_settings, mock_qdrant, mock_cache):
        from workers.tasks import index_repository_full

        mock_postgres = MagicMock()
        mock_postgres.get_project.return_value = None

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache):

            with pytest.raises(Exception):
                index_repository_full.apply(
                    args=["https://github.com/org/repo.git", "repo", "main"]
                ).get()

    def test_max_retries_exhausted_caches_failed_status(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache, monorepo_result
    ):
        """When retries >= max_retries, task caches 'failed' status and re-raises."""
        from workers.tasks import index_repository_full

        mock_indexer = MagicMock()
        mock_indexer.index_repository.side_effect = RuntimeError("indexing failed")
        mock_postgres.get_project.return_value = {"project_id": "proj-1", "org_id": "org-1"}

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("indexing.repo_cloner.clone_repo"), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache), \
             patch("indexing.monorepo_indexer.MonorepoIndexer", return_value=mock_indexer):

            # apply() with retries=3 means self.request.retries=3 >= max_retries=3
            with pytest.raises(RuntimeError):
                index_repository_full.apply(
                    args=["https://github.com/org/repo.git", "repo", "main"],
                    kwargs={},
                    retries=3,
                ).get()

        # Should have cached a "failed" status at some point
        set_calls = mock_cache.set.call_args_list
        statuses = [c[0][1].get("status") for c in set_calls if isinstance(c[0][1], dict)]
        assert "failed" in statuses

    def test_postgres_closed_on_exception(self, mock_settings, mock_qdrant, mock_cache):
        from workers.tasks import index_repository_full

        mock_postgres = MagicMock()
        mock_postgres.get_project.side_effect = RuntimeError("DB error")

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache):

            with pytest.raises(Exception):
                index_repository_full.apply(
                    args=["https://github.com/org/repo.git", "repo", "main"],
                    retries=3,
                ).get()

        mock_postgres.close.assert_called()

    def test_qdrant_closed_on_exception(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache
    ):
        from workers.tasks import index_repository_full

        mock_qdrant_instance = MagicMock()
        # Fail after qdrant is created
        mock_qdrant_instance.ensure_collection.side_effect = RuntimeError("Qdrant error")
        mock_postgres.get_project.return_value = {"project_id": "proj-1", "org_id": "org-1"}

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant_instance), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache):

            with pytest.raises(Exception):
                index_repository_full.apply(
                    args=["https://github.com/org/repo.git", "repo", "main"],
                    retries=3,
                ).get()

        mock_qdrant_instance.close.assert_called()


# ---------------------------------------------------------------------------
# index_repository_incremental — error path (lines 194-196)
# ---------------------------------------------------------------------------

class TestIndexRepositoryIncrementalErrorPath:
    def test_incremental_failure_retries(self):
        from workers.tasks import index_repository_incremental

        mock_module = MagicMock()
        mock_module.run_incremental_from_webhook.side_effect = RuntimeError("service down")

        with patch.dict(sys.modules, {"indexing.incremental_service": mock_module}):
            with pytest.raises(RuntimeError):
                index_repository_incremental.apply(
                    args=[
                        "https://github.com/org/repo.git",
                        "org/repo",
                        "abc123",
                        "def456",
                    ],
                    retries=3,
                ).get()

    def test_incremental_error_logs_failure(self, caplog):
        import logging
        from workers.tasks import index_repository_incremental

        mock_module = MagicMock()
        mock_module.run_incremental_from_webhook.side_effect = RuntimeError("boom")

        with caplog.at_level(logging.ERROR, logger="workers.tasks"):
            with patch.dict(sys.modules, {"indexing.incremental_service": mock_module}):
                with pytest.raises(RuntimeError):
                    index_repository_incremental.apply(
                        args=[
                            "https://github.com/org/repo.git",
                            "org/repo",
                            "abc123",
                            "def456",
                        ],
                        retries=3,
                    ).get()

        assert any("Incremental index failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# sync_jira_tickets task (lines 202-270)
# ---------------------------------------------------------------------------

class TestSyncJiraTickets:
    def _patch_all(self, mock_settings, mock_postgres, mock_qdrant, mock_cache,
                   jira_client=None, jira_indexer_result=None):
        """Return a context manager stack for the sync_jira_tickets task."""
        if jira_client is None:
            jira_client = MagicMock()
        if jira_indexer_result is None:
            jira_indexer_result = _JiraSyncResult(tickets_synced=5, embeddings_created=10)

        mock_jira_indexer = MagicMock()
        mock_jira_indexer.sync_tickets.return_value = jira_indexer_result

        patches = [
            patch("config.settings.Settings", return_value=mock_settings),
            patch("storage.postgres.PostgresClient", return_value=mock_postgres),
            patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant),
            patch("storage.redis_cache.RedisCache", return_value=mock_cache),
            patch("integrations.client_factory.build_jira_client", return_value=jira_client),
            patch("indexing.jira_indexer.JiraIndexer", return_value=mock_jira_indexer),
        ]
        return patches, mock_jira_indexer

    def test_success_returns_summary(self, mock_settings, mock_postgres, mock_qdrant, mock_cache):
        from workers.tasks import sync_jira_tickets

        patches, _ = self._patch_all(mock_settings, mock_postgres, mock_qdrant, mock_cache)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = sync_jira_tickets.apply(args=["proj-1"]).get()

        assert result["status"] == "completed"
        assert result["tickets_synced"] == 5
        assert result["embeddings_created"] == 10

    def test_project_not_found_raises(self, mock_settings, mock_qdrant, mock_cache):
        from workers.tasks import sync_jira_tickets

        mock_postgres = MagicMock()
        mock_postgres.get_project.return_value = None

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache):

            with pytest.raises(Exception):
                sync_jira_tickets.apply(args=["nonexistent-proj"], retries=3).get()

    def test_calls_postgres_close_in_finally(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache
    ):
        from workers.tasks import sync_jira_tickets

        patches, _ = self._patch_all(mock_settings, mock_postgres, mock_qdrant, mock_cache)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            sync_jira_tickets.apply(args=["proj-1"]).get()

        mock_postgres.close.assert_called()

    def test_calls_qdrant_close_in_finally(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache
    ):
        from workers.tasks import sync_jira_tickets

        mock_qdrant_instance = MagicMock()
        patches, _ = self._patch_all(
            mock_settings, mock_postgres, mock_qdrant_instance, mock_cache
        )

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            sync_jira_tickets.apply(args=["proj-1"]).get()

        mock_qdrant_instance.close.assert_called()

    def test_calls_cache_close_in_finally(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache
    ):
        from workers.tasks import sync_jira_tickets

        patches, _ = self._patch_all(mock_settings, mock_postgres, mock_qdrant, mock_cache)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            sync_jira_tickets.apply(args=["proj-1"]).get()

        mock_cache.close.assert_called()

    def test_caches_summary_on_success(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache
    ):
        from workers.tasks import sync_jira_tickets

        patches, _ = self._patch_all(mock_settings, mock_postgres, mock_qdrant, mock_cache)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            sync_jira_tickets.apply(args=["proj-1"]).get()

        mock_cache.set.assert_called()
        stored = mock_cache.set.call_args[0][1]
        assert stored["status"] == "completed"

    def test_proceeds_without_redis(self, mock_settings, mock_postgres, mock_qdrant):
        from workers.tasks import sync_jira_tickets

        mock_jira_indexer = MagicMock()
        mock_jira_indexer.sync_tickets.return_value = _JiraSyncResult(tickets_synced=2)

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", side_effect=Exception("Redis down")), \
             patch("integrations.client_factory.build_jira_client", return_value=MagicMock()), \
             patch("indexing.jira_indexer.JiraIndexer", return_value=mock_jira_indexer):

            result = sync_jira_tickets.apply(args=["proj-1"]).get()

        assert result["status"] == "completed"

    def test_sync_failure_caches_failed_status(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache
    ):
        from workers.tasks import sync_jira_tickets

        mock_jira_indexer = MagicMock()
        mock_jira_indexer.sync_tickets.side_effect = RuntimeError("Jira API down")
        mock_postgres.get_project.return_value = {
            "project_id": "proj-1",
            "org_id": "org-1",
            "slug": "myproject",
            "jira_base_url": "https://example.atlassian.net",
            "jira_email": "user@example.com",
            "jira_api_token_encrypted": "encrypted-token",
        }

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache), \
             patch("integrations.client_factory.build_jira_client", return_value=MagicMock()), \
             patch("indexing.jira_indexer.JiraIndexer", return_value=mock_jira_indexer):

            with pytest.raises(RuntimeError):
                sync_jira_tickets.apply(args=["proj-1"], retries=3).get()

        set_calls = mock_cache.set.call_args_list
        statuses = [c[0][1].get("status") for c in set_calls if isinstance(c[0][1], dict)]
        assert "failed" in statuses

    def test_uses_project_slug_as_project_key(
        self, mock_settings, mock_postgres, mock_qdrant, mock_cache
    ):
        from workers.tasks import sync_jira_tickets

        mock_postgres.get_project.return_value = {
            "project_id": "proj-1",
            "org_id": "org-1",
            "slug": "myapp",
            "jira_base_url": "https://example.atlassian.net",
            "jira_email": "user@example.com",
            "jira_api_token_encrypted": "encrypted-token",
        }

        mock_jira_indexer = MagicMock()
        mock_jira_indexer.sync_tickets.return_value = _JiraSyncResult()

        with patch("config.settings.Settings", return_value=mock_settings), \
             patch("storage.postgres.PostgresClient", return_value=mock_postgres), \
             patch("storage.qdrant_client.get_qdrant_for_project", return_value=mock_qdrant), \
             patch("storage.redis_cache.RedisCache", return_value=mock_cache), \
             patch("integrations.client_factory.build_jira_client", return_value=MagicMock()), \
             patch("indexing.jira_indexer.JiraIndexer", return_value=mock_jira_indexer):

            sync_jira_tickets.apply(args=["proj-1"]).get()

        mock_jira_indexer.sync_tickets.assert_called_once_with("MYAPP")
