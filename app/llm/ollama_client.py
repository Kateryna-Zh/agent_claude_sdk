"""Factories for Ollama-backed LLM and embeddings."""

from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.config import settings


def get_chat_model():
    """Return a ChatOllama instance configured from settings.

    Returns
    -------
    langchain_ollama.ChatOllama
        A chat model connected to the local Ollama server.
    """
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        request_timeout=settings.ollama_timeout_seconds,
    )


def get_embeddings():
    """Return an OllamaEmbeddings instance configured from settings.

    Returns
    -------
    langchain_ollama.OllamaEmbeddings
        An embedding model for vectorising documents and queries.
    """
    return OllamaEmbeddings(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embed_model,
    )
