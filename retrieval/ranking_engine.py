"""Rank and score retrieval results."""

import datetime
import logging
from typing import Dict, List, Optional

from retrieval import FileCandidate, SymbolMatch

logger = logging.getLogger(__name__)

WEIGHT_SEMANTIC: float = 0.55
WEIGHT_GRAPH: float = 0.20
WEIGHT_KEYWORD: float = 0.15
WEIGHT_GIT_RECENCY: float = 0.05
WEIGHT_SYMBOL_DENSITY: float = 0.05

DEFAULT_FILE_LIMIT: int = 10

_GIT_RECENCY_RECENT_DAYS: int = 7
_GIT_RECENCY_MEDIUM_DAYS: int = 30
_GIT_RECENCY_SCORE_RECENT: float = 1.0
_GIT_RECENCY_SCORE_MEDIUM: float = 0.7
_GIT_RECENCY_SCORE_OLD: float = 0.3

_DENSITY_THRESHOLDS: list = [
    (3, 1.0),
    (2, 0.6),
    (1, 0.3),
]


def group_symbols_by_file(symbols: list) -> dict:
    """Group a list of SymbolMatch objects by file_path.

    Returns a dict mapping file_path -> list[SymbolMatch].
    """
    grouped: Dict[str, List[SymbolMatch]] = {}
    for symbol in symbols:
        grouped.setdefault(symbol.file_path, []).append(symbol)
    return grouped


def compute_semantic_score(symbols: list) -> float:
    """Return the maximum score among symbols with source='vector', or 0.0."""
    scores = [s.score for s in symbols if s.source == "vector"]
    return max(scores) if scores else 0.0


def compute_graph_score(symbols: list) -> float:
    """Return the maximum score among symbols with source='graph', or 0.0."""
    scores = [s.score for s in symbols if s.source == "graph"]
    return max(scores) if scores else 0.0


def compute_keyword_score(symbols: list) -> float:
    """Return the maximum score among symbols with source='keyword', or 0.0."""
    scores = [s.score for s in symbols if s.source == "keyword"]
    return max(scores) if scores else 0.0


def compute_git_recency_score(
    file_path: str,
    repo: str,
    postgres,
    org_id: str = "",
    project_id: str = "",
) -> float:
    """Return a recency score based on the file's last_modified date.

    Thresholds (compared against datetime.datetime.now()):
      - Within 7 days  → 1.0
      - Within 30 days → 0.7
      - Older or unknown → 0.3
    """
    try:
        metadata = postgres.get_file_metadata(file_path, repo, org_id, project_id)
    except Exception:
        logger.warning("Failed to fetch metadata for %s/%s", repo, file_path)
        return _GIT_RECENCY_SCORE_OLD

    if metadata is None:
        return _GIT_RECENCY_SCORE_OLD

    last_modified: Optional[datetime.datetime] = metadata.get("last_modified")
    if last_modified is None:
        return _GIT_RECENCY_SCORE_OLD

    age = datetime.datetime.now() - last_modified
    if age.days <= _GIT_RECENCY_RECENT_DAYS:
        return _GIT_RECENCY_SCORE_RECENT
    if age.days <= _GIT_RECENCY_MEDIUM_DAYS:
        return _GIT_RECENCY_SCORE_MEDIUM
    return _GIT_RECENCY_SCORE_OLD


def compute_symbol_density_score(symbol_count: int) -> float:
    """Map symbol count to a density score.

    0 → 0.0, 1 → 0.3, 2 → 0.6, 3+ → 1.0
    """
    if symbol_count <= 0:
        return 0.0
    for threshold, score in _DENSITY_THRESHOLDS:
        if symbol_count >= threshold:
            return score
    return 0.0


def _build_file_candidate(
    file_path: str,
    repo: str,
    symbols: List[SymbolMatch],
    postgres,
    org_id: str = "",
    project_id: str = "",
) -> FileCandidate:
    """Compute all sub-scores and assemble a FileCandidate."""
    semantic = compute_semantic_score(symbols)
    graph = compute_graph_score(symbols)
    keyword = compute_keyword_score(symbols)
    git_recency = compute_git_recency_score(file_path, repo, postgres, org_id=org_id, project_id=project_id)
    density = compute_symbol_density_score(len(symbols))

    final_score = (
        WEIGHT_SEMANTIC * semantic
        + WEIGHT_GRAPH * graph
        + WEIGHT_KEYWORD * keyword
        + WEIGHT_GIT_RECENCY * git_recency
        + WEIGHT_SYMBOL_DENSITY * density
    )

    return FileCandidate(
        file_path=file_path,
        repo=repo,
        symbols=symbols,
        final_score=final_score,
        semantic_score=semantic,
        graph_score=graph,
        keyword_score=keyword,
        git_recency_score=git_recency,
        symbol_density_score=density,
    )


def rank_files(
    vector_matches: list,
    keyword_matches: list,
    graph_matches: list,
    postgres,
    repo: str,
    file_limit: int = DEFAULT_FILE_LIMIT,
    org_id: str = "",
    project_id: str = "",
) -> list:
    """Merge, score, and rank files from all retrieval sources.

    Steps:
      1. Merge all symbol matches into one list.
      2. Group by file_path.
      3. Compute all five sub-scores per file.
      4. Compute weighted final_score.
      5. Sort descending by (final_score, symbol_count, git_recency_score).
      6. Return the top file_limit FileCandidate objects.
    """
    all_symbols: List[SymbolMatch] = list(vector_matches) + list(keyword_matches) + list(graph_matches)

    if not all_symbols:
        return []

    grouped = group_symbols_by_file(all_symbols)

    candidates: List[FileCandidate] = [
        _build_file_candidate(file_path, repo, symbols, postgres, org_id=org_id, project_id=project_id)
        for file_path, symbols in grouped.items()
    ]

    candidates.sort(
        key=lambda fc: (fc.final_score, len(fc.symbols), fc.git_recency_score),
        reverse=True,
    )

    return candidates[:file_limit]
