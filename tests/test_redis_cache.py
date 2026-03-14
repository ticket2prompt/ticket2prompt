"""Tests for the Redis cache client."""

import json
from unittest.mock import MagicMock, patch, call

import pytest

from storage.redis_cache import RedisCache


# ---------------------------------------------------------------------------
# Redis availability detection (used for integration test skip marker)
# ---------------------------------------------------------------------------

def redis_available() -> bool:
    try:
        import redis
        r = redis.Redis.from_url("redis://localhost:6379")
        r.ping()
        r.close()
        return True
    except Exception:
        return False


skip_no_redis = pytest.mark.skipif(
    not redis_available(), reason="Redis not available"
)


# ---------------------------------------------------------------------------
# Unit tests (all Redis I/O mocked)
# ---------------------------------------------------------------------------

class TestRedisCacheInit:
    def test_redis_cache_init_stores_config(self):
        cache = RedisCache(url="redis://localhost:6379", default_ttl=1800)

        assert cache._url == "redis://localhost:6379"
        assert cache._default_ttl == 1800
        assert cache._client is None


class TestRedisCacheSet:
    def test_set_serializes_to_json(self):
        cache = RedisCache(url="redis://localhost:6379")
        mock_client = MagicMock()
        cache._client = mock_client

        value = {"foo": "bar", "count": 42}
        cache.set("mykey", value)

        mock_client.set.assert_called_once_with(
            "mykey",
            json.dumps(value),
            ex=3600,
        )

    def test_set_uses_default_ttl(self):
        cache = RedisCache(url="redis://localhost:6379", default_ttl=7200)
        mock_client = MagicMock()
        cache._client = mock_client

        cache.set("somekey", {"data": 1})

        _, kwargs = mock_client.set.call_args
        assert kwargs["ex"] == 7200

    def test_set_uses_custom_ttl(self):
        cache = RedisCache(url="redis://localhost:6379", default_ttl=3600)
        mock_client = MagicMock()
        cache._client = mock_client

        cache.set("somekey", {"data": 1}, ttl=120)

        _, kwargs = mock_client.set.call_args
        assert kwargs["ex"] == 120


class TestRedisCacheGet:
    def test_get_deserializes_json(self):
        cache = RedisCache(url="redis://localhost:6379")
        mock_client = MagicMock()
        cache._client = mock_client

        payload = {"result": "hello", "score": 0.95}
        mock_client.get.return_value = json.dumps(payload).encode()

        result = cache.get("somekey")

        mock_client.get.assert_called_once_with("somekey")
        assert result == payload

    def test_get_returns_none_on_miss(self):
        cache = RedisCache(url="redis://localhost:6379")
        mock_client = MagicMock()
        mock_client.get.return_value = None
        cache._client = mock_client

        result = cache.get("missing_key")

        assert result is None

    def test_connection_error_handled_gracefully(self):
        import redis as redis_lib

        cache = RedisCache(url="redis://localhost:6379")
        mock_client = MagicMock()
        mock_client.get.side_effect = redis_lib.ConnectionError("refused")
        cache._client = mock_client

        result = cache.get("any_key")

        assert result is None


class TestRedisCacheGetOrSet:
    def test_get_or_set_returns_cached(self):
        cache = RedisCache(url="redis://localhost:6379")
        mock_client = MagicMock()
        cached_value = {"cached": True}
        mock_client.get.return_value = json.dumps(cached_value).encode()
        cache._client = mock_client

        factory = MagicMock()
        result = cache.get_or_set("thekey", factory)

        assert result == cached_value
        factory.assert_not_called()

    def test_get_or_set_calls_factory_on_miss(self):
        cache = RedisCache(url="redis://localhost:6379")
        mock_client = MagicMock()
        mock_client.get.return_value = None
        cache._client = mock_client

        fresh_value = {"fresh": "data"}
        factory = MagicMock(return_value=fresh_value)

        result = cache.get_or_set("thekey", factory)

        assert result == fresh_value
        factory.assert_called_once()
        mock_client.set.assert_called_once_with(
            "thekey",
            json.dumps(fresh_value),
            ex=3600,
        )


# ---------------------------------------------------------------------------
# Integration tests (require a live Redis on localhost:6379)
# ---------------------------------------------------------------------------

INTEGRATION_PREFIX = "test:"


@pytest.fixture
def live_cache():
    """Provide a connected RedisCache and clean up test keys afterwards."""
    cache = RedisCache(url="redis://localhost:6379", default_ttl=60)
    cache.connect()

    yield cache

    # Cleanup all keys written during the test run
    for key in cache._client.scan_iter(f"{INTEGRATION_PREFIX}*"):
        cache._client.delete(key)

    cache.close()


@skip_no_redis
class TestRedisCacheIntegration:
    def test_set_and_get_roundtrip(self, live_cache):
        key = f"{INTEGRATION_PREFIX}roundtrip"
        value = {"hello": "world", "numbers": [1, 2, 3]}

        live_cache.set(key, value)
        result = live_cache.get(key)

        assert result == value

    def test_delete_key(self, live_cache):
        key = f"{INTEGRATION_PREFIX}to_delete"
        live_cache.set(key, {"temporary": True})

        live_cache.delete(key)
        result = live_cache.get(key)

        assert result is None

    def test_exists(self, live_cache):
        key = f"{INTEGRATION_PREFIX}existence"
        live_cache.set(key, {"exists": True})

        assert live_cache.exists(key) is True
        live_cache.delete(key)
        assert live_cache.exists(key) is False

    def test_get_or_set_caches_result(self, live_cache):
        key = f"{INTEGRATION_PREFIX}get_or_set"
        call_count = {"n": 0}

        def factory():
            call_count["n"] += 1
            return {"computed": True}

        # First call should invoke factory
        result1 = live_cache.get_or_set(key, factory)
        # Second call should read from cache
        result2 = live_cache.get_or_set(key, factory)

        assert result1 == {"computed": True}
        assert result2 == {"computed": True}
        assert call_count["n"] == 1

    def test_invalidate_pattern_deletes_matching(self, live_cache):
        live_cache.set(f"{INTEGRATION_PREFIX}match:a", {"a": 1})
        live_cache.set(f"{INTEGRATION_PREFIX}match:b", {"b": 2})
        live_cache.set(f"{INTEGRATION_PREFIX}keep:c", {"c": 3})

        live_cache.invalidate_pattern(f"{INTEGRATION_PREFIX}match:*")

        assert live_cache.get(f"{INTEGRATION_PREFIX}match:a") is None
        assert live_cache.get(f"{INTEGRATION_PREFIX}match:b") is None
        assert live_cache.get(f"{INTEGRATION_PREFIX}keep:c") == {"c": 3}

    def test_clear_repo_cache(self, live_cache):
        live_cache.set("repo:myrepo:file1", {"content": "a"})
        live_cache.set("repo:myrepo:file2", {"content": "b"})
        live_cache.set("repo:otherrepo:file3", {"content": "c"})

        live_cache.clear_repo_cache("myrepo")

        assert live_cache.get("repo:myrepo:file1") is None
        assert live_cache.get("repo:myrepo:file2") is None
        assert live_cache.get("repo:otherrepo:file3") == {"content": "c"}

        # Cleanup the non-prefixed keys manually since fixture only cleans INTEGRATION_PREFIX
        live_cache.delete("repo:otherrepo:file3")
