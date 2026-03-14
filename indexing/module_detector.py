"""Detect module boundaries in monorepos and classify files to modules."""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MODULE_SIGNALS = [
    "pyproject.toml",
    "package.json",
    "go.mod",
    "build.gradle",
    "Cargo.toml",
    "pom.xml",
]

SERVICE_DIR_NAMES = {"services", "apps", "packages", "modules"}

_IGNORED_DIRS = {
    "node_modules", "vendor", ".git", "dist", "build",
    "__pycache__", ".venv", "venv",
}

_MANIFEST_TO_LANGUAGE = {
    "pyproject.toml": "python",
    "package.json": "typescript",
    "go.mod": "go",
    "build.gradle": "java",
    "Cargo.toml": "rust",
    "pom.xml": "java",
}


@dataclass
class DetectedModule:
    """A discovered module boundary within a repository."""
    name: str            # e.g. "payments"
    path: str            # e.g. "services/payments" (relative to repo root)
    language: str | None
    manifest_file: str | None  # e.g. "pyproject.toml"


def _detect_language_from_manifest(manifest_file: str | None) -> str | None:
    """Map a manifest filename to a programming language."""
    if manifest_file is None:
        return None
    return _MANIFEST_TO_LANGUAGE.get(manifest_file)


def _find_manifest(dir_path: str) -> str | None:
    """Return the first MODULE_SIGNALS file found in dir_path, or None."""
    for signal in MODULE_SIGNALS:
        if os.path.isfile(os.path.join(dir_path, signal)):
            return signal
    return None


def detect_modules(repo_path: str) -> list[DetectedModule]:
    """Scan repo_path for module boundaries.

    Detection strategy:
    1. Walk top-level directories looking for SERVICE_DIR_NAMES (e.g. services/).
    2. Each direct child of a service dir is treated as a module, with or
       without a manifest file.
    3. Also check top-level directories for manifest files directly (e.g.
       libs/auth/ with its own pyproject.toml).
    4. Ignored directories (_IGNORED_DIRS) are never reported as modules.

    Returns a list of DetectedModule instances.  If none are found, returns a
    single root module with name="" and path="".
    """
    modules: list[DetectedModule] = []
    seen_paths: set[str] = set()

    try:
        top_level_entries = os.listdir(repo_path)
    except OSError:
        logger.warning("Cannot list repo_path: %s", repo_path)
        return [DetectedModule(name="", path="", language=None, manifest_file=None)]

    for entry in sorted(top_level_entries):
        entry_abs = os.path.join(repo_path, entry)

        if not os.path.isdir(entry_abs):
            continue
        if entry in _IGNORED_DIRS:
            continue

        if entry in SERVICE_DIR_NAMES:
            # Treat each child of this service directory as a module.
            _collect_service_children(entry_abs, entry, modules, seen_paths)
        else:
            # Check if this top-level dir itself carries a manifest (e.g. libs/auth).
            manifest = _find_manifest(entry_abs)
            if manifest is not None:
                rel_path = entry
                if rel_path not in seen_paths:
                    seen_paths.add(rel_path)
                    modules.append(DetectedModule(
                        name=entry,
                        path=rel_path,
                        language=_detect_language_from_manifest(manifest),
                        manifest_file=manifest,
                    ))

    if not modules:
        return [DetectedModule(name="", path="", language=None, manifest_file=None)]

    return modules


def _collect_service_children(
    service_dir_abs: str,
    service_dir_rel: str,
    modules: list[DetectedModule],
    seen_paths: set[str],
) -> None:
    """Add each non-ignored child directory of service_dir as a module."""
    try:
        children = os.listdir(service_dir_abs)
    except OSError:
        logger.warning("Cannot list service directory: %s", service_dir_abs)
        return

    for child in sorted(children):
        child_abs = os.path.join(service_dir_abs, child)

        if not os.path.isdir(child_abs):
            continue
        if child in _IGNORED_DIRS:
            continue

        rel_path = os.path.join(service_dir_rel, child)
        if rel_path in seen_paths:
            continue

        seen_paths.add(rel_path)
        manifest = _find_manifest(child_abs)
        modules.append(DetectedModule(
            name=child,
            path=rel_path,
            language=_detect_language_from_manifest(manifest),
            manifest_file=manifest,
        ))


def classify_file_to_module(file_path: str, modules: list[DetectedModule]) -> str:
    """Return the module name that best matches file_path.

    Matches are determined by the longest module path that is a prefix of
    file_path.  Returns "" if no module path matches (i.e. file belongs to the
    root module or to a repo with a single root module).

    Args:
        file_path: Relative file path within the repository.
        modules:   List of DetectedModule instances from detect_modules().

    Returns:
        The module name string, or "" for the root module.
    """
    best_name = ""
    best_length = -1

    for module in modules:
        if not module.path:
            # Root module — matches everything but we prefer more specific hits.
            if best_length < 0:
                best_name = module.name
                best_length = 0
            continue

        prefix = module.path if module.path.endswith(os.sep) else module.path + os.sep
        if file_path.startswith(prefix) or file_path == module.path:
            path_len = len(module.path)
            if path_len > best_length:
                best_length = path_len
                best_name = module.name

    return best_name


def detect_cross_module_dependencies(
    symbols: list[dict],
    edges: list[tuple[str, str, str]],
) -> list[dict]:
    """Return cross-module dependency records from a list of edges.

    Args:
        symbols: Each dict must have 'symbol_id' and 'module' keys.
        edges:   Each tuple is (from_id, to_id, relation_type).

    Returns:
        List of dicts with keys: from_module, to_module, from_symbol,
        to_symbol, relation_type.  Only edges that cross module boundaries
        are included.
    """
    symbol_module: dict[str, str] = {
        sym["symbol_id"]: sym["module"] for sym in symbols
    }

    cross: list[dict] = []
    for from_id, to_id, relation_type in edges:
        from_module = symbol_module.get(from_id)
        to_module = symbol_module.get(to_id)

        if from_module is None or to_module is None:
            continue
        if from_module == to_module:
            continue

        cross.append({
            "from_module": from_module,
            "to_module": to_module,
            "from_symbol": from_id,
            "to_symbol": to_id,
            "relation_type": relation_type,
        })

    return cross
