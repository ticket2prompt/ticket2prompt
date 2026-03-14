"""Unit tests for retrieval/graph_expansion.py."""

from unittest.mock import MagicMock

import pytest

from retrieval import SymbolMatch
from retrieval.graph_expansion import (
    GRAPH_DISTANCE_SCORES,
    _bfs_expand,
    expand_symbols,
    graph_expansion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_symbol(symbol_id: str, name: str = None, file_path: str = "a.py") -> dict:
    """Return a minimal postgres symbol record."""
    return {
        "symbol_id": symbol_id,
        "name": name or symbol_id,
        "type": "function",
        "file_path": file_path,
        "repo": "my-repo",
        "start_line": 1,
        "end_line": 10,
    }


def make_edge(from_symbol: str, to_symbol: str, relation_type: str = "calls") -> dict:
    return {
        "id": 1,
        "from_symbol": from_symbol,
        "to_symbol": to_symbol,
        "relation_type": relation_type,
    }


def make_symbol_match(symbol_id: str, score: float = 0.9, source: str = "vector") -> SymbolMatch:
    return SymbolMatch(
        symbol_id=symbol_id,
        name=symbol_id,
        type="function",
        file_path="a.py",
        repo="my-repo",
        start_line=1,
        end_line=10,
        score=score,
        source=source,
    )


def postgres_no_edges() -> MagicMock:
    """Postgres client stub that returns no edges for any symbol."""
    pg = MagicMock()
    pg.get_edges_from.return_value = []
    pg.get_edges_to.return_value = []
    return pg


# ---------------------------------------------------------------------------
# test_graph_distance_scores
# ---------------------------------------------------------------------------


def test_graph_distance_scores():
    assert GRAPH_DISTANCE_SCORES == {0: 1.0, 1: 0.7, 2: 0.4}


# ---------------------------------------------------------------------------
# _bfs_expand
# ---------------------------------------------------------------------------


def test_bfs_expand_no_edges():
    pg = postgres_no_edges()
    result = _bfs_expand(pg, seed_ids={"A"}, max_depth=2, org_id="", project_id="")
    assert result == {"A": 0}


def test_bfs_expand_one_hop():
    pg = MagicMock()
    # A → B
    pg.get_edges_from.side_effect = lambda sid, org_id, project_id: [make_edge("A", "B")] if sid == "A" else []
    pg.get_edges_to.return_value = []

    result = _bfs_expand(pg, seed_ids={"A"}, max_depth=2, org_id="", project_id="")
    assert result["A"] == 0
    assert result["B"] == 1


def test_bfs_expand_two_hops():
    pg = MagicMock()
    # A → B → C
    pg.get_edges_from.side_effect = lambda sid, org_id, project_id: (
        [make_edge("A", "B")] if sid == "A"
        else [make_edge("B", "C")] if sid == "B"
        else []
    )
    pg.get_edges_to.return_value = []

    result = _bfs_expand(pg, seed_ids={"A"}, max_depth=2, org_id="", project_id="")
    assert result["A"] == 0
    assert result["B"] == 1
    assert result["C"] == 2


def test_bfs_expand_respects_max_depth():
    pg = MagicMock()
    # A → B → C → D
    pg.get_edges_from.side_effect = lambda sid, org_id, project_id: (
        [make_edge("A", "B")] if sid == "A"
        else [make_edge("B", "C")] if sid == "B"
        else [make_edge("C", "D")] if sid == "C"
        else []
    )
    pg.get_edges_to.return_value = []

    result = _bfs_expand(pg, seed_ids={"A"}, max_depth=2, org_id="", project_id="")
    assert "D" not in result
    assert result["C"] == 2


def test_bfs_expand_bidirectional():
    pg = MagicMock()
    # X → A (seed A should discover X via get_edges_to)
    pg.get_edges_from.return_value = []
    pg.get_edges_to.side_effect = lambda sid, org_id, project_id: [make_edge("X", "A")] if sid == "A" else []

    result = _bfs_expand(pg, seed_ids={"A"}, max_depth=2, org_id="", project_id="")
    assert result["A"] == 0
    assert result["X"] == 1


def test_bfs_expand_no_revisit():
    pg = MagicMock()
    # Cycle: A → B → A
    pg.get_edges_from.side_effect = lambda sid, org_id, project_id: (
        [make_edge("A", "B")] if sid == "A"
        else [make_edge("B", "A")] if sid == "B"
        else []
    )
    pg.get_edges_to.return_value = []

    # Should terminate without infinite loop
    result = _bfs_expand(pg, seed_ids={"A"}, max_depth=2, org_id="", project_id="")
    assert result["A"] == 0
    assert result["B"] == 1


# ---------------------------------------------------------------------------
# expand_symbols
# ---------------------------------------------------------------------------


def test_expand_symbols_resolves_records():
    pg = postgres_no_edges()
    pg.get_symbol.return_value = make_symbol("A", name="func_a", file_path="src/a.py")

    results = expand_symbols(pg, seed_symbol_ids=["A"], max_depth=2, org_id="", project_id="")

    assert len(results) == 1
    match = results[0]
    assert isinstance(match, SymbolMatch)
    assert match.symbol_id == "A"
    assert match.name == "func_a"
    assert match.file_path == "src/a.py"
    assert match.repo == "my-repo"
    assert match.score == GRAPH_DISTANCE_SCORES[0]
    assert match.source == "graph"


def test_expand_symbols_skips_missing():
    pg = MagicMock()
    # A → B, but B has no symbol record
    pg.get_edges_from.side_effect = lambda sid, org_id, project_id: [make_edge("A", "B")] if sid == "A" else []
    pg.get_edges_to.return_value = []
    pg.get_symbol.side_effect = lambda sid: make_symbol(sid) if sid == "A" else None

    results = expand_symbols(pg, seed_symbol_ids=["A"], max_depth=2, org_id="", project_id="")
    symbol_ids = {m.symbol_id for m in results}
    assert "A" in symbol_ids
    assert "B" not in symbol_ids


# ---------------------------------------------------------------------------
# graph_expansion
# ---------------------------------------------------------------------------


def test_graph_expansion_deduplicates_with_initial():
    pg = postgres_no_edges()
    pg.get_symbol.return_value = make_symbol("A")

    # Initial has A with a high score (0.95)
    initial = [make_symbol_match("A", score=0.95, source="vector")]

    result = graph_expansion(pg, initial_matches=initial, max_depth=2, org_id="", project_id="")

    # A appears only once
    matches_for_a = [m for m in result if m.symbol_id == "A"]
    assert len(matches_for_a) == 1
    # Graph distance 0 score is 1.0, which is > 0.95, so graph score wins
    assert matches_for_a[0].score == GRAPH_DISTANCE_SCORES[0]


def test_graph_expansion_keeps_initial_score_when_higher(monkeypatch):
    """When initial score > graph score, the initial entry is preserved."""
    import retrieval.graph_expansion as ge

    pg = MagicMock()

    # Initial has A at score 0.9 (vector source)
    initial = [make_symbol_match("A", score=0.9, source="vector")]

    # Stub expand_symbols to return A with a lower graph score (distance 1 = 0.7)
    graph_a = SymbolMatch(
        symbol_id="A",
        name="A",
        type="function",
        file_path="a.py",
        repo="my-repo",
        start_line=1,
        end_line=10,
        score=0.7,
        source="graph",
    )
    monkeypatch.setattr(ge, "expand_symbols", lambda *args, **kwargs: [graph_a])

    result = graph_expansion(pg, initial_matches=initial, max_depth=2, org_id="", project_id="")

    matches_for_a = [m for m in result if m.symbol_id == "A"]
    assert len(matches_for_a) == 1
    # Initial score 0.9 > graph score 0.7, so initial entry wins
    assert matches_for_a[0].score == 0.9
    assert matches_for_a[0].source == "vector"


def test_graph_expansion_empty_initial():
    pg = postgres_no_edges()
    result = graph_expansion(pg, initial_matches=[], max_depth=2, org_id="", project_id="")
    assert result == []
