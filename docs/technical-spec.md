# Lookout MCP Technical Specification

## Overview

Lookout is an offline mock MCP server for a Tableau-inspired internal BI platform. AI agents use
Lookout through local MCP tools to discover analytical content, inspect datasources and dashboards,
run bounded structured queries, compare periods, render deterministic SVG chart artifacts, and
export larger result sets to local files.

The technical specification is the primary assignment artifact. The Python implementation is a
reference implementation that proves the spec while staying deterministic, local, and easy to run
from a clean checkout.

Lookout itself never calls an LLM. The LLM is the external MCP client invoking Lookout tools.

## Requirements Interpretation

- Build a credible model-visible MCP contract for a Tableau-like internal BI platform.
- Prove the contract with a small local reference implementation.
- Prefer deterministic offline behavior over production infrastructure realism.
- Persist metadata, run history, render metadata, and export metadata in SQLite.
- Write generated render/export/cache artifacts under `LOOKOUT_FS_ROOT`.
- Require no external services, network access, API keys, auth provider, Tableau server, or data
  warehouse for tests or smoke flows.

Out of scope:

- Real Tableau integration
- Real data warehouse integration
- Auth, users, roles, permissions, or multi-tenancy
- Realtime refresh
- External write-through
- Embedded LLM calls

## Architecture

The reference implementation uses Python 3.12, FastMCP from the official MCP Python SDK, SQLite
through the Python standard library, Pydantic, pytest, Ruff, and mypy.

Key modules:

- `src/lookout_mcp/server.py`: FastMCP server creation, `health_check`, and MCP tool registration.
- `src/lookout_mcp/tools/registry.py`: exact model-visible descriptions, input models, output
  models, common errors, notes, and examples.
- `src/lookout_mcp/tools/api.py`: callable backend implementation for each tool.
- `src/lookout_mcp/tools/workflow.py`: page-size and preview-limit enforcement, cursor encoding,
  fuzzy matching, warnings, and compact response helpers.
- `src/lookout_mcp/db.py`: SQLite migration and deterministic seed commands.
- `src/lookout_mcp/seed.py`: deterministic BI seed data and initial artifact generation.
- `migrations/001_core_domain_model.sql`: SQLite schema.
- `scripts/smoke.py`: end-to-end local workflow verification.

The optional `ui/` directory contains a dev-only Lookout Explorer UI. It is not part of the MCP
contract and is not required for assignment evaluation.

## Why Python and SQLite

Python + SQLite is a deliberate choice for an offline take-home assignment:

- The evaluator can run the system locally with a minimal toolchain.
- SQLite is inspectable, deterministic, and sufficient for metadata, run history, and artifact
  bookkeeping.
- Python keeps the MCP transport, validation, seed generation, and tests in one small codebase.
- The implementation focuses on the MCP contract rather than infrastructure.

The tradeoff is that SQLite is less realistic than a distributed warehouse plus object storage.
That realism is intentionally deferred because it would add setup cost without improving the
model-visible tool design.

## Why No Frontend Is Required

The evaluated product surface is MCP, not a browser application. A frontend is not required because
AI agents should be able to complete the core BI workflows through tools alone. The optional
Lookout Explorer UI exists only to help a human evaluator inspect seeded content and artifacts.
It reuses the same Python backend functions and does not add a separate business-logic path.

## Why No LLM Calls Are Inside Lookout

Lookout is agent-facing but not agentic. It provides deterministic data and tool contracts to an
external LLM client. Calling an LLM inside Lookout would introduce nondeterminism, cost, secrets,
network requirements, and ambiguous ownership of reasoning. Keeping Lookout LLM-free makes tests
repeatable and keeps the MCP server safe to run offline.

## Data Model and Schema

SQLite is the durable state store. Migrations are ordered SQL files under `migrations/`; applied
versions are tracked in `_lookout_migrations`.

Core tables:

- `datasources`
  - Columns: `id`, `name`, `label`, `description`, `theme`, `status`, `connection_type`, `tags`,
    `default_filters`, `row_count`, `cache_updated_at`, `source_updated_at`, timestamps.
  - Status values: `available`, `cache_stale`, `source_offline`.
  - Purpose: datasource catalog metadata and simulated source/cache status.
- `datasource_fields`
  - Columns: `id`, `datasource_id`, `name`, `label`, `data_type`, `semantic_role`,
    `description`, `default_aggregation`, `is_filterable`, `is_sortable`, `allowed_operators`,
    `ordinal`, timestamps.
  - Data types: `string`, `integer`, `decimal`, `date`, `datetime`, `boolean`.
  - Semantic roles: `identifier`, `dimension`, `measure`, `temporal`.
  - Purpose: field metadata used for validation, query safety, suggestions, and tool output.
- `workbooks`
  - Columns: `id`, `name`, `title`, `description`, `project`, `owner`, `tags`,
    `default_filters`, timestamps.
  - Purpose: dashboard/workbook catalog metadata.
- `views`
  - Columns: `id`, `workbook_id`, `datasource_id`, `name`, `title`, `description`,
    `chart_type`, `chart_config`, `query_spec`, `default_filters`, `visual_config`,
    `position`, timestamps.
  - Chart types: `bar`, `pie`, `treemap`, `line`, `histogram`.
  - Purpose: individual worksheet/view definitions, saved query specs, and visual metadata.
- `query_results`
  - Columns: `id`, `datasource_id`, `view_id`, `query_spec`, `row_count`, `preview_rows`,
    `status`, `warnings`, `executed_at`, `created_at`.
  - Status values: `completed`, `failed`.
  - Purpose: deterministic run metadata and bounded previews.
- `exports`
  - Columns: `id`, `query_result_id`, `view_id`, `format`, `artifact_path`, `row_count`,
    `status`, `metadata`, `created_at`.
  - Formats: `csv`, `json`.
  - Purpose: local export artifact metadata.
