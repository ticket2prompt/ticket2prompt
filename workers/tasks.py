"""Celery task definitions for repository indexing."""

import logging
import os

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_progress(cache, org_id: str, task_id: str, data: dict) -> None:
    """Write indexing progress to cache if available."""
    from storage.redis_cache import scoped_key
    if cache is not None:
        cache.set(scoped_key(org_id, "indexing", task_id), data, ttl=86400)


@celery_app.task(name="index_repository_full", bind=True, max_retries=3)
def index_repository_full(
    self,
    repo_url: str,
    repo_name: str,
    branch: str = "main",
    project_id: str = "",
    org_id: str = "",
):
    """Full repository indexing task.

    Clones the repo, detects modules, and indexes everything.
    """
    from config.settings import Settings
    from indexing.monorepo_indexer import MonorepoIndexer
    from indexing.repo_cloner import clone_repo
    from storage.postgres import PostgresClient
    from storage.qdrant_client import get_qdrant_for_project
    from storage.redis_cache import RedisCache

    settings = Settings()
    repo_path = os.path.join(settings.clone_base_dir, org_id, project_id)

    logger.info("Starting full index task for %s (task_id=%s)", repo_name, self.request.id)

    postgres = PostgresClient(settings.postgres_url)

    cache = None
    try:
        cache = RedisCache(settings.redis_url)
        cache.connect()
    except Exception:
        logger.warning("Redis unavailable for cache, proceeding without")
        cache = None

    qdrant = None
    try:
        postgres.connect()

        project = postgres.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        qdrant = get_qdrant_for_project(project, settings.qdrant_url, settings.embedding_dim, "code")
        qdrant.connect()
        qdrant.ensure_collection()

        # Clone the repository
        _update_progress(cache, org_id, self.request.id, {
            "status": "cloning",
            "repo_url": repo_url,
            "project_id": project_id,
        })
        clone_repo(repo_url, repo_path)

        # Clean previous data
        postgres.delete_edges_by_repo(repo_name, org_id, project_id)
        postgres.delete_symbols_by_repo(repo_name, org_id, project_id)
        qdrant.delete_by_project(project_id)

        _update_progress(cache, org_id, self.request.id, {
            "status": "parsing",
            "repo_url": repo_url,
            "project_id": project_id,
            "files_total": 0,
            "files_parsed": 0,
        })

        def on_file_progress(data: dict) -> None:
            _update_progress(cache, org_id, self.request.id, {
                "status": "parsing",
                "repo_url": repo_url,
                "project_id": project_id,
                "files_total": data["files_total"],
                "files_parsed": data["files_parsed"],
                "current_file": data["current_file"],
            })

        # Index with MonorepoIndexer
        indexer = MonorepoIndexer(
            postgres, qdrant, cache,
            org_id=org_id, project_id=project_id,
            progress_callback=on_file_progress,
        )
        result = indexer.index_repository(repo_path, repo_name)

        _update_progress(cache, org_id, self.request.id, {
            "status": "building_graph",
            "repo_url": repo_url,
            "project_id": project_id,
        })

        total_files = sum(m.files_indexed for m in result.module_results)
        total_symbols = sum(m.symbols_indexed for m in result.module_results)

        summary = {
            "status": "completed",
            "repo_url": repo_url,
            "files_indexed": total_files,
            "symbols_indexed": total_symbols,
            "modules_detected": result.modules_detected,
            "cross_module_edges": result.cross_module_edges,
        }

        # Cache the result
        _update_progress(cache, org_id, self.request.id, summary)

        logger.info("Full index complete for %s: %s", repo_name, summary)
        return summary

    except Exception as exc:
        logger.error("Full index failed for %s: %s", repo_name, exc)
        retry_count = self.request.retries
        if retry_count >= self.max_retries:
            _update_progress(cache, org_id, self.request.id, {
                "status": "failed",
                "repo_url": repo_url,
                "project_id": project_id,
                "message": str(exc),
                "retry_count": retry_count,
                "max_retries": self.max_retries,
            })
            raise
        else:
            _update_progress(cache, org_id, self.request.id, {
                "status": "retrying",
                "repo_url": repo_url,
                "project_id": project_id,
                "message": str(exc),
                "retry_count": retry_count + 1,
                "max_retries": self.max_retries,
            })
            raise self.retry(exc=exc, countdown=60 * (2 ** retry_count))
    finally:
        postgres.close()
        if qdrant is not None:
            qdrant.close()
        if cache is not None:
            cache.close()


@celery_app.task(name="index_repository_incremental", bind=True, max_retries=3)
def index_repository_incremental(
    self,
    repo_clone_url: str,
    repo_full_name: str,
    before_sha: str,
    after_sha: str,
):
    """Incremental indexing task triggered by webhooks."""
    from indexing.incremental_service import run_incremental_from_webhook

    logger.info(
        "Starting incremental index task for %s (%s..%s, task_id=%s)",
        repo_full_name, before_sha[:8], after_sha[:8], self.request.id,
    )

    try:
        result = run_incremental_from_webhook(
            repo_clone_url=repo_clone_url,
            repo_full_name=repo_full_name,
            before_sha=before_sha,
            after_sha=after_sha,
        )

        summary = {
            "status": "completed",
            "files_processed": result.files_processed,
            "symbols_added": result.symbols_added,
            "symbols_deleted": result.symbols_deleted,
            "errors": result.errors,
        }

        logger.info("Incremental index complete for %s: %s", repo_full_name, summary)
        return summary

    except Exception as exc:
        logger.error("Incremental index failed for %s: %s", repo_full_name, exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="sync_jira_tickets", bind=True, max_retries=3)
def sync_jira_tickets(self, project_id: str):
    """Sync Jira tickets for a project into Qdrant."""
    from config.settings import Settings
    from indexing.jira_indexer import JiraIndexer
    from integrations.client_factory import build_jira_client
    from storage.postgres import PostgresClient
    from storage.qdrant_client import get_qdrant_for_project
    from storage.redis_cache import RedisCache, scoped_key

    settings = Settings()

    postgres = PostgresClient(settings.postgres_url)
    cache = None
    project = None

    try:
        postgres.connect()

        # Get project details
        project = postgres.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        org_id = str(project["org_id"])

        try:
            cache = RedisCache(settings.redis_url)
            cache.connect()
        except Exception:
            logger.warning("Redis unavailable for cache")

        # Build clients
        jira_client = build_jira_client(project, settings.credential_encryption_key)
        qdrant = get_qdrant_for_project(project, settings.qdrant_url, settings.embedding_dim, "jira")
        qdrant.connect()

        try:
            indexer = JiraIndexer(jira_client, postgres, qdrant, org_id, project_id)

            # Extract project key from project slug
            project_key = project.get("slug", "").upper()
            result = indexer.sync_tickets(project_key)

            summary = {
                "status": "completed",
                "tickets_synced": result.tickets_synced,
                "embeddings_created": result.embeddings_created,
                "errors": result.errors,
            }

            if cache is not None:
                cache.set(scoped_key(org_id, "jira_sync", self.request.id), summary, ttl=86400)

            logger.info("Jira sync complete for project %s: %s", project_id, summary)
            return summary

        finally:
            qdrant.close()

    except Exception as exc:
        logger.error("Jira sync failed for project %s: %s", project_id, exc)
        if cache is not None and project is not None:
            cache.set(scoped_key(str(project.get("org_id", "")), "jira_sync", self.request.id), {
                "status": "failed",
                "message": str(exc),
            })
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        postgres.close()
        if cache is not None:
            cache.close()
