# Lookout MCP

Lookout is an offline mock MCP server for a Tableau-inspired internal BI platform.
The primary deliverable for this take-home assignment is the technical specification in
`docs/technical-spec.md`; the Python package is a small reference implementation that proves the
shape of the design.

## Scope

Lookout is intentionally local-only. It uses SQLite for persistent state and the local filesystem
for generated renders, exports, and cache files. It does not connect to Tableau, a warehouse, an
LLM API, an auth provider, or any external write-through system.

## Local Setup

Prerequisites:

- Python 3.12
- `make`

Create a virtual environment and install dependencies:

```bash
make install
```

Create a local environment file:

```bash
cp .env.example .env
```

Create or update the local SQLite schema:

```bash
make migrate
```

Load deterministic BI seed data:

```bash
make seed
```

Run quality checks and the end-to-end smoke flow:

```bash
make lint
make typecheck
make test
make test-unit
make test-integration
make smoke
```

Start the MCP server:

```bash
make run
```

`LOOKOUT_DB_PATH` and `LOOKOUT_FS_ROOT` are required. If either value is missing, CLI commands and
MCP tools fail with a clear `CONFIG_MISSING` error instead of falling back to hidden defaults. The
example `.env.example` keeps generated files under `./var`.

## End-to-End Smoke Flow

`make smoke` exercises the complete local workflow without API keys, external services, or an MCP
client. It verifies:

- discovery: `search_content`, `list_datasources`, `get_datasource`, `get_field_values`
- workbook inspection: `list_workbooks`, `get_workbook`, `get_view`
- view data: `get_view_data` with saved filters and with `filter_overrides`
- query/export: Q1 revenue by region via `query_datasource`, then `export_query_result`
- comparison: quarter-over-quarter revenue by region via `compare_periods`
- render/export: `render_view_image` and `export_view_data`
- failure behavior: `SOURCE_UNAVAILABLE`, `CACHE_STALE`, and `FIELD_NOT_FOUND` with suggestions

All smoke-generated render and export artifacts are checked to ensure they resolve under
`LOOKOUT_FS_ROOT`.

## Testing Strategy

The Python suite is split by pytest markers:

- `make test`: run the full suite with coverage reporting for `lookout_mcp`.
- `make test-unit`: run fast unit tests for ID validation, cursor encode/decode, filter/type
  validation, query builder behavior, error envelopes, fuzzy ambiguity, and token-safety helpers.
- `make test-integration`: run temporary SQLite/filesystem integration tests for migration,
  seeding, list/get tools, queries, comparisons, renders, exports, edge cases, and golden contract
  outputs.

See `docs/testing.md` for the manual QA checklist and the snapshot/golden coverage.

## Optional Lookout Explorer UI

Lookout Explorer is a secondary, dev-only browser UI for human evaluators. It is not required for
MCP usage, and the MCP tools plus `docs/technical-spec.md` remain the primary deliverable.

The UI is intentionally small: it reuses the same Python domain/API services as the MCP tools
through a local HTTP adapter and does not add auth, external services, or a separate business logic
path.

Install UI dependencies:

```bash
make ui-install
```

Seed local data if you have not already:

```bash
make seed
```

Start the dev-only adapter in one terminal:

```bash
make ui-api
```

Start the Vite UI in another terminal:

```bash
make ui-dev
```

Open the Vite URL printed by `make ui-dev`, usually `http://127.0.0.1:5173`. If the adapter is
running somewhere other than `http://127.0.0.1:8765`, set `VITE_LOOKOUT_API_BASE` when starting the
UI.

Run the optional UI smoke/component tests:

```bash
make ui-test
```

## Current Tool Surface

The MCP server exposes `health_check` plus the core Lookout BI workflow tools:

- Discovery: `search_content`, `list_datasources`, `get_datasource`, `get_field_values`
- Workbook and view inspection: `list_workbooks`, `get_workbook`, `list_views`, `get_view`
- Analysis: `get_view_data`, `query_datasource`, `compare_periods`
- Artifacts: `render_view_image`, `render_workbook_image`, `export_view_data`,
  `export_query_result`

All tool inputs are validated with Pydantic and all failures return:

```json
{"error": {"code": "...", "message": "...", "details": {}}}
```

## Current Data Model

The reference implementation includes SQLite migrations and deterministic seed data for the core
Lookout domain entities:

- `datasources`
- `datasource_fields`
- `workbooks`
- `views`
- `query_results`
- `exports`
- `renders`

Run `python -m lookout_mcp.db migrate` for a clean schema and `python -m lookout_mcp.db seed` to
reload deterministic BI scenarios. The seed covers retail sales, store performance, sales pipeline,
marketing spend, customer support, and inventory supply chain, including available, stale-cache, and
source-offline datasource states.

## Repository Layout

- `docs/technical-spec.md`: primary assignment artifact.
- `docs/engineering-decisions.md`: rationale behind architecture and implementation choices.
- `src/lookout_mcp/`: Python package for the reference MCP server.
- `ui/`: optional Vite/React Lookout Explorer evaluator demo.
- `migrations/`: ordered SQLite migration files.
- `scripts/`: local utility scripts.
- `tests/`: pytest suite.
- `data/`: optional deterministic seed data inputs in later phases.
- `var/`: local generated files, ignored except for directory placeholders.

## Development Commands

- `make lint`: run Ruff checks.
- `make format`: format Python files with Ruff.
- `make test`: run pytest with coverage reporting.
- `make test-unit`: run tests marked `unit`.
- `make test-integration`: run tests marked `integration`.
- `make typecheck`: run mypy.
- `make migrate`: apply pending SQLite migrations.
- `make seed`: migrate and load deterministic seed data.
- `make run`: start the MCP server.
- `make smoke`: run the end-to-end local workflow smoke check without an MCP client.
- `make ui-api`: start the optional dev-only HTTP adapter for Lookout Explorer.
- `make ui-dev`: start the optional Vite UI.
- `make ui-test`: run optional UI component/smoke tests.