- `renders`
  - Columns: `id`, `workbook_id`, `view_id`, `chart_type`, `artifact_path`, `width`, `height`,
    `status`, `warnings`, `visual_config`, `created_at`.
  - Purpose: local SVG render artifact metadata.

JSON columns are used for tags, default filters, allowed operators, chart config, query specs,
preview rows, warnings, metadata, and visual config where normalization would add complexity
without improving the mock MCP contract.

Indexes cover common access paths: datasource status/theme and labels; datasource fields by
datasource/filterability/sortability/type/role; workbooks by project/title; views by workbook
position, datasource/chart type, and title; query results by datasource/time and view; exports and
renders by linked query result, view, or workbook.

## ID Formats

IDs are deterministic and stable across seed runs. The Python validators and SQLite `CHECK`
constraints enforce:

| Entity | Format | Example |
| --- | --- | --- |
| Datasource | `ds_<12 lowercase hex>` | `ds_fc7964798790` |
| Field | `fld_<12 lowercase hex>` | `fld_2e6d04c29f1a` |
| Workbook | `wb_<12 lowercase hex>` | `wb_1118ee755343` |
| View | `view_<12 lowercase hex>` | `view_ddbc335fc3f3` |
| Query result | `run_<12 lowercase hex>` | `run_8000097c03fd` |
| Export | `exp_<12 lowercase hex>` | `exp_1782d50b7ec2` |
| Render | `rnd_<12 lowercase hex>` | `rnd_2cf3738409a1` |

Seed IDs are the first 12 lowercase hex characters of a SHA-256 digest over stable natural keys,
prefixed by entity type.

## Common Response and Error Semantics

All successful tools return JSON-serializable structured data. Expected failures return:

```json
{"error": {"code": "FIELD_NOT_FOUND", "message": "Field was not found.", "details": {"field": "revenu"}}}
```

Common warnings:

- `CACHE_STALE`: datasource data is available but served from a stale simulated cache.
- `RESULT_TRUNCATED`: inline rows were truncated to the preview limit.
- `SOURCE_DEGRADED`: cached metadata/results are available while the source is degraded or
  offline.

Deterministic lookup behavior:

- Explicit IDs are validated by prefix and shape.
- Name/title lookups use deterministic fuzzy matching.
- Tied matches return `AMBIGUOUS_MATCH` with candidate IDs instead of silently choosing.
- Field errors include suggestions when useful.

## Exact Model-visible Tool Descriptions

These descriptions are the strings registered with FastMCP for model-visible tools.

| Tool | Exact description |
| --- | --- |
| `health_check` | Return local Lookout service status and resolved configuration paths. |
| `search_content` | Search Lookout BI content across datasources, workbooks, views, and fields. Returns compact paginated matches only; use get tools for details. |
| `list_datasources` | List datasource metadata in compact pages. Use filters to narrow results; page size defaults to 10 and is capped at 25. |
| `get_datasource` | Get one datasource by ID or unambiguous name, including field metadata and status warnings. |
| `get_field_values` | List representative values for one datasource field in compact paginated form. Use search to narrow high-cardinality fields. |
| `list_workbooks` | List workbook metadata in compact pages, optionally filtered by project, datasource, or fuzzy query. |
| `get_workbook` | Get one workbook by ID or unambiguous title, including compact view metadata. |
| `list_views` | List view metadata in compact pages, optionally filtered by workbook, datasource, chart type, or fuzzy query. |
| `get_view` | Get one view by ID or unambiguous title, including chart configuration and saved query specification. |
| `get_view_data` | Run the saved query for one view, optionally adding filter overrides, and return a bounded row preview with compact summary statistics. Large results must be exported with export_view_data. |
| `query_datasource` | Run a structured query against one datasource and return a bounded row preview plus a query_result_id for export. |
| `compare_periods` | Compare one metric across current and comparison periods, returning bounded preview rows and summary deltas. |
| `render_view_image` | Render one view to a local image artifact under LOOKOUT_FS_ROOT and return artifact metadata, not inline image bytes. Use filter_overrides to render a filtered variant without changing the saved view. |
| `render_workbook_image` | Render one workbook dashboard to a local image artifact under LOOKOUT_FS_ROOT and return artifact metadata, not inline image bytes. |
| `export_view_data` | Export the rows behind one view to a local file under LOOKOUT_FS_ROOT. Use this instead of requesting large inline row sets. |
| `export_query_result` | Export a prior query result to a local file under LOOKOUT_FS_ROOT. Use this for rows beyond the preview limit. |

## Complete Tool Contracts

### `health_check`

Input: no fields.

Output:

- `status`
- `service`
- `db_path`
- `fs_root`
- `log_level`

Common errors: `CONFIG_MISSING`.

Example:

```json
{}
```

Success:

```json
{"status": "ok", "service": "lookout-mcp", "db_path": "lookout.sqlite3", "fs_root": "var", "log_level": "INFO"}
```

### `search_content`

Input:

- `query` (required string): search text for names, titles, descriptions, tags, field names, or
  IDs.
- `content_types` (optional array): any of `datasource`, `workbook`, `view`, `field`.
- `page_size` (optional integer): defaults to `10`, maximum `25`.
- `cursor` (optional string): opaque cursor for the same filters and sort.

Output model: `SearchContentOutput`.

Output shape:

- `items`: compact matches with `id`, `kind`, `label`, `score`, and matched metadata.
- `row_count`
- `returned_row_count`
- `truncated`
- `next_cursor`
- `warnings`

Common errors: `PAGE_SIZE_TOO_LARGE`, `INVALID_CURSOR`, `AMBIGUOUS_MATCH`.

Example:

```json
{"query": "revenue dashboard", "content_types": ["workbook", "view"], "page_size": 2}
```

