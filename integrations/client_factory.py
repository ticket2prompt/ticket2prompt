"""Factory functions for building per-project integration clients."""

from auth.credentials import decrypt_credential
from integrations.github_client import GitHubClient
from integrations.jira_client import JiraClient


def build_jira_client(project: dict, encryption_key: str) -> JiraClient:
    """Build a JiraClient using a project's stored encrypted credentials.

    Args:
        project: Project dict with jira_base_url, jira_email, jira_api_token_encrypted.
        encryption_key: The Fernet encryption key for decrypting stored credentials.

    Returns:
        Configured JiraClient instance.

    Raises:
        ValueError: If required Jira configuration is missing.
    """
    base_url = project.get("jira_base_url")
    email = project.get("jira_email")
    token_encrypted = project.get("jira_api_token_encrypted")

    if not base_url or not email or not token_encrypted:
        raise ValueError("Project is missing Jira configuration (base_url, email, or api_token)")

    api_token = decrypt_credential(token_encrypted, encryption_key)
    return JiraClient(base_url=base_url, email=email, api_token=api_token)


def build_github_client(project: dict, encryption_key: str) -> GitHubClient:
    """Build a GitHubClient using a project's stored encrypted credentials.

    Args:
        project: Project dict with github_token_encrypted.
        encryption_key: The Fernet encryption key for decrypting stored credentials.

    Returns:
        Configured GitHubClient instance.

    Raises:
        ValueError: If GitHub token is missing.
    """
    token_encrypted = project.get("github_token_encrypted")

    if not token_encrypted:
        raise ValueError("Project is missing GitHub token")

    token = decrypt_credential(token_encrypted, encryption_key)
    return GitHubClient(token=token)
