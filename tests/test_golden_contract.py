from __future__ import annotations

from pathlib import Path

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


@pytest.mark.integration
def test_golden_compact_list_output(seeded_config: LookoutConfig) -> None:
    result = api.list_datasources(page_size=2, _config=seeded_config)

    assert result == {
        "items": [
            {
                "id": "ds_4d5b68d21e5b",
                "label": "Customer Support",
                "row_count": 211900,
                "status": "available",
                "tags": ["customer support", "available", "seeded"],
                "theme": "customer support",
            },
            {
                "id": "ds_d9c9e0bb8d3d",
                "label": "Inventory Supply Chain",
                "row_count": 93600,
                "status": "cache_stale",
                "tags": ["inventory supply chain", "cache_stale", "seeded"],
                "theme": "inventory supply chain",
            },
        ],
        "row_count": 6,
        "returned_row_count": 2,
        "truncated": True,
        "next_cursor": (
            "eyJmaWx0ZXJfaGFzaCI6Ijg2ZWRiZjExOWRiOTk0NjAiLCJsYXN0X2lkIjoi"
            "ZHNfZDljOWUwYmI4ZDNkIiwic29ydF9rZXkiOiJsYWJlbCIsInZlcnNpb24iOjF9"
        ),
        "warnings": [
            {
                "code": "CACHE_STALE",
                "message": "Datasource cache is stale; results may lag the source system.",
                "details": {"status": "cache_stale"},
            },
            {
                "code": "SOURCE_DEGRADED",
                "message": (
                    "Datasource source is offline; serving deterministic cached metadata only."
                ),
                "details": {"status": "source_offline"},
            },
            {
                "code": "CACHE_STALE",
                "message": "Datasource cache is stale; results may lag the source system.",
                "details": {"status": "cache_stale"},
            },
        ],
    }


@pytest.mark.integration
def test_golden_get_datasource_schema(seeded_config: LookoutConfig) -> None:
    result = api.get_datasource(datasource="Retail Sales", _config=seeded_config)

    datasource = {
        key: value
        for key, value in result["datasource"].items()
        if key not in {"created_at", "updated_at"}
    }
    fields = result["fields"]

    assert datasource == {
        "id": "ds_fc7964798790",
        "name": "retail_sales",
        "label": "Retail Sales",
        "description": "Order-level retail revenue, margin, product, channel, and region metrics.",
        "theme": "retail sales",
        "status": "available",
        "connection_type": "sqlite_cache",
        "tags": ["retail sales", "available", "seeded"],
        "default_filters": {"period": "last_12_months"},
        "row_count": 482400,
        "cache_updated_at": "2026-01-15T08:00:00Z",
        "source_updated_at": "2026-01-15T07:45:00Z",
    }
    assert len(fields) == 8
    assert fields[1] == {
        "id": "fld_226c34dbd87b",
        "name": "order_date",
        "label": "Order Date",
        "data_type": "date",
        "semantic_role": "temporal",
        "default_aggregation": None,
        "is_filterable": True,
        "is_sortable": True,
        "allowed_operators": ["eq", "gte", "lte", "between"],
    }
    assert fields[5] == {
        "id": "fld_4b56a82f2c32",
        "name": "revenue",
        "label": "Revenue",
        "data_type": "decimal",
        "semantic_role": "measure",
        "default_aggregation": "sum",
        "is_filterable": True,
        "is_sortable": True,
        "allowed_operators": ["eq", "neq", "gt", "gte", "lt", "lte", "between"],
    }
    assert result["warnings"] == []


@pytest.mark.integration
def test_golden_representative_query_result(seeded_config: LookoutConfig) -> None:
    result = api.query_datasource(
        datasource="Retail Sales",
        query_spec={
            "group_by": ["region"],
            "metrics": [{"field": "revenue", "aggregation": "sum"}],
            "order_by": [{"field": "revenue", "direction": "desc"}],
        },
        preview_limit=2,
        _config=seeded_config,
    )

    assert result == {
        "rows": [
            {"region": "Central", "sum_revenue": 393102},
            {"region": "West", "sum_revenue": 368071},
        ],
        "row_count": 4,
        "returned_row_count": 2,
        "truncated": True,
        "next_cursor": None,
        "warnings": [
            {
                "code": "RESULT_TRUNCATED",
                "message": "Inline rows were truncated to the preview limit.",
                "details": {"row_count": 4, "returned_row_count": 2},
            }
        ],
        "query_result_id": "run_cb11007d1d4c",
    }


@pytest.mark.integration
def test_golden_representative_error_response(seeded_config: LookoutConfig) -> None:
    result = api.query_datasource(
        datasource="Retail Sales",
        query_spec={"filters": [{"field": "order_date", "operator": "eq", "value": "2026-99-99"}]},
        _config=seeded_config,
    )

    assert result == {
        "error": {
            "code": "INVALID_FILTER",
            "message": "Filter value is not valid for this field type.",
            "details": {
                "field": "order_date",
                "data_type": "date",
                "operator": "eq",
                "value": "2026-99-99",
            },
        }
    }
