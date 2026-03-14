"""Retrieval quality metrics.

Computes precision, recall, and Top-K accuracy for evaluating
how well the retrieval pipeline finds the correct files and symbols.
"""

from typing import List

from evaluation import EvaluationResult
from retrieval import RetrievalResult


def precision(retrieved_files: List[str], expected_files: List[str]) -> float:
    """Fraction of retrieved files that are relevant.

    Returns 0.0 if either list is empty.
    """
    if not retrieved_files or not expected_files:
        return 0.0
    retrieved_set = set(retrieved_files)
    expected_set = set(expected_files)
    return len(retrieved_set & expected_set) / len(retrieved_set)


def recall(retrieved_files: List[str], expected_files: List[str]) -> float:
    """Fraction of expected files that were retrieved.

    Returns 0.0 if either list is empty.
    """
    if not retrieved_files or not expected_files:
        return 0.0
    retrieved_set = set(retrieved_files)
    expected_set = set(expected_files)
    return len(retrieved_set & expected_set) / len(expected_set)


def top_k_accuracy(
    ranked_files: List[str], expected_files: List[str], k: int
) -> float:
    """Whether any expected file appears in the top-k ranked results.

    Returns 1.0 if at least one expected file is in the top-k, else 0.0.
    Returns 0.0 if either list is empty.
    """
    if not ranked_files or not expected_files:
        return 0.0
    top_k = set(ranked_files[:k])
    expected_set = set(expected_files)
    return 1.0 if top_k & expected_set else 0.0


def evaluate_retrieval(
    retrieval_result: RetrievalResult,
    expected_files: List[str],
    expected_symbols: List[str],
) -> EvaluationResult:
    """Evaluate a full retrieval result against ground truth.

    Computes precision, recall, Top-K accuracy (k=3,5,10),
    and symbol recall.
    """
    retrieved_files = [fc.file_path for fc in retrieval_result.ranked_files]
    retrieved_symbol_names = {s.name for s in retrieval_result.ranked_symbols}

    p = precision(retrieved_files, expected_files)
    r = recall(retrieved_files, expected_files)
    top_3 = top_k_accuracy(retrieved_files, expected_files, k=3)
    top_5 = top_k_accuracy(retrieved_files, expected_files, k=5)
    top_10 = top_k_accuracy(retrieved_files, expected_files, k=10)

    if expected_symbols:
        sym_recall = len(retrieved_symbol_names & set(expected_symbols)) / len(
            expected_symbols
        )
    else:
        sym_recall = 0.0

    return EvaluationResult(
        precision=p,
        recall=r,
        top_3_accuracy=top_3,
        top_5_accuracy=top_5,
        top_10_accuracy=top_10,
        retrieved_files=retrieved_files,
        expected_files=expected_files,
        symbol_recall=sym_recall,
    )
