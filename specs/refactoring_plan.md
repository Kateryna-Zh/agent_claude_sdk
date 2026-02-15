Refactoring Plan: Improve Readability Without Changing Logic                                   

 Context

 The codebase has grown organically and several files have accumulated long functions, duplicated patterns, missing comments, and debug print()
  calls. The goal is to improve readability and maintainability while keeping 100% of the existing logic untouched. No new features, no
 behavior changes.

 ---
 Phase 0: New Shared Utilities (create first — other phases depend on these)

 0A. New file: app/utils/llm_helpers.py

 Extract the 3-line LLM invocation pattern that repeats in quiz_agent (5x), router_agent, planner_agent, tutor_agent:

 def invoke_llm(prompt, llm=None):
     """Invoke the chat model and return the stripped response content string."""
     if llm is None:
         llm = get_chat_model()
     response = llm.invoke(prompt)
     return getattr(response, "content", str(response)).strip()

 0B. New file: app/utils/constants.py

 Centralize regex patterns and magic values duplicated across quiz_agent and router_agent:

 - NUMBERED_ANSWER_RE — compiled r"(\d+)\s*[\).:-]?\s*([A-D])" (used 3x in quiz_agent)
 - HAS_QUIZ_ANSWERS_RE — compiled r"\b\d+\s*[\).:-]?\s*[A-D]\b" (router_agent fast-path)
 - LINE_START_ANSWER_RE — compiled r"^\s*(\d+)\s*[:\)\.\-]\s*([A-D])\b" (quiz_agent fallback)
 - STOPWORDS — frozenset used in _match_retry_questions()
 - MIN_KEYWORD_OVERLAP = 2 — magic threshold in _match_retry_questions()
 - MCP_ROW_KEYS — ("rows", "data", "result", "results") used in mcp_repository + mcp_check

 0C. New file: app/db/row_extract.py

 Deduplicate _extract_rows() which is copy-pasted between:
 - app/db/mcp_repository.py:224-235 (simpler version)
 - app/cli/mcp_check.py:32-49 (general version with recursive dict descent)

 Use the mcp_check version as canonical. Reference MCP_ROW_KEYS from constants.

 ---
 Phase 1: Critical Agent Files

 1A. app/agents/quiz_agent.py (highest impact)

 Split quiz_node() (182 lines) into 4 helper functions:
 Helper: _handle_evaluation(user_input)
 Lines covered: 39-57
 Responsibility: Check for evaluation payload, invoke LLM, return result
 ────────────────────────────────────────
 Helper: _handle_scoring(quiz_state, answer_key, user_answers, user_input, db_context)
 Lines covered: 74-129
 Responsibility: Score answers, build quiz_save payload
 ────────────────────────────────────────
 Helper: _check_rag_relevance(rag_context, topic_name, user_input)
 Lines covered: 137-163
 Responsibility: Two-pass relevance filter (string match + LLM)
 ────────────────────────────────────────
 Helper: _generate_quiz(user_input, rag_context, wrong_questions_text, db_context)
 Lines covered: 165-202
 Responsibility: Generate quiz, extract/retry answer key
 After: quiz_node() becomes ~35 lines of delegation.

 Replace duplicated regex (lines 244, 251, 260, 270) with constants from app/utils/constants.py.

 Replace 5 LLM invocation sites with invoke_llm() from app/utils/llm_helpers.py.

 Replace print() with logger (lines 52, 68, 121). Remove redundant prints at lines 142, 160, 163, 196 where a logger.info immediately precedes
 them.

 Add comments:
 - _check_rag_relevance: explain the two-pass approach (fast substring match, then LLM judgment)
 - Lines 177-181: explain the two-stage answer key recovery (ask LLM for key, then regenerate MCQ-only)
 - _match_retry_questions line 423: explain stopword removal and MIN_KEYWORD_OVERLAP threshold

 1B. app/agents/db_agent.py

 Remove the TODO on line 16 (#TODO: needs refactoring!).

 Extract 2 helpers from _run_tool_calling() (70 lines → ~45 lines):
 ┌───────────────────────────────────────────────┬─────────┬───────────────────────────────────────────────────────────────┐
 │                    Helper                     │  Lines  │                            Purpose                            │
 ├───────────────────────────────────────────────┼─────────┼───────────────────────────────────────────────────────────────┤
 │ _patch_list_plan_items_args(args, db_context) │ 107-111 │ Fill in plan_id/title from db_context when LLM omitted them   │
 ├───────────────────────────────────────────────┼─────────┼───────────────────────────────────────────────────────────────┤
 │ _patch_write_plan_args(args, state)           │ 112-124 │ Ensure write_plan has full draft payload; return None to skip │
 └───────────────────────────────────────────────┴─────────┴───────────────────────────────────────────────────────────────┘
 Fix the if/elif bug on line 154: if name == "update_item_status" should be elif to continue the chain from line 152.

 Convert _format_tool_result_confirmation() (lines 140-174) to dict dispatch:
 _CONFIRMATION_FORMATTERS = {
     "write_plan": lambda d: f"Plan created (plan {d.get('created_plan_id')}).",
     "add_plan_item": lambda d: ...,
     ...
 }
 Replaces the long if-elif chain with a lookup.

 Add docstring to _resolve_plan_ids() (line 347) explaining exact vs. substring match logic.

 1C. app/agents/router_agent.py

 - Replace inline regex on line 24 with HAS_QUIZ_ANSWERS_RE from constants
 - Replace LLM invocation boilerplate (lines 40-44, 56-57) with invoke_llm()
 - Remove import re (no longer needed)

 ---
 Phase 2: Secondary Files

 2A. app/tools/db_tools.py

 Add docstring + comments to _strip_extras() (lines 46-69): explain that it recursively strips fields not declared in the Pydantic model,
 walking nested BaseModel and list[BaseModel] fields.

 Rename variables in list comprehensions:
 - _find_plan_candidates line 370: p → candidate
 - _find_item_candidates line 415: i → candidate

 2B. app/db/mcp_repository.py

 Replace _extract_rows() (lines 224-235) with import from app/db/row_extract.py.

 Add docstrings to MCP parameter conversion functions:
 - _to_dollar_params() (line 179): explain %s → $N conversion for pg-mcp-server
 - _inline_params() (line 191): explain parameter inlining when MCP_SUPPORTS_PARAMS=false
 - _literal() (line 205): explain SQL literal conversion for different Python types
 - _execute() (line 160): explain parameter conversion dispatch

 2C. app/cli/mcp_check.py

 Replace _extract_rows() (lines 32-49) with import from app/db/row_extract.py.

 Add comment to _args() (line 70) explaining it mirrors MCPRepository._execute() but is intentionally duplicated to test raw MCP connectivity.

 2D. app/db/repository.py

 Add docstring to _execute() (line 12): explain fetch parameter values ("one", "all", None) and error handling.

 Fix missing blank line between save_quiz_attempt and get_weak_topics (line 159).

 ---
 Phase 3: Lower-Priority Files

 3A. app/graph/routing.py

 Remove redundant print() calls on lines 79, 84, 87 (each has a logger.info immediately before).

 3B. app/agents/planner_agent.py

 - Replace print("PLANNER HIT") (line 29) with logger.info("Planner node invoked")
 - Replace LLM boilerplate (lines 43-47, 54-55) with invoke_llm()

 3C. app/agents/tutor_agent.py

 Replace LLM boilerplate (lines 43-45) with invoke_llm().

 3D. app/mcp/manager.py

 Add docstring to _parse_args() (line 81) explaining the comma-vs-space heuristic for CSV vs shell-style argument parsing.

 3E. app/mcp/client.py

 Add docstring to extract_payload() (line 13) explaining the three extraction strategies (structuredContent, text content → JSON parse,
 fallback to text dict).

 3F. app/rag/ingest.py and app/rag/retriever.py

 Add inline comments explaining magic values:
 - ingest.py line 32-34: chunk_size=1000, chunk_overlap=200
 - retriever.py line 23-25: search_type="mmr", k=6, fetch_k=12

 3G. app/main.py

 Replace print() calls (lines 41-42, 45, 78, 80, 89, 98) with logger.info or remove where a logger call immediately precedes. Remove the TODO
 on line 32.

 ---
 Files Modified (summary)
 ┌─────────────────────────────┬──────────────────────────────────────────────────────────────────────────┐
 │            File             │                                 Changes                                  │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/utils/llm_helpers.py    │ NEW — shared LLM invocation helper                                       │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/utils/constants.py      │ NEW — shared regex patterns and magic values                             │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/db/row_extract.py       │ NEW — canonical extract_rows() for MCP payloads                          │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/agents/quiz_agent.py    │ Split quiz_node(), replace regex/LLM duplication, print→logger, comments │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/agents/db_agent.py      │ Extract helpers, dict dispatch, fix elif, docstring, remove TODO         │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/agents/router_agent.py  │ Use shared constants/helpers, remove import re                           │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/tools/db_tools.py       │ Docstring on _strip_extras(), rename loop vars                           │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/db/mcp_repository.py    │ Use shared extract_rows(), add docstrings                                │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/cli/mcp_check.py        │ Use shared extract_rows(), add comment                                   │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/db/repository.py        │ Docstring on _execute(), fix blank line                                  │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/graph/routing.py        │ Remove redundant prints                                                  │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/agents/planner_agent.py │ print→logger, use invoke_llm()                                           │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/agents/tutor_agent.py   │ Use invoke_llm()                                                         │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/mcp/manager.py          │ Docstring on _parse_args()                                               │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/mcp/client.py           │ Docstring on extract_payload()                                           │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/rag/ingest.py           │ Comments on chunk_size/overlap                                           │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/rag/retriever.py        │ Comments on MMR params                                                   │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
 │ app/main.py                 │ print→logger, remove TODO                                                │
 └─────────────────────────────┴──────────────────────────────────────────────────────────────────────────┘
 ---
 Verification

 After each phase:
 pytest tests/ -v

 All existing tests must pass unchanged. The refactoring is purely structural — no behavior changes. The test files only import public APIs
 (route_after_quiz, execute_tool, db_agent, router_agent, routing, RouterOutput), none of which are renamed.

 Final sanity check:
 ruff check app/ tests/