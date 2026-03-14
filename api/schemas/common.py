"""Common API response schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(
        description='Service health status; ``"ok"`` when all dependencies are reachable.',
    )
    version: str = Field(
        description="Application version string (e.g. ``\"1.0.0\"``).",
    )


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: str = Field(
        description="Machine-readable error code identifying the error type (e.g. ``\"pipeline_error\"``).",
    )
    detail: Optional[str] = Field(
        default=None,
        description="Human-readable description of the error; omitted when not applicable.",
    )
