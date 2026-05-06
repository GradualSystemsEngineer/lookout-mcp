from __future__ import annotations

from typing import Any

import pytest

from lookout_mcp.tools.api import (
    QueryFilter,
    QueryMetric,
    QueryOrder,
    StructuredQuerySpec,
    _execute_structured_query,
    _validate_query_spec,
)
from lookout_mcp.tools.workflow import WorkflowError


@pytest.fixture
def retail_fields() -> list[dict[str, Any]]:
    return [
        {
            "id": "fld_226c34dbd87b",
            "name": "order_date",
            "label": "Order Date",
            "data_type": "date",
            "semantic_role": "temporal",
            "default_aggregation": None,
            "is_filterable": True,
            "is_sortable": True,
            "allowed_operators": ["eq", "gte", "lte", "between"],
        },
        {
            "id": "fld_437447dbc62c",
            "name": "region",
            "label": "Region",
            "data_type": "string",
            "semantic_role": "dimension",
            "default_aggregation": None,
            "is_filterable": True,
            "is_sortable": True,
            "allowed_operators": ["eq", "neq", "in", "contains"],
        },
        {
            "id": "fld_4b56a82f2c32",
            "name": "revenue",
            "label": "Revenue",
            "data_type": "decimal",
            "semantic_role": "measure",
            "default_aggregation": "sum",
            "is_filterable": True,
            "is_sortable": True,
            "allowed_operators": ["eq", "neq", "gt", "gte", "lt", "lte", "between"],
        },
    ]


@pytest.mark.unit
def test_filter_validation_accepts_field_type_compatible_values(
    retail_fields: list[dict[str, Any]],
) -> None:
    spec = StructuredQuerySpec(
        filters=[
            QueryFilter(
                field="order_date", operator="between", values=["2026-01-01", "2026-03-31"]
            ),
            QueryFilter(field="region", operator="in", values=["Northeast", "West"]),
            QueryFilter(field="revenue", operator="gte", value=1000.50),
        ]
    )

    selected_fields, metrics, filters, orders = _validate_query_spec(
        spec,
        retail_fields,
        allow_virtual_filters=False,
    )

    assert selected_fields == []
    assert metrics == []
    assert [query_filter.field for query_filter in filters] == ["order_date", "region", "revenue"]
    assert orders == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("query_filter", "expected_details"),
    [
        (
            QueryFilter(field="order_date", operator="eq", value="2026-99-99"),
            {"field": "order_date", "data_type": "date", "operator": "eq"},
        ),
        (
            QueryFilter(field="region", operator="starts_with", value="North"),
            {"field": "region", "operator": "starts_with"},
        ),
        (
            QueryFilter(field="revenue", operator="between", values=[100]),
            {"field": "revenue", "operator": "between", "value_count": 1},
        ),
        (
            QueryFilter(field="revenue", operator="eq", value="100"),
            {"field": "revenue", "data_type": "decimal", "operator": "eq"},
        ),
    ],
)
def test_filter_validation_rejects_malformed_values_and_invalid_operators(
    retail_fields: list[dict[str, Any]],
    query_filter: QueryFilter,
    expected_details: dict[str, Any],
) -> None:
    spec = StructuredQuerySpec(filters=[query_filter])

    with pytest.raises(WorkflowError) as exc_info:
        _validate_query_spec(spec, retail_fields, allow_virtual_filters=False)

    envelope = exc_info.value.to_envelope()
    assert envelope["error"]["code"] == "INVALID_FILTER"
    assert expected_details.items() <= envelope["error"]["details"].items()


@pytest.mark.unit
def test_query_builder_returns_deterministic_bounded_aggregate_rows(
    retail_fields: list[dict[str, Any]],
) -> None:
    datasource = {"id": "ds_fc7964798790", "row_count": 482_400}
    spec = StructuredQuerySpec(
        group_by=["region"],
        metrics=[QueryMetric(field="revenue", aggregation="sum")],
        order_by=[QueryOrder(field="revenue", direction="desc")],
        limit=2,
    )

    rows, row_count = _execute_structured_query(datasource, retail_fields, spec)

    assert row_count == 4
    assert rows == [
        {"region": "Central", "sum_revenue": 393102},
        {"region": "West", "sum_revenue": 368071},
    ]
