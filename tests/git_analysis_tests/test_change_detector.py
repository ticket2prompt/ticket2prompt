from unittest.mock import MagicMock, patch

import git
import pytest

from git_analysis.change_detector import (
    ChangeSet,
    ChangeType,
    FileChange,
    _parse_diff_status,
    detect_changes,
    detect_changes_from_repo,
)


# --- _parse_diff_status tests ---


def test_parse_diff_status_added():
    output = "A\tnew_file.py"
    changes = _parse_diff_status(output)

    assert len(changes) == 1
    assert changes[0].file_path == "new_file.py"
    assert changes[0].change_type == ChangeType.ADDED


def test_parse_diff_status_modified():
    output = "M\texisting_file.py"
    changes = _parse_diff_status(output)

    assert len(changes) == 1
    assert changes[0].file_path == "existing_file.py"
    assert changes[0].change_type == ChangeType.MODIFIED


def test_parse_diff_status_deleted():
    output = "D\told_file.py"
    changes = _parse_diff_status(output)

    assert len(changes) == 1
    assert changes[0].file_path == "old_file.py"
    assert changes[0].change_type == ChangeType.DELETED


def test_parse_diff_status_renamed_produces_delete_and_add():
    output = "R100\told_name.py\tnew_name.py"
    changes = _parse_diff_status(output)

    assert len(changes) == 2
    deleted = next(c for c in changes if c.change_type == ChangeType.DELETED)
    added = next(c for c in changes if c.change_type == ChangeType.ADDED)
    assert deleted.file_path == "old_name.py"
    assert added.file_path == "new_name.py"


def test_parse_diff_status_mixed():
    output = "A\tnew.py\nM\tchanged.py\nD\tremoved.py"
    changes = _parse_diff_status(output)

    assert len(changes) == 3
    paths = {c.file_path for c in changes}
    assert paths == {"new.py", "changed.py", "removed.py"}

    types = {c.file_path: c.change_type for c in changes}
    assert types["new.py"] == ChangeType.ADDED
    assert types["changed.py"] == ChangeType.MODIFIED
    assert types["removed.py"] == ChangeType.DELETED


def test_parse_diff_status_empty():
    changes = _parse_diff_status("")
    assert changes == []


# --- ChangeSet property tests ---


def test_changeset_properties_filter_by_type():
    changes = [
        FileChange(file_path="a.py", change_type=ChangeType.ADDED),
        FileChange(file_path="b.py", change_type=ChangeType.MODIFIED),
        FileChange(file_path="c.py", change_type=ChangeType.DELETED),
        FileChange(file_path="d.py", change_type=ChangeType.ADDED),
    ]
    changeset = ChangeSet(changes=changes, from_commit="abc123", to_commit="def456")

    assert len(changeset.added) == 2
    assert all(c.change_type == ChangeType.ADDED for c in changeset.added)

    assert len(changeset.modified) == 1
    assert changeset.modified[0].file_path == "b.py"

    assert len(changeset.deleted) == 1
    assert changeset.deleted[0].file_path == "c.py"


def test_changeset_stores_commit_refs():
    changeset = ChangeSet(changes=[], from_commit="abc123", to_commit="def456")
    assert changeset.from_commit == "abc123"
    assert changeset.to_commit == "def456"


# --- detect_changes_from_repo tests ---


def test_detect_changes_from_repo_returns_changeset():
    mock_repo = MagicMock(spec=git.Repo)
    mock_repo.git.diff.return_value = "A\tnew.py\nM\texisting.py"

    result = detect_changes_from_repo(mock_repo, "abc123", "def456")

    mock_repo.git.diff.assert_called_once_with("--name-status", "abc123", "def456")
    assert isinstance(result, ChangeSet)
    assert result.from_commit == "abc123"
    assert result.to_commit == "def456"
    assert len(result.changes) == 2


def test_detect_changes_from_repo_empty_diff():
    mock_repo = MagicMock(spec=git.Repo)
    mock_repo.git.diff.return_value = ""

    result = detect_changes_from_repo(mock_repo, "abc123", "def456")

    assert result.changes == []
    assert result.from_commit == "abc123"
    assert result.to_commit == "def456"


def test_detect_changes_from_repo_with_rename():
    mock_repo = MagicMock(spec=git.Repo)
    mock_repo.git.diff.return_value = "R100\told.py\tnew.py\nM\tother.py"

    result = detect_changes_from_repo(mock_repo, "abc123", "def456")

    assert len(result.changes) == 3
    assert len(result.deleted) == 1
    assert result.deleted[0].file_path == "old.py"
    assert len(result.added) == 1
    assert result.added[0].file_path == "new.py"
    assert len(result.modified) == 1


# --- detect_changes tests ---


def test_detect_changes_opens_repo_from_path():
    mock_repo = MagicMock(spec=git.Repo)
    mock_repo.git.diff.return_value = "M\tfile.py"

    with patch("git_analysis.change_detector.git.Repo", return_value=mock_repo) as mock_repo_cls:
        result = detect_changes("/path/to/repo", "abc123", "def456")

    mock_repo_cls.assert_called_once_with("/path/to/repo")
    assert isinstance(result, ChangeSet)
    assert result.from_commit == "abc123"
    assert result.to_commit == "def456"


def test_detect_changes_delegates_to_detect_changes_from_repo():
    mock_repo = MagicMock(spec=git.Repo)
    mock_repo.git.diff.return_value = "A\tnew.py\nD\told.py"

    with patch("git_analysis.change_detector.git.Repo", return_value=mock_repo):
        result = detect_changes("/path/to/repo", "abc123", "def456")

    assert len(result.changes) == 2
    assert len(result.added) == 1
    assert len(result.deleted) == 1
