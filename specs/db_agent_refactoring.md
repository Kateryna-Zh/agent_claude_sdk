# DB Agent Refactoring Spec

## Purpose
Move DB operations to explicit, validated tool contracts so the db agent can be more agentic (LLM chooses tools) while behavior stays predictable, testable, and safe.

## Why This Change
- Current tool outputs are inconsistent (mix of raw data, ad-hoc `error` keys, and side-effects), making agent behavior brittle.
- Hard-coded intent branches in `db_agent` reduce flexibility and are hard to extend safely.
- Pydantic validation enables structured errors, consistent tool interfaces, and spec-driven tests.

## Goals
- Standardize tool contracts: `ok=true` with `data`, `ok=false` with structured error.
- Validate all tool inputs with Pydantic.
- Make db agent rely on tool contracts for follow-ups and confirmation messaging.
- Keep DB operations deterministic and side-effect safe.

## Non-Goals
- Changing the underlying DB schema.
- Rewriting repository logic or storage backend.
- UI or prompt redesign outside db agent and tools.

## Tool Contract (Core)
All DB tools must return one of these shapes:

```json
{
  "ok": true,
  "data": { /* tool-specific payload */ }
}
```

```json
{
  "ok": false,
  "error": {
    "code": "validation_error|not_found|conflict|unknown_tool|db_error|permission_denied",
    "message": "Human-readable summary",
    "details": { /* optional */ }
  }
}
```

## Validation Rules
- Every tool input must be validated by a Pydantic model.
- Use Pydantic v2.12.5 (installed in this project).
- Pydantic model config: `model_config = ConfigDict(extra="forbid")` to reject unknown fields.
- Validation errors return `ok=false` with `code=validation_error`.
- If no entity is found, return `ok=false` with `code=not_found`.
- Avoid throwing raw exceptions to the agent. Convert DB exceptions to `db_error`.

## Error Details Shape
For `validation_error`, use:

```json
{
  "details": {
    "fields": [
      { "field": "field_name", "message": "reason" }
    ]
  }
}
```

For `not_found`, use:

```json
{
  "details": {
    "entity_type": "plan|item|topic|flashcard|message",
    "query": { "plan_id": 123, "plan_title": "..." }
  }
}
```

## Proposed Files and Responsibilities

### New Files
- `app/tools/contracts.py`
  - Defines `ToolSuccess`, `ToolError`, `ToolResult`.
  - Helper constructors like `ok(data)` and `err(code, message, details=None)`.

- `app/tools/db_tool_models.py`
  - Pydantic input models for each tool.
  - Shared types (PlanId, TopicId, etc.) and validators.

### Modified Files
- `app/tools/db_tools.py`
  - Validate args via `db_tool_models` before executing.
  - Return `ToolResult` consistently.
  - Replace ad-hoc `{"error": ...}` responses.

- `app/agents/db_agent.py`
  - Interpret `ToolResult` to produce confirmations or follow-up questions.
  - Reduce or remove hard-coded intent branches to let tool-calling drive decisions.

- `tests/test_db_tools_contracts.py`
  - Validate `ok=false` on invalid inputs.
  - Validate `ok=true` on core happy paths.

## Step-by-Step Tasks

1. **Define Contract Types**
   - Create `app/tools/contracts.py`.
   - Implement helpers: `ok(data)`, `err(code, message, details=None)`.

2. **Add Pydantic Models**
   - Create `app/tools/db_tool_models.py` with input models for all tools in `db_tools.py`.
   - Add minimal validators (e.g., non-empty titles, required IDs, numeric ranges).

3. **Refactor DB Tools**
   - Update each tool in `app/tools/db_tools.py`:
     - Parse `args` into a Pydantic model.
     - On validation failure, return `err("validation_error", ...)`.
     - On not found, return `err("not_found", ...)`.
     - On success, return `ok({...})`.

4. **Update db_agent**
   - In `app/agents/db_agent.py`, update result handling:
     - `ok=true`: use existing confirmation formatting.
     - `ok=false`: surface message or ask for clarifying info.
   - Reduce intent-based branching to allow tool-calling to decide.

5. **Tests**
   - Add `tests/test_db_tools_contracts.py` for tool validation and success paths.
   - Cover at least: `list_plans`, `list_plan_items`, `write_plan`, `update_item_status`.

## Tool Inventory and Contracts
This table defines the concrete tool list and expected input/output shapes.

- `list_plans`
  - Input model: `ListPlansInput` (no fields)
  - Success `data`: `{ "plans": [ { "plan_id": int, "title": str, "created_at": str } ] }`
  - Errors: `db_error`
- `list_plan_items`
  - Input model: `ListPlanItemsInput` (`plan_id?: int|\"latest\"`, `plan_title?: str`)
  - Success `data`: `{ "plan_items": { "<plan_id>": [ { "item_id": int, "title": str, "status": str } ] } }`
  - Errors: `validation_error`, `not_found`, `db_error`
