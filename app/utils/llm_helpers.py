"""Shared LLM invocation helper."""

from app.llm.ollama_client import get_chat_model


def invoke_llm(prompt: str, llm=None) -> str:
    """Invoke the chat model and return the stripped response content string."""
    if llm is None:
        llm = get_chat_model()
    response = llm.invoke(prompt)
    return getattr(response, "content", str(response)).strip()
