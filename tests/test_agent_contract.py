import os

import pytest

from src.access import is_admin_email, is_logged_in, user_email
from src.config import CONFIDENCE_THRESHOLD, MAX_RETRIES
from src.baseline import generate_sql_baseline
from src.db import is_read_only_sql, validate_read_only_db
from src.nodes import execute_sql
from src.schema_context import get_schema_context
from src.routers import retry_cap_exceeded, preflight_router, confidence_router, human_review_router, execute_result_router
from src.state import AgentState


def test_config_values_are_loaded_from_env():
    assert isinstance(CONFIDENCE_THRESHOLD, float)
    assert CONFIDENCE_THRESHOLD > 0
    assert isinstance(MAX_RETRIES, int)
    assert MAX_RETRIES > 0


def test_schema_context_contains_core_pagila_tables():
    schema = get_schema_context()
    assert "TABLE film" in schema
    assert "TABLE rental" in schema
    assert "TABLE customer" in schema
    assert "TABLE payment" in schema
    assert "TABLE inventory" in schema
    assert "TABLE store" in schema
    assert len(schema) < 5000


def test_baseline_generates_sql_for_easy_question():
    sql = generate_sql_baseline("Which 5 films were rented the most?", get_schema_context())
    assert isinstance(sql, str)
    assert len(sql) > 20
    assert "SELECT" in sql.upper()


def test_routers_follow_retry_logic():
    state: AgentState = {
        "question": "x",
        "schema_context": "",
        "generated_sql": None,
        "confidence": 0.9,
        "confidence_reasoning": None,
        "sql_error": None,
        "execution_result": None,
        "needs_human": False,
        "human_feedback": None,
        "retry_count": 0,
        "final_answer": None,
        "resolved": False,
        "in_scope": True,
    }
    assert confidence_router(state) == "execute_sql"
    assert preflight_router({**state, "in_scope": False}) == "respond"
    assert retry_cap_exceeded({**state, "retry_count": MAX_RETRIES}) is True
    assert human_review_router({**state, "human_feedback": "fix it", "retry_count": 1}) == "generate_sql"
    assert execute_result_router({**state, "sql_error": "oops", "retry_count": MAX_RETRIES}) == "respond"


def test_read_only_sql_guard_blocks_mutating_statements():
    assert is_read_only_sql("SELECT 1;") is True
    assert is_read_only_sql("WITH recent AS (SELECT 1) SELECT * FROM recent;") is True
    assert is_read_only_sql("DELETE FROM film WHERE film_id = 1;") is False
    assert is_read_only_sql("UPDATE customer SET active = false;") is False
    assert is_read_only_sql("DROP TABLE public.film;") is False


def test_validate_read_only_db_rejects_writable_connection(monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=None):
            self.query = query
            self.params = params

        def fetchone(self):
            if "current_user" in self.query.lower():
                return ("app_user",)
            return (True,)

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    conn = FakeConn()
    with pytest.raises(ValueError, match="read-only"):
        validate_read_only_db(conn)


def test_admin_access_is_case_insensitive_and_denies_unknown_users(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "Admin@example.com, reviewer@example.com")

    assert is_admin_email("admin@EXAMPLE.com") is True
    assert is_admin_email("reviewer@example.com") is True
    assert is_admin_email("visitor@example.com") is False
    assert is_admin_email(None) is False


def test_streamlit_user_proxy_access_is_safe_when_identity_is_missing():
    user = {}

    assert is_logged_in(user) is False
    assert user_email(user) is None


def test_query_results_preserve_sql_column_names(monkeypatch):
    class FakeCursor:
        description = [("title",), ("rental_count",)]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql):
            self.sql = sql

        def fetchall(self):
            return [("ACADEMY DINOSAUR", 23)]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr("src.nodes.get_connection", lambda: FakeConnection())
    result = execute_sql({"generated_sql": "SELECT title, rental_count FROM film", "retry_count": 0})

    assert result["execution_result"] == [{"title": "ACADEMY DINOSAUR", "rental_count": 23}]
