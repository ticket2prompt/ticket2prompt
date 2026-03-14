"""Tests for git_analysis.commit_analyzer module."""

import os
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch, call

import pytest

from git_analysis.change_detector import ChangeSet, FileChange, ChangeType
from git_analysis.commit_analyzer import CommitAnalyzer, IncrementalIndexResult


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_change_set(changes: list[FileChange]) -> ChangeSet:
    return ChangeSet(changes=changes, from_commit="abc", to_commit="def")


def _file_change(path: str, change_type: ChangeType) -> FileChange:
    return FileChange(file_path=path, change_type=change_type)


def _make_mocks():
    """Return (postgres, qdrant, cache) mocks with sensible defaults."""
    postgres = MagicMock()
    qdrant = MagicMock()
    cache = MagicMock()
    # delete_symbols_by_file returns a list of symbol_ids by default
    postgres.delete_symbols_by_file.return_value = ["sym1", "sym2"]
    return postgres, qdrant, cache


def _make_symbol(symbol_id="sym_abc", name="my_func", type="function",
                 file_path="src/foo.py", repo="repo", start_line=1, end_line=5):
    """Return a mock Symbol-like object."""
    sym = MagicMock()
    sym.symbol_id = symbol_id
    sym.name = name
    sym.type = type
    sym.file_path = file_path
    sym.repo = repo
    sym.start_line = start_line
    sym.end_line = end_line
    sym.source = "def my_func(): pass"
    return sym


def _make_extraction_result(symbols=None, edges=None):
    result = MagicMock()
    result.symbols = symbols if symbols is not None else [_make_symbol()]
    result.edges = edges if edges is not None else [("sym_abc", "sym_xyz", "calls")]
    return result


def _make_embedding_result(symbol_id="sym_abc"):
    emb = MagicMock()
    emb.symbol_id = symbol_id
    emb.embedding = [0.1, 0.2, 0.3]
    return emb


def _make_graph_result(edges=None):
    result = MagicMock()
    result.edges = edges if edges is not None else []
    return result


# ---------------------------------------------------------------------------
# Tests: added file
# ---------------------------------------------------------------------------

class TestProcessAddedFile:
    def test_process_added_file_calls_extract_and_store(self, tmp_path):
        """Adding a .py file extracts symbols, generates embeddings, and stores them."""
        # Arrange
        py_file = tmp_path / "src" / "foo.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text("def my_func(): pass\n")

        postgres, qdrant, cache = _make_mocks()
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)

        change_set = _make_change_set([_file_change("src/foo.py", ChangeType.ADDED)])

        sym = _make_symbol()
        extraction = _make_extraction_result(symbols=[sym])
        embeddings = [_make_embedding_result(sym.symbol_id)]
        graph = _make_graph_result()

        with (
            patch("git_analysis.commit_analyzer.should_index_file", return_value=True),
            patch("git_analysis.commit_analyzer.detect_language", return_value="python"),
            patch("git_analysis.commit_analyzer.extract_symbols", return_value=extraction) as mock_extract,
            patch("git_analysis.commit_analyzer.generate_embeddings", return_value=embeddings) as mock_embed,
            patch("git_analysis.commit_analyzer.build_graph", return_value=graph) as mock_graph,
        ):
            result = analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        # extract_symbols called with correct args
        mock_extract.assert_called_once_with(
            "src/foo.py",
            "def my_func(): pass\n",
            "my-repo",
            "python",
        )

        # generate_embeddings called with symbol dicts
        mock_embed.assert_called_once()
        sym_dicts = mock_embed.call_args[0][0]
        assert len(sym_dicts) == 1
        assert sym_dicts[0]["symbol_id"] == sym.symbol_id
        assert sym_dicts[0]["name"] == sym.name
        assert sym_dicts[0]["type"] == sym.type
        assert sym_dicts[0]["source"] == sym.source
        assert sym_dicts[0]["file_path"] == sym.file_path

        # postgres upsert called
        postgres.upsert_symbols_batch.assert_called_once()

        # qdrant upsert called
        qdrant.upsert_embeddings.assert_called_once()
        qdrant_call_args = qdrant.upsert_embeddings.call_args
        payloads = qdrant_call_args[0][1]
        assert payloads[0]["name"] == sym.name
        assert payloads[0]["type"] == sym.type
        assert payloads[0]["file_path"] == sym.file_path
        assert payloads[0]["repo"] == "my-repo"
        assert payloads[0]["start_line"] == sym.start_line
        assert payloads[0]["end_line"] == sym.end_line

        # edges inserted
        postgres.insert_edges.assert_called_once_with(graph.edges)

        # result counts
        assert result.files_processed == 1
        assert result.symbols_added == 1
        assert result.errors == []


