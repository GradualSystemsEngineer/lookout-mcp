# Testing and Verification

Lookout tests are deterministic and local-only. They use temporary SQLite databases and temporary
filesystem roots, so they do not depend on `.env`, external services, API keys, or test ordering.

## Automated Commands

Run the full Python suite with coverage:

```bash
make test
```

Run marker-scoped subsets:

```bash
make test-unit
make test-integration
```

Run the end-to-end workflow smoke check against the configured local `.env`:

```bash
make smoke
```

`make test` reports line coverage for `lookout_mcp` with missing lines. Unit tests cover ID and
cursor validation, filter/type validation, query builder behavior, error envelopes, fuzzy-match
ambiguity, and token-safety helpers. Integration tests seed SQLite in a temporary root and exercise
the MCP contract through callable tool functions.

## Golden Contract Checks

Golden tests lock representative output shapes for:

- compact list responses
- `get_datasource` schema and field metadata
- bounded `query_datasource` results
- standard error envelopes

The golden checks avoid volatile SQLite timestamps and assert stable IDs, row counts, warnings,
cursor shape, and compact response fields.

## Manual QA Checklist

After `make seed`, use `make smoke` as the primary manual QA checklist. It verifies:

- discovery with `search_content`, `list_datasources`, `get_datasource`, and `get_field_values`
- workbook inspection with `list_workbooks`, `get_workbook`, and `get_view`
- filtered view retrieval with `get_view_data`
- datasource querying with `query_datasource`
- period comparison with `compare_periods`
- view rendering with `render_view_image`
- data export with `export_view_data` and `export_query_result`
- failure recovery for source-offline data, stale-cache warnings, invalid fields, and safe artifact
  paths under `LOOKOUT_FS_ROOT`
