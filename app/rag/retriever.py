"""ChromaDB retriever factory."""


def get_retriever():
    """Create and return a LangChain retriever backed by ChromaDB.

    Returns
    -------
    langchain_core.retrievers.BaseRetriever
        A retriever configured to query the knowledge-base collection.
    """
    # TODO: Instantiate Chroma client with persist_directory from settings
    # TODO: Return chroma.as_retriever(search_kwargs={"k": 4})
    pass
