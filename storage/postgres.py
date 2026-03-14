"""PostgreSQL client with connection pooling for the ticket-to-prompt metadata store."""

import logging
from dataclasses import asdict
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)


class PostgresClient:
    """Thread-safe PostgreSQL client backed by a SimpleConnectionPool.

    Usage::

        client = PostgresClient(conn_string)
        client.connect()
        client.upsert_symbol(symbol)
        client.close()

    Or as a context manager (still requires an explicit connect() call)::

        with PostgresClient(conn_string) as client:
            client.connect()
            ...
    """

    def __init__(self, conn_string: str, min_conn: int = 1, max_conn: int = 10) -> None:
        self._conn_string = conn_string
        self._min_conn = min_conn
        self._max_conn = max_conn
        self._pool: Optional[psycopg2.pool.SimpleConnectionPool] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Initialize the connection pool. Must be called before any query."""
        self._pool = psycopg2.pool.SimpleConnectionPool(
            self._min_conn,
            self._max_conn,
            self._conn_string,
        )
        logger.debug("PostgresClient pool initialized (min=%d, max=%d)", self._min_conn, self._max_conn)

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
            logger.debug("PostgresClient pool closed")

    def __enter__(self) -> "PostgresClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_conn(self):
        """Acquire a connection from the pool."""
        if self._pool is None:
            raise RuntimeError("PostgresClient.connect() must be called before executing queries")
        return self._pool.getconn()

    def _put_conn(self, conn) -> None:
        """Return a connection to the pool."""
        if self._pool is not None:
            self._pool.putconn(conn)

    def _symbol_to_dict(self, symbol) -> dict:
        """Normalize a Symbol dataclass or plain dict to a dict."""
        if isinstance(symbol, dict):
            return symbol
        return asdict(symbol)

    def _edge_to_tuple(self, edge) -> tuple:
        """Normalize a GraphEdge dataclass or plain dict to (from, to, relation)."""
        if isinstance(edge, dict):
            return (edge["from_symbol"], edge["to_symbol"], edge["relation_type"])
        return (edge.from_symbol, edge.to_symbol, edge.relation_type)

    # ------------------------------------------------------------------
    # Symbols
    # ------------------------------------------------------------------

    def upsert_symbol(self, symbol, org_id: str, project_id: str) -> None:
        """Insert a symbol row; update all non-PK fields on conflict."""
        d = self._symbol_to_dict(symbol)
        d.setdefault("module", None)
        sql = """
            INSERT INTO symbols (symbol_id, name, type, file_path, repo, start_line, end_line, module, org_id, project_id)
            VALUES (%(symbol_id)s, %(name)s, %(type)s, %(file_path)s, %(repo)s, %(start_line)s, %(end_line)s, %(module)s, %(org_id)s, %(project_id)s)
            ON CONFLICT (symbol_id) DO UPDATE SET
                name       = EXCLUDED.name,
                type       = EXCLUDED.type,
                file_path  = EXCLUDED.file_path,
                repo       = EXCLUDED.repo,
                start_line = EXCLUDED.start_line,
                end_line   = EXCLUDED.end_line,
                module     = EXCLUDED.module,
                org_id     = EXCLUDED.org_id,
                project_id = EXCLUDED.project_id
        """
        d["org_id"] = org_id
        d["project_id"] = project_id
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, d)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def upsert_symbols_batch(self, symbols: list, org_id: str, project_id: str) -> None:
        """Batch-upsert a list of Symbol dataclasses or dicts using execute_values."""
        if not symbols:
            return

        rows = [
            (
                d["symbol_id"],
                d["name"],
                d["type"],
                d["file_path"],
                d["repo"],
                d["start_line"],
                d["end_line"],
                d.get("module"),
                org_id,
                project_id,
            )
            for d in (self._symbol_to_dict(s) for s in symbols)
        ]

        sql = """
            INSERT INTO symbols (symbol_id, name, type, file_path, repo, start_line, end_line, module, org_id, project_id)
            VALUES %s
            ON CONFLICT (symbol_id) DO UPDATE SET
                name       = EXCLUDED.name,
                type       = EXCLUDED.type,
                file_path  = EXCLUDED.file_path,
                repo       = EXCLUDED.repo,
                start_line = EXCLUDED.start_line,
                end_line   = EXCLUDED.end_line,
                module     = EXCLUDED.module,
                org_id     = EXCLUDED.org_id,
                project_id = EXCLUDED.project_id
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, sql, rows)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_symbol(self, symbol_id: str) -> Optional[dict]:
        """Return a single symbol row as a dict, or None if not found."""
        sql = """
            SELECT symbol_id, name, type, file_path, repo, start_line, end_line, module
            FROM symbols
            WHERE symbol_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (symbol_id,))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    def get_symbols_by_repo(self, repo: str, org_id: str, project_id: str) -> list[dict]:
        """Return all symbols for the given repo."""
        sql = """
            SELECT symbol_id, name, type, file_path, repo, start_line, end_line, module
            FROM symbols
            WHERE repo = %s AND org_id = %s AND project_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (repo, org_id, project_id))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def get_symbols_by_file(self, file_path: str, org_id: str, project_id: str) -> list[dict]:
        """Return all symbols whose file_path matches."""
        sql = """
            SELECT symbol_id, name, type, file_path, repo, start_line, end_line, module
            FROM symbols
            WHERE file_path = %s AND org_id = %s AND project_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (file_path, org_id, project_id))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def search_symbols_by_name(self, org_id: str, project_id: str, pattern: str) -> list:
        """Search symbols whose name matches a LIKE pattern within a project."""
        sql = """
            SELECT symbol_id, name, type, file_path, repo, start_line, end_line, module
            FROM symbols
            WHERE org_id = %s AND project_id = %s AND LOWER(name) LIKE LOWER(%s)
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (org_id, project_id, f"%{pattern}%"))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def get_file_metadata(self, file_path: str, repo: str, org_id: str, project_id: str) -> Optional[dict]:
        """Return a single file row for (file_path, repo), or None."""
        sql = """
            SELECT file_id, file_path, repo, last_modified, commit_count
            FROM files
            WHERE file_path = %s AND repo = %s AND org_id = %s AND project_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (file_path, repo, org_id, project_id))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    def delete_symbols_by_repo(self, repo: str, org_id: str, project_id: str) -> None:
        """Delete all symbol rows belonging to the given repo."""
        sql = "DELETE FROM symbols WHERE repo = %s AND org_id = %s AND project_id = %s"
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (repo, org_id, project_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def delete_symbols_by_file(self, file_path: str, repo: str, org_id: str, project_id: str) -> list[str]:
        """Delete all symbols for a file in a repo and return deleted symbol_ids."""
        sql = """
            DELETE FROM symbols
            WHERE file_path = %s AND repo = %s AND org_id = %s AND project_id = %s
            RETURNING symbol_id
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (file_path, repo, org_id, project_id))
                rows = cur.fetchall()
            conn.commit()
            return [row[0] for row in rows]
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_symbols_by_module(self, repo: str, module: str, org_id: str, project_id: str) -> list[dict]:
        """Return all symbols belonging to a specific module within a repo."""
        sql = """
            SELECT symbol_id, name, type, file_path, repo, start_line, end_line, module
            FROM symbols
            WHERE repo = %s AND module = %s AND org_id = %s AND project_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (repo, module, org_id, project_id))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def delete_symbols_by_module(self, repo: str, module: str, org_id: str, project_id: str) -> list[str]:
        """Delete all symbols for a module in a repo and return deleted symbol_ids."""
        sql = """
            DELETE FROM symbols
            WHERE repo = %s AND module = %s AND org_id = %s AND project_id = %s
            RETURNING symbol_id
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (repo, module, org_id, project_id))
                rows = cur.fetchall()
            conn.commit()
            return [row[0] for row in rows]
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def delete_edges_by_symbols(self, symbol_ids: list[str]) -> None:
        """Delete all graph edges referencing any of the given symbol IDs."""
        if not symbol_ids:
            return
        sql = """
            DELETE FROM graph_edges
            WHERE from_symbol = ANY(%s) OR to_symbol = ANY(%s)
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (symbol_ids, symbol_ids))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def upsert_file(
        self,
        file_path: str,
        repo: str,
        org_id: str,
        project_id: str,
        last_modified=None,
        commit_count: int = 0,
    ) -> None:
        """Insert or update a file record keyed on (file_path, repo, org_id, project_id)."""
        sql = """
            INSERT INTO files (file_path, repo, org_id, project_id, last_modified, commit_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (file_path, repo) DO UPDATE SET
                last_modified = EXCLUDED.last_modified,
                commit_count  = EXCLUDED.commit_count,
                org_id        = EXCLUDED.org_id,
                project_id    = EXCLUDED.project_id
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (file_path, repo, org_id, project_id, last_modified, commit_count))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_files_by_repo(self, repo: str, org_id: str, project_id: str) -> list[dict]:
        """Return all file rows for the given repo."""
        sql = """
            SELECT file_id, file_path, repo, last_modified, commit_count
            FROM files
            WHERE repo = %s AND org_id = %s AND project_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (repo, org_id, project_id))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Graph edges
    # ------------------------------------------------------------------

    def insert_edges(self, edges: list, org_id: str, project_id: str) -> None:
        """Batch-insert GraphEdge dataclasses or dicts into graph_edges."""
        if not edges:
            return

        rows = [self._edge_to_tuple(e) + (org_id, project_id) for e in edges]
        sql = """
            INSERT INTO graph_edges (from_symbol, to_symbol, relation_type, org_id, project_id)
            VALUES %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, sql, rows)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_edges_from(self, symbol_id: str, org_id: str, project_id: str) -> list[dict]:
        """Return all edges where from_symbol matches the given symbol_id."""
        sql = """
            SELECT id, from_symbol, to_symbol, relation_type
            FROM graph_edges
            WHERE from_symbol = %s AND org_id = %s AND project_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (symbol_id, org_id, project_id))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def get_edges_to(self, symbol_id: str, org_id: str, project_id: str) -> list[dict]:
        """Return all edges where to_symbol matches the given symbol_id."""
        sql = """
            SELECT id, from_symbol, to_symbol, relation_type
            FROM graph_edges
            WHERE to_symbol = %s AND org_id = %s AND project_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (symbol_id, org_id, project_id))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def delete_edges_by_repo(self, repo: str, org_id: str, project_id: str) -> None:
        """Delete all graph edges whose from_symbol or to_symbol belongs to the repo.

        Joins with the symbols table to identify which symbol IDs are owned by
        the given repo and project, then deletes any edge referencing those IDs.
        """
        sql = """
            DELETE FROM graph_edges
            WHERE org_id = %s AND project_id = %s
              AND (
                from_symbol IN (
                    SELECT symbol_id FROM symbols WHERE repo = %s AND org_id = %s AND project_id = %s
                )
                OR to_symbol IN (
                    SELECT symbol_id FROM symbols WHERE repo = %s AND org_id = %s AND project_id = %s
                )
              )
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (org_id, project_id, repo, org_id, project_id, repo, org_id, project_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Git metadata
    # ------------------------------------------------------------------

    def upsert_git_metadata(
        self,
        file_path: str,
        repo: str,
        org_id: str,
        project_id: str,
        last_commit_hash: Optional[str] = None,
        last_commit_author: Optional[str] = None,
        commit_frequency: int = 0,
        recent_pr: Optional[str] = None,
    ) -> None:
        """Insert or update a git_metadata row keyed on (file_path, repo)."""
        sql = """
            INSERT INTO git_metadata
                (file_path, repo, org_id, project_id, last_commit_hash, last_commit_author, commit_frequency, recent_pr)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (file_path, repo) DO UPDATE SET
                last_commit_hash   = EXCLUDED.last_commit_hash,
                last_commit_author = EXCLUDED.last_commit_author,
                commit_frequency   = EXCLUDED.commit_frequency,
                recent_pr          = EXCLUDED.recent_pr,
                org_id             = EXCLUDED.org_id,
                project_id         = EXCLUDED.project_id
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (file_path, repo, org_id, project_id, last_commit_hash, last_commit_author, commit_frequency, recent_pr),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_git_metadata(self, file_path: str, repo: str, org_id: str, project_id: str) -> Optional[dict]:
        """Return the git_metadata row for (file_path, repo), or None if absent."""
        sql = """
            SELECT id, file_path, repo, last_commit_hash, last_commit_author,
                   commit_frequency, recent_pr
            FROM git_metadata
            WHERE file_path = %s AND repo = %s AND org_id = %s AND project_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (file_path, repo, org_id, project_id))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Organizations
    # ------------------------------------------------------------------

    def create_org(self, name: str, slug: str) -> dict:
        """Insert a new organization and return org_id, name, slug."""
        sql = """
            INSERT INTO organizations (name, slug)
            VALUES (%s, %s)
            RETURNING org_id, name, slug
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (name, slug))
                row = cur.fetchone()
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_org(self, org_id: str) -> Optional[dict]:
        """Return the organization row for org_id, or None."""
        sql = "SELECT * FROM organizations WHERE org_id = %s"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (org_id,))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    def get_org_by_slug(self, slug: str) -> Optional[dict]:
        """Return the organization row for slug, or None."""
        sql = "SELECT * FROM organizations WHERE slug = %s"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (slug,))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    def list_orgs_for_user(self, user_id: str) -> list[dict]:
        """Return all organizations the user belongs to."""
        sql = """
            SELECT o.*
            FROM organizations o
            JOIN org_memberships m ON o.org_id = m.org_id
            WHERE m.user_id = %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (user_id,))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def create_team(self, org_id: str, name: str) -> dict:
        """Insert a new team and return team_id, org_id, name."""
        sql = """
            INSERT INTO teams (org_id, name)
            VALUES (%s, %s)
            RETURNING team_id, org_id, name
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (org_id, name))
                row = cur.fetchone()
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def list_teams(self, org_id: str) -> list[dict]:
        """Return all teams for the given org."""
        sql = "SELECT * FROM teams WHERE org_id = %s"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (org_id,))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def get_team(self, team_id: str) -> Optional[dict]:
        """Return the team row for team_id, or None."""
        sql = "SELECT * FROM teams WHERE team_id = %s"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (team_id,))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    def add_team_member(self, user_id: str, team_id: str, role: str = "member") -> dict:
        """Add a user to a team and return the membership row."""
        sql = """
            INSERT INTO team_memberships (user_id, team_id, role)
            VALUES (%s, %s, %s)
            RETURNING user_id, team_id, role
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (user_id, team_id, role))
                row = cur.fetchone()
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_team_membership(self, user_id: str, team_id: str) -> Optional[dict]:
        """Return the team membership row for (user_id, team_id), or None."""
        sql = "SELECT * FROM team_memberships WHERE user_id = %s AND team_id = %s"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (user_id, team_id))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(
        self,
        org_id: str,
        name: str,
        slug: str,
        github_repo_url: str,
        team_id: str = None,
        github_token_encrypted: str = None,
        jira_base_url: str = None,
        jira_email: str = None,
        jira_api_token_encrypted: str = None,
        default_branch: str = "main",
        collection_group: str = None,
    ) -> dict:
        """Insert a new project and return all fields."""
        sql = """
            INSERT INTO projects (
                org_id, name, slug, github_repo_url, team_id,
                github_token_encrypted, jira_base_url, jira_email,
                jira_api_token_encrypted, default_branch, collection_group
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (
                    org_id, name, slug, github_repo_url, team_id,
                    github_token_encrypted, jira_base_url, jira_email,
                    jira_api_token_encrypted, default_branch, collection_group,
                ))
                row = cur.fetchone()
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_project(self, project_id: str) -> Optional[dict]:
        """Return the project row for project_id, or None."""
        sql = "SELECT * FROM projects WHERE project_id = %s"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (project_id,))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    def list_projects(self, org_id: str) -> list[dict]:
        """Return all projects for the given org."""
        sql = "SELECT * FROM projects WHERE org_id = %s"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (org_id,))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def update_project(self, project_id: str, **kwargs) -> Optional[dict]:
        """Update only the provided fields on a project, setting updated_at = NOW()."""
        if not kwargs:
            return self.get_project(project_id)
        set_clauses = ", ".join(f"{key} = %s" for key in kwargs)
        sql = f"""
            UPDATE projects
            SET {set_clauses}, updated_at = NOW()
            WHERE project_id = %s
            RETURNING *
        """
        values = list(kwargs.values()) + [project_id]
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, values)
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row is not None else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_project_by_repo_url(self, github_repo_url: str) -> Optional[dict]:
        """Return the project row for a given github_repo_url, or None."""
        sql = "SELECT * FROM projects WHERE github_repo_url = %s"
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (github_repo_url,))
                row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            self._put_conn(conn)

    def delete_project(self, project_id: str, org_id: str) -> bool:
        """Delete a project and all related data in a single transaction."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                # Delete in FK-safe order
                cur.execute("DELETE FROM jira_tickets WHERE project_id = %s AND org_id = %s", (project_id, org_id))
                cur.execute("DELETE FROM git_metadata WHERE project_id = %s AND org_id = %s", (project_id, org_id))
                cur.execute("DELETE FROM graph_edges WHERE project_id = %s AND org_id = %s", (project_id, org_id))
                cur.execute("DELETE FROM files WHERE project_id = %s AND org_id = %s", (project_id, org_id))
                cur.execute("DELETE FROM symbols WHERE project_id = %s AND org_id = %s", (project_id, org_id))
                cur.execute("DELETE FROM projects WHERE project_id = %s AND org_id = %s", (project_id, org_id))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Jira Tickets
    # ------------------------------------------------------------------

    def upsert_jira_ticket(
        self,
        org_id: str,
        project_id: str,
        ticket_key: str,
        title: str,
        description: str = None,
        acceptance_criteria: str = None,
        status: str = None,
        priority: str = None,
        labels: list = None,
        components: list = None,
        epic_key: str = None,
        sprint_name: str = None,
        assignee: str = None,
        reporter: str = None,
        created_at=None,
        updated_at=None,
        resolved_at=None,
    ) -> dict:
        """Insert or update a Jira ticket keyed on (project_id, ticket_key)."""
        sql = """
            INSERT INTO jira_tickets (
                org_id, project_id, ticket_key, title, description,
                acceptance_criteria, status, priority, labels, components,
                epic_key, sprint_name, assignee, reporter,
                created_at, updated_at, resolved_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id, ticket_key) DO UPDATE SET
                title                = EXCLUDED.title,
                description          = EXCLUDED.description,
                acceptance_criteria  = EXCLUDED.acceptance_criteria,
                status               = EXCLUDED.status,
                priority             = EXCLUDED.priority,
                labels               = EXCLUDED.labels,
                components           = EXCLUDED.components,
                epic_key             = EXCLUDED.epic_key,
                sprint_name          = EXCLUDED.sprint_name,
                assignee             = EXCLUDED.assignee,
                reporter             = EXCLUDED.reporter,
                updated_at           = EXCLUDED.updated_at,
                resolved_at          = EXCLUDED.resolved_at
            RETURNING *
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (
                    org_id, project_id, ticket_key, title, description,
                    acceptance_criteria, status, priority,
                    psycopg2.extras.Json(labels) if labels is not None else None,
                    psycopg2.extras.Json(components) if components is not None else None,
                    epic_key, sprint_name, assignee, reporter,
                    created_at, updated_at, resolved_at,
                ))
                row = cur.fetchone()
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def get_jira_tickets_by_project(self, project_id: str, limit: int = 100) -> list[dict]:
        """Return up to limit Jira tickets for the given project."""
        sql = """
            SELECT * FROM jira_tickets
            WHERE project_id = %s
            ORDER BY updated_at DESC NULLS LAST
            LIMIT %s
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (project_id, limit))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)
