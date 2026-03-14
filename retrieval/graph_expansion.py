"""Expand context via code knowledge graph traversal."""

import logging
from collections import deque
from typing import Dict, List, Optional, Set

from retrieval import SymbolMatch

logger = logging.getLogger(__name__)

GRAPH_DISTANCE_SCORES: Dict[int, float] = {0: 1.0, 1: 0.7, 2: 0.4}


def _bfs_expand(postgres, seed_ids: set, max_depth: int, org_id: str, project_id: str) -> dict:
    """BFS traversal of the code graph.

    Traverses both outgoing (get_edges_from) and incoming (get_edges_to) edges
    from each visited node to discover all reachable neighbors.

    Returns:
        dict mapping symbol_id -> minimum distance from any seed.
    """
    distances: Dict[str, int] = {}
    queue: deque = deque()

    for seed_id in seed_ids:
        distances[seed_id] = 0
        queue.append((seed_id, 0))

    while queue:
        current_id, current_dist = queue.popleft()

        if current_dist >= max_depth:
            continue

        next_dist = current_dist + 1

        # Outgoing edges: neighbors are to_symbol values
        for edge in postgres.get_edges_from(current_id, org_id, project_id):
            neighbor = edge["to_symbol"]
            if neighbor not in distances:
                distances[neighbor] = next_dist
                queue.append((neighbor, next_dist))

        # Incoming edges: neighbors are from_symbol values
        for edge in postgres.get_edges_to(current_id, org_id, project_id):
            neighbor = edge["from_symbol"]
            if neighbor not in distances:
                distances[neighbor] = next_dist
                queue.append((neighbor, next_dist))

    return distances


def expand_symbols(
    postgres,
    seed_symbol_ids: list,
    max_depth: int = 2,
    org_id: str = "",
    project_id: str = "",
) -> List[SymbolMatch]:
    """Expand seed symbols via BFS and resolve each to a SymbolMatch.

    Symbols that cannot be resolved via postgres.get_symbol() are skipped.

    Returns:
        List of SymbolMatch with source="graph".
    """
    if not seed_symbol_ids:
        return []

    distances = _bfs_expand(postgres, seed_ids=set(seed_symbol_ids), max_depth=max_depth, org_id=org_id, project_id=project_id)

    results: List[SymbolMatch] = []
    for symbol_id, distance in distances.items():
        record = postgres.get_symbol(symbol_id)
        if record is None:
            logger.debug("Graph expansion: symbol %s not found, skipping", symbol_id)
            continue

        score = GRAPH_DISTANCE_SCORES.get(distance, 0.1)
        results.append(
            SymbolMatch(
                symbol_id=record["symbol_id"],
                name=record["name"],
                type=record["type"],
                file_path=record["file_path"],
                repo=record["repo"],
                start_line=record["start_line"],
                end_line=record["end_line"],
                score=score,
                source="graph",
            )
        )

    return results


def graph_expansion(
    postgres,
    initial_matches: list,
    max_depth: int = 2,
    org_id: str = "",
    project_id: str = "",
) -> List[SymbolMatch]:
    """Expand initial matches via graph traversal and merge results.

    Seeds the BFS from each symbol_id in initial_matches, then merges the
    discovered symbols with the initial list. When a symbol appears in both
    sets, the entry with the higher score is kept.

    Returns:
        Combined list of SymbolMatch instances, deduplicated by symbol_id.
    """
    if not initial_matches:
        return []

    seed_ids = [m.symbol_id for m in initial_matches]
    graph_matches = expand_symbols(postgres, seed_symbol_ids=seed_ids, max_depth=max_depth, org_id=org_id, project_id=project_id)

    # Index initial matches by symbol_id
    merged: Dict[str, SymbolMatch] = {m.symbol_id: m for m in initial_matches}

    # Merge graph matches: keep whichever score is higher
    for gm in graph_matches:
        existing = merged.get(gm.symbol_id)
        if existing is None:
            merged[gm.symbol_id] = gm
        elif gm.score > existing.score:
            merged[gm.symbol_id] = gm

    return list(merged.values())
