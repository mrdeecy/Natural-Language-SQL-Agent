from typing import TypedDict


class AgentState(TypedDict):
    question: str
    schema_context: str
    generated_sql: str | None
    confidence: float | None
    confidence_reasoning: str | None
    sql_error: str | None
    execution_result: list | None
    needs_human: bool
    human_feedback: str | None
    retry_count: int
    final_answer: str | None
    resolved: bool
    in_scope: bool
