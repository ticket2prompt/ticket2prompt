"""Extract symbols from source code using Tree-sitter."""

import hashlib
import logging
from dataclasses import dataclass, field

import tree_sitter
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)

_warned_languages: set[str] = set()


@dataclass
class Symbol:
    """A code symbol extracted from source."""
    symbol_id: str
    name: str
    type: str  # "function", "class", "method"
    file_path: str
    repo: str
    start_line: int
    end_line: int
    language: str
    source: str


@dataclass
class ExtractionResult:
    """Result of symbol extraction from a file."""
    symbols: list[Symbol] = field(default_factory=list)
    edges: list[tuple[str, str, str]] = field(default_factory=list)  # (from_id, to_id, relation_type)


def generate_symbol_id(repo: str, file_path: str, name: str, type: str) -> str:
    """Generate a deterministic symbol ID."""
    key = f"{repo}:{file_path}:{name}:{type}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _get_python_language() -> Language:
    """Get the Python tree-sitter language."""
    try:
        import tree_sitter_python
        return Language(tree_sitter_python.language())
    except ImportError:
        raise RuntimeError("tree-sitter-python not installed. Run: pip install tree-sitter-python")


def _get_javascript_language() -> Language:
    """Get the JavaScript tree-sitter language."""
    try:
        import tree_sitter_javascript
        return Language(tree_sitter_javascript.language())
    except ImportError:
        raise RuntimeError("tree-sitter-javascript not installed. Run: pip install tree-sitter-javascript")


def _get_typescript_language() -> Language:
    """Get the TypeScript tree-sitter language."""
    try:
        import tree_sitter_typescript
        return Language(tree_sitter_typescript.language_typescript())
    except ImportError:
        raise RuntimeError("tree-sitter-typescript not installed. Run: pip install tree-sitter-typescript")


def _get_tsx_language() -> Language:
    """Get the TSX tree-sitter language."""
    try:
        import tree_sitter_typescript
        return Language(tree_sitter_typescript.language_tsx())
    except ImportError:
        raise RuntimeError("tree-sitter-typescript not installed. Run: pip install tree-sitter-typescript")


_LANGUAGE_GETTERS = {
    "python": _get_python_language,
    "javascript": _get_javascript_language,
    "typescript": _get_typescript_language,
    "tsx": _get_tsx_language,
}


