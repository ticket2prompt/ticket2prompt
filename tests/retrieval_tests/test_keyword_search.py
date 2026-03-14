"""Unit tests for the keyword search module."""

from unittest.mock import MagicMock

import pytest

from retrieval import SymbolMatch, TicketInput
from retrieval.keyword_search import (
    compute_keyword_score,
    extract_keywords,
    keyword_search,
    search_symbols_by_keywords,
)


# ---------------------------------------------------------------------------
# extract_keywords
# ---------------------------------------------------------------------------


def test_extract_keywords_basic():
    result = extract_keywords("retry payment gateway")
    assert result == ["retry", "payment", "gateway"]


def test_extract_keywords_filters_short_words():
    # "or" (2 chars) and "is" (2 chars) should be excluded by min_length=3
    result = extract_keywords("retry or is payment")
    assert "or" not in result
    assert "is" not in result
    assert "retry" in result
    assert "payment" in result


def test_extract_keywords_filters_stopwords():
    result = extract_keywords("the payment and retry for gateway with auth")
    assert "the" not in result
    assert "and" not in result
    assert "for" not in result
    assert "with" not in result
    assert "payment" in result
    assert "retry" in result
    assert "gateway" in result
    assert "auth" in result


def test_extract_keywords_deduplicates():
    result = extract_keywords("retry payment retry gateway payment")
    assert result.count("retry") == 1
    assert result.count("payment") == 1
    assert result.count("gateway") == 1


def test_extract_keywords_max_limit():
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    result = extract_keywords(text, max_keywords=3)
    assert len(result) == 3


def test_extract_keywords_handles_punctuation():
    result = extract_keywords("retry, payment!")
    assert "retry" in result
    assert "payment" in result
    # Punctuation must not appear in tokens
    assert not any("," in kw or "!" in kw for kw in result)


# ---------------------------------------------------------------------------
# compute_keyword_score
# ---------------------------------------------------------------------------


def test_compute_keyword_score_one_match():
    assert compute_keyword_score(1) == pytest.approx(0.3)


def test_compute_keyword_score_two_matches():
    assert compute_keyword_score(2) == pytest.approx(0.6)


def test_compute_keyword_score_three_plus():
    assert compute_keyword_score(3) == pytest.approx(1.0)
    assert compute_keyword_score(5) == pytest.approx(1.0)
    assert compute_keyword_score(10) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# search_symbols_by_keywords
# ---------------------------------------------------------------------------


def _make_db_row(
    symbol_id: str = "sym-1",
    name: str = "retry_payment",
    symbol_type: str = "function",
    file_path: str = "payments/retry.py",
    repo: str = "my-repo",
    start_line: int = 10,
    end_line: int = 30,
) -> dict:
    return {
        "symbol_id": symbol_id,
        "name": name,
        "type": symbol_type,
        "file_path": file_path,
        "repo": repo,
        "start_line": start_line,
        "end_line": end_line,
    }


def test_search_symbols_by_keywords_single_match():
    postgres = MagicMock()
    row = _make_db_row()
    # Only "retry" produces a match; "payment" returns nothing
    postgres.search_symbols_by_name.side_effect = lambda org_id, project_id, kw: (
        [row] if kw == "retry" else []
    )

    results = search_symbols_by_keywords(postgres, ["retry", "payment"], "my-repo")

    assert len(results) == 1
    match = results[0]
    assert isinstance(match, SymbolMatch)
    assert match.symbol_id == "sym-1"
    assert match.score == pytest.approx(0.3)
    assert match.source == "keyword"


def test_search_symbols_by_keywords_multiple_keywords_same_symbol():
    postgres = MagicMock()
    row = _make_db_row()
    # Both keywords match the same symbol
    postgres.search_symbols_by_name.return_value = [row]

    results = search_symbols_by_keywords(postgres, ["retry", "payment"], "my-repo")

    assert len(results) == 1
    assert results[0].score == pytest.approx(0.6)


def test_search_symbols_by_keywords_no_matches():
    postgres = MagicMock()
    postgres.search_symbols_by_name.return_value = []

    results = search_symbols_by_keywords(postgres, ["retry", "payment"], "my-repo")

    assert results == []


# ---------------------------------------------------------------------------
# keyword_search (end-to-end)
# ---------------------------------------------------------------------------


def test_keyword_search_end_to_end():
    postgres = MagicMock()
    row = _make_db_row(
        symbol_id="sym-42",
        name="process_payment",
        symbol_type="function",
        file_path="billing/process.py",
        repo="my-repo",
        start_line=5,
        end_line=25,
    )
    # Return the row only when the keyword is "process" or "payment"
    postgres.search_symbols_by_name.side_effect = lambda org_id, project_id, kw: (
        [row] if kw in {"process", "payment"} else []
    )

    ticket = TicketInput(
        title="process payment",
        description="retry on failure",
        acceptance_criteria="",
        comments=[],
        repo="my-repo",
    )

    results = keyword_search(postgres, ticket, "my-repo")

    assert len(results) == 1
    match = results[0]
    assert match.symbol_id == "sym-42"
    assert match.source == "keyword"
    # "process" and "payment" both match → score 0.6
    assert match.score == pytest.approx(0.6)
