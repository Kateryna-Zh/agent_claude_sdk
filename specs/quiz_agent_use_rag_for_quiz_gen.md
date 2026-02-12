Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Plan: Quiz Agent — Use RAG (Knowledge Base) for Quiz Generation                              

 Context

 Currently, when a user asks for a quiz (e.g., "quiz me on LangChain"), the quiz agent generates questions purely from LLM general knowledge.
 The RAG retrieval pipeline already exists and is used successfully by the tutor agent, but the quiz flow bypasses it entirely — the router
 doesn't set needs_rag=true for QUIZ intent, and the quiz agent doesn't consume rag_context.

 The goal is to make quiz generation grounded in the Knowledge Base (ChromaDB) so questions are relevant to what the user has actually ingested.

 Tasks

 Task 1: Update router prompt to guide RAG for QUIZ intent

 File: app/prompts/router.py

 - Add a rule: "For QUIZ intent, set needs_rag = true when the quiz topic is covered by the KB."
 - Add an example showing QUIZ with needs_rag: true:
 User: "Quiz me on LangChain"
 Output:
 {"intent":"QUIZ","sub_intent":null,"needs_rag":true,"needs_web":false,"needs_db":false,"plan_title":null,"item_title":null}

 No code changes needed in router_agent.py — it already passes through the LLM's needs_rag decision for QUIZ intent, and the fast-path for quiz
 answers already hardcodes needs_rag: false (correct for scoring).

 Task 2: Update quiz prompts to accept RAG context

 File: app/prompts/quiz.py

 - Update QUIZ_GENERATE_SYSTEM_PROMPT to instruct the LLM to use provided KB context as the primary source for questions.
 - Update QUIZ_GENERATE_USER_PROMPT to include a {rag_context} placeholder alongside existing {user_input} and {db_context}.

 Example updated prompt structure:
 QUIZ_GENERATE_USER_PROMPT = """\
 Topic: {user_input}

 Knowledge base context:
 {rag_context}

 Weak areas from previous attempts:
 {db_context}
 """

 Task 3: Update quiz agent to pass RAG context into prompts

 File: app/agents/quiz_agent.py

 - Read rag_context from state (same pattern as tutor_node).
 - Pass it into QUIZ_GENERATE_USER_PROMPT.format(...).
 - When rag_context is empty, the prompt still works — the LLM falls back to its own knowledge (graceful degradation, no branching needed).
 - Also pass rag_context to _retry_regenerate_mcq_only() so retries are also KB-grounded.

 Task 4: Verify graph topology (no changes needed)

 Files: app/graph/builder.py, app/graph/routing.py

 The graph already supports the retrieve_context → quiz flow:
 - route_after_router routes to retrieve_context when needs_rag=true
 - retrieve_context has a conditional edge to route_to_specialist
 - route_to_specialist maps QUIZ intent to the "quiz" node

 No code changes required here — just verification.

 Flow After Changes

 User: "Quiz me on LangChain"
   → router (sets intent=QUIZ, needs_rag=true)
   → retrieve_context (queries ChromaDB, populates rag_context)
   → quiz (generates questions grounded in KB content)
   → format_response → END

 User: "Quiz me on React" (not in KB)
   → router (sets intent=QUIZ, needs_rag=false)
   → quiz (generates questions from LLM knowledge, as before)
   → format_response → END

 User: "1:A, 2:B, 3:C" (answering quiz)
   → router (fast-path, needs_rag=false)
   → quiz (scores answers, no RAG needed)
   → format_response → END

 Verification

 1. Start the server: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
 2. Test KB-grounded quiz: send "quiz me on LangChain" — verify server logs show RETRIEVE HIT and quiz questions reference KB content
 3. Test non-KB quiz: send "quiz me on React" — verify it still works (LLM-only generation)
 4. Test quiz scoring: answer the quiz — verify scoring still works correctly
 5. Run existing tests: pytest tests/ -v