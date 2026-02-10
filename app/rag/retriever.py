"""ChromaDB retriever factory."""

from langchain_chroma import Chroma

from app.config import settings
from app.llm.ollama_client import get_embeddings


def get_retriever():
    """Create and return a LangChain retriever backed by ChromaDB.

    Returns
    -------
    langchain_core.retrievers.BaseRetriever
        A retriever configured to query the knowledge-base collection.
    """
    embeddings = get_embeddings()
    chroma = Chroma(
        collection_name=settings.chroma_collection,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=embeddings,
    )
    return chroma.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 6, "fetch_k": 12},
    )
