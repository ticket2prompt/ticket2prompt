"""Tests for the Qdrant vector store client."""

from unittest.mock import MagicMock, call, patch

import pytest

from storage.qdrant_client import QdrantVectorStore


# ---------------------------------------------------------------------------
# Skip detection
# ---------------------------------------------------------------------------

def qdrant_available() -> bool:
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url="http://localhost:6333", timeout=2)
        client.get_collections()
        client.close()
        return True
    except Exception:
        return False


skip_no_qdrant = pytest.mark.skipif(
    not qdrant_available(), reason="Qdrant not available"
)

TEST_COLLECTION = "test_code_symbols"
VECTOR_SIZE = 384


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(symbol_id: str, value: float) -> object:
    """Return a minimal object that mimics EmbeddingResult."""
    from indexing.embedding_pipeline import EmbeddingResult
    return EmbeddingResult(
        symbol_id=symbol_id,
        embedding=[value] * VECTOR_SIZE,
    )


def _sample_payload(repo: str = "my-repo", suffix: str = "") -> dict:
    return {
        "symbol_name": f"my_function{suffix}",
        "symbol_type": "function",
        "file_path": f"src/module{suffix}.py",
        "repo": repo,
        "start_line": 1,
        "end_line": 10,
        "language": "python",
    }


# ---------------------------------------------------------------------------
# Unit tests (mocked QdrantClient)
# ---------------------------------------------------------------------------

class TestQdrantVectorStoreInit:
    def test_qdrant_store_init_stores_config(self):
        store = QdrantVectorStore(
            url="http://localhost:6333",
            collection_name="my_collection",
            vector_size=512,
        )
        assert store._url == "http://localhost:6333"
        assert store._collection_name == "my_collection"
        assert store._vector_size == 512
        assert store._client is None

    def test_default_collection_name_and_vector_size(self):
        store = QdrantVectorStore(url="http://localhost:6333")
        assert store._collection_name == "code_symbols"
        assert store._vector_size == 384


