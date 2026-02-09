"""RAG retrieval tool node."""

from app.models.state import GraphState


def retrieve_context_node(state: GraphState) -> dict:
    """Query ChromaDB for relevant document chunks.

    Populates: rag_context.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``rag_context``.
    """
    # TODO: Get retriever from app.rag.retriever.get_retriever()
    # TODO: Invoke retriever with state["user_input"]
    # TODO: Join document contents into a single string
    # TODO: Return {"rag_context": joined_text}
    pass
