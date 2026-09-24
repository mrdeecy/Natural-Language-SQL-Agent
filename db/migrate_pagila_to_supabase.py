from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = PROJECT_ROOT / "paglia" / "1. pagila-schema.sql"
DEFAULT_DATA = PROJECT_ROOT / "paglia" / "2. pagila-insert-data.sql"
load_dotenv(APP_ROOT / ".env", override=False)


def _load_sql(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"SQL file not found: {path}")
    sql = path.read_text(encoding="utf-8")
    # The dump was created for a local PostgreSQL owner named postgres.
    # Supabase owns objects through its managed roles, so these statements
    # must not be replayed against the hosted database.
    return re.sub(r"^\s*ALTER .* OWNER TO postgres;\s*$", "", sql, flags=re.MULTILINE)


def migrate(database_url: str, schema_path: Path, data_path: Path, reset: bool = False) -> dict[str, int]:
    if not database_url:
        raise ValueError("Set SUPABASE_DB_URL or pass --database-url before migrating.")

    schema_sql = _load_sql(schema_path)
    data_sql = _load_sql(data_path)

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            if reset:
                cursor.execute("DROP SCHEMA public CASCADE")
                cursor.execute("CREATE SCHEMA public")

            cursor.execute(schema_sql)
            cursor.execute(data_sql)
            cursor.execute(
                """
                SELECT table_name, row_count
                FROM (
                    SELECT 'film' AS table_name, COUNT(*)::int AS row_count FROM film
                    UNION ALL
                    SELECT 'customer', COUNT(*)::int FROM customer
                    UNION ALL
                    SELECT 'rental', COUNT(*)::int FROM rental
                ) counts
                ORDER BY table_name
                """
            )
            counts = dict(cursor.fetchall())
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the Pagila dump into a Supabase Postgres database.")
    parser.add_argument("--database-url", default=os.getenv("SUPABASE_DB_URL"), help="Supabase Postgres DSN")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Pagila schema SQL file")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Pagila data SQL file")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate the public schema before loading; use after a partial migration.",
    )
    args = parser.parse_args()

    counts = migrate(args.database_url or "", args.schema, args.data, reset=args.reset)
    print("Pagila migration completed successfully.")
    for table_name, count in counts.items():
        print(f"{table_name}: {count} rows")


if __name__ == "__main__":
    main()
