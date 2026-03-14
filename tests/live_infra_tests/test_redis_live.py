"""Integration tests for RedisCache against real Redis."""

import time

import pytest

pytestmark = pytest.mark.integration


class TestBasicOperations:
    def test_set_and_get(self, redis_cache):
        redis_cache.set("test_key", {"data": 42})
        result = redis_cache.get("test_key")
        assert result == {"data": 42}

    def test_get_missing_key(self, redis_cache):
        result = redis_cache.get("nonexistent")
        assert result is None

    def test_delete(self, redis_cache):
        redis_cache.set("del_key", "value")
        redis_cache.delete("del_key")
        assert redis_cache.get("del_key") is None

    def test_exists(self, redis_cache):
        redis_cache.set("exists_key", "value")
        assert redis_cache.exists("exists_key") is True
        assert redis_cache.exists("no_key") is False


class TestCacheAside:
    def test_get_or_set_miss(self, redis_cache):
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"computed": True}

        result = redis_cache.get_or_set("gos_key", factory)
        assert result == {"computed": True}
        assert call_count == 1

    def test_get_or_set_hit(self, redis_cache):
        redis_cache.set("gos_hit", {"cached": True})

        result = redis_cache.get_or_set("gos_hit", lambda: {"new": True})
        assert result == {"cached": True}


class TestBulkOperations:
    def test_invalidate_pattern(self, redis_cache):
        redis_cache.set("repo:myrepo:file1", "a")
        redis_cache.set("repo:myrepo:file2", "b")
        redis_cache.set("repo:other:file1", "c")

        redis_cache.invalidate_pattern("repo:myrepo:*")

        assert redis_cache.get("repo:myrepo:file1") is None
        assert redis_cache.get("repo:myrepo:file2") is None
        assert redis_cache.get("repo:other:file1") is not None

    def test_clear_repo_cache(self, redis_cache):
        redis_cache.set("repo:test-repo:key1", "v1")
        redis_cache.set("repo:test-repo:key2", "v2")

        redis_cache.clear_repo_cache("test-repo")

        assert redis_cache.get("repo:test-repo:key1") is None
        assert redis_cache.get("repo:test-repo:key2") is None


class TestTTL:
    def test_ttl_expiration(self, redis_cache):
        redis_cache.set("ttl_key", "value", ttl=1)
        assert redis_cache.get("ttl_key") == "value"
        time.sleep(2)
        assert redis_cache.get("ttl_key") is None
