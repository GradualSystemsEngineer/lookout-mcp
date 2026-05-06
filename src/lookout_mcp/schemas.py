"""Pydantic schemas shared by MCP tools, persistence, and local tests."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DatasourceStatus = Literal["available", "cache_stale", "source_offline"]
DataType = Literal["string", "integer", "decimal", "date", "datetime", "boolean"]
SemanticRole = Literal["identifier", "dimension", "measure", "temporal"]
DefaultAggregation = Literal["sum", "avg", "min", "max", "count", "count_distinct"]
ChartType = Literal["bar", "pie", "treemap", "line", "histogram"]
QueryResultStatus = Literal["completed", "failed"]
ArtifactStatus = Literal["ready", "failed"]

ID_PREFIXES = {
    "datasource": "ds",
    "field": "fld",
    "workbook": "wb",
    "view": "view",
    "query_result": "run",
    "export": "exp",
    "render": "rnd",
}

_ID_PATTERNS = {
    prefix: re.compile(rf"^{prefix}_[0-9a-f]{{12}}$") for prefix in ID_PREFIXES.values()
}


def deterministic_id(prefix: str, natural_key: str) -> str:
    """Build a stable Lookout ID from a type prefix and natural seed key."""

    if prefix not in _ID_PATTERNS:
        msg = f"Unknown Lookout ID prefix: {prefix}"
        raise ValueError(msg)
    digest = hashlib.sha256(natural_key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def validate_prefixed_id(value: str, prefix: str) -> str:
    """Validate a stable Lookout ID and return it unchanged."""

    pattern = _ID_PATTERNS.get(prefix)
    if pattern is None:
        msg = f"Unknown Lookout ID prefix: {prefix}"
        raise ValueError(msg)
    if not pattern.fullmatch(value):
        msg = f"Expected ID format {prefix}_<12 lowercase hex>"
        raise ValueError(msg)
    return value


class StrictModel(BaseModel):
    """Base model for structured Lookout records."""

    model_config = ConfigDict(extra="forbid")


class HealthCheckResult(StrictModel):
    """Output returned by the bootstrap health check."""

    status: str
    service: str
    db_path: Path
    fs_root: Path
    log_level: str


class DatasourceRecord(StrictModel):
    id: str
    name: str
    label: str
    description: str
    theme: str
    status: DatasourceStatus
    connection_type: str
    tags: list[str] = Field(default_factory=list)
    default_filters: dict[str, Any] = Field(default_factory=dict)
    row_count: int = Field(ge=0)
    cache_updated_at: str | None = None
    source_updated_at: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["datasource"])


class DatasourceFieldRecord(StrictModel):
    id: str
    datasource_id: str
    name: str
    label: str
    data_type: DataType
    semantic_role: SemanticRole
    description: str
    default_aggregation: DefaultAggregation | None = None
    is_filterable: bool
    is_sortable: bool
    allowed_operators: list[str] = Field(min_length=1)
    ordinal: int = Field(ge=1)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["field"])

    @field_validator("datasource_id")
    @classmethod
    def validate_datasource_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["datasource"])


class WorkbookRecord(StrictModel):
    id: str
    name: str
    title: str
    description: str
    project: str
    owner: str
    tags: list[str] = Field(default_factory=list)
    default_filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["workbook"])


class ViewRecord(StrictModel):
    id: str
    workbook_id: str
    datasource_id: str
    name: str
    title: str
    description: str
    chart_type: ChartType
    chart_config: dict[str, Any]
    query_spec: dict[str, Any]
    default_filters: dict[str, Any] = Field(default_factory=dict)
    visual_config: dict[str, Any] = Field(default_factory=dict)
    position: int = Field(ge=1)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["view"])

    @field_validator("workbook_id")
    @classmethod
    def validate_workbook_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["workbook"])

    @field_validator("datasource_id")
    @classmethod
    def validate_datasource_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["datasource"])


class QueryResultRecord(StrictModel):
    id: str
    datasource_id: str
    view_id: str | None = None
    query_spec: dict[str, Any]
    row_count: int = Field(ge=0)
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)
    status: QueryResultStatus
    warnings: list[str] = Field(default_factory=list)
    executed_at: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["query_result"])

    @field_validator("datasource_id")
    @classmethod
    def validate_datasource_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["datasource"])

    @field_validator("view_id")
    @classmethod
    def validate_view_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_prefixed_id(value, ID_PREFIXES["view"])


class ExportRecord(StrictModel):
    id: str
    query_result_id: str | None = None
    view_id: str | None = None
    format: Literal["csv", "json"]
    artifact_path: str
    row_count: int = Field(ge=0)
    status: ArtifactStatus
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["export"])

    @field_validator("query_result_id")
    @classmethod
    def validate_query_result_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_prefixed_id(value, ID_PREFIXES["query_result"])

    @field_validator("view_id")
    @classmethod
    def validate_view_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_prefixed_id(value, ID_PREFIXES["view"])


class RenderRecord(StrictModel):
    id: str
    workbook_id: str | None = None
    view_id: str | None = None
    chart_type: ChartType | None = None
    artifact_path: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    status: ArtifactStatus
    warnings: list[str] = Field(default_factory=list)
    visual_config: dict[str, Any] = Field(default_factory=dict)
    created_at: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_prefixed_id(value, ID_PREFIXES["render"])

    @field_validator("workbook_id")
    @classmethod
    def validate_workbook_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_prefixed_id(value, ID_PREFIXES["workbook"])

    @field_validator("view_id")
    @classmethod
    def validate_view_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_prefixed_id(value, ID_PREFIXES["view"])
