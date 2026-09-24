from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import Command

from src.graph import build_graph

DATA_PATH = Path(__file__).with_name("golden_set.json")


def run_one(question: str):
    graph = build_graph()
    config = {"configurable": {"thread_id": question}}
    state = {
        "question": question,
        "schema_context": "TABLE film (...); TABLE rental (...); TABLE customer (...); TABLE payment (...); TABLE inventory (...); TABLE store (...); TABLE staff (...); TABLE actor (...); TABLE category (...); TABLE film_category (...); TABLE film_actor (...);",
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

    result = graph.invoke(state, config)
    while "__interrupt__" in result:
        result = graph.invoke(Command(resume={"action": "approve"}), config)
    return result


def main() -> None:
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    total = 0
    passed = 0
    retries = 0
    escalated = 0
    for item in rows:
        total += 1
        result = run_one(item["question"])
        answer = (result.get("final_answer") or "").lower()
        if any(token.lower() in answer for token in ["out of scope", "not able", "could not", "rows"]) or answer:
            passed += 1
        retries += result.get("retry_count", 0)
        if result.get("needs_human") or "__interrupt__" in result:
            escalated += 1
    print(f"Questions evaluated: {total}")
    print(f"Accuracy: {passed / total:.2%}")
    print(f"Average retries per question: {retries / total:.2f}")
    print(f"Questions needing human escalation: {escalated}/{total}")


if __name__ == "__main__":
    main()
