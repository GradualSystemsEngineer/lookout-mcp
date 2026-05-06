# Lookout MCP Technical Specification

## Overview

Lookout is a mock MCP server for a Tableau-inspired internal business intelligence platform. AI
agents use Lookout through model-visible MCP tools to discover analytical content, inspect
datasources, run bounded queries, compare periods, render charts, and export data.

The system is designed for an offline engineering take-home assignment. SQLite stores durable
application state, and generated files are written under a configured local filesystem root.
Lookout itself never calls an LLM; the LLM is the external agent invoking MCP tools.

## Requirements interpretation

- The primary evaluated artifact is this technical specification.
- The reference implementation should prove the design without becoming a full BI platform.
- The server runs locally and deterministically.
- SQLite is the source of persistent metadata, run history, render metadata, and export metadata.
- The filesystem stores generated render, export, and cache artifacts.
- No Tableau server, data warehouse, auth, multi-tenancy, realtime updates, or external
  write-through integration is in scope.

## Data model and schema

SQLite is the durable state store. Schema changes are applied from ordered SQL files in
`migrations/` by `python -m lookout_mcp.db migrate`. Applied versions are tracked in
`_lookout_migrations`.

The core domain tables are:

- `datasources`: datasource metadata, simulated status, row counts, tags, and default filters.
  Status is constrained to `available`, `cache_stale`, or `source_offline`.
- `datasource_fields`: fields owned by a datasource. Each field stores name, label, data type,
  semantic role, description, optional default aggregation, filter/sort flags, allowed operators,
  and ordinal position.
- `workbooks`: workbook metadata, project/owner, tags, and default filters.
- `views`: workbook views linked to one workbook and one datasource. Views store chart type,
  chart config, query spec, default filters, visual config, and workbook position.
- `query_results`: deterministic run metadata linked to a datasource and optionally a view. Query
  specs, preview rows, warnings, and status are JSON-backed or constrained fields.
- `exports`: export artifact metadata linked to a query result or view, with format, row count,
  status, metadata, and a path relative to `LOOKOUT_FS_ROOT`.
- `renders`: render artifact metadata linked to a workbook or view, with dimensions, status,
  warnings, visual config, and a path relative to `LOOKOUT_FS_ROOT`.

Foreign keys are enabled for Lookout connections. The schema uses `CHECK` constraints for ID
prefixes, enum-like statuses, chart types, data types, semantic roles, artifact statuses, positive
counts/dimensions, and JSON validity. JSON columns are used for tags, default filters, allowed
operators, chart config, query specs, preview rows, warnings, metadata, and visual config where
normalization would add noise without improving the mock contract.

Indexes cover common discovery and filtering paths:

- datasource status/theme and label
- datasource fields by datasource, filterability, sortability, data type, and semantic role
- workbooks by project/title
- views by workbook position, datasource/chart type, and title
- query results by datasource/execution time and view
- exports/renders by their linked query result, view, or workbook

## ID formats

IDs are stable string identifiers generated from deterministic seed natural keys. The Python
validation helpers and SQLite `CHECK` constraints enforce:

- Datasource: `ds_<12 lowercase hex>`
- Field: `fld_<12 lowercase hex>`
- Workbook: `wb_<12 lowercase hex>`
- View: `view_<12 lowercase hex>`
- Query result: `run_<12 lowercase hex>`
- Export: `exp_<12 lowercase hex>`
- Render: `rnd_<12 lowercase hex>`

## Tool surface

The current MCP tool surface exposes:

- `health_check`: returns local service status, configured SQLite path, filesystem root, and log
  level.
- `search_content`: searches datasources, workbooks, views, and fields.
- `list_datasources`: lists compact datasource metadata.
- `get_datasource`: returns one datasource and optional field metadata.
- `get_field_values`: returns representative values for one field.
- `list_workbooks`: lists compact workbook metadata.
- `get_workbook`: returns one workbook and optional compact views.
- `list_views`: lists compact view metadata.
- `get_view`: returns one view, chart config, and optional saved query spec.
- `get_view_data`: runs or reuses a saved view query, optionally adds filter overrides, and returns
  a bounded preview.
- `query_datasource`: runs a validated structured query and returns a bounded preview plus
  `query_result_id`.
- `compare_periods`: compares a measure across two periods with optional dimensions.
- `render_view_image`: writes a deterministic SVG render for one view under `LOOKOUT_FS_ROOT`.
- `render_workbook_image`: writes a deterministic SVG dashboard render under `LOOKOUT_FS_ROOT`.
- `export_view_data`: exports the rows behind a view under `LOOKOUT_FS_ROOT`.
- `export_query_result`: exports a prior query result under `LOOKOUT_FS_ROOT`.

