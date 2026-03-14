"""Tests for auth security functions."""

import time
import pytest

from auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    generate_api_key,
    hash_api_key,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "test-password-123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        pw = "same-password"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2  # bcrypt uses random salt
        assert verify_password(pw, h1)
        assert verify_password(pw, h2)


class TestJWT:
    def _make_settings(self, secret="test-secret", hours=1):
        """Create a mock Settings object."""

        class MockSettings:
            jwt_secret = secret
            jwt_expiry_hours = hours

        return MockSettings()

    def test_create_and_decode_token(self):
        settings = self._make_settings()
        token, expires_in = create_access_token("user-1", "org-1", "org_admin", settings)
        assert isinstance(token, str)
        assert expires_in == 3600  # 1 hour

        payload = decode_token(token, "test-secret")
        assert payload.sub == "user-1"
        assert payload.org_id == "org-1"
        assert payload.role == "org_admin"

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_token("invalid-token", "test-secret")

    def test_wrong_secret_raises(self):
        settings = self._make_settings(secret="secret-1")
        token, _ = create_access_token("user-1", "org-1", "member", settings)
        with pytest.raises(Exception):
            decode_token(token, "wrong-secret")


class TestApiKey:
    def test_generate_api_key_format(self):
        raw, key_hash, prefix = generate_api_key()
        assert raw.startswith("ttp_")
        assert len(prefix) == 8
        assert raw[:8] == prefix
        assert len(key_hash) == 64  # SHA-256 hex

    def test_hash_api_key_matches(self):
        raw, expected_hash, _ = generate_api_key()
        assert hash_api_key(raw) == expected_hash

    def test_different_keys_each_call(self):
        raw1, _, _ = generate_api_key()
        raw2, _, _ = generate_api_key()
        assert raw1 != raw2