# ---------------------------------------------------------------------------
# Tests: modified file
# ---------------------------------------------------------------------------

class TestProcessModifiedFile:
    def test_process_modified_file_deletes_then_readds(self, tmp_path):
        """Modifying a file deletes old symbols+edges then indexes fresh ones."""
        py_file = tmp_path / "src" / "bar.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text("def updated_func(): pass\n")

        postgres, qdrant, cache = _make_mocks()
        deleted_ids = ["old_sym1", "old_sym2"]
        postgres.delete_symbols_by_file.return_value = deleted_ids

        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)
        change_set = _make_change_set([_file_change("src/bar.py", ChangeType.MODIFIED)])

        sym = _make_symbol(symbol_id="new_sym", name="updated_func")
        extraction = _make_extraction_result(symbols=[sym], edges=[])
        embeddings = [_make_embedding_result("new_sym")]
        graph = _make_graph_result()

        with (
            patch("git_analysis.commit_analyzer.should_index_file", return_value=True),
            patch("git_analysis.commit_analyzer.detect_language", return_value="python"),
            patch("git_analysis.commit_analyzer.extract_symbols", return_value=extraction),
            patch("git_analysis.commit_analyzer.generate_embeddings", return_value=embeddings),
            patch("git_analysis.commit_analyzer.build_graph", return_value=graph),
        ):
            result = analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        # Old symbols must be deleted first
        postgres.delete_symbols_by_file.assert_called_once_with("src/bar.py", "my-repo")
        qdrant.delete_by_symbol_ids.assert_called_once_with(deleted_ids)
        postgres.delete_edges_by_symbols.assert_called_once_with(deleted_ids)

        # Then re-added
        postgres.upsert_symbols_batch.assert_called_once()
        qdrant.upsert_embeddings.assert_called_once()

        assert result.files_processed == 1
        assert result.symbols_deleted == len(deleted_ids)
        assert result.symbols_added == 1
        assert result.errors == []

    def test_modified_file_delete_order_before_add(self, tmp_path):
        """Deletion must complete before any upsert is attempted."""
        py_file = tmp_path / "mod.py"
        py_file.write_text("x = 1\n")

        postgres, qdrant, cache = _make_mocks()
        postgres.delete_symbols_by_file.return_value = ["s1"]

        manager = MagicMock()
        manager.attach_mock(postgres, "pg")
        manager.attach_mock(qdrant, "qd")

        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)
        change_set = _make_change_set([_file_change("mod.py", ChangeType.MODIFIED)])

        sym = _make_symbol()
        extraction = _make_extraction_result(symbols=[sym])
        embeddings = [_make_embedding_result()]
        graph = _make_graph_result()

        with (
            patch("git_analysis.commit_analyzer.should_index_file", return_value=True),
            patch("git_analysis.commit_analyzer.detect_language", return_value="python"),
            patch("git_analysis.commit_analyzer.extract_symbols", return_value=extraction),
            patch("git_analysis.commit_analyzer.generate_embeddings", return_value=embeddings),
            patch("git_analysis.commit_analyzer.build_graph", return_value=graph),
        ):
            analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        call_names = [c[0] for c in manager.mock_calls]
        delete_idx = next(i for i, c in enumerate(call_names) if "delete_symbols_by_file" in c)
        upsert_idx = next(i for i, c in enumerate(call_names) if "upsert_symbols_batch" in c)
        assert delete_idx < upsert_idx, "delete must come before upsert"


# ---------------------------------------------------------------------------
# Tests: deleted file
# ---------------------------------------------------------------------------

