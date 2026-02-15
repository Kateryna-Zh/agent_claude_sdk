"""Shared regex patterns and magic values used across agents."""

import re

# Matches "1. A", "2) B", "3: C", "4-D", "5 A" etc. — numbered answer with letter.
# Used in quiz_agent (_extract_answer_key, _parse_answer_list) for answer parsing.
NUMBERED_ANSWER_RE = re.compile(r"(\d+)\s*[\).:-]?\s*([A-D])", re.IGNORECASE)

# Detects whether user input contains quiz-style numbered answers (word-boundary variant).
# Used in router_agent for fast-path quiz answer detection.
HAS_QUIZ_ANSWERS_RE = re.compile(r"\b\d+\s*[\).:-]?\s*[A-D]\b", re.IGNORECASE)

# Line-start variant for answer key extraction fallback.
# Used in quiz_agent _extract_answer_key when inline pattern finds nothing.
LINE_START_ANSWER_RE = re.compile(r"^\s*(\d+)\s*[:\)\.\-]\s*([A-D])\b", re.IGNORECASE)

# Common English stopwords removed before keyword overlap matching.
STOPWORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "is", "of", "in", "to", "and", "or"}
)

# Minimum keyword overlap required to match a retry question to a generated question.
MIN_KEYWORD_OVERLAP = 2

# Keys to probe when extracting row data from MCP server responses.
MCP_ROW_KEYS = ("rows", "data", "result", "results")
