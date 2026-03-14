"""Database schema migrations."""

from pathlib import Path

import psycopg2

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# SQL to add multi-tenant columns to existing tables that already have data.
# Each statement is idempotent (ADD COLUMN IF NOT EXISTS).
_MULTI_TENANT_MIGRATION_SQL = """
ALTER TABLE symbols
    ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(org_id),
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(project_id);

ALTER TABLE files
    ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(org_id),
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(project_id);

ALTER TABLE graph_edges
    ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(org_id),
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(project_id);

ALTER TABLE git_metadata
    ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(org_id),
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(project_id);
"""


def get_schema_sql() -> str:
    """Read and return the schema SQL."""
    return SCHEMA_PATH.read_text()


def apply_schema(conn_string: str) -> None:
    """Apply the database schema to a PostgreSQL database."""
    sql = get_schema_sql()
    conn = psycopg2.connect(conn_string)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def apply_multi_tenant_migration(conn_string: str) -> None:
    """Add org_id and project_id columns to existing tables.

    Safe to run against a database that already has rows — all ALTER TABLE
    statements use IF NOT EXISTS so they are fully idempotent.  The columns
    are added as nullable FKs so existing rows are not rejected; callers
    should backfill the values (see scripts/migrate_to_multi_tenant.py)
    before enforcing NOT NULL.
    """
    conn = psycopg2.connect(conn_string)
    try:
        with conn.cursor() as cur:
            cur.execute(_MULTI_TENANT_MIGRATION_SQL)
        conn.commit()
    finally:
        conn.close()
