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

Bootstrap phase only defines the package and configuration foundation. The planned persistent
entities are:

- `datasources`
- `datasource_fields`
- `workbooks`
- `views`
- `query_results`
- `exports`
- `renders`

Detailed table definitions, constraints, indexes, and migration strategy will be added in the
domain/data-model phase.

## ID formats

Planned IDs are stable string identifiers with type prefixes:

- Datasource: `ds_<12 lowercase hex>`
- Field: `fld_<12 lowercase hex>`
- Workbook: `wb_<12 lowercase hex>`
- View: `view_<12 lowercase hex>`
- Query result: `run_<12 lowercase hex>`
- Export: `exp_<12 lowercase hex>`
- Render: `rnd_<12 lowercase hex>`

## Tool surface

Bootstrap exposes:

- `health_check`: returns local service status, configured SQLite path, filesystem root, and log
  level.

Planned MCP tools:

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

Later phases will add deterministic seed data for retail sales, store performance, sales pipeline,
marketing spend, customer support, and inventory or supply chain. Seed data will cover available,
stale-cache, and source-offline datasource states.

## Testing strategy

Bootstrap tests cover configuration loading, error envelope shape, and the local health check.
Later phases will add migration, seed integrity, pagination, fuzzy matching, query validation,
render/export, and integration tests for every MCP tool.

## Explicit tradeoffs

- The spec remains the primary artifact; implementation exists to validate it.
- Local SQLite keeps setup simple and deterministic at the cost of distributed-system realism.
- Filesystem render/export artifacts are easier to inspect than object storage mocks.
- Auth, multi-tenancy, realtime updates, and external write-through are intentionally deferred.

