"""Fernet-based encryption for per-project credential storage."""

import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet(key: str) -> Fernet:
    """Derive a 32-byte Fernet key from an arbitrary string key.

    Fernet requires exactly 32 url-safe base64-encoded bytes.  We derive that
    from *key* by taking its SHA-256 digest and base64-encoding the result.

    Args:
        key: The raw credential encryption key from settings.

    Returns:
        A ``Fernet`` instance ready for encrypt/decrypt operations.
    """
    digest = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_credential(plaintext: str, key: str) -> str:
    """Encrypt *plaintext* with Fernet symmetric encryption.

    Args:
        plaintext: The secret value to encrypt (e.g. a Jira API token).
        key: The ``credential_encryption_key`` from application settings.

    Returns:
        A base64-encoded ciphertext string safe for storage in the database.
    """
    return _fernet(key).encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str, key: str) -> str:
    """Decrypt a Fernet-encrypted *ciphertext*.

    Args:
        ciphertext: The base64-encoded ciphertext produced by
            ``encrypt_credential``.
        key: The ``credential_encryption_key`` from application settings.

    Returns:
        The original plaintext string.

    Raises:
        cryptography.fernet.InvalidToken: If the ciphertext is corrupt or the
            key does not match.
    """
    return _fernet(key).decrypt(ciphertext.encode()).decode()
