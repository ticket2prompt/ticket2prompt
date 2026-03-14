"""Qdrant vector database client."""

import logging
import uuid
from typing import Optional

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

_UPSERT_BATCH_SIZE = 100
_SYMBOL_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_URL


def _symbol_id_to_point_id(symbol_id: str) -> str:
    """Convert an arbitrary string symbol ID to a deterministic UUID string.

    Qdrant requires point IDs to be unsigned integers or UUIDs.  We use a
    UUID v5 (SHA-1 namespaced hash) so the mapping is stable and collision-
    resistant.  The original ``symbol_id`` is also stored in the payload so
    it can be recovered on read.
    """
    return str(uuid.uuid5(_SYMBOL_ID_NAMESPACE, symbol_id))


class QdrantVectorStore:
    """Client for storing and searching code symbol embeddings in Qdrant."""

    def __init__(
        self,
        url: str,
        collection_name: str = "code_symbols",
        vector_size: int = 384,
    ) -> None:
        self._url = url
        self._collection_name = collection_name
        self._vector_size = vector_size
        self._client: Optional[QdrantClient] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Instantiate the underlying QdrantClient."""
        self._client = QdrantClient(url=self._url)
        logger.info("Connected to Qdrant at %s", self._url)

    def close(self) -> None:
        """Close the underlying QdrantClient connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Disconnected from Qdrant")

    def __enter__(self) -> "QdrantVectorStore":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def ensure_collection(self) -> None:
        """Create the collection if it does not already exist.

        Uses cosine distance and the configured vector size.
        """
        if self._client.collection_exists(self._collection_name):
            logger.debug("Collection '%s' already exists", self._collection_name)
            return

        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=models.VectorParams(
                size=self._vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info(
            "Created collection '%s' (size=%d, distance=COSINE)",
            self._collection_name,
            self._vector_size,
        )

    def delete_collection(self) -> None:
        """Drop the collection entirely."""
        self._client.delete_collection(self._collection_name)
        logger.info("Deleted collection '%s'", self._collection_name)

    def get_collection_info(self) -> dict:
        """Return basic stats about the collection.

        Returns:
            Dict with at minimum ``points_count`` key.
        """
        info = self._client.get_collection(self._collection_name)
        return {
            "points_count": info.points_count,
            "status": str(info.status),
            "vectors_count": getattr(info, "vectors_count", None),
        }

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    def upsert_embeddings(
        self,
        embeddings: list,
        payloads: list,
    ) -> None:
        """Batch-upsert embeddings with their associated payloads.

        Args:
            embeddings: List of objects with symbol_id and embedding attrs.
            payloads: Matching list of payload dicts (one per embedding).
        """
        points = [
            models.PointStruct(
                id=_symbol_id_to_point_id(emb.symbol_id),
                vector=emb.embedding,
                payload={**payload, "symbol_id": emb.symbol_id},
            )
            for emb, payload in zip(embeddings, payloads)
        ]

        for batch_start in range(0, len(points), _UPSERT_BATCH_SIZE):
            batch = points[batch_start : batch_start + _UPSERT_BATCH_SIZE]
            self._client.upsert(
                collection_name=self._collection_name,
                points=batch,
            )
            logger.debug(
                "Upserted %d points (batch starting at %d)",
                len(batch),
                batch_start,
            )

    def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Search for the nearest neighbours to ``query_vector``.

        Args:
            query_vector: Dense embedding to query against.
            top_k: Maximum number of results to return.
            filters: Optional simple equality filter dict,
                e.g. ``{"repo": "my-repo"}``.

        Returns:
            List of dicts, each with keys ``symbol_id``, ``score``,
            and ``payload``.
        """
        query_filter = self._build_filter(filters) if filters else None

        response = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "symbol_id": point.payload.get("symbol_id", str(point.id)),
                "score": point.score,
                "payload": point.payload,
            }
            for point in response.points
        ]

    def delete_by_repo(self, repo: str) -> None:
        """Delete all points whose payload ``repo`` field matches ``repo``.

        Args:
            repo: Repository identifier to filter on.
        """
        repo_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="repo",
                    match=models.MatchValue(value=repo),
                )
            ]
        )
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=repo_filter,
        )
        logger.info("Deleted points for repo '%s'", repo)

    def delete_by_module(self, repo: str, module: str) -> None:
        """Delete all points whose payload matches both repo and module."""
        module_filter = models.Filter(
            must=[
                models.FieldCondition(key="repo", match=models.MatchValue(value=repo)),
                models.FieldCondition(key="module", match=models.MatchValue(value=module)),
            ]
        )
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=module_filter,
        )
        logger.info("Deleted points for repo '%s', module '%s'", repo, module)

    def delete_by_symbol_ids(self, symbol_ids: list[str]) -> None:
        """Delete points by their symbol IDs.

        Converts each symbol_id to its deterministic UUID point ID
        and deletes the corresponding points.
        """
        if not symbol_ids:
            return
        point_ids = [_symbol_id_to_point_id(sid) for sid in symbol_ids]
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.PointIdsList(points=point_ids),
        )
        logger.info("Deleted %d points by symbol IDs", len(point_ids))

    def delete_by_project(self, project_id: str) -> None:
        """Delete all points belonging to a specific project."""
        project_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="project_id",
                    match=models.MatchValue(value=project_id),
                )
            ]
        )
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=project_filter,
        )
        logger.info("Deleted points for project_id '%s'", project_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_filter(self, filters: dict) -> models.Filter:
        """Convert a simple key/value dict into a Qdrant Filter.

        Each key-value pair becomes a ``FieldCondition`` with exact
        match semantics.  All conditions are combined with ``must``
        (logical AND).
        """
        conditions = [
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=value),
            )
            for key, value in filters.items()
        ]
        return models.Filter(must=conditions)


def get_collection_name(project: dict, content_type: str = "code") -> str:
    """Resolve the Qdrant collection name for a project.

    If the project belongs to a collection_group, uses group_{group}_{type}.
    Otherwise uses proj_{project_id}_{type}.
    """
    if project.get("collection_group"):
        return f"group_{project['collection_group']}_{content_type}"
    return f"proj_{project['project_id']}_{content_type}"


def get_qdrant_for_project(project: dict, qdrant_url: str, vector_size: int = 384, content_type: str = "code") -> "QdrantVectorStore":
    """Create a QdrantVectorStore instance scoped to a project's collection."""
    collection = get_collection_name(project, content_type)
    return QdrantVectorStore(url=qdrant_url, collection_name=collection, vector_size=vector_size)
