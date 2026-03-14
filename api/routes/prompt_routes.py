"""Prompt retrieval endpoints — project-scoped."""

import logging

from fastapi import APIRouter, Depends

from api.dependencies import get_redis
from api.exceptions import TicketNotFoundError
from api.schemas.prompt import PromptResponse
from auth.middleware import get_current_user, require_project_access
from storage.redis_cache import scoped_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["prompts"])


@router.get("/prompt/{ticket_id}", response_model=PromptResponse)
def get_prompt(
    project_id: str,
    ticket_id: str,
    current_user=Depends(get_current_user),
    project=Depends(require_project_access),
    cache=Depends(get_redis),
):
    """Retrieve a previously generated prompt."""
    org_id = str(project["org_id"])
    if cache is None:
        raise TicketNotFoundError(f"No prompt found for ticket_id={ticket_id}")

    cached = cache.get(scoped_key(org_id, "prompt", project_id, ticket_id))
    if cached is None:
        raise TicketNotFoundError(f"No prompt found for ticket_id={ticket_id}")

    return PromptResponse(ticket_id=ticket_id, **cached)