Success:

```json
{"items": [{"id": "view_7ed2cb9bdb45", "kind": "view", "label": "Dashboard: Monthly Revenue Trend", "score": 325, "matched_fields": ["name", "title", "description"]}, {"id": "view_e17b7f8655b7", "kind": "view", "label": "Dashboard: Q1 Revenue by Region", "score": 325, "matched_fields": ["name", "title", "description"]}], "row_count": 89, "returned_row_count": 2, "truncated": true, "next_cursor": "eyJmaWx0ZXJfaGFzaCI6IjYwNzM3ZDdlNTk3Mjc4YjMiLCJsYXN0X2lkIjoidmlld19lMTdiN2Y4NjU1YjciLCJzb3J0X2tleSI6InNlYXJjaF9zY29yZSIsInZlcnNpb24iOjF9", "warnings": []}
```

### `list_datasources`

Input:

- `status` (optional string): `available`, `cache_stale`, or `source_offline`.
- `theme` (optional string): exact theme filter.
- `query` (optional string): fuzzy filter over name, label, tags, or ID.
- `page_size` (optional integer): defaults to `10`, maximum `25`.
- `cursor` (optional string): opaque cursor for the same filters and sort.

Output model: `DatasourceListOutput`.

Output shape:

- `items`: compact datasource items with `id`, `label`, `status`, `theme`, `row_count`, `tags`.
- `row_count`
- `returned_row_count`
- `truncated`
- `next_cursor`
- `warnings`

Common errors: `PAGE_SIZE_TOO_LARGE`, `INVALID_CURSOR`, `AMBIGUOUS_MATCH`.

Example:

```json
{"status": "cache_stale", "page_size": 10}
```

Success:

```json
{"items": [{"id": "ds_b84bb3100a6a", "label": "Store Performance", "status": "cache_stale", "theme": "store performance", "row_count": 37200, "tags": ["store performance", "cache_stale", "seeded"]}], "row_count": 2, "returned_row_count": 2, "truncated": false, "next_cursor": null, "warnings": [{"code": "CACHE_STALE", "message": "Datasource cache is stale; results may lag the source system.", "details": {"status": "cache_stale"}}]}
```

### `get_datasource`

Input:

- `datasource` (required string): datasource ID or unambiguous datasource name/label.
- `include_fields` (optional boolean): defaults to `true`.

Output model: `DatasourceDetailOutput`.

Output shape:

- `datasource`: full datasource metadata.
- `fields`: compact field metadata when requested.
- `warnings`: source/cache warnings.

Common errors: `NOT_FOUND`, `AMBIGUOUS_MATCH`.

Example:

```json
{"datasource": "Retail Sales", "include_fields": true}
```

Success:

```json
{"datasource": {"id": "ds_fc7964798790", "label": "Retail Sales", "status": "available", "row_count": 482400}, "fields": [{"id": "fld_2e6d04c29f1a", "name": "channel", "label": "Channel", "data_type": "string"}], "warnings": []}
```

### `get_field_values`

Input:

- `datasource` (required string): datasource ID or unambiguous datasource name/label.
- `field` (required string): field ID, name, or label.
- `search` (optional string): prefix or contains search over values.
- `page_size` (optional integer): defaults to `10`, maximum `25`.
- `cursor` (optional string): opaque cursor for the same filters and sort.

Output model: `FieldValuesOutput`.

Output shape:

- `items`: representative value items.
- `row_count`
- `returned_row_count`
- `truncated`
- `next_cursor`
- `warnings`

Common errors: `PAGE_SIZE_TOO_LARGE`, `INVALID_CURSOR`, `AMBIGUOUS_MATCH`, `NOT_FOUND`.

Example:

```json
{"datasource": "Retail Sales", "field": "region", "page_size": 4}
```

Success:

```json
{"items": [{"id": "fld_437447dbc62c:1", "value": "Northeast"}, {"id": "fld_437447dbc62c:2", "value": "Southeast"}, {"id": "fld_437447dbc62c:3", "value": "West"}, {"id": "fld_437447dbc62c:4", "value": "Central"}], "row_count": 4, "returned_row_count": 4, "truncated": false, "next_cursor": null, "warnings": []}
```

### `list_workbooks`

Input:

- `project` (optional string): exact project filter.
- `datasource` (optional string): datasource ID/name/label filter.
- `query` (optional string): fuzzy filter over title, description, tags, or ID.
- `page_size` (optional integer): defaults to `10`, maximum `25`.
- `cursor` (optional string): opaque cursor for the same filters and sort.

Output model: `WorkbookListOutput`.

Output shape:

- `items`: compact workbook items with `id`, `title`, `project`, `owner`, `tags`.
- `row_count`
- `returned_row_count`
- `truncated`
- `next_cursor`
- `warnings`

Common errors: `PAGE_SIZE_TOO_LARGE`, `INVALID_CURSOR`, `AMBIGUOUS_MATCH`.

Example:

```json
{"datasource": "Retail Sales", "page_size": 10}
```

Success:

```json
{"items": [{"id": "wb_22c5ed3575e6", "title": "Retail Sales Executive Dashboard", "project": "Executive Dashboards", "owner": "lookout-demo", "tags": ["retail sales", "dashboard", "executive"]}], "row_count": 6, "returned_row_count": 6, "truncated": false, "next_cursor": null, "warnings": []}
```

### `get_workbook`

Input:

- `workbook` (required string): workbook ID or unambiguous workbook name/title.
- `include_views` (optional boolean): defaults to `true`.

Output model: `WorkbookDetailOutput`.

Output shape:

- `workbook`: workbook metadata.
- `views`: compact view metadata when requested.
- `warnings`

Common errors: `NOT_FOUND`, `AMBIGUOUS_MATCH`.

Example:

```json
{"workbook": "Retail Sales Executive Dashboard", "include_views": true}
```

