"""Analyze commit history for indexing."""

import logging
import os
from dataclasses import dataclass, field

from git_analysis.change_detector import ChangeSet, ChangeType
from indexing.embedding_pipeline import generate_embeddings
from indexing.file_filter import detect_language, should_index_file
from indexing.graph_builder import build_graph
from indexing.symbol_extractor import extract_symbols
from storage.postgres import PostgresClient
from storage.qdrant_client import QdrantVectorStore
from storage.redis_cache import RedisCache

logger = logging.getLogger(__name__)


@dataclass
class IncrementalIndexResult:
    files_processed: int = 0
    symbols_added: int = 0
    symbols_updated: int = 0
    symbols_deleted: int = 0
    embeddings_updated: int = 0
    edges_updated: int = 0
    errors: list[str] = field(default_factory=list)


class CommitAnalyzer:
    """Incrementally index repository changes derived from a git changeset."""

    def __init__(
        self,
        postgres: PostgresClient,
        qdrant: QdrantVectorStore,
        cache: RedisCache | None = None,
    ) -> None:
        self._postgres = postgres
        self._qdrant = qdrant
        self._cache = cache

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_changes(
        self,
        change_set: ChangeSet,
        repo_path: str,
        repo_name: str,
    ) -> IncrementalIndexResult:
        """Process all file changes in *change_set* and update the index.

        Args:
            change_set: Detected changes between two commits.
            repo_path: Absolute path to the checked-out repository.
            repo_name: Logical repository identifier (used as the ``repo`` key).

        Returns:
            Summary of what was indexed / deleted.
        """
        result = IncrementalIndexResult()

        for file_change in change_set.changes:
            file_path = file_change.file_path
            change_type = file_change.change_type

            if not should_index_file(file_path):
                logger.debug("Skipping non-indexable file: %s", file_path)
                continue

            try:
                if change_type == ChangeType.ADDED:
                    symbols_added, edges_added = self._handle_added_file(
                        file_path, repo_path, repo_name
                    )
                    result.symbols_added += symbols_added
                    result.edges_updated += edges_added

                elif change_type == ChangeType.MODIFIED:
                    symbols_deleted, symbols_added, edges_added = self._handle_modified_file(
                        file_path, repo_path, repo_name
                    )
                    result.symbols_deleted += symbols_deleted
                    result.symbols_added += symbols_added
                    result.edges_updated += edges_added

                elif change_type == ChangeType.DELETED:
                    symbols_deleted = self._handle_deleted_file(file_path, repo_name)
                    result.symbols_deleted += symbols_deleted

                result.files_processed += 1

            except Exception as exc:
                error_msg = f"Error processing {file_path}: {exc}"
                logger.error(error_msg, exc_info=True)
                result.errors.append(error_msg)

        self._invalidate_cache(repo_name)
        return result

    # ------------------------------------------------------------------
    # File-level handlers
    # ------------------------------------------------------------------

    def _handle_added_file(
        self, file_path: str, repo_path: str, repo_name: str
    ) -> tuple[int, int]:
        """Index a newly added file.

        Returns:
            (symbols_added, edges_added)
        """
        source_code = self._read_source(file_path, repo_path)
        language = detect_language(file_path) or "unknown"

        extraction = extract_symbols(file_path, source_code, repo_name, language)
        if not extraction.symbols:
            return 0, 0

        symbol_dicts = [_symbol_to_dict(s) for s in extraction.symbols]

        embeddings = generate_embeddings(symbol_dicts)
        payloads = [_symbol_to_payload(s, repo_name) for s in extraction.symbols]

        self._postgres.upsert_symbols_batch(extraction.symbols)
        self._qdrant.upsert_embeddings(embeddings, payloads)

        graph = build_graph(symbol_dicts, extraction.edges)
        self._postgres.insert_edges(graph.edges)

        return len(extraction.symbols), len(graph.edges)

    def _handle_modified_file(
        self, file_path: str, repo_path: str, repo_name: str
    ) -> tuple[int, int, int]:
        """Re-index a modified file by deleting old data then adding fresh data.

        Returns:
            (symbols_deleted, symbols_added, edges_added)
        """
        symbols_deleted = self._delete_file_index(file_path, repo_name)
        symbols_added, edges_added = self._handle_added_file(file_path, repo_path, repo_name)
        return symbols_deleted, symbols_added, edges_added

    def _handle_deleted_file(self, file_path: str, repo_name: str) -> int:
        """Remove all index data for a deleted file.

        Returns:
            Number of symbols deleted.
        """
        return self._delete_file_index(file_path, repo_name)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _invalidate_cache(self, repo_name: str) -> None:
        """Clear all cached entries for *repo_name* if a cache is configured."""
        if self._cache is not None:
            self._cache.clear_repo_cache(repo_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_source(self, file_path: str, repo_path: str) -> str:
        """Read source code from disk."""
        abs_path = os.path.join(repo_path, file_path)
        with open(abs_path, encoding="utf-8") as fh:
            return fh.read()

    def _delete_file_index(self, file_path: str, repo_name: str) -> int:
        """Delete symbols and edges for a file; return the count deleted."""
        symbol_ids = self._postgres.delete_symbols_by_file(file_path, repo_name)
        if symbol_ids:
            self._qdrant.delete_by_symbol_ids(symbol_ids)
            self._postgres.delete_edges_by_symbols(symbol_ids)
        return len(symbol_ids)


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------

def _symbol_to_dict(symbol) -> dict:
    """Convert a Symbol to the dict format expected by generate_embeddings / build_graph."""
    d = {
        "symbol_id": symbol.symbol_id,
        "name": symbol.name,
        "type": symbol.type,
        "source": symbol.source,
        "file_path": symbol.file_path,
    }
    module = getattr(symbol, "module", None)
    if module:
        d["module"] = module
    return d


def _symbol_to_payload(symbol, repo_name: str, module: str = "") -> dict:
    """Build the Qdrant payload dict for a symbol."""
    payload = {
        "name": symbol.name,
        "type": symbol.type,
        "file_path": symbol.file_path,
        "repo": repo_name,
        "start_line": symbol.start_line,
        "end_line": symbol.end_line,
    }
    effective_module = module or getattr(symbol, "module", "")
    if effective_module:
        payload["module"] = effective_module
    return payload
