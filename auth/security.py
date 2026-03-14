"""Core security utilities: password hashing, JWT, and API key generation."""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt

from auth.models import TokenPayload
from config.settings import Settings


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*.

    Args:
        password: The plaintext password to hash.

    Returns:
        A bcrypt hash string suitable for storage.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* password.

    Args:
        plain: The plaintext password provided by the user.
        hashed: The bcrypt hash retrieved from storage.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(
    user_id: str,
    org_id: str,
    role: str,
    settings: Settings,
) -> tuple[str, int]:
    """Create a signed JWT access token.

    Args:
        user_id: The subject claim (user's UUID).
        org_id: The organization the token is scoped to.
        role: The user's role within that organization.
        settings: Application settings supplying jwt_secret and
            jwt_expiry_hours.

    Returns:
        A (token, expires_in_seconds) tuple where *token* is the encoded JWT
        string and *expires_in_seconds* is the lifetime in seconds.
    """
    expiry_seconds = settings.jwt_expiry_hours * 3600
    exp = datetime.now(tz=timezone.utc) + timedelta(seconds=expiry_seconds)
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expiry_seconds


def decode_token(token: str, secret: str) -> TokenPayload:
    """Decode and validate a JWT, returning its claims as a ``TokenPayload``.

    Args:
        token: The encoded JWT string.
        secret: The HMAC secret used to verify the signature.

    Returns:
        A ``TokenPayload`` with the decoded claims.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is malformed or the signature is
            invalid.
    """
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    return TokenPayload(
        sub=payload["sub"],
        org_id=payload["org_id"],
        role=payload["role"],
        exp=payload["exp"],
    )


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key with its hash and display prefix.

    The raw key has the form ``ttp_<32 hex chars>`` and is only returned once
    at creation time.  Only the SHA-256 hash is persisted.

    Returns:
        A (raw_key, key_hash, key_prefix) tuple where:
        - *raw_key* is the full plaintext key to return to the caller.
        - *key_hash* is the SHA-256 digest used for storage and lookup.
        - *key_prefix* is the first 8 characters of the raw key, safe to
          display in listings.
    """
    raw_key = "ttp_" + secrets.token_hex(16)
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix


def hash_api_key(key: str) -> str:
    """Return the SHA-256 hex digest of *key*.

    Args:
        key: The raw API key string to hash.

    Returns:
        A lowercase hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(key.encode()).hexdigest()
