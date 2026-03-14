"""Ticket expansion: convert a Jira ticket into multiple code-search queries."""

import hashlib
import logging
import re
from typing import Callable, List, Optional

from retrieval import TicketInput

logger = logging.getLogger(__name__)


def combine_ticket_text(ticket: TicketInput) -> str:
    """Concatenate all ticket fields into a single search-friendly string.

    Args:
        ticket: Input ticket with title, description, acceptance_criteria, and comments.

    Returns:
        Single string combining all non-empty ticket fields.
    """
    parts = [ticket.title, ticket.description]

    if ticket.acceptance_criteria:
        parts.append(ticket.acceptance_criteria)

    parts.extend(ticket.comments)

    return " ".join(part for part in parts if part)


def build_expansion_prompt(ticket_text: str, max_queries: int = 6) -> str:
    """Build a prompt that asks an LLM to generate code-search queries.

    Args:
        ticket_text: Combined ticket text to expand.
        max_queries: Maximum number of queries the LLM should produce.

    Returns:
        Prompt string ready to send to an LLM.
    """
    return (
        f"You are a code-search assistant. Given the following software ticket, "
        f"generate up to {max_queries} specific search queries that a developer "
        f"would use to find the relevant source code files, functions, and classes "
        f"needed to implement or fix this ticket.\n\n"
        f"Output one query per line. Do not include explanations or numbering.\n\n"
        f"Ticket:\n{ticket_text}"
    )


def parse_expansion_response(response: str, max_queries: int = 6) -> List[str]:
    """Parse an LLM response into a deduplicated list of search queries.

    Strips leading list prefixes (e.g. "1. ", "- ", "* "), deduplicates,
    and trims to at most max_queries entries.

    Args:
        response: Raw LLM output string.
        max_queries: Maximum number of queries to return.

    Returns:
        List of cleaned, unique query strings.
    """
    if not response or not response.strip():
        return []

    seen = set()
    queries: List[str] = []

    for line in response.splitlines():
        line = line.strip()
        if not line:
            continue

        # Strip numbered prefixes like "1. ", "2) ", and bullet prefixes "- ", "* "
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = re.sub(r"^[-*]\s+", "", line)
        line = line.strip()

        if not line:
            continue

        if line in seen:
            continue

        seen.add(line)
        queries.append(line)

        if len(queries) >= max_queries:
            break

    return queries


def expand_ticket(
    ticket: TicketInput,
    llm_fn: Callable[[str], str],
    cache=None,
    max_queries: int = 6,
) -> List[str]:
    """Expand a ticket into a list of code-search queries.

    Checks the cache first. On a miss, calls llm_fn with a generated prompt,
    parses the response, stores the result in the cache, and returns it.

    Falls back to returning [combined_text] if llm_fn raises or returns an
    empty response.

    Args:
        ticket: Input ticket to expand.
        llm_fn: Callable that accepts a prompt string and returns a response string.
        cache: Optional RedisCache instance. Pass None to skip caching.
        max_queries: Maximum number of queries to generate.

    Returns:
        List of search query strings. Always contains at least one entry.
    """
    combined_text = combine_ticket_text(ticket)
    cache_key = _build_cache_key(ticket.repo, combined_text)

    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for expansion key %r", cache_key)
            return cached

    try:
        prompt = build_expansion_prompt(combined_text, max_queries=max_queries)
        response = llm_fn(prompt)
        queries = parse_expansion_response(response, max_queries=max_queries)
    except Exception as exc:
        logger.warning("LLM expansion failed, falling back to combined text: %s", exc)
        return [combined_text]

    if not queries:
        logger.warning("LLM returned empty expansion response, falling back to combined text")
        return [combined_text]

    if cache is not None:
        cache.set(cache_key, queries)

    return queries


def _build_cache_key(repo: str, combined_text: str) -> str:
    """Construct a deterministic cache key for the given repo and ticket text.

    Args:
        repo: Repository identifier.
        combined_text: Combined ticket text used to derive the hash.

    Returns:
        Cache key string of the form ``repo:<repo>:expansion:<hash>``.
    """
    text_hash = hashlib.sha256(combined_text.encode()).hexdigest()[:16]
    return f"repo:{repo}:expansion:{text_hash}"
