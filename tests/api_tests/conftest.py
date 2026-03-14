"""Shared fixtures for API tests."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.dependencies import get_postgres, get_redis, get_qdrant, get_pipeline_config
from auth.middleware import get_current_user, require_project_access

FAKE_ORG_ID = "test-org-id"
FAKE_PROJECT_ID = "test-project-id"


@pytest.fixture
def mock_postgres():
    return MagicMock()


@pytest.fixture
def mock_redis():
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = None
    return mock


@pytest.fixture
def mock_qdrant():
    return MagicMock()


@pytest.fixture
def mock_pipeline_config():
    return MagicMock()


@pytest.fixture
def app(mock_postgres, mock_redis, mock_qdrant, mock_pipeline_config):
    """Create a FastAPI app with mocked dependencies."""
    application = create_app()
    application.dependency_overrides[get_postgres] = lambda: mock_postgres
    application.dependency_overrides[get_redis] = lambda: mock_redis
    application.dependency_overrides[get_qdrant] = lambda: mock_qdrant
    application.dependency_overrides[get_pipeline_config] = lambda: mock_pipeline_config

    def mock_get_current_user():
        return {"user_id": "test-user-id", "org_id": FAKE_ORG_ID, "role": "member"}

    def mock_require_project_access():
        return {
            "id": FAKE_PROJECT_ID,
            "org_id": FAKE_ORG_ID,
            "github_repo_url": "https://github.com/org/repo.git",
            "default_branch": "main",
            "slug": "org/repo",
            "name": "repo",
        }

    application.dependency_overrides[get_current_user] = mock_get_current_user
    application.dependency_overrides[require_project_access] = mock_require_project_access

    return application


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)
