"""Tests for Qdrant multi-tenant collection naming."""

from storage.qdrant_client import get_collection_name, get_qdrant_for_project


class TestCollectionNaming:
    def test_standalone_project(self):
        project = {"project_id": "abc-123", "collection_group": None}
        assert get_collection_name(project, "code") == "proj_abc-123_code"
        assert get_collection_name(project, "jira") == "proj_abc-123_jira"

    def test_grouped_project(self):
        project = {"project_id": "abc-123", "collection_group": "backend-services"}
        assert get_collection_name(project, "code") == "group_backend-services_code"
        assert get_collection_name(project, "jira") == "group_backend-services_jira"

    def test_empty_collection_group_treated_as_standalone(self):
        project = {"project_id": "abc-123", "collection_group": ""}
        assert get_collection_name(project, "code") == "proj_abc-123_code"

    def test_grouped_projects_share_collection(self):
        proj_a = {"project_id": "a", "collection_group": "shared"}
        proj_b = {"project_id": "b", "collection_group": "shared"}
        assert get_collection_name(proj_a, "code") == get_collection_name(proj_b, "code")


class TestQdrantFactory:
    def test_creates_store_with_correct_collection(self):
        project = {"project_id": "test-proj", "collection_group": None}
        store = get_qdrant_for_project(project, "http://localhost:6333", 384, "code")
        assert store._collection_name == "proj_test-proj_code"
        assert store._vector_size == 384
