"""Redis caching layer with JSON serialization and TTL support."""

import json
import logging
from typing import Any, Callable, Optional

import redis

logger = logging.getLogger(__name__)


def scoped_key(org_id: str, *parts: str) -> str:
    """Build a tenant-scoped Redis key.

    Example: scoped_key("org123", "prompt", "proj456", "ticket789")
    → "org123:prompt:proj456:ticket789"
    """
    return f"{org_id}:{':'.join(parts)}"


class RedisCache:
    """JSON-based Redis cache with TTL support.

    All values are JSON-serialized before storage and deserialized on
    retrieval.  Connection errors are caught and logged so callers treat
    the cache as a best-effort layer rather than a hard dependency.

    Usage::

        cache = RedisCache(url="redis://localhost:6379", default_ttl=3600)
        cache.connect()

        cache.set("key", {"data": 1})
        value = cache.get("key")          # {"data": 1}
        cache.close()

    Or as a context manager::

        with RedisCache(url=REDIS_URL) as cache:
            value = cache.get_or_set("key", expensive_fn)
    """

    def __init__(self, url: str, default_ttl: int = 3600) -> None:
        """Initialise configuration without opening a connection.

        Args:
            url: Redis connection URL, e.g. ``redis://localhost:6379``.
            default_ttl: Seconds a key lives when no explicit TTL is given.
        """
        self._url = url
        self._default_ttl = default_ttl
        self._client: Optional[redis.Redis] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open the Redis connection and verify it with a PING."""
        self._client = redis.Redis.from_url(self._url, decode_responses=False)
        self._client.ping()
        logger.info("Redis connection established: %s", self._url)

    def close(self) -> None:
        """Close the Redis connection if it is open."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Redis connection closed.")

    def __enter__(self) -> "RedisCache":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Core cache operations
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Retrieve and JSON-deserialise a cached value.

        Returns ``None`` on cache miss or any Redis error.

        Args:
            key: Cache key to look up.
        """
        try:
            raw = self._client.get(key)
        except (redis.ConnectionError, redis.RedisError) as exc:
            logger.warning("Redis GET failed for key %r: %s", key, exc)
            return None

        if raw is None:
            return None

        return json.loads(raw)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """JSON-serialise *value* and store it under *key* with a TTL.

        Args:
            key: Cache key.
            value: JSON-serialisable value to cache.
            ttl: Time-to-live in seconds.  Falls back to ``default_ttl``.
        """
        expiry = ttl if ttl is not None else self._default_ttl
        serialized = json.dumps(value)
        try:
            self._client.set(key, serialized, ex=expiry)
        except (redis.ConnectionError, redis.RedisError) as exc:
            logger.warning("Redis SET failed for key %r: %s", key, exc)

    def delete(self, key: str) -> None:
        """Delete *key* from the cache.

        Args:
            key: Cache key to remove.
        """
        try:
            self._client.delete(key)
        except (redis.ConnectionError, redis.RedisError) as exc:
            logger.warning("Redis DELETE failed for key %r: %s", key, exc)

    def exists(self, key: str) -> bool:
        """Return ``True`` if *key* is present in the cache.

        Args:
            key: Cache key to check.
        """
        try:
            return bool(self._client.exists(key))
        except (redis.ConnectionError, redis.RedisError) as exc:
            logger.warning("Redis EXISTS failed for key %r: %s", key, exc)
            return False

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
    ) -> Any:
        """Cache-aside: return cached value or compute, cache, and return it.

        The *factory* callable is only invoked when the key is absent from
        the cache.  The freshly computed value is stored before returning.

        Args:
            key: Cache key.
            factory: Zero-argument callable that produces the value.
            ttl: Optional TTL override in seconds.

        Returns:
            Cached or freshly computed value.
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    # ------------------------------------------------------------------
    # Bulk invalidation helpers
    # ------------------------------------------------------------------

    def invalidate_pattern(self, pattern: str) -> None:
        """Delete all keys matching *pattern* using SCAN (not KEYS).

        Using SCAN avoids blocking the Redis server on large key spaces.

        Args:
            pattern: Glob-style pattern, e.g. ``"repo:myrepo:*"``.
        """
        try:
            for key in self._client.scan_iter(pattern):
                self._client.delete(key)
        except (redis.ConnectionError, redis.RedisError) as exc:
            logger.warning(
                "Redis invalidate_pattern failed for %r: %s", pattern, exc
            )

    def clear_repo_cache(self, repo: str) -> None:
        """Remove all cached entries associated with *repo*.

        Delegates to :meth:`invalidate_pattern` with the key prefix
        ``repo:<repo>:*``.

        Args:
            repo: Repository identifier used as part of the key namespace.
        """
        self.invalidate_pattern(f"repo:{repo}:*")

    def clear_project_cache(self, org_id: str, project_id: str) -> None:
        """Remove all cached entries for a specific project within an org."""
        self.invalidate_pattern(f"{org_id}:*:{project_id}:*")
