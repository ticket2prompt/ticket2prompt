"""GitHub API client."""

from dataclasses import dataclass

import httpx


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitHubClientError(Exception):
    """Raised for GitHub API errors (HTTP errors, network failures)."""


class GitHubRateLimitError(GitHubClientError):
    """Raised when the GitHub API rate limit is exhausted (403 + remaining=0)."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RepoMetadata:
    full_name: str
    default_branch: str
    language: str | None
    clone_url: str
    last_pushed_at: str | None


@dataclass
class PullRequestInfo:
    pr_number: int
    title: str
    author: str
    merged_at: str | None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GitHubClient:
    """Synchronous GitHub REST API client backed by httpx."""

    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        self._token = token
        self._api_url = api_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
        """Return metadata for the given repository."""
        data = self._request("GET", f"/repos/{owner}/{repo}")
        return RepoMetadata(
            full_name=data["full_name"],
            default_branch=data["default_branch"],
            language=data.get("language"),
            clone_url=data["clone_url"],
            last_pushed_at=data.get("pushed_at"),
        )

    def get_pull_requests_for_commit(
        self, owner: str, repo: str, commit_sha: str
    ) -> list[PullRequestInfo]:
        """Return all pull requests associated with the given commit SHA.

        Uses GitHub's "list pull requests associated with a commit" endpoint:
        GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls
        """
        data = self._request("GET", f"/repos/{owner}/{repo}/commits/{commit_sha}/pulls")
        return [
            PullRequestInfo(
                pr_number=pr["number"],
                title=pr["title"],
                author=pr["user"]["login"],
                merged_at=pr.get("merged_at"),
            )
            for pr in data
        ]

    def get_default_branch(self, owner: str, repo: str) -> str:
        """Return the default branch name for the given repository."""
        return self.get_repo_metadata(owner, repo).default_branch

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Execute an HTTP request and return the parsed JSON body.

        Raises:
            GitHubRateLimitError: when a 403 response has X-RateLimit-Remaining: 0.
            GitHubClientError: for any other HTTP error or network failure.
        """
        url = f"{self._api_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **kwargs.pop("headers", {}),
        }
        try:
            with httpx.Client() as http:
                response = http.request(method, url, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise GitHubClientError(str(exc)) from exc

        self._check_rate_limit(response)

        if response.status_code >= 400:
            raise GitHubClientError(
                f"GitHub API error {response.status_code} for {method} {path}"
            )

        return response.json()

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """Raise GitHubRateLimitError when the rate limit is exhausted.

        GitHub returns 403 with X-RateLimit-Remaining: 0 when the limit is hit.
        """
        if (
            response.status_code == 403
            and str(response.headers.get("X-RateLimit-Remaining", "")) == "0"
        ):
            reset = response.headers.get("X-RateLimit-Reset", "unknown")
            raise GitHubRateLimitError(
                f"GitHub rate limit exceeded. Resets at: {reset}"
            )
