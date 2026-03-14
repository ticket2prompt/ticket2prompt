"""Evaluation framework shared data types."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class EvaluationResult:
    """Result of evaluating retrieval quality against ground truth."""
    precision: float
    recall: float
    top_3_accuracy: float
    top_5_accuracy: float
    top_10_accuracy: float
    retrieved_files: List[str]
    expected_files: List[str]
    symbol_recall: float
