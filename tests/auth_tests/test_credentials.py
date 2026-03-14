"""Tests for credential encryption/decryption."""

import pytest
from auth.credentials import encrypt_credential, decrypt_credential


class TestCredentialEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        key = "my-secret-encryption-key"
        plaintext = "github_pat_abc123xyz"

        encrypted = encrypt_credential(plaintext, key)
        assert encrypted != plaintext

        decrypted = decrypt_credential(encrypted, key)
        assert decrypted == plaintext

    def test_wrong_key_fails(self):
        encrypted = encrypt_credential("secret", "key-1")
        with pytest.raises(Exception):
            decrypt_credential(encrypted, "key-2")

    def test_different_encryptions_for_same_input(self):
        key = "test-key"
        e1 = encrypt_credential("same", key)
        e2 = encrypt_credential("same", key)
        # Fernet uses random IV so ciphertexts differ
        assert e1 != e2
        # But both decrypt to same value
        assert decrypt_credential(e1, key) == "same"
        assert decrypt_credential(e2, key) == "same"

    def test_empty_string(self):
        key = "test-key"
        encrypted = encrypt_credential("", key)
        assert decrypt_credential(encrypted, key) == ""
