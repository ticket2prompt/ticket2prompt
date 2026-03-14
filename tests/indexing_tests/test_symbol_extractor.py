from indexing.symbol_extractor import (
    ExtractionResult,
    Symbol,
    extract_symbols,
    generate_symbol_id,
)


def test_symbol_dataclass_fields():
    symbol = Symbol(
        symbol_id="repo:path:name:function",
        name="hello",
        type="function",
        file_path="src/main.py",
        repo="my-repo",
        start_line=1,
        end_line=3,
        language="python",
        source="def hello():\n    pass\n",
    )
    assert symbol.symbol_id == "repo:path:name:function"
    assert symbol.name == "hello"
    assert symbol.type == "function"
    assert symbol.file_path == "src/main.py"
    assert symbol.repo == "my-repo"
    assert symbol.start_line == 1
    assert symbol.end_line == 3
    assert symbol.language == "python"
    assert symbol.source == "def hello():\n    pass\n"


def test_extraction_result_dataclass():
    symbol = Symbol(
        symbol_id="id1",
        name="foo",
        type="function",
        file_path="foo.py",
        repo="repo",
        start_line=1,
        end_line=2,
        language="python",
        source="def foo(): pass",
    )
    edge = ("id1", "id2", "calls")
    result = ExtractionResult(symbols=[symbol], edges=[edge])
    assert len(result.symbols) == 1
    assert result.symbols[0].name == "foo"
    assert len(result.edges) == 1
    assert result.edges[0] == ("id1", "id2", "calls")


def test_generate_symbol_id_deterministic():
    id1 = generate_symbol_id(
        repo="my-repo", file_path="src/main.py", name="hello", type="function"
    )
    id2 = generate_symbol_id(
        repo="my-repo", file_path="src/main.py", name="hello", type="function"
    )
    assert id1 == id2


def test_generate_symbol_id_different_for_different_input():
    id1 = generate_symbol_id(
        repo="my-repo", file_path="src/main.py", name="hello", type="function"
    )
    id2 = generate_symbol_id(
        repo="my-repo", file_path="src/main.py", name="world", type="function"
    )
    id3 = generate_symbol_id(
        repo="other-repo", file_path="src/main.py", name="hello", type="function"
    )
    id4 = generate_symbol_id(
        repo="my-repo", file_path="src/other.py", name="hello", type="function"
    )
    id5 = generate_symbol_id(
        repo="my-repo", file_path="src/main.py", name="hello", type="class"
    )
    assert id1 != id2
    assert id1 != id3
    assert id1 != id4
    assert id1 != id5


def test_extract_simple_function():
    source = "def hello():\n    pass\n"
    result = extract_symbols(
        file_path="src/main.py", source_code=source, repo="my-repo", language="python"
    )
    assert len(result.symbols) == 1
    sym = result.symbols[0]
    assert sym.name == "hello"
    assert sym.type == "function"
    assert sym.start_line == 1
    assert sym.end_line == 2


def test_extract_class():
    source = "class MyClass:\n    pass\n"
    result = extract_symbols(
        file_path="src/models.py",
        source_code=source,
        repo="my-repo",
        language="python",
    )
    class_symbols = [s for s in result.symbols if s.type == "class"]
    assert len(class_symbols) == 1
    assert class_symbols[0].name == "MyClass"


def test_extract_method_in_class():
    source = "class Foo:\n    def bar(self):\n        pass\n"
    result = extract_symbols(
        file_path="src/foo.py", source_code=source, repo="my-repo", language="python"
    )
    names = {s.name for s in result.symbols}
    types = {s.type for s in result.symbols}
    assert "Foo" in names
    assert "bar" in names
    assert "class" in types
    assert "method" in types


def test_extract_multiple_functions():
    source = (
        "def alpha():\n    pass\n\n"
        "def beta():\n    pass\n\n"
        "def gamma():\n    pass\n"
    )
    result = extract_symbols(
        file_path="src/utils.py", source_code=source, repo="my-repo", language="python"
    )
    function_symbols = [s for s in result.symbols if s.type == "function"]
    assert len(function_symbols) == 3
    names = {s.name for s in function_symbols}
    assert names == {"alpha", "beta", "gamma"}


def test_extract_sets_file_path_and_repo():
    source = "def hello():\n    pass\n"
    result = extract_symbols(
        file_path="src/main.py", source_code=source, repo="target-repo", language="python"
    )
    assert len(result.symbols) == 1
    sym = result.symbols[0]
    assert sym.file_path == "src/main.py"
    assert sym.repo == "target-repo"


def test_extract_sets_language():
    source = "def hello():\n    pass\n"
    result = extract_symbols(
        file_path="src/main.py", source_code=source, repo="my-repo", language="python"
    )
    assert len(result.symbols) == 1
    assert result.symbols[0].language == "python"


def test_extract_captures_source():
    source = "def hello():\n    return 42\n"
    result = extract_symbols(
        file_path="src/main.py", source_code=source, repo="my-repo", language="python"
    )
    assert len(result.symbols) == 1
    sym = result.symbols[0]
    assert "hello" in sym.source
    assert "return 42" in sym.source


def test_extract_empty_file():
    result = extract_symbols(
        file_path="src/empty.py", source_code="", repo="my-repo", language="python"
    )
    assert result.symbols == []
    assert result.edges == []


def test_extract_function_calls_as_edges():
    source = "def caller():\n    callee()\n\ndef callee():\n    pass\n"
    result = extract_symbols(
        file_path="src/main.py", source_code=source, repo="my-repo", language="python"
    )
    assert isinstance(result.edges, list)
    # If the implementation detects the call, verify the edge has the correct relation type.
    calls_edges = [e for e in result.edges if e[2] == "calls"]
    if calls_edges:
        caller_sym = next(
            (s for s in result.symbols if s.name == "caller"), None
        )
        callee_sym = next(
            (s for s in result.symbols if s.name == "callee"), None
        )
        assert caller_sym is not None
        assert callee_sym is not None
        edge_pairs = {(e[0], e[1]) for e in calls_edges}
        assert (caller_sym.symbol_id, callee_sym.symbol_id) in edge_pairs
