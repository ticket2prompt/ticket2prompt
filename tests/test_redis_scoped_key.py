"""Tests for Redis scoped key helper."""

from storage.redis_cache import scoped_key


class TestScopedKey:
    def test_basic(self):
        assert scoped_key("org1", "prompt", "proj1", "ticket1") == "org1:prompt:proj1:ticket1"

    def test_single_part(self):
        assert scoped_key("org1", "health") == "org1:health"

    def test_empty_org(self):
        assert scoped_key("", "key") == ":key"
