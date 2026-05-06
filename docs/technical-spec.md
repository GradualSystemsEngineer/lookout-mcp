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

Planned MCP tools for later phases:

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

## Workflow mapping

Planned workflows map to tools as follows:

- Discovery: `search_content`, `list_datasources`, `get_datasource`, `get_field_values`
- Workbook inspection: `list_workbooks`, `get_workbook`, `list_views`, `get_view`
- View analysis: `get_view`, `get_view_data`, `render_view_image`, `export_view_data`
- Ad hoc analysis: `query_datasource`, `compare_periods`, `export_query_result`
- Dashboard rendering: `render_workbook_image`
- Failure recovery: standard error envelopes plus warnings for degraded but readable states

## Pagination and filter semantics

List and query tools will be bounded by default. Metadata list tools should default to small pages
and return compact items. Query tools should return previews inline and require exports for large
result sets. Cursor pagination will use opaque cursors that encode version, sort key, last seen ID,
and a filter hash.

Filters will be validated against datasource field metadata, field data types, allowed operators,
and sortability/filterability flags.

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

- How much SQL mode should be exposed versus structured-only query input?
- What minimum seed scale best demonstrates realistic BI discovery without bloating the repo?
- Whether the optional demo UI is worth implementing after the core MCP contract is complete.

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

Small placeholder export and render artifacts are written under `LOOKOUT_FS_ROOT/exports` and
`LOOKOUT_FS_ROOT/renders` to keep metadata paths inspectable and constrained to the configured
filesystem root.

## Testing strategy

Tests cover configuration loading, error envelope shape, the local health check, migration
application, migration tracking, SQLite ID constraints, Pydantic ID validation, deterministic seed
counts, relationship integrity, datasource status coverage, chart type coverage, allowed operator
presence, workbook/view relationships, and artifact paths staying under `LOOKOUT_FS_ROOT`.

Later phases will add pagination, fuzzy matching, query validation, render/export behavior, and
integration tests for every MCP tool as those tool contracts are implemented.

## Explicit tradeoffs

- The spec remains the primary artifact; implementation exists to validate it.
- Local SQLite keeps setup simple and deterministic at the cost of distributed-system realism.
- Filesystem render/export artifacts are easier to inspect than object storage mocks.
- Auth, multi-tenancy, realtime updates, and external write-through are intentionally deferred.