Success:

```json
{"workbook": {"id": "wb_22c5ed3575e6", "title": "Retail Sales Executive Dashboard", "project": "Executive Dashboards"}, "views": [{"id": "view_e17b7f8655b7", "title": "Dashboard: Q1 Revenue by Region", "chart_type": "bar"}], "warnings": []}
```

### `list_views`

Input:

- `workbook` (optional string): workbook ID/name/title.
- `datasource` (optional string): datasource ID/name/label.
- `chart_type` (optional string): one of `bar`, `pie`, `treemap`, `line`, `histogram`.
- `query` (optional string): fuzzy filter over title, description, tags, field names, or ID.
- `page_size` (optional integer): defaults to `10`, maximum `25`.
- `cursor` (optional string): opaque cursor for the same filters and sort.

Output model: `ViewListOutput`.

Output shape:

- `items`: compact view items with `id`, `title`, `workbook_id`, `datasource_id`,
  `chart_type`, `position`.
- `row_count`
- `returned_row_count`
- `truncated`
- `next_cursor`
- `warnings`

Common errors: `PAGE_SIZE_TOO_LARGE`, `INVALID_CURSOR`, `AMBIGUOUS_MATCH`,
`UNSUPPORTED_CHART_TYPE`.

Example:

```json
{"datasource": "Retail Sales", "chart_type": "bar", "page_size": 2}
```

Success:

```json
{"items": [{"id": "view_80a986a56ae6", "title": "Category Revenue Treemap Context: Q1 Revenue by Region", "workbook_id": "wb_db7f24d543c8", "datasource_id": "ds_fc7964798790", "chart_type": "bar", "position": 1}, {"id": "view_e17b7f8655b7", "title": "Dashboard: Q1 Revenue by Region", "workbook_id": "wb_22c5ed3575e6", "datasource_id": "ds_fc7964798790", "chart_type": "bar", "position": 1}], "row_count": 6, "returned_row_count": 2, "truncated": true, "next_cursor": "eyJmaWx0ZXJfaGFzaCI6IjRhMDc0MmFlZGQ0YWUzZTQiLCJsYXN0X2lkIjoidmlld19lMTdiN2Y4NjU1YjciLCJzb3J0X2tleSI6InRpdGxlIiwidmVyc2lvbiI6MX0", "warnings": []}
```

### `get_view`

Input:

- `view` (required string): view ID or unambiguous view name/title.
- `include_query_spec` (optional boolean): defaults to `true`.

Output model: `ViewDetailOutput`.

Output shape:

- `view`: full view metadata, chart configuration, and optionally saved query spec.
- `warnings`

Common errors: `NOT_FOUND`, `AMBIGUOUS_MATCH`.

Example:

```json
{"view": "Q1 Revenue by Region", "include_query_spec": true}
```

Success:

```json
{"view": {"id": "view_cd948d133126", "title": "Q1 Revenue by Region", "chart_type": "bar", "query_spec": {"operation": "aggregate", "group_by": ["region"], "metrics": [{"field": "revenue", "aggregation": "sum"}]}}, "warnings": []}
```

### `get_view_data`

Input:

- `view` (required string): view ID or unambiguous view name/title.
- `filter_overrides` (optional object or array): a dict becomes field-value equality filters; an
  array may contain structured filter objects.
- `preview_limit` (optional integer): defaults to `100`, maximum `1000`.

Output model: `ViewDataOutput`.

Output shape:

- `query_result_id`: stable run ID for this saved view query.
- `rows`: bounded preview rows.
- `row_count`
- `returned_row_count`
- `truncated`
- `next_cursor`
- `warnings`
- `summary_statistics`: compact min/max/average/trend summary for numeric fields in the returned
  preview rows.

Common errors: `INVALID_INPUT`, `INVALID_FILTER`, `INVALID_SORT`, `NOT_FOUND`,
`FIELD_NOT_FOUND`, `AMBIGUOUS_MATCH`, `LIMIT_EXCEEDED`, `QUERY_TIMEOUT`,
`SOURCE_UNAVAILABLE`.

Example:

```json
{"view": "Q1 Revenue by Region", "filter_overrides": {"region": "Northeast"}, "preview_limit": 2}
```

Success:

```json
{"query_result_id": "run_ac79185d999f", "rows": [{"region": "Central", "sum_revenue": 393102}, {"region": "West", "sum_revenue": 368071}], "row_count": 4, "returned_row_count": 2, "truncated": true, "next_cursor": null, "warnings": [{"code": "RESULT_TRUNCATED", "message": "Inline rows were truncated to the preview limit.", "details": {"row_count": 4, "returned_row_count": 2}}], "summary_statistics": {"basis": "returned_preview_rows", "numeric_fields": {"sum_revenue": {"min": 368071, "max": 393102, "avg": 380586.5, "trend": {"first": 393102, "last": 368071, "delta": -25031, "direction": "down"}}}}}
```

### `query_datasource`

Input:

- `datasource` (required string): datasource ID or unambiguous datasource name/label.
- `query_spec` (required object): structured query spec using validated field names.
- `preview_limit` (optional integer): defaults to `100`, maximum `1000`.

Structured query spec fields:

- `operation`: `aggregate`, `detail`, or `histogram`; defaults to `aggregate`.
- `fields`: selected fields for detail queries.
- `metrics`: objects with `field`, optional `aggregation`, optional `alias`.
- `filters`: object equality filters or structured filter objects.
- `group_by`: dimension fields for aggregate queries.
- `order_by` or `sort`: objects with `field` and `direction`.
- `limit`: maximum synthetic query rows, capped at `1000`.
- `field` and `bins`: histogram-specific fields.
- `timeout_ms`: requests below one millisecond return deterministic `QUERY_TIMEOUT`.
- `sql`: rejected with `UNSUPPORTED_SQL`.