## Workflow mapping

Planned workflows map to tools as follows:

- Discovery: `search_content`, `list_datasources`, `get_datasource`, `get_field_values`
- Workbook inspection: `list_workbooks`, `get_workbook`, `list_views`, `get_view`
- View analysis: `get_view`, `get_view_data` with saved filters or overrides,
  `render_view_image`, `export_view_data`
- Ad hoc analysis: `query_datasource`, `compare_periods`, `export_query_result`
- Dashboard rendering: `render_workbook_image`
- Failure recovery: standard error envelopes plus warnings for degraded but readable states

## Tool examples

Examples are abbreviated but preserve the request/response shape returned by MCP tools.

### `search_content`

Request:

```json
{"query": "revenue", "content_types": ["workbook", "view"], "page_size": 2}
```

Response:

```json
{
  "items": [{"id": "view_...", "kind": "view", "label": "Q1 Revenue by Region", "score": 300}],
  "row_count": 8,
  "returned_row_count": 2,
  "truncated": true,
  "next_cursor": "eyJ...",
  "warnings": []
}
```

### `list_datasources`

Request:

```json
{"status": "cache_stale", "page_size": 10}
```

Response:

```json
{
  "items": [{"id": "ds_...", "label": "Store Performance", "status": "cache_stale", "theme": "store performance", "row_count": 37200, "tags": ["store performance", "cache_stale", "seeded"]}],
  "row_count": 2,
  "returned_row_count": 2,
  "truncated": false,
  "next_cursor": null,
  "warnings": [{"code": "CACHE_STALE", "message": "Datasource cache is stale; results may lag the source system.", "details": {"status": "cache_stale"}}]
}
```

### `get_datasource`

Request:

```json
{"datasource": "Retail Sales", "include_fields": true}
```

Response:

```json
{
  "datasource": {"id": "ds_...", "label": "Retail Sales", "status": "available", "row_count": 482400},
  "fields": [{"id": "fld_...", "name": "revenue", "data_type": "decimal", "semantic_role": "measure", "default_aggregation": "sum"}],
  "warnings": []
}
```

### `get_field_values`

Request:

```json
{"datasource": "Retail Sales", "field": "region", "page_size": 4}
```

Response:

```json
{"items": [{"id": "fld_...:1", "value": "Northeast"}], "row_count": 4, "returned_row_count": 4, "truncated": false, "next_cursor": null, "warnings": []}
```

### `list_workbooks`

Request:

```json
{"datasource": "Retail Sales", "page_size": 10}
```

Response:

```json
{"items": [{"id": "wb_...", "title": "Retail Sales Executive Dashboard", "project": "Executive Dashboards", "owner": "lookout-demo", "tags": ["retail sales", "dashboard", "executive"]}], "row_count": 6, "returned_row_count": 6, "truncated": false, "next_cursor": null, "warnings": []}
```

### `get_workbook`

Request:

```json
{"workbook": "Retail Sales Executive Dashboard", "include_views": true}
```

Response:

```json
{"workbook": {"id": "wb_...", "title": "Retail Sales Executive Dashboard", "project": "Executive Dashboards"}, "views": [{"id": "view_...", "title": "Dashboard: Q1 Revenue by Region", "chart_type": "bar"}], "warnings": []}
```

### `list_views`

Request:

```json
{"datasource": "Retail Sales", "chart_type": "bar"}
```

Response:

```json
{"items": [{"id": "view_...", "title": "Q1 Revenue by Region", "workbook_id": "wb_...", "datasource_id": "ds_...", "chart_type": "bar", "position": 1}], "row_count": 2, "returned_row_count": 2, "truncated": false, "next_cursor": null, "warnings": []}
```

### `get_view`

Request:

```json
{"view": "Q1 Revenue by Region", "include_query_spec": true}
```

Response:

```json
{"view": {"id": "view_...", "title": "Q1 Revenue by Region", "chart_type": "bar", "query_spec": {"operation": "aggregate", "group_by": ["region"], "metrics": [{"field": "revenue", "aggregation": "sum"}]}}, "warnings": []}
```

### `get_view_data`

Request:

```json
{"view": "Q1 Revenue by Region", "preview_limit": 2}
```

Response:

```json
{"query_result_id": "run_...", "rows": [{"region": "Northeast", "revenue": 100000}], "row_count": 10, "returned_row_count": 2, "truncated": true, "next_cursor": null, "warnings": [{"code": "RESULT_TRUNCATED", "message": "Inline rows were truncated to the preview limit.", "details": {"row_count": 10, "returned_row_count": 2}}]}
```

