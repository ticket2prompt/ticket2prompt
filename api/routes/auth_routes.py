"""Authentication endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_postgres, get_settings_dep
from auth.models import UserCreate, UserLogin, TokenResponse, ApiKeyCreate, ApiKeyResponse, CurrentUser
from auth.security import hash_password, verify_password, create_access_token, generate_api_key
from auth.middleware import get_current_user, require_org_admin
from auth.postgres_auth import (
    create_user, get_user_by_email, create_org, add_org_member, create_api_key
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    request: UserCreate,
    postgres=Depends(get_postgres),
    settings=Depends(get_settings_dep),
):
    """Register a new user and create their organization."""
    existing = get_user_by_email(postgres, request.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    pw_hash = hash_password(request.password)
    user = create_user(postgres, request.email, pw_hash, request.display_name)
    org = create_org(postgres, request.org_name, request.org_slug)
    add_org_member(postgres, user["user_id"], org["org_id"], "org_admin")

    token, expires_in = create_access_token(
        user_id=user["user_id"],
        org_id=str(org["org_id"]),
        role="org_admin",
        settings=settings,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/login", response_model=TokenResponse)
def login(
    request: UserLogin,
    postgres=Depends(get_postgres),
    settings=Depends(get_settings_dep),
):
    """Authenticate and return a JWT token."""
    user = get_user_by_email(postgres, request.email)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account disabled")

    # Get the user's first org membership for the token
    orgs = postgres.list_orgs_for_user(user["user_id"])
    if not orgs:
        raise HTTPException(status_code=403, detail="No organization membership found")

    org = orgs[0]
    token, expires_in = create_access_token(
        user_id=str(user["user_id"]),
        org_id=str(org["org_id"]),
        role=org["role"],
        settings=settings,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me")
def me(current_user: CurrentUser = Depends(get_current_user)):
    """Return the current authenticated user's info."""
    return current_user.model_dump()


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=201)
def create_api_key_endpoint(
    request: ApiKeyCreate,
    current_user=Depends(require_org_admin),
    postgres=Depends(get_postgres),
):
    """Generate an API key for the organization. Requires org_admin."""
    from datetime import datetime, timedelta, timezone

    raw_key, key_hash, key_prefix = generate_api_key()

    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

    create_api_key(
        postgres,
        org_id=current_user.org_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        description=request.description,
        expires_at=expires_at,
    )

    return ApiKeyResponse(
        key=raw_key,
        key_prefix=key_prefix,
        description=request.description,
        expires_at=str(expires_at) if expires_at else None,
    )