Output model: `QueryDatasourceOutput`.

Output shape:

- `query_result_id`
- `rows`: bounded preview rows.
- `row_count`
- `returned_row_count`
- `truncated`
- `next_cursor`
- `warnings`

Common errors: `INVALID_INPUT`, `INVALID_FILTER`, `INVALID_SORT`, `NOT_FOUND`,
`FIELD_NOT_FOUND`, `AMBIGUOUS_MATCH`, `LIMIT_EXCEEDED`, `QUERY_TIMEOUT`,
`SOURCE_UNAVAILABLE`, `UNSUPPORTED_SQL`.

Example:

```json
{"datasource": "Retail Sales", "query_spec": {"operation": "aggregate", "group_by": ["region"], "metrics": [{"field": "revenue", "aggregation": "sum"}], "order_by": [{"field": "revenue", "direction": "desc"}]}, "preview_limit": 2}
```

Success:

```json
{"query_result_id": "run_94b17a81da4f", "rows": [{"region": "Central", "sum_revenue": 393102}, {"region": "West", "sum_revenue": 368071}], "row_count": 4, "returned_row_count": 2, "truncated": true, "next_cursor": null, "warnings": [{"code": "RESULT_TRUNCATED", "message": "Inline rows were truncated to the preview limit.", "details": {"row_count": 4, "returned_row_count": 2}}]}
```

### `compare_periods`

Input:

- `datasource` (required string): datasource ID or unambiguous datasource name/label.
- `metric` (required string): measure field ID, name, or label.
- `period_field` (required string): temporal field ID, name, or label.
- `current_period` (required object): period selector such as `{"quarter": "Q1"}`.
- `comparison_period` (required object): period selector such as `{"quarter": "Q4"}`.
- `dimensions` (optional array): dimension fields.
- `preview_limit` (optional integer): defaults to `100`, maximum `1000`.

Output model: `ComparePeriodsOutput`.

Output shape:

- `comparison`: metric, period field, current total, comparison total, delta, percent delta.
- `rows`: bounded preview rows.
- `row_count`
- `returned_row_count`
- `truncated`
- `next_cursor`
- `warnings`

Common errors: `INVALID_INPUT`, `INVALID_FILTER`, `INVALID_SORT`, `NOT_FOUND`,
`FIELD_NOT_FOUND`, `AMBIGUOUS_MATCH`, `LIMIT_EXCEEDED`, `QUERY_TIMEOUT`,
`SOURCE_UNAVAILABLE`.

Example:

```json
{"datasource": "Retail Sales", "metric": "revenue", "period_field": "order_date", "current_period": {"quarter": "Q1"}, "comparison_period": {"quarter": "Q4"}, "dimensions": ["region"], "preview_limit": 2}
```

Success:

```json
{"comparison": {"metric": "revenue", "period_field": "order_date", "current_total": 900000, "comparison_total": 840000, "delta": 60000, "pct_delta": 0.0714}, "rows": [{"region": "Northeast", "current_value": 240000, "comparison_value": 210000, "delta": 30000, "pct_delta": 0.1429}], "row_count": 4, "returned_row_count": 2, "truncated": true, "next_cursor": null, "warnings": [{"code": "RESULT_TRUNCATED", "message": "Inline rows were truncated to the preview limit.", "details": {"row_count": 4, "returned_row_count": 2}}]}
```

### `render_view_image`

Input:

- `view` (required string): view ID or unambiguous view name/title.
- `filter_overrides` (optional object or array): render-time filters using the same semantics as
  `get_view_data`. Overrides affect the generated artifact identity but do not modify the saved
  view.
- `width` (optional integer): defaults to `1200`, must be positive.
- `height` (optional integer): defaults to `800`, must be positive.

Output model: `RenderArtifactOutput`.

Output shape:

- `render_id`
- `artifact_path`: relative to `LOOKOUT_FS_ROOT`.
- `width`
- `height`
- `status`
- `warnings`

Common errors: `INVALID_INPUT`, `INVALID_FILTER`, `FIELD_NOT_FOUND`, `NOT_FOUND`,
`AMBIGUOUS_MATCH`, `LIMIT_EXCEEDED`, `RENDER_FAILED`, `RATE_LIMITED`.

Example:

```json
{"view": "Q1 Revenue by Region", "width": 1200, "height": 800}
```

Success:

```json
{"render_id": "rnd_a3adef0c852e", "artifact_path": "renders/rnd_a3adef0c852e.svg", "width": 1200, "height": 800, "status": "ready", "warnings": []}
```

Filtered example:

```json
{"view": "Q1 Revenue by Region", "filter_overrides": {"region": "Northeast"}, "width": 1200, "height": 800}
```

### `render_workbook_image`

Input:

- `workbook` (required string): workbook ID or unambiguous workbook name/title.
- `width` (optional integer): defaults to `1440`, must be positive.
- `height` (optional integer): defaults to `960`, must be positive.

Output model: `RenderArtifactOutput`.

Output shape:

- `render_id`
- `artifact_path`: relative to `LOOKOUT_FS_ROOT`.
- `width`
- `height`
- `status`
- `warnings`

Common errors: `INVALID_INPUT`, `NOT_FOUND`, `AMBIGUOUS_MATCH`, `LIMIT_EXCEEDED`,
`RENDER_FAILED`, `RATE_LIMITED`.

Example:

```json
{"workbook": "Retail Sales Executive Dashboard", "width": 1440, "height": 960}
```

Success:

```json
{"render_id": "rnd_d8d02bd6aa32", "artifact_path": "renders/rnd_d8d02bd6aa32.svg", "width": 1440, "height": 960, "status": "ready", "warnings": []}
```

### `export_view_data`

Input:

- `view` (required string): view ID or unambiguous view name/title.
- `format` (optional string): `csv` or `json`; defaults to `csv`.

