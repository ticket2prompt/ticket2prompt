"""Tests for indexing.monorepo_indexer module."""

import os
from dataclasses import dataclass, field
from unittest.mock import MagicMock, call, patch

import pytest

from indexing.module_detector import DetectedModule
from indexing.monorepo_indexer import (
    ModuleIndexResult,
    MonorepoIndexResult,
    MonorepoIndexer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_module(name: str, path: str, language=None, manifest_file=None) -> DetectedModule:
    return DetectedModule(name=name, path=path, language=language, manifest_file=manifest_file)


def _make_mocks():
    """Return (postgres, qdrant, cache) mocks with sensible defaults."""
    postgres = MagicMock()
    qdrant = MagicMock()
    cache = MagicMock()
    postgres.get_symbols_by_repo.return_value = []
    postgres.get_edges_from.return_value = []
    return postgres, qdrant, cache


def _make_symbol_mock(symbol_id="sym_1", name="func", type="function",
                      file_path="src/foo.py", repo="repo",
                      start_line=1, end_line=5, language="python"):
    sym = MagicMock()
    sym.symbol_id = symbol_id
    sym.name = name
    sym.type = type
    sym.file_path = file_path
    sym.repo = repo
    sym.start_line = start_line
    sym.end_line = end_line
    sym.language = language
    sym.source = "def func(): pass"
    return sym


def _make_extraction_result(symbols=None, edges=None):
    result = MagicMock()
    result.symbols = symbols if symbols is not None else []
    result.edges = edges if edges is not None else []
    return result


def _make_graph_result(edges=None):
    result = MagicMock()
    result.edges = edges if edges is not None else []
    return result


def _make_embedding_result(symbol_id="sym_1"):
    emb = MagicMock()
    emb.symbol_id = symbol_id
    emb.embedding = [0.1, 0.2, 0.3]
    return emb


# ---------------------------------------------------------------------------
# TestMonorepoIndexer
# ---------------------------------------------------------------------------

class TestMonorepoIndexer:
    def test_indexes_each_module_separately(self, tmp_path):
        """A repo with 2 modules results in index_module being called twice."""
        (tmp_path / "services" / "payments").mkdir(parents=True)
        (tmp_path / "services" / "auth").mkdir(parents=True)

        module_a = _make_module("payments", os.path.join("services", "payments"))
        module_b = _make_module("auth", os.path.join("services", "auth"))

        postgres, qdrant, cache = _make_mocks()
        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)

        with (
            patch("indexing.monorepo_indexer.detect_modules", return_value=[module_a, module_b]),
            patch.object(indexer, "index_module", return_value=ModuleIndexResult(
                module_name="test", files_indexed=0, symbols_indexed=0, edges_created=0,
            )) as mock_index_module,
            patch.object(indexer, "detect_and_store_cross_module_deps", return_value=0),
        ):
            result = indexer.index_repository(str(tmp_path), "org/repo")

        assert mock_index_module.call_count == 2
        call_modules = [c.args[2] for c in mock_index_module.call_args_list]
        assert module_a in call_modules
        assert module_b in call_modules
        assert result.modules_detected == 2

    def test_module_metadata_stored_in_qdrant_payload(self, tmp_path):
        """Qdrant payloads must include the module name."""
        module = _make_module("payments", "", language="python")
        py_file = tmp_path / "handler.py"
        py_file.write_text("def handle(): pass\n")

        sym = _make_symbol_mock(symbol_id="sym_p", file_path="handler.py")
        extraction = _make_extraction_result(symbols=[sym], edges=[])
        embedding = _make_embedding_result("sym_p")
        graph = _make_graph_result(edges=[])

        postgres, qdrant, cache = _make_mocks()
        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)

        with (
            patch("indexing.monorepo_indexer.filter_files", return_value=["handler.py"]),
            patch("indexing.monorepo_indexer.detect_language", return_value="python"),
            patch("indexing.monorepo_indexer.extract_symbols", return_value=extraction),
            patch("indexing.monorepo_indexer.generate_embeddings", return_value=[embedding]),
            patch("indexing.monorepo_indexer.build_graph", return_value=graph),
        ):
            indexer.index_module(str(tmp_path), "org/repo", module)

        qdrant.upsert_embeddings.assert_called_once()
        _, payloads = qdrant.upsert_embeddings.call_args[0]
        assert len(payloads) == 1
        assert payloads[0]["module"] == "payments"

    def test_flat_repo_indexes_as_single_module(self, tmp_path):
        """When detect_modules returns a single root module, only one index_module call is made."""
        root_module = _make_module("", "")

        postgres, qdrant, cache = _make_mocks()
        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)

        with (
            patch("indexing.monorepo_indexer.detect_modules", return_value=[root_module]),
            patch.object(indexer, "index_module", return_value=ModuleIndexResult(
                module_name="", files_indexed=2, symbols_indexed=5, edges_created=1,
            )) as mock_index_module,
            patch.object(indexer, "detect_and_store_cross_module_deps", return_value=0),
        ):
            result = indexer.index_repository(str(tmp_path), "org/repo")

        assert mock_index_module.call_count == 1
        assert result.modules_detected == 1

    def test_cross_module_edges_created(self, tmp_path):
        """detect_and_store_cross_module_deps result is reflected in MonorepoIndexResult."""
        module_a = _make_module("payments", os.path.join("services", "payments"))
        module_b = _make_module("auth", os.path.join("services", "auth"))

        postgres, qdrant, cache = _make_mocks()
        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)

        with (
            patch("indexing.monorepo_indexer.detect_modules", return_value=[module_a, module_b]),
            patch.object(indexer, "index_module", return_value=ModuleIndexResult(
                module_name="test", files_indexed=1, symbols_indexed=3, edges_created=2,
            )),
            patch.object(
                indexer, "detect_and_store_cross_module_deps", return_value=4,
            ) as mock_cross,
        ):
            result = indexer.index_repository(str(tmp_path), "org/repo")

        mock_cross.assert_called_once_with("org/repo", [module_a, module_b])
        assert result.cross_module_edges == 4

    def test_index_result_aggregates_module_results(self, tmp_path):
        """MonorepoIndexResult totals reflect the sum of all module results."""
        module_a = _make_module("payments", os.path.join("services", "payments"))
        module_b = _make_module("auth", os.path.join("services", "auth"))

        result_a = ModuleIndexResult(
            module_name="payments", files_indexed=3, symbols_indexed=10, edges_created=5,
        )
        result_b = ModuleIndexResult(
            module_name="auth", files_indexed=2, symbols_indexed=7, edges_created=3,
            errors=["auth/broken.py: parse error"],
        )

        postgres, qdrant, cache = _make_mocks()
        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)

        side_effects = [result_a, result_b]
        with (
            patch("indexing.monorepo_indexer.detect_modules", return_value=[module_a, module_b]),
            patch.object(indexer, "index_module", side_effect=side_effects),
            patch.object(indexer, "detect_and_store_cross_module_deps", return_value=2),
        ):
            result = indexer.index_repository(str(tmp_path), "org/repo")

        assert result.modules_detected == 2
        assert len(result.module_results) == 2
        assert result.cross_module_edges == 2
        assert len(result.total_errors) == 1
        assert "auth/broken.py: parse error" in result.total_errors

    def test_index_module_skips_unsupported_language(self, tmp_path):
        """Files whose language cannot be detected are skipped without error."""
        module = _make_module("", "")
        (tmp_path / "README.md").write_text("# readme")

        postgres, qdrant, cache = _make_mocks()
        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)

        with (
            patch("indexing.monorepo_indexer.filter_files", return_value=["README.md"]),
            patch("indexing.monorepo_indexer.detect_language", return_value=None),
        ):
            module_result = indexer.index_module(str(tmp_path), "org/repo", module)

        assert module_result.files_indexed == 0
        assert module_result.symbols_indexed == 0
        assert module_result.errors == []
        postgres.upsert_symbols_batch.assert_not_called()
        qdrant.upsert_embeddings.assert_not_called()

    def test_index_module_error_captured_continues(self, tmp_path):
        """An error on one file is captured and processing continues."""
        module = _make_module("", "")
        good_file = tmp_path / "good.py"
        good_file.write_text("def ok(): pass\n")

        sym = _make_symbol_mock(symbol_id="sym_good", file_path="good.py")
        good_extraction = _make_extraction_result(symbols=[sym], edges=[])
        good_embedding = _make_embedding_result("sym_good")
        graph = _make_graph_result(edges=[])

        def extract_side_effect(file_path, *args, **kwargs):
            if "bad" in file_path:
                raise RuntimeError("Parse failed")
            return good_extraction

        postgres, qdrant, cache = _make_mocks()
        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)

        with (
            patch("indexing.monorepo_indexer.filter_files", return_value=["bad.py", "good.py"]),
            patch("indexing.monorepo_indexer.detect_language", return_value="python"),
            patch("indexing.monorepo_indexer.extract_symbols", side_effect=extract_side_effect),
            patch("indexing.monorepo_indexer.generate_embeddings", return_value=[good_embedding]),
            patch("indexing.monorepo_indexer.build_graph", return_value=graph),
        ):
            module_result = indexer.index_module(str(tmp_path), "org/repo", module)

        assert len(module_result.errors) == 1
        assert "bad.py" in module_result.errors[0]
        assert module_result.files_indexed == 1

    def test_detect_and_store_cross_module_deps_returns_count(self, tmp_path):
        """detect_and_store_cross_module_deps returns the count of cross-module edges."""
        modules = [
            _make_module("payments", os.path.join("services", "payments")),
            _make_module("auth", os.path.join("services", "auth")),
        ]

        postgres, qdrant, cache = _make_mocks()
        postgres.get_symbols_by_repo.return_value = [
            {"symbol_id": "sym_pay", "file_path": os.path.join("services", "payments", "handler.py")},
            {"symbol_id": "sym_auth", "file_path": os.path.join("services", "auth", "verify.py")},
        ]
        # payments symbol calls auth symbol
        postgres.get_edges_from.side_effect = lambda sym_id, org_id, project_id: (
            [{"from_symbol": "sym_pay", "to_symbol": "sym_auth", "relation_type": "calls"}]
            if sym_id == "sym_pay"
            else []
        )

        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)
        count = indexer.detect_and_store_cross_module_deps("org/repo", modules)

        assert count == 1

    def test_detect_and_store_cross_module_deps_no_symbols(self):
        """Returns 0 immediately when no symbols exist for the repo."""
        modules = [_make_module("payments", "services/payments")]

        postgres, qdrant, cache = _make_mocks()
        postgres.get_symbols_by_repo.return_value = []

        indexer = MonorepoIndexer(postgres=postgres, qdrant=qdrant, cache=cache)
        count = indexer.detect_and_store_cross_module_deps("org/repo", modules)

        assert count == 0
        postgres.get_edges_from.assert_not_called()
