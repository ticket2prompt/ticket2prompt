"""Tests verifying the repository scaffold exists and is importable."""

import importlib
import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path("/Users/karthik/projects/ticket-to-prompt")

# Ensure the project root is on sys.path so packages are importable.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 1. Top-level packages are importable
# ---------------------------------------------------------------------------

TOP_LEVEL_PACKAGES = [
    "api",
    "indexing",
    "retrieval",
    "prompts",
    "workflows",
    "storage",
    "integrations",
    "git_analysis",
    "config",
]


@pytest.mark.parametrize("package", TOP_LEVEL_PACKAGES)
def test_top_level_package_importable(package: str) -> None:
    """Each top-level package must be importable as a Python package."""
    importlib.import_module(package)


# ---------------------------------------------------------------------------
# 2. Expected module files exist on disk
# ---------------------------------------------------------------------------

EXPECTED_FILES = [
    "api/main.py",
    "api/routes/jira_routes.py",
    "api/routes/repo_routes.py",
    "api/routes/prompt_routes.py",
    "indexing/repo_cloner.py",
    "indexing/file_filter.py",
    "indexing/symbol_extractor.py",
    "indexing/embedding_pipeline.py",
    "indexing/graph_builder.py",
    "retrieval/vector_search.py",
    "retrieval/keyword_search.py",
    "retrieval/graph_expansion.py",
    "retrieval/ranking_engine.py",
    "retrieval/context_builder.py",
    "prompts/context_compression.py",
    "prompts/prompt_generator.py",
    "prompts/prompt_templates.py",
    "workflows/langgraph_pipeline.py",
    "workflows/pipeline_steps.py",
    "storage/postgres.py",
    "storage/qdrant_client.py",
    "storage/redis_cache.py",
    "integrations/jira_client.py",
    "integrations/github_client.py",
    "integrations/webhook_handlers.py",
    "git_analysis/change_detector.py",
    "git_analysis/commit_analyzer.py",
    "git_analysis/ownership_mapper.py",
    "config/settings.py",
    "config/logging_config.py",
    "scripts/index_repository.py",
]


@pytest.mark.parametrize("relative_path", EXPECTED_FILES)
def test_module_file_exists(relative_path: str) -> None:
    """Each expected module file must exist on disk."""
    full_path = PROJECT_ROOT / relative_path
    assert full_path.exists(), f"Expected file not found: {full_path}"


# ---------------------------------------------------------------------------
# 3. Sub-packages have __init__.py files
# ---------------------------------------------------------------------------

EXPECTED_INIT_FILES = [
    "api/routes/__init__.py",
    "api/schemas/__init__.py",
    "tests/indexing_tests/__init__.py",
    "tests/retrieval_tests/__init__.py",
    "tests/prompt_tests/__init__.py",
]


@pytest.mark.parametrize("relative_path", EXPECTED_INIT_FILES)
def test_subpackage_init_exists(relative_path: str) -> None:
    """Each sub-package directory must contain an __init__.py file."""
    full_path = PROJECT_ROOT / relative_path
    assert full_path.exists(), f"Expected __init__.py not found: {full_path}"
