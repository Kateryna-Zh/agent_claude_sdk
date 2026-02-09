"""Request and response schemas for the /chat endpoint."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Incoming chat message from the user."""

    session_id: int | None = None
    message: str


class ChatResponse(BaseModel):
    """Outgoing response from the assistant."""

    session_id: int
    reply: str
