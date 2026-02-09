"""FastAPI application with a single POST /chat endpoint."""

from fastapi import FastAPI

from app.schemas.chat import ChatRequest, ChatResponse
from app.graph.builder import build_graph

app = FastAPI(title="Learning Assistant", version="0.1.0")

graph = build_graph()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Handle a user chat message.

    Invokes the LangGraph compiled graph and returns the assistant reply.
    """
    # TODO: Invoke graph with request.message and request.session_id
    # TODO: Return ChatResponse with session_id and reply from graph output
    pass
