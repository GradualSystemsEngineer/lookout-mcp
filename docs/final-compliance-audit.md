# Final Compliance Audit

Date: 2026-05-05

Auditor: Codex final senior-level audit pass.

Source materials reviewed:

- `HandshakeInstructions.pdf` via OCR of `docs/Page1.png` through `docs/Page12.png`
- `README.md`
- `docs/technical-spec.md`
- `docs/engineering-decisions.md`
- `docs/testing.md`
- `lookout_codex_prompts/*.md`
- `pyproject.toml`
- `Makefile`
- `migrations/001_core_domain_model.sql`
- `src/lookout_mcp/**`
- `tests/**`
- `scripts/smoke.py`

Overall assessment: ready after this pass. The repository clearly presents
`docs/technical-spec.md` as the primary deliverable, keeps the implementation secondary, and proves
the MCP contract with deterministic local tests.

## Compliance Matrix

| Requirement | Source / rationale | Status | Evidence in repo | Gap | Recommended fix | Fixed in this pass |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Primary deliverable is a technical specification. | PDF Page 1: submitted artifact is one technical specification. | Met | `README.md`, `docs/technical-spec.md` overview. | None. | None. | No |
| 2. Spec includes data model/schema. | PDF Pages 1 and 7. | Met | `docs/technical-spec.md` Data Model and Schema. | None. | None. | No |
| 3. Spec includes relationships. | PDF Page 1 requires tables and relationships. | Met | Schema docs plus FK constraints in `migrations/001_core_domain_model.sql`. | None. | None. | No |
| 4. Spec includes ID formats. | PDF Page 7 emphasizes ID formats. | Met | `docs/technical-spec.md` ID Formats; `src/lookout_mcp/schemas.py`. | None. | None. | No |
| 5. Spec justifies schema choices. | PDF Page 1 requires justification for choices. | Met | SQLite/JSON/index rationale in spec and `docs/engineering-decisions.md`. | None. | None. | No |
| 6. Spec includes complete MCP tool surface. | PDF Page 1 requires every planned MCP tool. | Met | `docs/technical-spec.md` Complete Tool Contracts; `src/lookout_mcp/tools/registry.py`. | None. | None. | No |
| 7. Every tool has exact model-visible description. | PDF Page 1 and Page 7. | Met | Exact description table in spec matches `MODEL_VISIBLE_TOOL_DESCRIPTIONS`; `server.py` registers them. | None. | None. | Yes |
| 8. Every tool has inputs. | PDF Page 1. | Met | Per-tool Input sections in spec; Pydantic input models in registry. | None. | None. | Yes |
| 9. Every tool has outputs. | PDF Page 1. | Met | Per-tool Output shape sections in spec; output models in registry. | None. | None. | Yes |
| 10. Every tool has error modes. | PDF Page 1. | Met | Per-tool Common errors plus Error, Retry, and Rate-limit Strategy. | None. | None. | Yes |
| 11. Every tool has documentation notes. | PDF Page 1. | Met | `TOOL_REGISTRY` notes for all 15 tools; reflected in spec narrative. | None. | None. | No |
| 12. Every tool has at least one example call. | PDF Page 1. | Met | Per-tool examples in spec and `TOOL_REGISTRY`. | None. | None. | Yes |
| 13. Workflow mapping exists for W1-W8. | PDF Pages 6, 11, and 12. | Met | `docs/technical-spec.md` Workflow-to-tool Mapping now explicitly labels W1-W8. | Previous table was correct but did not label W1-W8. | Label each product workflow and map tool sequence. | Yes |
| 14. Pagination semantics are consistent. | PDF Pages 6 and 8. | Met | `normalize_list_page_size`, cursor helpers, Pagination Semantics docs. | None. | None. | No |
| 15. Filter semantics are consistent. | PDF Page 6 and BI workflow W3/W4. | Met | Filter and Sort Semantics docs; `_validate_query_spec`; render/view filters now share validation. | Render filters were missing. | Add render-time filter validation. | Yes |
| 16. Assumptions are explicit. | PDF Page 6. | Met | `docs/technical-spec.md` Assumptions. | None. | None. | No |
| 17. Implementation notes explain complex tool logic. | PDF Pages 6-8. | Met | Query Safety, Technical Implementation Notes, and Tool SQL/Filesystem Interactions. | SQL/files touched needed sharper coverage. | Add interaction map. | Yes |
| 18. Implementation notes explain SQL and filesystem interactions. | PDF Page 8 says each tool receives DB/FS and should describe what it touches. | Met | Tool SQL and Filesystem Interactions table. | Previous docs were too high level. | Add per-tool-area SQL/FS table. | Yes |
| 19. Export behavior is described. | PDF Page 8 and W8. | Met | Export tool docs, Query Safety, Tool SQL/Filesystem Interactions. | CSV header order was not protected in code. | Preserve first-row/model header order and test it. | Yes |
| 20. Open questions have reasoned positions. | PDF Page 12 asks about read-only failure modes. | Met | Open Questions and Positions; Position on Read-only Failure Modes. | Heading was less explicit. | Add explicit open-question section. | Yes |
| 21. Seed strategy is realistic. | PDF Page 12 target scale; product brief examples. | Met | Seed Data Strategy; `seed.py` creates 6 datasources, 36 workbooks, and 180 views, with five chart views per workbook. | Earlier seed shape had 36 workbooks but only 60 total views. | Expand focused analysis workbooks so every workbook sits within the brief's 4-12 chart range. | Yes |
| 22. Testing strategy explains what and why. | PDF Page 7. | Met | `docs/testing.md`, Testing Strategy in spec, pytest markers. | None. | None. | No |
| 23. Explicit tradeoffs are documented. | PDF Page 7. | Met | Explicit Tradeoffs and Intentionally Deferred Work. | None. | None. | No |
| 24. Offline operation is preserved. | PDF Page 7 technical context. | Met | No runtime external calls; README states no network/API keys; tests use temp DB/FS. | None. | None. | No |
| 25. SQLite is used for persistent state. | PDF Page 7 state backend. | Met | `db.py`, migration SQL, README architecture. | None. | None. | No |
| 26. No external runtime services are required. | PDF Page 7. | Met | Core commands use Python/SQLite/filesystem only. Optional UI is secondary. | None. | None. | No |
| 27. No real Tableau server is assumed. | Product brief: mock Tableau-style system. | Met | README/spec out-of-scope; no Tableau dependencies. | None. | None. | No |
| 28. No real data warehouse is assumed. | PDF Page 7. | Met | Structured synthetic query engine over seeded metadata. | None. | None. | No |
| 29. No auth/multi-tenancy is implemented unless out of scope. | PDF Page 12 non-goals. | Met | Out-of-scope sections; no auth code. | None. | None. | No |
| 30. No real-time updates are implemented. | PDF Page 12 non-goals. | Met | Static seed data; no subscriptions/watchers. | None. | None. | No |
| 31. No dashboard editing is implemented. | PDF Page 12 non-goals. | Met | Tool surface is read/filter/query/render/export only. | None. | None. | No |
| 32. Datasources are modeled. | Product brief core concepts. | Met | `datasources` table and `DatasourceRecord`. | None. | None. | No |
| 33. Datasource fields include metadata. | Product brief core concepts. | Met | `datasource_fields` table includes name, type, description, semantic role, operators. | None. | None. | No |
| 34. Workbooks are modeled. | Product brief core concepts. | Met | `workbooks` table and list/get tools. | None. | None. | No |
| 35. Views are modeled. | Product brief core concepts. | Met | `views` table with chart config, query spec, filters, visual config. | None. | None. | No |
| 36. Supported chart types are represented. | PDF Page 11: bar, pie, treemap, line, histogram. | Met | Schema `ChartType`, SQL CHECK, seed chart counts. | None. | None. | No |
| 37. W1 Explore Datasources works. | Product workflow W1. | Met | `search_content`, `list_datasources`, `get_datasource`, `get_field_values`; smoke script. | None. | None. | No |
| 38. W2 View Workbook Contents works. | Product workflow W2. | Met | `list_workbooks`, `get_workbook`, `list_views`, `get_view`; tests/smoke. | None. | None. | No |
| 39. W3 Apply Filters to Views works. | Product workflow W3. | Met | `get_view_data(filter_overrides=...)` and validation tests. | Invalid override fields were too permissive. | Validate overrides separately against real datasource fields. | Yes |
| 40. W4 Query Datasource works. | Product workflow W4. | Met | `query_datasource`; exports; structured query tests. | Raw SQL is intentionally unsupported. | Document and preserve `UNSUPPORTED_SQL`. | No |
| 41. W5 Compare Time Periods works. | Product workflow W5. | Met | `compare_periods` output includes totals/deltas/pct deltas; tests/smoke. | None. | None. | No |
| 42. W6 Analyze View Details works. | Product workflow W6. | Met | `get_view` returns chart/query config; `get_view_data` now returns values plus compact summary statistics. | View data lacked explicit summary stats. | Add preview-based numeric summary statistics. | Yes |
| 43. W7 Generate View Images works. | Product workflow W7. | Met | `render_view_image`, `render_workbook_image`, SVG artifacts under `LOOKOUT_FS_ROOT`; smoke. | `render_view_image` lacked filter overrides. SVG-only render is a documented tradeoff. | Add `filter_overrides` and validation. | Yes |
| 44. W8 Export View Data works. | Product workflow W8. | Met | `export_view_data`, `export_query_result`, artifact tests. | CSV headers were sorted rather than preserving model/row order. | Preserve first-row header order and test. | Yes |
| 45. Tool outputs are bounded and token-conscious. | PDF evaluation: token consumption. | Met | Page cap 25, preview cap 1000, exports for larger results. | None. | None. | No |
| 46. List/get split is implemented or clearly specified. | PDF Page 8 patterns. | Met | list/get tools for datasources, workbooks, views. | None. | None. | No |
| 47. Pagination prevents large dumps. | PDF Pages 6 and 8. | Met | Cursor pagination and page limits. | None. | None. | No |
| 48. Query preview limits are enforced. | PDF evaluation: token budget. | Met | `normalize_query_preview_limit`; `LIMIT_EXCEEDED` tests. | None. | None. | No |
| 49. Large outputs use files/exports instead of inline dumps. | PDF Page 9 avoids bulk dumps. | Met | Export/render tools return artifact metadata, not contents. | None. | None. | No |
| 50. Error envelope is consistent. | PDF Pages 4 and 6. | Met | `error_envelope`, edge tests assert shape. | None. | None. | No |
| 51. Error messages are actionable for agents. | PDF Page 9 avoids silent failures. | Met | Suggestions for field errors, retry guidance in docs. | None. | None. | No |
| 52. Source-offline/cache-stale failure modes are addressed. | PDF Page 12 open question. | Met | `status`, `SOURCE_UNAVAILABLE`, `CACHE_STALE`, `SOURCE_DEGRADED`; tests. | None. | None. | No |
| 53. Timeouts or runaway query protections exist. | Evaluation criteria: timeouts/unexpected inputs. | Met | Structured query limits, preview caps, deterministic `QUERY_TIMEOUT`, no raw SQL engine. | Timeout is simulated because queries are synthetic. | Document as deliberate mock behavior. | No |
| 54. Rate limiting/throttling or equivalent runaway protection is discussed/implemented. | Evaluation criteria: protocols/rate limiting. | Met | `_ExpensiveOperationGuard`, `RATE_LIMITED`, docs. | None. | None. | No |
| 55. Tests cover normal and edge cases. | PDF Page 7 testing strategy. | Met | Unit/integration/golden/edge tests; smoke. | None. | None. | Yes |
| 56. README can onboard a fresh evaluator. | Final packaging prompt and assignment intent. | Met | Clean checkout setup, architecture, commands, limitations, interview notes. | None. | None. | No |
| 57. Clean-checkout setup commands are accurate. | Evaluator should run locally. | Met | `Makefile`, README, `.env.example`. | Pending final command run at time of writing. | Run final command suite. | No |
| 58. Smoke test exists or manual verification steps exist. | Integration requirement. | Met | `scripts/smoke.py`, `make smoke`, `docs/testing.md`. | Smoke did not cover render filters. | Add filtered render call. | Yes |
| 59. Implementation aligns with documentation. | Submission coherence. | Met | Registry/docs/code cross-check; updated specs for new contract details. | Render filters and summaries needed alignment. | Update code, tests, README, spec. | Yes |
| 60. Submission is coherent and interview-ready. | Evaluation favors judgment over volume. | Met | Spec-first framing, engineering decisions, tradeoffs, final checklist. | Main residual risk is synthetic behavior scope, now clearly documented. | Keep limitations explicit. | Yes |
| 61. Seeded dashboards match target chart density. | PDF Page 12 scale says 30-80 dashboards, each with 4-12 charts. | Met | Tests assert every workbook has between 4 and 12 views; seed currently creates 36 workbooks with 5 views each. | Previous seed data had focused one-view analysis workbooks. | Populate supporting context views in every focused analysis workbook. | Yes |

