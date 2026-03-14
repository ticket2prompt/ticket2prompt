"""End-to-end evaluation runner.

Runs synthetic tickets through the full LangGraph pipeline and
evaluates retrieval quality against expected ground truth.
"""

import time
from dataclasses import dataclass, field
from typing import List

from evaluation import EvaluationResult
from evaluation.dataset import EvaluationTicket
from evaluation.retrieval_metrics import evaluate_retrieval
from prompts import GeneratedPrompt
from retrieval import RetrievalResult, TicketInput
from workflows.langgraph_pipeline import run_pipeline
from workflows.pipeline_steps import PipelineConfig


@dataclass
class E2EResult:
    """Result of running one ticket through the E2E pipeline."""
    ticket_id: str
    evaluation: EvaluationResult
    prompt: GeneratedPrompt
    execution_time_ms: float
    errors: List[str] = field(default_factory=list)


def _ticket_to_input(ticket: EvaluationTicket) -> TicketInput:
    """Convert an EvaluationTicket to a TicketInput for the pipeline."""
    return TicketInput(
        title=ticket.title,
        description=ticket.description,
        acceptance_criteria=ticket.acceptance_criteria,
        repo=ticket.repo,
    )


def _extract_retrieval_result(state: dict) -> RetrievalResult:
    """Extract a RetrievalResult from the pipeline's final state dict."""
    ranked_files = state.get("ranked_files", [])
    vector_matches = state.get("vector_matches", [])
    keyword_matches = state.get("keyword_matches", [])
    graph_matches = state.get("graph_matches", [])
    all_symbols = vector_matches + keyword_matches + graph_matches
    return RetrievalResult(
        ranked_files=ranked_files,
        ranked_symbols=all_symbols,
        query_count=len(state.get("expanded_queries", [])),
        total_candidates=len(all_symbols),
    )


def run_e2e_evaluation(
    config: PipelineConfig, ticket: EvaluationTicket
) -> E2EResult:
    """Run a single evaluation ticket through the full pipeline."""
    ticket_input = _ticket_to_input(ticket)

    start = time.monotonic()
    state = run_pipeline(config, ticket_input)
    elapsed_ms = (time.monotonic() - start) * 1000

    retrieval_result = _extract_retrieval_result(state)
    evaluation = evaluate_retrieval(
        retrieval_result,
        expected_files=ticket.expected_files,
        expected_symbols=ticket.expected_symbols,
    )

    prompt = state.get("generated_prompt", GeneratedPrompt())
    errors = state.get("errors", [])

    return E2EResult(
        ticket_id=ticket.ticket_id,
        evaluation=evaluation,
        prompt=prompt,
        execution_time_ms=elapsed_ms,
        errors=errors,
    )


def run_evaluation_suite(
    config: PipelineConfig, dataset: List[EvaluationTicket]
) -> List[E2EResult]:
    """Run all tickets in the dataset through the pipeline."""
    return [run_e2e_evaluation(config, ticket) for ticket in dataset]