class TestEnsureCollection:
    def test_ensure_collection_creates_with_correct_params(self):
        from qdrant_client import models

        with patch("storage.qdrant_client.QdrantClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.collection_exists.return_value = False

            store = QdrantVectorStore(url="http://localhost:6333")
            store.connect()
            store.ensure_collection()

            mock_instance.create_collection.assert_called_once()
            call_kwargs = mock_instance.create_collection.call_args

            assert call_kwargs.kwargs["collection_name"] == "code_symbols" or \
                   call_kwargs.args[0] == "code_symbols"

            vectors_config = (
                call_kwargs.kwargs.get("vectors_config")
                or call_kwargs.args[1]
            )
            assert isinstance(vectors_config, models.VectorParams)
            assert vectors_config.size == 384
            assert vectors_config.distance == models.Distance.COSINE

    def test_ensure_collection_skips_create_when_exists(self):
        with patch("storage.qdrant_client.QdrantClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.collection_exists.return_value = True

            store = QdrantVectorStore(url="http://localhost:6333")
            store.connect()
            store.ensure_collection()

            mock_instance.create_collection.assert_not_called()


class TestUpsertEmbeddings:
    def test_upsert_builds_point_structs(self):
        from qdrant_client import models
        from storage.qdrant_client import _symbol_id_to_point_id

        with patch("storage.qdrant_client.QdrantClient") as MockClient:
            mock_instance = MockClient.return_value

            store = QdrantVectorStore(url="http://localhost:6333")
            store.connect()

            embeddings = [
                _make_embedding("sym-1", 0.1),
                _make_embedding("sym-2", 0.2),
            ]
            payloads = [
                _sample_payload(suffix="-1"),
                _sample_payload(suffix="-2"),
            ]

            store.upsert_embeddings(embeddings, payloads)

            assert mock_instance.upsert.called
            upsert_call = mock_instance.upsert.call_args
            points = upsert_call.kwargs.get("points") or upsert_call.args[1]

            assert len(points) == 2
            for point, emb, payload in zip(points, embeddings, payloads):
                assert isinstance(point, models.PointStruct)
                # Point IDs are deterministic UUIDs derived from symbol_id
                assert point.id == _symbol_id_to_point_id(emb.symbol_id)
                assert point.vector == emb.embedding
                # Original symbol_id is preserved in the payload for round-tripping
                assert point.payload["symbol_id"] == emb.symbol_id
                for key, val in payload.items():
                    assert point.payload[key] == val

    def test_upsert_batches_in_groups_of_100(self):
        with patch("storage.qdrant_client.QdrantClient") as MockClient:
            mock_instance = MockClient.return_value

            store = QdrantVectorStore(url="http://localhost:6333")
            store.connect()

            embeddings = [_make_embedding(f"sym-{i}", float(i) / 1000) for i in range(250)]
            payloads = [_sample_payload(suffix=f"-{i}") for i in range(250)]

            store.upsert_embeddings(embeddings, payloads)

            # 250 items split into batches of 100 → 3 upsert calls
            assert mock_instance.upsert.call_count == 3


class TestSearch:
    def test_search_returns_formatted_results(self):
        with patch("storage.qdrant_client.QdrantClient") as MockClient:
            mock_instance = MockClient.return_value

            mock_point_1 = MagicMock()
            mock_point_1.id = "sym-1"
            mock_point_1.score = 0.95
            mock_point_1.payload = _sample_payload(suffix="-1")

            mock_point_2 = MagicMock()
            mock_point_2.id = "sym-2"
            mock_point_2.score = 0.80
            mock_point_2.payload = _sample_payload(suffix="-2")

            mock_response = MagicMock()
            mock_response.points = [mock_point_1, mock_point_2]
            mock_instance.query_points.return_value = mock_response

            store = QdrantVectorStore(url="http://localhost:6333")
            store.connect()

            query_vector = [0.1] * VECTOR_SIZE
            results = store.search(query_vector, top_k=10)

            assert len(results) == 2
            assert results[0] == {
                "symbol_id": "sym-1",
                "score": 0.95,
                "payload": mock_point_1.payload,
            }
            assert results[1] == {
                "symbol_id": "sym-2",
                "score": 0.80,
                "payload": mock_point_2.payload,
            }

    def test_search_passes_top_k_as_limit(self):
        with patch("storage.qdrant_client.QdrantClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = MagicMock()
            mock_response.points = []
            mock_instance.query_points.return_value = mock_response

            store = QdrantVectorStore(url="http://localhost:6333")
            store.connect()

            store.search([0.1] * VECTOR_SIZE, top_k=5)

            call_kwargs = mock_instance.query_points.call_args.kwargs
            assert call_kwargs.get("limit") == 5

    def test_search_with_filter_passes_query_filter(self):
        from qdrant_client import models

        with patch("storage.qdrant_client.QdrantClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = MagicMock()
            mock_response.points = []
            mock_instance.query_points.return_value = mock_response

            store = QdrantVectorStore(url="http://localhost:6333")
            store.connect()

            store.search([0.1] * VECTOR_SIZE, filters={"repo": "my-repo"})

            call_kwargs = mock_instance.query_points.call_args.kwargs
            query_filter = call_kwargs.get("query_filter")
            assert query_filter is not None
            assert isinstance(query_filter, models.Filter)


class TestDeleteByRepo:
    def test_delete_by_repo_uses_filter(self):
        from qdrant_client import models

        with patch("storage.qdrant_client.QdrantClient") as MockClient:
            mock_instance = MockClient.return_value

            store = QdrantVectorStore(url="http://localhost:6333")
            store.connect()

            store.delete_by_repo("my-repo")

            assert mock_instance.delete.called
            call_kwargs = mock_instance.delete.call_args

            points_selector = (
                call_kwargs.kwargs.get("points_selector")
                or call_kwargs.args[1]
            )
            assert isinstance(points_selector, models.Filter)

            must_conditions = points_selector.must
            assert must_conditions is not None
            assert len(must_conditions) == 1
            condition = must_conditions[0]
            assert isinstance(condition, models.FieldCondition)
            assert condition.key == "repo"
            assert condition.match.value == "my-repo"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def qdrant_store():
    """Create a QdrantVectorStore connected to the local Qdrant instance."""
    store = QdrantVectorStore(
        url="http://localhost:6333",
        collection_name=TEST_COLLECTION,
        vector_size=VECTOR_SIZE,
    )
    store.connect()
    store.ensure_collection()
    yield store
    # Cleanup: drop the test collection after each test
    try:
        store.delete_collection()
    except Exception:
        pass
    store.close()


@skip_no_qdrant
class TestIntegrationEnsureCollection:
    def test_ensure_collection_creates(self, qdrant_store):
        from qdrant_client import QdrantClient
        client = QdrantClient(url="http://localhost:6333")
        info = client.get_collection(TEST_COLLECTION)
        client.close()
        assert info is not None


@skip_no_qdrant
class TestIntegrationUpsertAndSearch:
    def test_upsert_and_search_roundtrip(self, qdrant_store):
        embeddings = [
            _make_embedding("sym-a", 0.9),
            _make_embedding("sym-b", 0.5),
            _make_embedding("sym-c", 0.1),
        ]
        payloads = [
            _sample_payload(repo="repo-a", suffix="-a"),
            _sample_payload(repo="repo-b", suffix="-b"),
            _sample_payload(repo="repo-c", suffix="-c"),
        ]

        qdrant_store.upsert_embeddings(embeddings, payloads)

        query_vector = [0.9] * VECTOR_SIZE
        results = qdrant_store.search(query_vector, top_k=3)

        assert len(results) == 3
        symbol_ids = {r["symbol_id"] for r in results}
        assert symbol_ids == {"sym-a", "sym-b", "sym-c"}

        for result in results:
            assert "symbol_id" in result
            assert "score" in result
            assert "payload" in result
            assert isinstance(result["score"], float)

    def test_search_with_repo_filter(self, qdrant_store):
        embeddings = [
            _make_embedding("sym-x", 0.8),
            _make_embedding("sym-y", 0.8),
        ]
        payloads = [
            _sample_payload(repo="repo-filter-1", suffix="-x"),
            _sample_payload(repo="repo-filter-2", suffix="-y"),
        ]

        qdrant_store.upsert_embeddings(embeddings, payloads)

        query_vector = [0.8] * VECTOR_SIZE
        results = qdrant_store.search(
            query_vector, top_k=10, filters={"repo": "repo-filter-1"}
        )

        assert len(results) == 1
        assert results[0]["symbol_id"] == "sym-x"
        assert results[0]["payload"]["repo"] == "repo-filter-1"

    def test_search_top_k_limit(self, qdrant_store):
        embeddings = [_make_embedding(f"sym-{i}", float(i) / 10) for i in range(5)]
        payloads = [_sample_payload(suffix=f"-{i}") for i in range(5)]

        qdrant_store.upsert_embeddings(embeddings, payloads)

        query_vector = [0.5] * VECTOR_SIZE
        results = qdrant_store.search(query_vector, top_k=2)

        assert len(results) == 2


@skip_no_qdrant
class TestIntegrationDeleteByRepo:
    def test_delete_by_repo(self, qdrant_store):
        embeddings = [
            _make_embedding("keep-sym", 0.7),
            _make_embedding("delete-sym", 0.7),
        ]
        payloads = [
            _sample_payload(repo="keep-repo", suffix="-keep"),
            _sample_payload(repo="delete-repo", suffix="-delete"),
        ]

        qdrant_store.upsert_embeddings(embeddings, payloads)

        qdrant_store.delete_by_repo("delete-repo")

        query_vector = [0.7] * VECTOR_SIZE
        results = qdrant_store.search(query_vector, top_k=10)

        symbol_ids = {r["symbol_id"] for r in results}
        assert "delete-sym" not in symbol_ids
        assert "keep-sym" in symbol_ids


@skip_no_qdrant
class TestIntegrationCollectionInfo:
    def test_collection_info_returns_point_count(self, qdrant_store):
        embeddings = [
            _make_embedding("info-sym-1", 0.3),
            _make_embedding("info-sym-2", 0.6),
        ]
        payloads = [
            _sample_payload(suffix="-1"),
            _sample_payload(suffix="-2"),
        ]

        qdrant_store.upsert_embeddings(embeddings, payloads)

        info = qdrant_store.get_collection_info()

        assert "points_count" in info
        assert info["points_count"] == 2
