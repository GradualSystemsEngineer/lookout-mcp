"""Model-visible tool registry for the Lookout MCP surface."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from lookout_mcp.schemas import StrictModel
from lookout_mcp.tools.workflow import (
    LIST_DEFAULT_PAGE_SIZE,
    LIST_MAX_PAGE_SIZE,
    QUERY_PREVIEW_DEFAULT_ROWS,
    QUERY_PREVIEW_MAX_ROWS,
    CompactListOutput,
    QueryPreviewOutput,
)

ContentType = Literal["datasource", "workbook", "view", "field"]
ExportFormat = Literal["csv", "json"]


class ToolExample(StrictModel):
    description: str
    input: dict[str, object]


class ToolDefinition(StrictModel):
    name: str
    description: str
    input_model: str
    output_model: str
    common_errors: list[str]
    notes: list[str]
    examples: list[ToolExample]


class CursorPageInput(StrictModel):
    page_size: int | None = Field(
        default=None,
        description=(
            f"Optional page size. Defaults to {LIST_DEFAULT_PAGE_SIZE}; "
            f"maximum {LIST_MAX_PAGE_SIZE}."
        ),
    )
    cursor: str | None = Field(
        default=None,
        description="Opaque cursor returned by a previous page for the same filters and sort.",
    )


class SearchContentInput(CursorPageInput):
    query: str = Field(
        description="Search text for names, titles, descriptions, tags, field names, or IDs."
    )
    content_types: list[ContentType] | None = Field(
        default=None,
        description=(
            "Optional content types to search. Omit to search datasources, workbooks, "
            "views, and fields."
        ),
    )


class ListDatasourcesInput(CursorPageInput):
    status: str | None = None
    theme: str | None = None
    query: str | None = Field(
        default=None, description="Optional fuzzy filter over name, label, tags, or ID."
    )


class GetDatasourceInput(StrictModel):
    datasource: str = Field(description="Datasource ID or unambiguous datasource name/label.")
    include_fields: bool = Field(
        default=True, description="Include compact datasource field metadata."
    )


class GetFieldValuesInput(CursorPageInput):
    datasource: str = Field(description="Datasource ID or unambiguous datasource name/label.")
    field: str = Field(description="Field ID, name, or label.")
    search: str | None = Field(
        default=None, description="Optional prefix or contains search over values."
    )


class ListWorkbooksInput(CursorPageInput):
    project: str | None = None
    datasource: str | None = Field(
        default=None, description="Optional datasource ID/name to constrain results."
    )
    query: str | None = Field(
        default=None, description="Optional fuzzy filter over title, description, tags, or ID."
    )


class GetWorkbookInput(StrictModel):
    workbook: str = Field(description="Workbook ID or unambiguous workbook name/title.")
    include_views: bool = Field(default=True, description="Include compact view metadata.")


class ListViewsInput(CursorPageInput):
    workbook: str | None = Field(default=None, description="Optional workbook ID/name/title.")
    datasource: str | None = Field(default=None, description="Optional datasource ID/name/label.")
    chart_type: str | None = None
    query: str | None = Field(
        default=None,
        description="Optional fuzzy filter over title, description, tags, field names, or ID.",
    )


class GetViewInput(StrictModel):
    view: str = Field(description="View ID or unambiguous view name/title.")
    include_query_spec: bool = Field(
        default=True, description="Include the saved structured query spec."
    )


class GetViewDataInput(StrictModel):
    view: str = Field(description="View ID or unambiguous view name/title.")
    filter_overrides: dict[str, object] | list[dict[str, object]] = Field(
        default_factory=dict,
        description=(
            "Optional filters to add to the saved view query. A dict is treated as "
            "field=value equality filters; a list may use structured filter objects."
        ),
    )
    preview_limit: int | None = Field(
        default=None,
        description=(
            f"Inline row preview limit. Defaults to {QUERY_PREVIEW_DEFAULT_ROWS}; "
            f"maximum {QUERY_PREVIEW_MAX_ROWS}. Use export_view_data for more rows."
        ),
    )


class QueryDatasourceInput(StrictModel):
    datasource: str = Field(description="Datasource ID or unambiguous datasource name/label.")
    query_spec: dict[str, object] = Field(
        description="Structured query spec using validated field names."
    )
    preview_limit: int | None = Field(
        default=None,
        description=(
            f"Inline row preview limit. Defaults to {QUERY_PREVIEW_DEFAULT_ROWS}; "
            f"maximum {QUERY_PREVIEW_MAX_ROWS}. Use export_query_result for more rows."
        ),
    )


class ComparePeriodsInput(StrictModel):
    datasource: str = Field(description="Datasource ID or unambiguous datasource name/label.")
    metric: str = Field(description="Measure field ID, name, or label.")
    period_field: str = Field(description="Temporal field ID, name, or label.")
    current_period: dict[str, object]
    comparison_period: dict[str, object]
    dimensions: list[str] = Field(default_factory=list)
    preview_limit: int | None = Field(
        default=None,
        description=(
            f"Defaults to {QUERY_PREVIEW_DEFAULT_ROWS}; maximum {QUERY_PREVIEW_MAX_ROWS}."
        ),
    )


class RenderViewImageInput(StrictModel):
    view: str = Field(description="View ID or unambiguous view name/title.")
    filter_overrides: dict[str, object] | list[dict[str, object]] = Field(
        default_factory=dict,
        description=(
            "Optional render-time filters. A dict is treated as field=value equality filters; "
            "a list may use structured filter objects."
        ),
    )
    width: int = Field(default=1200, gt=0)
    height: int = Field(default=800, gt=0)


class RenderWorkbookImageInput(StrictModel):
    workbook: str = Field(description="Workbook ID or unambiguous workbook name/title.")
    width: int = Field(default=1440, gt=0)
    height: int = Field(default=960, gt=0)


class ExportViewDataInput(StrictModel):
    view: str = Field(description="View ID or unambiguous view name/title.")
    format: ExportFormat = "csv"


class ExportQueryResultInput(StrictModel):
    query_result_id: str = Field(
        description="Query result ID returned by query_datasource or get_view_data."
    )
    format: ExportFormat = "csv"


class SearchContentOutput(CompactListOutput):
    pass


class DatasourceListOutput(CompactListOutput):
    pass


class DatasourceDetailOutput(StrictModel):
    datasource: dict[str, object]
    fields: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[dict[str, object]] = Field(default_factory=list)


class FieldValuesOutput(CompactListOutput):
    pass


class WorkbookListOutput(CompactListOutput):
    pass


class WorkbookDetailOutput(StrictModel):
    workbook: dict[str, object]
    views: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[dict[str, object]] = Field(default_factory=list)


class ViewListOutput(CompactListOutput):
    pass


class ViewDetailOutput(StrictModel):
    view: dict[str, object]
    warnings: list[dict[str, object]] = Field(default_factory=list)


class ViewDataOutput(QueryPreviewOutput):
    query_result_id: str | None = None
    summary_statistics: dict[str, object] = Field(default_factory=dict)


class QueryDatasourceOutput(QueryPreviewOutput):
    query_result_id: str


class ComparePeriodsOutput(QueryPreviewOutput):
    comparison: dict[str, object]


class RenderArtifactOutput(StrictModel):
    render_id: str
    artifact_path: str
    width: int
    height: int
    status: str
    warnings: list[dict[str, object]] = Field(default_factory=list)


class ExportArtifactOutput(StrictModel):
    export_id: str
    artifact_path: str
    format: ExportFormat
    row_count: int
    status: str
    warnings: list[dict[str, object]] = Field(default_factory=list)


COMMON_DISCOVERY_ERRORS = [
    "PAGE_SIZE_TOO_LARGE",
    "INVALID_CURSOR",
    "AMBIGUOUS_MATCH",
]
COMMON_GET_ERRORS = [
    "NOT_FOUND",
    "AMBIGUOUS_MATCH",
]
COMMON_QUERY_ERRORS = [
    "INVALID_INPUT",
    "INVALID_FILTER",
    "INVALID_SORT",
    "NOT_FOUND",
    "FIELD_NOT_FOUND",
    "AMBIGUOUS_MATCH",
    "LIMIT_EXCEEDED",
    "QUERY_TIMEOUT",
    "SOURCE_UNAVAILABLE",
]
COMMON_RENDER_ERRORS = [
    "INVALID_INPUT",
    "INVALID_FILTER",
    "FIELD_NOT_FOUND",
    "NOT_FOUND",
    "AMBIGUOUS_MATCH",
    "LIMIT_EXCEEDED",
    "RENDER_FAILED",
    "RATE_LIMITED",
]
COMMON_EXPORT_ERRORS = [
    "INVALID_INPUT",
    "NOT_FOUND",
    "AMBIGUOUS_MATCH",
    "LIMIT_EXCEEDED",
    "EXPORT_FAILED",
    "RATE_LIMITED",
]

MODEL_VISIBLE_TOOL_DESCRIPTIONS: dict[str, str] = {
    "search_content": (
        "Search Lookout BI content across datasources, workbooks, views, and fields. "
        "Returns compact paginated matches only; use get tools for details."
    ),
    "list_datasources": (
        "List datasource metadata in compact pages. Use filters to narrow results; "
        "page size defaults to 10 and is capped at 25."
    ),
    "get_datasource": (
        "Get one datasource by ID or unambiguous name, including field metadata and "
        "status warnings."
    ),
    "get_field_values": (
        "List representative values for one datasource field in compact paginated form. "
        "Use search to narrow high-cardinality fields."
    ),
    "list_workbooks": (
        "List workbook metadata in compact pages, optionally filtered by project, "
        "datasource, or fuzzy query."
    ),
    "get_workbook": (
        "Get one workbook by ID or unambiguous title, including compact view metadata."
    ),
    "list_views": (
        "List view metadata in compact pages, optionally filtered by workbook, datasource, "
        "chart type, or fuzzy query."
    ),
    "get_view": (
        "Get one view by ID or unambiguous title, including chart configuration and saved "
        "query specification."
    ),
    "get_view_data": (
        "Run the saved query for one view, optionally adding filter overrides, and return "
        "a bounded row preview with compact summary statistics. Large results must be exported "
        "with export_view_data."
    ),
    "query_datasource": (
        "Run a structured query against one datasource and return a bounded row preview "
        "plus a query_result_id for export."
    ),
    "compare_periods": (
        "Compare one metric across current and comparison periods, returning bounded "
        "preview rows and summary deltas."
    ),
    "render_view_image": (
        "Render one view to a local image artifact under LOOKOUT_FS_ROOT and return "
        "artifact metadata, not inline image bytes. Use filter_overrides to render a filtered "
        "variant without changing the saved view."
    ),
    "render_workbook_image": (
        "Render one workbook dashboard to a local image artifact under LOOKOUT_FS_ROOT "
        "and return artifact metadata, not inline image bytes."
    ),
    "export_view_data": (
        "Export the rows behind one view to a local file under LOOKOUT_FS_ROOT. Use this "
        "instead of requesting large inline row sets."
    ),
    "export_query_result": (
        "Export a prior query result to a local file under LOOKOUT_FS_ROOT. Use this for "
        "rows beyond the preview limit."
    ),
}


def _definition(
    *,
    name: str,
    input_model: type[StrictModel],
    output_model: type[StrictModel],
    common_errors: list[str],
    notes: list[str],
    examples: list[ToolExample],
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS[name],
        input_model=input_model.__name__,
        output_model=output_model.__name__,
        common_errors=common_errors,
        notes=notes,
        examples=examples,
    )


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "search_content": _definition(
        name="search_content",
        input_model=SearchContentInput,
        output_model=SearchContentOutput,
        common_errors=COMMON_DISCOVERY_ERRORS,
        notes=[
            "Search returns candidates, not full records.",
            "Resolve ambiguous targets by passing an explicit ID to get tools.",
        ],
        examples=[
            ToolExample(
                description="Find revenue dashboards.",
                input={"query": "revenue dashboard", "content_types": ["workbook", "view"]},
            )
        ],
    ),
    "list_datasources": _definition(
        name="list_datasources",
        input_model=ListDatasourcesInput,
        output_model=DatasourceListOutput,
        common_errors=COMMON_DISCOVERY_ERRORS,
        notes=[
            "Compact items omit field lists and default filters.",
            "Use get_datasource for full datasource details.",
        ],
        examples=[
            ToolExample(
                description="List stale datasource metadata.", input={"status": "cache_stale"}
            )
        ],
    ),
    "get_datasource": _definition(
        name="get_datasource",
        input_model=GetDatasourceInput,
        output_model=DatasourceDetailOutput,
        common_errors=COMMON_GET_ERRORS,
        notes=[
            "Returns CACHE_STALE or SOURCE_DEGRADED warnings when simulated status requires it."
        ],
        examples=[
            ToolExample(
                description="Inspect a datasource and its fields.",
                input={"datasource": "Retail Sales"},
            )
        ],
    ),
    "get_field_values": _definition(
        name="get_field_values",
        input_model=GetFieldValuesInput,
        output_model=FieldValuesOutput,
        common_errors=COMMON_DISCOVERY_ERRORS + ["NOT_FOUND"],
        notes=[
            "Values are representative and paginated; never request unbounded cardinality dumps."
        ],
        examples=[
            ToolExample(
                description="Sample region values.",
                input={"datasource": "Retail Sales", "field": "region"},
            )
        ],
    ),
    "list_workbooks": _definition(
        name="list_workbooks",
        input_model=ListWorkbooksInput,
        output_model=WorkbookListOutput,
        common_errors=COMMON_DISCOVERY_ERRORS,
        notes=["Compact items are intended for discovery before get_workbook."],
        examples=[
            ToolExample(
                description="List executive dashboards.", input={"project": "Executive Dashboards"}
            )
        ],
    ),
    "get_workbook": _definition(
        name="get_workbook",
        input_model=GetWorkbookInput,
        output_model=WorkbookDetailOutput,
        common_errors=COMMON_GET_ERRORS,
        notes=["Includes compact view metadata by default."],
        examples=[
            ToolExample(
                description="Inspect an executive dashboard.",
                input={"workbook": "Retail Sales Executive Dashboard"},
            )
        ],
    ),
    "list_views": _definition(
        name="list_views",
        input_model=ListViewsInput,
        output_model=ViewListOutput,
        common_errors=COMMON_DISCOVERY_ERRORS,
        notes=["Use get_view for chart config, query spec, and full metadata."],
        examples=[
            ToolExample(
                description="Find line views for a datasource.",
                input={"datasource": "Retail Sales", "chart_type": "line"},
            )
        ],
    ),
    "get_view": _definition(
        name="get_view",
        input_model=GetViewInput,
        output_model=ViewDetailOutput,
        common_errors=COMMON_GET_ERRORS,
        notes=["Returns the saved structured query spec; it does not run the query."],
        examples=[
            ToolExample(description="Inspect a view.", input={"view": "Q1 Revenue by Region"})
        ],
    ),
    "get_view_data": _definition(
        name="get_view_data",
        input_model=GetViewDataInput,
        output_model=ViewDataOutput,
        common_errors=COMMON_QUERY_ERRORS,
        notes=[
            "Inline rows are previews only and are capped at 1,000.",
            "Use export_view_data for large row sets.",
        ],
        examples=[
            ToolExample(
                description="Preview saved view data.",
                input={"view": "Q1 Revenue by Region", "preview_limit": 100},
            ),
            ToolExample(
                description="Preview saved view data with a filter override.",
                input={
                    "view": "Q1 Revenue by Region",
                    "filter_overrides": {"region": "Northeast"},
                    "preview_limit": 100,
                },
            ),
        ],
    ),
    "query_datasource": _definition(
        name="query_datasource",
        input_model=QueryDatasourceInput,
        output_model=QueryDatasourceOutput,
        common_errors=COMMON_QUERY_ERRORS,
        notes=[
            "Structured query specs are validated against field metadata.",
            "No raw unbounded row dumps are returned.",
        ],
        examples=[
            ToolExample(
                description="Aggregate revenue by region.",
                input={
                    "datasource": "Retail Sales",
                    "query_spec": {
                        "operation": "aggregate",
                        "group_by": ["region"],
                        "metrics": [{"field": "revenue", "aggregation": "sum"}],
                    },
                },
            )
        ],
    ),
    "compare_periods": _definition(
        name="compare_periods",
        input_model=ComparePeriodsInput,
        output_model=ComparePeriodsOutput,
        common_errors=COMMON_QUERY_ERRORS,
        notes=["Comparison output includes summary deltas plus bounded preview rows."],
        examples=[
            ToolExample(
                description="Compare current quarter revenue.",
                input={
                    "datasource": "Retail Sales",
                    "metric": "revenue",
                    "period_field": "order_date",
                    "current_period": {"quarter": "Q1"},
                    "comparison_period": {"quarter": "Q4"},
                },
            )
        ],
    ),
    "render_view_image": _definition(
        name="render_view_image",
        input_model=RenderViewImageInput,
        output_model=RenderArtifactOutput,
        common_errors=COMMON_RENDER_ERRORS,
        notes=[
            "Returns artifact metadata and a path relative to LOOKOUT_FS_ROOT.",
            "Never returns inline image bytes.",
            "Render-time filters are validated with the same field/operator rules as view data.",
        ],
        examples=[
            ToolExample(
                description="Render a view.",
                input={"view": "Q1 Revenue by Region", "width": 1200, "height": 800},
            ),
            ToolExample(
                description="Render a filtered view variant.",
                input={
                    "view": "Q1 Revenue by Region",
                    "filter_overrides": {"region": "Northeast"},
                    "width": 1200,
                    "height": 800,
                },
            )
        ],
    ),
    "render_workbook_image": _definition(
        name="render_workbook_image",
        input_model=RenderWorkbookImageInput,
        output_model=RenderArtifactOutput,
        common_errors=[
            error
            for error in COMMON_RENDER_ERRORS
            if error not in {"INVALID_FILTER", "FIELD_NOT_FOUND"}
        ],
        notes=[
            "Returns artifact metadata and a path relative to LOOKOUT_FS_ROOT.",
            "Never returns inline image bytes.",
        ],
        examples=[
            ToolExample(
                description="Render a dashboard.",
                input={
                    "workbook": "Retail Sales Executive Dashboard",
                    "width": 1440,
                    "height": 960,
                },
            )
        ],
    ),
    "export_view_data": _definition(
        name="export_view_data",
        input_model=ExportViewDataInput,
        output_model=ExportArtifactOutput,
        common_errors=COMMON_EXPORT_ERRORS,
        notes=["Exports large row sets to a local artifact instead of returning rows inline."],
        examples=[
            ToolExample(
                description="Export view data as CSV.",
                input={"view": "Pipeline Health by Stage", "format": "csv"},
            )
        ],
    ),
    "export_query_result": _definition(
        name="export_query_result",
        input_model=ExportQueryResultInput,
        output_model=ExportArtifactOutput,
        common_errors=COMMON_EXPORT_ERRORS,
        notes=["Use the query_result_id returned by query_datasource or get_view_data."],
        examples=[
            ToolExample(
                description="Export a previous query result.",
                input={"query_result_id": "run_0123abcdef89", "format": "csv"},
            )
        ],
    ),
}
