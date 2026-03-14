"""Compress context to fit token budgets."""

from typing import Dict, List

from prompts import CodeSnippet, CompressedContext
from retrieval import FileCandidate, SymbolMatch

DEFAULT_TOKEN_BUDGET = 5000
SAFETY_MARGIN_RATIO = 0.05


def estimate_tokens(text: str) -> int:
    """Estimate token count as character count divided by 4."""
    return len(text) // 4


def extract_snippet(file_content: str, symbol: SymbolMatch) -> CodeSnippet:
    """Extract lines start_line to end_line (1-indexed) from file_content.

    Clamps out-of-range line numbers to valid bounds.
    """
    lines = file_content.splitlines()
    total_lines = len(lines)

    # Clamp start and end to valid 1-indexed range
    start = max(1, min(symbol.start_line, total_lines))
    end = max(start, min(symbol.end_line, total_lines))

    # Convert to 0-indexed slice
    extracted_lines = lines[start - 1 : end]
    content = "\n".join(extracted_lines)

    return CodeSnippet(
        file_path=symbol.file_path,
        symbol_name=symbol.name,
        symbol_type=symbol.type,
        start_line=start,
        end_line=end,
        content=content,
        token_count=estimate_tokens(content),
    )


def deduplicate_snippets(snippets: List[CodeSnippet]) -> List[CodeSnippet]:
    """Remove duplicate snippets by (file_path, symbol_name, symbol_type).

    Keeps the first occurrence and preserves order.
    """
    seen: set[tuple[str, str, str]] = set()
    result: List[CodeSnippet] = []

    for snippet in snippets:
        key = (snippet.file_path, snippet.symbol_name, snippet.symbol_type)
        if key not in seen:
            seen.add(key)
            result.append(snippet)

    return result


def compress_context(
    ranked_files: List[FileCandidate],
    file_contents: Dict[str, str],
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> CompressedContext:
    """Compress ranked file candidates into a token-budgeted context.

    Iterates ranked_files in order, extracts snippets for each symbol,
    deduplicates, and greedily adds snippets until the effective budget is
    exhausted.
    """
    effective_budget = token_budget * (1 - SAFETY_MARGIN_RATIO)

    # Collect all snippets in ranked order
    all_snippets: List[CodeSnippet] = []
    for file_candidate in ranked_files:
        content = file_contents.get(file_candidate.file_path)
        if content is None:
            continue
        for symbol in file_candidate.symbols:
            snippet = extract_snippet(content, symbol)
            all_snippets.append(snippet)

    # Deduplicate preserving order
    unique_snippets = deduplicate_snippets(all_snippets)

    # Greedily fill within budget
    selected: List[CodeSnippet] = []
    total_tokens = 0

    for snippet in unique_snippets:
        if total_tokens + snippet.token_count > effective_budget:
            break
        selected.append(snippet)
        total_tokens += snippet.token_count

    files_included = len({s.file_path for s in selected})
    symbols_included = len(selected)

    return CompressedContext(
        snippets=selected,
        total_tokens=total_tokens,
        budget=token_budget,
        files_included=files_included,
        symbols_included=symbols_included,
    )
