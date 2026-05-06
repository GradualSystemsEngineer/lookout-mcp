# Lookout MCP

Lookout is an offline mock MCP server for a Tableau-inspired internal BI platform. AI agents use
its local MCP tools to discover BI content, inspect datasources and dashboards, run bounded
analysis queries, compare periods, render SVG chart artifacts, and export larger result sets.
View data previews include compact summary statistics, and view renders support validated
filter overrides for one-off filtered artifacts.

The primary take-home deliverable is [docs/technical-spec.md](/Users/aaronmcdaniel/Code/lookout-mcp/docs/technical-spec.md).
The Python package is a reference implementation that proves the specification, stays fully local,
and requires no Tableau server, warehouse, API keys, auth provider, or LLM calls.

## Assignment Scope

The assignment asks for a technical specification for a Tableau-like MCP integration, plus enough
reference implementation to make the design concrete and testable. In this repo:

- [docs/technical-spec.md](/Users/aaronmcdaniel/Code/lookout-mcp/docs/technical-spec.md) is the
  source of truth for the model-visible contract, data model, workflows, errors, and tradeoffs.
- [docs/engineering-decisions.md](/Users/aaronmcdaniel/Code/lookout-mcp/docs/engineering-decisions.md)
  captures durable rationale.
- [docs/testing.md](/Users/aaronmcdaniel/Code/lookout-mcp/docs/testing.md) captures automated and
  manual verification.
- [src/lookout_mcp](/Users/aaronmcdaniel/Code/lookout-mcp/src/lookout_mcp) contains the local
  Python MCP server and backend tool implementation.
- [ui](/Users/aaronmcdaniel/Code/lookout-mcp/ui) contains an optional evaluator-only browser UI.

## Clean Checkout Setup

Prerequisites:

- Python 3.12
- `make`
- Optional UI only: Node.js/npm

From a clean checkout:

```bash
make install
cp .env.example .env
make migrate
make seed
```

The checked-in `.env.example` sets:

```bash
LOOKOUT_DB_PATH=./lookout.sqlite3
LOOKOUT_FS_ROOT=./var
LOOKOUT_LOG_LEVEL=INFO
```

`LOOKOUT_DB_PATH` and `LOOKOUT_FS_ROOT` are required. If either is missing, CLI entrypoints and MCP
tools fail deterministically with `CONFIG_MISSING`.

## Required Commands

Install dependencies:

```bash
make install
```

Create or update the SQLite schema:

```bash
make migrate
```

Load deterministic seed data and seed artifacts:

```bash
make seed
```

Run tests:

```bash
make test
```

Start the MCP server:

```bash
make run
```

Run the end-to-end smoke test:

```bash
make smoke
```

Optional evaluator UI:

```bash
make ui-install
make ui-api
make ui-dev
make ui-test
```

The UI is not required for MCP usage or assignment evaluation; it is a small local browser aid for
human inspection.

## Architecture Overview

Lookout is intentionally boring and local:

- `server.py` registers the FastMCP server and model-visible tool descriptions.
- `tools/registry.py` defines exact tool descriptions, Pydantic input/output models, common errors,
  notes, and examples.
- `tools/api.py` contains callable backend tool behavior and structured logging.
- `tools/workflow.py` contains pagination, cursor, fuzzy matching, warnings, and token-limit
  helpers.
- `db.py` applies migrations and loads deterministic seed data.
- `seed.py` builds deterministic BI records and initial render/export files.
- SQLite stores metadata, saved query/run metadata, render metadata, and export metadata.
- The local filesystem under `LOOKOUT_FS_ROOT` stores generated SVG, CSV, and JSON artifacts.

## Tool Surface Summary

The MCP server exposes `health_check` plus the core BI workflow tools:

- Discovery: `search_content`, `list_datasources`, `get_datasource`, `get_field_values`
- Workbook and view inspection: `list_workbooks`, `get_workbook`, `list_views`, `get_view`
- Analysis: `get_view_data`, `query_datasource`, `compare_periods`
- Artifacts: `render_view_image`, `render_workbook_image`, `export_view_data`,
  `export_query_result`

Every backend tool returns JSON-serializable data. Expected failures use:

```json
{"error": {"code": "FIELD_NOT_FOUND", "message": "Field was not found.", "details": {"field": "revenu"}}}
```

## Data Model Summary

SQLite tables:

- `datasources`: BI datasource metadata, simulated source status, tags, row counts, defaults
- `datasource_fields`: field names, labels, data types, semantic roles, aggregations, filter/sort
  flags, allowed operators
