import os
from unittest.mock import MagicMock, patch

import git
import pytest

from indexing.repo_cloner import CloneError, clone_repo


def test_clone_repo_calls_git_clone(tmp_path):
    target = str(tmp_path / "repo")
    mock_repo = MagicMock(spec=git.Repo)

    with patch("git.Repo.clone_from", return_value=mock_repo) as mock_clone:
        result = clone_repo("https://github.com/org/repo.git", target)

    mock_clone.assert_called_once_with("https://github.com/org/repo.git", target)
    assert result is mock_repo


def test_clone_repo_returns_repo_object(tmp_path):
    target = str(tmp_path / "repo")
    mock_repo = MagicMock(spec=git.Repo)

    with patch("git.Repo.clone_from", return_value=mock_repo):
        result = clone_repo("https://github.com/org/repo.git", target)

    assert result is mock_repo


def test_clone_repo_existing_directory_with_git(tmp_path):
    target = str(tmp_path / "existing_repo")
    os.makedirs(os.path.join(target, ".git"))
    mock_repo = MagicMock(spec=git.Repo)

    with patch("git.Repo", return_value=mock_repo) as mock_git_repo:
        with patch("git.Repo.clone_from") as mock_clone:
            result = clone_repo("https://github.com/org/repo.git", target)

    mock_clone.assert_not_called()
    mock_git_repo.assert_called_once_with(target)
    assert result is mock_repo


def test_clone_repo_invalid_url_raises_clone_error(tmp_path):
    target = str(tmp_path / "repo")

    with patch(
        "git.Repo.clone_from",
        side_effect=git.exc.GitCommandError("clone", 128),
    ):
        with pytest.raises(CloneError) as exc_info:
            clone_repo("https://github.com/invalid/repo.git", target)

    assert "https://github.com/invalid/repo.git" in str(exc_info.value)


def test_clone_repo_permission_error_raises_clone_error(tmp_path):
    target = str(tmp_path / "repo")

    with patch("git.Repo.clone_from", side_effect=PermissionError("Permission denied")):
        with pytest.raises(CloneError):
            clone_repo("https://github.com/org/repo.git", target)


def test_clone_repo_creates_target_parent_directory(tmp_path):
    target = str(tmp_path / "nested" / "repo")
    mock_repo = MagicMock(spec=git.Repo)

    with patch("git.Repo.clone_from", return_value=mock_repo):
        clone_repo("https://github.com/org/repo.git", target)

    assert os.path.isdir(os.path.dirname(target))


def test_clone_error_is_exception():
    assert issubclass(CloneError, Exception)
