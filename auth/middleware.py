"""FastAPI dependency functions for authentication and authorization."""

import logging

import jwt
from fastapi import Depends, HTTPException, Request, status

from api.dependencies import get_postgres, get_settings_dep
from auth.models import CurrentUser
from auth.security import decode_token, hash_api_key
from config.settings import Settings

logger = logging.getLogger(__name__)


def get_current_user(
    request: Request,
    postgres=Depends(get_postgres),
    settings: Settings = Depends(get_settings_dep),
) -> CurrentUser:
    """Resolve the authenticated user from the incoming request.

    Checks the ``Authorization: Bearer <token>`` header first.  If absent,
    falls back to the ``X-API-Key`` header and performs a database lookup.

    Args:
        request: The current FastAPI request object.
        postgres: The ``PostgresClient`` instance from application state.
        settings: Application settings used to decode the JWT.

    Returns:
        A ``CurrentUser`` representing the authenticated caller.

    Raises:
        HTTPException 401: If no valid credential is provided or the token /
            API key is invalid or expired.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        return _resolve_jwt(token, settings)

    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return _resolve_api_key(api_key, postgres)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_jwt(token: str, settings: Settings) -> CurrentUser:
    """Decode a JWT and return the corresponding ``CurrentUser``.

    Args:
        token: The raw JWT string extracted from the Authorization header.
        settings: Application settings supplying the JWT secret.

    Returns:
        A ``CurrentUser`` populated from the token claims.

    Raises:
        HTTPException 401: If the token is expired or otherwise invalid.
    """
    try:
        payload = decode_token(token, settings.jwt_secret)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.debug("Invalid JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # We need user email and display_name — these are not in the JWT claims so
    # we embed a minimal CurrentUser with what we have.  Routes that need the
    # full profile can fetch it separately.
    return CurrentUser(
        user_id=payload.sub,
        email="",           # not stored in JWT; fetch from DB if required
        display_name="",    # not stored in JWT; fetch from DB if required
        org_id=payload.org_id,
        role=payload.role,
    )


def _resolve_api_key(raw_key: str, postgres) -> CurrentUser:
    """Look up an API key and return the corresponding ``CurrentUser``.

    Args:
        raw_key: The plaintext API key from the ``X-API-Key`` header.
        postgres: The ``PostgresClient`` instance used to query the database.

    Returns:
        A ``CurrentUser`` scoped to the organization that owns the key.

    Raises:
        HTTPException 401: If the key is not found, inactive, or expired.
    """
    from datetime import datetime, timezone

    key_hash = hash_api_key(raw_key)
    row = postgres.get_api_key_by_hash(key_hash)

    if row is None or not row.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_at = row.get("expires_at")
    if expires_at is not None:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(tz=timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return CurrentUser(
        user_id="",                        # API keys are org-scoped, not user-scoped
        email="",
        display_name="",
        org_id=str(row["org_id"]),
        role=row.get("role", "api_key"),
    )


def require_org_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Raise 403 if the caller is not an org admin.

    Args:
        current_user: The resolved identity from ``get_current_user``.

    Returns:
        *current_user* unchanged when the role check passes.

    Raises:
        HTTPException 403: If the user's role is not ``org_admin``.
    """
    if current_user.role != "org_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin role required",
        )
    return current_user


def require_project_access(
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    postgres=Depends(get_postgres),
) -> dict:
    """Verify the caller belongs to the organization that owns *project_id*.

    Args:
        project_id: The UUID of the project to look up.
        current_user: The resolved identity from ``get_current_user``.
        postgres: The ``PostgresClient`` instance from application state.

    Returns:
        The project row as a dict when access is granted.

    Raises:
        HTTPException 404: If the project does not exist.
        HTTPException 403: If the project belongs to a different organization.
    """
    project = postgres.get_project(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id!r} not found",
        )

    if str(project["org_id"]) != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this project is not permitted",
        )

    return project