Output model: `ExportArtifactOutput`.

Output shape:

- `export_id`
- `artifact_path`: relative to `LOOKOUT_FS_ROOT`.
- `format`
- `row_count`
- `status`
- `warnings`

Common errors: `INVALID_INPUT`, `NOT_FOUND`, `AMBIGUOUS_MATCH`, `LIMIT_EXCEEDED`,
`EXPORT_FAILED`, `RATE_LIMITED`.

Example:

```json
{"view": "Pipeline Health by Stage", "format": "csv"}
```

Success:

```json
{"export_id": "exp_63d4ef849ea9", "artifact_path": "exports/exp_63d4ef849ea9.csv", "format": "csv", "row_count": 10, "status": "ready", "warnings": []}
```

### `export_query_result`

Input:

- `query_result_id` (required string): query result ID returned by `query_datasource` or
  `get_view_data`.
- `format` (optional string): `csv` or `json`; defaults to `csv`.

Output model: `ExportArtifactOutput`.

Output shape:

- `export_id`
- `artifact_path`: relative to `LOOKOUT_FS_ROOT`.
- `format`
- `row_count`
- `status`
- `warnings`

Common errors: `INVALID_INPUT`, `NOT_FOUND`, `AMBIGUOUS_MATCH`, `LIMIT_EXCEEDED`,
`EXPORT_FAILED`, `RATE_LIMITED`.

Example:

```json
{"query_result_id": "run_8000097c03fd", "format": "json"}
```

Success:

```json
{"export_id": "exp_cc936e7aea90", "artifact_path": "exports/exp_cc936e7aea90.json", "format": "json", "row_count": 10, "status": "ready", "warnings": []}
```

## Workflow-to-tool Mapping

| Workflow | Tool sequence | Notes |
| --- | --- | --- |
| Check local server readiness | `health_check` | Confirms local configuration paths before analysis work. |
| W1 Explore datasources | `search_content` or `list_datasources` -> `get_datasource` -> `get_field_values` | List tools return compact datasource summaries; get tools return field metadata and representative values without bulk dumps. |
| W2 View workbook contents | `list_workbooks` -> `get_workbook` -> `list_views` or `get_view` | Workbooks expose title, description, project, owner, and contained compact view metadata. |
| W3 Apply filters to views | `get_view` -> `get_view_data` with `filter_overrides` | Overrides are validated against datasource fields and are applied only to that run. |
| W4 Query datasource | `get_datasource` -> `query_datasource` -> optional `export_query_result` | Structured query specs support detail, aggregate, and histogram retrieval with bounded previews and CSV/JSON export. |
| W5 Compare time periods | `get_datasource` -> `compare_periods` | Returns metric totals, deltas, percentage deltas, and bounded dimension rows for the agent to analyze. |
| W6 Analyze view details | `get_view` -> `get_view_data` | `get_view` returns chart type, title, chart config, axis/field mapping, saved query spec, and `get_view_data` returns values plus compact summary statistics. |
| W7 Generate view images | `render_view_image` with optional `filter_overrides`; `render_workbook_image` for dashboards | Render tools write SVG artifacts under `LOOKOUT_FS_ROOT` and return metadata instead of inline image bytes. |
| W8 Export view data | `export_view_data`; or `get_view_data` -> `export_query_result` | CSV headers are derived from the query rows behind the view/query result and written under `LOOKOUT_FS_ROOT/exports`. |
| Recover from failures | Standard error envelopes, candidate suggestions, warnings, and retry hints | Agents can retry with candidate IDs, smaller limits, corrected fields, or exports as directed by error details. |

## Pagination Semantics

Metadata list tools use compact pages:

- Default `page_size`: `10`.
- Maximum `page_size`: `25`.
- Invalid values return `PAGE_SIZE_TOO_LARGE`.
- Page responses include `row_count`, `returned_row_count`, `truncated`, and `next_cursor`.
- Cursors are opaque base64url-encoded JSON containing cursor version, sort key, last seen ID, and
  filter hash.
- Cursor decoding rejects malformed, unsupported-version, sort-mismatched, or filter-mismatched
  cursors with `INVALID_CURSOR`.

Query preview tools use bounded inline rows:

- Default `preview_limit`: `100`.
- Maximum `preview_limit`: `1000`.
- Invalid values return `LIMIT_EXCEEDED`.
- Truncated previews include a `RESULT_TRUNCATED` warning.
- Larger result access must use export tools.

## Filter and Sort Semantics

Filters are validated against datasource field metadata:

- Field must exist for the datasource unless explicitly allowed as a virtual saved-view filter.
- Field must be marked `is_filterable`.
- Operator must appear in the field's `allowed_operators`.
- String values must be JSON strings.
- Integer values must be JSON integers, not booleans.
- Decimal values must be JSON numbers, not booleans.
- Boolean values must be JSON booleans.
- Date values must be ISO date strings.
- Datetime values must be ISO datetime strings.
- `between` requires exactly two values.
- `in` requires at least one value.
- `contains` is only valid for string fields.

Sort clauses are validated against sortable fields or metric aliases. Invalid sort fields return
`INVALID_SORT`.

## Query Safety

Lookout intentionally avoids raw SQL execution in the reference implementation. Requests containing
`query_spec.sql` return `UNSUPPORTED_SQL` with a recovery hint to use structured fields, metrics,
filters, and `group_by`.

Query safety controls:

- Structured query specs only.
- Field/type/operator validation before execution.
- Source status checks before ad hoc queries.
- `query_spec.limit` capped at `1000`.
- Inline previews capped at `1000`.
- Detail query row counts are simulated from datasource metadata but preview rows remain bounded.
- Render/export paths are generated from Lookout IDs, not user filenames.
- Artifact paths are resolved under `LOOKOUT_FS_ROOT`; escapes are rejected.
- SVG text is escaped before writing render files.
- Expensive artifact operations are guarded by an in-process concurrency limit.

