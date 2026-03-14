"""Evaluation dataset loader and validator.

Loads curated test tickets with expected ground truth from JSON files
for measuring retrieval quality.
"""

import json
from dataclasses import dataclass, field
from typing import List


@dataclass
class EvaluationTicket:
    """A test ticket with expected ground truth for evaluation."""
    ticket_id: str
    title: str
    description: str
    acceptance_criteria: str
    repo: str
    expected_files: List[str]
    expected_symbols: List[str]
    expected_behavior: str


def load_dataset(path: str) -> List[EvaluationTicket]:
    """Load evaluation tickets from a JSON file.

    Expects a JSON object with a "tickets" key containing a list of ticket objects.
    """
    with open(path, "r") as f:
        data = json.load(f)
    return [EvaluationTicket(**item) for item in data["tickets"]]


def validate_dataset(tickets: List[EvaluationTicket]) -> List[str]:
    """Validate evaluation tickets, returning a list of error strings.

    Checks for: empty ticket_id, duplicate ticket_ids, empty title,
    missing expected_files, missing expected_symbols.
    """
    errors = []
    seen_ids: set = set()

    for i, t in enumerate(tickets):
        if not t.ticket_id:
            errors.append(f"Ticket at index {i} has empty ticket_id")
        if t.ticket_id in seen_ids:
            errors.append(f"Duplicate ticket_id: {t.ticket_id}")
        seen_ids.add(t.ticket_id)
        if not t.title:
            errors.append(f"Ticket {t.ticket_id} has empty title")
        if not t.expected_files:
            errors.append(f"Ticket {t.ticket_id} has no expected_files")
        if not t.expected_symbols:
            errors.append(f"Ticket {t.ticket_id} has no expected_symbols")

    return errors
