"""Filter files by language and ignore rules."""

import os
from pathlib import Path

DEFAULT_IGNORE_DIRS: set[str] = {
    "node_modules", "dist", "build", "vendor", "coverage",
    ".git", "__pycache__", ".venv", "venv", ".tox",
    ".mypy_cache", ".pytest_cache",
}

DEFAULT_IGNORE_EXTENSIONS: set[str] = {
    ".pyc", ".pyo", ".so", ".o", ".a", ".dylib",
    ".class", ".jar", ".lock", ".min.js", ".min.css", ".map",
}

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".swift": "swift",
}


def detect_language(file_path: str) -> str | None:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_EXTENSIONS.get(ext)


def should_index_file(
    file_path: str,
    ignore_dirs: set[str] | None = None,
    ignore_extensions: set[str] | None = None,
) -> bool:
    """Check if a file should be indexed based on ignore rules."""
    dirs_to_ignore = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
    exts_to_ignore = ignore_extensions if ignore_extensions is not None else DEFAULT_IGNORE_EXTENSIONS

    parts = Path(file_path).parts
    for part in parts:
        if part in dirs_to_ignore:
            return False

    ext = Path(file_path).suffix.lower()
    if ext in exts_to_ignore:
        return False

    if detect_language(file_path) is None:
        return False

    return True


def filter_files(
    root_dir: str,
    ignore_dirs: set[str] | None = None,
    ignore_extensions: set[str] | None = None,
) -> list[str]:
    """Walk directory and return list of indexable file paths relative to root."""
    result = []
    root = Path(root_dir)

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place
        dirs_to_ignore = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
        dirnames[:] = [d for d in dirnames if d not in dirs_to_ignore]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root)
            if should_index_file(rel_path, ignore_dirs, ignore_extensions):
                result.append(rel_path)

    return sorted(result)
