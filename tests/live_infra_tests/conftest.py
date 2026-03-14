"""Shared fixtures for integration tests using testcontainers."""

import uuid

import pytest

# Mark all tests in this directory as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def postgres_url():
    """Start a PostgreSQL container and return the connection URL."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:17", username="test", password="test", dbname="test_db") as pg:
        url = pg.get_connection_url()
        # testcontainers returns postgresql+psycopg2://... — strip the driver spec
        url = url.replace("postgresql+psycopg2://", "postgresql://")
        yield url


@pytest.fixture(scope="session")
def redis_url():
    """Start a Redis container and return the connection URL."""
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7") as r:
        host = r.get_container_host_ip()
        port = r.get_exposed_port(6379)
        yield f"redis://{host}:{port}"


@pytest.fixture(scope="session")
def qdrant_url():
    """Start a Qdrant container and return the HTTP API URL."""
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    with DockerContainer("qdrant/qdrant:latest").with_exposed_ports(6333) as qdrant:
        wait_for_logs(qdrant, "Qdrant gRPC listening", timeout=30)
        host = qdrant.get_container_host_ip()
        port = qdrant.get_exposed_port(6333)
        yield f"http://{host}:{port}"


@pytest.fixture
def postgres_client(postgres_url):
    """Create a connected PostgresClient with schema applied."""
    from storage.postgres import PostgresClient

    client = PostgresClient(postgres_url)
    client.connect()

    _apply_schema(client)

    yield client

    _truncate_tables(client)
    client.close()


@pytest.fixture
def qdrant_store(qdrant_url):
    """Create a connected QdrantVectorStore with a unique test collection."""
    from storage.qdrant_client import QdrantVectorStore

    collection_name = f"test_{uuid.uuid4().hex[:8]}"
    store = QdrantVectorStore(url=qdrant_url, collection_name=collection_name, vector_size=384)
    store.connect()
    store.ensure_collection()

    yield store

    try:
        store.delete_collection()
    except Exception:
        pass
    store.close()


@pytest.fixture
def redis_cache(redis_url):
    """Create a connected RedisCache."""
    from storage.redis_cache import RedisCache

    cache = RedisCache(redis_url)
    cache.connect()

    yield cache

    # Flush the test database to clean up
    cache._client.flushdb()
    cache.close()


def _apply_schema(client):
    """Apply the database schema to the test database."""
    from storage.migrations import get_schema_sql

    sql = get_schema_sql()

    conn = client._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        # Schema may already exist (IF NOT EXISTS guards in schema.sql)
    finally:
        client._put_conn(conn)


def _truncate_tables(client):
    """Truncate all tables for cleanup between tests."""
    conn = client._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE TABLE graph_edges, git_metadata, symbols, files CASCADE"
            )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        client._put_conn(conn)
