"""Unit tests for retrieval/ticket_expansion.py."""

import hashlib
from unittest.mock import MagicMock

import pytest

from retrieval import TicketInput
from retrieval.ticket_expansion import (
    build_expansion_prompt,
    combine_ticket_text,
    expand_ticket,
    parse_expansion_response,
)


# ---------------------------------------------------------------------------
# combine_ticket_text
# ---------------------------------------------------------------------------


def test_combine_ticket_text_all_fields():
    ticket = TicketInput(
        title="Add payment retry logic",
        description="Implement exponential backoff for failed payments.",
        acceptance_criteria="Retries up to 3 times with backoff.",
        comments=["First comment", "Second comment"],
        repo="payments-service",
    )
    result = combine_ticket_text(ticket)
    assert "Add payment retry logic" in result
    assert "Implement exponential backoff for failed payments." in result
    assert "Retries up to 3 times with backoff." in result
    assert "First comment" in result
    assert "Second comment" in result


def test_combine_ticket_text_minimal():
    ticket = TicketInput(
        title="Fix null pointer",
        description="NullPointerException in UserService.",
    )
    result = combine_ticket_text(ticket)
    assert "Fix null pointer" in result
    assert "NullPointerException in UserService." in result
    # Empty fields should not inject noise
    assert result.strip() != ""


# ---------------------------------------------------------------------------
# parse_expansion_response
# ---------------------------------------------------------------------------


def test_parse_expansion_response_basic():
    response = "find payment retry logic\nlocate exponential backoff implementation\nsearch PaymentService class"
    queries = parse_expansion_response(response)
    assert "find payment retry logic" in queries
    assert "locate exponential backoff implementation" in queries
    assert "search PaymentService class" in queries


def test_parse_expansion_response_strips_numbering():
    response = "1. first query\n2. second query\n- third query\n* fourth query"
    queries = parse_expansion_response(response)
    assert "first query" in queries
    assert "second query" in queries
    assert "third query" in queries
    assert "fourth query" in queries
    # Ensure prefixes are stripped
    for q in queries:
        assert not q.startswith("1.")
        assert not q.startswith("2.")
        assert not q.startswith("-")
        assert not q.startswith("*")


def test_parse_expansion_response_deduplicates():
    response = "find payment service\nfind payment service\nlocate retry logic"
    queries = parse_expansion_response(response)
    assert queries.count("find payment service") == 1
    assert "locate retry logic" in queries


def test_parse_expansion_response_respects_max():
    lines = "\n".join(f"query number {i}" for i in range(10))
    queries = parse_expansion_response(lines, max_queries=4)
    assert len(queries) <= 4


def test_parse_expansion_response_empty_string():
    queries = parse_expansion_response("")
    assert queries == []


# ---------------------------------------------------------------------------
# build_expansion_prompt
# ---------------------------------------------------------------------------


def test_build_expansion_prompt_includes_ticket_text():
    ticket_text = "Add retry logic for payment failures with exponential backoff"
    prompt = build_expansion_prompt(ticket_text, max_queries=6)
    assert ticket_text in prompt
    # Prompt should instruct the LLM to generate search queries
    assert isinstance(prompt, str)
    assert len(prompt) > len(ticket_text)


# ---------------------------------------------------------------------------
# expand_ticket
# ---------------------------------------------------------------------------


def test_expand_ticket_calls_llm_and_returns_queries():
    ticket = TicketInput(
        title="Implement caching layer",
        description="Add Redis caching to the user service.",
        repo="user-service",
    )
    llm_response = "find Redis cache implementation\nlocate user service caching\nsearch cache TTL configuration"
    llm_fn = MagicMock(return_value=llm_response)

    queries = expand_ticket(ticket, llm_fn=llm_fn, cache=None)

    llm_fn.assert_called_once()
    assert isinstance(queries, list)
    assert len(queries) > 0
    assert "find Redis cache implementation" in queries


def test_expand_ticket_caches_result():
    ticket = TicketInput(
        title="Add logging",
        description="Structured logging for API requests.",
        repo="api-service",
    )
    llm_fn = MagicMock(return_value="find logging middleware\nlocate request logger")
    cache = MagicMock()
    cache.get.return_value = None  # cache miss

    queries = expand_ticket(ticket, llm_fn=llm_fn, cache=cache)

    cache.set.assert_called_once()
    call_args = cache.set.call_args
    key = call_args[0][0]
    value = call_args[0][1]
    assert "api-service" in key
    assert isinstance(value, list)
    assert value == queries


def test_expand_ticket_returns_cached_result():
    ticket = TicketInput(
        title="Add logging",
        description="Structured logging for API requests.",
        repo="api-service",
    )
    cached_queries = ["cached query one", "cached query two"]
    cache = MagicMock()
    cache.get.return_value = cached_queries
    llm_fn = MagicMock()

    queries = expand_ticket(ticket, llm_fn=llm_fn, cache=cache)

    llm_fn.assert_not_called()
    assert queries == cached_queries


def test_expand_ticket_fallback_on_llm_failure():
    ticket = TicketInput(
        title="Fix bug",
        description="Crash in payment module.",
        repo="payments",
    )
    llm_fn = MagicMock(side_effect=RuntimeError("LLM unavailable"))

    queries = expand_ticket(ticket, llm_fn=llm_fn, cache=None)

    combined = combine_ticket_text(ticket)
    assert queries == [combined]


def test_expand_ticket_fallback_on_empty_response():
    ticket = TicketInput(
        title="Fix bug",
        description="Crash in payment module.",
        repo="payments",
    )
    llm_fn = MagicMock(return_value="")

    queries = expand_ticket(ticket, llm_fn=llm_fn, cache=None)

    combined = combine_ticket_text(ticket)
    assert queries == [combined]


def test_expand_ticket_cache_key_uses_repo_and_hash():
    ticket = TicketInput(
        title="Add feature",
        description="Some description.",
        repo="my-repo",
    )
    cache = MagicMock()
    cache.get.return_value = None
    llm_fn = MagicMock(return_value="query one\nquery two")

    expand_ticket(ticket, llm_fn=llm_fn, cache=cache)

    combined = combine_ticket_text(ticket)
    expected_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
    expected_key = f"repo:my-repo:expansion:{expected_hash}"
    cache.get.assert_called_once_with(expected_key)
    cache.set.assert_called_once()
    assert cache.set.call_args[0][0] == expected_key
