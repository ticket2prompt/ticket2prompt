"""FastAPI application entry point."""

import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.exceptions import register_exception_handlers
from api.schemas.common import HealthResponse
from config.settings import get_settings
from storage.postgres import PostgresClient
from storage.redis_cache import RedisCache

logger = logging.getLogger(__name__)

APP_VERSION = "0.2.0"

_SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "storage" / "schema.sql"


def _run_migrations(postgres: PostgresClient) -> None:
    """Apply schema.sql idempotently so tables and indexes are always in sync."""
    schema_sql = _SCHEMA_PATH.read_text()
    conn = postgres._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        logger.info("Database migrations applied successfully")
    except Exception:
        conn.rollback()
        raise
    finally:
        postgres._put_conn(conn)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of storage connections."""
    settings = get_settings()

    postgres = PostgresClient(settings.postgres_url)
    redis_cache = RedisCache(settings.redis_url)

    try:
        postgres.connect()
        _run_migrations(postgres)
    except Exception as exc:
        logger.error("PostgreSQL startup failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Cannot start: PostgreSQL unavailable — {exc}") from exc

    try:
        redis_cache.connect()
    except Exception:
        logger.warning("Redis connection failed; caching will be unavailable")
        redis_cache = None

    app.state.postgres = postgres
    app.state.redis = redis_cache

    yield

    if redis_cache is not None:
        redis_cache.close()
    if postgres is not None:
        postgres.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="Ticket to Prompt",
        version=APP_VERSION,
        description="Multi-tenant system to convert Jira tickets into context-rich prompts.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    from api.routes.auth_routes import router as auth_router
    from api.routes.org_routes import router as org_router
    from api.routes.team_routes import router as team_router
    from api.routes.project_routes import router as project_router
    from api.routes.jira_routes import router as jira_router
    from api.routes.jira_sync_routes import router as jira_sync_router
    from api.routes.prompt_routes import router as prompt_router
    from api.routes.repo_routes import router as repo_router
    from integrations.webhook_handlers import router as webhook_router

    application.include_router(auth_router)
    application.include_router(org_router)
    application.include_router(team_router)
    application.include_router(project_router)
    application.include_router(jira_router)
    application.include_router(jira_sync_router)
    application.include_router(repo_router)
    application.include_router(prompt_router)
    application.include_router(webhook_router)

    @application.get("/health", response_model=HealthResponse)
    def health_check():
        return HealthResponse(status="ok", version=APP_VERSION)

    return application


app = create_app()
