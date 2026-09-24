from __future__ import annotations

import sys
import uuid
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.types import Command

from src.graph import build_graph
from src.schema_context import get_schema_context


_GRAPH_CACHE: dict[str, object] = {}


def _get_graph_for_thread(thread_id: str):
    graph = _GRAPH_CACHE.get(thread_id)
    if graph is None:
        graph = build_graph()
        _GRAPH_CACHE[thread_id] = graph
    return graph


def _serialize_result(question: str, result: dict, thread_id: str | None = None) -> dict:
    return {
        "status": "ok" if result.get("final_answer") or result.get("execution_result") is not None else "error",
        "question": question,
        "generated_sql": result.get("generated_sql"),
        "confidence": result.get("confidence"),
        "confidence_reasoning": result.get("confidence_reasoning"),
        "final_answer": result.get("final_answer"),
        "execution_result": result.get("execution_result"),
        "sql_error": result.get("sql_error"),
        "retry_count": result.get("retry_count", 0),
        "resolved": result.get("resolved", False),
        "thread_id": thread_id,
    }


def run_question(
    question: str,
    auto_approve: bool = True,
    thread_id: str | None = None,
    decision: dict | None = None,
) -> dict:
    if not question or not question.strip():
        return {
            "status": "empty",
            "question": question,
            "generated_sql": None,
            "confidence": None,
            "confidence_reasoning": None,
            "final_answer": "Please enter a question.",
            "execution_result": None,
            "sql_error": None,
            "retry_count": 0,
            "resolved": False,
            "thread_id": thread_id,
        }

    thread_id = thread_id or str(uuid.uuid4())
    app = _get_graph_for_thread(thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    if decision is not None:
        resume_payload = {
            "action": decision.get("action", "approve"),
            "reason": decision.get("reason"),
        }
        result = app.invoke(Command(resume=resume_payload), config)
        return _serialize_result(question, result, thread_id)

    initial_state = {
        "question": question,
        "schema_context": get_schema_context(),
        "generated_sql": None,
        "confidence": None,
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

    result = app.invoke(initial_state, config)

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        if not auto_approve:
            return {
                "status": "needs_human",
                "question": question,
                "generated_sql": result.get("generated_sql"),
                "confidence": result.get("confidence"),
                "confidence_reasoning": result.get("confidence_reasoning"),
                "final_answer": None,
                "execution_result": None,
                "sql_error": None,
                "retry_count": result.get("retry_count", 0),
                "payload": payload,
                "resolved": False,
                "thread_id": thread_id,
            }

        result = app.invoke(Command(resume={"action": "approve"}), config)

    return _serialize_result(question, result, thread_id)


def ask(question: str):
    result = run_question(question, auto_approve=True)
    return result.get("final_answer")


if __name__ == "__main__":
    for q in [
        "Which 5 films were rented the most?",
        "What is the average rental duration by film category?",
        "Which customers have never returned a film?",
    ]:
        print(f"\nQuestion: {q}\nAnswer: {ask(q)}")
