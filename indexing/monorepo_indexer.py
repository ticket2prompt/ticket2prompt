"""Index a monorepo by detecting modules and indexing each independently."""

import logging
import os
from dataclasses import dataclass, field
from typing import Callable

from indexing.embedding_pipeline import generate_embeddings
from indexing.file_filter import detect_language, filter_files
from indexing.graph_builder import build_graph
from indexing.module_detector import (
    DetectedModule,
    classify_file_to_module,
    detect_cross_module_dependencies,
    detect_modules,
)
from indexing.symbol_extractor import extract_symbols
from storage.postgres import PostgresClient
from storage.qdrant_client import QdrantVectorStore
from storage.redis_cache import RedisCache

logger = logging.getLogger(__name__)


@dataclass
class ModuleIndexResult:
    """Index result for a single module."""
    module_name: str
    files_indexed: int
    symbols_indexed: int
    edges_created: int
    errors: list[str] = field(default_factory=list)


@dataclass
class MonorepoIndexResult:
    """Aggregated index result for the entire repository."""
    modules_detected: int
    module_results: list[ModuleIndexResult] = field(default_factory=list)
    cross_module_edges: int = 0
    total_errors: list[str] = field(default_factory=list)


class MonorepoIndexer:
    """Index a monorepo by detecting modules and indexing each independently."""

    def __init__(
        self,
        postgres: PostgresClient,
        qdrant: QdrantVectorStore,
        cache: RedisCache | None = None,
        org_id: str = "",
        project_id: str = "",
        progress_callback: Callable[[dict], None] | None = None,
    ) -> None:
        self._postgres = postgres
        self._qdrant = qdrant
        self._cache = cache
        self._org_id = org_id
        self._project_id = project_id
        self._progress_callback = progress_callback

    def index_repository(self, repo_path: str, repo_name: str) -> MonorepoIndexResult:
        """Detect modules, index each, then build cross-module edges.

        Args:
            repo_path: Absolute path to the cloned repository on disk.
            repo_name: Logical name for the repository (e.g. "org/repo").

        Returns:
            MonorepoIndexResult with per-module and aggregate statistics.
        """
        logger.info("Detecting modules in %s", repo_path)
        modules = detect_modules(repo_path)
        logger.info("Detected %d module(s)", len(modules))

        result = MonorepoIndexResult(modules_detected=len(modules))

        for module in modules:
            module_result = self.index_module(repo_path, repo_name, module)
            result.module_results.append(module_result)
            result.total_errors.extend(module_result.errors)

        cross_count = self.detect_and_store_cross_module_deps(repo_name, modules)
        result.cross_module_edges = cross_count

        return result

    def index_module(
        self,
        repo_path: str,
        repo_name: str,
        module: DetectedModule,
    ) -> ModuleIndexResult:
        """Index a single module within the repository.

        Walks all indexable files within the module's subtree, extracts
        symbols, generates embeddings (with module metadata in the payload),
        stores everything in Postgres and Qdrant, and builds the code graph.

        Args:
            repo_path:  Absolute path to the repository root.
            repo_name:  Logical repository name.
            module:     The module to index.

        Returns:
            ModuleIndexResult with file, symbol, and edge counts.
        """
        module_root = os.path.join(repo_path, module.path) if module.path else repo_path
        logger.info("Indexing module '%s' at %s", module.name or "<root>", module_root)

        all_files = filter_files(module_root)
        files_indexed = 0
        all_symbols: list[dict] = []
        all_raw_edges: list[tuple[str, str, str]] = []
        errors: list[str] = []

        for rel_file in all_files:
            # rel_file is relative to module_root; make it relative to repo root
            if module.path:
                repo_rel_file = os.path.join(module.path, rel_file)
            else:
                repo_rel_file = rel_file

            abs_file = os.path.join(module_root, rel_file)
            language = detect_language(rel_file)
            if language is None:
                continue

            try:
                with open(abs_file, encoding="utf-8", errors="replace") as fh:
                    source_code = fh.read()

                extraction = extract_symbols(repo_rel_file, source_code, repo_name, language)

                sym_dicts = [
                    {
                        "symbol_id": sym.symbol_id,
                        "name": sym.name,
                        "type": sym.type,
                        "file_path": sym.file_path,
                        "repo": sym.repo,
                        "start_line": sym.start_line,
                        "end_line": sym.end_line,
                        "language": sym.language,
                        "source": sym.source,
                        "module": module.name,
                    }
                    for sym in extraction.symbols
                ]
                all_symbols.extend(sym_dicts)
                all_raw_edges.extend(extraction.edges)
                files_indexed += 1

            except Exception as exc:
                msg = f"{repo_rel_file}: {exc}"
                logger.error("Error indexing file %s: %s", repo_rel_file, exc)
                errors.append(msg)

            if self._progress_callback:
                self._progress_callback({
                    "files_parsed": files_indexed + len(errors),
                    "files_total": len(all_files),
                    "current_file": repo_rel_file,
                })

        if all_symbols:
            # Store symbols in Postgres
            self._postgres.upsert_symbols_batch(all_symbols, self._org_id, self._project_id)

            # Generate embeddings and store in Qdrant
            embeddings = generate_embeddings(all_symbols)
            payloads = [
                {
                    "name": sym["name"],
                    "type": sym["type"],
                    "file_path": sym["file_path"],
                    "repo": sym["repo"],
                    "start_line": sym["start_line"],
                    "end_line": sym["end_line"],
                    "module": sym["module"],
                    "org_id": self._org_id,
                    "project_id": self._project_id,
                }
                for sym in all_symbols
            ]
            self._qdrant.upsert_embeddings(embeddings, payloads)

        # Build and persist code graph
        graph = build_graph(all_symbols, all_raw_edges)
        if graph.edges:
            self._postgres.insert_edges(graph.edges, self._org_id, self._project_id)

        return ModuleIndexResult(
            module_name=module.name,
            files_indexed=files_indexed,
            symbols_indexed=len(all_symbols),
            edges_created=len(graph.edges),
            errors=errors,
        )

    def detect_and_store_cross_module_deps(
        self,
        repo_name: str,
        modules: list[DetectedModule],
    ) -> int:
        """Find and record cross-module dependencies already stored in Postgres.

        Queries all symbols for the repo, fetches all edges that reference
        those symbols, classifies each symbol to its module, then records
        any edges that cross module boundaries.

        Args:
            repo_name: Logical repository name used to query Postgres.
            modules:   List of detected modules for classification.

        Returns:
            Number of cross-module edges found.
        """
        symbols = self._postgres.get_symbols_by_repo(repo_name, self._org_id, self._project_id)
        if not symbols:
            return 0

        # Build a symbol_id -> module mapping using classify_file_to_module
        symbol_dicts: list[dict] = []
        for sym in symbols:
            module_name = classify_file_to_module(sym["file_path"], modules)
            symbol_dicts.append({
                "symbol_id": sym["symbol_id"],
                "module": module_name,
            })

        # Gather all edges for these symbols
        symbol_ids = {s["symbol_id"] for s in symbol_dicts}
        raw_edges: list[tuple[str, str, str]] = []
        for sym_id in symbol_ids:
            edges = self._postgres.get_edges_from(sym_id, self._org_id, self._project_id)
            for edge in edges:
                raw_edges.append((
                    edge["from_symbol"],
                    edge["to_symbol"],
                    edge["relation_type"],
                ))

        cross = detect_cross_module_dependencies(symbol_dicts, raw_edges)

        logger.info(
            "Found %d cross-module edge(s) for repo '%s'", len(cross), repo_name
        )
        return len(cross)
