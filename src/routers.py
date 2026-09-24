from __future__ import annotations

from src.config import CONFIDENCE_THRESHOLD, MAX_RETRIES
from src.state import AgentState


def retry_cap_exceeded(state: AgentState) -> bool:
    return state["retry_count"] >= MAX_RETRIES


def preflight_router(state: AgentState) -> str:
    return "respond" if not state["in_scope"] else "generate_sql"


def confidence_router(state: AgentState) -> str:
    if state["confidence"] is not None and state["confidence"] >= CONFIDENCE_THRESHOLD:
        return "execute_sql"
    return "human_review"


def human_review_router(state: AgentState) -> str:
    if retry_cap_exceeded(state):
        return "respond"
    return "execute_sql" if state["human_feedback"] is None else "generate_sql"


def execute_result_router(state: AgentState) -> str:
    if state["sql_error"] is None:
        return "respond"
    if retry_cap_exceeded(state):
        return "respond"
    return "generate_sql"
