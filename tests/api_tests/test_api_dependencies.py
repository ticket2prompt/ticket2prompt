"""Tests for api/dependencies.py."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from api.dependencies import (
    get_pipeline_config,
    get_postgres,
    get_qdrant,
    get_redis,
    get_settings_dep,
)


# ---------------------------------------------------------------------------
# get_settings_dep
# ---------------------------------------------------------------------------

class TestGetSettingsDep:
    def test_returns_settings_object(self):
        from config.settings import Settings
        # Clear the lru_cache so this test is isolated
        get_settings_dep.cache_clear()
        settings = get_settings_dep()
        assert isinstance(settings, Settings)

    def test_is_cached(self):
        get_settings_dep.cache_clear()
        s1 = get_settings_dep()
        s2 = get_settings_dep()
        assert s1 is s2


# ---------------------------------------------------------------------------
# get_postgres
# ---------------------------------------------------------------------------

class TestGetPostgres:
    def _make_request(self, postgres):
        mock_request = MagicMock()
        mock_request.app.state.postgres = postgres
        return mock_request

    def test_returns_postgres_from_state(self):
        mock_postgres = MagicMock()
        request = self._make_request(mock_postgres)
        result = get_postgres(request)
        assert result is mock_postgres

    def test_raises_503_when_postgres_is_none(self):
        request = self._make_request(None)
        with pytest.raises(HTTPException) as exc_info:
            get_postgres(request)
        assert exc_info.value.status_code == 503
        assert "unavailable" in exc_info.value.detail.lower()

    def test_503_detail_message(self):
        request = self._make_request(None)
        with pytest.raises(HTTPException) as exc_info:
            get_postgres(request)
        assert exc_info.value.detail == "Database unavailable"


# ---------------------------------------------------------------------------
# get_redis
# ---------------------------------------------------------------------------

class TestGetRedis:
    def _make_request(self, redis):
        mock_request = MagicMock()
        mock_request.app.state.redis = redis
        return mock_request

    def test_returns_redis_from_state(self):
        mock_redis = MagicMock()
        request = self._make_request(mock_redis)
        result = get_redis(request)
        assert result is mock_redis

    def test_returns_none_when_redis_is_none(self):
        request = self._make_request(None)
        result = get_redis(request)
        assert result is None

    def test_does_not_raise_when_redis_is_none(self):
        request = self._make_request(None)
        # Should not raise — Redis is optional
        result = get_redis(request)
        assert result is None


# ---------------------------------------------------------------------------
# get_qdrant
# ---------------------------------------------------------------------------

class TestGetQdrant:
    def _make_request(self, qdrant):
        mock_request = MagicMock()
        mock_request.app.state.qdrant = qdrant
        return mock_request

    def test_returns_qdrant_from_state(self):
        mock_qdrant = MagicMock()
        request = self._make_request(mock_qdrant)
        result = get_qdrant(request)
        assert result is mock_qdrant

    def test_returns_none_when_qdrant_is_none(self):
        request = self._make_request(None)
        result = get_qdrant(request)
        assert result is None


# ---------------------------------------------------------------------------
# get_pipeline_config
# ---------------------------------------------------------------------------

class TestGetPipelineConfig:
    def _make_request(self, config):
        mock_request = MagicMock()
        mock_request.app.state.pipeline_config = config
        return mock_request

    def test_returns_pipeline_config_from_state(self):
        mock_config = MagicMock()
        request = self._make_request(mock_config)
        result = get_pipeline_config(request)
        assert result is mock_config

    def test_returns_none_when_config_is_none(self):
        request = self._make_request(None)
        result = get_pipeline_config(request)
        assert result is None