def _get_node_text(node: tree_sitter.Node, source_bytes: bytes) -> str:
    """Extract text from a tree-sitter node."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8")


def extract_symbols(
    file_path: str,
    source_code: str,
    repo: str,
    language: str = "python",
) -> ExtractionResult:
    """Parse source code and extract symbols.

    Currently only supports Python.
    """
    if not source_code.strip():
        return ExtractionResult()

    getter = _LANGUAGE_GETTERS.get(language)
    if getter is None:
        if language not in _warned_languages:
            logger.warning("Language %s not yet supported, skipping", language)
            _warned_languages.add(language)
        return ExtractionResult()

    try:
        lang = getter()
    except RuntimeError:
        if language not in _warned_languages:
            logger.warning("Tree-sitter grammar for %s not installed, skipping", language)
            _warned_languages.add(language)
        return ExtractionResult()

    parser = Parser(lang)

    source_bytes = source_code.encode("utf-8")
    tree = parser.parse(source_bytes)

    symbols: list[Symbol] = []
    edges: list[tuple[str, str, str]] = []

    if language == "python":
        _extract_from_node(
            tree.root_node, source_bytes, file_path, repo, language,
            symbols, edges, parent_class=None,
        )
    else:
        _extract_js_ts_from_node(
            tree.root_node, source_bytes, file_path, repo, language,
            symbols, edges, parent_class=None,
        )

    return ExtractionResult(symbols=symbols, edges=edges)


def _extract_from_node(
    node: tree_sitter.Node,
    source_bytes: bytes,
    file_path: str,
    repo: str,
    language: str,
    symbols: list[Symbol],
    edges: list[tuple[str, str, str]],
    parent_class: str | None = None,
) -> None:
    """Recursively extract symbols from AST nodes."""
    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = _get_node_text(name_node, source_bytes)
            sym_type = "method" if parent_class else "function"
            sym_id = generate_symbol_id(repo, file_path, name, sym_type)
            source = _get_node_text(node, source_bytes)

            symbols.append(Symbol(
                symbol_id=sym_id,
                name=name,
                type=sym_type,
                file_path=file_path,
                repo=repo,
                start_line=node.start_point[0] + 1,  # 1-indexed
                end_line=node.end_point[0] + 1,
                language=language,
                source=source,
            ))

            _extract_calls(node, source_bytes, repo, file_path, sym_id, symbols, edges)

    elif node.type == "class_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            class_name = _get_node_text(name_node, source_bytes)
            sym_id = generate_symbol_id(repo, file_path, class_name, "class")
            source = _get_node_text(node, source_bytes)

            symbols.append(Symbol(
                symbol_id=sym_id,
                name=class_name,
                type="class",
                file_path=file_path,
                repo=repo,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                source=source,
            ))

            # Recurse into class body with class context
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    _extract_from_node(
                        child, source_bytes, file_path, repo, language,
                        symbols, edges, parent_class=class_name,
                    )
            return  # Don't recurse again below

    # Default: recurse into children
    for child in node.children:
        _extract_from_node(
            child, source_bytes, file_path, repo, language,
            symbols, edges, parent_class=parent_class,
        )


def _extract_js_ts_from_node(
    node: tree_sitter.Node,
    source_bytes: bytes,
    file_path: str,
    repo: str,
    language: str,
    symbols: list[Symbol],
    edges: list[tuple[str, str, str]],
    parent_class: str | None = None,
) -> None:
    """Recursively extract symbols from JavaScript/TypeScript AST nodes."""
    if node.type == "function_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = _get_node_text(name_node, source_bytes)
            sym_id = generate_symbol_id(repo, file_path, name, "function")
            source = _get_node_text(node, source_bytes)
            symbols.append(Symbol(
                symbol_id=sym_id, name=name, type="function",
                file_path=file_path, repo=repo,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                language=language, source=source,
            ))
            _extract_js_calls(node, source_bytes, repo, file_path, sym_id, edges)

    elif node.type == "class_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            class_name = _get_node_text(name_node, source_bytes)
            sym_id = generate_symbol_id(repo, file_path, class_name, "class")
            source = _get_node_text(node, source_bytes)
            symbols.append(Symbol(
                symbol_id=sym_id, name=class_name, type="class",
                file_path=file_path, repo=repo,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                language=language, source=source,
            ))
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    _extract_js_ts_from_node(
                        child, source_bytes, file_path, repo, language,
                        symbols, edges, parent_class=class_name,
                    )
            return

    elif node.type == "method_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = _get_node_text(name_node, source_bytes)
            sym_id = generate_symbol_id(repo, file_path, name, "method")
            source = _get_node_text(node, source_bytes)
            symbols.append(Symbol(
                symbol_id=sym_id, name=name, type="method",
                file_path=file_path, repo=repo,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                language=language, source=source,
            ))
            _extract_js_calls(node, source_bytes, repo, file_path, sym_id, edges)

    elif node.type in ("lexical_declaration", "variable_declaration"):
        # Handle: const foo = () => {} or const foo = function() {}
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node and value_node and value_node.type in ("arrow_function", "function"):
                    name = _get_node_text(name_node, source_bytes)
                    sym_id = generate_symbol_id(repo, file_path, name, "function")
                    source = _get_node_text(node, source_bytes)
                    symbols.append(Symbol(
                        symbol_id=sym_id, name=name, type="function",
                        file_path=file_path, repo=repo,
                        start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                        language=language, source=source,
                    ))
                    _extract_js_calls(value_node, source_bytes, repo, file_path, sym_id, edges)
        return

    elif node.type == "interface_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = _get_node_text(name_node, source_bytes)
            sym_id = generate_symbol_id(repo, file_path, name, "interface")
            source = _get_node_text(node, source_bytes)
            symbols.append(Symbol(
                symbol_id=sym_id, name=name, type="interface",
                file_path=file_path, repo=repo,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                language=language, source=source,
            ))
        return

    elif node.type == "type_alias_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = _get_node_text(name_node, source_bytes)
            sym_id = generate_symbol_id(repo, file_path, name, "type")
            source = _get_node_text(node, source_bytes)
            symbols.append(Symbol(
                symbol_id=sym_id, name=name, type="type",
                file_path=file_path, repo=repo,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                language=language, source=source,
            ))
        return

    # Default: recurse into children
    for child in node.children:
        _extract_js_ts_from_node(
            child, source_bytes, file_path, repo, language,
            symbols, edges, parent_class=parent_class,
        )


def _extract_js_calls(
    func_node: tree_sitter.Node,
    source_bytes: bytes,
    repo: str,
    file_path: str,
    caller_id: str,
    edges: list[tuple[str, str, str]],
) -> None:
    """Extract function call edges from JS/TS function bodies."""
    for node in _walk(func_node):
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func and func.type == "identifier":
                callee_name = _get_node_text(func, source_bytes)
                callee_id = generate_symbol_id(repo, file_path, callee_name, "function")
                edges.append((caller_id, callee_id, "calls"))


def _extract_calls(
    func_node: tree_sitter.Node,
    source_bytes: bytes,
    repo: str,
    file_path: str,
    caller_id: str,
    symbols: list[Symbol],
    edges: list[tuple[str, str, str]],
) -> None:
    """Extract function call edges from within a function body."""
    for node in _walk(func_node):
        if node.type == "call":
            func = node.child_by_field_name("function")
            if func and func.type == "identifier":
                callee_name = _get_node_text(func, source_bytes)
                callee_id = generate_symbol_id(repo, file_path, callee_name, "function")
                edges.append((caller_id, callee_id, "calls"))


def _walk(node: tree_sitter.Node):
    """Walk all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
