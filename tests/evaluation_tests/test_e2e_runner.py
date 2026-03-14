"""Tests for the end-to-end evaluation runner."""

from unittest.mock import MagicMock, patch

import pytest

from evaluation import EvaluationResult
from evaluation.dataset import EvaluationTicket
from evaluation.e2e_runner import (
    E2EResult,
    _extract_retrieval_result,
    _ticket_to_input,
    run_e2e_evaluation,
    run_evaluation_suite,
)
from prompts import GeneratedPrompt
from retrieval import FileCandidate, SymbolMatch, TicketInput


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


def _make_eval_ticket(
    ticket_id: str = "TEST-001",
    title: str = "Test ticket",
    description: str = "A test description",
    repo: str = "my-repo",
    expected_files: list | None = None,
    expected_symbols: list | None = None,
) -> EvaluationTicket:
    return EvaluationTicket(
        ticket_id=ticket_id,
        title=title,
        description=description,
        acceptance_criteria="- Some criteria",
        repo=repo,
        expected_files=expected_files or ["src/a.py", "src/b.py"],
        expected_symbols=expected_symbols or ["func_a", "func_b"],
        expected_behavior="Expected behavior",
    )


# ---------------------------------------------------------------------------
# _ticket_to_input
# ---------------------------------------------------------------------------

def test_ticket_to_input():
    ticket = _make_eval_ticket(
        title="My title",
        description="My desc",
        repo="test-repo",
    )
    result = _ticket_to_input(ticket)

    assert isinstance(result, TicketInput)
    assert result.title == "My title"
    assert result.description == "My desc"
    assert result.repo == "test-repo"
    assert result.acceptance_criteria == "- Some criteria"


# ---------------------------------------------------------------------------
# _extract_retrieval_result
# ---------------------------------------------------------------------------

def test_extract_retrieval_result():
    state = {
        "ranked_files": [
            _make_file_candidate("src/a.py"),
            _make_file_candidate("src/b.py"),
        ],
        "vector_matches": [_make_symbol("v1", source="vector")],
        "keyword_matches": [_make_symbol("k1", source="keyword")],
        "graph_matches": [_make_symbol("g1", source="graph")],
        "expanded_queries": ["q1", "q2", "q3"],
    }
    result = _extract_retrieval_result(state)

    assert len(result.ranked_files) == 2
    assert len(result.ranked_symbols) == 3
    assert result.query_count == 3
    assert result.total_candidates == 3


def test_extract_retrieval_result_empty_state():
    result = _extract_retrieval_result({})

    assert result.ranked_files == []
    assert result.ranked_symbols == []
    assert result.query_count == 0
    assert result.total_candidates == 0


# ---------------------------------------------------------------------------
# run_e2e_evaluation
# ---------------------------------------------------------------------------

@patch("evaluation.e2e_runner.run_pipeline")
def test_run_e2e_evaluation(mock_run_pipeline):
    mock_run_pipeline.return_value = {
        "ticket": None,
        "repo": "my-repo",
        "expanded_queries": ["q1", "q2"],
        "vector_matches": [
            _make_symbol("v1", name="func_a", file_path="src/a.py"),
        ],
        "keyword_matches": [
            _make_symbol("k1", name="func_c", file_path="src/c.py"),
        ],
        "graph_matches": [],
        "ranked_files": [
            _make_file_candidate("src/a.py"),
            _make_file_candidate("src/c.py"),
        ],
        "compressed_context": None,
        "file_contents": {},
        "generated_prompt": GeneratedPrompt(
            prompt_text="Generated prompt text",
            token_count=100,
            files_referenced=["src/a.py", "src/c.py"],
            symbols_referenced=["func_a", "func_c"],
        ),
        "errors": [],
    }

    config = MagicMock()
    ticket = _make_eval_ticket(
        ticket_id="PAY-1001",
        expected_files=["src/a.py", "src/b.py"],
        expected_symbols=["func_a", "func_b"],
    )

    result = run_e2e_evaluation(config, ticket)

    assert isinstance(result, E2EResult)
    assert result.ticket_id == "PAY-1001"
    assert result.execution_time_ms > 0
    assert result.errors == []

    # precision: 1 of 2 retrieved (src/a.py) is expected
    assert result.evaluation.precision == pytest.approx(0.5)
    # recall: 1 of 2 expected (src/a.py) was found
    assert result.evaluation.recall == pytest.approx(0.5)
    # symbol_recall: 1 of 2 (func_a found, func_b not)
    assert result.evaluation.symbol_recall == pytest.approx(0.5)

    assert result.prompt.prompt_text == "Generated prompt text"

    mock_run_pipeline.assert_called_once()


@patch("evaluation.e2e_runner.run_pipeline")
def test_run_e2e_evaluation_with_errors(mock_run_pipeline):
    mock_run_pipeline.return_value = {
        "ranked_files": [],
        "vector_matches": [],
        "keyword_matches": [],
        "graph_matches": [],
        "expanded_queries": [],
        "generated_prompt": GeneratedPrompt(),
        "errors": ["Embedding failed: model not found"],
    }

    config = MagicMock()
    ticket = _make_eval_ticket()

    result = run_e2e_evaluation(config, ticket)

    assert result.errors == ["Embedding failed: model not found"]
    assert result.evaluation.precision == pytest.approx(0.0)
    assert result.evaluation.recall == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# run_evaluation_suite
# ---------------------------------------------------------------------------

@patch("evaluation.e2e_runner.run_pipeline")
def test_run_evaluation_suite(mock_run_pipeline):
    mock_run_pipeline.return_value = {
        "ranked_files": [_make_file_candidate("src/a.py")],
        "vector_matches": [_make_symbol("v1", name="func_a")],
        "keyword_matches": [],
        "graph_matches": [],
        "expanded_queries": ["q1"],
        "generated_prompt": GeneratedPrompt(prompt_text="prompt"),
        "errors": [],
    }

    config = MagicMock()
    dataset = [
        _make_eval_ticket(ticket_id="T-1"),
        _make_eval_ticket(ticket_id="T-2"),
    ]

    results = run_evaluation_suite(config, dataset)

    assert len(results) == 2
    assert results[0].ticket_id == "T-1"
    assert results[1].ticket_id == "T-2"
    assert mock_run_pipeline.call_count == 2
