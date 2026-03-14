"""Tests for webhook handlers.

All tests use FastAPI TestClient — no real HTTP calls.
"""
import hashlib
import hmac
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from integrations.webhook_handlers import (
    WebhookEvent,
    verify_signature,
    parse_push_event,
    parse_pull_request_event,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_signature(payload: bytes, secret: str) -> str:
    """Compute the HMAC-SHA256 signature like GitHub does."""
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _make_push_payload(
    repo_full_name: str = "org/repo",
    clone_url: str = "https://github.com/org/repo.git",
    default_branch: str = "main",
    ref: str = "refs/heads/main",
    before: str = "abc123",
    after: str = "def456",
) -> dict:
    return {
        "ref": ref,
        "before": before,
        "after": after,
        "repository": {
            "full_name": repo_full_name,
            "clone_url": clone_url,
            "default_branch": default_branch,
        },
    }


def _make_pr_payload(
    action: str = "closed",
    merged: bool = True,
    repo_full_name: str = "org/repo",
    clone_url: str = "https://github.com/org/repo.git",
    default_branch: str = "main",
    base_sha: str = "base123",
    merge_commit_sha: str = "merge456",
) -> dict:
    return {
        "action": action,
        "pull_request": {
            "merged": merged,
            "merge_commit_sha": merge_commit_sha,
            "base": {
                "ref": default_branch,
                "sha": base_sha,
            },
        },
        "repository": {
            "full_name": repo_full_name,
            "clone_url": clone_url,
            "default_branch": default_branch,
        },
    }


def _make_test_app(webhook_secret: str = "test-secret"):
    """Build a minimal FastAPI app using only the webhook router.

    Returns (app, mock_settings) — caller is responsible for patching
    get_settings before making requests.
    """
    from fastapi import FastAPI
    from integrations.webhook_handlers import router as webhook_router

    mock_settings = MagicMock()
    mock_settings.github_webhook_secret = webhook_secret

    app = FastAPI()
    app.include_router(webhook_router)
    return app, mock_settings


# ---------------------------------------------------------------------------
# Tests: verify_signature
# ---------------------------------------------------------------------------

class TestVerifySignature:
    def test_valid_signature_passes(self):
        payload = b'{"test": true}'
        secret = "my-secret"
        sig = _compute_signature(payload, secret)
        assert verify_signature(payload, sig, secret) is True

    def test_invalid_signature_returns_false(self):
        payload = b'{"test": true}'
        assert verify_signature(payload, "sha256=wronghash", "my-secret") is False

    def test_missing_signature_returns_false(self):
        assert verify_signature(b"data", "", "secret") is False

    def test_empty_secret_returns_false(self):
        assert verify_signature(b"data", "sha256=abc", "") is False

    def test_missing_sha256_prefix_returns_false(self):
        assert verify_signature(b"data", "md5=abc", "secret") is False


# ---------------------------------------------------------------------------
# Tests: parse_push_event
# ---------------------------------------------------------------------------

class TestParsePushEvent:
    def test_parse_push_event_extracts_fields(self):
        payload = _make_push_payload()
        event = parse_push_event(payload)

        assert isinstance(event, WebhookEvent)
        assert event.event_type == "push"
        assert event.repo_full_name == "org/repo"
        assert event.repo_clone_url == "https://github.com/org/repo.git"
        assert event.default_branch == "main"
        assert event.before_sha == "abc123"
        assert event.after_sha == "def456"
        assert event.ref == "refs/heads/main"

    def test_parse_push_event_custom_branch(self):
        payload = _make_push_payload(ref="refs/heads/develop", default_branch="develop")
        event = parse_push_event(payload)
        assert event.ref == "refs/heads/develop"
        assert event.default_branch == "develop"


# ---------------------------------------------------------------------------
# Tests: parse_pull_request_event
# ---------------------------------------------------------------------------

class TestParsePullRequestEvent:
    def test_merged_pr_returns_event(self):
        payload = _make_pr_payload(action="closed", merged=True)
        event = parse_pull_request_event(payload)

        assert event is not None
        assert event.event_type == "pull_request"
        assert event.repo_full_name == "org/repo"
        assert event.after_sha == "merge456"

    def test_opened_pr_returns_none(self):
        payload = _make_pr_payload(action="opened", merged=False)
        assert parse_pull_request_event(payload) is None

    def test_closed_without_merge_returns_none(self):
        payload = _make_pr_payload(action="closed", merged=False)
        assert parse_pull_request_event(payload) is None


# ---------------------------------------------------------------------------
# Tests: webhook endpoint
# ---------------------------------------------------------------------------

class TestWebhookEndpoint:
    def test_push_to_default_branch_accepted(self):
        secret = "test-secret"
        payload = _make_push_payload()
        body = json.dumps(payload).encode()
        sig = _compute_signature(body, secret)

        app, mock_settings = _make_test_app(webhook_secret=secret)
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings), \
             patch("integrations.webhook_handlers.index_repository_incremental") as mock_task:
            mock_task.delay = MagicMock()
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_type"] == "push"

    def test_push_to_non_default_branch_ignored(self):
        secret = "test-secret"
        payload = _make_push_payload(ref="refs/heads/feature-branch")
        body = json.dumps(payload).encode()
        sig = _compute_signature(body, secret)

        app, mock_settings = _make_test_app(webhook_secret=secret)
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings):
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_invalid_signature_returns_403(self):
        app, mock_settings = _make_test_app(webhook_secret="real-secret")
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings):
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=b'{"test": true}',
                headers={
                    "X-Hub-Signature-256": "sha256=wrong",
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 403

    def test_missing_signature_returns_403(self):
        app, mock_settings = _make_test_app(webhook_secret="real-secret")
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings):
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=b'{"test": true}',
                headers={
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 403

    def test_empty_webhook_secret_returns_403(self):
        """When webhook secret is not configured, all webhooks are rejected."""
        app, mock_settings = _make_test_app(webhook_secret="")
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings):
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=b'{"test": true}',
                headers={
                    "X-Hub-Signature-256": "sha256=abc",
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 403

    def test_merged_pr_triggers_accepted(self):
        secret = "test-secret"
        payload = _make_pr_payload(action="closed", merged=True)
        body = json.dumps(payload).encode()
        sig = _compute_signature(body, secret)

        app, mock_settings = _make_test_app(webhook_secret=secret)
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings), \
             patch("integrations.webhook_handlers.index_repository_incremental") as mock_task:
            mock_task.delay = MagicMock()
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_type"] == "pull_request"

    def test_opened_pr_ignored(self):
        secret = "test-secret"
        payload = _make_pr_payload(action="opened", merged=False)
        body = json.dumps(payload).encode()
        sig = _compute_signature(body, secret)

        app, mock_settings = _make_test_app(webhook_secret=secret)
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings):
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_unsupported_event_returns_ignored(self):
        secret = "test-secret"
        body = b'{"action": "created"}'
        sig = _compute_signature(body, secret)

        app, mock_settings = _make_test_app(webhook_secret=secret)
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings):
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "star",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_push_event_dispatches_background_task(self):
        """Push to default branch should enqueue index_repository_incremental via Celery."""
        secret = "test-secret"
        payload = _make_push_payload(
            repo_full_name="org/repo",
            clone_url="https://github.com/org/repo.git",
            before="abc123",
            after="def456",
        )
        body = json.dumps(payload).encode()
        sig = _compute_signature(body, secret)

        app, mock_settings = _make_test_app(webhook_secret=secret)
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings), \
             patch("integrations.webhook_handlers.index_repository_incremental") as mock_task:
            mock_delay = MagicMock()
            mock_task.delay = mock_delay
            client = TestClient(app, raise_server_exceptions=True)
            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        mock_delay.assert_called_once_with(
            "https://github.com/org/repo.git",
            "org/repo",
            "abc123",
            "def456",
        )

    def test_merged_pr_dispatches_background_task(self):
        """Merged PR webhook should enqueue index_repository_incremental via Celery."""
        secret = "test-secret"
        payload = _make_pr_payload(
            action="closed",
            merged=True,
            repo_full_name="org/repo",
            clone_url="https://github.com/org/repo.git",
            base_sha="base123",
            merge_commit_sha="merge456",
        )
        body = json.dumps(payload).encode()
        sig = _compute_signature(body, secret)

        app, mock_settings = _make_test_app(webhook_secret=secret)
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings), \
             patch("integrations.webhook_handlers.index_repository_incremental") as mock_task:
            mock_delay = MagicMock()
            mock_task.delay = mock_delay
            client = TestClient(app, raise_server_exceptions=True)
            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        mock_delay.assert_called_once_with(
            "https://github.com/org/repo.git",
            "org/repo",
            "base123",
            "merge456",
        )

    def test_malformed_json_returns_400(self):
        secret = "test-secret"
        body = b'not valid json'
        sig = _compute_signature(body, secret)

        app, mock_settings = _make_test_app(webhook_secret=secret)
        with patch("integrations.webhook_handlers.get_settings", return_value=mock_settings):
            client = TestClient(app)
            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
        assert response.status_code == 400
