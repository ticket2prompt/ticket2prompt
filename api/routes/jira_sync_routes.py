"""Jira ticket sync endpoints."""

import logging

from fastapi import APIRouter, Depends

from api.dependencies import get_redis
from auth.middleware import get_current_user, require_project_access
from storage.redis_cache import scoped_key
from workers.tasks import sync_jira_tickets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/jira", tags=["jira-sync"])


@router.post("/sync", status_code=202)
def trigger_jira_sync(
    project_id: str,
    current_user=Depends(get_current_user),
    project=Depends(require_project_access),
    cache=Depends(get_redis),
):
    """Trigger a Jira ticket sync for this project."""
    org_id = str(project["org_id"])

    task = sync_jira_tickets.delay(project_id)
    job_id = task.id

    if cache is not None:
        cache.set(scoped_key(org_id, "jira_sync", job_id), {
            "status": "in_progress",
            "project_id": project_id,
        })

    return {"status": "sync_started", "job_id": job_id}


@router.get("/sync/{job_id}")
def get_sync_status(
    project_id: str,
    job_id: str,
    current_user=Depends(get_current_user),
    project=Depends(require_project_access),
    cache=Depends(get_redis),
):
    """Check Jira sync job status."""
    org_id = str(project["org_id"])
    if cache is not None:
        status = cache.get(scoped_key(org_id, "jira_sync", job_id))
        if status:
            return status
    return {"status": "unknown", "job_id": job_id}
