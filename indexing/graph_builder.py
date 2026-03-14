"""Build code knowledge graph from extracted symbols."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

VALID_RELATION_TYPES: set[str] = {
    "calls", "imports", "inherits", "implements", "references",
}


@dataclass
class GraphNode:
    """A node in the code knowledge graph."""
    symbol_id: str
    name: str
    type: str
    file_path: str
    repo: str


@dataclass
class GraphEdge:
    """An edge in the code knowledge graph."""
    from_symbol: str
    to_symbol: str
    relation_type: str


@dataclass
class GraphBuildResult:
    """Result of building a code knowledge graph."""
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


def validate_edge(
    from_symbol: str,
    to_symbol: str,
    relation_type: str,
    known_symbols: set[str],
) -> bool:
    """Validate that an edge references known symbols and has a valid relation type."""
    if from_symbol not in known_symbols:
        return False
    if to_symbol not in known_symbols:
        return False
    if relation_type not in VALID_RELATION_TYPES:
        return False
    return True


def build_graph(
    symbols: list[dict],
    raw_edges: list[tuple[str, str, str]],
) -> GraphBuildResult:
    """Build a validated code knowledge graph.

    Args:
        symbols: List of dicts with keys: symbol_id, name, type, file_path, repo
        raw_edges: List of (from_id, to_id, relation_type) tuples

    Returns:
        GraphBuildResult with validated nodes and edges.
    """
    nodes = [
        GraphNode(
            symbol_id=sym["symbol_id"],
            name=sym["name"],
            type=sym["type"],
            file_path=sym["file_path"],
            repo=sym["repo"],
        )
        for sym in symbols
    ]

    known_ids = {sym["symbol_id"] for sym in symbols}

    edges = []
    for from_id, to_id, rel_type in raw_edges:
        if validate_edge(from_id, to_id, rel_type, known_ids):
            edges.append(GraphEdge(
                from_symbol=from_id,
                to_symbol=to_id,
                relation_type=rel_type,
            ))
        else:
            logger.debug(
                "Skipping invalid edge: %s -> %s (%s)", from_id, to_id, rel_type
            )

    return GraphBuildResult(nodes=nodes, edges=edges)
