"""Web search summarization prompt template."""

RESEARCH_SYSTEM_PROMPT = """\
You are a research assistant. Summarise the web search results below into a
concise, informative briefing for the user. Focus on:

- What changed or what's new.
- Practical implications for a learner/developer.
- Links to authoritative sources when available.

Web search results:
{web_context}
"""

RESEARCH_USER_PROMPT = """\
User's question: {user_input}
"""
