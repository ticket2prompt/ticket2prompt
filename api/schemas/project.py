"""Project endpoint schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1, pattern="^[a-z0-9-]+$")
    github_repo_url: str = Field(..., min_length=1)
    team_id: Optional[str] = None
    default_branch: str = Field(default="main")
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None  # plaintext, will be encrypted before storage
    github_token: Optional[str] = None  # plaintext, will be encrypted before storage
    collection_group: Optional[str] = None


class ProjectResponse(BaseModel):
    project_id: str
    org_id: str
    team_id: Optional[str] = None
    name: str
    slug: str
    github_repo_url: str
    default_branch: str
    collection_group: Optional[str] = None
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    has_jira_token: bool = False
    has_github_token: bool = False
    created_at: str
    updated_at: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    github_repo_url: Optional[str] = None
    default_branch: Optional[str] = None
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    github_token: Optional[str] = None
    collection_group: Optional[str] = None
