"""Pydantic models for authentication and authorization."""

from typing import Optional

from pydantic import BaseModel


class UserCreate(BaseModel):
    """Payload for registering a new user and organization."""

    email: str
    password: str
    display_name: str
    org_name: str
    org_slug: str


class UserLogin(BaseModel):
    """Payload for authenticating an existing user."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT access token returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Claims decoded from a JWT access token."""

    sub: str       # user_id
    org_id: str
    role: str
    exp: int


class CurrentUser(BaseModel):
    """Resolved identity attached to the current request."""

    user_id: str
    email: str
    display_name: str
    org_id: str
    role: str


class ApiKeyCreate(BaseModel):
    """Payload for creating a new API key."""

    description: str
    expires_in_days: Optional[int] = None


class ApiKeyResponse(BaseModel):
    """API key details returned at creation time.

    ``key`` is only included in the creation response and is never stored in
    plaintext; subsequent lookups return only the prefix and metadata.
    """

    key: str          # raw key — only returned once
    key_prefix: str
    description: str
    expires_at: Optional[str] = None