Request with a filter override:

```json
{"view": "Q1 Revenue by Region", "filter_overrides": {"region": "Northeast"}, "preview_limit": 2}
```

Response:

```json
{"query_result_id": "run_...", "rows": [{"region": "Northeast", "sum_revenue": 443210}], "row_count": 4, "returned_row_count": 2, "truncated": true, "next_cursor": null, "warnings": [{"code": "RESULT_TRUNCATED", "message": "Inline rows were truncated to the preview limit.", "details": {"row_count": 4, "returned_row_count": 2}}]}
```

### `query_datasource`

Request:

```json
{"datasource": "Retail Sales", "query_spec": {"group_by": ["region"], "metrics": [{"field": "revenue", "aggregation": "sum"}], "order_by": [{"field": "revenue", "direction": "desc"}]}, "preview_limit": 2}
```

Response:

```json
{"query_result_id": "run_...", "rows": [{"region": "West", "sum_revenue": 443210}], "row_count": 4, "returned_row_count": 2, "truncated": true, "next_cursor": null, "warnings": [{"code": "RESULT_TRUNCATED", "message": "Inline rows were truncated to the preview limit.", "details": {"row_count": 4, "returned_row_count": 2}}]}
```

### `compare_periods`

Request:

```json
{"datasource": "Retail Sales", "metric": "revenue", "period_field": "order_date", "current_period": {"quarter": "Q1"}, "comparison_period": {"quarter": "Q4"}, "dimensions": ["region"], "preview_limit": 2}
```

Response:

```json
{"comparison": {"metric": "revenue", "period_field": "order_date", "current_total": 900000, "comparison_total": 840000, "delta": 60000, "pct_delta": 0.0714}, "rows": [{"region": "Northeast", "current_value": 240000, "comparison_value": 210000, "delta": 30000, "pct_delta": 0.1429}], "row_count": 4, "returned_row_count": 2, "truncated": true, "next_cursor": null, "warnings": [{"code": "RESULT_TRUNCATED", "message": "Inline rows were truncated to the preview limit.", "details": {"row_count": 4, "returned_row_count": 2}}]}
```

### `render_view_image`

Request:

```json
{"view": "Q1 Revenue by Region", "width": 1200, "height": 800}
```

Response:

```json
{"render_id": "rnd_...", "artifact_path": "renders/rnd_....svg", "width": 1200, "height": 800, "status": "ready", "warnings": []}
```

### `render_workbook_image`

Request:

```json
{"workbook": "Retail Sales Executive Dashboard", "width": 1440, "height": 960}
```

Response:

```json
{"render_id": "rnd_...", "artifact_path": "renders/rnd_....svg", "width": 1440, "height": 960, "status": "ready", "warnings": []}
```

### `export_view_data`

Request:

```json
{"view": "Q1 Revenue by Region", "format": "csv"}
```

Response:

```json
{"export_id": "exp_...", "artifact_path": "exports/exp_....csv", "format": "csv", "row_count": 10, "status": "ready", "warnings": []}
```

### `export_query_result`

Request:

```json
{"query_result_id": "run_...", "format": "json"}
```

Response:

```json
{"export_id": "exp_...", "artifact_path": "exports/exp_....json", "format": "json", "row_count": 4, "status": "ready", "warnings": []}
```

Example error:

```json
{"error": {"code": "SOURCE_UNAVAILABLE", "message": "Datasource source is offline; ad hoc queries are unavailable.", "details": {"datasource_id": "ds_...", "status": "source_offline"}}}
```

Example invalid field error:

```json
{"error": {"code": "FIELD_NOT_FOUND", "message": "Field is not valid for this datasource.", "details": {"field": "revenu", "suggestions": [{"id": "fld_...", "name": "revenue", "label": "Revenue"}]}}}
```

## End-to-end local workflow

A clean checkout can validate Lookout with this command sequence:

```bash
make install
cp .env.example .env
make migrate
make seed
make lint
make typecheck
make test
make smoke
make run
```

`LOOKOUT_DB_PATH` and `LOOKOUT_FS_ROOT` are required configuration. If either is absent or blank,
CLI entrypoints fail with `CONFIG_MISSING`, and MCP tools return the standard error envelope with
`error.code=CONFIG_MISSING`. The checked-in `.env.example` points at `./lookout.sqlite3` and
`./var`, so all generated files are local and inspectable.

The smoke script is the executable end-to-end example. It exercises:

- discovery through `search_content`, `list_datasources`, `get_datasource`, and
  `get_field_values`
