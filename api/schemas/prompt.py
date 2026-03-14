"""Prompt retrieval endpoint schemas."""

from pydantic import BaseModel, Field
from typing import List


class PromptResponse(BaseModel):
    """Response body for GET /prompt/{ticket_id}."""

    ticket_id: str = Field(
        description="UUID of the ticket whose prompt is being retrieved.",
    )
    prompt_text: str = Field(
        description="Full generated prompt text as stored when the ticket was originally processed.",
    )
    token_count: int = Field(
        description="Approximate token count of ``prompt_text`` after context compression.",
    )
    files_referenced: List[str] = Field(
        description="Relative file paths that were included as context in the generated prompt.",
    )
    symbols_referenced: List[str] = Field(
        description="Fully-qualified symbol names (functions, classes) surfaced in the prompt.",
    )
