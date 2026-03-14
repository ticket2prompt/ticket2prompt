"""Tests for the evaluation dataset loader and validator."""

import json
import os

import pytest

from evaluation.dataset import EvaluationTicket, load_dataset, validate_dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _make_ticket(
    ticket_id: str = "TEST-001",
    title: str = "Test ticket",
    description: str = "A test description",
    acceptance_criteria: str = "- Some criteria",
    repo: str = "test-repo",
    expected_files: list | object = _SENTINEL,
    expected_symbols: list | object = _SENTINEL,
    expected_behavior: str = "Expected behavior",
) -> EvaluationTicket:
    return EvaluationTicket(
        ticket_id=ticket_id,
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        repo=repo,
        expected_files=["src/a.py"] if expected_files is _SENTINEL else expected_files,
        expected_symbols=["func_a"] if expected_symbols is _SENTINEL else expected_symbols,
        expected_behavior=expected_behavior,
    )


def _write_dataset(tmp_path, tickets: list[dict]) -> str:
    path = str(tmp_path / "dataset.json")
    with open(path, "w") as f:
        json.dump({"tickets": tickets}, f)
    return path


# ---------------------------------------------------------------------------
# load_dataset
# ---------------------------------------------------------------------------

def test_load_dataset_valid(tmp_path):
    ticket_data = [
        {
            "ticket_id": "T-1",
            "title": "Title",
            "description": "Desc",
            "acceptance_criteria": "AC",
            "repo": "repo",
            "expected_files": ["a.py"],
            "expected_symbols": ["func"],
            "expected_behavior": "Works",
        }
    ]
    path = _write_dataset(tmp_path, ticket_data)
    result = load_dataset(path)

    assert len(result) == 1
    assert isinstance(result[0], EvaluationTicket)
    assert result[0].ticket_id == "T-1"
    assert result[0].title == "Title"
    assert result[0].expected_files == ["a.py"]


def test_load_dataset_multiple_tickets(tmp_path):
    tickets = [
        {
            "ticket_id": f"T-{i}",
            "title": f"Title {i}",
            "description": "Desc",
            "acceptance_criteria": "AC",
            "repo": "repo",
            "expected_files": ["a.py"],
            "expected_symbols": ["func"],
            "expected_behavior": "Works",
        }
        for i in range(3)
    ]
    path = _write_dataset(tmp_path, tickets)
    result = load_dataset(path)

    assert len(result) == 3
    assert result[0].ticket_id == "T-0"
    assert result[2].ticket_id == "T-2"


def test_load_dataset_missing_file():
    with pytest.raises(FileNotFoundError):
        load_dataset("/nonexistent/path/dataset.json")


def test_load_dataset_invalid_json(tmp_path):
    path = str(tmp_path / "bad.json")
    with open(path, "w") as f:
        f.write("not valid json{{{")
    with pytest.raises(json.JSONDecodeError):
        load_dataset(path)


def test_load_dataset_actual_fixture():
    """Integration test: load the real fixture file and validate it."""
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "evaluation",
        "fixtures",
        "evaluation_dataset.json",
    )
    fixture_path = os.path.normpath(fixture_path)
    tickets = load_dataset(fixture_path)

    assert len(tickets) >= 5
    errors = validate_dataset(tickets)
    assert errors == [], f"Fixture validation errors: {errors}"


# ---------------------------------------------------------------------------
# validate_dataset
# ---------------------------------------------------------------------------

def test_validate_dataset_valid():
    tickets = [_make_ticket("T-1"), _make_ticket("T-2")]
    errors = validate_dataset(tickets)
    assert errors == []


def test_validate_dataset_empty_ticket_id():
    tickets = [_make_ticket(ticket_id="")]
    errors = validate_dataset(tickets)
    assert any("empty ticket_id" in e for e in errors)


def test_validate_dataset_duplicate_ticket_ids():
    tickets = [_make_ticket("T-1"), _make_ticket("T-1")]
    errors = validate_dataset(tickets)
    assert any("Duplicate ticket_id" in e for e in errors)


def test_validate_dataset_empty_title():
    tickets = [_make_ticket(title="")]
    errors = validate_dataset(tickets)
    assert any("empty title" in e for e in errors)


def test_validate_dataset_no_expected_files():
    tickets = [_make_ticket(expected_files=[])]
    errors = validate_dataset(tickets)
    assert any("no expected_files" in e for e in errors)


def test_validate_dataset_no_expected_symbols():
    tickets = [_make_ticket(expected_symbols=[])]
    errors = validate_dataset(tickets)
    assert any("no expected_symbols" in e for e in errors)


def test_validate_dataset_multiple_errors():
    tickets = [
        _make_ticket(ticket_id="", title="", expected_files=[], expected_symbols=[])
    ]
    errors = validate_dataset(tickets)
    # Should catch empty ticket_id, empty title, no expected_files, no expected_symbols
    assert len(errors) >= 4
