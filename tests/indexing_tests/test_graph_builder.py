import pytest
from indexing.graph_builder import (
    GraphNode,
    GraphEdge,
    GraphBuildResult,
    VALID_RELATION_TYPES,
    build_graph,
    validate_edge,
)


def test_graph_node_dataclass():
    node = GraphNode(
        symbol_id="repo:src/foo.py:MyClass",
        name="MyClass",
        type="class",
        file_path="src/foo.py",
        repo="repo",
    )
    assert node.symbol_id == "repo:src/foo.py:MyClass"
    assert node.name == "MyClass"
    assert node.type == "class"
    assert node.file_path == "src/foo.py"
    assert node.repo == "repo"


def test_graph_edge_dataclass():
    edge = GraphEdge(
        from_symbol="repo:src/foo.py:MyClass",
        to_symbol="repo:src/bar.py:OtherClass",
        relation_type="calls",
    )
    assert edge.from_symbol == "repo:src/foo.py:MyClass"
    assert edge.to_symbol == "repo:src/bar.py:OtherClass"
    assert edge.relation_type == "calls"


def test_valid_relation_types():
    assert "calls" in VALID_RELATION_TYPES
    assert "imports" in VALID_RELATION_TYPES
    assert "inherits" in VALID_RELATION_TYPES
    assert "implements" in VALID_RELATION_TYPES
    assert "references" in VALID_RELATION_TYPES


def test_validate_edge_valid():
    known_symbols = {"sym_a", "sym_b"}
    assert validate_edge("sym_a", "sym_b", "calls", known_symbols) is True


def test_validate_edge_unknown_from_symbol():
    known_symbols = {"sym_b"}
    assert validate_edge("sym_a", "sym_b", "calls", known_symbols) is False


def test_validate_edge_unknown_to_symbol():
    known_symbols = {"sym_a"}
    assert validate_edge("sym_a", "sym_b", "calls", known_symbols) is False


def test_validate_edge_invalid_relation_type():
    known_symbols = {"sym_a", "sym_b"}
    assert validate_edge("sym_a", "sym_b", "unknown", known_symbols) is False


def test_build_graph_basic():
    symbols = [
        {"symbol_id": "repo:a.py:func_a", "name": "func_a", "type": "function", "file_path": "a.py", "repo": "repo"},
        {"symbol_id": "repo:b.py:func_b", "name": "func_b", "type": "function", "file_path": "b.py", "repo": "repo"},
    ]
    raw_edges = [("repo:a.py:func_a", "repo:b.py:func_b", "calls")]
    result = build_graph(symbols, raw_edges)
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert result.edges[0].relation_type == "calls"


def test_build_graph_filters_invalid_edges():
    symbols = [
        {"symbol_id": "repo:a.py:func_a", "name": "func_a", "type": "function", "file_path": "a.py", "repo": "repo"},
        {"symbol_id": "repo:b.py:func_b", "name": "func_b", "type": "function", "file_path": "b.py", "repo": "repo"},
    ]
    raw_edges = [
        ("repo:a.py:func_a", "repo:b.py:func_b", "calls"),
        ("repo:a.py:func_a", "repo:nonexistent.py:ghost", "calls"),
    ]
    result = build_graph(symbols, raw_edges)
    assert len(result.edges) == 1
    assert result.edges[0].to_symbol == "repo:b.py:func_b"


def test_build_graph_empty():
    result = build_graph([], [])
    assert result.nodes == []
    assert result.edges == []


def test_build_graph_multiple_edges():
    symbols = [
        {"symbol_id": "repo:a.py:A", "name": "A", "type": "class", "file_path": "a.py", "repo": "repo"},
        {"symbol_id": "repo:b.py:B", "name": "B", "type": "class", "file_path": "b.py", "repo": "repo"},
        {"symbol_id": "repo:c.py:C", "name": "C", "type": "class", "file_path": "c.py", "repo": "repo"},
    ]
    raw_edges = [
        ("repo:a.py:A", "repo:b.py:B", "calls"),
        ("repo:b.py:B", "repo:c.py:C", "calls"),
        ("repo:a.py:A", "repo:c.py:C", "imports"),
    ]
    result = build_graph(symbols, raw_edges)
    assert len(result.edges) == 3
    relation_types = {edge.relation_type for edge in result.edges}
    assert "calls" in relation_types
    assert "imports" in relation_types


def test_build_graph_preserves_node_metadata():
    symbols = [
        {
            "symbol_id": "myrepo:src/utils.py:helper_func",
            "name": "helper_func",
            "type": "function",
            "file_path": "src/utils.py",
            "repo": "myrepo",
        }
    ]
    result = build_graph(symbols, [])
    assert len(result.nodes) == 1
    node = result.nodes[0]
    assert node.symbol_id == "myrepo:src/utils.py:helper_func"
    assert node.name == "helper_func"
    assert node.type == "function"
    assert node.file_path == "src/utils.py"
    assert node.repo == "myrepo"


def test_graph_build_result_dataclass():
    nodes = [
        GraphNode(symbol_id="repo:a.py:A", name="A", type="class", file_path="a.py", repo="repo")
    ]
    edges = [
        GraphEdge(from_symbol="repo:a.py:A", to_symbol="repo:b.py:B", relation_type="inherits")
    ]
    result = GraphBuildResult(nodes=nodes, edges=edges)
    assert result.nodes == nodes
    assert result.edges == edges
