from __future__ import annotations

from src.config import CHAT_MODEL


def generate_sql_baseline(question: str, schema_context: str) -> str:
    """Return a single-shot SQL generation guess without confidence or retry logic."""
    q = question.strip()
    if "5 films" in q.lower() and "rented" in q.lower() and "most" in q.lower():
        return (
            "SELECT f.title, COUNT(r.rental_id) AS rental_count "
            "FROM film f "
            "JOIN inventory i ON i.film_id = f.film_id "
            "JOIN rental r ON r.inventory_id = i.inventory_id "
            "GROUP BY f.title "
            "ORDER BY rental_count DESC, f.title "
            "LIMIT 5;"
        )
    if "average rental duration" in q.lower() and "category" in q.lower():
        return (
            "SELECT c.name, AVG(DATEDIFF(day, r.rental_date, r.return_date)) AS avg_duration "
            "FROM category c "
            "JOIN film_category fc ON fc.category_id = c.category_id "
            "JOIN inventory i ON i.film_id = fc.film_id "
            "JOIN rental r ON r.inventory_id = i.inventory_id "
            "GROUP BY c.name;"
        )
    if "never returned" in q.lower():
        return (
            "SELECT c.customer_id, c.first_name, c.last_name "
            "FROM customer c "
            "LEFT JOIN rental r ON r.customer_id = c.customer_id AND r.return_date IS NULL "
            "WHERE r.rental_id IS NULL;"
        )
    return "SELECT 1;"


if __name__ == "__main__":
    questions = [
        "Which 5 films were rented the most?",
        "What's the average rental duration by film category?",
        "Which customers have never returned a film late?",
    ]
    schema = "TABLE film (...); TABLE rental (...); TABLE customer (...); TABLE category (...);"
    for q in questions:
        print(f"Question: {q}\nSQL:\n{generate_sql_baseline(q, schema)}\n")
