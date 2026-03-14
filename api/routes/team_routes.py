"""Team management endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_postgres
from api.schemas.team import TeamCreate, TeamResponse, TeamMemberAdd
from auth.middleware import get_current_user
from auth.postgres_auth import get_org_membership

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orgs/{org_id}/teams", tags=["teams"])


@router.post("", response_model=TeamResponse, status_code=201)
def create_team(
    org_id: str,
    request: TeamCreate,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
):
    """Create a new team in the organization."""
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    team = postgres.create_team(org_id, request.name)
    return TeamResponse(
        team_id=str(team["team_id"]),
        org_id=str(team["org_id"]),
        name=team["name"],
        created_at=str(team["created_at"]),
    )


@router.get("", response_model=list[TeamResponse])
def list_teams(
    org_id: str,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
):
    """List teams in the organization."""
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    teams = postgres.list_teams(org_id)
    return [
        TeamResponse(
            team_id=str(t["team_id"]),
            org_id=str(t["org_id"]),
            name=t["name"],
            created_at=str(t["created_at"]),
        )
        for t in teams
    ]


@router.post("/{team_id}/members", status_code=201)
def add_team_member(
    org_id: str,
    team_id: str,
    request: TeamMemberAdd,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
):
    """Add a member to a team."""
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    team = postgres.get_team(team_id)
    if not team or str(team["org_id"]) != org_id:
        raise HTTPException(status_code=404, detail="Team not found")
    result = postgres.add_team_member(request.user_id, team_id, request.role)
    return {"status": "added", "team_id": team_id, "user_id": request.user_id, "role": result["role"]}
