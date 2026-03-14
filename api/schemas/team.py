"""Team endpoint schemas."""

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1)


class TeamResponse(BaseModel):
    team_id: str
    org_id: str
    name: str
    created_at: str


class TeamMemberAdd(BaseModel):
    user_id: str = Field(..., min_length=1)
    role: str = Field(default="member", pattern="^(team_admin|member)$")
