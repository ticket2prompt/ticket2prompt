"""Detect file changes between commits."""

import logging
from dataclasses import dataclass
from enum import Enum

import git

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileChange:
    file_path: str
    change_type: ChangeType


@dataclass
class ChangeSet:
    changes: list[FileChange]
    from_commit: str
    to_commit: str

    @property
    def added(self) -> list[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.ADDED]

    @property
    def modified(self) -> list[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.MODIFIED]

    @property
    def deleted(self) -> list[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.DELETED]


def detect_changes(repo_path: str, from_commit: str, to_commit: str) -> ChangeSet:
    """Open a git repository at repo_path and detect changes between two commits.

    Args:
        repo_path: Filesystem path to the git repository.
        from_commit: Starting commit SHA or ref.
        to_commit: Ending commit SHA or ref.

    Returns:
        A ChangeSet describing all file changes between the two commits.
    """
    repo = git.Repo(repo_path)
    return detect_changes_from_repo(repo, from_commit, to_commit)


def detect_changes_from_repo(repo: git.Repo, from_commit: str, to_commit: str) -> ChangeSet:
    """Detect file changes between two commits using an existing Repo object.

    Args:
        repo: An open git.Repo instance.
        from_commit: Starting commit SHA or ref.
        to_commit: Ending commit SHA or ref.

    Returns:
        A ChangeSet describing all file changes between the two commits.
    """
    logger.debug("Diffing %s..%s in %s", from_commit, to_commit, repo.working_tree_dir)
    diff_output = repo.git.diff("--name-status", from_commit, to_commit)
    changes = _parse_diff_status(diff_output)
    return ChangeSet(changes=changes, from_commit=from_commit, to_commit=to_commit)


def _parse_diff_status(diff_output: str) -> list[FileChange]:
    """Parse git diff --name-status output into FileChange objects.

    Each line is expected to be one of:
        M<TAB>path/to/file.py        (modified)
        A<TAB>path/to/file.py        (added)
        D<TAB>path/to/file.py        (deleted)
        R<score><TAB>old<TAB>new     (renamed → treated as delete + add)

    Args:
        diff_output: Raw string output from `git diff --name-status`.

    Returns:
        List of FileChange objects.
    """
    if not diff_output.strip():
        return []

    changes: list[FileChange] = []
    for line in diff_output.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        status = parts[0]

        if status.startswith("R"):
            # Rename: R<score>\told_path\tnew_path
            old_path, new_path = parts[1], parts[2]
            changes.append(FileChange(file_path=old_path, change_type=ChangeType.DELETED))
            changes.append(FileChange(file_path=new_path, change_type=ChangeType.ADDED))
        elif status == "A":
            changes.append(FileChange(file_path=parts[1], change_type=ChangeType.ADDED))
        elif status == "M":
            changes.append(FileChange(file_path=parts[1], change_type=ChangeType.MODIFIED))
        elif status == "D":
            changes.append(FileChange(file_path=parts[1], change_type=ChangeType.DELETED))
        else:
            logger.warning("Unrecognized diff status token: %r in line %r", status, line)

    return changes
