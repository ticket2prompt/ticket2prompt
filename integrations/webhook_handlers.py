"""Webhook handlers for GitHub events."""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Request, HTTPException

from config.settings import get_settings
from workers.tasks import index_repository_incremental

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@dataclass
class WebhookEvent:
    """Parsed webhook event data."""
    event_type: str          # "push" or "pull_request"
    repo_full_name: str      # e.g. "org/repo"
    repo_clone_url: str
    default_branch: str
    before_sha: Optional[str] = None   # for push events
    after_sha: Optional[str] = None    # for push events
    ref: Optional[str] = None          # e.g. "refs/heads/main"


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature.

    Args:
        payload_body: Raw request body bytes.
        signature_header: Value of X-Hub-Signature-256 header (e.g. "sha256=abc123...").
        secret: The webhook secret configured in GitHub.

    Returns:
        True if signature matches, False otherwise.
    """
    if not signature_header or not secret:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header[7:]  # strip "sha256="
    mac = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256)
    computed = mac.hexdigest()
    return hmac.compare_digest(computed, expected_signature)


def parse_push_event(payload: dict) -> WebhookEvent:
    """Parse a GitHub push event payload into a WebhookEvent."""
    repo = payload.get("repository", {})
    return WebhookEvent(
        event_type="push",
        repo_full_name=repo.get("full_name", ""),
        repo_clone_url=repo.get("clone_url", ""),
        default_branch=repo.get("default_branch", "main"),
        before_sha=payload.get("before"),
        after_sha=payload.get("after"),
        ref=payload.get("ref"),
    )


def parse_pull_request_event(payload: dict) -> Optional[WebhookEvent]:
    """Parse a GitHub pull_request event payload.

    Returns None if the PR action is not 'closed' with merged=True.
    Only merged PRs should trigger indexing.
    """
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})

    if action != "closed" or not pr.get("merged", False):
        return None

    repo = payload.get("repository", {})
    base = pr.get("base", {})

    return WebhookEvent(
        event_type="pull_request",
        repo_full_name=repo.get("full_name", ""),
        repo_clone_url=repo.get("clone_url", ""),
        default_branch=base.get("ref", repo.get("default_branch", "main")),
        before_sha=pr.get("base", {}).get("sha"),
        after_sha=pr.get("merge_commit_sha"),
        ref=f"refs/heads/{base.get('ref', 'main')}",
    )


@router.post("/github")
async def handle_github_webhook(request: Request) -> dict:
    """Handle incoming GitHub webhook events.

    1. Verify HMAC-SHA256 signature
    2. Parse event type from X-GitHub-Event header
    3. Dispatch to appropriate parser
    4. Return acknowledgment
    """
    settings = get_settings()

    # Verify webhook secret is configured
    if not settings.github_webhook_secret:
        raise HTTPException(status_code=403, detail="Webhook secret not configured")

    # Read raw body for signature verification
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(body, signature, settings.github_webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse event type
    event_type = request.headers.get("X-GitHub-Event", "")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Dispatch based on event type
    if event_type == "push":
        event = parse_push_event(payload)

        # Only process pushes to the default branch
        expected_ref = f"refs/heads/{event.default_branch}"
        if event.ref != expected_ref:
            logger.info("Ignoring push to non-default branch: %s", event.ref)
            return {"status": "ignored", "reason": "non-default branch"}

        logger.info("Processing push event for %s (%s..%s)",
                    event.repo_full_name, event.before_sha, event.after_sha)

        index_repository_incremental.delay(
            event.repo_clone_url,
            event.repo_full_name,
            event.before_sha,
            event.after_sha,
        )
        return {"status": "accepted", "event_type": "push", "repo": event.repo_full_name}

    elif event_type == "pull_request":
        event = parse_pull_request_event(payload)

        if event is None:
            return {"status": "ignored", "reason": "PR not merged"}

        logger.info("Processing merged PR for %s", event.repo_full_name)

        index_repository_incremental.delay(
            event.repo_clone_url,
            event.repo_full_name,
            event.before_sha,
            event.after_sha,
        )
        return {"status": "accepted", "event_type": "pull_request", "repo": event.repo_full_name}

    else:
        logger.debug("Ignoring unsupported event type: %s", event_type)
        return {"status": "ignored", "reason": f"unsupported event: {event_type}"}