class TestProcessDeletedFile:
    def test_process_deleted_file_removes_symbols_and_edges(self):
        """Deleting a file removes its symbols from postgres, qdrant, and edges."""
        postgres, qdrant, cache = _make_mocks()
        deleted_ids = ["d1", "d2", "d3"]
        postgres.delete_symbols_by_file.return_value = deleted_ids

        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)
        change_set = _make_change_set([_file_change("src/gone.py", ChangeType.DELETED)])

        with patch("git_analysis.commit_analyzer.should_index_file", return_value=True):
            result = analyzer.process_changes(change_set, "/any/path", "my-repo")

        postgres.delete_symbols_by_file.assert_called_once_with("src/gone.py", "my-repo")
        qdrant.delete_by_symbol_ids.assert_called_once_with(deleted_ids)
        postgres.delete_edges_by_symbols.assert_called_once_with(deleted_ids)

        # No upserts
        postgres.upsert_symbols_batch.assert_not_called()
        qdrant.upsert_embeddings.assert_not_called()

        assert result.files_processed == 1
        assert result.symbols_deleted == len(deleted_ids)
        assert result.errors == []


# ---------------------------------------------------------------------------
# Tests: mixed changeset
# ---------------------------------------------------------------------------

class TestMixedChangeset:
    def test_mixed_changeset_handles_all_types(self, tmp_path):
        """A changeset with add + modify + delete processes all three correctly."""
        (tmp_path / "added.py").write_text("def new(): pass\n")
        (tmp_path / "modified.py").write_text("def changed(): pass\n")

        postgres, qdrant, cache = _make_mocks()
        postgres.delete_symbols_by_file.return_value = ["old_sym"]

        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)
        change_set = _make_change_set([
            _file_change("added.py", ChangeType.ADDED),
            _file_change("modified.py", ChangeType.MODIFIED),
            _file_change("deleted.py", ChangeType.DELETED),
        ])

        sym = _make_symbol()
        extraction = _make_extraction_result(symbols=[sym], edges=[])
        embeddings = [_make_embedding_result()]
        graph = _make_graph_result()

        with (
            patch("git_analysis.commit_analyzer.should_index_file", return_value=True),
            patch("git_analysis.commit_analyzer.detect_language", return_value="python"),
            patch("git_analysis.commit_analyzer.extract_symbols", return_value=extraction),
            patch("git_analysis.commit_analyzer.generate_embeddings", return_value=embeddings),
            patch("git_analysis.commit_analyzer.build_graph", return_value=graph),
        ):
            result = analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        assert result.files_processed == 3
        # Two symbol upserts (added + modified re-add)
        assert postgres.upsert_symbols_batch.call_count == 2
        # Two qdrant upserts (added + modified re-add)
        assert qdrant.upsert_embeddings.call_count == 2
        # delete called for modified + deleted (2 files)
        assert postgres.delete_symbols_by_file.call_count == 2
        assert result.errors == []


# ---------------------------------------------------------------------------
# Tests: non-indexable files skipped
# ---------------------------------------------------------------------------

