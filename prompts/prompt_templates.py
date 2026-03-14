"""Prompt templates for Cursor."""

from typing import List

from prompts import CodeSnippet, CompressedContext
from retrieval import TicketInput


def format_task_section(ticket: TicketInput) -> str:
    """Format a '## Task' section from the ticket."""
    lines = [
        "## Task",
        "",
        f"**Title:** {ticket.title}",
        "",
        f"**Description:** {ticket.description}",
    ]

    if ticket.acceptance_criteria:
        lines += [
            "",
            "**Acceptance Criteria:**",
            ticket.acceptance_criteria,
        ]

    if ticket.comments:
        lines += ["", "**Comments:**"]
        for comment in ticket.comments:
            lines.append(f"- {comment}")

    return "\n".join(lines)


def format_repo_context_section(repo: str) -> str:
    """Format a '## Repository Context' section."""
    return "\n".join([
        "## Repository Context",
        "",
        f"**Repository:** {repo}",
    ])


def format_relevant_files_section(file_paths: List[str]) -> str:
    """Format a '## Relevant Files' section."""
    if not file_paths:
        return "\n".join([
            "## Relevant Files",
            "",
            "No files identified.",
        ])

    lines = ["## Relevant Files", ""]
    for path in file_paths:
        lines.append(f"- {path}")
    return "\n".join(lines)


def format_code_snippets_section(snippets: List[CodeSnippet]) -> str:
    """Format a '## Code Snippets' section."""
    if not snippets:
        return "\n".join([
            "## Code Snippets",
            "",
            "No code snippets available.",
        ])

    lines = ["## Code Snippets"]
    for snippet in snippets:
        lines += [
            "",
            f"**{snippet.file_path}** — `{snippet.symbol_name}` ({snippet.symbol_type})"
            f" lines {snippet.start_line}–{snippet.end_line}",
            "",
            "```",
            snippet.content,
            "```",
        ]
    return "\n".join(lines)


def format_implementation_instructions_section(ticket: TicketInput) -> str:
    """Format a '## Implementation Instructions' section."""
    lines = [
        "## Implementation Instructions",
        "",
        "- Make changes to the files listed above",
        "- Follow existing code patterns",
    ]

    if ticket.acceptance_criteria:
        lines.append("- Ensure changes satisfy the acceptance criteria")

    return "\n".join(lines)


def format_constraints_section() -> str:
    """Format a '## Constraints' section with standard constraints."""
    return "\n".join([
        "## Constraints",
        "",
        "- Minimize changes to existing code",
        "- Maintain backward compatibility",
        "- Follow existing naming conventions",
        "- Add appropriate error handling",
    ])


def format_expected_behavior_section(ticket: TicketInput) -> str:
    """Format a '## Expected Behavior' section."""
    return "\n".join([
        "## Expected Behavior",
        "",
        f"The changes should accomplish: **{ticket.title}**",
        "",
        ticket.description,
    ])


def assemble_prompt(
    ticket: TicketInput,
    compressed_context: CompressedContext,
    repo: str,
) -> str:
    """Assemble all sections into a single prompt string."""
    # Deduplicate file paths while preserving order
    seen: set = set()
    unique_file_paths: List[str] = []
    for snippet in compressed_context.snippets:
        if snippet.file_path not in seen:
            seen.add(snippet.file_path)
            unique_file_paths.append(snippet.file_path)

    sections = [
        format_task_section(ticket),
        format_repo_context_section(repo),
        format_relevant_files_section(unique_file_paths),
        format_code_snippets_section(compressed_context.snippets),
        format_implementation_instructions_section(ticket),
        format_constraints_section(),
        format_expected_behavior_section(ticket),
    ]

    return "\n\n".join(sections)
