from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/formfiller",
)
DB_CONNECT_RETRIES = max(1, int(os.environ.get("DB_CONNECT_RETRIES", "10")))
DB_CONNECT_DELAY = max(0.1, float(os.environ.get("DB_CONNECT_DELAY", "1.5")))


def _connect() -> psycopg2.extensions.connection:
    last_error: Exception | None = None
    for attempt in range(1, DB_CONNECT_RETRIES + 1):
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception as exc:
            last_error = exc
            if attempt < DB_CONNECT_RETRIES:
                time.sleep(DB_CONNECT_DELAY)
    assert last_error is not None
    raise last_error


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_user(row: dict | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def init_db() -> bool:
    seeded_admin = False
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(10) NOT NULL DEFAULT 'user',
                    quota_remaining INTEGER,
                    total_submitted INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]

        if count == 0:
            from web.auth import hash_password

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (username, password_hash, role, quota_remaining)
                    VALUES (%s, %s, 'admin', NULL)
                    """,
                    ("admin", hash_password("admin1")),
                )
            seeded_admin = True

    return seeded_admin


def get_user_by_username(username: str) -> dict | None:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return _row_to_user(cur.fetchone())


def get_user_by_id(user_id: int) -> dict | None:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return _row_to_user(cur.fetchone())


def create_user(
    username: str,
    password_hash: str,
    role: str = "user",
    quota_remaining: int | None = 0,
) -> dict:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role, quota_remaining)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (username, password_hash, role, quota_remaining),
        )
        return dict(cur.fetchone())


def update_quota(user_id: int, quota_remaining: int | None) -> dict | None:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE users
            SET quota_remaining = %s
            WHERE id = %s
            RETURNING *
            """,
            (quota_remaining, user_id),
        )
        return _row_to_user(cur.fetchone())


def delete_user(user_id: int) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return cur.rowcount > 0


def list_users() -> list[dict]:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM users
            ORDER BY
                CASE WHEN role = 'admin' THEN 0 ELSE 1 END,
                username ASC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def search_users(query: str) -> list[dict]:
    term = f"%{query.strip()}%"
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM users
            WHERE username ILIKE %s
            ORDER BY
                CASE WHEN role = 'admin' THEN 0 ELSE 1 END,
                username ASC
            """,
            (term,),
        )
        return [dict(row) for row in cur.fetchall()]


def decrement_quota(user_id: int) -> int | None:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE users
            SET quota_remaining = CASE
                WHEN quota_remaining IS NULL THEN NULL
                ELSE quota_remaining - 1
            END
            WHERE id = %s
              AND (quota_remaining IS NULL OR quota_remaining > 0)
            RETURNING quota_remaining
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            user = get_user_by_id(user_id)
            return None if user is None else user["quota_remaining"]
        return row["quota_remaining"]


def increment_total(user_id: int) -> int | None:
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE users
            SET total_submitted = total_submitted + 1
            WHERE id = %s
            RETURNING total_submitted
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return None if row is None else row["total_submitted"]
