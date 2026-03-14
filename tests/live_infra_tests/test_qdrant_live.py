"""Integration tests for QdrantVectorStore against real Qdrant."""

import pytest

pytestmark = pytest.mark.integration


def _make_embedding(symbol_id, vector):
    """Create a mock embedding object with symbol_id and embedding attributes."""

    class Emb:
        def __init__(self, sid, vec):
            self.symbol_id = sid
            self.embedding = vec

    return Emb(symbol_id, vector)


def _make_unit_vector(dim=384, index=0):
    """Create a unit vector with 1.0 at the given index."""
    vec = [0.0] * dim
    vec[index % dim] = 1.0
    return vec


class TestCollectionManagement:
    def test_ensure_collection(self, qdrant_store):
        info = qdrant_store.get_collection_info()
        assert info["points_count"] == 0

    def test_collection_info_after_upsert(self, qdrant_store):
        emb = _make_embedding("info::sym1", _make_unit_vector(index=0))
        payload = {"name": "sym1", "type": "function", "file_path": "a.py", "repo": "r"}
        qdrant_store.upsert_embeddings([emb], [payload])

        info = qdrant_store.get_collection_info()
        assert info["points_count"] >= 1


class TestSearchOperations:
    def test_upsert_and_search(self, qdrant_store):
        embeddings = [
            _make_embedding("search::a", _make_unit_vector(index=0)),
            _make_embedding("search::b", _make_unit_vector(index=1)),
        ]
        payloads = [
            {"name": "a", "type": "function", "file_path": "a.py", "repo": "repo"},
            {"name": "b", "type": "function", "file_path": "b.py", "repo": "repo"},
        ]
        qdrant_store.upsert_embeddings(embeddings, payloads)

        results = qdrant_store.search(_make_unit_vector(index=0), top_k=5)
        assert len(results) >= 1
        assert results[0]["symbol_id"] == "search::a"

    def test_search_with_repo_filter(self, qdrant_store):
        embeddings = [
            _make_embedding("filter::a", _make_unit_vector(index=0)),
            _make_embedding("filter::b", _make_unit_vector(index=0)),
        ]
        payloads = [
            {"name": "a", "type": "function", "file_path": "a.py", "repo": "repo1"},
            {"name": "b", "type": "function", "file_path": "b.py", "repo": "repo2"},
        ]
        qdrant_store.upsert_embeddings(embeddings, payloads)

        results = qdrant_store.search(
            _make_unit_vector(index=0), top_k=10, filters={"repo": "repo1"}
        )
        assert all(r["payload"]["repo"] == "repo1" for r in results)


class TestDeleteOperations:
    def test_delete_by_repo(self, qdrant_store):
        embeddings = [
            _make_embedding("delrepo::a", _make_unit_vector(index=0)),
            _make_embedding("delrepo::b", _make_unit_vector(index=1)),
        ]
        payloads = [
            {"name": "a", "type": "function", "file_path": "a.py", "repo": "delete-me"},
            {"name": "b", "type": "function", "file_path": "b.py", "repo": "keep-me"},
        ]
        qdrant_store.upsert_embeddings(embeddings, payloads)

        qdrant_store.delete_by_repo("delete-me")

        results = qdrant_store.search(_make_unit_vector(index=0), top_k=10)
        repos = [r["payload"]["repo"] for r in results]
        assert "delete-me" not in repos

    def test_delete_by_symbol_ids(self, qdrant_store):
        embeddings = [
            _make_embedding("delsym::a", _make_unit_vector(index=0)),
            _make_embedding("delsym::b", _make_unit_vector(index=1)),
        ]
        payloads = [
            {"name": "a", "type": "function", "file_path": "a.py", "repo": "r"},
            {"name": "b", "type": "function", "file_path": "b.py", "repo": "r"},
        ]
        qdrant_store.upsert_embeddings(embeddings, payloads)

        qdrant_store.delete_by_symbol_ids(["delsym::a"])

        results = qdrant_store.search(_make_unit_vector(index=0), top_k=10)
        ids = [r["symbol_id"] for r in results]
        assert "delsym::a" not in ids
