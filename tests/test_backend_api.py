from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lookout_mcp.config import LookoutConfig
from lookout_mcp.db import seed
from lookout_mcp.server import create_mcp_server
from lookout_mcp.tools import api


def _config(tmp_path: Path) -> LookoutConfig:
    config = LookoutConfig(
        db_path=tmp_path / "lookout.sqlite3",
        fs_root=tmp_path / "var",
        log_level="INFO",
    )
    seed(config)
    return config


def _assert_ok(result: dict[str, Any]) -> dict[str, Any]:
    assert "error" not in result
    return result


@pytest.mark.integration
def test_mcp_server_registers_backend_tools() -> None:
    server = create_mcp_server()

    assert server is not None


@pytest.mark.integration
def test_discovery_and_metadata_tools_succeed_against_seeded_data(tmp_path: Path) -> None:
    config = _config(tmp_path)

    search = _assert_ok(api.search_content(query="revenue", _config=config))
    datasources = _assert_ok(api.list_datasources(page_size=2, _config=config))
    next_page = _assert_ok(api.list_datasources(cursor=datasources["next_cursor"], _config=config))
    datasource = _assert_ok(api.get_datasource(datasource="Retail Sales", _config=config))
    values = _assert_ok(
        api.get_field_values(datasource="Retail Sales", field="region", _config=config)
    )
    workbooks = _assert_ok(api.list_workbooks(datasource="Retail Sales", _config=config))
    workbook = _assert_ok(
        api.get_workbook(workbook="Retail Sales Executive Dashboard", _config=config)
    )
    views = _assert_ok(api.list_views(datasource="Retail Sales", chart_type="bar", _config=config))
    view = _assert_ok(api.get_view(view="Q1 Revenue by Region", _config=config))

    assert search["returned_row_count"] > 0
    assert datasources["returned_row_count"] == 2
    assert datasources["next_cursor"]
    assert next_page["returned_row_count"] == 4
    assert datasource["datasource"]["label"] == "Retail Sales"
    assert len(datasource["fields"]) == 8
    assert [item["value"] for item in values["items"]][:2] == ["Northeast", "Southeast"]
    assert workbooks["returned_row_count"] == 6
    assert workbook["views"]
    assert views["items"][0]["chart_type"] == "bar"
    assert view["view"]["title"] == "Q1 Revenue by Region"


@pytest.mark.integration
def test_query_tools_return_bounded_previews_and_warnings(tmp_path: Path) -> None:
    config = _config(tmp_path)

    stale = _assert_ok(api.get_datasource(datasource="Store Performance", _config=config))
    view_data = _assert_ok(
        api.get_view_data(
            view="Top Stores by Same-store Growth",
            preview_limit=2,
            _config=config,
        )
    )
    query = _assert_ok(
        api.query_datasource(
            datasource="Retail Sales",
            query_spec={
                "group_by": ["region"],
                "metrics": [{"field": "revenue", "aggregation": "sum"}],
                "order_by": [{"field": "revenue", "direction": "desc"}],
            },
            preview_limit=2,
            _config=config,
        )
    )
    comparison = _assert_ok(
        api.compare_periods(
            datasource="Retail Sales",
            metric="revenue",
            period_field="order_date",
            current_period={"quarter": "Q1"},
            comparison_period={"quarter": "Q4"},
            dimensions=["region"],
            preview_limit=2,
            _config=config,
        )
    )

    assert stale["warnings"][0]["code"] == "CACHE_STALE"
    assert view_data["returned_row_count"] == 2
    assert view_data["warnings"][0]["code"] == "CACHE_STALE"
    assert query["returned_row_count"] == 2
    assert query["truncated"] is True
    assert query["warnings"][0]["code"] == "RESULT_TRUNCATED"
    assert query["query_result_id"].startswith("run_")
    assert comparison["comparison"]["metric"] == "revenue"
    assert comparison["returned_row_count"] == 2


@pytest.mark.integration
def test_tool_errors_use_standard_envelope(tmp_path: Path) -> None:
    config = _config(tmp_path)

    too_large_page = api.list_datasources(page_size=26, _config=config)
    bad_filter = api.query_datasource(
        datasource="Retail Sales",
        query_spec={"filters": [{"field": "missing", "operator": "eq", "value": "x"}]},
        _config=config,
    )
    source_offline = api.query_datasource(
        datasource="Marketing Spend",
        query_spec={"group_by": ["channel"], "metrics": [{"field": "spend"}]},
        _config=config,
    )
    limit = api.query_datasource(
        datasource="Retail Sales",
        query_spec={"group_by": ["region"], "metrics": [{"field": "revenue"}], "limit": 1001},
        _config=config,
    )
    timeout = api.query_datasource(
        datasource="Retail Sales",
        query_spec={"group_by": ["region"], "metrics": [{"field": "revenue"}], "timeout_ms": 0},
        _config=config,
    )

    assert too_large_page["error"]["code"] == "PAGE_SIZE_TOO_LARGE"
    assert bad_filter["error"]["code"] == "INVALID_FILTER"
    assert source_offline["error"]["code"] == "SOURCE_UNAVAILABLE"
    assert limit["error"]["code"] == "LIMIT_EXCEEDED"
    assert timeout["error"]["code"] == "QUERY_TIMEOUT"


@pytest.mark.integration
def test_render_and_export_tools_create_files_under_filesystem_root(tmp_path: Path) -> None:
    config = _config(tmp_path)

    render_view = _assert_ok(
        api.render_view_image(view="Q1 Revenue by Region", width=640, height=360, _config=config)
    )
    render_workbook = _assert_ok(
        api.render_workbook_image(
            workbook="Retail Sales Executive Dashboard",
            width=800,
            height=600,
            _config=config,
        )
    )
    query = _assert_ok(
        api.query_datasource(
            datasource="Retail Sales",
            query_spec={"group_by": ["region"], "metrics": [{"field": "revenue"}]},
            _config=config,
        )
    )
    export_query = _assert_ok(
        api.export_query_result(query_result_id=query["query_result_id"], _config=config)
    )
    export_view = _assert_ok(
        api.export_view_data(view="Q1 Revenue by Region", format="json", _config=config)
    )

    for artifact in (render_view, render_workbook, export_query, export_view):
        artifact_path = (config.fs_root / artifact["artifact_path"]).resolve()
        assert artifact_path.relative_to(config.fs_root.resolve())
        assert artifact_path.is_file()

    assert render_view["status"] == "ready"
    assert render_workbook["status"] == "ready"
    assert export_query["status"] == "ready"
    assert export_view["format"] == "json"
