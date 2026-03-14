"""Auth-related database queries using the raw psycopg2 PostgresClient."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def create_user(
    postgres,
    email: str,
    password_hash: str,
    display_name: str,
) -> dict:
    """Insert a new user row and return the created record.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        email: The user's email address (must be unique).
        password_hash: A bcrypt hash of the user's password.
        display_name: The user's human-readable name.

    Returns:
        A dict with ``user_id``, ``email``, and ``display_name``.

    Raises:
        psycopg2.IntegrityError: If the email already exists.
    """
    conn = postgres._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, display_name)
                VALUES (%s, %s, %s)
                RETURNING user_id, email, display_name
                """,
                (email, password_hash, display_name),
            )
            row = cur.fetchone()
        conn.commit()
        return {"user_id": str(row[0]), "email": row[1], "display_name": row[2]}
    except Exception:
        conn.rollback()
        raise
    finally:
        postgres._put_conn(conn)


def get_user_by_email(postgres, email: str) -> Optional[dict]:
    """Return the user row matching *email*, or None if not found.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        email: The email address to look up.

    Returns:
        A dict of the user row or ``None``.
    """
    import psycopg2.extras

    conn = postgres._get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT user_id, email, password_hash, display_name, created_at FROM users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
        return dict(row) if row is not None else None
    finally:
        postgres._put_conn(conn)


def get_user_by_id(postgres, user_id: str) -> Optional[dict]:
    """Return the user row matching *user_id*, or None if not found.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        user_id: The UUID of the user.

    Returns:
        A dict of the user row or ``None``.
    """
    import psycopg2.extras

    conn = postgres._get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT user_id, email, password_hash, display_name, created_at FROM users WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        return dict(row) if row is not None else None
    finally:
        postgres._put_conn(conn)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


def create_org(postgres, name: str, slug: str) -> dict:
    """Insert a new organization row and return the created record.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        name: The human-readable organization name.
        slug: A URL-safe unique identifier for the organization.

    Returns:
        A dict with ``org_id``, ``name``, and ``slug``.

    Raises:
        psycopg2.IntegrityError: If the slug already exists.
    """
    conn = postgres._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO organizations (name, slug)
                VALUES (%s, %s)
                RETURNING org_id, name, slug
                """,
                (name, slug),
            )
            row = cur.fetchone()
        conn.commit()
        return {"org_id": str(row[0]), "name": row[1], "slug": row[2]}
    except Exception:
        conn.rollback()
        raise
    finally:
        postgres._put_conn(conn)


def get_org(postgres, org_id: str) -> Optional[dict]:
    """Return the organization row matching *org_id*, or None if not found.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        org_id: The UUID of the organization.

    Returns:
        A dict of the organization row or ``None``.
    """
    import psycopg2.extras

    conn = postgres._get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT org_id, name, slug, created_at FROM organizations WHERE org_id = %s",
                (org_id,),
            )
            row = cur.fetchone()
        return dict(row) if row is not None else None
    finally:
        postgres._put_conn(conn)


# ---------------------------------------------------------------------------
# Organization memberships
# ---------------------------------------------------------------------------


def add_org_member(postgres, user_id: str, org_id: str, role: str) -> dict:
    """Insert a membership linking *user_id* to *org_id* with *role*.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        user_id: The UUID of the user.
        org_id: The UUID of the organization.
        role: The role to assign (e.g. ``"org_admin"`` or ``"member"``).

    Returns:
        A dict with ``user_id``, ``org_id``, and ``role``.

    Raises:
        psycopg2.IntegrityError: If the membership already exists.
    """
    conn = postgres._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO org_memberships (user_id, org_id, role)
                VALUES (%s, %s, %s)
                RETURNING user_id, org_id, role
                """,
                (user_id, org_id, role),
            )
            row = cur.fetchone()
        conn.commit()
        return {"user_id": str(row[0]), "org_id": str(row[1]), "role": row[2]}
    except Exception:
        conn.rollback()
        raise
    finally:
        postgres._put_conn(conn)


def get_org_membership(postgres, user_id: str, org_id: str) -> Optional[dict]:
    """Return the membership row for *(user_id, org_id)*, or None if absent.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        user_id: The UUID of the user.
        org_id: The UUID of the organization.

    Returns:
        A dict of the membership row or ``None``.
    """
    import psycopg2.extras

    conn = postgres._get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT user_id, org_id, role, joined_at
                FROM org_memberships
                WHERE user_id = %s AND org_id = %s
                """,
                (user_id, org_id),
            )
            row = cur.fetchone()
        return dict(row) if row is not None else None
    finally:
        postgres._put_conn(conn)


def list_orgs_for_user(postgres, user_id: str) -> list[dict]:
    """Return all organizations the user belongs to, with their role.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        user_id: The UUID of the user.

    Returns:
        A list of dicts, each containing ``org_id``, ``name``, ``slug``, and
        ``role``.
    """
    import psycopg2.extras

    conn = postgres._get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT o.org_id, o.name, o.slug, m.role, m.joined_at
                FROM organizations o
                JOIN org_memberships m ON o.org_id = m.org_id
                WHERE m.user_id = %s
                ORDER BY m.joined_at
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        postgres._put_conn(conn)


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


def create_api_key(
    postgres,
    org_id: str,
    key_hash: str,
    key_prefix: str,
    description: str,
    expires_at=None,
) -> dict:
    """Insert a new API key row and return the created record.

    The raw key is never stored here — only the SHA-256 hash.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        org_id: The UUID of the organization that owns this key.
        key_hash: SHA-256 hex digest of the raw API key.
        key_prefix: First 8 characters of the raw key, safe to display.
        description: Human-readable label for this key.
        expires_at: Optional expiry as a ``datetime`` (timezone-aware) or
            ``None`` for a non-expiring key.

    Returns:
        A dict with ``key_id``, ``org_id``, ``key_prefix``, ``description``,
        ``is_active``, and ``expires_at``.
    """
    conn = postgres._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_keys (org_id, key_hash, key_prefix, description, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING key_id, org_id, key_prefix, description, is_active, expires_at
                """,
                (org_id, key_hash, key_prefix, description, expires_at),
            )
            row = cur.fetchone()
        conn.commit()
        return {
            "key_id": str(row[0]),
            "org_id": str(row[1]),
            "key_prefix": row[2],
            "description": row[3],
            "is_active": row[4],
            "expires_at": row[5].isoformat() if row[5] is not None else None,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        postgres._put_conn(conn)


def get_api_key_by_hash(postgres, key_hash: str) -> Optional[dict]:
    """Return the API key row matching *key_hash*, or None if not found.

    Used during request authentication to validate an incoming ``X-API-Key``
    header.

    Args:
        postgres: A connected ``PostgresClient`` instance.
        key_hash: SHA-256 hex digest of the raw API key.

    Returns:
        A dict including ``key_id``, ``org_id``, ``key_prefix``,
        ``description``, ``is_active``, and ``expires_at``, or ``None``.
    """
    import psycopg2.extras

    conn = postgres._get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT key_id, org_id, key_prefix, description, is_active, expires_at
                FROM api_keys
                WHERE key_hash = %s
                """,
                (key_hash,),
            )
            row = cur.fetchone()
        return dict(row) if row is not None else None
    finally:
        postgres._put_conn(conn)
