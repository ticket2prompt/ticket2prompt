"""Organization endpoint schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1, pattern="^[a-z0-9-]+$")


class OrgResponse(BaseModel):
    org_id: str
    name: str
    slug: str
    created_at: str


class OrgMemberAdd(BaseModel):
    email: str = Field(..., min_length=1)
    role: str = Field(default="member", pattern="^(org_admin|member)$")


class OrgMemberResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str