- `write_plan`
  - Input model: `WritePlanInput` (`title: str`, `items: list`)
  - Success `data`: `{ "created_plan_id": int }`
  - Errors: `validation_error`, `db_error`
- `add_plan_item`
  - Input model: `AddPlanItemInput` (`plan_id: int|\"latest\"`, `title: str`, `due_date?: str`, `notes?: str`)
  - Success `data`: `{ "item_id": int }`
  - Errors: `validation_error`, `not_found`, `db_error`
- `update_item_status`
  - Input model: `UpdateItemStatusInput` (`status: str`, `item_id?: int`, `item_title?: str`, `plan_id?: int|\"latest\"`, `plan_title?: str`)
  - Success `data`: `{ "item_id": int, "status": str }`
  - Errors: `validation_error`, `not_found`, `conflict`, `db_error`
- `update_plan_status`
  - Input model: `UpdatePlanStatusInput` (`status: str`, `plan_id?: int|\"latest\"`, `plan_title?: str`)
  - Success `data`: `{ "plan_id": int, "status": str }`
  - Errors: `validation_error`, `not_found`, `conflict`, `db_error`
- `save_quiz_attempt`
  - Input model: `SaveQuizAttemptInput` (`topic_id?: int`, `question: str`, `user_answer?: str`, `score?: float`, `feedback?: str`)
  - Success `data`: `{ "attempt_id": int }`
  - Errors: `validation_error`, `db_error`
- `get_wrong_questions`
  - Input model: `GetWrongQuestionsInput` (`topic_id: int`)
  - Success `data`: `{ "wrong_questions": [ ... ] }`
  - Errors: `validation_error`, `not_found`, `db_error`
- `delete_quiz_attempt`
  - Input model: `DeleteQuizAttemptInput` (`attempt_id: int`)
  - Success `data`: `{ "deleted_attempt_id": int }`
  - Errors: `validation_error`, `not_found`, `db_error`
- `get_weak_topics`
  - Input model: `GetWeakTopicsInput` (`limit?: int`)
  - Success `data`: `{ "weak_topics": [ ... ] }`
  - Errors: `validation_error`, `db_error`
- `get_due_flashcards`
  - Input model: `GetDueFlashcardsInput` (`limit?: int`)
  - Success `data`: `{ "due_flashcards": [ ... ] }`
  - Errors: `validation_error`, `db_error`
- `create_flashcard`
  - Input model: `CreateFlashcardInput` (`front: str`, `back: str`, `topic_id?: int`)
  - Success `data`: `{ "card_id": int }`
  - Errors: `validation_error`, `db_error`
- `update_flashcard_review`
  - Input model: `UpdateFlashcardReviewInput` (`card_id: int`, `ease_factor?: float`, `next_review_at?: str`)
  - Success `data`: `{ "card_id": int }`
  - Errors: `validation_error`, `db_error`
- `get_messages`
  - Input model: `GetMessagesInput` (`session_id: int`)
  - Success `data`: `{ "messages": [ ... ] }`
  - Errors: `validation_error`, `db_error`
- `save_message`
  - Input model: `SaveMessageInput` (`session_id: int`, `role: str`, `content: str`)
  - Success `data`: `{ "message_id": int }`
  - Errors: `validation_error`, `db_error`

## Quiz Flow Tools (Explicit)
Define explicit quiz tools instead of hard-coded logic:

- `quiz_pre_fetch`
  - Input: `topic_name: str`
  - Success `data`: `{ "topic_id": int, "topic_name": str, "wrong_questions": [ ... ] }`
  - Errors: `validation_error`, `db_error`
- `quiz_post_save`
  - Input: `topic_id: int`, `wrong_answers: list`, `correct_retries: list[int]`
  - Success `data`: `{ "saved_wrong": int, "deleted_correct": int }`
  - Errors: `validation_error`, `db_error`

## db_agent Error Handling Policy
- `validation_error`: ask for missing/incorrect fields using `details.fields` in follow-up.
- `not_found`: ask clarifying question if user can provide an alternative; otherwise return a brief message.
- `db_error`: return a brief apology and suggest retry.

## Migration Notes
- Update all callers that expect raw tool payloads to read `result["data"]`.
- Remove or adapt any logic that checks `\"error\" in result` to use `result[\"ok\"] == false` instead.

## Acceptance Criteria
- All DB tools return `ToolResult` with `ok` boolean and either `data` or `error`.
- Invalid inputs produce `validation_error` with helpful messages.
- db agent responses are driven by tool results, not hard-coded branches.
- Tests pass for contract validation and happy paths.

## Verification
- Run `pytest tests/test_db_tools_contracts.py`.
- Manually call a tool with invalid args and confirm:
  - Response `ok=false`, `code=validation_error`.
- Call a tool with valid args and confirm:
  - Response `ok=true` and expected data payload.
