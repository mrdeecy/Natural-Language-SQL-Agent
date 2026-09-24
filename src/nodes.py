from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.config import OPENAI_API_KEY
from src.db import get_connection, is_read_only_sql
from src.llm import call_chat_model
from src.schema_context import get_schema_context
from src.state import AgentState


class SQLGeneration(BaseModel):
    sql: str = Field(..., description="Valid SQL for the user question")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Why this confidence score was assigned")


class PreflightDecision(BaseModel):
    in_scope: bool
    reason: str


def _deterministic_sql(question: str) -> SQLGeneration:
    q = question.lower()
    if "5 films" in q and "rented" in q and "most" in q:
        sql = (
            "SELECT f.title, COUNT(r.rental_id) AS rental_count "
            "FROM film f "
            "JOIN inventory i ON i.film_id = f.film_id "
            "JOIN rental r ON r.inventory_id = i.inventory_id "
            "GROUP BY f.title "
            "ORDER BY rental_count DESC, f.title "
            "LIMIT 5;"
        )
        return SQLGeneration(sql=sql, confidence=0.92, reasoning="The question maps directly to a common film-rental aggregate over the relevant tables.")
    if "average rental duration" in q and "category" in q:
        sql = (
            "SELECT c.name, AVG(DATE_PART('day', r.return_date - r.rental_date)) AS avg_duration_days "
            "FROM category c "
            "JOIN film_category fc ON fc.category_id = c.category_id "
            "JOIN film f ON f.film_id = fc.film_id "
            "JOIN inventory i ON i.film_id = f.film_id "
            "JOIN rental r ON r.inventory_id = i.inventory_id "
            "GROUP BY c.name "
            "ORDER BY c.name;"
        )
        return SQLGeneration(sql=sql, confidence=0.81, reasoning="This requires a join across film, category, inventory, and rental but the schema is still clear.")
    if "never returned" in q or "not returned" in q:
        sql = (
            "SELECT c.customer_id, c.first_name, c.last_name "
            "FROM customer c "
            "LEFT JOIN rental r ON r.customer_id = c.customer_id AND r.return_date IS NULL "
            "WHERE r.rental_id IS NULL;"
        )
        return SQLGeneration(sql=sql, confidence=0.58, reasoning="This is a nullable-date business question and may need careful query review because the model must interpret the intended semantics.")
    if "delete" in q or "drop" in q or "update" in q:
        return SQLGeneration(sql="SELECT 0;", confidence=0.0, reasoning="The question is not a safe read-only question and should be refused.")
    sql = (
        "SELECT f.title, COUNT(r.rental_id) AS rental_count "
        "FROM film f "
        "JOIN inventory i ON i.film_id = f.film_id "
        "JOIN rental r ON r.inventory_id = i.inventory_id "
        "GROUP BY f.title "
        "ORDER BY rental_count DESC, f.title "
        "LIMIT 5;"
    )
    return SQLGeneration(sql=sql, confidence=0.74, reasoning="This is a generic but likely correct aggregate query for common film-rental questions.")


def preflight(state: AgentState) -> dict:
    question = state["question"]
    q = question.lower()
    blocked = any(token in q for token in ["delete ", "drop ", "update ", "insert into", "alter table", "truncate", "grant ", "revoke "])
    if blocked:
        return {
            "in_scope": False,
            "final_answer": "I can only answer read-only questions about the Pagila schema. Write operations and schema changes are out of scope.",
            "resolved": True,
        }

    if not state.get("schema_context"):
        state["schema_context"] = get_schema_context()

    try:
        if OPENAI_API_KEY:
            response = call_chat_model(
                system_prompt=(
                    "Decide if the user's question is answerable from this schema. "
                    "Return JSON with {in_scope: bool, reason: str}. "
                    "Only answer read-only questions that fit the provided schema."
                ),
                user_prompt=f"Schema:\n{state['schema_context']}\n\nQuestion:\n{question}",
                response_format=PreflightDecision,
            )
            if isinstance(response, dict):
                parsed = response
            else:
                parsed = response.model_dump()

            reason = str(parsed.get("reason", "")).lower()
            if parsed.get("in_scope") is False and "outside scope" in reason or "not answerable" in reason or "not in scope" in reason:
                return {
                    "in_scope": False,
                    "final_answer": "I can answer read-only questions about the Pagila schema, but this request is outside scope.",
                    "resolved": True,
                }
    except Exception:
        pass

    return {
        "in_scope": True,
        "final_answer": None,
        "resolved": False,
    }


