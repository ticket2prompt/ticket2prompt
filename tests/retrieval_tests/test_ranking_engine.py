"""Tests for the ranking engine module."""

import datetime
from unittest.mock import MagicMock

import pytest

from retrieval import FileCandidate, SymbolMatch
from retrieval.ranking_engine import (
    DEFAULT_FILE_LIMIT,
    WEIGHT_GIT_RECENCY,
    WEIGHT_GRAPH,
    WEIGHT_KEYWORD,
    WEIGHT_SEMANTIC,
    WEIGHT_SYMBOL_DENSITY,
    compute_git_recency_score,
    compute_graph_score,
    compute_keyword_score,
    compute_semantic_score,
    compute_symbol_density_score,
    group_symbols_by_file,
    rank_files,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_symbol(
    symbol_id: str,
    file_path: str,
    repo: str = "my-repo",
    score: float = 0.8,
    source: str = "vector",
) -> SymbolMatch:
    return SymbolMatch(
        symbol_id=symbol_id,
        name=symbol_id,
        type="function",
        file_path=file_path,
        repo=repo,
        start_line=1,
        end_line=10,
        score=score,
        source=source,
    )


def _make_postgres(file_path: str, repo: str, last_modified: datetime.datetime | None):
    """Return a mock postgres whose get_file_metadata returns the given last_modified."""
    postgres = MagicMock()
    postgres.get_file_metadata.return_value = (
        {
            "file_id": "f1",
            "file_path": file_path,
            "repo": repo,
            "last_modified": last_modified,
            "commit_count": 5,
        }
        if last_modified is not None
        else None
    )
    return postgres


# ---------------------------------------------------------------------------
# group_symbols_by_file
# ---------------------------------------------------------------------------

def test_group_symbols_by_file_basic():
    symbols = [
        _make_symbol("sym1", "src/a.py"),
        _make_symbol("sym2", "src/b.py"),
        _make_symbol("sym3", "src/a.py"),
    ]
    result = group_symbols_by_file(symbols)

    assert set(result.keys()) == {"src/a.py", "src/b.py"}
    assert len(result["src/a.py"]) == 2
    assert len(result["src/b.py"]) == 1
    assert {s.symbol_id for s in result["src/a.py"]} == {"sym1", "sym3"}


def test_group_symbols_by_file_empty():
    result = group_symbols_by_file([])
    assert result == {}


# ---------------------------------------------------------------------------
# compute_semantic_score
# ---------------------------------------------------------------------------

def test_compute_semantic_score_takes_max():
    symbols = [
        _make_symbol("a", "f.py", score=0.5, source="vector"),
        _make_symbol("b", "f.py", score=0.9, source="vector"),
        _make_symbol("c", "f.py", score=0.7, source="vector"),
    ]
    assert compute_semantic_score(symbols) == pytest.approx(0.9)


def test_compute_semantic_score_no_vector_matches():
    symbols = [
        _make_symbol("a", "f.py", score=0.9, source="keyword"),
        _make_symbol("b", "f.py", score=0.8, source="graph"),
    ]
    assert compute_semantic_score(symbols) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_graph_score
# ---------------------------------------------------------------------------

def test_compute_graph_score_takes_max():
    symbols = [
        _make_symbol("a", "f.py", score=0.4, source="graph"),
        _make_symbol("b", "f.py", score=0.85, source="graph"),
        _make_symbol("c", "f.py", score=0.6, source="keyword"),
    ]
    assert compute_graph_score(symbols) == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# compute_keyword_score
# ---------------------------------------------------------------------------

def test_compute_keyword_score_from_matches():
    symbols = [
        _make_symbol("a", "f.py", score=0.3, source="keyword"),
        _make_symbol("b", "f.py", score=0.75, source="keyword"),
        _make_symbol("c", "f.py", score=0.5, source="vector"),
    ]
    assert compute_keyword_score(symbols) == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# compute_git_recency_score
# ---------------------------------------------------------------------------

def test_compute_git_recency_score_recent():
    last_modified = datetime.datetime.now() - datetime.timedelta(days=3)
    postgres = _make_postgres("src/a.py", "repo", last_modified)
    score = compute_git_recency_score("src/a.py", "repo", postgres)
    assert score == pytest.approx(1.0)


def test_compute_git_recency_score_month_old():
    last_modified = datetime.datetime.now() - datetime.timedelta(days=15)
    postgres = _make_postgres("src/a.py", "repo", last_modified)
    score = compute_git_recency_score("src/a.py", "repo", postgres)
    assert score == pytest.approx(0.7)


def test_compute_git_recency_score_old():
    last_modified = datetime.datetime.now() - datetime.timedelta(days=60)
    postgres = _make_postgres("src/a.py", "repo", last_modified)
    score = compute_git_recency_score("src/a.py", "repo", postgres)
    assert score == pytest.approx(0.3)


def test_compute_git_recency_score_no_metadata():
    postgres = MagicMock()
    postgres.get_file_metadata.return_value = None
    score = compute_git_recency_score("src/missing.py", "repo", postgres)
    assert score == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# compute_symbol_density_score
# ---------------------------------------------------------------------------

def test_compute_symbol_density_score_values():
    assert compute_symbol_density_score(0) == pytest.approx(0.0)
    assert compute_symbol_density_score(1) == pytest.approx(0.3)
    assert compute_symbol_density_score(2) == pytest.approx(0.6)
    assert compute_symbol_density_score(3) == pytest.approx(1.0)
    assert compute_symbol_density_score(5) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# rank_files
# ---------------------------------------------------------------------------

def test_rank_files_correct_formula():
    """
    One file with known scores; verify the weighted sum is applied correctly.

    Manually chosen symbol scores:
      semantic  = 0.8  (vector symbol)
      graph     = 0.6  (graph symbol)
      keyword   = 0.4  (keyword symbol)
      density   = 1.0  (3 symbols → 1.0)

    Git recency: mock last_modified 3 days ago → 1.0

    Expected final_score:
      0.55*0.8 + 0.20*0.6 + 0.15*0.4 + 0.05*1.0 + 0.05*1.0
      = 0.44 + 0.12 + 0.06 + 0.05 + 0.05
      = 0.72
    """
    file_path = "src/service.py"
    repo = "my-repo"

    vector_matches = [_make_symbol("v1", file_path, repo=repo, score=0.8, source="vector")]
    graph_matches = [_make_symbol("g1", file_path, repo=repo, score=0.6, source="graph")]
    keyword_matches = [_make_symbol("k1", file_path, repo=repo, score=0.4, source="keyword")]

    last_modified = datetime.datetime.now() - datetime.timedelta(days=3)
    postgres = _make_postgres(file_path, repo, last_modified)

    results = rank_files(vector_matches, keyword_matches, graph_matches, postgres, repo)

    assert len(results) == 1
    fc = results[0]
    assert fc.file_path == file_path
    assert fc.semantic_score == pytest.approx(0.8)
    assert fc.graph_score == pytest.approx(0.6)
    assert fc.keyword_score == pytest.approx(0.4)
    assert fc.git_recency_score == pytest.approx(1.0)
    assert fc.symbol_density_score == pytest.approx(1.0)
    assert fc.final_score == pytest.approx(0.72)


def test_rank_files_ordering():
    """Files with higher final scores appear first."""
    repo = "my-repo"

    # file_a: high semantic score → should rank first
    vector_a = [_make_symbol("va", "src/a.py", repo=repo, score=0.95, source="vector")]
    # file_b: low semantic score → should rank second
    vector_b = [_make_symbol("vb", "src/b.py", repo=repo, score=0.2, source="vector")]

    # recent metadata for both so git scores are equal (1.0)
    last_modified = datetime.datetime.now() - datetime.timedelta(days=2)
    postgres = MagicMock()
    postgres.get_file_metadata.return_value = {
        "file_id": "x",
        "file_path": "any",
        "repo": repo,
        "last_modified": last_modified,
        "commit_count": 1,
    }

    results = rank_files(vector_a + vector_b, [], [], postgres, repo, file_limit=10)

    assert len(results) == 2
    assert results[0].file_path == "src/a.py"
    assert results[1].file_path == "src/b.py"
    assert results[0].final_score > results[1].final_score


def test_rank_files_respects_limit():
    """With 15 distinct files and limit=10, only 10 are returned."""
    repo = "my-repo"
    symbols = [
        _make_symbol(f"sym{i}", f"src/file{i}.py", repo=repo, score=0.5, source="vector")
        for i in range(15)
    ]

    postgres = MagicMock()
    postgres.get_file_metadata.return_value = None  # all → 0.3 git recency

    results = rank_files(symbols, [], [], postgres, repo, file_limit=10)

    assert len(results) == 10


def test_rank_files_tiebreaking():
    """When final_score is identical, the file with more symbols wins."""
    repo = "my-repo"
    last_modified = datetime.datetime.now() - datetime.timedelta(days=3)

    # file_a: 1 vector symbol at score 0.8
    # file_b: 2 vector symbols both at score 0.8 → same semantic score but more symbols
    vector_a = [_make_symbol("va1", "src/a.py", repo=repo, score=0.8, source="vector")]
    vector_b = [
        _make_symbol("vb1", "src/b.py", repo=repo, score=0.8, source="vector"),
        _make_symbol("vb2", "src/b.py", repo=repo, score=0.8, source="vector"),
    ]

    postgres = MagicMock()
    postgres.get_file_metadata.return_value = {
        "file_id": "x",
        "file_path": "any",
        "repo": repo,
        "last_modified": last_modified,
        "commit_count": 1,
    }

    results = rank_files(vector_a + vector_b, [], [], postgres, repo, file_limit=10)

    assert len(results) == 2
    # file_b has 2 symbols vs file_a's 1; tiebreak → file_b first
    assert results[0].file_path == "src/b.py"
    assert results[1].file_path == "src/a.py"


def test_rank_files_empty_inputs():
    """All empty inputs return an empty list."""
    postgres = MagicMock()
    postgres.get_file_metadata.return_value = None

    results = rank_files([], [], [], postgres, "my-repo")
    assert results == []


def test_rank_files_only_vector_matches():
    """No keyword or graph matches; formula still computes correctly."""
    repo = "my-repo"
    file_path = "src/only_vector.py"
    vector_matches = [_make_symbol("v1", file_path, repo=repo, score=0.7, source="vector")]

    last_modified = datetime.datetime.now() - datetime.timedelta(days=20)
    postgres = _make_postgres(file_path, repo, last_modified)

    results = rank_files(vector_matches, [], [], postgres, repo)

    assert len(results) == 1
    fc = results[0]
    assert fc.semantic_score == pytest.approx(0.7)
    assert fc.graph_score == pytest.approx(0.0)
    assert fc.keyword_score == pytest.approx(0.0)
    assert fc.git_recency_score == pytest.approx(0.7)    # 20 days → within 30 → 0.7
    assert fc.symbol_density_score == pytest.approx(0.3)  # 1 symbol → 0.3

    expected = (
        WEIGHT_SEMANTIC * 0.7
        + WEIGHT_GRAPH * 0.0
        + WEIGHT_KEYWORD * 0.0
        + WEIGHT_GIT_RECENCY * 0.7
        + WEIGHT_SYMBOL_DENSITY * 0.3
    )
    assert fc.final_score == pytest.approx(expected)
