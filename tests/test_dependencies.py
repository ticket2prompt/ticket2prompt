import importlib

import pytest


@pytest.mark.parametrize(
    "import_name, description",
    [
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI server"),
        ("pydantic", "Data validation"),
        ("pydantic_settings", "Settings management"),
        ("langgraph", "LangGraph workflow orchestration"),
        ("litellm", "LLM abstraction layer"),
        ("qdrant_client", "Qdrant vector database client"),
        ("psycopg2", "PostgreSQL driver"),
        ("redis", "Redis client"),
        ("tree_sitter", "Tree-sitter parser"),
        ("sentence_transformers", "Sentence Transformers embeddings"),
        ("git", "GitPython git access"),
        ("pytest", "Test framework"),
        ("httpx", "HTTP test client"),
    ],
)
def test_dependency_importable(import_name: str, description: str) -> None:
    module = importlib.import_module(import_name)
    assert module is not None, f"Failed to import {import_name} ({description})"


def test_fastapi_version() -> None:
    import fastapi

    assert fastapi.__version__, "fastapi.__version__ should not be empty or None"
