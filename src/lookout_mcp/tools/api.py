"""Callable backend implementation for the Lookout MCP tool surface."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import logging
import re
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator

from lookout_mcp.config import ConfigError, LookoutConfig, load_config
from lookout_mcp.db import connect
from lookout_mcp.errors import error_envelope
from lookout_mcp.schemas import (
    DatasourceRecord,
    StrictModel,
    deterministic_id,
    validate_prefixed_id,
)
from lookout_mcp.tools.registry import (
    ComparePeriodsInput,
    ExportQueryResultInput,
    ExportViewDataInput,
    GetDatasourceInput,
    GetFieldValuesInput,
    GetViewDataInput,
    GetViewInput,
    GetWorkbookInput,
    ListDatasourcesInput,
    ListViewsInput,
    ListWorkbooksInput,
    QueryDatasourceInput,
    RenderViewImageInput,
    RenderWorkbookImageInput,
    SearchContentInput,
)
from lookout_mcp.tools.workflow import (
    AmbiguousMatchError,
    InvalidCursorError,
    TokenLimitError,
    ToolWarning,
    WorkflowError,
    bound_query_preview,
    compact_datasource_item,
    compact_list_output,
    decode_cursor,
    encode_cursor,
    filter_hash,
    fuzzy_candidates,
    normalize_list_page_size,
    normalize_query_preview_limit,
    resolve_fuzzy_match,
    warning_for_datasource_status,
)

EXPENSIVE_OPERATION_LIMIT = 2
MAX_RENDER_PIXELS = 4_000_000
MAX_EXPORT_ROWS = 10_000
MAX_QUERY_ROWS = 1_000
TOOL_TIMESTAMP = "2026-01-15T09:30:00Z"

Aggregation = Literal["sum", "avg", "min", "max", "count", "count_distinct"]
ExportFormat = Literal["csv", "json"]
LOGGER = logging.getLogger("lookout_mcp.tools")


class _ExpensiveOperationGuard:
    def __init__(self, max_active: int) -> None:
        self._max_active = max_active
        self._active = 0
        self._lock = threading.Lock()

    @contextmanager
    def run(self, operation: str) -> Any:
        with self._lock:
            if self._active >= self._max_active:
                raise WorkflowError(
                    "RATE_LIMITED",
                    "Too many expensive Lookout operations are already running.",
                    {"operation": operation, "max_active": self._max_active},
                )
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1


_EXPENSIVE_GUARD = _ExpensiveOperationGuard(EXPENSIVE_OPERATION_LIMIT)


class QueryMetric(StrictModel):
    field: str
    aggregation: Aggregation | None = None
    alias: str | None = None


class QueryFilter(StrictModel):
    field: str
    operator: str = "eq"
    value: Any = None
    values: list[Any] | None = None


class QueryOrder(StrictModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.lower()
        return value


class StructuredQuerySpec(StrictModel):
    operation: Literal["aggregate", "detail", "histogram"] = "aggregate"
    fields: list[str] = Field(default_factory=list)
    metrics: list[QueryMetric] = Field(default_factory=list)
    filters: list[QueryFilter] | dict[str, Any] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[QueryOrder] = Field(default_factory=list)
    sort: list[QueryOrder] = Field(default_factory=list)
    page_size: int | None = None
    cursor: str | None = None
    limit: int | None = None
    field: str | None = None
    bins: int | None = Field(default=None, gt=0, le=100)
    datasource_id: str | None = None
    sql: str | None = None
    timeout_ms: int | None = None


def _configure_logging(log_level_name: str | None = None) -> None:
    log_level = getattr(logging, log_level_name or "INFO", logging.INFO)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=log_level, format="%(message)s")
    LOGGER.setLevel(log_level)


def _loaded_config(config: LookoutConfig | None) -> LookoutConfig:
    loaded = load_config() if config is None else config
    _configure_logging(loaded.log_level)
    loaded.ensure_filesystem_root()
    return loaded


def _json_loads(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(zip(row.keys(), row, strict=True))


def _datasource_from_row(row: Mapping[str, Any]) -> DatasourceRecord:
    data = dict(row)
    data["tags"] = _json_loads(data["tags"])
    data["default_filters"] = _json_loads(data["default_filters"])
    data.pop("created_at", None)
    data.pop("updated_at", None)
    return DatasourceRecord.model_validate(data)


def _record_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = _row_dict(row)
    for key in (
        "tags",
        "default_filters",
        "allowed_operators",
        "chart_config",
        "query_spec",
        "visual_config",
        "preview_rows",
        "warnings",
        "metadata",
    ):
        if key in data:
            data[key] = _json_loads(data[key])
    for key in ("is_filterable", "is_sortable"):
        if key in data:
            data[key] = bool(data[key])
    return data


def _all_datasources(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute("SELECT * FROM datasources ORDER BY label, id").fetchall()
    return [_record_from_row(row) for row in rows]


def _all_workbooks(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute("SELECT * FROM workbooks ORDER BY title, id").fetchall()
    return [_record_from_row(row) for row in rows]


def _all_views(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            views.*,
            workbooks.title AS workbook_title,
            datasources.label AS datasource_label,
            datasources.status AS datasource_status
        FROM views
        JOIN workbooks ON workbooks.id = views.workbook_id
        JOIN datasources ON datasources.id = views.datasource_id
        ORDER BY views.title, views.id
        """
    ).fetchall()
    return [_record_from_row(row) for row in rows]


