"""Migrate an existing single-tenant database to the multi-tenant schema.

Steps
-----
1. Ensure the multi-tenant tables exist (organizations, projects, …).
2. Create a default organization and a default project derived from the
   current environment's GitHub / Jira settings.
3. Backfill org_id and project_id on all legacy rows in symbols, files,
   graph_edges, and git_metadata.

Run once against an existing database.  Safe to re-run — each step is
idempotent.

Usage
-----
    python scripts/migrate_to_multi_tenant.py

Environment variables are read from .env via the application Settings.
"""

import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

# Make sure the project root is on sys.path when the script is run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import get_settings  # noqa: E402
from storage.migrations import apply_multi_tenant_migration  # noqa: E402

DEFAULT_ORG_NAME = "default"
DEFAULT_ORG_SLUG = "default"
DEFAULT_PROJECT_NAME = "default"
DEFAULT_PROJECT_SLUG = "default"


def _connect(conn_string: str):
    return psycopg2.connect(conn_string)


def _ensure_default_org(cur, org_name: str, org_slug: str) -> str:
    """Insert the default org if it does not exist; return its org_id."""
    cur.execute(
        """
        INSERT INTO organizations (name, slug)
        VALUES (%s, %s)
        ON CONFLICT (slug) DO NOTHING
        """,
        (org_name, org_slug),
    )
    cur.execute("SELECT org_id FROM organizations WHERE slug = %s", (org_slug,))
    row = cur.fetchone()
    return str(row["org_id"])


def _ensure_default_project(
    cur,
    org_id: str,
    project_name: str,
    project_slug: str,
    github_repo_url: str,
    jira_base_url: str,
    jira_email: str,
) -> str:
    """Insert the default project if it does not exist; return its project_id."""
    cur.execute(
        """
        INSERT INTO projects (
            org_id, name, slug,
            github_repo_url,
            jira_base_url, jira_email
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (org_id, slug) DO NOTHING
        """,
        (
            org_id,
            project_name,
            project_slug,
            github_repo_url or "https://github.com/default/default",
            jira_base_url or None,
            jira_email or None,
        ),
    )
    cur.execute(
        "SELECT project_id FROM projects WHERE org_id = %s AND slug = %s",
        (org_id, project_slug),
    )
    row = cur.fetchone()
    return str(row["project_id"])


def _backfill_table(cur, table: str, org_id: str, project_id: str) -> int:
    """Set org_id and project_id on all rows that have not been migrated yet."""
    cur.execute(
        f"""
        UPDATE {table}
        SET org_id = %s, project_id = %s
        WHERE org_id IS NULL OR project_id IS NULL
        """,
        (org_id, project_id),
    )
    return cur.rowcount


def run_migration(conn_string: str) -> None:
    settings = get_settings()

    print("Step 1: Adding multi-tenant columns to existing tables (if absent)…")
    apply_multi_tenant_migration(conn_string)
    print("  Done.")

    conn = _connect(conn_string)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            print(
                f"Step 2: Creating default organization '{DEFAULT_ORG_NAME}' "
                f"(slug='{DEFAULT_ORG_SLUG}')…"
            )
            org_id = _ensure_default_org(cur, DEFAULT_ORG_NAME, DEFAULT_ORG_SLUG)
            print(f"  org_id = {org_id}")

            print(
                f"Step 3: Creating default project '{DEFAULT_PROJECT_NAME}' "
                f"(slug='{DEFAULT_PROJECT_SLUG}')…"
            )
            project_id = _ensure_default_project(
                cur,
                org_id=org_id,
                project_name=DEFAULT_PROJECT_NAME,
                project_slug=DEFAULT_PROJECT_SLUG,
                github_repo_url=settings.github_api_url,
                jira_base_url=settings.jira_base_url,
                jira_email=settings.jira_email,
            )
            print(f"  project_id = {project_id}")

            print("Step 4: Backfilling org_id / project_id on legacy rows…")
            for table in ("symbols", "files", "graph_edges", "git_metadata"):
                updated = _backfill_table(cur, table, org_id, project_id)
                print(f"  {table}: {updated} rows updated")

        conn.commit()
        print("\nMigration complete.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    _settings = get_settings()
    run_migration(_settings.postgres_url)
