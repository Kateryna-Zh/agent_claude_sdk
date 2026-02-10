# agent_claude_sdk

## MCP Checks (Best Practices)

Purpose: Verify MCP server connectivity and DB read/write without relying on agent logic.

Scope: Local-only checks. The CLI writes test rows unless `--cleanup` is used.

Prerequisites:
- Local Postgres running and schema applied from `db/init.sql`.
- MCP server configured via `.env` (see below).
- `MCP_ALLOW_WRITE_OPS=true` for write tests.

Required env keys:
- `DB_BACKEND=mcp`
- `MCP_SERVER_COMMAND` / `MCP_SERVER_ARGS`
- `MCP_DATABASE_URL`
- `MCP_ALLOW_WRITE_OPS`
- `MCP_SUPPORTS_PARAMS` (for `pg-mcp-server`, set `false`)

Commands:
- CLI check (read/write):
```bash
python3 -m app.cli.mcp_check --message "hello from mcp test"
```
- CLI check with cleanup:
```bash
python3 -m app.cli.mcp_check --message "hello from mcp test" --cleanup
```
- MCP health endpoint:
```bash
curl http://localhost:8000/health/mcp
```

Success criteria:
- CLI exit code `0`
- Output includes `message_present: True`
- `/health/mcp` returns `{ "ok": true, ... }`

Troubleshooting:
- Use `--debug` to print raw MCP payloads and tool schema:
```bash
python3 -m app.cli.mcp_check --message "hello" --debug
```
- If you see parameter errors, confirm:
  - `MCP_QUERY_KEY=sql`
  - `MCP_SUPPORTS_PARAMS=false`
  - `MCP_ALLOW_WRITE_OPS=true`

Data hygiene:
- Use `--cleanup` if you do not want test rows persisted.
- If needed, delete test rows manually from `messages` and `sessions`.

Security notes:
- Keep MCP local-only and never expose it publicly.
- Pin MCP server version in `.env`/`.env.example` (e.g., `pg-mcp-server@x.y.z`).
- Do not commit `.env` with credentials.

Versioning:
- Update this section whenever MCP server version or tool schema changes.

## PostgreSQL Access (MCP + psycopg2 fallback)

Overview:
- Default DB backend is MCP (`DB_BACKEND=mcp`).
- MCP server is started/stopped with FastAPI lifespan.
- If MCP fails, the app logs a warning and falls back to psycopg2 (configurable).

Key modules:
- MCP lifecycle: `app/mcp/manager.py`
- MCP client wrapper: `app/mcp/client.py`
- MCP repository: `app/db/mcp_repository.py`
- psycopg2 repository: `app/db/repository.py`
- backend selection: `app/db/repository_factory.py`
- graph nodes: `app/tools/db_read.py`, `app/tools/db_write.py`

Config (MCP):
- `MCP_SERVER_COMMAND` / `MCP_SERVER_ARGS` (pin version in args)
- `MCP_DATABASE_URL`
- `MCP_ALLOW_WRITE_OPS=true` (required for write tests)
- `MCP_TOOL_NAME=query`
- `MCP_QUERY_KEY=sql`
- `MCP_SUPPORTS_PARAMS=false` (pg-mcp-server uses only `sql`)
- `MCP_FALLBACK_TO_PSYCOPG2=true`

Config (psycopg2 fallback):
- `PG_HOST`, `PG_PORT`, `PG_DATABASE`, `PG_USER`, `PG_PASSWORD`
- `PG_POOL_MIN`, `PG_POOL_MAX`

Runtime behavior:
- MCP is the primary path for reads/writes.
- If MCP is unavailable or returns errors, fallback logs:
  - `MCP DB read failed, falling back to psycopg2`
  - `MCP DB write failed, falling back to psycopg2`

Notes:
- pg-mcp-server does not accept query params; when `MCP_SUPPORTS_PARAMS=false`, SQL is inlined safely for local use.
- Keep MCP local-only and never expose it publicly.

## Agents, Routing, and Orchestration (LangGraph + LangChain)

This project uses LangGraph for orchestration and LangChain for model calls and MCP client sessions. There is no LCEL pipe (`|`) usage; agents call the model directly with `llm.invoke(...)` and parse outputs with Pydantic.

### Orchestration Flow

Entry point:
- `app/graph/builder.py` builds the LangGraph state machine.

Routing logic:
- `app/agents/router_agent.py` classifies intent and sets routing flags.
- `app/graph/routing.py` maps intent/flags to the next node.

Execution path (simplified):
- Router -> optional context tools (`retrieve_context`, `web_search`) -> specialist agent -> `format_response`
- DB reads/writes for plans and progress are handled by `db_agent` (tool-calling executor).

### Agents and Responsibilities

Router agent:
- File: `app/agents/router_agent.py`
- Uses the router prompt (`app/prompts/router.py`) to classify intents like PLAN, REVIEW, LOG_PROGRESS.
- Sets `needs_db` and `sub_intent` so the graph knows which node to run next.
- Includes follow-up handling for review flows (title-only replies after a list-items request).

Planner agent:
- File: `app/agents/planner_agent.py`
- Generates a plan draft with structured JSON validated by `app/schemas/planner.py`.
- Returns a Markdown summary to the user and a structured `plan_draft` for saving.

DB agent (tool-calling executor):
- File: `app/agents/db_agent.py`
- Executes DB actions using native Ollama tool calling (with a fallback to `db_plan`).
- Tools are defined in `app/tools/db_tools.py` and cover list/create/update operations.
- Formats responses and handles duplicate titles using `created_at` for disambiguation.
- Progress updates (`update_item_status`) are plan-scoped. If no plan is specified, the tool-calling model may guess a plan ID; if the item is not in that plan, the update returns `item_not_found`.

Tutor, Quiz, Research agents:
- Files: `app/agents/tutor_agent.py`, `app/agents/quiz_agent.py`, `app/agents/research_agent.py`
- Tutor uses RAG context for explanations.
- Quiz and Research flows are routed by the router intent.

### Parsing and Schema Validation

Parsing utilities:
- File: `app/utils/llm_parse.py`
- LLM outputs are parsed and validated with Pydantic schemas.
- Includes sanitization and JSON extraction for robustness.

Schemas:
- Router: `app/schemas/router.py`
- Planner: `app/schemas/planner.py`
- DB plans are validated via `DBPlanOutput` (router schema module).

### MCP Integration in Agents

MCP client usage:
- `db_agent` uses repository backends (MCP or psycopg2) to execute tools.
- MCP session parameters come from `.env` and `app/config.py`.

DB execution flow:
- Planner creates a draft.
- On confirmation, DB agent writes the plan (`create_plan` + `add_plan_item`) and formats the response.
