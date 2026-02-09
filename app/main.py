"""FastAPI application with a single POST /chat endpoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.graph.builder import build_graph
from app.config import settings
from app.mcp.client import extract_payload
from app.mcp.manager import mcp_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_manager.start()
    yield
    await mcp_manager.stop()


app = FastAPI(title="Learning Assistant", version="0.1.0", lifespan=lifespan)

graph = build_graph()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Handle a user chat message.

    Invokes the LangGraph compiled graph and returns the assistant reply.
    """
    # TODO: Invoke graph with request.message and request.session_id
    # TODO: Return ChatResponse with session_id and reply from graph output
    pass


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
