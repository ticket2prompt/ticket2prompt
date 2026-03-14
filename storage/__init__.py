"""Storage layer for PostgreSQL, Qdrant, and Redis."""

from storage.postgres import PostgresClient
from storage.redis_cache import RedisCache

__all__ = ["PostgresClient", "QdrantVectorStore", "RedisCache"]


def __getattr__(name):
    if name == "QdrantVectorStore":
        from storage.qdrant_client import QdrantVectorStore
        return QdrantVectorStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
