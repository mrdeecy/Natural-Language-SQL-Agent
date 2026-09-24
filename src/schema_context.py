from __future__ import annotations

import os

from src.config import DATABASE_URL

DEFAULT_TABLES = [
    "film",
    "customer",
    "rental",
    "payment",
    "inventory",
    "store",
    "staff",
    "actor",
    "category",
    "film_category",
    "film_actor",
]

TABLE_INFO = {
    "film": "film_id PK, title, description, release_year, rental_duration, rental_rate, replacement_cost, rating, language_id FK->language.language_id",
    "customer": "customer_id PK, first_name, last_name, email, address_id FK->address.address_id, activebool, create_date, active",
    "rental": "rental_id PK, rental_date, inventory_id FK->inventory.inventory_id, customer_id FK->customer.customer_id, return_date, staff_id FK->staff.staff_id, last_update",
    "payment": "payment_id PK, customer_id FK->customer.customer_id, staff_id FK->staff.staff_id, rental_id FK->rental.rental_id, amount, payment_date",
    "inventory": "inventory_id PK, film_id FK->film.film_id, store_id FK->store.store_id, last_update",
    "store": "store_id PK, manager_staff_id FK->staff.staff_id, address_id FK->address.address_id, last_update",
    "staff": "staff_id PK, first_name, last_name, address_id FK->address.address_id, email, store_id FK->store.store_id, active, username, last_update",
    "actor": "actor_id PK, first_name, last_name, last_update",
    "category": "category_id PK, name, last_update",
    "film_category": "film_id FK->film.film_id, category_id FK->category.category_id, last_update",
    "film_actor": "actor_id FK->actor.actor_id, film_id FK->film.film_id, last_update",
}


def _fallback_schema(tables: list[str] | None = None) -> str:
    selected = (tables or DEFAULT_TABLES)
    selected = [table for table in selected if table in TABLE_INFO]
    if not selected:
        selected = DEFAULT_TABLES
    lines = [f"TABLE {table} ({TABLE_INFO[table]})" for table in selected]
    return "\n".join(lines)


def get_schema_context(tables: list[str] | None = None) -> str:
    """Return a compact schema block for the core Pagila tables.

    If a live Postgres connection is available, the function can introspect
    information_schema. Otherwise it falls back to a static condensed schema that
    is dense enough for the LLM and suitable for offline unit tests.
    """
    if tables is None:
        tables = DEFAULT_TABLES

    if not DATABASE_URL or "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
        return _fallback_schema(tables)

    try:
        import psycopg2

        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                table_filter = "'" + "','".join(tables) + "'" if tables else "''"
                cur.execute(
                    """
                    SELECT table_name,
                           STRING_AGG(DISTINCT column_name || ' ' || data_type, ', ' ORDER BY column_name) AS cols
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = ANY(%s)
                    GROUP BY table_name
                    ORDER BY table_name;
                    """,
                    (list(tables),),
                )
                rows = cur.fetchall()
                if rows:
                    lines = []
                    for table_name, cols in rows:
                        lines.append(f"TABLE {table_name} ({cols})")
                    return "\n".join(lines)
    except Exception:
        pass

    return _fallback_schema(tables)
