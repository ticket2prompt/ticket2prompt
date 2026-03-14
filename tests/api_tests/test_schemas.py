"""Tests for new API schemas."""

import pytest
from pydantic import ValidationError

from api.schemas.org import OrgCreate, OrgResponse
from api.schemas.team import TeamCreate, TeamResponse
from api.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate


class TestOrgCreate:
    def test_valid(self):
        org = OrgCreate(name="Acme Corp", slug="acme-corp")
        assert org.name == "Acme Corp"
        assert org.slug == "acme-corp"

    def test_invalid_slug(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="Test", slug="Invalid Slug!")

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="", slug="valid")


class TestProjectCreate:
    def test_valid_minimal(self):
        p = ProjectCreate(
            name="My Project",
            slug="my-project",
            github_repo_url="https://github.com/org/repo",
        )
        assert p.default_branch == "main"
        assert p.collection_group is None

    def test_valid_with_all_fields(self):
        p = ProjectCreate(
            name="Full Project",
            slug="full-project",
            github_repo_url="https://github.com/org/repo",
            team_id="team-123",
            jira_base_url="https://jira.example.com",
            jira_email="bot@example.com",
            jira_api_token="secret",
            github_token="ghp_abc",
            collection_group="backend-group",
        )
        assert p.collection_group == "backend-group"
        assert p.jira_api_token == "secret"

    def test_invalid_slug_rejected(self):
        with pytest.raises(ValidationError):
            ProjectCreate(
                name="Test",
                slug="UPPERCASE",
                github_repo_url="https://github.com/org/repo",
            )


class TestProjectUpdate:
    def test_partial_update(self):
        u = ProjectUpdate(name="New Name")
        dumped = u.model_dump(exclude_none=True)
        assert dumped == {"name": "New Name"}

    def test_empty_update(self):
        u = ProjectUpdate()
        dumped = u.model_dump(exclude_none=True)
        assert dumped == {}


class TestProjectResponse:
    def test_has_token_flags(self):
        r = ProjectResponse(
            project_id="p1", org_id="o1", name="Test", slug="test",
            github_repo_url="https://github.com/org/repo",
            default_branch="main",
            has_jira_token=True, has_github_token=False,
            created_at="2024-01-01", updated_at="2024-01-01",
        )
        assert r.has_jira_token is True
        assert r.has_github_token is False
