from __future__ import annotations

import re

import psycopg2

from src.config import DATABASE_URL


READ_ONLY_SQL_REJECTION = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|rename|comment|vacuum|analyze|copy|call)\b",
    flags=re.IGNORECASE,
)


def is_read_only_sql(sql: str | None) -> bool:
    """Reject mutating SQL before it reaches the database."""
    if not sql or not sql.strip():
        return False

    normalized = re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.DOTALL | re.MULTILINE)
    normalized = normalized.strip()
    if not normalized:
        return False
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()

    first_keyword = re.match(r"\b([A-Za-z_]+)\b", normalized)
    if first_keyword is None:
        return False

    first_word = first_keyword.group(1).lower()
    if first_word not in {"select", "with", "explain", "values", "show"}:
        return False

    return READ_ONLY_SQL_REJECTION.search(normalized) is None


def validate_read_only_db(conn) -> None:
    """Raise if the configured database user can still write to the schema."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_user")
        row = cur.fetchone()
        user = row[0] if row else None
        if not user:
            raise ValueError("Database connection does not expose a current user.")

        for privilege_sql, privilege_name in (
            ("SELECT has_database_privilege(%s, current_database(), 'CREATE')", "CREATE"),
            ("SELECT has_database_privilege(%s, current_database(), 'CONNECT')", "CONNECT"),
            ("SELECT has_schema_privilege(%s, 'public', 'CREATE')", "schema CREATE"),
        ):
            cur.execute(privilege_sql, (user,))
            row = cur.fetchone()
            granted = bool(row[0]) if row else False
            if granted and privilege_name != "CONNECT":
                raise ValueError(f"Database user '{user}' is not read-only: it has {privilege_name} privilege.")

        for table in ("public.film", "public.customer", "public.rental", "public.payment"):
            cur.execute("SELECT has_table_privilege(%s, %s, 'INSERT')", (user, table))
            row = cur.fetchone()
            if row and row[0]:
                raise ValueError(f"Database user '{user}' is not read-only: it can insert into {table}.")
            cur.execute("SELECT has_table_privilege(%s, %s, 'UPDATE')", (user, table))
            row = cur.fetchone()
            if row and row[0]:
                raise ValueError(f"Database user '{user}' is not read-only: it can update {table}.")
            cur.execute("SELECT has_table_privilege(%s, %s, 'DELETE')", (user, table))
            row = cur.fetchone()
            if row and row[0]:
                raise ValueError(f"Database user '{user}' is not read-only: it can delete from {table}.")


def get_connection():
    """Return a connection using the configured read-only PostgreSQL role."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not configured.")

    conn = psycopg2.connect(DATABASE_URL)
    try:
        validate_read_only_db(conn)
    except Exception:
        conn.close()
        raise
    return conn
