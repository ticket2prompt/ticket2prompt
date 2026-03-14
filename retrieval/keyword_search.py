"""Keyword search: extract terms from a ticket and match against symbol names."""

import logging
import re
from typing import List

from retrieval import SymbolMatch, TicketInput

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "this", "that",
    "these", "those", "it", "its", "not", "no", "if", "when", "then",
    "than", "as", "so", "up", "out", "about",
}


def extract_keywords(text: str, min_length: int = 3, max_keywords: int = 10) -> List[str]:
    """Lowercase, tokenise on non-alphanumeric chars, filter stopwords and short
    words, deduplicate while preserving first-seen order, then cap at max_keywords."""
    tokens = re.split(r"[^a-zA-Z0-9]+", text.lower())
    seen: set = set()
    keywords: List[str] = []
    for token in tokens:
        if (
            token
            and len(token) >= min_length
            and token not in STOPWORDS
            and token not in seen
        ):
            seen.add(token)
            keywords.append(token)
            if len(keywords) == max_keywords:
                break
    return keywords


def compute_keyword_score(match_count: int) -> float:
    """Score based on how many distinct keywords matched a symbol.

    1 match → 0.3, 2 → 0.6, 3+ → 1.0
    """
    if match_count >= 3:
        return 1.0
    return round(match_count * 0.3, 10)


def search_symbols_by_keywords(
    postgres,
    keywords: List[str],
    repo: str,
    org_id: str = "",
    project_id: str = "",
) -> List[SymbolMatch]:
    """Query postgres for each keyword and aggregate hits per symbol.

    A symbol matched by N distinct keywords receives score = compute_keyword_score(N).
    """
    # symbol_id → {"row": dict, "match_count": int}
    aggregated: dict = {}

    for keyword in keywords:
        rows = postgres.search_symbols_by_name(org_id, project_id, keyword)
        for row in rows:
            sid = row["symbol_id"]
            if sid not in aggregated:
                aggregated[sid] = {"row": row, "match_count": 0}
            aggregated[sid]["match_count"] += 1

    results: List[SymbolMatch] = []
    for sid, entry in aggregated.items():
        row = entry["row"]
        score = compute_keyword_score(entry["match_count"])
        results.append(
            SymbolMatch(
                symbol_id=row["symbol_id"],
                name=row["name"],
                type=row["type"],
                file_path=row["file_path"],
                repo=row["repo"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                score=score,
                source="keyword",
            )
        )

    logger.debug(
        "keyword search found %d symbols from %d keywords in repo %s",
        len(results),
        len(keywords),
        repo,
    )
    return results


def keyword_search(
    postgres,
    ticket: TicketInput,
    repo: str,
    org_id: str = "",
    project_id: str = "",
) -> List[SymbolMatch]:
    """Full pipeline: combine ticket text → extract keywords → search symbols."""
    combined_text = (
        f"{ticket.title} {ticket.description} {ticket.acceptance_criteria}"
        f" {' '.join(ticket.comments)}"
    )
    keywords = extract_keywords(combined_text)
    if not keywords:
        logger.debug("No keywords extracted from ticket for repo %s", repo)
        return []
    return search_symbols_by_keywords(postgres, keywords, repo, org_id=org_id, project_id=project_id)
