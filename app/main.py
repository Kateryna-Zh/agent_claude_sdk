"""FastAPI application with a single POST /chat endpoint."""

from contextlib import asynccontextmanager
import logging
import concurrent.futures
import itertools

from fastapi import FastAPI, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.graph.builder import build_graph
from app.config import settings
from app.mcp.client import extract_payload
from app.mcp.manager import mcp_manager
from app.db.repository_factory import get_repository

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_manager.start()
    yield
    await mcp_manager.stop()


app = FastAPI(title="Learning Assistant", version="0.1.0", lifespan=lifespan)

graph = build_graph()
_PLAN_DRAFTS: dict[int, dict] = {}
_SESSION_CACHE: dict[int, dict] = {}
_SESSION_COUNTER = itertools.count(1)
 # TODO: Add a debug flag to toggle verbose flow logs (router/db_planner) for demos vs normal runs.


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Handle a user chat message.

    Invokes the LangGraph compiled graph and returns the assistant reply.
    """
    print("CHAT HIT", flush=True)
    print("CHAT: building state", flush=True)
    if settings.db_backend.lower() == "mcp":
        session_id = request.session_id or next(_SESSION_COUNTER)
    else:
        repo = get_repository()
        session_id = request.session_id or repo.create_session()
    plan_draft = _PLAN_DRAFTS.get(session_id)
    last_state = _SESSION_CACHE.get(session_id, {})
    last_intent = last_state.get("last_intent")
    last_db_context = last_state.get("last_db_context")

    state_input = {
        "messages": [],
        "user_input": request.message,
        "intent": "",
        "needs_rag": False,
        "needs_web": False,
        "needs_db": False,
        "rag_context": "",
        "web_context": "",
        "db_context": last_db_context or {},
        "specialist_output": "",
        "user_response": "",
        "final_response": "",
        "session_id": session_id,
        "plan_draft": plan_draft,
        "plan_confirmed": False,
        "last_intent": last_intent,
        "last_db_context": last_db_context,
        "sub_intent": "",
        "db_plan": [],
    }

    print("CHAT: state built", flush=True)
    logger.info("Graph invoke started")
    print("CHAT: graph invoke start", flush=True)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(graph.invoke, state_input)
            done, _ = concurrent.futures.wait(
                [future], timeout=settings.chat_timeout_seconds
            )
            if not done:
                logger.error("Graph invoke timed out")
                print("CHAT: graph invoke timeout", flush=True)
                raise HTTPException(
                    status_code=504, detail="Chat processing timed out"
                )
            result = future.result()
    except concurrent.futures.TimeoutError as exc:
        logger.error("Graph invoke timed out")
        raise HTTPException(status_code=504, detail="Chat processing timed out") from exc
    logger.info("Graph invoke finished")
    print("CHAT: graph invoke finished", flush=True)
    reply = result.get("final_response") or result.get("user_response") or ""

    if result.get("plan_confirmed"):
        _PLAN_DRAFTS.pop(session_id, None)
    elif result.get("plan_draft"):
        _PLAN_DRAFTS[session_id] = result["plan_draft"]
    _SESSION_CACHE[session_id] = {
        "last_intent": result.get("intent", last_intent),
        "last_db_context": result.get("db_context", last_db_context),
    }

    return ChatResponse(session_id=session_id, reply=reply)


@app.get("/health/mcp")
async def health_mcp():
    """Simple MCP health check (connectivity + query)."""
    session = mcp_manager.get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="MCP session not available")

    sql = "SELECT 1 AS ok"
    args = {settings.mcp_query_key: sql}
    if settings.mcp_supports_params:
        args[settings.mcp_params_key] = []

    try:
        result = await session.call_tool(settings.mcp_tool_name, args)
        payload = extract_payload(result)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"ok": True, "payload": payload}
