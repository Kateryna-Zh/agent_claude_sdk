"""Integration-style tests for graph builder routing flow."""

from app.graph import builder


def _base_state():
    return {
        "messages": [],
        "user_input": "hello",
        "intent": "",
        "needs_rag": False,
        "needs_web": False,
        "needs_db": False,
        "rag_context": "",
        "web_context": "",
        "db_context": {},
        "specialist_output": "",
        "user_response": "",
        "final_response": "",
        "session_id": 1,
        "plan_draft": None,
        "plan_confirmed": False,
        "quiz_state": None,
        "quiz_feedback": None,
        "last_intent": None,
        "last_db_context": None,
        "sub_intent": "",
    }


def test_build_graph_db_path_reaches_format_response(monkeypatch):
    monkeypatch.setattr(
        builder,
        "router_node",
        lambda _state: {"intent": "REVIEW", "needs_db": True, "needs_rag": False, "needs_web": False},
    )
    monkeypatch.setattr(builder, "db_agent_node", lambda _state: {"user_response": "db response"})
    monkeypatch.setattr(builder, "format_response_node", lambda state: {"final_response": state.get("user_response", "")})

    graph = builder.build_graph()
    result = graph.invoke(_base_state())
    assert result["final_response"] == "db response"


def test_build_graph_rag_path_routes_to_tutor(monkeypatch):
    monkeypatch.setattr(
        builder,
        "router_node",
        lambda _state: {"intent": "EXPLAIN", "needs_db": False, "needs_rag": True, "needs_web": False},
    )
    monkeypatch.setattr(builder, "retrieve_context_node", lambda _state: {"rag_context": "kb"})
    monkeypatch.setattr(builder, "tutor_node", lambda _state: {"user_response": "tutor response"})
    monkeypatch.setattr(builder, "format_response_node", lambda state: {"final_response": state.get("user_response", "")})

    graph = builder.build_graph()
    result = graph.invoke(_base_state())
    assert result["final_response"] == "tutor response"


def test_build_graph_web_path_routes_to_research(monkeypatch):
    monkeypatch.setattr(
        builder,
        "router_node",
        lambda _state: {"intent": "LATEST", "needs_db": False, "needs_rag": False, "needs_web": True},
    )
    monkeypatch.setattr(builder, "web_search_node", lambda _state: {"web_context": "Result 1: Source"})
    monkeypatch.setattr(builder, "research_node", lambda _state: {"user_response": "research response"})
    monkeypatch.setattr(builder, "format_response_node", lambda state: {"final_response": state.get("user_response", "")})

    graph = builder.build_graph()
    result = graph.invoke(_base_state())
    assert result["final_response"] == "research response"