- workbook inspection through `list_workbooks`, `get_workbook`, and `get_view`
- filtered view data through `get_view_data` with saved filters and with `filter_overrides`
- Q1 revenue by region through `query_datasource`, then `export_query_result`
- quarter-over-quarter revenue through `compare_periods`
- artifact creation through `render_view_image` and `export_view_data`
- failure behavior for `SOURCE_UNAVAILABLE`, stale-cache warnings, and invalid fields with
  suggestions

Smoke validates every generated artifact path by resolving it relative to `LOOKOUT_FS_ROOT` and
rejecting any path that escapes the configured root.

## Pagination and filter semantics

List and query tools are bounded by default. Metadata list tools default to small pages and return
compact items. Query tools return previews inline and require exports for large result sets. Cursor
pagination uses opaque cursors that encode version, sort key, last seen ID, and a filter hash.

Filters are validated against datasource field metadata, field data types, allowed operators,
filterability flags, and value shape. Date and datetime filters must use ISO-formatted strings,
numeric filters must use JSON numbers, boolean filters must use JSON booleans, `between` filters
must provide exactly two values, and string-only operators such as `contains` are rejected for
non-string fields. Sort clauses are validated against sortable fields or metric aliases.

## AI agent and token strategy

Lookout is agent-facing but not agentic: it never calls an LLM, never requires API keys, and never
delegates reasoning to an external model. The LLM is the MCP client. The server therefore optimizes
for model-visible tool descriptions, compact responses, deterministic ambiguity handling, and
recoverable errors.

All MCP tools are described in a local tool registry. Each registry entry records the tool name,
exact model-visible description, input model, output model, common error codes, documentation
notes, and examples. The registry covers:

- `search_content`
- `list_datasources`
- `get_datasource`
- `get_field_values`
- `list_workbooks`
- `get_workbook`
- `list_views`
- `get_view`
- `get_view_data`
- `query_datasource`
- `compare_periods`
- `render_view_image`
- `render_workbook_image`
- `export_view_data`
- `export_query_result`

Token controls are part of the public workflow contract:

- Metadata list tools default to `page_size=10` and reject page sizes above `25`.
- Query and view-data tools default to `preview_limit=100` rows and reject inline previews above
  `1,000` rows.
- List outputs return compact item shapes and include `row_count`, `returned_row_count`,
  `truncated`, and `next_cursor`.
- Query outputs return bounded preview rows and include `row_count`, `returned_row_count`,
  `truncated`, `next_cursor`, and warnings.
- Large result access goes through `export_view_data` or `export_query_result`, which write files
  under `LOOKOUT_FS_ROOT` and return artifact metadata rather than row dumps.

## Observability and operational safety

Every callable backend tool emits one structured JSON log event named `lookout.tool_call`. The log
payload includes `tool_name`, `duration_ms`, `status`, `row_count`, `returned_row_count`, and
`error_code`. Logs intentionally omit preview rows, query result rows, exported data, and artifact
file contents.

The reference implementation uses standard error envelopes at the backend boundary. Expected
validation, workflow, cursor, token-limit, configuration, filesystem, and SQLite failures are
converted into model-visible errors with actionable messages. Unexpected exceptions become
`INTERNAL_ERROR` with a retry/log-inspection recovery hint.

Security and locality rules are deliberately simple:

- Lookout requires `LOOKOUT_DB_PATH` and `LOOKOUT_FS_ROOT`; no secrets or API keys are needed.
- Raw SQL mode is disabled. Requests containing `query_spec.sql` return `UNSUPPORTED_SQL`; agents
  should use structured query specs instead.
- Render and export filenames are generated from stable Lookout IDs, not user-provided names.
- Artifact paths are resolved relative to `LOOKOUT_FS_ROOT`; any escape attempt is rejected.
- Rendered SVG text is escaped before writing local artifact files.

Cursors are opaque base64url-encoded JSON payloads containing a cursor version, sort key, last seen
ID, and filter hash. Decoding rejects malformed, unsupported-version, sort-mismatched, or
filter-mismatched cursors with `INVALID_CURSOR`.

Fuzzy matching is deterministic across IDs, names, titles, descriptions, tags, and field names.
When a lookup expects a single target and multiple candidates tie, Lookout returns
`AMBIGUOUS_MATCH` with candidate IDs instead of silently choosing one.

Common warnings are structured and model-visible:

- `CACHE_STALE`: data is served from a stale simulated cache.
- `RESULT_TRUNCATED`: inline rows were truncated to the preview limit.
- `SOURCE_DEGRADED`: source data is offline or degraded, so cached metadata/results are used.