## Findings Fixed in This Pass

- Added validated `filter_overrides` to `render_view_image`, including MCP server registration,
  registry schema, docs, demo UI adapter support, smoke coverage, and backend tests.
- Added compact `summary_statistics` to `get_view_data` so W6 can retrieve values and numeric
  summaries without dumping large datasets.
- Tightened `get_view_data` filter override validation so invalid override fields return
  `FIELD_NOT_FOUND` instead of being treated as virtual saved-view filters.
- Changed CSV export headers to preserve first-row/model order instead of sorting field names.
- Made W1-W8 explicit in the workflow mapping.
- Added an explicit open-question position section and a SQL/filesystem interaction map.
- Expanded seed data from 60 to 180 views so all 36 seeded workbooks contain five chart views,
  matching the target dashboard/chart-density range.

## Residual Risks and Limitations

- Rendering is deterministic SVG only. The product brief allows PNG/SVG; SVG proves the artifact
  workflow without adding image-rendering dependencies. This should be framed as an explicit
  tradeoff in the interview.
- Query execution is synthetic and deterministic, not a SQL engine over warehouse rows. This is
  appropriate for the spec-first mock, but it is not production BI execution.
- `QUERY_TIMEOUT` is simulated through input validation because there is no real long-running
  warehouse query path.
