"""Organization management endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_postgres
from api.schemas.org import OrgCreate, OrgResponse, OrgMemberAdd, OrgMemberResponse
from auth.middleware import get_current_user, require_org_admin
from auth.postgres_auth import get_user_by_email, add_org_member

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.post("", response_model=OrgResponse, status_code=201)
def create_org(
    request: OrgCreate,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
):
    """Create a new organization. The current user becomes org_admin."""
    org = postgres.create_org(request.name, request.slug)
    add_org_member(postgres, current_user.user_id, org["org_id"], "org_admin")
    return OrgResponse(
        org_id=str(org["org_id"]),
        name=org["name"],
        slug=org["slug"],
        created_at=str(org["created_at"]),
    )


@router.get("", response_model=list[OrgResponse])
def list_orgs(
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
):
    """List organizations the current user belongs to."""
    orgs = postgres.list_orgs_for_user(current_user.user_id)
    return [
        OrgResponse(
            org_id=str(o["org_id"]),
            name=o["name"],
            slug=o["slug"],
            created_at=str(o["created_at"]),
        )
        for o in orgs
    ]


@router.get("/{org_id}", response_model=OrgResponse)
def get_org(
    org_id: str,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
):
    """Get organization details. User must be a member."""
    from auth.postgres_auth import get_org_membership
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    org = postgres.get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrgResponse(
        org_id=str(org["org_id"]),
        name=org["name"],
        slug=org["slug"],
        created_at=str(org["created_at"]),
    )


@router.post("/{org_id}/members", response_model=OrgMemberResponse, status_code=201)
def add_member(
    org_id: str,
    request: OrgMemberAdd,
    current_user=Depends(require_org_admin),
    postgres=Depends(get_postgres),
):
    """Add a member to the organization. Requires org_admin role."""
    if current_user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Not admin of this organization")
    user = get_user_by_email(postgres, request.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    membership = add_org_member(postgres, user["user_id"], org_id, request.role)
    return OrgMemberResponse(
        user_id=str(user["user_id"]),
        email=user["email"],
        display_name=user["display_name"],
        role=membership["role"],
    )
