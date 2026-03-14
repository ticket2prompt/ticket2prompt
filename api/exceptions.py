"""API domain exceptions and FastAPI exception handlers."""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class TicketNotFoundError(Exception):
    """Raised when a prompt for a given ticket ID is not found in the cache.

    Converted to an HTTP 404 response by
    :func:`register_exception_handlers`.
    """

    pass


class PipelineError(Exception):
    """Raised when the LangGraph pipeline fails during any processing stage.

    Stages that can trigger this exception include ticket expansion,
    embedding generation, vector search, graph expansion, ranking, context
    compression, and prompt generation.  Converted to an HTTP 500 response
    by :func:`register_exception_handlers`.
    """

    pass


class IndexingError(Exception):
    """Raised when repository indexing fails inside a Celery worker.

    Converted to an HTTP 500 response by
    :func:`register_exception_handlers`.
    """

    pass


def register_exception_handlers(app):
    """Register domain exception handlers on a FastAPI application instance.

    Maps each domain exception to a structured JSON error response with an
    appropriate HTTP status code.  Must be called once during application
    startup (e.g. in ``create_app()``).

    Registered handlers:

    * :exc:`TicketNotFoundError` → HTTP 404 with ``error="ticket_not_found"``
    * :exc:`PipelineError` → HTTP 500 with ``error="pipeline_error"``
    * :exc:`IndexingError` → HTTP 500 with ``error="indexing_error"``

    Args:
        app: The ``FastAPI`` application instance on which to register the
            exception handlers.
    """

    @app.exception_handler(TicketNotFoundError)
    async def ticket_not_found_handler(request: Request, exc: TicketNotFoundError):
        """Handle TicketNotFoundError and return a 404 JSON response.

        Args:
            request: The incoming FastAPI ``Request`` object.
            exc: The :exc:`TicketNotFoundError` that was raised.

        Returns:
            JSONResponse with HTTP status 404 and an ``error`` / ``detail``
            payload.
        """
        return JSONResponse(
            status_code=404,
            content={"error": "ticket_not_found", "detail": str(exc)},
        )

    @app.exception_handler(PipelineError)
    async def pipeline_error_handler(request: Request, exc: PipelineError):
        """Handle PipelineError and return a 500 JSON response.

        Args:
            request: The incoming FastAPI ``Request`` object.
            exc: The :exc:`PipelineError` that was raised.

        Returns:
            JSONResponse with HTTP status 500 and an ``error`` / ``detail``
            payload.
        """
        logger.error("Pipeline error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "pipeline_error", "detail": str(exc)},
        )

    @app.exception_handler(IndexingError)
    async def indexing_error_handler(request: Request, exc: IndexingError):
        """Handle IndexingError and return a 500 JSON response.

        Args:
            request: The incoming FastAPI ``Request`` object.
            exc: The :exc:`IndexingError` that was raised.

        Returns:
            JSONResponse with HTTP status 500 and an ``error`` / ``detail``
            payload.
        """
        logger.error("Indexing error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "indexing_error", "detail": str(exc)},
        )
