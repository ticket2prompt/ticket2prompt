"""Additional repo_cloner tests for uncovered lines (46-47, 66-77).

Lines 46-47: unexpected exception in clone_repo raises CloneError.
Lines 66-77: clone_or_update_repo — existing repo fetches, non-existing delegates to clone_repo,
             and fetch failure raises CloneError.
"""

import os
from unittest.mock import MagicMock, patch

import git
import pytest

from indexing.repo_cloner import CloneError, clone_repo, clone_or_update_repo


# ---------------------------------------------------------------------------
# clone_repo — unexpected exception path (lines 46-47)
# ---------------------------------------------------------------------------

class TestCloneRepoUnexpectedException:
    def test_unexpected_exception_raises_clone_error(self, tmp_path):
        target = str(tmp_path / "repo")

        with patch(
            "git.Repo.clone_from",
            side_effect=OSError("Disk full"),
        ):
            with pytest.raises(CloneError) as exc_info:
                clone_repo("https://github.com/org/repo.git", target)

        assert "Unexpected error" in str(exc_info.value)
        assert "https://github.com/org/repo.git" in str(exc_info.value)

    def test_unexpected_exception_chained_from_original(self, tmp_path):
        target = str(tmp_path / "repo")
        original = OSError("something weird")

        with patch("git.Repo.clone_from", side_effect=original):
            with pytest.raises(CloneError) as exc_info:
                clone_repo("https://github.com/org/repo.git", target)

        assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# clone_or_update_repo — existing repo fetches (lines 66-75)
# ---------------------------------------------------------------------------

class TestCloneOrUpdateRepo:
    def test_existing_repo_fetches_from_origin(self, tmp_path):
        target = str(tmp_path / "repo")
        os.makedirs(os.path.join(target, ".git"))

        mock_repo = MagicMock(spec=git.Repo)
        mock_remote = MagicMock()
        mock_repo.remotes.origin = mock_remote

        with patch("git.Repo", return_value=mock_repo):
            result = clone_or_update_repo("https://github.com/org/repo.git", target)

        mock_remote.fetch.assert_called_once()
        assert result is mock_repo

    def test_existing_repo_fetch_failure_raises_clone_error(self, tmp_path):
        target = str(tmp_path / "repo")
        os.makedirs(os.path.join(target, ".git"))

        mock_repo = MagicMock(spec=git.Repo)
        mock_remote = MagicMock()
        mock_remote.fetch.side_effect = git.exc.GitCommandError("fetch", 128)
        mock_repo.remotes.origin = mock_remote

        with patch("git.Repo", return_value=mock_repo):
            with pytest.raises(CloneError) as exc_info:
                clone_or_update_repo("https://github.com/org/repo.git", target)

        assert "Failed to fetch origin" in str(exc_info.value)
        assert target in str(exc_info.value)

    def test_non_existing_repo_delegates_to_clone_repo(self, tmp_path):
        target = str(tmp_path / "new_repo")
        mock_repo = MagicMock(spec=git.Repo)

        with patch("git.Repo.clone_from", return_value=mock_repo) as mock_clone:
            result = clone_or_update_repo("https://github.com/org/repo.git", target)

        mock_clone.assert_called_once_with("https://github.com/org/repo.git", target)
        assert result is mock_repo

    def test_non_existing_repo_clone_failure_raises_clone_error(self, tmp_path):
        target = str(tmp_path / "new_repo")

        with patch(
            "git.Repo.clone_from",
            side_effect=git.exc.GitCommandError("clone", 128),
        ):
            with pytest.raises(CloneError):
                clone_or_update_repo("https://github.com/org/repo.git", target)

    def test_fetch_error_is_chained(self, tmp_path):
        target = str(tmp_path / "repo")
        os.makedirs(os.path.join(target, ".git"))

        mock_repo = MagicMock(spec=git.Repo)
        original_error = git.exc.GitCommandError("fetch", 128)
        mock_repo.remotes.origin.fetch.side_effect = original_error

        with patch("git.Repo", return_value=mock_repo):
            with pytest.raises(CloneError) as exc_info:
                clone_or_update_repo("https://github.com/org/repo.git", target)

        assert exc_info.value.__cause__ is original_error
