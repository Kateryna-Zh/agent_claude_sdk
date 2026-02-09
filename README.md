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
