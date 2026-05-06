# Engineering Decisions

## Stack Choice

Lookout uses Python 3.12, the official MCP Python SDK/FastMCP, SQLite, Pydantic, pytest, Ruff,
and mypy. This is intentionally boring: the evaluator can run it locally, the behavior is easy to
inspect, and the implementation focuses on MCP contract quality instead of infrastructure.

The optional Lookout Explorer UI uses Vite and React only as evaluator support. It is secondary to
the MCP tool surface and calls the same Python backend functions through a small local HTTP
adapter.

## SQLite and Schema

SQLite is the durable state store for metadata, run history, render metadata, and export metadata.
The schema uses explicit tables for datasources, fields, workbooks, views, query results, exports,
and renders. JSON columns are used for tags, query specs, warnings, and visual configuration where
normalizing the mock data would add complexity without improving the agent contract.

Migrations are ordered SQL files under `migrations/` and are tracked in `_lookout_migrations`.
Seed data is deterministic: stable natural keys produce stable IDs, and tests can regenerate the
same BI scenarios without network access or API keys.

## Tool Surface Design

The tool names are focused around agent workflows:

- discovery: `search_content`, `list_datasources`, `get_field_values`
- inspection: `get_datasource`, `list_workbooks`, `get_workbook`, `list_views`, `get_view`
- analysis: `get_view_data`, `query_datasource`, `compare_periods`
- artifacts: `render_view_image`, `render_workbook_image`, `export_view_data`,
  `export_query_result`

MCP transport registration lives in `server.py`. Tool descriptions and Pydantic input/output
models live in `tools/registry.py`. Callable backend behavior lives in `tools/api.py`, with shared
pagination, fuzzy matching, warnings, cursor, and token-limit helpers in `tools/workflow.py`.

## Token and Cost Strategy

Lookout never calls an LLM. It assumes the external MCP client is an agent and keeps responses
bounded so the agent can reason over them cheaply.

Metadata list tools return compact pages, default to `page_size=10`, and reject `page_size > 25`.
Query tools return inline previews only, default to `preview_limit=100`, and reject
`preview_limit > 1000`. Large result access goes through export tools that write local artifacts
under `LOOKOUT_FS_ROOT` and return metadata instead of row dumps.

Logs follow the same discipline: structured tool-call logs include tool name, duration, status,
row counts, and error code, but never include preview rows or exported row data.

## Failure Modes

All model-visible failures use the standard envelope:

```json
{"error": {"code": "...", "message": "...", "details": {}}}
```

Validation errors include Pydantic details. Lookup and field errors include candidate suggestions
where useful. Cursor, page-size, preview-limit, source-offline, stale-cache, export, render, and
configuration failures are explicit and actionable for an AI agent.

Raw SQL is not enabled in the reference implementation. Structured query specs are required; SQL
payloads return `UNSUPPORTED_SQL` with a recovery hint. Artifact paths are generated from stable
Lookout IDs and resolved under `LOOKOUT_FS_ROOT`; path escapes are rejected.

## Testing Strategy

Unit tests cover configuration loading, error envelope shape, ID validation, cursor
encode/decode, token limits, fuzzy ambiguity, warning helpers, filter validation, and query
builder behavior.

Integration tests use temporary SQLite databases and filesystem roots. They cover migration and
seed behavior, tool contracts, standard errors, stale/source-offline states, render/export
artifact creation, safe artifact paths, structured observability logs, and golden response shapes.
`make smoke` runs the end-to-end local workflow against the configured `.env`.

## Tradeoffs

The technical specification remains the primary artifact; the implementation proves it without
becoming a complete BI product. SQLite and filesystem artifacts are less realistic than a
warehouse plus object storage, but they are easier to inspect and safer for an offline take-home.
Auth, multi-tenancy, realtime updates, write-through integrations, and real Tableau connectivity
are intentionally out of scope.