## Token Usage Controls

Lookout does not incur internal LLM cost, but it is designed to keep external agent context usage
low:

- Compact list outputs omit verbose descriptions, full field lists, default filters, preview rows,
  and artifact contents.
- List tools cap pages at `25`.
- Query tools return previews only and cap previews at `1000`.
- Exports are the intended path for larger results.
- Render tools return artifact metadata and never inline image bytes.
- Structured logs include tool name, duration, status, row counts, and error code, but omit row
  payloads and file contents.

## Error, Retry, and Rate-limit Strategy

Expected errors are deterministic and actionable:

- `CONFIG_MISSING`: set `LOOKOUT_DB_PATH` and `LOOKOUT_FS_ROOT`.
- `PAGE_SIZE_TOO_LARGE`: reduce `page_size`.
- `LIMIT_EXCEEDED`: reduce `preview_limit` or `query_spec.limit`, or use an export.
- `INVALID_CURSOR`: restart pagination with the same filters.
- `NOT_FOUND`: search/list first or use a valid ID.
- `AMBIGUOUS_MATCH`: retry with one returned candidate ID.
- `FIELD_NOT_FOUND`: use a suggested field or inspect datasource fields.
- `INVALID_FILTER`: correct operator/value/type/filterability.
- `INVALID_SORT`: sort by a sortable field or metric alias.
- `SOURCE_UNAVAILABLE`: source is simulated offline; do not retry unchanged.
- `CACHE_STALE`: warning only; result is usable but may lag source.
- `UNSUPPORTED_SQL`: use structured query specs.
- `QUERY_TIMEOUT`: reduce complexity or retry with a valid timeout.
- `RATE_LIMITED`: retry later or reduce concurrent render/export requests.
- `EXPORT_FAILED` and `RENDER_FAILED`: inspect local filesystem permissions and paths.
- `INTERNAL_ERROR`: unexpected failure; inspect local logs.

The reference implementation has no external HTTP rate limit because it does not call external
services. Local concurrency limits apply to expensive artifact operations.

## Open Questions and Positions

### Should read-only failure modes be exposed?

Position: yes. Even though Lookout is offline and synthetic, agents should see realistic
read-only degradation states because analysts routinely encounter stale extracts, unavailable
sources, and cached dashboard data. Hiding those states would make the mock less like a BI
platform and would fail to train agents to recover safely.

Lookout exposes these states as `status` on datasources, structured warnings on readable cached
workflows, and hard errors when a workflow cannot safely proceed.

## Position on Read-only Failure Modes

Lookout's MCP tools are read-only with respect to external systems because there are no external
systems. The only writes are local SQLite metadata updates and local artifact creation under
`LOOKOUT_FS_ROOT`.

Read-only failures are represented in two ways:

- Hard failures when a workflow cannot safely proceed, such as `SOURCE_UNAVAILABLE` for ad hoc
  queries against a source-offline datasource.
- Warnings when cached/mock data remains usable, such as `CACHE_STALE` and `SOURCE_DEGRADED`.

This gives agents a deterministic recovery path without pretending that stale or offline source
states are fresh data.

## Seed Data Strategy

`python -m lookout_mcp.db seed` migrates the configured database, clears the core domain tables,
and reloads deterministic BI records. Rerunning seed produces stable IDs, row counts, relationships,
and representative artifacts.

Seed datasource themes:

- `Retail Sales` (`available`)
- `Store Performance` (`cache_stale`)
- `Sales Pipeline` (`available`)
- `Marketing Spend` (`source_offline`)
- `Customer Support` (`available`)
- `Inventory Supply Chain` (`cache_stale`)

Each datasource has eight fields with data types, semantic roles, filter/sort flags, default
aggregations where relevant, and allowed operators derived from data type.

The seed generator creates:

- 6 datasources
- 48 datasource fields
- 36 workbooks
- 180 views
- Seeded query results, exports, and renders for representative workflows

Each seeded workbook contains five views, so the catalog sits within the brief's target shape of
30 to 80 dashboards with 4 to 12 charts each while remaining small enough for deterministic local
tests. Focused analysis workbooks keep one primary view title unprefixed for clean lookup and add
supporting context views with prefixed titles; executive dashboards contain the same five
datasource views with dashboard-specific titles.

Seeded workflows include revenue by region, store growth, sales pipeline health, marketing spend,
support backlog, inventory supply chain, executive dashboards, stale-cache warnings, and
source-offline failures.

Small seed export and render artifacts are written under `LOOKOUT_FS_ROOT/exports` and
`LOOKOUT_FS_ROOT/renders` so artifact metadata is inspectable and path constraints are testable.

## Local Setup and Execution

From a clean checkout:

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

Required environment:

```bash
LOOKOUT_DB_PATH=./lookout.sqlite3
LOOKOUT_FS_ROOT=./var
LOOKOUT_LOG_LEVEL=INFO
```

`make smoke` exercises discovery, datasource inspection, workbook/view inspection, saved view
queries, filter overrides, ad hoc datasource queries, period comparisons, render creation, export
creation, source-offline failures, stale-cache warnings, invalid-field suggestions, and safe
artifact paths under `LOOKOUT_FS_ROOT`.

## Testing Strategy

Tests are split into `unit` and `integration` pytest markers:

- `make test`: full suite with coverage.
- `make test-unit`: fast unit tests.
- `make test-integration`: temporary SQLite/filesystem integration tests.
- `make smoke`: end-to-end workflow against the configured local `.env`.

Unit coverage includes:

- Configuration loading and `CONFIG_MISSING`.
- Standard error envelope shape.
- ID validation.
- Cursor encode/decode and mismatch handling.
- Page-size and preview-limit enforcement.
- Fuzzy ambiguity handling.
- Warning helpers.
- Filter validation by field type/operator.
- Query builder behavior.

Integration coverage includes:

- Migration application and tracking.
- Deterministic seed counts and relationships.
- Datasource status and chart type coverage.
- Artifact paths constrained to `LOOKOUT_FS_ROOT`.
- Discovery/list/get tools.
- Saved view previews.
- Structured datasource queries.
- Period comparisons.
- Render/export artifact creation.
- Stale-cache and source-offline behavior.
- Structured observability logs that omit row payloads.
- Golden response shapes for representative tool outputs and errors.

Manual QA is documented in `docs/testing.md`; the smoke script is the executable checklist.

## Observability

Each callable backend tool emits one structured JSON log event named `lookout.tool_call`.

Fields:

- `tool_name`
- `duration_ms`
- `status`
- `row_count`
- `returned_row_count`
- `error_code`

Logs intentionally omit preview rows, query rows, exported data, image bytes, and artifact file
contents.

## Assumptions

- The evaluator can run Python 3.12 locally.
- MCP clients interact with Lookout over local stdio.
- Seed data is deterministic and safe to regenerate.
- Generated files can be written under `LOOKOUT_FS_ROOT`.
- Source/cache status is simulated as part of the mock BI platform.
- The spec is the source of truth; the implementation validates it but does not aim to become a
  complete BI product.

## Technical Implementation Notes

- FastMCP registers a small stdio MCP server named `lookout`.
- Pydantic models validate tool inputs and structured outputs.
- SQLite connections enable foreign keys.
- Migrations are idempotent and tracked.
- Seed clears and reloads domain tables in dependency order.
- Query IDs, render IDs, and export IDs are deterministic for equivalent inputs where practical.
- Rendered artifacts are SVG files with escaped text.
- Exported artifacts are CSV or JSON.
- `.env.example` keeps local generated files under `./var`.
- Generated `var/` contents, local SQLite databases, virtualenvs, and caches are not submission
  artifacts.

### Tool SQL and Filesystem Interactions

| Tool area | SQLite tables touched | Filesystem interaction |
| --- | --- | --- |
| Discovery/list/get | Reads `datasources`, `datasource_fields`, `workbooks`, and `views` with indexed filters and deterministic fuzzy matching. | None. |
| Saved view data | Reads `views`, `datasources`, `datasource_fields`, and cached `query_results`; writes/updates `query_results` when a filtered run is generated. | None. |
| Ad hoc datasource query | Reads `datasources` and `datasource_fields`; writes/updates `query_results` with bounded preview rows and run metadata. | None. |
| Period comparison | Reads `datasources` and `datasource_fields`; no persisted query result because the response is already a compact comparison summary. | None. |
| View/workbook render | Reads `views`, `workbooks`, `datasources`, and `datasource_fields`; writes/updates `renders`. | Writes generated SVG files to `LOOKOUT_FS_ROOT/renders/<render_id>.svg`; path containment is checked before writing. |
| View/query export | Reads `query_results`, `views`, and `datasources`; writes/updates `exports`. | Writes CSV or JSON files to `LOOKOUT_FS_ROOT/exports/<export_id>.<format>`; no user-supplied filenames are accepted. |

Render-time `filter_overrides` are validated against datasource fields and become part of the
deterministic render ID. Export column headers are derived from the row dictionaries behind the
view or query result so CSV headers match the returned data model.

## Explicit Tradeoffs

- Specification-first: the spec remains the evaluated artifact, and implementation is intentionally
  narrow.
- Local SQLite over warehouse mocks: easier setup and deterministic tests at the cost of production
  realism.
- Filesystem artifacts over object storage: easier inspection and path-safety testing.
- Structured query specs over raw SQL: safer for agents and easier to validate.
- Deterministic synthetic rows over real data execution: sufficient for MCP contract testing.
- SVG renders over real visualization rendering: proves artifact workflow without large graphics
  dependencies.
- No auth or multi-tenancy: avoids out-of-scope policy complexity.
- Optional UI only: MCP tools are the required interface.

## Intentionally Deferred Work

- Real Tableau API integration.
- Real warehouse execution.
- Read-only SQL compatibility mode with static analysis and safe execution limits.
- Auth, users, roles, permissions, and multi-tenancy.
- Realtime refresh and subscriptions.
- Production object storage for artifacts.
- More chart/image formats.
- Richer cache lifecycle and cleanup policies.
- Larger transcript-based MCP client examples.

## Final Checklist

- Fresh checkout works with `make install`, `.env.example`, `make migrate`, and `make seed`.
- DB migration works.
- Seed works.
- All tests pass.
- MCP server starts.
- Core workflows work through `make smoke`.
- Render/export files are created under `LOOKOUT_FS_ROOT`.
- Failure modes are deterministic.
- No external services or API keys are required.
- Spec and implementation agree.
- No unresolved drafting markers remain.

## Follow-up Interview Notes

- Python + SQLite were chosen because they are boring, local, inspectable, and deterministic.
- No frontend is required because MCP tools are the evaluated product surface; the optional UI is
  only an evaluator aid.
- No LLM calls are inside Lookout because the LLM is the MCP client, and internal model calls would
  add cost, secrets, nondeterminism, and scope creep.
- Token usage is controlled through compact outputs, hard list/query caps, exports for large
  results, render metadata instead of inline image bytes, and log redaction.
- Query safety comes from structured specs, field/type/operator validation, disabled raw SQL,
  bounded previews, source-status checks, deterministic errors, and safe artifact paths.
- Failure modes use standard envelopes for hard failures and structured warnings for degraded but
  readable states.
- Deferred work is intentionally limited to production integrations, auth, read-only SQL,
  realtime updates, object storage, richer rendering, and broader examples.
