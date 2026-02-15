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
    # search_type="mmr" (Maximal Marginal Relevance) balances relevance with
    # diversity so retrieved chunks cover different aspects of the query.
    # fetch_k=12 fetches twice as many candidates as the final k=6 to give
    # the MMR re-ranker enough material to select diverse results from.
    return chroma.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 6, "fetch_k": 12},
    )