def _fields_for_datasource(
    connection: sqlite3.Connection,
    datasource_id: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT *
        FROM datasource_fields
        WHERE datasource_id = ?
        ORDER BY ordinal
        """,
        (datasource_id,),
    ).fetchall()
    return [_record_from_row(row) for row in rows]


def _compact_field(field: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": field["id"],
        "name": field["name"],
        "label": field["label"],
        "data_type": field["data_type"],
        "semantic_role": field["semantic_role"],
        "default_aggregation": field["default_aggregation"],
        "is_filterable": field["is_filterable"],
        "is_sortable": field["is_sortable"],
        "allowed_operators": field["allowed_operators"],
    }


def _compact_workbook(workbook: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": workbook["id"],
        "title": workbook["title"],
        "project": workbook["project"],
        "owner": workbook["owner"],
        "tags": workbook["tags"],
    }


def _compact_view(view: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": view["id"],
        "title": view["title"],
        "workbook_id": view["workbook_id"],
        "datasource_id": view["datasource_id"],
        "chart_type": view["chart_type"],
        "position": view["position"],
    }


def _field_lookup_records(fields: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": field["id"],
            "name": field["name"],
            "label": field["label"],
            "description": field["description"],
        }
        for field in fields
    ]


def _field_suggestions(value: str, fields: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    records = _field_lookup_records(fields)
    by_id = {str(record["id"]): record for record in records}
    suggestions = []
    for candidate in fuzzy_candidates(value, records, kind="field")[:3]:
        record = by_id[candidate.id]
        suggestions.append(
            {
                "id": candidate.id,
                "name": str(record["name"]),
                "label": candidate.label,
            }
        )
    return suggestions


def _resolve_datasource(
    connection: sqlite3.Connection,
    value: str,
) -> dict[str, Any]:
    rows = _all_datasources(connection)
    if value.startswith("ds_"):
        validate_prefixed_id(value, "ds")
        for row in rows:
            if row["id"] == value:
                return row
        raise WorkflowError("NOT_FOUND", "Datasource was not found.", {"datasource": value})

    match = resolve_fuzzy_match(value, rows, kind="datasource")
    if match is None:
        raise WorkflowError("NOT_FOUND", "Datasource was not found.", {"datasource": value})
    return next(row for row in rows if row["id"] == match.id)


def _resolve_workbook(
    connection: sqlite3.Connection,
    value: str,
) -> dict[str, Any]:
    rows = _all_workbooks(connection)
    if value.startswith("wb_"):
        validate_prefixed_id(value, "wb")
        for row in rows:
            if row["id"] == value:
                return row
        raise WorkflowError("NOT_FOUND", "Workbook was not found.", {"workbook": value})

    match = resolve_fuzzy_match(value, rows, kind="workbook")
    if match is None:
        raise WorkflowError("NOT_FOUND", "Workbook was not found.", {"workbook": value})
    return next(row for row in rows if row["id"] == match.id)


def _resolve_view(connection: sqlite3.Connection, value: str) -> dict[str, Any]:
    rows = _all_views(connection)
    if value.startswith("view_"):
        validate_prefixed_id(value, "view")
        for row in rows:
            if row["id"] == value:
                return row
        raise WorkflowError("NOT_FOUND", "View was not found.", {"view": value})

    match = resolve_fuzzy_match(value, rows, kind="view")
    if match is None:
        raise WorkflowError("NOT_FOUND", "View was not found.", {"view": value})
    return next(row for row in rows if row["id"] == match.id)


def _resolve_field(
    fields: Sequence[Mapping[str, Any]],
    value: str,
    *,
    role: str | None = None,
) -> dict[str, Any]:
    candidates = [field for field in fields if role is None or field["semantic_role"] == role]
    if value.startswith("fld_"):
        validate_prefixed_id(value, "fld")
        for field in candidates:
            if field["id"] == value:
                return dict(field)
        raise WorkflowError("FIELD_NOT_FOUND", "Field was not found.", {"field": value})

    exact = [
        field
        for field in candidates
        if value.lower() in {str(field["name"]).lower(), str(field["label"]).lower()}
    ]
    if len(exact) == 1:
        return dict(exact[0])
    if len(exact) > 1:
        raise AmbiguousMatchError(
            fuzzy_candidates(value, _field_lookup_records(exact), kind="field")[: len(exact)]
        )

    match = resolve_fuzzy_match(value, _field_lookup_records(candidates), kind="field")
    if match is None:
        raise WorkflowError(
            "FIELD_NOT_FOUND",
            "Field was not found.",
            {"field": value, "suggestions": _field_suggestions(value, candidates)},
        )
    return next(dict(field) for field in candidates if field["id"] == match.id)


def _normalize_filters(filters: list[QueryFilter] | dict[str, Any]) -> list[QueryFilter]:
    if isinstance(filters, dict):
        return [
            QueryFilter(field=field, operator="eq", value=value) for field, value in filters.items()
        ]
    return filters


def _field_map(fields: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for field in fields:
        concrete = dict(field)
        mapped[str(field["id"]).lower()] = concrete
        mapped[str(field["name"]).lower()] = concrete
        mapped[str(field["label"]).lower()] = concrete
    return mapped


def _resolve_query_field(
    value: str,
    fields: Sequence[Mapping[str, Any]],
    *,
    error_code: str,
) -> dict[str, Any]:
    mapped = _field_map(fields)
    field = mapped.get(value.lower())
    if field is None:
        raise WorkflowError(
            error_code,
            "Field is not valid for this datasource.",
            {"field": value, "suggestions": _field_suggestions(value, fields)},
        )
    return field


def _filter_payload_to_list(
    filters: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    if filters is None:
        return []
    if isinstance(filters, Mapping):
        return [
            {"field": field, "operator": "eq", "value": value} for field, value in filters.items()
        ]
    return [dict(item) for item in filters]


def _filter_values(query_filter: QueryFilter) -> list[Any]:
    if query_filter.values is not None:
        return list(query_filter.values)
    if (
        query_filter.operator in {"between", "in"}
        and isinstance(query_filter.value, Sequence)
        and not isinstance(query_filter.value, str | bytes | bytearray)
    ):
        return list(query_filter.value)
    return [query_filter.value]


def _is_valid_filter_value(value: Any, data_type: str) -> bool:
    if data_type == "string":
        return isinstance(value, str)
    if data_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if data_type == "decimal":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if data_type == "boolean":
        return isinstance(value, bool)
    if data_type == "date":
        if not isinstance(value, str):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if data_type == "datetime":
        if not isinstance(value, str):
            return False
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return True
    return False


def _validate_filter_value(
    query_filter: QueryFilter,
    field: Mapping[str, Any],
) -> None:
    data_type = str(field["data_type"])
    operator = query_filter.operator
    values = _filter_values(query_filter)

    if operator == "between" and len(values) != 2:
        raise WorkflowError(
            "INVALID_FILTER",
            "Between filters require exactly two values.",
            {"field": field["name"], "operator": operator, "value_count": len(values)},
        )
    if operator == "in" and not values:
        raise WorkflowError(
            "INVALID_FILTER",
            "In filters require at least one value.",
            {"field": field["name"], "operator": operator},
        )
    if operator == "contains" and data_type != "string":
        raise WorkflowError(
            "INVALID_FILTER",
            "Contains filters are only valid for string fields.",
            {"field": field["name"], "data_type": data_type, "operator": operator},
        )

    for value in values:
        if not _is_valid_filter_value(value, data_type):
            raise WorkflowError(
                "INVALID_FILTER",
                "Filter value is not valid for this field type.",
                {
                    "field": field["name"],
                    "data_type": data_type,
                    "operator": operator,
                    "value": value,
                },
            )


def _validate_query_spec(
    spec: StructuredQuerySpec,
    fields: Sequence[Mapping[str, Any]],
    *,
    allow_virtual_filters: bool,
) -> tuple[list[dict[str, Any]], list[QueryMetric], list[QueryFilter], list[QueryOrder]]:
    if spec.sql:
        raise WorkflowError(
            "UNSUPPORTED_SQL",
            "SQL mode is not supported by this offline reference implementation.",
            {"recovery_hint": "Use structured query_spec fields, metrics, filters, and group_by."},
        )
    if spec.timeout_ms is not None and spec.timeout_ms < 1:
        raise WorkflowError(
            "QUERY_TIMEOUT",
            "Query timeout elapsed before execution could start.",
            {"timeout_ms": spec.timeout_ms},
        )
    if spec.limit is not None and (spec.limit < 1 or spec.limit > MAX_QUERY_ROWS):
        raise WorkflowError(
            "LIMIT_EXCEEDED",
            f"query_spec.limit must be between 1 and {MAX_QUERY_ROWS}.",
            {"max": MAX_QUERY_ROWS, "requested": spec.limit},
        )
    if spec.page_size is not None:
        normalize_query_preview_limit(spec.page_size)

    selected_fields: list[dict[str, Any]] = []
    metrics = list(spec.metrics)
    filters = _normalize_filters(spec.filters)
    orders = list(spec.order_by or spec.sort)

    for name in [*spec.fields, *spec.group_by]:
        field = _resolve_query_field(name, fields, error_code="FIELD_NOT_FOUND")
        selected_fields.append(field)

    if spec.operation == "histogram":
        if spec.field is None:
            raise WorkflowError("INVALID_INPUT", "Histogram queries require field.", {})
        field = _resolve_query_field(spec.field, fields, error_code="FIELD_NOT_FOUND")
        if field["semantic_role"] != "measure":
            raise WorkflowError(
                "INVALID_FILTER",
                "Histogram field must be a measure.",
                {"field": field["name"], "semantic_role": field["semantic_role"]},
            )
        selected_fields.append(field)

    for metric in metrics:
        field = _resolve_query_field(metric.field, fields, error_code="FIELD_NOT_FOUND")
        if field["semantic_role"] != "measure":
            raise WorkflowError(
                "INVALID_FILTER",
                "Metric fields must have semantic_role=measure.",
                {"field": field["name"], "semantic_role": field["semantic_role"]},
            )
        if metric.aggregation is None and field["default_aggregation"] is None:
            raise WorkflowError(
                "INVALID_INPUT",
                "Metric requires an aggregation because the field has no default.",
                {"field": field["name"]},
            )

    for query_filter in filters:
        filter_field = _field_map(fields).get(query_filter.field.lower())
        if filter_field is None:
            if allow_virtual_filters:
                continue
            raise WorkflowError(
                "FIELD_NOT_FOUND",
                "Filter field is not valid for this datasource.",
                {
                    "field": query_filter.field,
                    "suggestions": _field_suggestions(query_filter.field, fields),
                },
            )
        if not filter_field["is_filterable"]:
            raise WorkflowError(
                "INVALID_FILTER",
                "Field is not filterable.",
                {"field": filter_field["name"]},
            )
        if query_filter.operator not in filter_field["allowed_operators"]:
            raise WorkflowError(
                "INVALID_FILTER",
                "Filter operator is not allowed for this field.",
                {
                    "field": filter_field["name"],
                    "operator": query_filter.operator,
                    "allowed_operators": filter_field["allowed_operators"],
                },
            )
        _validate_filter_value(query_filter, filter_field)

    orderable_names = {field["name"] for field in fields if field["is_sortable"]}
    orderable_names.update({field["label"] for field in fields if field["is_sortable"]})
    for order in orders:
        order_field = _field_map(fields).get(order.field.lower())
        if order_field is None:
            metric_aliases = {metric.alias for metric in metrics if metric.alias}
            metric_names = {metric.field for metric in metrics}
            if order.field not in metric_aliases and order.field not in metric_names:
                raise WorkflowError(
                    "INVALID_SORT",
                    "Sort field is invalid.",
                    {"field": order.field},
                )
            continue
        if (
            order_field["name"] not in orderable_names
            and order_field["label"] not in orderable_names
        ):
            raise WorkflowError(
                "INVALID_SORT",
                "Field is not sortable.",
                {"field": order_field["name"]},
            )

    return selected_fields, metrics, filters, orders


def _hash_int(*parts: object, minimum: int = 10, maximum: int = 1_000_000) -> int:
    encoded = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    span = maximum - minimum + 1
    return minimum + (int(digest[:12], 16) % span)


def _representative_values(field: Mapping[str, Any]) -> list[Any]:
    name = str(field["name"])
    labels: dict[str, list[Any]] = {
        "region": ["Northeast", "Southeast", "West", "Central"],
        "channel": ["Retail", "Ecommerce", "Partner", "Paid Search", "Lifecycle"],
        "category": ["Apparel", "Home", "Electronics", "Beauty"],
        "stage": ["Qualified", "Proposal", "Commit", "Closed Won"],
        "owner_region": ["East", "West", "Central", "International"],
        "segment": ["Enterprise", "Mid-Market", "SMB"],
        "priority": ["P1", "P2", "P3", "P4"],
        "product_area": ["Core Platform", "Integrations", "Mobile", "Billing"],
        "vendor": ["Northstar", "Apex", "Blue River", "Summit"],
        "store_format": ["Mall", "Outlet", "Flagship", "Neighborhood"],
        "audience": ["Prospects", "Customers", "Expansion", "Winback"],
    }
    if name in labels:
        return labels[name]
    if field["data_type"] in {"date", "datetime"}:
        return ["2025-10-01", "2025-11-01", "2025-12-01", "2026-01-01"]
    if field["data_type"] == "boolean":
        return [True, False]
    if field["semantic_role"] == "identifier":
        prefix = re.sub(r"[^a-z0-9]+", "_", name).strip("_") or "id"
        return [f"{prefix}_{index:03d}" for index in range(1, 5)]
    if field["semantic_role"] == "measure":
        return [100, 250, 500, 1_000]
    return ["A", "B", "C", "D"]


def _metric_alias(metric: QueryMetric, fields: Sequence[Mapping[str, Any]]) -> str:
    if metric.alias:
        return metric.alias
    field = _resolve_query_field(metric.field, fields, error_code="FIELD_NOT_FOUND")
    aggregation = metric.aggregation or field["default_aggregation"] or "sum"
    return f"{aggregation}_{field['name']}"


def _execute_structured_query(
    datasource: Mapping[str, Any],
    fields: Sequence[Mapping[str, Any]],
    spec: StructuredQuerySpec,
    *,
    allow_virtual_filters: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    selected_fields, metrics, _filters, orders = _validate_query_spec(
        spec,
        fields,
        allow_virtual_filters=allow_virtual_filters,
    )
    limit = spec.limit or spec.page_size or MAX_QUERY_ROWS

    if spec.operation == "histogram":
        target = _resolve_query_field(str(spec.field), fields, error_code="FIELD_NOT_FOUND")
        bins = spec.bins or 12
        histogram_rows = [
            {
                "bucket_start": index * 10,
                "bucket_end": (index + 1) * 10,
                "record_count": _hash_int(datasource["id"], target["name"], index, maximum=500),
            }
            for index in range(bins)
        ]
        return histogram_rows[:limit], len(histogram_rows)

    if spec.operation == "detail" or (spec.fields and not metrics and not spec.group_by):
        visible_fields = selected_fields or [dict(field) for field in fields[:5]]
        row_count = min(int(datasource["row_count"]), MAX_QUERY_ROWS)
        rows: list[dict[str, Any]] = []
        for index in range(row_count):
            row: dict[str, Any] = {}
            for field in visible_fields:
                values = _representative_values(field)
                row[str(field["name"])] = values[index % len(values)]
            rows.append(row)
        return rows[:limit], int(datasource["row_count"])

    group_fields = [
        _resolve_query_field(name, fields, error_code="FIELD_NOT_FOUND") for name in spec.group_by
    ]
    if not metrics:
        measures = [field for field in fields if field["semantic_role"] == "measure"]
        if not measures:
            raise WorkflowError(
                "INVALID_INPUT",
                "Aggregate queries require at least one metric.",
                {},
            )
        first_measure = measures[0]
        metrics = [
            QueryMetric(
                field=str(first_measure["name"]),
                aggregation=str(first_measure["default_aggregation"] or "sum"),  # type: ignore[arg-type]
            )
        ]

    value_sets = [_representative_values(field)[:4] for field in group_fields]
    if not value_sets:
        combinations: list[tuple[Any, ...]] = [()]
    elif len(value_sets) == 1:
        combinations = [(value,) for value in value_sets[0]]
    else:
        combinations = [(left, right) for left in value_sets[0] for right in value_sets[1]]

    rows = []
    for combo_index, combination in enumerate(combinations):
        row = {str(field["name"]): combination[index] for index, field in enumerate(group_fields)}
        for metric in metrics:
            alias = _metric_alias(metric, fields)
            row[alias] = _hash_int(
                datasource["id"],
                alias,
                combo_index,
                minimum=100,
                maximum=500_000,
            )
        rows.append(row)

    for order in reversed(orders):
        key = order.field
        if rows and key not in rows[0]:
            try:
                key = _metric_alias(
                    next(metric for metric in metrics if metric.field == order.field),
                    fields,
                )
            except StopIteration:
                resolved = _field_map(fields).get(order.field.lower())
                key = str(resolved["name"]) if resolved else order.field
        rows.sort(key=lambda row: row.get(key, ""), reverse=order.direction == "desc")

    return rows[:limit], len(rows)


def _paginate_records(
    records: Sequence[Mapping[str, Any]],
    *,
    page_size: int | None,
    cursor: str | None,
    sort_key: str,
    filter_payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], int, str | None]:
    size = normalize_list_page_size(page_size)
    request_hash = filter_hash(filter_payload)
    start_index = 0
    if cursor is not None:
        payload = decode_cursor(
            cursor,
            expected_sort_key=sort_key,
            expected_filter_hash=request_hash,
        )
        ids = [str(record["id"]) for record in records]
        try:
            start_index = ids.index(payload.last_id) + 1
        except ValueError as exc:
            raise InvalidCursorError(
                "Cursor target no longer exists.",
                last_id=payload.last_id,
            ) from exc

    page = [dict(record) for record in records[start_index : start_index + size]]
    next_cursor = None
    if start_index + size < len(records) and page:
        next_cursor = encode_cursor(
            sort_key=sort_key,
            last_id=str(page[-1]["id"]),
            filter_hash_value=request_hash,
        )
    return page, len(records), next_cursor


def _warnings_dicts(status: str) -> list[dict[str, Any]]:
    return [warning.model_dump() for warning in warning_for_datasource_status(status)]


def _run_tool(
    input_model: type[StrictModel],
    payload: Mapping[str, Any],
    handler: Callable[[Any, LookoutConfig], dict[str, Any]],
    config: LookoutConfig | None,
) -> dict[str, Any]:
    tool_name = handler.__name__.removeprefix("_")
    started_at = time.perf_counter()
    result: dict[str, Any]
    _configure_logging(config.log_level if config else None)
    try:
        validated = input_model.model_validate(dict(payload))
        result = handler(validated, _loaded_config(config))
    except ValidationError as exc:
        result = error_envelope(
            "INVALID_INPUT",
            "Input validation failed.",
            {"errors": exc.errors(include_url=False)},
        )
    except ConfigError as exc:
        result = error_envelope(
            "CONFIG_MISSING",
            str(exc),
            {"missing": exc.missing},
        )
    except (WorkflowError, TokenLimitError, InvalidCursorError, AmbiguousMatchError) as exc:
        result = exc.to_envelope()
    except ValueError as exc:
        result = error_envelope("INVALID_INPUT", str(exc), {})
    except sqlite3.Error as exc:
        result = error_envelope(
            "DATASTORE_ERROR",
            "Lookout could not read or update the local SQLite database.",
            {"recovery_hint": "Run make migrate and make seed, then retry the tool call."},
        )
        LOGGER.debug("sqlite datastore error in %s: %s", tool_name, exc)
    except OSError as exc:
        result = error_envelope(
            "FILESYSTEM_ERROR",
            "Lookout could not access the configured local filesystem root.",
            {"recovery_hint": "Check LOOKOUT_FS_ROOT exists and is writable."},
        )
        LOGGER.debug("filesystem error in %s: %s", tool_name, exc)
    except Exception as exc:  # pragma: no cover - defensive boundary for MCP clients
        result = error_envelope(
            "INTERNAL_ERROR",
            "Lookout failed unexpectedly while handling this tool call.",
            {"recovery_hint": "Retry with the same bounded request, then inspect local logs."},
        )
        LOGGER.debug("unexpected error in %s: %s", tool_name, exc)

    _log_tool_result(tool_name, started_at, result)
    return result


def _log_tool_result(tool_name: str, started_at: float, result: Mapping[str, Any]) -> None:
    error = result.get("error")
    error_code = str(error["code"]) if isinstance(error, Mapping) else None
    status = "error" if error_code else "ok"
    payload = {
        "event": "lookout.tool_call",
        "tool_name": tool_name,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "status": status,
        "row_count": result.get("row_count"),
        "returned_row_count": result.get("returned_row_count"),
        "error_code": error_code,
    }
    LOGGER.info(json.dumps(payload, sort_keys=True))


def _safe_artifact_path(fs_root: Path, relative_path: str) -> Path:
    root = fs_root.resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(
            "INVALID_PATH",
            "Artifact path escapes LOOKOUT_FS_ROOT.",
            {"artifact_path": relative_path},
        ) from exc
    return target


def _write_export_file(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    export_format: ExportFormat,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if export_format == "json":
        path.write_text(json.dumps(list(rows), sort_keys=True, indent=2), encoding="utf-8")
        return

    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _insert_query_result(
    connection: sqlite3.Connection,
    *,
    datasource_id: str,
    view_id: str | None,
    query_spec: Mapping[str, Any],
    row_count: int,
    rows: Sequence[Mapping[str, Any]],
    warnings: Sequence[ToolWarning],
) -> str:
    natural = json.dumps(
        {"datasource_id": datasource_id, "view_id": view_id, "query_spec": query_spec},
        sort_keys=True,
        default=str,
    )
    query_result_id = deterministic_id("run", f"query-result:{natural}")
    connection.execute(
        """
        INSERT INTO query_results (
            id, datasource_id, view_id, query_spec, row_count, preview_rows,
            status, warnings, executed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            datasource_id = excluded.datasource_id,
            view_id = excluded.view_id,
            query_spec = excluded.query_spec,
            row_count = excluded.row_count,
            preview_rows = excluded.preview_rows,
            status = excluded.status,
            warnings = excluded.warnings,
            executed_at = excluded.executed_at
        """,
        (
            query_result_id,
            datasource_id,
            view_id,
            json.dumps(query_spec, sort_keys=True, separators=(",", ":"), default=str),
            row_count,
            json.dumps(list(rows), sort_keys=True, separators=(",", ":"), default=str),
            json.dumps([warning.code for warning in warnings], sort_keys=True),
            TOOL_TIMESTAMP,
        ),
    )
    return query_result_id


def search_content(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(SearchContentInput, kwargs, _search_content, kwargs.pop("_config", None))


def _search_content(input_data: SearchContentInput, config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        content_types = set(input_data.content_types or ["datasource", "workbook", "view", "field"])
        candidates: list[dict[str, Any]] = []

        if "datasource" in content_types:
            candidates.extend(
                candidate.model_dump()
                for candidate in fuzzy_candidates(
                    input_data.query,
                    _all_datasources(connection),
                    kind="datasource",
                )
            )
        if "workbook" in content_types:
            candidates.extend(
                candidate.model_dump()
                for candidate in fuzzy_candidates(
                    input_data.query,
                    _all_workbooks(connection),
                    kind="workbook",
                )
            )
        if "view" in content_types:
            candidates.extend(
                candidate.model_dump()
                for candidate in fuzzy_candidates(
                    input_data.query,
                    _all_views(connection),
                    kind="view",
                )
            )
        if "field" in content_types:
            rows = connection.execute(
                """
                SELECT
                    datasource_fields.*,
                    datasources.label AS datasource_label
                FROM datasource_fields
                JOIN datasources ON datasources.id = datasource_fields.datasource_id
                ORDER BY datasource_fields.label, datasource_fields.id
                """
            ).fetchall()
            field_records = [_record_from_row(row) for row in rows]
            candidates.extend(
                candidate.model_dump()
                for candidate in fuzzy_candidates(
                    input_data.query,
                    field_records,
                    kind="field",
                    searchable_fields=("id", "name", "label", "description", "datasource_label"),
                )
            )

        candidates.sort(
            key=lambda item: (
                -int(item["score"]),
                str(item["kind"]),
                str(item["label"]),
                str(item["id"]),
            )
        )
        page, row_count, next_cursor = _paginate_records(
            candidates,
            page_size=input_data.page_size,
            cursor=input_data.cursor,
            sort_key="search_score",
            filter_payload={"query": input_data.query, "content_types": sorted(content_types)},
        )
        return compact_list_output(page, row_count=row_count, next_cursor=next_cursor).model_dump()


def list_datasources(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(ListDatasourcesInput, kwargs, _list_datasources, kwargs.pop("_config", None))


def _list_datasources(input_data: ListDatasourcesInput, config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        records = _all_datasources(connection)
        if input_data.status:
            records = [record for record in records if record["status"] == input_data.status]
        if input_data.theme:
            records = [record for record in records if record["theme"] == input_data.theme]
        if input_data.query:
            ids = {
                candidate.id
                for candidate in fuzzy_candidates(input_data.query, records, kind="datasource")
            }
            records = [record for record in records if record["id"] in ids]
        compact = [
            compact_datasource_item(_datasource_from_row(record)).model_dump() for record in records
        ]
        page, row_count, next_cursor = _paginate_records(
            compact,
            page_size=input_data.page_size,
            cursor=input_data.cursor,
            sort_key="label",
            filter_payload={
                "status": input_data.status,
                "theme": input_data.theme,
                "query": input_data.query,
            },
        )
        warnings = [
            warning
            for record in records
            for warning in warning_for_datasource_status(str(record["status"]))
        ]
        return compact_list_output(
            page,
            row_count=row_count,
            next_cursor=next_cursor,
            warnings=warnings,
        ).model_dump()


def get_datasource(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(GetDatasourceInput, kwargs, _get_datasource, kwargs.pop("_config", None))


def _get_datasource(input_data: GetDatasourceInput, config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        datasource = _resolve_datasource(connection, input_data.datasource)
        fields = (
            _fields_for_datasource(connection, str(datasource["id"]))
            if input_data.include_fields
            else []
        )
        return {
            "datasource": datasource,
            "fields": [_compact_field(field) for field in fields],
            "warnings": _warnings_dicts(str(datasource["status"])),
        }


def get_field_values(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(GetFieldValuesInput, kwargs, _get_field_values, kwargs.pop("_config", None))


def _get_field_values(input_data: GetFieldValuesInput, config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        datasource = _resolve_datasource(connection, input_data.datasource)
        fields = _fields_for_datasource(connection, str(datasource["id"]))
        field = _resolve_field(fields, input_data.field)
        values = [
            {"id": f"{field['id']}:{index}", "value": value}
            for index, value in enumerate(_representative_values(field), start=1)
        ]
        if input_data.search:
            search = input_data.search.lower()
            values = [item for item in values if search in str(item["value"]).lower()]
        page, row_count, next_cursor = _paginate_records(
            values,
            page_size=input_data.page_size,
            cursor=input_data.cursor,
            sort_key="value",
            filter_payload={
                "datasource": datasource["id"],
                "field": field["id"],
                "search": input_data.search,
            },
        )
        return compact_list_output(
            page,
            row_count=row_count,
            next_cursor=next_cursor,
            warnings=warning_for_datasource_status(str(datasource["status"])),
        ).model_dump()


def list_workbooks(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(ListWorkbooksInput, kwargs, _list_workbooks, kwargs.pop("_config", None))


def _list_workbooks(input_data: ListWorkbooksInput, config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        records = _all_workbooks(connection)
        if input_data.project:
            records = [record for record in records if record["project"] == input_data.project]
        if input_data.datasource:
            datasource = _resolve_datasource(connection, input_data.datasource)
            workbook_ids = {
                str(row["workbook_id"])
                for row in connection.execute(
                    "SELECT DISTINCT workbook_id FROM views WHERE datasource_id = ?",
                    (datasource["id"],),
                ).fetchall()
            }
            records = [record for record in records if record["id"] in workbook_ids]
        if input_data.query:
            ids = {
                candidate.id
                for candidate in fuzzy_candidates(input_data.query, records, kind="workbook")
            }
            records = [record for record in records if record["id"] in ids]
        compact = [_compact_workbook(record) for record in records]
        page, row_count, next_cursor = _paginate_records(
            compact,
            page_size=input_data.page_size,
            cursor=input_data.cursor,
            sort_key="title",
            filter_payload={
                "project": input_data.project,
                "datasource": input_data.datasource,
                "query": input_data.query,
            },
        )
        return compact_list_output(page, row_count=row_count, next_cursor=next_cursor).model_dump()


def get_workbook(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(GetWorkbookInput, kwargs, _get_workbook, kwargs.pop("_config", None))


def _get_workbook(input_data: GetWorkbookInput, config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        workbook = _resolve_workbook(connection, input_data.workbook)
        views = [
            _compact_view(view)
            for view in _all_views(connection)
            if view["workbook_id"] == workbook["id"]
        ]
        statuses = {
            str(view["datasource_status"])
            for view in _all_views(connection)
            if view["workbook_id"] == workbook["id"]
        }
        warnings = [
            warning.model_dump()
            for status in sorted(statuses)
            for warning in warning_for_datasource_status(status)
        ]
        return {
            "workbook": workbook,
            "views": views if input_data.include_views else [],
            "warnings": warnings,
        }


def list_views(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(ListViewsInput, kwargs, _list_views, kwargs.pop("_config", None))


def _list_views(input_data: ListViewsInput, config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        records = _all_views(connection)
        if input_data.workbook:
            workbook = _resolve_workbook(connection, input_data.workbook)
            records = [record for record in records if record["workbook_id"] == workbook["id"]]
        if input_data.datasource:
            datasource = _resolve_datasource(connection, input_data.datasource)
            records = [record for record in records if record["datasource_id"] == datasource["id"]]
        if input_data.chart_type:
            if input_data.chart_type not in {"bar", "pie", "treemap", "line", "histogram"}:
                raise WorkflowError(
                    "UNSUPPORTED_CHART_TYPE",
                    "chart_type is not supported.",
                    {"chart_type": input_data.chart_type},
                )
            records = [
                record for record in records if record["chart_type"] == input_data.chart_type
            ]
        if input_data.query:
            ids = {
                candidate.id
                for candidate in fuzzy_candidates(input_data.query, records, kind="view")
            }
            records = [record for record in records if record["id"] in ids]
        compact = [_compact_view(record) for record in records]
        page, row_count, next_cursor = _paginate_records(
            compact,
            page_size=input_data.page_size,
            cursor=input_data.cursor,
            sort_key="title",
            filter_payload={
                "workbook": input_data.workbook,
                "datasource": input_data.datasource,
                "chart_type": input_data.chart_type,
                "query": input_data.query,
            },
        )
        return compact_list_output(page, row_count=row_count, next_cursor=next_cursor).model_dump()


def get_view(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(GetViewInput, kwargs, _get_view, kwargs.pop("_config", None))


def _get_view(input_data: GetViewInput, config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        view = _resolve_view(connection, input_data.view)
        output_view = dict(view)
        if not input_data.include_query_spec:
            output_view.pop("query_spec", None)
        return {
            "view": output_view,
            "warnings": _warnings_dicts(str(view["datasource_status"])),
        }


def get_view_data(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(GetViewDataInput, kwargs, _get_view_data, kwargs.pop("_config", None))


def _get_view_data(input_data: GetViewDataInput, config: LookoutConfig) -> dict[str, Any]:
    normalize_query_preview_limit(input_data.preview_limit)
    with _EXPENSIVE_GUARD.run("query"), connect(config.db_path) as connection:
        view = _resolve_view(connection, input_data.view)
        datasource = _resolve_datasource(connection, str(view["datasource_id"]))
        filter_overrides = _filter_payload_to_list(input_data.filter_overrides)
        warnings = warning_for_datasource_status(str(datasource["status"]))
        if not filter_overrides:
            rows = connection.execute(
                """
                    SELECT *
                    FROM query_results
                    WHERE view_id = ? AND status = 'completed'
                    ORDER BY executed_at DESC, id
                    LIMIT 1
                    """,
                (view["id"],),
            ).fetchall()
        else:
            rows = []
        if rows:
            query_result = _record_from_row(rows[0])
            preview = bound_query_preview(
                query_result["preview_rows"],
                preview_limit=input_data.preview_limit,
                row_count=int(query_result["row_count"]),
                warnings=warnings,
            ).model_dump()
            preview["query_result_id"] = query_result["id"]
            return preview
        if datasource["status"] == "source_offline":
            raise WorkflowError(
                "SOURCE_UNAVAILABLE",
                "Datasource source is offline and no cached query result exists for this view.",
                {"datasource_id": datasource["id"], "view_id": view["id"]},
            )
        fields = _fields_for_datasource(connection, str(datasource["id"]))
        query_spec = dict(view["query_spec"])
        if filter_overrides:
            query_spec["filters"] = [
                *_filter_payload_to_list(query_spec.get("filters")),
                *filter_overrides,
            ]
        spec = StructuredQuerySpec.model_validate(query_spec)
        query_rows, row_count = _execute_structured_query(
            datasource,
            fields,
            spec,
            allow_virtual_filters=True,
        )
        query_result_id = _insert_query_result(
            connection,
            datasource_id=str(datasource["id"]),
            view_id=str(view["id"]),
            query_spec=query_spec,
            row_count=row_count,
            rows=query_rows,
            warnings=warnings,
        )
        preview = bound_query_preview(
            query_rows,
            preview_limit=input_data.preview_limit,
            row_count=row_count,
            warnings=warnings,
        ).model_dump()
        preview["query_result_id"] = query_result_id
        return preview


def query_datasource(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(QueryDatasourceInput, kwargs, _query_datasource, kwargs.pop("_config", None))


def _query_datasource(input_data: QueryDatasourceInput, config: LookoutConfig) -> dict[str, Any]:
    normalize_query_preview_limit(input_data.preview_limit)
    with _EXPENSIVE_GUARD.run("query"), connect(config.db_path) as connection:
        datasource = _resolve_datasource(connection, input_data.datasource)
        if datasource["status"] == "source_offline":
            raise WorkflowError(
                "SOURCE_UNAVAILABLE",
                "Datasource source is offline; ad hoc queries are unavailable.",
                {"datasource_id": datasource["id"], "status": datasource["status"]},
            )
        fields = _fields_for_datasource(connection, str(datasource["id"]))
        spec = StructuredQuerySpec.model_validate(input_data.query_spec)
        query_rows, row_count = _execute_structured_query(datasource, fields, spec)
        warnings = warning_for_datasource_status(str(datasource["status"]))
        query_result_id = _insert_query_result(
            connection,
            datasource_id=str(datasource["id"]),
            view_id=None,
            query_spec=input_data.query_spec,
            row_count=row_count,
            rows=query_rows,
            warnings=warnings,
        )
        preview = bound_query_preview(
            query_rows,
            preview_limit=input_data.preview_limit,
            row_count=row_count,
            warnings=warnings,
        ).model_dump()
        preview["query_result_id"] = query_result_id
        return preview


def compare_periods(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(ComparePeriodsInput, kwargs, _compare_periods, kwargs.pop("_config", None))


def _period_label(period: Mapping[str, Any]) -> str:
    return json.dumps(dict(period), sort_keys=True, separators=(",", ":"))


def _compare_periods(input_data: ComparePeriodsInput, config: LookoutConfig) -> dict[str, Any]:
    normalize_query_preview_limit(input_data.preview_limit)
    with _EXPENSIVE_GUARD.run("query"):  # noqa: SIM117
        with connect(config.db_path) as connection:
            datasource = _resolve_datasource(connection, input_data.datasource)
            if datasource["status"] == "source_offline":
                raise WorkflowError(
                    "SOURCE_UNAVAILABLE",
                    "Datasource source is offline; period comparisons are unavailable.",
                    {"datasource_id": datasource["id"], "status": datasource["status"]},
                )
            fields = _fields_for_datasource(connection, str(datasource["id"]))
            metric = _resolve_field(fields, input_data.metric, role="measure")
            period_field = _resolve_field(fields, input_data.period_field, role="temporal")
            dimensions = [_resolve_field(fields, dimension) for dimension in input_data.dimensions]
            warnings = warning_for_datasource_status(str(datasource["status"]))

            dimension_values = [_representative_values(field)[:4] for field in dimensions]
            if not dimension_values:
                combinations: list[tuple[Any, ...]] = [()]
            elif len(dimension_values) == 1:
                combinations = [(value,) for value in dimension_values[0]]
            else:
                combinations = [
                    (left, right) for left in dimension_values[0] for right in dimension_values[1]
                ]

            rows: list[dict[str, Any]] = []
            current_total = 0
            comparison_total = 0
            for index, combination in enumerate(combinations):
                current = _hash_int(
                    datasource["id"],
                    metric["id"],
                    "current",
                    index,
                    maximum=400_000,
                )
                comparison_value = _hash_int(
                    datasource["id"],
                    metric["id"],
                    "comparison",
                    index,
                    maximum=400_000,
                )
                delta = current - comparison_value
                pct_delta = None if comparison_value == 0 else round(delta / comparison_value, 4)
                row = {
                    str(field["name"]): combination[position]
                    for position, field in enumerate(dimensions)
                }
                row.update(
                    {
                        "current_value": current,
                        "comparison_value": comparison_value,
                        "delta": delta,
                        "pct_delta": pct_delta,
                    }
                )
                rows.append(row)
                current_total += current
                comparison_total += comparison_value

            total_delta = current_total - comparison_total
            comparison_summary = {
                "metric": metric["name"],
                "period_field": period_field["name"],
                "current_period": input_data.current_period,
                "comparison_period": input_data.comparison_period,
                "current_total": current_total,
                "comparison_total": comparison_total,
                "delta": total_delta,
                "pct_delta": None
                if comparison_total == 0
                else round(total_delta / comparison_total, 4),
                "current_period_label": _period_label(input_data.current_period),
                "comparison_period_label": _period_label(input_data.comparison_period),
            }
            preview = bound_query_preview(
                rows,
                preview_limit=input_data.preview_limit,
                row_count=len(rows),
                warnings=warnings,
            ).model_dump()
            preview["comparison"] = comparison_summary
            return preview


def render_view_image(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(RenderViewImageInput, kwargs, _render_view_image, kwargs.pop("_config", None))


def _render_view_image(input_data: RenderViewImageInput, config: LookoutConfig) -> dict[str, Any]:
    return _render_artifact(
        config,
        target_type="view",
        target_value=input_data.view,
        width=input_data.width,
        height=input_data.height,
    )


def render_workbook_image(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(
        RenderWorkbookImageInput,
        kwargs,
        _render_workbook_image,
        kwargs.pop("_config", None),
    )


def _render_workbook_image(
    input_data: RenderWorkbookImageInput,
    config: LookoutConfig,
) -> dict[str, Any]:
    return _render_artifact(
        config,
        target_type="workbook",
        target_value=input_data.workbook,
        width=input_data.width,
        height=input_data.height,
    )


def _render_artifact(
    config: LookoutConfig,
    *,
    target_type: Literal["view", "workbook"],
    target_value: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    if width * height > MAX_RENDER_PIXELS:
        raise WorkflowError(
            "LIMIT_EXCEEDED",
            "Requested render dimensions are too large.",
            {"max_pixels": MAX_RENDER_PIXELS, "requested_pixels": width * height},
        )
    with _EXPENSIVE_GUARD.run("render"):  # noqa: SIM117
        with connect(config.db_path) as connection:
            if target_type == "view":
                target = _resolve_view(connection, target_value)
                target_id = str(target["id"])
                title = str(target["title"])
                chart_type = str(target["chart_type"])
                warnings = warning_for_datasource_status(str(target["datasource_status"]))
                workbook_id: str | None = None
                view_id: str | None = target_id
            else:
                target = _resolve_workbook(connection, target_value)
                target_id = str(target["id"])
                title = str(target["title"])
                chart_type = None
                view_rows = [
                    view for view in _all_views(connection) if view["workbook_id"] == target_id
                ]
                warnings = [
                    warning
                    for status in sorted({str(view["datasource_status"]) for view in view_rows})
                    for warning in warning_for_datasource_status(status)
                ]
                workbook_id = target_id
                view_id = None

            render_id = deterministic_id(
                "rnd",
                f"render:{target_type}:{target_id}:{width}:{height}",
            )
            artifact_path = f"renders/{render_id}.svg"
            target_path = _safe_artifact_path(config.fs_root, artifact_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            escaped_title = html.escape(title)
            target_path.write_text(
                "\n".join(
                    [
                        (
                            '<svg xmlns="http://www.w3.org/2000/svg" '
                            f'width="{width}" height="{height}">'
                        ),
                        f"<title>{escaped_title}</title>",
                        f'<rect width="{width}" height="{height}" fill="#f8fafc"/>',
                        (
                            '<text x="32" y="48" font-size="28" fill="#111827">'
                            f"{escaped_title}</text>"
                        ),
                        (
                            '<text x="32" y="88" font-size="16" fill="#475569">'
                            f"Lookout deterministic {target_type} render</text>"
                        ),
                        "</svg>",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO renders (
                    id, workbook_id, view_id, chart_type, artifact_path, width, height,
                    status, warnings, visual_config, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?)
                """,
                (
                    render_id,
                    workbook_id,
                    view_id,
                    chart_type,
                    artifact_path,
                    width,
                    height,
                    json.dumps([warning.code for warning in warnings], sort_keys=True),
                    json.dumps({"target_type": target_type, "title": title}, sort_keys=True),
                    TOOL_TIMESTAMP,
                ),
            )
            return {
                "render_id": render_id,
                "artifact_path": artifact_path,
                "width": width,
                "height": height,
                "status": "ready",
                "warnings": [warning.model_dump() for warning in warnings],
            }


def export_view_data(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(ExportViewDataInput, kwargs, _export_view_data, kwargs.pop("_config", None))


def _export_view_data(input_data: ExportViewDataInput, config: LookoutConfig) -> dict[str, Any]:
    with _EXPENSIVE_GUARD.run("export"):
        data = _get_view_data(
            GetViewDataInput(view=input_data.view, preview_limit=MAX_QUERY_ROWS),
            config,
        )
        if "error" in data:
            return data
        query_result_id = str(data["query_result_id"])
        return _export_query_result_by_id(config, query_result_id, input_data.format)


def export_query_result(**kwargs: Any) -> dict[str, Any]:
    return _run_tool(
        ExportQueryResultInput,
        kwargs,
        _export_query_result,
        kwargs.pop("_config", None),
    )


def _export_query_result(
    input_data: ExportQueryResultInput,
    config: LookoutConfig,
) -> dict[str, Any]:
    return _export_query_result_by_id(config, input_data.query_result_id, input_data.format)


def _export_query_result_by_id(
    config: LookoutConfig,
    query_result_id: str,
    export_format: ExportFormat,
) -> dict[str, Any]:
    with _EXPENSIVE_GUARD.run("export"):
        validate_prefixed_id(query_result_id, "run")
        with connect(config.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM query_results WHERE id = ? AND status = 'completed'",
                (query_result_id,),
            ).fetchone()
            if row is None:
                raise WorkflowError(
                    "NOT_FOUND",
                    "Query result was not found.",
                    {"query_result_id": query_result_id},
                )
            query_result = _record_from_row(row)
            rows = list(query_result["preview_rows"])
            row_count = int(query_result["row_count"])
            if row_count > MAX_EXPORT_ROWS:
                raise WorkflowError(
                    "LIMIT_EXCEEDED",
                    "Query result is too large for the offline export cap.",
                    {"max": MAX_EXPORT_ROWS, "row_count": row_count},
                )
            export_id = deterministic_id("exp", f"export:{query_result_id}:{export_format}")
            artifact_path = f"exports/{export_id}.{export_format}"
            target_path = _safe_artifact_path(config.fs_root, artifact_path)
            try:
                _write_export_file(target_path, rows, export_format)
            except OSError as exc:
                raise WorkflowError(
                    "EXPORT_FAILED",
                    "Failed to write export artifact.",
                    {"artifact_path": artifact_path},
                ) from exc
            connection.execute(
                """
                INSERT OR REPLACE INTO exports (
                    id, query_result_id, view_id, format, artifact_path, row_count,
                    status, metadata, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'ready', ?, ?)
                """,
                (
                    export_id,
                    query_result_id,
                    query_result["view_id"],
                    export_format,
                    artifact_path,
                    row_count,
                    json.dumps({"source": "tool"}, sort_keys=True),
                    TOOL_TIMESTAMP,
                ),
            )
            datasource = _resolve_datasource(connection, str(query_result["datasource_id"]))
            return {
                "export_id": export_id,
                "artifact_path": artifact_path,
                "format": export_format,
                "row_count": row_count,
                "status": "ready",
                "warnings": _warnings_dicts(str(datasource["status"])),
            }