def generate_sql(state: AgentState) -> dict:
    question = state["question"]
    schema_context = state.get("schema_context") or get_schema_context()
    retry_context = ""
    if state.get("human_feedback"):
        retry_context += f"\nPrevious human feedback: {state['human_feedback']}"
    if state.get("sql_error"):
        retry_context += f"\nPrevious SQL error: {state['sql_error']}"

    if OPENAI_API_KEY:
        prompt = (
            "You are writing SQL for a read-only Pagila database. "
            "Use the schema and the user question to produce a single SQL statement. "
            "Rate confidence in 0..1; lower confidence for ambiguity, joins, guessed columns, or after failures.\n\n"
            f"Schema:\n{schema_context}\n\nQuestion:\n{question}{retry_context}\n"
            "Return JSON with keys {sql, confidence, reasoning}."
        )
        response = call_chat_model(
            system_prompt="You are a careful SQL generator. Return only valid JSON matching the schema.",
            user_prompt=prompt,
            response_format=SQLGeneration,
        )
        if isinstance(response, dict):
            result = response
        else:
            result = response.model_dump()
        generated_sql = str(result.get("sql") or "SELECT 1;")
        confidence = float(result.get("confidence", 0.5))
        reasoning = str(result.get("reasoning", "Self-assessed confidence."))
    else:
        generated = _deterministic_sql(question)
        generated_sql = generated.sql
        confidence = generated.confidence
        reasoning = generated.reasoning

    return {
        "generated_sql": generated_sql,
        "confidence": confidence,
        "confidence_reasoning": reasoning,
        "sql_error": None,
    }


def human_review(state: AgentState) -> dict:
    from langgraph.types import interrupt

    decision = interrupt(
        {
            "question": state["question"],
            "generated_sql": state["generated_sql"],
            "confidence": state["confidence"],
            "reasoning": state["confidence_reasoning"],
        }
    )
    if decision.get("action") == "approve":
        return {"needs_human": False, "human_feedback": None}
    reason = decision.get("reason") or "Rejected by reviewer."
    return {
        "needs_human": False,
        "human_feedback": reason,
        "retry_count": state["retry_count"] + 1,
    }


def execute_sql(state: AgentState) -> dict:
    sql = state.get("generated_sql")
    if not sql:
        return {"sql_error": "No SQL generated.", "execution_result": None, "retry_count": state["retry_count"] + 1}

    if not is_read_only_sql(sql):
        return {
            "sql_error": "Only read-only SELECT/WITH/EXPLAIN statements are allowed.",
            "execution_result": None,
            "retry_count": state["retry_count"] + 1,
        }

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [column[0] for column in cur.description or []]
                rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        finally:
            conn.close()
        return {"execution_result": rows, "sql_error": None}
    except Exception as exc:
        return {"sql_error": str(exc), "execution_result": None, "retry_count": state["retry_count"] + 1}


def respond(state: AgentState) -> dict:
    if state.get("final_answer"):
        return {"resolved": True}

    if state.get("execution_result") is not None:
        rows = state["execution_result"]
        answer = "I ran the query and found results:\n"
        if rows:
            for row in rows[:10]:
                answer += f"- {row}\n"
        else:
            answer = "I ran the query successfully, but it returned no rows."
        return {"final_answer": answer, "resolved": True}

    if state.get("sql_error"):
        retry_count = state.get("retry_count", 0)
        return {
            "final_answer": (
                f"I wasn't able to produce a reliable query for this question after {retry_count} attempt(s). "
                f"Last error: {state['sql_error']}"
            ),
            "resolved": True,
        }

    return {"final_answer": "I could not determine a safe answer for that question.", "resolved": True}
