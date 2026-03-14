"""Tests for the context_compression module."""

import pytest

from prompts import CodeSnippet, CompressedContext
from retrieval import FileCandidate, SymbolMatch
from prompts.context_compression import (
    DEFAULT_TOKEN_BUDGET,
    SAFETY_MARGIN_RATIO,
    compress_context,
    deduplicate_snippets,
    estimate_tokens,
    extract_snippet,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_symbol(
    name: str,
    file_path: str,
    start_line: int = 1,
    end_line: int = 5,
    repo: str = "my-repo",
    score: float = 0.8,
    symbol_type: str = "function",
) -> SymbolMatch:
    return SymbolMatch(
        symbol_id=f"{file_path}:{name}",
        name=name,
        type=symbol_type,
        file_path=file_path,
        repo=repo,
        start_line=start_line,
        end_line=end_line,
        score=score,
    )


def _make_file_candidate(
    file_path: str,
    symbols: list[SymbolMatch],
    repo: str = "my-repo",
    final_score: float = 0.8,
) -> FileCandidate:
    return FileCandidate(
        file_path=file_path,
        repo=repo,
        symbols=symbols,
        final_score=final_score,
    )


def _make_snippet(
    file_path: str,
    symbol_name: str,
    symbol_type: str = "function",
    token_count: int = 100,
) -> CodeSnippet:
    return CodeSnippet(
        file_path=file_path,
        symbol_name=symbol_name,
        symbol_type=symbol_type,
        start_line=1,
        end_line=5,
        content="def foo(): pass",
        token_count=token_count,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_default_token_budget():
    assert DEFAULT_TOKEN_BUDGET == 5000


def test_safety_margin_ratio():
    assert SAFETY_MARGIN_RATIO == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


def test_estimate_tokens_empty_string():
    assert estimate_tokens("") == 0


def test_estimate_tokens_short_text():
    # "Hello" = 5 chars → 5 // 4 = 1
    assert estimate_tokens("Hello") == 1


def test_estimate_tokens_exact_divisible():
    # 8 chars → 8 // 4 = 2
    assert estimate_tokens("abcdefgh") == 2


def test_estimate_tokens_longer_text():
    text = "a" * 400
    assert estimate_tokens(text) == 100


def test_estimate_tokens_truncates_remainder():
    # 13 chars → 13 // 4 = 3
    assert estimate_tokens("a" * 13) == 3


# ---------------------------------------------------------------------------
# extract_snippet
# ---------------------------------------------------------------------------


FILE_CONTENT = """\
line one
line two
line three
line four
line five
line six
line seven
"""


def test_extract_snippet_normal():
    symbol = _make_symbol("my_func", "src/foo.py", start_line=2, end_line=4)
    snippet = extract_snippet(FILE_CONTENT, symbol)

    assert snippet.file_path == "src/foo.py"
    assert snippet.symbol_name == "my_func"
    assert snippet.symbol_type == "function"
    assert snippet.start_line == 2
    assert snippet.end_line == 4
    assert "line two" in snippet.content
    assert "line three" in snippet.content
    assert "line four" in snippet.content
    assert "line one" not in snippet.content
    assert "line five" not in snippet.content
    assert snippet.token_count == estimate_tokens(snippet.content)


def test_extract_snippet_single_line():
    symbol = _make_symbol("my_func", "src/foo.py", start_line=3, end_line=3)
    snippet = extract_snippet(FILE_CONTENT, symbol)

    assert "line three" in snippet.content
    assert "line two" not in snippet.content
    assert "line four" not in snippet.content


def test_extract_snippet_first_line():
    symbol = _make_symbol("my_func", "src/foo.py", start_line=1, end_line=1)
    snippet = extract_snippet(FILE_CONTENT, symbol)

    assert "line one" in snippet.content


def test_extract_snippet_out_of_range_start_clamped():
    # start_line = 0 should clamp to 1
    symbol = _make_symbol("my_func", "src/foo.py", start_line=0, end_line=2)
    snippet = extract_snippet(FILE_CONTENT, symbol)

    assert "line one" in snippet.content
    assert "line two" in snippet.content


def test_extract_snippet_end_beyond_file_clamped():
    lines = FILE_CONTENT.splitlines()
    total_lines = len(lines)
    # end_line beyond total lines should clamp to last line
    symbol = _make_symbol("my_func", "src/foo.py", start_line=5, end_line=total_lines + 10)
    snippet = extract_snippet(FILE_CONTENT, symbol)

    assert "line five" in snippet.content
    assert "line seven" in snippet.content


def test_extract_snippet_start_beyond_file():
    lines = FILE_CONTENT.splitlines()
    total_lines = len(lines)
    # start_line beyond total_lines should still return something (clamped)
    symbol = _make_symbol("my_func", "src/foo.py", start_line=total_lines + 5, end_line=total_lines + 10)
    snippet = extract_snippet(FILE_CONTENT, symbol)

    # Content may be empty or last line — just ensure no exception and token_count is set
    assert snippet.token_count == estimate_tokens(snippet.content)


def test_extract_snippet_token_count_computed():
    symbol = _make_symbol("my_func", "src/foo.py", start_line=1, end_line=3)
    snippet = extract_snippet(FILE_CONTENT, symbol)

    expected_tokens = estimate_tokens(snippet.content)
    assert snippet.token_count == expected_tokens


# ---------------------------------------------------------------------------
# deduplicate_snippets
# ---------------------------------------------------------------------------


def test_deduplicate_snippets_empty():
    assert deduplicate_snippets([]) == []


def test_deduplicate_snippets_no_duplicates():
    snippets = [
        _make_snippet("src/a.py", "func_a"),
        _make_snippet("src/b.py", "func_b"),
    ]
    result = deduplicate_snippets(snippets)
    assert len(result) == 2


def test_deduplicate_snippets_with_duplicates_keeps_first():
    first = _make_snippet("src/a.py", "func_a", token_count=100)
    duplicate = _make_snippet("src/a.py", "func_a", token_count=999)
    third = _make_snippet("src/b.py", "func_b", token_count=50)

    result = deduplicate_snippets([first, duplicate, third])

    assert len(result) == 2
    # First occurrence is kept
    assert result[0].token_count == 100
    assert result[1].symbol_name == "func_b"


def test_deduplicate_snippets_key_is_file_symbol_type():
    # Same file and name but different type → not duplicates
    s1 = CodeSnippet(
        file_path="src/a.py", symbol_name="MyClass",
        symbol_type="class", start_line=1, end_line=5,
        content="class MyClass: pass", token_count=10,
    )
    s2 = CodeSnippet(
        file_path="src/a.py", symbol_name="MyClass",
        symbol_type="function", start_line=10, end_line=15,
        content="def MyClass(): pass", token_count=10,
    )
    result = deduplicate_snippets([s1, s2])
    assert len(result) == 2


def test_deduplicate_snippets_preserves_order():
    snippets = [
        _make_snippet("src/c.py", "func_c"),
        _make_snippet("src/a.py", "func_a"),
        _make_snippet("src/b.py", "func_b"),
        _make_snippet("src/a.py", "func_a"),  # duplicate
    ]
    result = deduplicate_snippets(snippets)
    assert len(result) == 3
    assert result[0].file_path == "src/c.py"
    assert result[1].file_path == "src/a.py"
    assert result[2].file_path == "src/b.py"


# ---------------------------------------------------------------------------
# compress_context
# ---------------------------------------------------------------------------


def test_compress_context_empty_inputs():
    result = compress_context([], {})

    assert isinstance(result, CompressedContext)
    assert result.snippets == []
    assert result.total_tokens == 0
    assert result.files_included == 0
    assert result.symbols_included == 0
    assert result.budget == DEFAULT_TOKEN_BUDGET


def test_compress_context_custom_budget_stored():
    result = compress_context([], {}, token_budget=1000)
    assert result.budget == 1000


def test_compress_context_file_not_in_contents():
    symbol = _make_symbol("func_a", "src/a.py", start_line=1, end_line=3)
    file_candidate = _make_file_candidate("src/a.py", [symbol])

    # file_contents does not contain "src/a.py"
    result = compress_context([file_candidate], {})

    assert result.snippets == []
    assert result.files_included == 0
    assert result.symbols_included == 0


def test_compress_context_single_symbol_within_budget():
    file_content = "def func_a():\n    return 1\n"
    symbol = _make_symbol("func_a", "src/a.py", start_line=1, end_line=2)
    file_candidate = _make_file_candidate("src/a.py", [symbol])

    result = compress_context(
        [file_candidate],
        {"src/a.py": file_content},
        token_budget=5000,
    )

    assert len(result.snippets) == 1
    assert result.snippets[0].symbol_name == "func_a"
    assert result.files_included == 1
    assert result.symbols_included == 1
    assert result.total_tokens > 0
    assert result.budget == 5000


def test_compress_context_multiple_files_within_budget():
    content_a = "def func_a():\n    return 1\n"
    content_b = "def func_b():\n    return 2\n"

    symbol_a = _make_symbol("func_a", "src/a.py", start_line=1, end_line=2)
    symbol_b = _make_symbol("func_b", "src/b.py", start_line=1, end_line=2)

    candidates = [
        _make_file_candidate("src/a.py", [symbol_a]),
        _make_file_candidate("src/b.py", [symbol_b]),
    ]

    result = compress_context(
        candidates,
        {"src/a.py": content_a, "src/b.py": content_b},
        token_budget=5000,
    )

    assert result.files_included == 2
    assert result.symbols_included == 2
    assert len(result.snippets) == 2


def test_compress_context_exceeds_budget_truncates():
    """When total tokens exceed the effective budget, stop adding snippets."""
    # Each line is 10 chars → ~2-3 tokens per line, ~5 per symbol over 2 lines
    # Use a very small budget to force truncation
    large_content = "\n".join(f"{'x' * 80}  # line {i}" for i in range(50))

    symbols = [
        _make_symbol(f"func_{i}", "src/big.py", start_line=i + 1, end_line=i + 5)
        for i in range(10)
    ]
    candidates = [_make_file_candidate("src/big.py", symbols)]

    # Token budget so small that only 1-2 symbols fit
    small_budget = 50
    result = compress_context(
        candidates,
        {"src/big.py": large_content},
        token_budget=small_budget,
    )

    # Should include fewer than all 10 symbols
    assert result.symbols_included < 10
    # Total tokens should not exceed the effective budget
    effective_budget = small_budget * (1 - SAFETY_MARGIN_RATIO)
    assert result.total_tokens <= effective_budget


def test_compress_context_zero_budget():
    content = "def func_a():\n    return 1\n"
    symbol = _make_symbol("func_a", "src/a.py", start_line=1, end_line=2)
    candidates = [_make_file_candidate("src/a.py", [symbol])]

    result = compress_context(candidates, {"src/a.py": content}, token_budget=0)

    # Effective budget = 0 * (1 - 0.05) = 0; nothing should fit
    assert result.snippets == []
    assert result.symbols_included == 0
    assert result.total_tokens == 0


def test_compress_context_deduplicates_symbols():
    """Symbols appearing in multiple file candidates are deduplicated."""
    content = "def func_a():\n    return 1\n"
    symbol_a1 = _make_symbol("func_a", "src/a.py", start_line=1, end_line=2)
    symbol_a2 = _make_symbol("func_a", "src/a.py", start_line=1, end_line=2)  # duplicate

    # Two candidates both pointing to the same file and symbol
    candidates = [
        _make_file_candidate("src/a.py", [symbol_a1]),
        _make_file_candidate("src/a.py", [symbol_a2]),
    ]

    result = compress_context(candidates, {"src/a.py": content}, token_budget=5000)

    assert result.symbols_included == 1
    assert len(result.snippets) == 1


def test_compress_context_total_tokens_matches_snippets():
    content_a = "def func_a():\n    return 1\n"
    content_b = "def func_b():\n    return 2\n"

    symbol_a = _make_symbol("func_a", "src/a.py", start_line=1, end_line=2)
    symbol_b = _make_symbol("func_b", "src/b.py", start_line=1, end_line=2)

    candidates = [
        _make_file_candidate("src/a.py", [symbol_a]),
        _make_file_candidate("src/b.py", [symbol_b]),
    ]

    result = compress_context(
        candidates,
        {"src/a.py": content_a, "src/b.py": content_b},
        token_budget=5000,
    )

    expected_tokens = sum(s.token_count for s in result.snippets)
    assert result.total_tokens == expected_tokens


def test_compress_context_files_included_counts_unique_files():
    content = "def func_a():\n    return 1\ndef func_b():\n    return 2\n"
    symbol_a = _make_symbol("func_a", "src/a.py", start_line=1, end_line=2)
    symbol_b = _make_symbol("func_b", "src/a.py", start_line=3, end_line=4)

    # Same file, two symbols
    candidates = [_make_file_candidate("src/a.py", [symbol_a, symbol_b])]

    result = compress_context(candidates, {"src/a.py": content}, token_budget=5000)

    assert result.files_included == 1
    assert result.symbols_included == 2


def test_compress_context_respects_ranked_file_order():
    """Symbols from the highest-ranked file should be included first."""
    content_a = "def func_a():\n    return 1\n"
    content_b = "def func_b():\n    return 2\n"

    symbol_a = _make_symbol("func_a", "src/a.py", start_line=1, end_line=2)
    symbol_b = _make_symbol("func_b", "src/b.py", start_line=1, end_line=2)

    # a.py has higher final_score and comes first
    candidates = [
        _make_file_candidate("src/a.py", [symbol_a], final_score=0.9),
        _make_file_candidate("src/b.py", [symbol_b], final_score=0.5),
    ]

    # Very small budget: fits exactly 1 symbol
    # Each content has 2 lines, ~26 chars → ~6 tokens
    result = compress_context(
        candidates,
        {"src/a.py": content_a, "src/b.py": content_b},
        token_budget=10,  # tight budget
    )

    # Only the first file's symbol should fit
    if result.symbols_included == 1:
        assert result.snippets[0].symbol_name == "func_a"
