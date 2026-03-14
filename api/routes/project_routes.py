"""Project management endpoints."""

import logging
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_postgres, get_settings_dep, get_redis
from api.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from auth.middleware import get_current_user
from auth.postgres_auth import get_org_membership
from auth.credentials import encrypt_credential
from storage.qdrant_client import get_qdrant_for_project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orgs/{org_id}/projects", tags=["projects"])


def _project_to_response(p: dict) -> ProjectResponse:
    return ProjectResponse(
        project_id=str(p["project_id"]),
        org_id=str(p["org_id"]),
        team_id=str(p["team_id"]) if p.get("team_id") else None,
        name=p["name"],
        slug=p["slug"],
        github_repo_url=p["github_repo_url"],
        default_branch=p.get("default_branch", "main"),
        collection_group=p.get("collection_group"),
        jira_base_url=p.get("jira_base_url"),
        jira_email=p.get("jira_email"),
        has_jira_token=bool(p.get("jira_api_token_encrypted")),
        has_github_token=bool(p.get("github_token_encrypted")),
        created_at=str(p["created_at"]),
        updated_at=str(p["updated_at"]),
    )


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    org_id: str,
    request: ProjectCreate,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
    settings=Depends(get_settings_dep),
):
    """Create a new project in the organization."""
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    github_token_enc = None
    if request.github_token and settings.credential_encryption_key:
        github_token_enc = encrypt_credential(request.github_token, settings.credential_encryption_key)

    jira_token_enc = None
    if request.jira_api_token and settings.credential_encryption_key:
        jira_token_enc = encrypt_credential(request.jira_api_token, settings.credential_encryption_key)

    project = postgres.create_project(
        org_id=org_id,
        name=request.name,
        slug=request.slug,
        github_repo_url=request.github_repo_url,
        team_id=request.team_id,
        github_token_encrypted=github_token_enc,
        jira_base_url=request.jira_base_url,
        jira_email=request.jira_email,
        jira_api_token_encrypted=jira_token_enc,
        default_branch=request.default_branch,
        collection_group=request.collection_group,
    )
    return _project_to_response(project)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    org_id: str,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
):
    """List projects in the organization."""
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    projects = postgres.list_projects(org_id)
    return [_project_to_response(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    org_id: str,
    project_id: str,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
):
    """Get project details."""
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    project = postgres.get_project(project_id)
    if not project or str(project["org_id"]) != org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    org_id: str,
    project_id: str,
    request: ProjectUpdate,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
    settings=Depends(get_settings_dep),
):
    """Update project settings."""
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    project = postgres.get_project(project_id)
    if not project or str(project["org_id"]) != org_id:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = request.model_dump(exclude_none=True)

    # Encrypt secrets before storage
    if "github_token" in updates and settings.credential_encryption_key:
        updates["github_token_encrypted"] = encrypt_credential(updates.pop("github_token"), settings.credential_encryption_key)
    elif "github_token" in updates:
        updates.pop("github_token")

    if "jira_api_token" in updates and settings.credential_encryption_key:
        updates["jira_api_token_encrypted"] = encrypt_credential(updates.pop("jira_api_token"), settings.credential_encryption_key)
    elif "jira_api_token" in updates:
        updates.pop("jira_api_token")

    if not updates:
        return _project_to_response(project)

    updated = postgres.update_project(project_id, **updates)
    return _project_to_response(updated)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    org_id: str,
    project_id: str,
    current_user=Depends(get_current_user),
    postgres=Depends(get_postgres),
    cache=Depends(get_redis),
    settings=Depends(get_settings_dep),
):
    """Delete a project and all associated data."""
    membership = get_org_membership(postgres, current_user.user_id, org_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    project = postgres.get_project(project_id)
    if not project or str(project["org_id"]) != org_id:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete Qdrant vectors for both code and jira collections
    for content_type in ("code", "jira"):
        try:
            qdrant = get_qdrant_for_project(project, settings.qdrant_url, settings.embedding_dim, content_type)
            qdrant.connect()
            try:
                qdrant.delete_by_project(project_id)
            finally:
                qdrant.close()
        except Exception:
            logger.warning("Failed to delete %s vectors for project %s", content_type, project_id)

    # Clear Redis cache
    if cache is not None:
        try:
            cache.clear_project_cache(org_id, project_id)
            cache.invalidate_pattern(f"{org_id}:indexing:*")
        except Exception:
            logger.warning("Failed to clear cache for project %s", project_id)

    # Delete all Postgres data
    postgres.delete_project(project_id, org_id)

    # Remove cloned repo directory
    repo_dir = os.path.join(settings.clone_base_dir, org_id, project_id)
    shutil.rmtree(repo_dir, ignore_errors=True)

    return None
