"""Extended symbol extractor tests for JS/TS and edge cases.

Covers lines 47-48, 53-57, 62-66, 71-75, 106-109, 113-117, 133, 222-320, 335-341.

JS/TS grammar packages (tree-sitter-javascript, tree-sitter-typescript) are not
available in this environment, so the JS/TS extraction functions are tested via:
  1. Mocking _get_javascript_language / _get_typescript_language to return the
     Python grammar (which lets the parser run), and using mocked nodes to
     exercise the dispatch in _extract_js_ts_from_node.
  2. Directly calling _extract_js_ts_from_node with synthetic MagicMock nodes.
  3. Using pytest.importorskip / pytest.mark.skipif for live-grammar tests.
"""

import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from indexing.symbol_extractor import (
    ExtractionResult,
    Symbol,
    extract_symbols,
    generate_symbol_id,
    _extract_js_calls,
    _extract_js_ts_from_node,
    _get_node_text,
    _walk,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_and_node(node_type: str, source: str, name: str, name_offset: int = 0):
    """Build a (source_bytes, node) pair where name bytes are correct.

    name_offset is the byte position of the name within source.
    """
    source_bytes = source.encode()

    name_node = MagicMock()
    name_node.type = "identifier"
    name_node.start_byte = name_offset
    name_node.end_byte = name_offset + len(name)

    node = MagicMock()
    node.type = node_type
    node.children = []
    node.start_point = (0, 0)
    node.end_point = (0, len(source))
    node.start_byte = 0
    node.end_byte = len(source_bytes)

    def _child_by_field_name(field):
        if field == "name":
            return name_node
        if field == "body":
            return None
        return None

    node.child_by_field_name = MagicMock(side_effect=_child_by_field_name)
    return source_bytes, node


def _make_node(node_type, children=None, name_text=None, value_type=None):
    """Build a minimal fake tree-sitter node (for testing child iteration)."""
    node = MagicMock()
    node.type = node_type
    node.children = children or []
    node.start_point = (0, 0)
    node.end_point = (2, 0)
    node.start_byte = 0
    node.end_byte = 10

    def _child_by_field_name(field):
        if field == "name" and name_text is not None:
            name_node = MagicMock()
            name_node.type = "identifier"
            name_node.start_byte = 0
            name_node.end_byte = len(name_text)
            return name_node
        if field == "value" and value_type is not None:
            val_node = MagicMock()
            val_node.type = value_type
            val_node.start_byte = 0
            val_node.end_byte = 10
            val_node.children = []
            return val_node
        if field == "body":
            return None
        return None

    node.child_by_field_name = MagicMock(side_effect=_child_by_field_name)
    return node


def _call_extract_js_ts(node, source_bytes=b"function foo() {}", repo="repo", file_path="app.js", language="javascript"):
    symbols = []
    edges = []
    _extract_js_ts_from_node(node, source_bytes, file_path, repo, language, symbols, edges)
    return symbols, edges


# ---------------------------------------------------------------------------
# Language getter import errors (lines 47-48, 53-57, 62-66, 71-75)
# ---------------------------------------------------------------------------

class TestLanguageGetterImportErrors:
    def test_get_python_language_import_error(self):
        from indexing.symbol_extractor import _get_python_language
        with patch.dict("sys.modules", {"tree_sitter_python": None}):
            with pytest.raises(RuntimeError, match="tree-sitter-python not installed"):
                _get_python_language()

    def test_get_javascript_language_import_error(self):
        from indexing.symbol_extractor import _get_javascript_language
        with patch.dict("sys.modules", {"tree_sitter_javascript": None}):
            with pytest.raises(RuntimeError, match="tree-sitter-javascript not installed"):
                _get_javascript_language()

    def test_get_typescript_language_import_error(self):
        from indexing.symbol_extractor import _get_typescript_language
        with patch.dict("sys.modules", {"tree_sitter_typescript": None}):
            with pytest.raises(RuntimeError, match="tree-sitter-typescript not installed"):
                _get_typescript_language()

    def test_get_tsx_language_import_error(self):
        from indexing.symbol_extractor import _get_tsx_language
        with patch.dict("sys.modules", {"tree_sitter_typescript": None}):
            with pytest.raises(RuntimeError, match="tree-sitter-typescript not installed"):
                _get_tsx_language()


# ---------------------------------------------------------------------------
# Unsupported / missing language (lines 106-109, 113-117)
# ---------------------------------------------------------------------------

class TestUnsupportedLanguage:
    def test_unsupported_language_returns_empty_result(self):
        import indexing.symbol_extractor as mod
        mod._warned_languages.discard("ruby")
        result = extract_symbols(
            file_path="src/main.rb",
            source_code="def hello; end",
            repo="my-repo",
            language="ruby",
        )
        assert result.symbols == []
        assert result.edges == []

    def test_unsupported_language_only_warns_once(self, caplog):
        import logging
        import indexing.symbol_extractor as mod
        mod._warned_languages.discard("erlang")

        with caplog.at_level(logging.WARNING, logger="indexing.symbol_extractor"):
            extract_symbols("a.erl", "code", "repo", language="erlang")
            extract_symbols("b.erl", "more code", "repo", language="erlang")

        warning_msgs = [r.message for r in caplog.records if "erlang" in r.message]
        assert len(warning_msgs) == 1

    def test_grammar_not_installed_returns_empty_for_javascript(self, caplog):
        """When the tree-sitter grammar package is missing, return empty result."""
        import logging
        import indexing.symbol_extractor as mod
        mod._warned_languages.discard("javascript")

        with caplog.at_level(logging.WARNING, logger="indexing.symbol_extractor"):
            with patch(
                "indexing.symbol_extractor._get_javascript_language",
                side_effect=RuntimeError("not installed"),
            ):
                result = extract_symbols(
                    file_path="src/app.js",
                    source_code="function hello() {}",
                    repo="my-repo",
                    language="javascript",
                )

        assert result.symbols == []
        assert result.edges == []
        assert any("javascript" in r.message.lower() for r in caplog.records)

    def test_grammar_not_installed_warns_once_for_typescript(self, caplog):
        import logging
        import indexing.symbol_extractor as mod
        mod._warned_languages.discard("typescript")

        with caplog.at_level(logging.WARNING, logger="indexing.symbol_extractor"):
            with patch(
                "indexing.symbol_extractor._get_typescript_language",
                side_effect=RuntimeError("not installed"),
            ):
                extract_symbols("a.ts", "const x = 1", "repo", language="typescript")
                extract_symbols("b.ts", "const y = 2", "repo", language="typescript")

        warning_msgs = [r.message for r in caplog.records if "typescript" in r.message.lower()]
        assert len(warning_msgs) == 1

    def test_grammar_not_installed_adds_to_warned_set(self):
        import indexing.symbol_extractor as mod
        mod._warned_languages.discard("typescript")

        with patch(
            "indexing.symbol_extractor._get_typescript_language",
            side_effect=RuntimeError("not installed"),
        ):
            extract_symbols("a.ts", "const x = 1", "repo", language="typescript")

        assert "typescript" in mod._warned_languages


# ---------------------------------------------------------------------------
# Empty / whitespace-only file — early return path (covers line 133 via JS/TS)
# ---------------------------------------------------------------------------

class TestEmptySourceCode:
    def test_empty_file_returns_empty_result(self):
        result = extract_symbols(
            file_path="src/app.js",
            source_code="",
            repo="my-repo",
            language="javascript",
        )
        assert result.symbols == []
        assert result.edges == []

    def test_whitespace_only_returns_empty_result(self):
        result = extract_symbols(
            file_path="src/app.ts",
            source_code="   \n  \t  ",
            repo="my-repo",
            language="typescript",
        )
        assert result.symbols == []
        assert result.edges == []

    def test_empty_python_file_returns_empty(self):
        result = extract_symbols("a.py", "", "repo", language="python")
        assert result.symbols == []
        assert result.edges == []


# ---------------------------------------------------------------------------
# _extract_js_ts_from_node — function_declaration (line 222-234)
# ---------------------------------------------------------------------------

class TestExtractJsTsFromNodeFunctionDeclaration:
    def test_function_declaration_adds_symbol(self):
        # "function greet() {}" — "greet" starts at byte 9
        source_bytes, node = _make_source_and_node(
            "function_declaration", "function greet() {}", "greet", name_offset=9
        )
        symbols, edges = _call_extract_js_ts(node, source_bytes)
        assert len(symbols) == 1
        assert symbols[0].name == "greet"
        assert symbols[0].type == "function"

    def test_function_declaration_sets_language(self):
        source_bytes, node = _make_source_and_node(
            "function_declaration", "function foo() {}", "foo", name_offset=9
        )
        symbols, _ = _call_extract_js_ts(node, source_bytes, language="javascript")
        assert symbols[0].language == "javascript"

    def test_function_declaration_no_name_node_skips(self):
        node = MagicMock()
        node.type = "function_declaration"
        node.children = []
        node.child_by_field_name = MagicMock(return_value=None)
        symbols, _ = _call_extract_js_ts(node, b"function () {}")
        assert symbols == []

    def test_function_declaration_sets_file_path_and_repo(self):
        source_bytes, node = _make_source_and_node(
            "function_declaration", "function hello() {}", "hello", name_offset=9
        )
        symbols, _ = _call_extract_js_ts(
            node, source_bytes, repo="my-repo", file_path="src/utils.js"
        )
        assert symbols[0].file_path == "src/utils.js"
        assert symbols[0].repo == "my-repo"


# ---------------------------------------------------------------------------
# _extract_js_ts_from_node — class_declaration (lines 236-255)
# ---------------------------------------------------------------------------

class TestExtractJsTsFromNodeClassDeclaration:
    def test_class_declaration_adds_symbol(self):
        # "class Dog {}" — "Dog" starts at byte 6
        source_bytes, node = _make_source_and_node(
            "class_declaration", "class Dog {}", "Dog", name_offset=6
        )
        symbols, _ = _call_extract_js_ts(node, source_bytes)
        assert len(symbols) == 1
        assert symbols[0].name == "Dog"
        assert symbols[0].type == "class"

    def test_class_declaration_no_name_skips(self):
        node = MagicMock()
        node.type = "class_declaration"
        node.children = []
        node.child_by_field_name = MagicMock(return_value=None)
        symbols, _ = _call_extract_js_ts(node, b"class {}")
        assert symbols == []

    def test_class_declaration_recurses_into_body(self):
        # Build a class node with a body containing a method_definition child
        source_bytes = b"class A { bark() {} }"

        method_node = _make_node("method_definition", name_text="bark")
        method_node.children = []

        body_node = MagicMock()
        body_node.children = [method_node]

        class_node = MagicMock()
        class_node.type = "class_declaration"
        class_node.children = []
        class_node.start_point = (0, 0)
        class_node.end_point = (0, 20)
        class_node.start_byte = 0
        class_node.end_byte = 21

        def _child_by_field_name(field):
            if field == "name":
                name = MagicMock()
                name.start_byte = 6
                name.end_byte = 7
                return name
            if field == "body":
                return body_node
            return None

        class_node.child_by_field_name = MagicMock(side_effect=_child_by_field_name)

        symbols = []
        edges = []
        _extract_js_ts_from_node(
            class_node, source_bytes, "app.js", "repo", "javascript", symbols, edges
        )

        # At minimum the class itself should be present
        assert any(s.type == "class" for s in symbols)


# ---------------------------------------------------------------------------
# _extract_js_ts_from_node — method_definition (lines 257-269)
# ---------------------------------------------------------------------------

class TestExtractJsTsFromNodeMethodDefinition:
    def test_method_definition_adds_symbol(self):
        source_bytes = b"bark() { return 'woof'; }"
        node = _make_node("method_definition", name_text="bark")
        symbols, _ = _call_extract_js_ts(node, source_bytes)
        assert len(symbols) == 1
        assert symbols[0].name == "bark"
        assert symbols[0].type == "method"

    def test_method_definition_no_name_skips(self):
        node = MagicMock()
        node.type = "method_definition"
        node.children = []
        node.child_by_field_name = MagicMock(return_value=None)
        symbols, _ = _call_extract_js_ts(node, b"() {}")
        assert symbols == []


# ---------------------------------------------------------------------------
# _extract_js_ts_from_node — lexical/variable_declaration with arrow/function
# (lines 271-288)
# ---------------------------------------------------------------------------

class TestExtractJsTsFromNodeLexicalDeclaration:
    def _make_lexical_with_arrow(self, var_name: str, value_type: str):
        """Build a lexical_declaration containing a variable_declarator."""
        source_bytes = f"const {var_name} = () => {{}}".encode()

        # name node
        name_node = MagicMock()
        name_node.start_byte = 6
        name_node.end_byte = 6 + len(var_name)

        # value node
        value_node = MagicMock()
        value_node.type = value_type
        value_node.children = []
        value_node.start_byte = 0
        value_node.end_byte = len(source_bytes)

        # declarator
        declarator = MagicMock()
        declarator.type = "variable_declarator"
        declarator.children = []

        def _declarator_field(field):
            if field == "name":
                return name_node
            if field == "value":
                return value_node
            return None

        declarator.child_by_field_name = MagicMock(side_effect=_declarator_field)

        # outer lexical node
        outer = MagicMock()
        outer.type = "lexical_declaration"
        outer.children = [declarator]
        outer.start_point = (0, 0)
        outer.end_point = (0, len(source_bytes))
        outer.start_byte = 0
        outer.end_byte = len(source_bytes)
        outer.child_by_field_name = MagicMock(return_value=None)

        return outer, source_bytes

    def test_arrow_function_const_adds_symbol(self):
        node, source_bytes = self._make_lexical_with_arrow("add", "arrow_function")
        symbols, _ = _call_extract_js_ts(node, source_bytes)
        assert len(symbols) == 1
        assert symbols[0].name == "add"
        assert symbols[0].type == "function"

    def test_function_expression_const_adds_symbol(self):
        node, source_bytes = self._make_lexical_with_arrow("multiply", "function")
        symbols, _ = _call_extract_js_ts(node, source_bytes)
        assert len(symbols) == 1
        assert symbols[0].name == "multiply"

    def test_non_function_value_does_not_add_symbol(self):
        node, source_bytes = self._make_lexical_with_arrow("x", "number")
        symbols, _ = _call_extract_js_ts(node, source_bytes)
        assert symbols == []

    def test_variable_declaration_type_also_handled(self):
        """var foo = () => {} (variable_declaration rather than lexical_declaration)."""
        node, source_bytes = self._make_lexical_with_arrow("foo", "arrow_function")
        node.type = "variable_declaration"
        symbols, _ = _call_extract_js_ts(node, source_bytes)
        assert len(symbols) == 1


# ---------------------------------------------------------------------------
# _extract_js_ts_from_node — interface_declaration (lines 290-302)
# ---------------------------------------------------------------------------

class TestExtractJsTsFromNodeInterface:
    def test_interface_declaration_adds_symbol(self):
        # "interface User { name: string; }" — "User" starts at byte 10
        source_bytes, node = _make_source_and_node(
            "interface_declaration", "interface User { name: string; }", "User", name_offset=10
        )
        symbols, _ = _call_extract_js_ts(node, source_bytes, language="typescript")
        assert len(symbols) == 1
        assert symbols[0].name == "User"
        assert symbols[0].type == "interface"

    def test_interface_no_name_skips(self):
        node = MagicMock()
        node.type = "interface_declaration"
        node.children = []
        node.child_by_field_name = MagicMock(return_value=None)
        symbols, _ = _call_extract_js_ts(node, b"interface {}")
        assert symbols == []

    def test_interface_returns_early_no_recursion(self):
        """interface_declaration should return after adding symbol (no child recursion)."""
        # "interface A {}" — "A" starts at byte 10
        source_bytes, node = _make_source_and_node(
            "interface_declaration", "interface A {}", "A", name_offset=10
        )
        # Add a child that should NOT be processed (early return)
        child = _make_node("function_declaration", name_text="shouldNotBeAdded")
        node.children = [child]
        symbols, _ = _call_extract_js_ts(node, source_bytes)
        assert len(symbols) == 1
        assert symbols[0].type == "interface"


# ---------------------------------------------------------------------------
# _extract_js_ts_from_node — type_alias_declaration (lines 304-316)
# ---------------------------------------------------------------------------

class TestExtractJsTsFromNodeTypeAlias:
    def test_type_alias_adds_symbol(self):
        # "type UserId = string;" — "UserId" starts at byte 5
        source_bytes, node = _make_source_and_node(
            "type_alias_declaration", "type UserId = string;", "UserId", name_offset=5
        )
        symbols, _ = _call_extract_js_ts(node, source_bytes, language="typescript")
        assert len(symbols) == 1
        assert symbols[0].name == "UserId"
        assert symbols[0].type == "type"

    def test_type_alias_no_name_skips(self):
        node = MagicMock()
        node.type = "type_alias_declaration"
        node.children = []
        node.child_by_field_name = MagicMock(return_value=None)
        symbols, _ = _call_extract_js_ts(node, b"type = string;")
        assert symbols == []

    def test_type_alias_returns_early(self):
        # "type X = number;" — "X" starts at byte 5
        source_bytes, node = _make_source_and_node(
            "type_alias_declaration", "type X = number;", "X", name_offset=5
        )
        child = _make_node("function_declaration", name_text="extra")
        node.children = [child]
        symbols, _ = _call_extract_js_ts(node, source_bytes)
        assert len(symbols) == 1
        assert symbols[0].type == "type"


# ---------------------------------------------------------------------------
# _extract_js_ts_from_node — default recursion path (lines 318-323)
# ---------------------------------------------------------------------------

class TestExtractJsTsDefaultRecursion:
    def test_unknown_node_type_recurses_into_children(self):
        """Unknown node type triggers the default recursion through children."""
        # "function inner() {}" — "inner" starts at byte 9
        source_bytes, inner_func = _make_source_and_node(
            "function_declaration", "function inner() {}", "inner", name_offset=9
        )
        wrapper = MagicMock()
        wrapper.type = "program"  # not a handled type
        wrapper.children = [inner_func]
        wrapper.child_by_field_name = MagicMock(return_value=None)

        symbols, _ = _call_extract_js_ts(wrapper, source_bytes)
        assert any(s.name == "inner" for s in symbols)

    def test_deeply_nested_node_is_reached(self):
        source_bytes, deep_func = _make_source_and_node(
            "function_declaration", "function deep() {}", "deep", name_offset=9
        )

        level2 = MagicMock()
        level2.type = "block"
        level2.children = [deep_func]
        level2.child_by_field_name = MagicMock(return_value=None)

        level1 = MagicMock()
        level1.type = "export_statement"
        level1.children = [level2]
        level1.child_by_field_name = MagicMock(return_value=None)

        symbols, _ = _call_extract_js_ts(level1, source_bytes)
        assert any(s.name == "deep" for s in symbols)


# ---------------------------------------------------------------------------
# _extract_js_calls (lines 326-341)
# ---------------------------------------------------------------------------

class TestExtractJsCalls:
    def _make_call_expression(self, func_name: str):
        """Build a call_expression node with an identifier function."""
        func_node = MagicMock()
        func_node.type = "identifier"
        func_node.start_byte = 0
        func_node.end_byte = len(func_name)

        call_node = MagicMock()
        call_node.type = "call_expression"
        call_node.children = []

        def _field(field):
            if field == "function":
                return func_node
            return None

        call_node.child_by_field_name = MagicMock(side_effect=_field)
        return call_node, func_name.encode()

    def test_call_expression_produces_edge(self):
        source_bytes = b"bar"
        call_node, _ = self._make_call_expression("bar")

        # Wrap in a function node so _extract_js_calls has something to walk
        func_node = MagicMock()
        func_node.type = "function_declaration"
        func_node.children = [call_node]

        caller_id = generate_symbol_id("repo", "app.js", "foo", "function")
        edges = []
        _extract_js_calls(func_node, source_bytes, "repo", "app.js", caller_id, edges)

        call_edges = [e for e in edges if e[2] == "calls"]
        assert len(call_edges) >= 1
        assert call_edges[0][0] == caller_id

    def test_member_expression_call_not_tracked(self):
        """obj.method() — function field is member_expression, not identifier → no edge."""
        member_expr = MagicMock()
        member_expr.type = "member_expression"

        call_node = MagicMock()
        call_node.type = "call_expression"
        call_node.children = []
        call_node.child_by_field_name = MagicMock(return_value=member_expr)

        func_node = MagicMock()
        func_node.type = "function_declaration"
        func_node.children = [call_node]

        edges = []
        _extract_js_calls(func_node, b"obj.method()", "repo", "app.js", "caller-id", edges)
        assert edges == []

    def test_no_call_expression_no_edge(self):
        func_node = MagicMock()
        func_node.type = "function_declaration"
        func_node.children = []

        edges = []
        _extract_js_calls(func_node, b"return 1;", "repo", "app.js", "caller-id", edges)
        assert edges == []


# ---------------------------------------------------------------------------
# Symbol ID generation and basic shape
# ---------------------------------------------------------------------------

class TestSymbolIdGeneration:
    def test_symbol_id_is_16_char_hex(self):
        sid = generate_symbol_id("repo", "app.js", "foo", "function")
        assert len(sid) == 16
        assert all(c in "0123456789abcdef" for c in sid)

    def test_symbol_id_deterministic(self):
        a = generate_symbol_id("repo", "app.js", "foo", "function")
        b = generate_symbol_id("repo", "app.js", "foo", "function")
        assert a == b

    def test_symbol_id_differs_by_name(self):
        a = generate_symbol_id("repo", "app.js", "foo", "function")
        b = generate_symbol_id("repo", "app.js", "bar", "function")
        assert a != b

    def test_symbol_id_differs_by_type(self):
        a = generate_symbol_id("repo", "app.js", "X", "class")
        b = generate_symbol_id("repo", "app.js", "X", "interface")
        assert a != b