class TestNonIndexableFilesSkipped:
    def test_pyc_file_is_skipped(self):
        """.pyc files must not be indexed."""
        postgres, qdrant, cache = _make_mocks()
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)

        change_set = _make_change_set([_file_change("src/__pycache__/foo.cpython-312.pyc", ChangeType.ADDED)])

        # should_index_file returns False for .pyc files; we rely on the real impl
        result = analyzer.process_changes(change_set, "/repo", "my-repo")

        postgres.upsert_symbols_batch.assert_not_called()
        qdrant.upsert_embeddings.assert_not_called()
        assert result.files_processed == 0
        assert result.symbols_added == 0

    def test_non_code_file_is_skipped(self):
        """Files that should_index_file rejects are silently skipped."""
        postgres, qdrant, cache = _make_mocks()
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)

        change_set = _make_change_set([_file_change("README.md", ChangeType.ADDED)])

        with patch("git_analysis.commit_analyzer.should_index_file", return_value=False):
            result = analyzer.process_changes(change_set, "/repo", "my-repo")

        postgres.upsert_symbols_batch.assert_not_called()
        assert result.files_processed == 0


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_error_in_one_file_continues_others(self, tmp_path):
        """An exception while processing file A does not prevent file B from being processed."""
        (tmp_path / "good.py").write_text("def ok(): pass\n")
        # bad.py will cause extract_symbols to raise

        postgres, qdrant, cache = _make_mocks()
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)

        change_set = _make_change_set([
            _file_change("bad.py", ChangeType.ADDED),
            _file_change("good.py", ChangeType.ADDED),
        ])

        # bad.py doesn't exist on disk – reading it will fail, or we can mock extract_symbols
        # We'll mock should_index_file to True for both and use side_effect on extract_symbols
        sym = _make_symbol()
        extraction_good = _make_extraction_result(symbols=[sym], edges=[])
        embeddings_good = [_make_embedding_result()]
        graph_good = _make_graph_result()

        def extract_side_effect(file_path, source_code, repo, language):
            if "bad" in file_path:
                raise RuntimeError("Parsing failed")
            return extraction_good

        with (
            patch("git_analysis.commit_analyzer.should_index_file", return_value=True),
            patch("git_analysis.commit_analyzer.detect_language", return_value="python"),
            patch("git_analysis.commit_analyzer.extract_symbols", side_effect=extract_side_effect),
            patch("git_analysis.commit_analyzer.generate_embeddings", return_value=embeddings_good),
            patch("git_analysis.commit_analyzer.build_graph", return_value=graph_good),
        ):
            result = analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        # good.py was still processed
        postgres.upsert_symbols_batch.assert_called_once()

        # error was captured
        assert len(result.errors) == 1
        assert "bad.py" in result.errors[0]

    def test_error_message_contains_file_path(self, tmp_path):
        """Error entries must include the file path for traceability."""
        (tmp_path / "broken.py").write_text("x = 1\n")
        postgres, qdrant, cache = _make_mocks()
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)
        change_set = _make_change_set([_file_change("broken.py", ChangeType.ADDED)])

        with (
            patch("git_analysis.commit_analyzer.should_index_file", return_value=True),
            patch("git_analysis.commit_analyzer.detect_language", return_value="python"),
            patch("git_analysis.commit_analyzer.extract_symbols", side_effect=ValueError("bad parse")),
        ):
            result = analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        assert len(result.errors) == 1
        assert "broken.py" in result.errors[0]


# ---------------------------------------------------------------------------
# Tests: cache invalidation
# ---------------------------------------------------------------------------

class TestCacheInvalidation:
    def test_cache_invalidation_called_after_process(self, tmp_path):
        """clear_repo_cache is called once at the end of process_changes."""
        postgres, qdrant, cache = _make_mocks()
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)
        change_set = _make_change_set([])  # empty – no files to process

        analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        cache.clear_repo_cache.assert_called_once_with("my-repo")

    def test_cache_invalidated_with_correct_repo(self, tmp_path):
        """Cache is invalidated using the repo_name passed to process_changes."""
        postgres, qdrant, cache = _make_mocks()
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=cache)
        change_set = _make_change_set([])

        analyzer.process_changes(change_set, str(tmp_path), "different-repo")

        cache.clear_repo_cache.assert_called_once_with("different-repo")

    def test_no_cache_does_not_raise(self, tmp_path):
        """CommitAnalyzer works fine when cache=None."""
        postgres, qdrant, _ = _make_mocks()
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=None)
        change_set = _make_change_set([])

        result = analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        assert isinstance(result, IncrementalIndexResult)
        assert result.errors == []

    def test_no_cache_no_clear_called(self, tmp_path):
        """When cache is None, no attribute access on None occurs (no AttributeError)."""
        postgres, qdrant, _ = _make_mocks()
        # If _invalidate_cache incorrectly calls None.clear_repo_cache, we'd get AttributeError
        analyzer = CommitAnalyzer(postgres=postgres, qdrant=qdrant, cache=None)
        change_set = _make_change_set([_file_change("src/x.py", ChangeType.DELETED)])

        postgres.delete_symbols_by_file.return_value = []

        with patch("git_analysis.commit_analyzer.should_index_file", return_value=True):
            result = analyzer.process_changes(change_set, str(tmp_path), "my-repo")

        assert result.errors == []