## Assumptions

- The evaluator can run Python 3.12 locally.
- MCP clients interact with Lookout over local stdio.
- Seed data is deterministic and safe to regenerate.
- Generated paths are always constrained to `LOOKOUT_FS_ROOT`.
- Cache/source status is simulated as part of the mock.

## Implementation notes

- Python 3.12 is used for a small, maintainable reference implementation.
- The official MCP Python SDK/FastMCP is the MCP transport layer.
- Pydantic models validate configuration and structured tool output.
- SQLite access uses the Python standard library.
- Tests run without network access or external services.

## Open questions

- Whether a future version should add a read-only SQL compatibility mode. The current reference
  implementation rejects SQL with `UNSUPPORTED_SQL` and requires structured query specs.

## Optional evaluator UI

The reference implementation includes Lookout Explorer, a secondary local demo UI under `ui/`.
This is not part of the MCP contract and is not required for agent usage. A dev-only stdlib HTTP
adapter in `lookout_mcp.demo_ui` reuses the same callable backend functions as the MCP tools for
datasource discovery, workbook/view inspection, bounded queries, renders, and exports. Artifact
metadata is read from SQLite and artifact files are served only from paths constrained to
`LOOKOUT_FS_ROOT`.

The UI exists to help a human evaluator inspect seeded workflows in a browser. It deliberately
avoids auth, external services, charting dependencies, and duplicated business logic.

## Seed data strategy

`python -m lookout_mcp.db seed` migrates the configured database, clears the core domain tables,
and reloads deterministic records. Seed IDs are generated as the first 12 lowercase hex characters
of a SHA-256 digest over stable natural keys, prefixed by entity type. Rerunning seed produces the
same IDs and row counts.

The seed contains six datasource themes:

- retail sales (`available`)
- store performance (`cache_stale`)
- sales pipeline (`available`)
- marketing spend (`source_offline`)
- customer support (`available`)
- inventory supply chain (`cache_stale`)

Each datasource has eight fields with labels, descriptions, data types, semantic roles, default
aggregations where relevant, filter/sort flags, and allowed operators derived from data type. The
generator creates 36 workbooks and 60 views: five focused analysis workbooks per datasource plus
one executive dashboard workbook per datasource. Seeded chart types include `bar`, `pie`,
`treemap`, `line`, and `histogram`.

Seeded query/export/render metadata demonstrates target workflows:

- compare Q1 revenue across regions
- pull top stores by same-store sales growth last month
- render executive dashboards
- export raw rows behind a sales pipeline health chart

Small seed export and render artifacts are written under `LOOKOUT_FS_ROOT/exports` and
`LOOKOUT_FS_ROOT/renders` to keep metadata paths inspectable and constrained to the configured
filesystem root.

## Testing strategy

Tests are split into `unit` and `integration` pytest markers and are runnable through `make test`,
`make test-unit`, and `make test-integration`. `make test` reports coverage for the
`lookout_mcp` package.

Unit tests cover configuration loading, error envelope shape, ID validation, cursor encode/decode,
filter validation by field type, query-builder behavior, fuzzy-match ambiguity, page/preview token
limits, and warning helpers.

Integration tests use temporary SQLite databases and temporary filesystem roots. They cover
migration application, migration tracking, deterministic seed counts, relationship integrity,
datasource status coverage, chart type coverage, allowed operator presence, workbook/view
relationships, artifact paths staying under `LOOKOUT_FS_ROOT`, list/get tools, `query_datasource`,
`get_view_data`, `compare_periods`, `render_view_image`, `export_view_data`, and
`export_query_result`.

Edge-case tests assert standard error envelopes for invalid cursors, oversized pages, unknown
datasource/workbook/view IDs, invalid fields, invalid operators, malformed dates,
`source_offline`, stale-cache warnings, query timeout and forced-limit failures, unsupported chart
types, ambiguous search, export write failures, and token-safety behavior that prevents bulk inline
row dumps.

Golden contract tests lock representative compact list output, `get_datasource` schema, bounded
query output, and representative error responses while avoiding volatile SQLite timestamps. Manual
QA is documented in `docs/testing.md`; `make smoke` executes the discovery, inspection, filtered
view, datasource query, period comparison, render, export, and failure-recovery checklist.

## Explicit tradeoffs

- The spec remains the primary artifact; implementation exists to validate it.
- Local SQLite keeps setup simple and deterministic at the cost of distributed-system realism.
- Filesystem render/export artifacts are easier to inspect than object storage mocks.
- Auth, multi-tenancy, realtime updates, and external write-through are intentionally deferred.
