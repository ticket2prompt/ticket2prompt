"""Jira ticket intake endpoints — project-scoped."""

import logging
import os
import uuid

from fastapi import APIRouter, Depends

from api.dependencies import get_postgres, get_redis, get_settings_dep
from api.exceptions import PipelineError
from api.schemas.ticket import JiraTicketRequest, JiraTicketResponse
from auth.middleware import get_current_user, require_project_access
from retrieval import TicketInput
from storage.qdrant_client import get_qdrant_for_project
from storage.redis_cache import scoped_key
from workflows.langgraph_pipeline import run_pipeline
from workflows.pipeline_steps import PipelineConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["tickets"])


@router.post("/ticket", response_model=JiraTicketResponse)
def process_ticket(
    project_id: str,
    request: JiraTicketRequest,
    current_user=Depends(get_current_user),
    project=Depends(require_project_access),
    postgres=Depends(get_postgres),
    cache=Depends(get_redis),
    settings=Depends(get_settings_dep),
):
    """Process a Jira ticket and generate a context-rich prompt for a specific project."""
    ticket_id = str(uuid.uuid4())
    org_id = str(project["org_id"])

    # Build project-scoped Qdrant clients
    code_qdrant = get_qdrant_for_project(project, settings.qdrant_url, settings.embedding_dim, "code")
    code_qdrant.connect()

    jira_qdrant = None
    try:
        jira_qdrant = get_qdrant_for_project(project, settings.qdrant_url, settings.embedding_dim, "jira")
        jira_qdrant.connect()
    except Exception:
        logger.debug("Jira Qdrant collection not available for project %s", project_id)

    # Resolve repo name from project config
    repo = project.get("slug", project.get("name", ""))

    ticket = TicketInput(
        title=request.title,
        description=request.description,
        acceptance_criteria=request.acceptance_criteria,
        comments=request.comments,
        repo=repo,
    )

    repo_base_path = os.path.join(settings.clone_base_dir, org_id, project_id)
    pipeline_config = PipelineConfig(
        postgres=postgres,
        qdrant=code_qdrant,
        cache=cache,
        jira_qdrant=jira_qdrant,
        org_id=org_id,
        project_id=project_id,
        repo_base_path=repo_base_path,
    )

    try:
        result = run_pipeline(pipeline_config, ticket)
    except Exception as exc:
        logger.error("Pipeline failed for ticket %s: %s", ticket_id, exc)
        raise PipelineError(f"Pipeline failed: {exc}") from exc
    finally:
        code_qdrant.close()
        if jira_qdrant:
            jira_qdrant.close()

    generated_prompt = result["generated_prompt"]

    prompt_data = {
        "prompt_text": generated_prompt.prompt_text,
        "token_count": generated_prompt.token_count,
        "files_referenced": generated_prompt.files_referenced,
        "symbols_referenced": generated_prompt.symbols_referenced,
    }

    if cache is not None:
        cache.set(scoped_key(org_id, "prompt", project_id, ticket_id), prompt_data)

    return JiraTicketResponse(
        status="completed",
        ticket_id=ticket_id,
        **prompt_data,
    )
