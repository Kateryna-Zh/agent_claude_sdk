"""LangGraph graph builder — assembles the full agent graph."""

from langgraph.graph import StateGraph, START, END

from app.models.state import GraphState
from app.agents.router_agent import router_node
from app.agents.planner_agent import planner_node
from app.agents.tutor_agent import tutor_node
from app.agents.quiz_agent import quiz_node
from app.agents.research_agent import research_node
from app.agents.db_agent import db_agent_node
from app.tools.retrieve_context import retrieve_context_node
from app.tools.web_search import web_search_node
from app.tools.format_response import format_response_node
from app.graph.routing import (
    route_after_router,
    route_to_specialist,
    route_after_db,
    route_after_quiz,
)


def build_graph():
    """Construct and compile the LangGraph agent graph.

    Graph topology::

        START → router → (conditional) → [retrieve_context / web_search / db]
                                                ↓
                                         specialist → format_response → END

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
    graph.add_node("planner", planner_node)
    graph.add_node("tutor", tutor_node)
    graph.add_node("quiz", quiz_node)
    graph.add_node("research", research_node)
    graph.add_node("db", db_agent_node)
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
            "planner": "planner",
            "tutor": "tutor",
            "quiz": "quiz",
            "research": "research",
            "db": "db",
        },
    )

    # --- Context nodes → specialist ---
    # do we really need to route again after context nodes? We use retrived context only for tutor for now
    graph.add_conditional_edges("retrieve_context", route_to_specialist,
                                {"planner": "planner", "tutor": "tutor",
                                 "quiz": "quiz", "research": "research", "db": "db"})
    # for now web search results are used only for research agent
    graph.add_conditional_edges("web_search", route_to_specialist,
                                {"planner": "planner", "tutor": "tutor",
                                 "quiz": "quiz", "research": "research", "db": "db"})
    graph.add_conditional_edges("db", route_after_db, {
                                "retrieve_context": "retrieve_context",
                                "quiz": "quiz",
                                "format_response": "format_response",
                                })

    graph.add_conditional_edges("quiz", route_after_quiz, {
                                    "db": "db",
                                    "format_response": "format_response",
                                })

    # --- Specialist → format_response ---
    graph.add_edge("planner", "format_response")
    graph.add_edge("tutor", "format_response")
    graph.add_edge("research", "format_response")

    # --- format_response → END ---
    graph.add_edge("format_response", END)

    return graph.compile()
