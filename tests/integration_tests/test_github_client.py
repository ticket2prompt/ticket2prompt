"""Tests for the GitHub API client.

All tests mock httpx.Client — no real GitHub API calls are made.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from integrations.github_client import (
    GitHubClient,
    GitHubClientError,
    GitHubRateLimitError,
    PullRequestInfo,
    RepoMetadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int, json_body: dict, headers: dict | None = None) -> MagicMock:
    """Build a mock httpx.Response with the given status, body, and headers."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_body
    response.headers = headers or {}
    return response


def _make_client(token: str = "test-token") -> GitHubClient:
    return GitHubClient(token=token, api_url="https://api.github.com")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetRepoMetadata:
    def test_get_repo_metadata_success(self):
        """Returns a populated RepoMetadata on a 200 response."""
        payload = {
            "full_name": "octocat/Hello-World",
            "default_branch": "main",
            "language": "Python",
            "clone_url": "https://github.com/octocat/Hello-World.git",
            "pushed_at": "2024-01-15T10:00:00Z",
        }
        mock_response = _make_response(200, payload)

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            result = client.get_repo_metadata("octocat", "Hello-World")

        assert isinstance(result, RepoMetadata)
        assert result.full_name == "octocat/Hello-World"
        assert result.default_branch == "main"
        assert result.language == "Python"
        assert result.clone_url == "https://github.com/octocat/Hello-World.git"
        assert result.last_pushed_at == "2024-01-15T10:00:00Z"

    def test_get_repo_metadata_language_none(self):
        """language field maps to None when the API returns null."""
        payload = {
            "full_name": "octocat/empty-repo",
            "default_branch": "main",
            "language": None,
            "clone_url": "https://github.com/octocat/empty-repo.git",
            "pushed_at": None,
        }
        mock_response = _make_response(200, payload)

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            result = client.get_repo_metadata("octocat", "empty-repo")

        assert result.language is None
        assert result.last_pushed_at is None

    def test_get_repo_metadata_not_found(self):
        """A 404 response raises GitHubClientError."""
        mock_response = _make_response(404, {"message": "Not Found"})

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            with pytest.raises(GitHubClientError, match="404"):
                client.get_repo_metadata("octocat", "nonexistent")


class TestGetPullRequestsForCommit:
    def test_get_pull_requests_for_commit(self):
        """Returns a list of PullRequestInfo objects parsed from the API response."""
        payload = [
            {
                "number": 42,
                "title": "Fix the thing",
                "user": {"login": "alice"},
                "merged_at": "2024-01-10T08:00:00Z",
            },
            {
                "number": 43,
                "title": "Add feature",
                "user": {"login": "bob"},
                "merged_at": None,
            },
        ]
        mock_response = _make_response(200, payload)

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            results = client.get_pull_requests_for_commit(
                "octocat", "Hello-World", "abc123def456"
            )

        assert len(results) == 2
        assert all(isinstance(pr, PullRequestInfo) for pr in results)

        first = results[0]
        assert first.pr_number == 42
        assert first.title == "Fix the thing"
        assert first.author == "alice"
        assert first.merged_at == "2024-01-10T08:00:00Z"

        second = results[1]
        assert second.pr_number == 43
        assert second.merged_at is None

    def test_get_pull_requests_for_commit_empty(self):
        """Returns an empty list when no PRs are associated with the commit."""
        mock_response = _make_response(200, [])

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            results = client.get_pull_requests_for_commit("octocat", "Hello-World", "deadbeef")

        assert results == []


class TestGetDefaultBranch:
    def test_get_default_branch(self):
        """Returns the default_branch string from the repo metadata endpoint."""
        payload = {
            "full_name": "octocat/Hello-World",
            "default_branch": "develop",
            "language": "Go",
            "clone_url": "https://github.com/octocat/Hello-World.git",
            "pushed_at": "2024-02-01T00:00:00Z",
        }
        mock_response = _make_response(200, payload)

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            branch = client.get_default_branch("octocat", "Hello-World")

        assert branch == "develop"


class TestRateLimitHandling:
    def test_rate_limit_raises_github_rate_limit_error(self):
        """A 403 with X-RateLimit-Remaining: 0 raises GitHubRateLimitError."""
        mock_response = _make_response(
            403,
            {"message": "API rate limit exceeded"},
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            with pytest.raises(GitHubRateLimitError):
                client.get_repo_metadata("octocat", "Hello-World")

    def test_rate_limit_error_includes_reset_time(self):
        """GitHubRateLimitError message includes the reset timestamp."""
        reset_ts = "1700000000"
        mock_response = _make_response(
            403,
            {"message": "API rate limit exceeded"},
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset_ts},
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            with pytest.raises(GitHubRateLimitError, match=reset_ts):
                client.get_repo_metadata("octocat", "Hello-World")

    def test_403_without_rate_limit_header_raises_client_error(self):
        """A 403 without X-RateLimit-Remaining: 0 raises plain GitHubClientError."""
        mock_response = _make_response(
            403,
            {"message": "Forbidden"},
            headers={"X-RateLimit-Remaining": "50"},
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            with pytest.raises(GitHubClientError):
                client.get_repo_metadata("octocat", "Hello-World")

        # Must NOT be a rate-limit error
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            with pytest.raises(GitHubClientError) as exc_info:
                client.get_repo_metadata("octocat", "Hello-World")
            assert not isinstance(exc_info.value, GitHubRateLimitError)


class TestNetworkError:
    def test_network_error_raises_github_client_error(self):
        """An httpx network-level error is wrapped in GitHubClientError."""
        # httpx.RequestError requires a `request` kwarg; use a subclass that
        # overrides __str__ to carry a message without needing a real request.
        class _ConnError(httpx.RequestError):
            def __init__(self, message: str) -> None:
                self._message = message

            def __str__(self) -> str:
                return self._message

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.side_effect = _ConnError("Connection refused")
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = _make_client()
            with pytest.raises(GitHubClientError, match="Connection refused"):
                client.get_repo_metadata("octocat", "Hello-World")


class TestAuthorizationHeader:
    def test_request_sends_bearer_token(self):
        """Every request must include the Authorization: Bearer <token> header."""
        payload = {
            "full_name": "octocat/Hello-World",
            "default_branch": "main",
            "language": "Python",
            "clone_url": "https://github.com/octocat/Hello-World.git",
            "pushed_at": "2024-01-15T10:00:00Z",
        }
        mock_response = _make_response(200, payload)

        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_response
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client = GitHubClient(token="secret-token", api_url="https://api.github.com")
            client.get_repo_metadata("octocat", "Hello-World")

            _, call_kwargs = mock_http.request.call_args
            headers = call_kwargs.get("headers", {})
            assert headers.get("Authorization") == "Bearer secret-token"
