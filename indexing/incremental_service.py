"""Service layer for running incremental indexing triggered by webhooks."""

import logging
import os

from config.settings import Settings
from git_analysis.change_detector import detect_changes
from git_analysis.commit_analyzer import CommitAnalyzer, IncrementalIndexResult
from indexing.repo_cloner import clone_repo
from storage.postgres import PostgresClient
from storage.qdrant_client import QdrantVectorStore
from storage.redis_cache import RedisCache

logger = logging.getLogger(__name__)


def run_incremental_from_webhook(
    repo_clone_url: str,
    repo_full_name: str,
    before_sha: str,
    after_sha: str,
    settings: Settings | None = None,
) -> IncrementalIndexResult:
    """Run incremental indexing for a webhook event.

    Clones/updates the repo, detects changes between commits,
    and runs CommitAnalyzer.process_changes().

    Args:
        repo_clone_url: Git clone URL for the repository.
        repo_full_name: Logical repo name (e.g. "org/repo").
        before_sha: The commit SHA before the push/merge.
        after_sha: The commit SHA after the push/merge.
        settings: Application settings. Uses defaults if None.

    Returns:
        IncrementalIndexResult with indexing statistics.
    """
    if settings is None:
        settings = Settings()

    repo_path = os.path.join(settings.clone_base_dir, repo_full_name)

    logger.info(
        "Starting incremental index for %s (%s..%s)",
        repo_full_name, before_sha[:8], after_sha[:8],
    )

    # Clone or update the repository
    clone_repo(repo_clone_url, repo_path)

    # Detect changes between the two commits
    change_set = detect_changes(repo_path, before_sha, after_sha)
    logger.info(
        "Detected %d file changes (%d added, %d modified, %d deleted)",
        len(change_set.changes),
        len(change_set.added),
        len(change_set.modified),
        len(change_set.deleted),
    )

    if not change_set.changes:
        logger.info("No indexable changes detected, skipping")
        return IncrementalIndexResult()

    # Initialize storage clients
    postgres = PostgresClient(settings.postgres_url)
    qdrant = QdrantVectorStore(
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection_name,
        vector_size=settings.embedding_dim,
    )
    cache = RedisCache(settings.redis_url)

    postgres.connect()
    qdrant.connect()
    qdrant.ensure_collection()

    try:
        cache.connect()
    except Exception:
        logger.warning("Redis unavailable, proceeding without cache")
        cache = None

    try:
        analyzer = CommitAnalyzer(postgres, qdrant, cache)
        result = analyzer.process_changes(change_set, repo_path, repo_full_name)

        logger.info(
            "Incremental indexing complete: %d files, +%d/-%d symbols, %d errors",
            result.files_processed,
            result.symbols_added,
            result.symbols_deleted,
            len(result.errors),
        )
        return result

    finally:
        if cache is not None:
            cache.close()
        qdrant.close()
        postgres.close()
