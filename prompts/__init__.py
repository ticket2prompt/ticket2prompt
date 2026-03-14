"""Prompt generation shared data types."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CodeSnippet:
    """A code snippet extracted from a file."""
    file_path: str
    symbol_name: str
    symbol_type: str
    start_line: int
    end_line: int
    content: str
    token_count: int = 0


@dataclass
class CompressedContext:
    """Context compressed to fit within a token budget."""
    snippets: List[CodeSnippet] = field(default_factory=list)
    total_tokens: int = 0
    budget: int = 0
    files_included: int = 0
    symbols_included: int = 0


@dataclass
class GeneratedPrompt:
    """A fully assembled prompt ready for Cursor."""
    prompt_text: str = ""
    token_count: int = 0
    files_referenced: List[str] = field(default_factory=list)
    symbols_referenced: List[str] = field(default_factory=list)
