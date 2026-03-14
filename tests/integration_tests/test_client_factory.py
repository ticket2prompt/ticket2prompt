"""Tests for integrations/client_factory.py."""

from unittest.mock import MagicMock, patch

import pytest

from auth.credentials import encrypt_credential
from integrations.client_factory import build_github_client, build_jira_client
from integrations.github_client import GitHubClient
from integrations.jira_client import JiraClient


ENCRYPTION_KEY = "test-encryption-key"


def _encrypt(plaintext: str) -> str:
    return encrypt_credential(plaintext, ENCRYPTION_KEY)


# ---------------------------------------------------------------------------
# build_jira_client
# ---------------------------------------------------------------------------

class TestBuildJiraClient:
    def _project(self, base_url="https://example.atlassian.net", email="user@example.com", token="mytoken"):
        return {
            "jira_base_url": base_url,
            "jira_email": email,
            "jira_api_token_encrypted": _encrypt(token),
        }

    def test_returns_jira_client_instance(self):
        project = self._project()
        client = build_jira_client(project, ENCRYPTION_KEY)
        assert isinstance(client, JiraClient)

    def test_decrypts_token_correctly(self):
        plaintext_token = "my-secret-api-token"
        project = self._project(token=plaintext_token)

        with patch("integrations.jira_client.httpx.Client") as mock_http:
            client = build_jira_client(project, ENCRYPTION_KEY)

        # Check that the auth tuple passed to httpx contains the decrypted token
        call_kwargs = mock_http.call_args[1]
        assert call_kwargs["auth"][1] == plaintext_token

    def test_passes_base_url(self):
        project = self._project(base_url="https://mycompany.atlassian.net")

        with patch("integrations.jira_client.httpx.Client"):
            client = build_jira_client(project, ENCRYPTION_KEY)

        assert client._base_url == "https://mycompany.atlassian.net"

    def test_missing_base_url_raises_value_error(self):
        project = {
            "jira_email": "user@example.com",
            "jira_api_token_encrypted": _encrypt("token"),
        }
        with pytest.raises(ValueError, match="missing Jira configuration"):
            build_jira_client(project, ENCRYPTION_KEY)

    def test_missing_email_raises_value_error(self):
        project = {
            "jira_base_url": "https://example.atlassian.net",
            "jira_api_token_encrypted": _encrypt("token"),
        }
        with pytest.raises(ValueError, match="missing Jira configuration"):
            build_jira_client(project, ENCRYPTION_KEY)

    def test_missing_token_raises_value_error(self):
        project = {
            "jira_base_url": "https://example.atlassian.net",
            "jira_email": "user@example.com",
        }
        with pytest.raises(ValueError, match="missing Jira configuration"):
            build_jira_client(project, ENCRYPTION_KEY)

    def test_none_base_url_raises_value_error(self):
        project = {
            "jira_base_url": None,
            "jira_email": "user@example.com",
            "jira_api_token_encrypted": _encrypt("token"),
        }
        with pytest.raises(ValueError):
            build_jira_client(project, ENCRYPTION_KEY)

    def test_empty_string_base_url_raises_value_error(self):
        project = {
            "jira_base_url": "",
            "jira_email": "user@example.com",
            "jira_api_token_encrypted": _encrypt("token"),
        }
        with pytest.raises(ValueError):
            build_jira_client(project, ENCRYPTION_KEY)

    def test_empty_project_dict_raises_value_error(self):
        with pytest.raises(ValueError):
            build_jira_client({}, ENCRYPTION_KEY)


# ---------------------------------------------------------------------------
# build_github_client
# ---------------------------------------------------------------------------

class TestBuildGithubClient:
    def _project(self, token="ghp_testtoken"):
        return {"github_token_encrypted": _encrypt(token)}

    def test_returns_github_client_instance(self):
        project = self._project()
        client = build_github_client(project, ENCRYPTION_KEY)
        assert isinstance(client, GitHubClient)

    def test_decrypts_token_correctly(self):
        plaintext_token = "ghp_real_token_here"
        project = self._project(token=plaintext_token)
        client = build_github_client(project, ENCRYPTION_KEY)
        # GitHubClient stores the token; check it was decrypted correctly
        assert client._token == plaintext_token

    def test_missing_github_token_raises_value_error(self):
        project = {}
        with pytest.raises(ValueError, match="missing GitHub token"):
            build_github_client(project, ENCRYPTION_KEY)

    def test_none_github_token_raises_value_error(self):
        project = {"github_token_encrypted": None}
        with pytest.raises(ValueError, match="missing GitHub token"):
            build_github_client(project, ENCRYPTION_KEY)

    def test_empty_github_token_raises_value_error(self):
        project = {"github_token_encrypted": ""}
        with pytest.raises(ValueError, match="missing GitHub token"):
            build_github_client(project, ENCRYPTION_KEY)

    def test_different_tokens_produce_different_clients(self):
        p1 = self._project(token="token-one")
        p2 = self._project(token="token-two")
        c1 = build_github_client(p1, ENCRYPTION_KEY)
        c2 = build_github_client(p2, ENCRYPTION_KEY)
        assert c1._token != c2._token
