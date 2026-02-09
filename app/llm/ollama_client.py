"""Factories for Ollama-backed LLM and embeddings."""


def get_chat_model():
    """Return a ChatOllama instance configured from settings.

    Returns
    -------
    langchain_ollama.ChatOllama
        A chat model connected to the local Ollama server.
    """
    # TODO: Return ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)
    pass


def get_embeddings():
    """Return an OllamaEmbeddings instance configured from settings.

    Returns
    -------
    langchain_ollama.OllamaEmbeddings
        An embedding model for vectorising documents and queries.
    """
    # TODO: Return OllamaEmbeddings(base_url=settings.ollama_base_url, model=settings.ollama_embed_model)
    pass
