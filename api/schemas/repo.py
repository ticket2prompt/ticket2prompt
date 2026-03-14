"""Repository indexing endpoint schemas."""

from pydantic import BaseModel, Field


class RepoIndexRequest(BaseModel):
    """Request body for POST /repo/index."""

    repo_url: str = Field(
        ...,
        min_length=1,
        description="Git clone URL of the repository to index (e.g. ``\"https://github.com/org/repo.git\"``).",
    )
    branch: str = Field(
        default="main",
        description="Branch name to check out during indexing; defaults to ``\"main\"``.",
    )


class RepoIndexResponse(BaseModel):
    """Response body for POST /repo/index."""

    status: str = Field(
        description='Indexing job status; ``"indexing_started"`` immediately after enqueue.',
    )
    job_id: str = Field(
        description="Celery task ID; pass to ``GET /repo/index/{job_id}`` to poll progress.",
    )
    repo_url: str = Field(
        description="Git clone URL of the repository being indexed, echoed from the request.",
    )
