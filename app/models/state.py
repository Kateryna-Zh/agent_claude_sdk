"""LangGraph shared state definition."""

from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GraphState(TypedDict):
    """Shared state passed between all LangGraph nodes.

    Fields
    ------
    messages : list[BaseMessage]
        Conversation history managed by the ``add_messages`` reducer.
    user_input : str
        Raw text the user sent in this turn.
    intent : str
        Classification produced by the router (PLAN | EXPLAIN | QUIZ | LOG_PROGRESS | REVIEW | LATEST).
    needs_rag : bool
        Whether RAG retrieval is required.
    needs_web : bool
        Whether web search is required.
    needs_db : bool
        Whether a database read is required.
    rag_context : str
        Retrieved document chunks (populated by retrieve_context tool).
    web_context : str
        Web search results (populated by web_search tool).
    db_context : dict[str, Any]
        Data fetched from PostgreSQL.
    specialist_output : str
        Text produced by the specialist agent node.
    final_response : str
        Formatted response returned to the user.
    session_id : int | None
        Active session identifier for DB persistence.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str
    intent: str
    needs_rag: bool
    needs_web: bool
    needs_db: bool
    rag_context: str
    web_context: str
    db_context: dict[str, Any]
    specialist_output: str
    final_response: str
    session_id: int | None
