"""RAG retrieval tool node."""

import os

from app.rag.retriever import get_retriever

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
    print("RETRIEVE HIT", flush=True)
    query = state.get("user_input", "")
    if not query:
        return {"rag_context": ""}

    retriever = get_retriever()
    if hasattr(retriever, "invoke"):
        docs = retriever.invoke(query)
    else:
        docs = retriever.get_relevant_documents(query)

    if not docs:
        print("RETRIEVE EMPTY", flush=True)
        return {"rag_context": ""}

    chunks: list[str] = []
    print(f"RETRIEVE: {len(docs)} docs", flush=True)
    for doc in docs:
        source = doc.metadata.get("source") or ""
        source_name = os.path.basename(source) if source else ""
        preview = doc.page_content.strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:160] + "..."
        print(
            f"RETRIEVE DOC: source={source_name or 'unknown'} preview={preview}",
            flush=True,
        )
        if source_name:
            chunks.append(f"Source: {source_name}\n{doc.page_content.strip()}")
        else:
            chunks.append(doc.page_content.strip())
    joined_text = "\n\n".join(chunks).strip()
    return {"rag_context": joined_text}
