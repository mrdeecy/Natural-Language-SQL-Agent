from __future__ import annotations

import os

import psycopg2


def main() -> None:
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql://sql_agent:CHANGE_ME@localhost:5432/pagila",
    )
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("DELETE FROM actor WHERE actor_id = -1;")
        print("UNEXPECTED: write succeeded")
        conn.rollback()
        cur.close()
        conn.close()
        raise SystemExit(1)
    except Exception as exc:  # pragma: no cover
        print(f"Permission denied as expected: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