- The optional UI is a helpful inspection aid but not the evaluated surface. It should not be
  allowed to dominate the submission discussion.
- The implementation supports the target catalog scale, but exported row content is bounded by the
  offline mock cap rather than materializing 100,000 full rows.

## Verification Log

Commands run so far:

| Command | Result | Notes |
| --- | --- | --- |
| `pdftotext HandshakeInstructions.pdf -` | Completed, no text extracted | PDF is image-only; OCR was required. |
| `tesseract docs/Page*.png stdout --psm 6` | Passed | OCR confirmed assignment requirements. |
| `.venv/bin/python -m pytest tests/test_backend_api.py tests/test_contract_edges.py -q` | Passed | 24 targeted backend/edge tests passed after fixes. |
| Registry introspection script | Passed | 15 core tools, descriptions present, notes/examples present. |
| Seed-count introspection script | Passed | 6 datasources, 48 fields, 36 workbooks, 180 views, 5 views per workbook, all 5 chart types covered. |
| `make lint` | Passed | Ruff reported all checks passed. |
| `make typecheck` | Failed, then passed | Initial failure was a mypy-only type mismatch in the new render-filter helper; fixed by converting override payloads to `QueryFilter` models. Final run: no issues in 19 source files. |
| `make test` | Passed | 53 tests passed; coverage reported 82% overall. |
| `make smoke` | Passed | Exercised discovery, workbook/view inspection, filtered view data, structured query, export, compare, filtered render, source-offline error, stale-cache warning, and field suggestions. |
| `make lint` final rerun | Passed | Ruff reported all checks passed after the seed-density change. |
| `make typecheck` final rerun | Passed | Mypy reported no issues in 19 source files after the seed-density change. |
| `make test` final rerun | Passed | 53 tests passed after the seed-density change. |
| `make smoke` final rerun | Passed | Filtered render, export, stale-cache, source-offline, and field-suggestion workflows pass after the seed-density change. |

Final verification commands for a local evaluator:

```bash
make lint
make typecheck
make test
make smoke
```
