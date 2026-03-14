import logging

import pytest

from config.settings import Settings, get_settings
from config.logging_config import setup_logging

ENV_VARS = ["POSTGRES_URL", "REDIS_URL", "QDRANT_URL", "EMBEDDING_MODEL", "API_PORT", "LOG_LEVEL", "DEBUG"]


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# --- Settings tests ---

def test_settings_defaults():
    settings = Settings(_env_file=None)
    assert settings.postgres_url == ""
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.embedding_model == "bge-small-en"
    assert settings.api_port == 8000
    assert settings.log_level == "INFO"
    assert settings.debug is False


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgresql://prod:prod@db:5432/prod_db")
    settings = Settings()
    assert settings.postgres_url == "postgresql://prod:prod@db:5432/prod_db"
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.embedding_model == "bge-small-en"
    assert settings.api_port == 8000
    assert settings.log_level == "INFO"
    assert settings.debug is False


def test_settings_multiple_overrides(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://prod-cache:6379")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant-prod:6333")
    monkeypatch.setenv("EMBEDDING_MODEL", "bge-large-en")
    settings = Settings()
    assert settings.redis_url == "redis://prod-cache:6379"
    assert settings.qdrant_url == "http://qdrant-prod:6333"
    assert settings.embedding_model == "bge-large-en"


def test_settings_api_port_from_env(monkeypatch):
    monkeypatch.setenv("API_PORT", "9000")
    settings = Settings()
    assert settings.api_port == 9000
    assert isinstance(settings.api_port, int)


def test_settings_debug_flag(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    settings = Settings()
    assert settings.debug is True


def test_settings_log_level_case_insensitive(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    settings = Settings()
    assert settings.log_level == "debug"


def test_get_settings_returns_settings_instance():
    result = get_settings()
    assert isinstance(result, Settings)


def test_settings_postgres_url_format(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgresql://u:p@localhost:5432/db")
    settings = Settings()
    assert settings.postgres_url.startswith("postgresql://")


def test_settings_qdrant_url_format():
    settings = Settings()
    assert settings.qdrant_url.startswith("http")


# --- Logging tests ---

def test_setup_logging_callable():
    assert callable(setup_logging)


def test_setup_logging_sets_level():
    setup_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_default_level():
    setup_logging()
    assert logging.getLogger().level == logging.INFO
