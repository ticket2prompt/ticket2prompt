"""CLI script to index a repository end-to-end."""

import argparse
import logging
import os
import sys
from dataclasses import asdict

from config.settings import Settings
from git_analysis.change_detector import detect_changes
from git_analysis.commit_analyzer import CommitAnalyzer
from indexing.file_filter import filter_files
from indexing.repo_cloner import clone_repo
from storage.postgres import PostgresClient
from storage.qdrant_client import QdrantVectorStore
from storage.redis_cache import RedisCache

logger = logging.getLogger(__name__)


def parse_args(args=None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Index a git repository into the ticket-to-prompt knowledge base."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Repository URL to clone and index.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Branch to checkout after cloning.",
    )
    parser.add_argument(
        "--target-dir",
        default=None,
        dest="target_dir",
        help="Directory to clone into (default: <clone_base_dir>/<repo_name>).",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=False,
        help="Perform incremental indexing instead of a full re-index.",
    )
    parser.add_argument(
        "--from-commit",
        default=None,
        dest="from_commit",
        help="Base commit SHA for incremental mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="Show what would be indexed without writing to storage.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args(args)


def setup_logging(log_level: str) -> None:
    """Configure root logger level and a simple stream handler."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger().setLevel(numeric_level)


def extract_repo_name(repo_url: str) -> str:
    """Extract repo name from URL.

    Examples:
        https://github.com/org/repo.git  -> org/repo
        https://github.com/org/repo      -> org/repo
        git@github.com:org/repo.git      -> org/repo
    """
    # Normalise SSH-style URLs (git@host:org/repo.git) to path form
    url = repo_url
    if ":" in url and not url.startswith("http"):
        # git@github.com:org/repo.git  ->  org/repo.git
        url = url.split(":", 1)[1]

    # Strip trailing .git
    if url.endswith(".git"):
        url = url[:-4]

    # Take the last two path segments as org/repo
    parts = url.replace("\\", "/").split("/")
    parts = [p for p in parts if p]  # drop empty segments
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return parts[-1] if parts else url


def run_full_index(
    repo_path: str,
    repo_name: str,
    postgres,
    qdrant,
    settings,
    dry_run: bool = False,
) -> dict:
    """Run full indexing: extract symbols, generate embeddings, build graph, store everything.

    Args:
        repo_path: Local path to the cloned repository.
        repo_name: Canonical repo identifier (e.g. 'org/repo').
        postgres: Connected PostgresClient.
        qdrant: Connected QdrantVectorStore.
        settings: Settings instance.
        dry_run: When True, skip all storage writes.

    Returns:
        Summary dict with keys: files_processed, symbols_extracted, embeddings_generated.
    """
    if dry_run:
        logger.info("[dry-run] Would index %s at %s", repo_name, repo_path)
        files = filter_files(repo_path)
        return {"files_processed": len(files), "symbols_extracted": 0, "embeddings_generated": 0}

    # Clean previous data
    logger.info("Cleaning previous data for %s", repo_name)
    postgres.delete_edges_by_repo(repo_name)
    postgres.delete_symbols_by_repo(repo_name)
    qdrant.delete_by_repo(repo_name)

    # Use MonorepoIndexer for actual indexing
    from indexing.monorepo_indexer import MonorepoIndexer

    cache = RedisCache(settings.redis_url)
    try:
        cache.connect()
    except Exception:
        cache = None

    try:
        indexer = MonorepoIndexer(postgres, qdrant, cache)
        result = indexer.index_repository(repo_path, repo_name)

        total_symbols = sum(m.symbols_indexed for m in result.module_results)
        total_files = sum(m.files_indexed for m in result.module_results)

        return {
            "files_processed": total_files,
            "symbols_extracted": total_symbols,
            "embeddings_generated": total_symbols,  # 1:1 with symbols
            "modules_detected": result.modules_detected,
            "cross_module_edges": result.cross_module_edges,
        }
    finally:
        if cache is not None:
            cache.close()


def run_incremental_index(
    repo_path: str,
    repo_name: str,
    from_commit: str,
    to_commit: str,
    postgres,
    qdrant,
    cache,
) -> dict:
    """Run incremental indexing using CommitAnalyzer.

    Args:
        repo_path: Local path to the cloned repository.
        repo_name: Canonical repo identifier.
        from_commit: Base commit SHA.
        to_commit: Target commit SHA (usually HEAD).
        postgres: Connected PostgresClient.
        qdrant: Connected QdrantVectorStore.
        cache: Connected RedisCache.

    Returns:
        Summary dict from CommitAnalyzer.process_changes.
    """
    logger.info(
        "Detecting changes between %s and %s in %s",
        from_commit,
        to_commit,
        repo_path,
    )
    change_set = detect_changes(repo_path, from_commit, to_commit)
    logger.info(
        "Change set: %d added, %d modified, %d deleted",
        len(change_set.added),
        len(change_set.modified),
        len(change_set.deleted),
    )

    analyzer = CommitAnalyzer(postgres, qdrant, cache)
    result = analyzer.process_changes(change_set, repo_path, repo_name)
    if isinstance(result, dict):
        return result
    # CommitAnalyzer returns IncrementalIndexResult dataclass — convert to dict
    try:
        return asdict(result)
    except TypeError:
        return {}


def main(args=None) -> None:
    """Main entry point.

    Parses arguments, initialises clients, clones the repo, and delegates to
    either run_full_index or run_incremental_index.
    """
    ns = parse_args(args)
    setup_logging(ns.log_level)

    settings = Settings()
    repo_name = extract_repo_name(ns.repo)
    repo_path = ns.target_dir or os.path.join(settings.clone_base_dir, repo_name)

    logger.info("Indexing repository: %s", ns.repo)
    logger.info("Repo name: %s", repo_name)
    logger.info("Target path: %s", repo_path)

    # Initialise storage clients
    postgres = PostgresClient(settings.postgres_url)
    qdrant = QdrantVectorStore(
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection_name,
        vector_size=settings.embedding_dim,
    )

    postgres.connect()
    qdrant.connect()
    qdrant.ensure_collection()

    cache = None
    if ns.incremental:
        cache = RedisCache(settings.redis_url)
        cache.connect()

    try:
        # Clone (or reuse) the repository
        repo = clone_repo(ns.repo, repo_path)

        # Optional branch checkout
        if ns.branch:
            logger.info("Checking out branch: %s", ns.branch)
            repo.git.checkout(ns.branch)

        if ns.incremental:
            to_commit = repo.head.commit.hexsha
            from_commit = ns.from_commit or _resolve_previous_commit(repo)
            summary = run_incremental_index(
                repo_path=repo_path,
                repo_name=repo_name,
                from_commit=from_commit,
                to_commit=to_commit,
                postgres=postgres,
                qdrant=qdrant,
                cache=cache,
            )
        else:
            summary = run_full_index(
                repo_path=repo_path,
                repo_name=repo_name,
                postgres=postgres,
                qdrant=qdrant,
                settings=settings,
                dry_run=ns.dry_run,
            )

        logger.info("Indexing complete. Summary: %s", summary)
        print("Done.", summary)

    finally:
        postgres.close()
        qdrant.close()
        if cache is not None:
            cache.close()


def _resolve_previous_commit(repo) -> str:
    """Return the SHA of the commit before HEAD, or HEAD~1 as a fallback."""
    try:
        return repo.head.commit.parents[0].hexsha
    except (IndexError, AttributeError):
        return "HEAD~1"


if __name__ == "__main__":
    main()
