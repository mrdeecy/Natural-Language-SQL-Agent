from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.types import Command

from src.graph import build_graph

DATA_PATH = Path(__file__).with_name("golden_set.json")


def run_one(question: str):
    graph = build_graph()
    config = {
        "configurable": {"thread_id": f"eval:{question}"},
        "run_name": "pagila-sql-agent-evaluation",
        "tags": ["evaluation", "pagila"],
        "metadata": {"evaluation_question": question},
    }
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


def score_item(item: dict, result: dict) -> dict[str, object]:
    sql = (result.get("generated_sql") or "").lower()
    answer = (result.get("final_answer") or "").lower()
    expected_sql = [value.lower() for value in item.get("expected_sql_contains", [])]
    expected_result = [value.lower() for value in item.get("expected_result_contains", [])]
    is_refusal = "out of scope" in expected_result

    sql_passed = all(value in sql for value in expected_sql) if not is_refusal else True
    result_text = f"{answer}\n{json.dumps(result.get('execution_result'), default=str)}"
    result_passed = all(value in result_text for value in expected_result)
    executed = result.get("execution_result") is not None
    error_free = result.get("sql_error") is None

    return {
        "id": item["id"],
        "question": item["question"],
        "sql_passed": sql_passed,
        "result_passed": result_passed,
        "executed": executed,
        "error_free": error_free,
        "passed": sql_passed and result_passed and (error_free or is_refusal),
        "status": result.get("status", "unknown"),
    }


def main() -> None:
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    total = 0
    passed = 0
    sql_passed = 0
    result_passed = 0
    executed = 0
    retries = 0
    escalated = 0
    failures = []
    for item in rows:
        total += 1
        result = run_one(item["question"])
        score = score_item(item, result)
        if score["passed"]:
            passed += 1
        if score["sql_passed"]:
            sql_passed += 1
        if score["result_passed"]:
            result_passed += 1
        if score["executed"]:
            executed += 1
        retries += result.get("retry_count", 0)
        if result.get("needs_human") or "__interrupt__" in result:
            escalated += 1
        if not score["passed"]:
            failures.append({
                "id": item["id"],
                "question": item["question"],
                "sql_error": result.get("sql_error"),
                "answer": result.get("final_answer"),
            })
    print(f"Questions evaluated: {total}")
    print(f"Contract pass rate: {passed / total:.2%}")
    print(f"SQL contract pass rate: {sql_passed / total:.2%}")
    print(f"Result contract pass rate: {result_passed / total:.2%}")
    print(f"Successful executions: {executed}/{total}")
    print(f"Average retries per question: {retries / total:.2f}")
    print(f"Questions needing human escalation: {escalated}/{total}")
    for failure in failures:
        print(f"Failure {failure['id']}: {failure['question']}")
        if failure["sql_error"]:
            print(f"  SQL error: {failure['sql_error']}")
        elif failure["answer"]:
            print(f"  Answer: {failure['answer']}")


if __name__ == "__main__":
    main()
