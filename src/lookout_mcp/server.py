"""MCP server entrypoint for Lookout."""

from __future__ import annotations

from typing import Any

from lookout_mcp.config import LookoutConfig, load_config
from lookout_mcp.schemas import HealthCheckResult
from lookout_mcp.tools import api
from lookout_mcp.tools.registry import MODEL_VISIBLE_TOOL_DESCRIPTIONS


def health_check(config: LookoutConfig | None = None) -> dict[str, Any]:
    """Return a local smoke-check payload for tests and MCP clients."""

    loaded = load_config() if config is None else config
    loaded.ensure_filesystem_root()
    return HealthCheckResult(
        status="ok",
        service="lookout-mcp",
        db_path=loaded.db_path,
        fs_root=loaded.fs_root,
        log_level=loaded.log_level,
    ).model_dump(mode="json")


def create_mcp_server() -> Any:
    """Create the FastMCP server with bootstrap tools registered."""

    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("lookout")

    @mcp.tool(
        name="health_check",
        description="Return local Lookout service status and resolved configuration paths.",
    )
    def _health_check() -> dict[str, Any]:
        return health_check()

    @mcp.tool(name="search_content", description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["search_content"])
    def _search_content(
        query: str,
        content_types: list[str] | None = None,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return api.search_content(
            query=query,
            content_types=content_types,
            page_size=page_size,
            cursor=cursor,
        )

    @mcp.tool(
        name="list_datasources",
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["list_datasources"],
    )
    def _list_datasources(
        status: str | None = None,
        theme: str | None = None,
        query: str | None = None,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return api.list_datasources(
            status=status,
            theme=theme,
            query=query,
            page_size=page_size,
            cursor=cursor,
        )

    @mcp.tool(name="get_datasource", description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["get_datasource"])
    def _get_datasource(datasource: str, include_fields: bool = True) -> dict[str, Any]:
        return api.get_datasource(datasource=datasource, include_fields=include_fields)

    @mcp.tool(
        name="get_field_values",
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["get_field_values"],
    )
    def _get_field_values(
        datasource: str,
        field: str,
        search: str | None = None,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return api.get_field_values(
            datasource=datasource,
            field=field,
            search=search,
            page_size=page_size,
            cursor=cursor,
        )

    @mcp.tool(name="list_workbooks", description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["list_workbooks"])
    def _list_workbooks(
        project: str | None = None,
        datasource: str | None = None,
        query: str | None = None,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return api.list_workbooks(
            project=project,
            datasource=datasource,
            query=query,
            page_size=page_size,
            cursor=cursor,
        )

    @mcp.tool(name="get_workbook", description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["get_workbook"])
    def _get_workbook(workbook: str, include_views: bool = True) -> dict[str, Any]:
        return api.get_workbook(workbook=workbook, include_views=include_views)

    @mcp.tool(name="list_views", description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["list_views"])
    def _list_views(
        workbook: str | None = None,
        datasource: str | None = None,
        chart_type: str | None = None,
        query: str | None = None,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return api.list_views(
            workbook=workbook,
            datasource=datasource,
            chart_type=chart_type,
            query=query,
            page_size=page_size,
            cursor=cursor,
        )

    @mcp.tool(name="get_view", description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["get_view"])
    def _get_view(view: str, include_query_spec: bool = True) -> dict[str, Any]:
        return api.get_view(view=view, include_query_spec=include_query_spec)

    @mcp.tool(name="get_view_data", description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["get_view_data"])
    def _get_view_data(view: str, preview_limit: int | None = None) -> dict[str, Any]:
        return api.get_view_data(view=view, preview_limit=preview_limit)

    @mcp.tool(
        name="query_datasource",
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["query_datasource"],
    )
    def _query_datasource(
        datasource: str,
        query_spec: dict[str, object],
        preview_limit: int | None = None,
    ) -> dict[str, Any]:
        return api.query_datasource(
            datasource=datasource,
            query_spec=query_spec,
            preview_limit=preview_limit,
        )

    @mcp.tool(
        name="compare_periods",
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["compare_periods"],
    )
    def _compare_periods(
        datasource: str,
        metric: str,
        period_field: str,
        current_period: dict[str, object],
        comparison_period: dict[str, object],
        dimensions: list[str] | None = None,
        preview_limit: int | None = None,
    ) -> dict[str, Any]:
        return api.compare_periods(
            datasource=datasource,
            metric=metric,
            period_field=period_field,
            current_period=current_period,
            comparison_period=comparison_period,
            dimensions=dimensions or [],
            preview_limit=preview_limit,
        )

    @mcp.tool(
        name="render_view_image",
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["render_view_image"],
    )
    def _render_view_image(view: str, width: int = 1200, height: int = 800) -> dict[str, Any]:
        return api.render_view_image(view=view, width=width, height=height)

    @mcp.tool(
        name="render_workbook_image",
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["render_workbook_image"],
    )
    def _render_workbook_image(
        workbook: str,
        width: int = 1440,
        height: int = 960,
    ) -> dict[str, Any]:
        return api.render_workbook_image(workbook=workbook, width=width, height=height)

    @mcp.tool(
        name="export_view_data",
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["export_view_data"],
    )
    def _export_view_data(view: str, format: str = "csv") -> dict[str, Any]:
        return api.export_view_data(view=view, format=format)

    @mcp.tool(
        name="export_query_result",
        description=MODEL_VISIBLE_TOOL_DESCRIPTIONS["export_query_result"],
    )
    def _export_query_result(query_result_id: str, format: str = "csv") -> dict[str, Any]:
        return api.export_query_result(query_result_id=query_result_id, format=format)

    return mcp


def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
