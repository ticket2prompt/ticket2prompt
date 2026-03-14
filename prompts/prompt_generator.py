"""Assemble final prompts from compressed context."""

from typing import Dict, List, Optional

from prompts import GeneratedPrompt
from prompts.context_compression import (
    DEFAULT_TOKEN_BUDGET,
    compress_context,
    estimate_tokens,
)
from prompts.prompt_templates import assemble_prompt
from retrieval import FileCandidate, TicketInput


def generate_prompt(
    ticket: TicketInput,
    ranked_files: Optional[List[FileCandidate]],
    file_contents: Dict[str, str],
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> GeneratedPrompt:
    """Generate a prompt from a ticket and ranked file candidates.

    Compresses context to fit within the token budget. If the assembled
    prompt exceeds the budget, retries once with a reduced budget (80%).

    Raises ValueError if the ticket title is empty.
    """
    if not ticket.title or not ticket.title.strip():
        raise ValueError("Ticket title is required")

    if ranked_files is None:
        ranked_files = []

    compressed = compress_context(ranked_files, file_contents, token_budget)
    prompt_text = assemble_prompt(ticket, compressed, ticket.repo)
    token_count = estimate_tokens(prompt_text)

    if token_count > token_budget:
        reduced_budget = int(token_budget * 0.8)
        compressed = compress_context(ranked_files, file_contents, reduced_budget)
        prompt_text = assemble_prompt(ticket, compressed, ticket.repo)
        token_count = estimate_tokens(prompt_text)

    files_referenced = list({s.file_path for s in compressed.snippets})
    symbols_referenced = list({s.symbol_name for s in compressed.snippets})

    return GeneratedPrompt(
        prompt_text=prompt_text,
        token_count=token_count,
        files_referenced=files_referenced,
        symbols_referenced=symbols_referenced,
    )


def generate_prompt_from_retrieval(
    ticket: TicketInput,
    retrieval_result,
    postgres,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> GeneratedPrompt:
    """Generate a prompt by loading file contents from postgres.

    Extracts unique file paths from retrieval_result.ranked_files, queries
    postgres for each file's content, and delegates to generate_prompt.
    Files where postgres returns None are skipped.
    """
    ranked_files = retrieval_result.ranked_files

    seen_paths: set = set()
    file_contents: Dict[str, str] = {}

    for file_candidate in ranked_files:
        path = file_candidate.file_path
        if path in seen_paths:
            continue
        seen_paths.add(path)

        content = postgres.get_file_content(path, ticket.repo)
        if content is not None:
            file_contents[path] = content

    return generate_prompt(ticket, ranked_files, file_contents, token_budget=token_budget)
