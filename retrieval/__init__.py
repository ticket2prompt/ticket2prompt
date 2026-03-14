"""Retrieval pipeline shared data types."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class TicketInput:
    """Input ticket data for retrieval."""
    title: str
    description: str
    acceptance_criteria: str = ""
    comments: List[str] = field(default_factory=list)
    repo: str = ""
    module: str = ""


@dataclass
class SymbolMatch:
    """A symbol matched by a retrieval source."""
    symbol_id: str
    name: str
    type: str
    file_path: str
    repo: str
    start_line: int
    end_line: int
    score: float
    source: str = ""  # "vector", "keyword", "graph"
    module: str = ""


@dataclass
class FileCandidate:
    """A ranked file with aggregated scores."""
    file_path: str
    repo: str
    symbols: List[SymbolMatch] = field(default_factory=list)
    final_score: float = 0.0
    semantic_score: float = 0.0
    graph_score: float = 0.0
    keyword_score: float = 0.0
    git_recency_score: float = 0.0
    symbol_density_score: float = 0.0


@dataclass
class RetrievalResult:
    """Full result of the retrieval pipeline."""
    ranked_files: List[FileCandidate] = field(default_factory=list)
    ranked_symbols: List[SymbolMatch] = field(default_factory=list)
    query_count: int = 0
    total_candidates: int = 0
