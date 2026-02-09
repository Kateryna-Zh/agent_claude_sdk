"""LangGraph graph builder — assembles the full agent graph."""

from langgraph.graph import StateGraph, START, END

from app.models.state import GraphState
from app.agents.router_agent import router_node
from app.agents.planner_agent import planner_node
from app.agents.tutor_agent import tutor_node
from app.agents.quiz_agent import quiz_node
from app.agents.research_agent import research_node
from app.tools.retrieve_context import retrieve_context_node
from app.tools.web_search import web_search_node
from app.tools.db_read import db_read_node
from app.tools.db_write import db_write_node
from app.tools.format_response import format_response_node
from app.graph.routing import (
    route_after_router,
    route_to_specialist,
    route_after_specialist,
)


def build_graph():
    """Construct and compile the LangGraph agent graph.

    Graph topology::

        START → router → (conditional) → [retrieve_context / web_search / db_read]
                                                ↓
                                         specialist → (conditional) → [db_write]
                                                                         ↓
                                                                   format_response → END

    Returns
    -------
    langgraph.graph.CompiledGraph
        The compiled, ready-to-invoke graph.
    """
    graph = StateGraph(GraphState)

    # --- Add nodes ---
    graph.add_node("router", router_node)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("db_read", db_read_node)
    graph.add_node("planner", planner_node)
    graph.add_node("tutor", tutor_node)
    graph.add_node("quiz", quiz_node)
    graph.add_node("research", research_node)
    graph.add_node("db_write", db_write_node)
    graph.add_node("format_response", format_response_node)

    # --- Entry point ---
    graph.add_edge(START, "router")

    # --- Conditional: after router → context gathering or specialist ---
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "retrieve_context": "retrieve_context",
            "web_search": "web_search",
            "db_read": "db_read",
            "specialist": "router",  # placeholder; will route to specialist
        },
    )

    # --- Context nodes → specialist ---
    graph.add_conditional_edges("retrieve_context", route_to_specialist,
                                {"planner": "planner", "tutor": "tutor",
                                 "quiz": "quiz", "research": "research"})
    graph.add_conditional_edges("web_search", route_to_specialist,
                                {"planner": "planner", "tutor": "tutor",
                                 "quiz": "quiz", "research": "research"})
    graph.add_conditional_edges("db_read", route_to_specialist,
                                {"planner": "planner", "tutor": "tutor",
                                 "quiz": "quiz", "research": "research"})

    # --- Specialist → optional db_write → format_response ---
    graph.add_conditional_edges(
        "planner", route_after_specialist,
        {"db_write": "db_write", "format_response": "format_response"},
    )
    graph.add_conditional_edges(
        "tutor", route_after_specialist,
        {"db_write": "db_write", "format_response": "format_response"},
    )
    graph.add_conditional_edges(
        "quiz", route_after_specialist,
        {"db_write": "db_write", "format_response": "format_response"},
    )
    graph.add_conditional_edges(
        "research", route_after_specialist,
        {"db_write": "db_write", "format_response": "format_response"},
    )

    # --- db_write → format_response ---
    graph.add_edge("db_write", "format_response")

    # --- format_response → END ---
    graph.add_edge("format_response", END)

    return graph.compile()
