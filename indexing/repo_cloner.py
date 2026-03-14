"""Clone repositories using GitPython."""

import logging
import os
from pathlib import Path

import git

logger = logging.getLogger(__name__)


class CloneError(Exception):
    """Raised when a repository clone operation fails."""


def clone_repo(repo_url: str, target_path: str) -> git.Repo:
    """Clone a git repository to target_path, or open it if already cloned.

    Args:
        repo_url: The URL of the git repository to clone.
        target_path: Local filesystem path to clone into.

    Returns:
        A git.Repo object for the cloned/opened repository.

    Raises:
        CloneError: If the clone operation fails.
    """
    target = Path(target_path)

    # If the target already has a .git directory, open the existing repo
    if (target / ".git").exists():
        logger.info("Repository already exists at %s, opening existing", target_path)
        return git.Repo(target_path)

    # Ensure parent directory exists
    os.makedirs(target.parent, exist_ok=True)

    try:
        logger.info("Cloning %s into %s", repo_url, target_path)
        return git.Repo.clone_from(repo_url, target_path)
    except git.exc.GitCommandError as e:
        raise CloneError(f"Failed to clone {repo_url}: {e}") from e
    except PermissionError as e:
        raise CloneError(f"Permission denied cloning to {target_path}: {e}") from e
    except Exception as e:
        raise CloneError(f"Unexpected error cloning {repo_url}: {e}") from e


def clone_or_update_repo(repo_url: str, target_path: str) -> git.Repo:
    """Clone a repository or fetch the latest refs if it already exists.

    If *target_path* contains a valid git repository, fetch from origin to
    bring remote refs up to date.  Otherwise delegates to :func:`clone_repo`.

    Args:
        repo_url: The URL of the git repository.
        target_path: Local filesystem path.

    Returns:
        A git.Repo object for the cloned/updated repository.

    Raises:
        CloneError: If the clone or fetch operation fails.
    """
    target = Path(target_path)

    if (target / ".git").exists():
        logger.info("Repository exists at %s, fetching latest refs", target_path)
        repo = git.Repo(target_path)
        try:
            repo.remotes.origin.fetch()
        except git.exc.GitCommandError as e:
            raise CloneError(f"Failed to fetch origin for {target_path}: {e}") from e
        return repo

    return clone_repo(repo_url, target_path)
