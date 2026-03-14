"""Jira ticket endpoint schemas."""

from pydantic import BaseModel, Field
from typing import List


class JiraTicketRequest(BaseModel):
    """Request body for POST /jira/ticket."""

    title: str = Field(
        ...,
        min_length=1,
        description="Ticket title or summary (maps to the Jira summary field).",
    )
    description: str = Field(
        default="",
        description="Full ticket description providing context for the pipeline.",
    )
    acceptance_criteria: str = Field(
        default="",
        description="Acceptance criteria text used to sharpen retrieval and prompt focus.",
    )
    comments: List[str] = Field(
        default=[],
        description="Ordered list of ticket comments, oldest first, for additional context.",
    )
    repo: str = Field(
        default="",
        description="Optional repository name override. Resolved from project if empty.",
    )


class JiraTicketResponse(BaseModel):
    """Response body for POST /jira/ticket."""

    status: str = Field(
        description='Processing status; ``"completed"`` on success.',
    )
    ticket_id: str = Field(
        description="UUID assigned to this processing request; use it to retrieve the prompt later.",
    )
    prompt_text: str = Field(
        description="Full generated prompt text ready to paste into a code-generation LLM.",
    )
    token_count: int = Field(
        description="Approximate token count of ``prompt_text`` after context compression.",
    )
    files_referenced: List[str] = Field(
        description="Relative file paths included as context in the generated prompt.",
    )
    symbols_referenced: List[str] = Field(
        description="Fully-qualified symbol names (functions, classes) surfaced in the prompt.",
    )
