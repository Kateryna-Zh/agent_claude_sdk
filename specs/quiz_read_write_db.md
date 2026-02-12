ere is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Plan: Quiz Agent — RAG-Based Quizzes + Wrong-Answer Tracking (Agentic Flow)

 Context

 
 Wrong answers are not tracked. When a user gets quiz questions wrong, those questions should be saved to the DB via the db_agent. On
 subsequent quizzes, previously-wrong questions should be fetched from DB and re-included. When the user finally answers them correctly, they
 get removed.

 The solution uses a fully agentic graph flow — DB operations go through the db_agent node, RAG through retrieve_context, with proper
 conditional routing between them.

 ---
 New Graph Flows

 Quiz Generation (Turn 1):

 router (QUIZ, needs_db=true, needs_rag=true/false)
   → db_agent (fetch wrong questions for topic → db_context["wrong_questions"])
   → [if needs_rag] retrieve_context (ChromaDB → rag_context)
   → quiz (generate quiz using rag_context + wrong_questions)
   → format_response → END

 Quiz Scoring (Turn 2):

 router (QUIZ fast-path, needs_db=false)
   → quiz (score answers, put save/delete instructions in db_context["quiz_save"])
   → db_agent (save wrong answers, delete correct retries)
   → format_response → END

 Existing flows (REVIEW, LOG_PROGRESS, etc.) — unchanged:

 router → db → format_response → END

 ---
 Tasks

 Task 1: Add quiz_results_saved field to GraphState

 File: app/models/state.py

 Add one new field:
 quiz_results_saved: bool  # Prevents db→quiz loop after post-quiz save

 Task 2: Change graph edges from fixed to conditional for db and quiz nodes

 File: app/graph/builder.py

 Current (fixed edges):
 graph.add_edge("db", "format_response")
 graph.add_edge("quiz", "format_response")

 New (conditional edges):
 graph.add_conditional_edges("db", route_after_db, {
     "retrieve_context": "retrieve_context",
     "quiz": "quiz",
     "format_response": "format_response",
 })

 graph.add_conditional_edges("quiz", route_after_quiz, {
     "db": "db",
     "format_response": "format_response",
 })

 Import route_after_db and route_after_quiz from app.graph.routing.

 Task 3: Add two new routing functions

 File: app/graph/routing.py

 def route_after_db(state: GraphState) -> str:
     """After db node: for QUIZ pre-fetch, continue to RAG or quiz. Otherwise format."""
     intent = state.get("intent")
     if intent == "QUIZ" and not state.get("quiz_results_saved"):
         # Pre-quiz DB done → continue to RAG retrieval or quiz
         if state.get("needs_rag"):
             return "retrieve_context"
         return "quiz"
     # All other intents (REVIEW, LOG_PROGRESS, PLAN/SAVE_PLAN) + post-quiz DB
     return "format_response"


 def route_after_quiz(state: GraphState) -> str:
     """After quiz node: if scoring produced save/delete instructions, route to db."""
     db_context = state.get("db_context") or {}
     if db_context.get("quiz_save"):
         return "db"
     return "format_response"

 Task 4: Force needs_db=true for QUIZ intent in router

 File: app/agents/router_agent.py

 Add one line after the existing intent-specific overrides (around line 89):
 elif parsed.intent == "QUIZ":
     needs_db = True  # Always check for prior wrong questions 

 This ensures every QUIZ generation goes through db_agent first. The fast-path (quiz answers) is unaffected — it returns before this code runs
 (line 24-33).


 Task 6: Add repository methods

 Files: app/db/mcp_repository.py, app/db/repository.py

 Add two new methods to both repositories:

 1. get_wrong_questions(topic_id: int) -> list[dict]
 SELECT attempt_id, question FROM quiz_attempts WHERE topic_id = %s
 2. delete_quiz_attempt(attempt_id: int) -> None
 DELETE FROM quiz_attempts WHERE attempt_id = %s

 Existing methods we'll reuse (no changes needed):
 - upsert_topic(name, tags) → creates topic if needed, returns topic_id
 - save_quiz_attempt(topic_id, question, user_answer, score, feedback) → saves attempt

 Task 7: Add QUIZ handling to db_agent

 File: app/agents/db_agent.py

 Add QUIZ intent handling at the top of db_agent_node():

 Pre-quiz (no quiz_save in db_context):
 1. Extract topic name from user_input via _extract_topic_name() (regex: strip "quiz/test me on/about")
 2. Call repo.upsert_topic(topic_name) → get topic_id
 3. Call repo.get_wrong_questions(topic_id) → list of {attempt_id, question}
 4. Store in db_context: wrong_questions, quiz_topic_id, quiz_topic_name
 5. Return {"db_context": db_context} — does NOT set specialist_output or user_response (these will come from quiz node later)

 Post-quiz (quiz_save present in db_context):
 1. Pop quiz_save from db_context
 2. For each wrong answer: repo.save_quiz_attempt(topic_id, question, user_answer, 0.0, None)
 3. For each correct retry: repo.delete_quiz_attempt(attempt_id)
 4. Return {"quiz_results_saved": True, "db_context": db_context} — does NOT overwrite specialist_output / user_response (preserves quiz scoring
  output)

 Add helper:
 def _extract_topic_name(user_input: str) -> str:
     """Strip common quiz prefixes to get the topic name."""
     cleaned = re.sub(
         r'^(quiz|test|examine)\s+(me\s+)?(on|about)\s+',
         '', user_input, flags=re.IGNORECASE
     ).strip()
     return cleaned or user_input

 Task 8: Update quiz prompts

 File: app/prompts/quiz.py

 - Update QUIZ_GENERATE_SYSTEM_PROMPT:
   - When KB context is provided, base questions on it
   - When retry questions are provided, re-include them in the quiz
 - Update QUIZ_GENERATE_USER_PROMPT — add {rag_context} and {wrong_questions}:
 Topic: {user_input}

 Knowledge base context:
 {rag_context}

 Previously wrong questions (must include in quiz):
 {wrong_questions}

 
 Task 9: Update quiz agent

 File: app/agents/quiz_agent.py

 9a. Quiz generation changes:

 1. Read rag_context from state
 2. Read db_context["wrong_questions"] — format as numbered text for the prompt
 3. Read db_context["quiz_topic_id"] and db_context["quiz_topic_name"]
 4. Pass rag_context and formatted wrong questions to QUIZ_GENERATE_USER_PROMPT.format(...)
 5. After generating quiz, add _extract_questions() helper to parse quiz text into {number: question_text} dict
 6. Track which generated questions correspond to DB retry questions — store retry_attempt_ids in quiz_state (map of question number →
 attempt_id)
 7. Store topic_id and topic_name in quiz_state

 9b. Quiz scoring changes:

 After _score_answers():
 1. Get topic_id from quiz_state
 2. Extract individual question texts via _extract_questions(quiz_state["quiz_text"])
 3. Build quiz_save payload:
   - wrong_answers: list of {question, user_answer} for incorrect answers
   - correct_retries: list of attempt_id values for correctly-answered retry questions
   - topic_id: from quiz_state
 4. Put quiz_save into db_context — this triggers route_after_quiz → db
 5. Return {"user_response": score_text, "specialist_output": score_text, "quiz_state": None, "db_context": db_context}

 9c. Retry regeneration:

 Pass rag_context to _retry_regenerate_mcq_only() so retries are also KB-grounded.

 ---
 Files Modified
 ┌────────────────────────────┬───────────────────────────────────────────────────┐
 │            File            │                      Change                       │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/models/state.py        │ Add quiz_results_saved: bool field                │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/graph/builder.py       │ Change db and quiz edges to conditional           │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/graph/routing.py       │ Add route_after_db(), route_after_quiz()          │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/agents/router_agent.py │ Force needs_db=true for QUIZ intent               │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/prompts/router.py      │ Add QUIZ+RAG rule and example                     │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/db/mcp_repository.py   │ Add get_wrong_questions(), delete_quiz_attempt()  │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/db/repository.py       │ Add get_wrong_questions(), delete_quiz_attempt()  │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/agents/db_agent.py     │ Add pre-quiz and post-quiz QUIZ handling          │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/prompts/quiz.py        │ Add {rag_context}, {wrong_questions} placeholders │
 ├────────────────────────────┼───────────────────────────────────────────────────┤
 │ app/agents/quiz_agent.py   │ RAG context, wrong questions, scoring → quiz_save │
 └────────────────────────────┴───────────────────────────────────────────────────┘
 Verification

 1. pytest tests/ -v — existing tests pass
 2. Start server: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
 3. KB-grounded quiz: "quiz me on LangChain" → logs show db_agent fetches wrong questions, then RETRIEVE HIT, quiz questions reference KB
 content
 4. Answer incorrectly → verify flow goes quiz → db_agent → format_response; check quiz_attempts table has entries
 5. Quiz same topic again → verify db_agent fetches those wrong questions, they appear in new quiz
 6. Answer retries correctly → verify those entries are deleted from quiz_attempts
 7. Non-KB quiz: "quiz me on React" → db_agent runs (no wrong questions), skips RAG, LLM-only quiz
 8. Existing flows: REVIEW, LOG_PROGRESS still work unchanged (db → format_response)