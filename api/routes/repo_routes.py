"""Repository indexing endpoints — project-scoped."""

import logging

from fastapi import APIRouter, Depends

from api.dependencies import get_redis, get_settings_dep, get_postgres
from api.schemas.repo import RepoIndexResponse
from auth.middleware import get_current_user, require_project_access
from storage.redis_cache import scoped_key
from workers.tasks import index_repository_full

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["indexing"])


@router.post("/index", response_model=RepoIndexResponse, status_code=202)
def index_repository(
    project_id: str,
    current_user=Depends(get_current_user),
    project=Depends(require_project_access),
    cache=Depends(get_redis),
):
    """Enqueue a repository indexing job for this project."""
    org_id = str(project["org_id"])
    repo_url = project["github_repo_url"]
    branch = project.get("default_branch", "main")
    repo_name = project.get("slug", project.get("name", ""))

    task = index_repository_full.delay(repo_url, repo_name, branch, project_id, org_id)
    job_id = task.id

    if cache is not None:
        cache.set(scoped_key(org_id, "indexing", job_id), {
            "status": "in_progress",
            "repo_url": repo_url,
            "project_id": project_id,
        })

    return RepoIndexResponse(
        status="indexing_started",
        job_id=job_id,
        repo_url=repo_url,
    )


@router.get("/index/{job_id}")
def get_index_status(
    project_id: str,
    job_id: str,
    current_user=Depends(get_current_user),
    project=Depends(require_project_access),
    cache=Depends(get_redis),
):
    """Return indexing job status."""
    org_id = str(project["org_id"])
    if cache is not None:
        status = cache.get(scoped_key(org_id, "indexing", job_id))
        if status:
            return status
    return {"status": "unknown", "job_id": job_id}
