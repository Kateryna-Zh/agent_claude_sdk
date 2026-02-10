"""Research agent node — summarises web search results."""

import logging

from app.llm.ollama_client import get_chat_model
from app.models.state import GraphState
from app.prompts.research import RESEARCH_SYSTEM_PROMPT, RESEARCH_USER_PROMPT

logger = logging.getLogger("uvicorn.error")


def research_node(state: GraphState) -> dict:
    """Summarise web search results into a user-friendly briefing.

    Populates: specialist_output.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``specialist_output``.
    """
    web_context = state.get("web_context", "")
    user_input = state.get("user_input", "")
    if not web_context.strip():
        msg = "I couldn't find any web results to summarize for that question."
        logger.info("RESEARCH: no web_context")
        return {"user_response": msg, "specialist_output": msg}

    logger.info("RESEARCH: web_context chars=%d", len(web_context))
    # NOTE: Deterministic summary to avoid hallucinations: format provided results only.
    # TODO(deletion): If we re-enable LLM summarization, remove this path or move it
    # into a dedicated helper with tests.
    entries = [e.strip() for e in web_context.split("\n\n") if e.strip()]
    lines = ["Based on the provided web results, here are the top sources and excerpts:"]
    update_mentions = []
    keywords = ("release", "version", "update", "announc", "beta", "rc", "latest", "changes", "release notes")

    for entry in entries:
        title = ""
        url = ""
        snippet = ""
        for row in entry.splitlines():
            if row.startswith("Result "):
                title = row.split(":", 1)[-1].strip()
            elif row.startswith("URL:"):
                url = row.split(":", 1)[-1].strip()
            elif row.startswith("Snippet:"):
                snippet = row.split(":", 1)[-1].strip()
        if title or url:
            label = title or "Untitled"
            if url:
                label = f"{label} — {url}"
            lines.append(f"- {label}")
        if snippet:
            lines.append(f"  Snippet: {snippet}")
            lower = snippet.lower()
            if any(k in lower for k in keywords):
                update_mentions.append(snippet)

    if update_mentions:
        lines.append("Possible update-related mentions found in snippets:")
        for mention in update_mentions[:3]:
            lines.append(f"- {mention}")
    else:
        lines.append("No explicit update statements were found in the provided snippets.")

    content = "\n".join(lines).strip()
    return {"user_response": content, "specialist_output": content}
