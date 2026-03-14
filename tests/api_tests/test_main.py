"""Tests for api/main.py — lifespan events, middleware, and app creation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import APP_VERSION, create_app, lifespan, _run_migrations


# ---------------------------------------------------------------------------
# _run_migrations helper
# ---------------------------------------------------------------------------

class TestRunMigrations:
    def test_executes_schema_sql(self):
        fake_sql = "CREATE TABLE foo (id INT);"
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_postgres = MagicMock()
        mock_postgres._get_conn.return_value = mock_conn

        with patch("api.main._SCHEMA_PATH") as mock_path:
            mock_path.read_text.return_value = fake_sql
            _run_migrations(mock_postgres)

        mock_cursor.execute.assert_called_once_with(fake_sql)
        mock_conn.commit.assert_called_once()

    def test_rolls_back_and_re_raises_on_failure(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("SQL error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_postgres = MagicMock()
        mock_postgres._get_conn.return_value = mock_conn

        with patch("api.main._SCHEMA_PATH") as mock_path:
            mock_path.read_text.return_value = "BAD SQL;"
            with pytest.raises(Exception, match="SQL error"):
                _run_migrations(mock_postgres)

        mock_conn.rollback.assert_called_once()

    def test_returns_conn_to_pool_in_finally(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_postgres = MagicMock()
        mock_postgres._get_conn.return_value = mock_conn

        with patch("api.main._SCHEMA_PATH") as mock_path:
            mock_path.read_text.return_value = "SELECT 1;"
            _run_migrations(mock_postgres)

        mock_postgres._put_conn.assert_called_once_with(mock_conn)

    def test_returns_conn_to_pool_on_failure(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("boom")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_postgres = MagicMock()
        mock_postgres._get_conn.return_value = mock_conn

        with patch("api.main._SCHEMA_PATH") as mock_path:
            mock_path.read_text.return_value = "INVALID;"
            with pytest.raises(Exception):
                _run_migrations(mock_postgres)

        mock_postgres._put_conn.assert_called_once_with(mock_conn)


# ---------------------------------------------------------------------------
# lifespan — startup / shutdown
# ---------------------------------------------------------------------------

class TestLifespan:
    @pytest.mark.anyio
    async def test_lifespan_sets_postgres_on_app_state(self):
        mock_postgres = MagicMock()
        mock_redis = MagicMock()
        mock_settings = MagicMock()
        mock_settings.postgres_url = "postgresql://localhost/db"
        mock_settings.redis_url = "redis://localhost:6379"

        app = create_app()

        with patch("api.main.get_settings", return_value=mock_settings), \
             patch("api.main.PostgresClient", return_value=mock_postgres), \
             patch("api.main.RedisCache", return_value=mock_redis), \
             patch("api.main._run_migrations"):

            async with lifespan(app):
                assert app.state.postgres is mock_postgres

    @pytest.mark.anyio
    async def test_lifespan_sets_redis_on_app_state(self):
        mock_postgres = MagicMock()
        mock_redis = MagicMock()
        mock_settings = MagicMock()
        mock_settings.postgres_url = "postgresql://localhost/db"
        mock_settings.redis_url = "redis://localhost:6379"

        app = create_app()

        with patch("api.main.get_settings", return_value=mock_settings), \
             patch("api.main.PostgresClient", return_value=mock_postgres), \
             patch("api.main.RedisCache", return_value=mock_redis), \
             patch("api.main._run_migrations"):

            async with lifespan(app):
                assert app.state.redis is mock_redis

    @pytest.mark.anyio
    async def test_lifespan_closes_postgres_on_shutdown(self):
        mock_postgres = MagicMock()
        mock_redis = MagicMock()
        mock_settings = MagicMock()
        mock_settings.postgres_url = "postgresql://localhost/db"
        mock_settings.redis_url = "redis://localhost:6379"

        app = create_app()

        with patch("api.main.get_settings", return_value=mock_settings), \
             patch("api.main.PostgresClient", return_value=mock_postgres), \
             patch("api.main.RedisCache", return_value=mock_redis), \
             patch("api.main._run_migrations"):

            async with lifespan(app):
                pass

        mock_postgres.close.assert_called_once()

    @pytest.mark.anyio
    async def test_lifespan_closes_redis_on_shutdown(self):
        mock_postgres = MagicMock()
        mock_redis = MagicMock()
        mock_settings = MagicMock()
        mock_settings.postgres_url = "postgresql://localhost/db"
        mock_settings.redis_url = "redis://localhost:6379"

        app = create_app()

        with patch("api.main.get_settings", return_value=mock_settings), \
             patch("api.main.PostgresClient", return_value=mock_postgres), \
             patch("api.main.RedisCache", return_value=mock_redis), \
             patch("api.main._run_migrations"):

            async with lifespan(app):
                pass

        mock_redis.close.assert_called_once()

    @pytest.mark.anyio
    async def test_lifespan_postgres_failure_raises_runtime_error(self):
        mock_postgres = MagicMock()
        mock_postgres.connect.side_effect = Exception("Connection refused")
        mock_settings = MagicMock()
        mock_settings.postgres_url = "postgresql://localhost/db"
        mock_settings.redis_url = "redis://localhost:6379"

        app = create_app()

        with patch("api.main.get_settings", return_value=mock_settings), \
             patch("api.main.PostgresClient", return_value=mock_postgres), \
             patch("api.main.RedisCache", return_value=MagicMock()):

            with pytest.raises(RuntimeError, match="Cannot start"):
                async with lifespan(app):
                    pass

    @pytest.mark.anyio
    async def test_lifespan_redis_failure_sets_none(self):
        mock_postgres = MagicMock()
        mock_redis = MagicMock()
        mock_redis.connect.side_effect = Exception("Redis unavailable")
        mock_settings = MagicMock()
        mock_settings.postgres_url = "postgresql://localhost/db"
        mock_settings.redis_url = "redis://localhost:6379"

        app = create_app()

        with patch("api.main.get_settings", return_value=mock_settings), \
             patch("api.main.PostgresClient", return_value=mock_postgres), \
             patch("api.main.RedisCache", return_value=mock_redis), \
             patch("api.main._run_migrations"):

            async with lifespan(app):
                # Redis failure is non-fatal; state.redis becomes None
                assert app.state.redis is None


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------

class TestCreateApp:
    def test_creates_fastapi_app(self):
        from fastapi import FastAPI
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_title(self):
        app = create_app()
        assert app.title == "Ticket to Prompt"

    def test_app_version(self):
        app = create_app()
        assert app.version == APP_VERSION

    def test_app_version_constant(self):
        assert APP_VERSION == "0.2.0"

    def test_cors_middleware_present(self):
        from starlette.middleware.cors import CORSMiddleware
        app = create_app()
        middleware_types = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_types
