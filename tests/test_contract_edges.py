from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lookout_mcp.config import LookoutConfig
from lookout_mcp.db import seed
from lookout_mcp.tools import api


@pytest.fixture
def seeded_config(tmp_path: Path) -> LookoutConfig:
    config = LookoutConfig(
        db_path=tmp_path / "lookout.sqlite3",
        fs_root=tmp_path / "var",
        log_level="INFO",
    )
    seed(config)
    return config


def _error_code(result: dict[str, Any]) -> str:
    return str(result["error"]["code"])


@pytest.mark.integration
@pytest.mark.parametrize(
    ("call", "expected_code"),
    [
        (
            lambda config: api.list_datasources(cursor="not-a-cursor", _config=config),
            "INVALID_CURSOR",
        ),
        (
            lambda config: api.list_datasources(page_size=26, _config=config),
            "PAGE_SIZE_TOO_LARGE",
        ),
        (
            lambda config: api.get_datasource(datasource="ds_000000000000", _config=config),
            "NOT_FOUND",
        ),
        (
            lambda config: api.get_workbook(workbook="wb_000000000000", _config=config),
            "NOT_FOUND",
        ),
        (
            lambda config: api.get_view(view="view_000000000000", _config=config),
            "NOT_FOUND",
        ),
        (
            lambda config: api.query_datasource(
                datasource="Retail Sales",
                query_spec={
                    "filters": [{"field": "missing_field", "operator": "eq", "value": "x"}]
                },
                _config=config,
            ),
            "FIELD_NOT_FOUND",
        ),
        (
            lambda config: api.query_datasource(
                datasource="Retail Sales",
                query_spec={
                    "filters": [{"field": "region", "operator": "starts_with", "value": "N"}]
                },
                _config=config,
            ),
            "INVALID_FILTER",
        ),
        (
            lambda config: api.query_datasource(
                datasource="Retail Sales",
                query_spec={
                    "filters": [{"field": "order_date", "operator": "eq", "value": "2026-99-99"}]
                },
                _config=config,
            ),
            "INVALID_FILTER",
        ),
        (
            lambda config: api.query_datasource(
                datasource="Marketing Spend",
                query_spec={"group_by": ["channel"], "metrics": [{"field": "spend"}]},
                _config=config,
            ),
            "SOURCE_UNAVAILABLE",
        ),
        (
            lambda config: api.query_datasource(
                datasource="Retail Sales",
                query_spec={
                    "group_by": ["region"],
                    "metrics": [{"field": "revenue"}],
                    "timeout_ms": 0,
                },
                _config=config,
            ),
            "QUERY_TIMEOUT",
        ),
        (
            lambda config: api.query_datasource(
                datasource="Retail Sales",
                query_spec={
                    "group_by": ["region"],
                    "metrics": [{"field": "revenue"}],
                    "limit": 1001,
                },
                _config=config,
            ),
            "LIMIT_EXCEEDED",
        ),
        (
            lambda config: api.list_views(chart_type="scatter", _config=config),
            "UNSUPPORTED_CHART_TYPE",
        ),
        (
            lambda config: api.get_view(view="Revenue", _config=config),
            "AMBIGUOUS_MATCH",
        ),
    ],
)
def test_contract_edge_cases_return_standard_errors(
    seeded_config: LookoutConfig,
    call: Any,
    expected_code: str,
) -> None:
    result = call(seeded_config)

    assert _error_code(result) == expected_code
    assert set(result["error"]) == {"code", "message", "details"}


@pytest.mark.integration
def test_cache_stale_warning_is_visible_on_metadata_query_and_export(
    seeded_config: LookoutConfig,
) -> None:
    datasource = api.get_datasource(datasource="Store Performance", _config=seeded_config)
    query = api.query_datasource(
        datasource="Store Performance",
        query_spec={"group_by": ["region"], "metrics": [{"field": "sales"}]},
        preview_limit=2,
        _config=seeded_config,
    )
    export = api.export_query_result(
        query_result_id=str(query["query_result_id"]),
        format="json",
        _config=seeded_config,
    )

    assert datasource["warnings"][0]["code"] == "CACHE_STALE"
    assert query["warnings"][0]["code"] == "CACHE_STALE"
    assert export["warnings"][0]["code"] == "CACHE_STALE"


@pytest.mark.integration
def test_token_safety_limits_prevent_bulk_inline_dumps(seeded_config: LookoutConfig) -> None:
    list_result = api.list_datasources(_config=seeded_config)
    query_result = api.query_datasource(
        datasource="Retail Sales",
        query_spec={"operation": "detail", "fields": ["order_id", "region", "revenue"]},
        _config=seeded_config,
    )

    assert list_result["returned_row_count"] == 6
    assert "description" not in list_result["items"][0]
    assert "default_filters" not in list_result["items"][0]
    assert query_result["row_count"] == 482_400
    assert query_result["returned_row_count"] == 100
    assert query_result["truncated"] is True
    assert query_result["warnings"][0]["code"] == "RESULT_TRUNCATED"


@pytest.mark.integration
def test_export_path_creation_failure_returns_export_failed(
    seeded_config: LookoutConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = api.query_datasource(
        datasource="Retail Sales",
        query_spec={"group_by": ["region"], "metrics": [{"field": "revenue"}]},
        _config=seeded_config,
    )

    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated filesystem failure")

    monkeypatch.setattr(api, "_write_export_file", fail_write)

    result = api.export_query_result(
        query_result_id=str(query["query_result_id"]),
        _config=seeded_config,
    )

    assert result["error"]["code"] == "EXPORT_FAILED"
    assert result["error"]["details"]["artifact_path"].startswith("exports/exp_")
