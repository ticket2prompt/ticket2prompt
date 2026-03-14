"""Tests for the retrieval metrics module."""

import pytest

from evaluation import EvaluationResult
from evaluation.retrieval_metrics import (
    evaluate_retrieval,
    precision,
    recall,
    top_k_accuracy,
)
from retrieval import FileCandidate, RetrievalResult, SymbolMatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_symbol(
    symbol_id: str,
    name: str = "",
    file_path: str = "src/a.py",
    repo: str = "my-repo",
    score: float = 0.8,
    source: str = "vector",
) -> SymbolMatch:
    return SymbolMatch(
        symbol_id=symbol_id,
        name=name or symbol_id,
        type="function",
        file_path=file_path,
        repo=repo,
        start_line=1,
        end_line=10,
        score=score,
        source=source,
    )


def _make_file_candidate(
    file_path: str,
    repo: str = "my-repo",
    final_score: float = 0.7,
) -> FileCandidate:
    return FileCandidate(
        file_path=file_path,
        repo=repo,
        final_score=final_score,
    )


# ---------------------------------------------------------------------------
# precision
# ---------------------------------------------------------------------------

def test_precision_perfect():
    assert precision(["a.py", "b.py"], ["a.py", "b.py"]) == pytest.approx(1.0)


def test_precision_partial():
    assert precision(["a.py", "b.py", "c.py"], ["a.py", "b.py"]) == pytest.approx(2 / 3)


def test_precision_no_overlap():
    assert precision(["a.py"], ["b.py"]) == pytest.approx(0.0)


def test_precision_empty_retrieved():
    assert precision([], ["a.py"]) == pytest.approx(0.0)


def test_precision_empty_expected():
    assert precision(["a.py"], []) == pytest.approx(0.0)


def test_precision_both_empty():
    assert precision([], []) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# recall
# ---------------------------------------------------------------------------

def test_recall_perfect():
    assert recall(["a.py", "b.py"], ["a.py", "b.py"]) == pytest.approx(1.0)


def test_recall_partial():
    assert recall(["a.py"], ["a.py", "b.py"]) == pytest.approx(0.5)


def test_recall_no_overlap():
    assert recall(["c.py"], ["a.py", "b.py"]) == pytest.approx(0.0)


def test_recall_empty_retrieved():
    assert recall([], ["a.py"]) == pytest.approx(0.0)


def test_recall_empty_expected():
    assert recall(["a.py"], []) == pytest.approx(0.0)


def test_recall_both_empty():
    assert recall([], []) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# top_k_accuracy
# ---------------------------------------------------------------------------

def test_top_k_accuracy_hit_in_top_3():
    ranked = ["a.py", "b.py", "c.py", "d.py", "e.py"]
    assert top_k_accuracy(ranked, ["b.py"], k=3) == pytest.approx(1.0)


def test_top_k_accuracy_miss_in_top_3():
    ranked = ["a.py", "b.py", "c.py", "d.py", "e.py"]
    assert top_k_accuracy(ranked, ["d.py"], k=3) == pytest.approx(0.0)


def test_top_k_accuracy_hit_in_top_5():
    ranked = ["a.py", "b.py", "c.py", "d.py", "e.py"]
    assert top_k_accuracy(ranked, ["e.py"], k=5) == pytest.approx(1.0)


def test_top_k_accuracy_hit_at_boundary():
    ranked = ["a.py", "b.py", "c.py"]
    assert top_k_accuracy(ranked, ["c.py"], k=3) == pytest.approx(1.0)


def test_top_k_accuracy_just_outside_k():
    ranked = ["a.py", "b.py", "c.py", "d.py"]
    assert top_k_accuracy(ranked, ["d.py"], k=3) == pytest.approx(0.0)


def test_top_k_accuracy_empty_ranked():
    assert top_k_accuracy([], ["a.py"], k=3) == pytest.approx(0.0)


def test_top_k_accuracy_empty_expected():
    assert top_k_accuracy(["a.py"], [], k=3) == pytest.approx(0.0)


def test_top_k_accuracy_k_larger_than_list():
    ranked = ["a.py", "b.py"]
    assert top_k_accuracy(ranked, ["b.py"], k=10) == pytest.approx(1.0)


def test_top_k_accuracy_multiple_expected_any_hit():
    ranked = ["a.py", "b.py", "c.py"]
    assert top_k_accuracy(ranked, ["x.py", "c.py"], k=3) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# evaluate_retrieval
# ---------------------------------------------------------------------------

def test_evaluate_retrieval_integration():
    retrieval_result = RetrievalResult(
        ranked_files=[
            _make_file_candidate("src/a.py"),
            _make_file_candidate("src/b.py"),
            _make_file_candidate("src/c.py"),
        ],
        ranked_symbols=[
            _make_symbol("s1", name="process_payment", file_path="src/a.py"),
            _make_symbol("s2", name="handle_error", file_path="src/b.py"),
            _make_symbol("s3", name="log_event", file_path="src/c.py"),
        ],
    )
    expected_files = ["src/a.py", "src/b.py", "src/d.py"]
    expected_symbols = ["process_payment", "handle_error", "validate_input"]

    result = evaluate_retrieval(retrieval_result, expected_files, expected_symbols)

    assert isinstance(result, EvaluationResult)
    # precision: 2 of 3 retrieved are expected
    assert result.precision == pytest.approx(2 / 3)
    # recall: 2 of 3 expected were found
    assert result.recall == pytest.approx(2 / 3)
    # top_3: src/a.py or src/b.py in top 3 → 1.0
    assert result.top_3_accuracy == pytest.approx(1.0)
    assert result.top_5_accuracy == pytest.approx(1.0)
    assert result.top_10_accuracy == pytest.approx(1.0)
    # symbol_recall: 2 of 3 expected symbols found
    assert result.symbol_recall == pytest.approx(2 / 3)
    assert result.retrieved_files == ["src/a.py", "src/b.py", "src/c.py"]
    assert result.expected_files == expected_files


def test_evaluate_retrieval_empty_result():
    retrieval_result = RetrievalResult()
    result = evaluate_retrieval(retrieval_result, ["a.py"], ["sym1"])

    assert result.precision == pytest.approx(0.0)
    assert result.recall == pytest.approx(0.0)
    assert result.top_3_accuracy == pytest.approx(0.0)
    assert result.symbol_recall == pytest.approx(0.0)


def test_evaluate_retrieval_perfect_match():
    retrieval_result = RetrievalResult(
        ranked_files=[
            _make_file_candidate("src/a.py"),
            _make_file_candidate("src/b.py"),
        ],
        ranked_symbols=[
            _make_symbol("s1", name="func_a"),
            _make_symbol("s2", name="func_b"),
        ],
    )
    result = evaluate_retrieval(
        retrieval_result,
        expected_files=["src/a.py", "src/b.py"],
        expected_symbols=["func_a", "func_b"],
    )

    assert result.precision == pytest.approx(1.0)
    assert result.recall == pytest.approx(1.0)
    assert result.symbol_recall == pytest.approx(1.0)
