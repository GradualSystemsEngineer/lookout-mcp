from __future__ import annotations

from pathlib import Path
from typing import Any

from lookout_mcp.config import load_config
from lookout_mcp.server import create_mcp_server, health_check
from lookout_mcp.tools import api


def _assert_ok(step: str, result: dict[str, Any]) -> dict[str, Any]:
    if "error" in result:
        raise SystemExit(f"{step} failed: {result}")
    print(f"ok - {step}")
    return result


def _assert_error(step: str, result: dict[str, Any], code: str) -> dict[str, Any]:
    actual = result.get("error", {}).get("code")
    if actual != code:
        raise SystemExit(f"{step} expected {code}, got {result}")
    print(f"ok - {step} returned {code}")
    return result


def _assert_warning(step: str, result: dict[str, Any], code: str) -> None:
    warning_codes = {warning["code"] for warning in result.get("warnings", [])}
    if code not in warning_codes:
        raise SystemExit(f"{step} expected warning {code}, got {result}")
    print(f"ok - {step} warning {code}")


def _assert_artifact_under_root(step: str, fs_root: Path, artifact: dict[str, Any]) -> None:
    relative_path = str(artifact["artifact_path"])
    artifact_path = (fs_root / relative_path).resolve()
    try:
        artifact_path.relative_to(fs_root.resolve())
    except ValueError as exc:
        raise SystemExit(f"{step} escaped LOOKOUT_FS_ROOT: {relative_path}") from exc
    if not artifact_path.is_file():
        raise SystemExit(f"{step} artifact does not exist: {artifact_path}")
    print(f"ok - {step} wrote {relative_path}")


def main() -> None:
    health = _assert_ok("health_check", health_check())
    config = load_config()
    fs_root = Path(str(health["fs_root"]))

    if create_mcp_server() is None:
        raise SystemExit("create_mcp_server failed")
    print("ok - MCP server can be constructed")

    _assert_ok("search_content", api.search_content(query="revenue", page_size=3))
    datasources = _assert_ok("list_datasources", api.list_datasources(page_size=3))
    if datasources["returned_row_count"] == 0:
        raise SystemExit("list_datasources returned no seeded datasources; run make seed first")

    datasource = _assert_ok("get_datasource", api.get_datasource(datasource="Retail Sales"))
    _assert_ok(
        "get_field_values",
        api.get_field_values(datasource=datasource["datasource"]["id"], field="region"),
    )

    _assert_ok("list_workbooks", api.list_workbooks(datasource="Retail Sales"))
    workbook = _assert_ok(
        "get_workbook",
        api.get_workbook(workbook="Retail Sales Executive Dashboard"),
    )
    if not workbook["views"]:
        raise SystemExit("get_workbook returned no views")
    _assert_ok("get_view", api.get_view(view="Q1 Revenue by Region"))

    _assert_ok(
        "get_view_data default filters",
        api.get_view_data(view="Q1 Revenue by Region", preview_limit=3),
    )
    _assert_ok(
        "get_view_data filter overrides",
        api.get_view_data(
            view="Q1 Revenue by Region",
            filter_overrides={"region": "Northeast"},
            preview_limit=3,
        ),
    )

    query = _assert_ok(
        "query_datasource Q1 revenue by region",
        api.query_datasource(
            datasource="Retail Sales",
            query_spec={
                "operation": "aggregate",
                "group_by": ["region"],
                "metrics": [{"field": "revenue", "aggregation": "sum"}],
                "filters": [
                    {
                        "field": "order_date",
                        "operator": "between",
                        "values": ["2026-01-01", "2026-03-31"],
                    }
                ],
                "order_by": [{"field": "revenue", "direction": "desc"}],
            },
            preview_limit=4,
        ),
    )
    query_export = _assert_ok(
        "export_query_result",
        api.export_query_result(query_result_id=query["query_result_id"], format="json"),
    )
    _assert_artifact_under_root("export_query_result", fs_root, query_export)

    _assert_ok(
        "compare_periods quarter over quarter",
        api.compare_periods(
            datasource="Retail Sales",
            metric="revenue",
            period_field="order_date",
            current_period={"quarter": "Q1", "year": 2026},
            comparison_period={"quarter": "Q4", "year": 2025},
            dimensions=["region"],
            preview_limit=4,
        ),
    )

    render = _assert_ok(
        "render_view_image",
        api.render_view_image(
            view="Q1 Revenue by Region",
            filter_overrides={"region": "Northeast"},
            width=640,
            height=360,
        ),
    )
    _assert_artifact_under_root("render_view_image", fs_root, render)
    view_export = _assert_ok(
        "export_view_data",
        api.export_view_data(view="Q1 Revenue by Region", format="csv"),
    )
    _assert_artifact_under_root("export_view_data", fs_root, view_export)

    offline = api.query_datasource(
        datasource="Marketing Spend",
        query_spec={"group_by": ["channel"], "metrics": [{"field": "spend"}]},
    )
    _assert_error("source_offline query", offline, "SOURCE_UNAVAILABLE")

    stale = _assert_ok(
        "cache_stale view data",
        api.get_view_data(view="Top Stores by Same-store Growth", preview_limit=3),
    )
    _assert_warning("cache_stale view data", stale, "CACHE_STALE")

    invalid_field = api.query_datasource(
        datasource="Retail Sales",
        query_spec={"group_by": ["revenu"], "metrics": [{"field": "revenue"}]},
    )
    field_error = _assert_error("invalid field", invalid_field, "FIELD_NOT_FOUND")
    if not field_error["error"]["details"].get("suggestions"):
        raise SystemExit(f"invalid field did not include suggestions: {field_error}")
    print("ok - invalid field suggestions returned")

    print(f"smoke complete - db={config.db_path} fs_root={config.fs_root}")


if __name__ == "__main__":
    main()