- `workbooks`: workbook metadata, project, owner, tags, defaults
- `views`: workbook views, chart type/config, saved structured query spec, visual config
- `query_results`: deterministic query run metadata and bounded previews
- `exports`: CSV/JSON artifact metadata
- `renders`: SVG render artifact metadata

Stable IDs use typed prefixes such as `ds_<12 hex>`, `fld_<12 hex>`, `wb_<12 hex>`,
`view_<12 hex>`, `run_<12 hex>`, `exp_<12 hex>`, and `rnd_<12 hex>`.

## Token and Cost Strategy

Lookout never calls an LLM, so there is no internal model cost. It is still designed for cheap
agent usage:

- Metadata list tools default to `page_size=10` and reject values above `25`.
- Query preview tools default to `preview_limit=100` and reject values above `1000`.
- List responses return compact items, not verbose records.
- Query tools return bounded previews and require exports for larger result access.
- Export and render tools return local artifact metadata rather than inline file contents.
- `render_view_image` accepts validated `filter_overrides` for filtered image artifacts without
  mutating the saved view.
- Structured logs omit preview rows and exported data.

## Errors, Retries, and Rate Limits

Failure modes are deterministic and model-visible. Validation, lookup, cursor, filter, sort,
configuration, source-status, render, export, and token-limit failures are converted to the
standard error envelope.

Retry guidance is encoded by error type:

- Retry after changing input: `INVALID_INPUT`, `INVALID_FILTER`, `INVALID_SORT`,
  `FIELD_NOT_FOUND`, `PAGE_SIZE_TOO_LARGE`, `LIMIT_EXCEEDED`, `INVALID_CURSOR`
- Retry after choosing a candidate ID: `AMBIGUOUS_MATCH`
- Do not retry unchanged: `SOURCE_UNAVAILABLE`, `UNSUPPORTED_SQL`, `CONFIG_MISSING`
- Retry later or reduce concurrency: `RATE_LIMITED`
- Inspect local filesystem/configuration: `EXPORT_FAILED`, `RENDER_FAILED`

Expensive render/export operations use an in-process concurrency guard and return `RATE_LIMITED`
when the local limit is exceeded.

## Testing Approach

Automated verification is local and deterministic:

```bash
make lint
make typecheck
make test
make smoke
```

Unit tests cover configuration, error envelopes, ID validation, cursor encode/decode, fuzzy
matching, warning helpers, filter validation, query-builder behavior, and token limits.
Integration tests use temporary SQLite databases and filesystem roots to cover migration, seeding,
tool contracts, stale/source-offline states, render/export artifact creation, safe artifact paths,
observability logs, and golden response shapes. `make smoke` exercises the complete evaluator
workflow against `.env`.

## Known Limitations

- No real Tableau or warehouse integration.
- No auth, users, permissions, or multi-tenancy.
- No realtime refresh or external write-through.
- Query execution is deterministic synthetic behavior, not a SQL engine over warehouse rows.
- Raw SQL mode is intentionally rejected with `UNSUPPORTED_SQL`.
- Render output is deterministic SVG, not pixel-perfect BI visualization rendering.
- The optional UI is dev-only and is not part of the MCP contract.

## Future Improvements

- Add read-only SQL compatibility with static analysis and row/timeout limits.
- Add richer permission modeling if auth becomes in scope.
- Add a fuller artifact lifecycle, including cache expiry and cleanup policies.
- Add more chart types and image formats.
- Add deeper MCP client examples and transcript-based evaluator scenarios.
- Add realistic warehouse adapters behind the same structured query contract.

## Final Checklist

- Fresh checkout works with `make install`, `.env.example`, `make migrate`, and `make seed`.
- DB migration works.
- Seed works and creates deterministic local artifacts.
- All tests pass with `make test`.
- MCP server starts with `make run`.
- Core workflows pass through `make smoke`.
- Render/export files are created under `LOOKOUT_FS_ROOT`.
- Failure modes are deterministic and use the standard envelope.
- No external services or API keys are required.
- Spec and implementation agree.

## Follow-up Interview Notes

Python + SQLite keeps the submission easy to run, inspect, and test while still proving the MCP
contract. No frontend is required because the evaluated surface is the agent-facing MCP tool
contract; the optional UI is only a human inspection aid. Lookout does not call an LLM because the
LLM is the external MCP client, and embedding model calls would add cost, secrets, nondeterminism,
and scope creep.

Token usage is controlled with compact list responses, hard page/preview caps, exports for large
results, and log redaction. Query safety comes from structured query specs, field/type/operator
validation, source-status checks, inline row limits, disabled raw SQL, safe artifact paths, and
deterministic errors. Deferred work is limited to real BI integrations, auth, SQL compatibility,
realtime refresh, production artifact storage, and richer rendering.
