from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src import nodes, routers
from src.state import AgentState


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("preflight", nodes.preflight)
    g.add_node("generate_sql", nodes.generate_sql)
    g.add_node("human_review", nodes.human_review)
    g.add_node("execute_sql", nodes.execute_sql)
    g.add_node("respond", nodes.respond)

    g.set_entry_point("preflight")

    g.add_conditional_edges("preflight", routers.preflight_router, {
        "generate_sql": "generate_sql",
        "respond": "respond",
    })

    g.add_conditional_edges("generate_sql", routers.confidence_router, {
        "execute_sql": "execute_sql",
        "human_review": "human_review",
    })

    g.add_conditional_edges("human_review", routers.human_review_router, {
        "execute_sql": "execute_sql",
        "generate_sql": "generate_sql",
        "respond": "respond",
    })

    g.add_conditional_edges("execute_sql", routers.execute_result_router, {
        "respond": "respond",
        "generate_sql": "generate_sql",
    })

    g.add_edge("respond", END)

    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)
