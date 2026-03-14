"""FastAPI dependency injection factories."""

from functools import lru_cache

from fastapi import Depends, HTTPException, Request

from config.settings import Settings, get_settings


@lru_cache
def get_settings_dep() -> Settings:
    """Return a cached application ``Settings`` singleton.

    Uses ``functools.lru_cache`` so that ``get_settings()`` is called only
    once per process lifetime, keeping config parsing out of the hot path.

    Returns:
        Settings: The application settings object populated from environment
        variables and/or a ``.env`` file.
    """
    return get_settings()


def get_postgres(request: Request):
    """Return the ``PostgresClient`` stored on application state.

    Args:
        request: The current FastAPI ``Request`` object, injected
            automatically by the dependency system.

    Raises:
        HTTPException: 503 if PostgreSQL is unavailable.
    """
    postgres = request.app.state.postgres
    if postgres is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return postgres


def get_redis(request: Request):
    """Return the ``RedisCache`` stored on application state.

    Args:
        request: The current FastAPI ``Request`` object, injected
            automatically by the dependency system.

    Returns:
        The ``RedisCache`` instance attached to ``app.state.redis`` at
        startup, or ``None`` if Redis is unavailable or was not configured.
    """
    return request.app.state.redis


def get_qdrant(request: Request):
    """Return the ``QdrantVectorStore`` stored on application state.

    Args:
        request: The current FastAPI ``Request`` object, injected
            automatically by the dependency system.

    Returns:
        The ``QdrantVectorStore`` instance attached to ``app.state.qdrant``
        at startup, or ``None`` if the vector store was not initialised.
    """
    return request.app.state.qdrant


def get_pipeline_config(request: Request):
    """Return the ``PipelineConfig`` stored on application state.

    Args:
        request: The current FastAPI ``Request`` object, injected
            automatically by the dependency system.

    Returns:
        The ``PipelineConfig`` instance attached to ``app.state.pipeline_config``
        at startup, containing all settings required to run the LangGraph
        retrieval pipeline.
    """
    return request.app.state.pipeline_config
