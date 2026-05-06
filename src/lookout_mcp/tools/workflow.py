"""Agent-facing workflow helpers for compact, bounded MCP tool responses."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

from lookout_mcp.errors import error_envelope
from lookout_mcp.schemas import DatasourceRecord, StrictModel

LIST_DEFAULT_PAGE_SIZE = 10
LIST_MAX_PAGE_SIZE = 25
QUERY_PREVIEW_DEFAULT_ROWS = 100
QUERY_PREVIEW_MAX_ROWS = 1_000
CURSOR_VERSION = 1

WarningCode = Literal["CACHE_STALE", "RESULT_TRUNCATED", "SOURCE_DEGRADED"]


class WorkflowError(ValueError):
    """Structured error that can be returned through the standard envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_envelope(self) -> dict[str, dict[str, Any]]:
        return error_envelope(self.code, self.message, self.details)


class InvalidCursorError(WorkflowError):
    """Raised when an opaque cursor is malformed or no longer matches a request."""

    def __init__(self, message: str = "Cursor is invalid.", **details: Any) -> None:
        super().__init__("INVALID_CURSOR", message, details)


class AmbiguousMatchError(WorkflowError):
    """Raised when deterministic fuzzy matching cannot choose a single target."""

    def __init__(self, candidates: Sequence[MatchCandidate]) -> None:
        super().__init__(
            "AMBIGUOUS_MATCH",
            "The query matched multiple candidates. Choose one candidate ID explicitly.",
            {"candidates": [candidate.model_dump() for candidate in candidates]},
        )


class TokenLimitError(WorkflowError):
    """Raised when a request asks for an unbounded or over-limit inline result."""


class ToolWarning(StrictModel):
    code: WarningCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CursorPayload(StrictModel):
    version: int
    sort_key: str
    last_id: str
    filter_hash: str


class PageEnvelope(StrictModel):
    row_count: int = Field(ge=0)
    returned_row_count: int = Field(ge=0)
    truncated: bool
    next_cursor: str | None = None


class CompactDatasourceItem(StrictModel):
    id: str
    label: str
    status: str
    theme: str
    row_count: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)


class CompactListOutput(StrictModel):
    items: list[dict[str, Any]]
    row_count: int = Field(ge=0)
    returned_row_count: int = Field(ge=0)
    truncated: bool
    next_cursor: str | None = None
    warnings: list[ToolWarning] = Field(default_factory=list)


class QueryPreviewOutput(StrictModel):
    rows: list[dict[str, Any]]
    row_count: int = Field(ge=0)
    returned_row_count: int = Field(ge=0)
    truncated: bool
    next_cursor: str | None = None
    warnings: list[ToolWarning] = Field(default_factory=list)


class MatchCandidate(StrictModel):
    id: str
    kind: str
    label: str
    score: int
    matched_fields: list[str] = Field(default_factory=list)


def normalize_list_page_size(page_size: int | None) -> int:
    """Return a safe metadata-list page size or raise a structured error."""

    if page_size is None:
        return LIST_DEFAULT_PAGE_SIZE
    if page_size < 1 or page_size > LIST_MAX_PAGE_SIZE:
        raise TokenLimitError(
            "INVALID_PAGE_SIZE",
            f"page_size must be between 1 and {LIST_MAX_PAGE_SIZE}.",
            {
                "default": LIST_DEFAULT_PAGE_SIZE,
                "max": LIST_MAX_PAGE_SIZE,
                "requested": page_size,
            },
        )
    return page_size


def normalize_query_preview_limit(limit: int | None) -> int:
    """Return a safe inline query preview limit or raise a structured error."""

    if limit is None:
        return QUERY_PREVIEW_DEFAULT_ROWS
    if limit < 1 or limit > QUERY_PREVIEW_MAX_ROWS:
        raise TokenLimitError(
            "QUERY_PREVIEW_LIMIT_EXCEEDED",
            f"preview_limit must be between 1 and {QUERY_PREVIEW_MAX_ROWS}.",
            {
                "default": QUERY_PREVIEW_DEFAULT_ROWS,
                "max": QUERY_PREVIEW_MAX_ROWS,
                "requested": limit,
                "recovery_hint": "Use an export tool for larger result sets.",
            },
        )
    return limit


def filter_hash(filters: Mapping[str, Any] | None = None) -> str:
    """Build a stable hash for cursor/request compatibility checks."""

    encoded = json.dumps(filters or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def encode_cursor(*, sort_key: str, last_id: str, filter_hash_value: str) -> str:
    payload = CursorPayload(
        version=CURSOR_VERSION,
        sort_key=sort_key,
        last_id=last_id,
        filter_hash=filter_hash_value,
    )
    encoded = json.dumps(payload.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def decode_cursor(
    cursor: str,
    *,
    expected_sort_key: str | None = None,
    expected_filter_hash: str | None = None,
) -> CursorPayload:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = CursorPayload.model_validate_json(decoded)
    except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
        raise InvalidCursorError("Cursor is not valid base64url JSON.") from exc

    if payload.version != CURSOR_VERSION:
        raise InvalidCursorError(
            "Cursor version is not supported.",
            version=payload.version,
            supported_version=CURSOR_VERSION,
        )
    if expected_sort_key is not None and payload.sort_key != expected_sort_key:
        raise InvalidCursorError(
            "Cursor sort key does not match this request.",
            expected_sort_key=expected_sort_key,
            cursor_sort_key=payload.sort_key,
        )
    if expected_filter_hash is not None and payload.filter_hash != expected_filter_hash:
        raise InvalidCursorError(
            "Cursor filters do not match this request.",
            expected_filter_hash=expected_filter_hash,
            cursor_filter_hash=payload.filter_hash,
        )
    return payload


def compact_datasource_item(
    datasource: DatasourceRecord | Mapping[str, Any],
) -> CompactDatasourceItem:
    """Project a datasource into the compact shape used by list responses."""

    if isinstance(datasource, DatasourceRecord):
        return CompactDatasourceItem(
            id=datasource.id,
            label=datasource.label,
            status=datasource.status,
            theme=datasource.theme,
            row_count=datasource.row_count,
            tags=datasource.tags,
        )
    return CompactDatasourceItem(
        id=str(datasource["id"]),
        label=str(datasource["label"]),
        status=str(datasource["status"]),
        theme=str(datasource["theme"]),
        row_count=int(datasource["row_count"]),
        tags=list(datasource.get("tags", [])),
    )


def compact_list_output(
    items: Sequence[BaseModel | Mapping[str, Any]],
    *,
    row_count: int,
    next_cursor: str | None = None,
    warnings: Sequence[ToolWarning] = (),
) -> CompactListOutput:
    compact_items = [
        item.model_dump(exclude_none=True) if isinstance(item, BaseModel) else dict(item)
        for item in items
    ]
    return CompactListOutput(
        items=compact_items,
        row_count=row_count,
        returned_row_count=len(compact_items),
        truncated=next_cursor is not None or len(compact_items) < row_count,
        next_cursor=next_cursor,
        warnings=list(warnings),
    )


def bound_query_preview(
    rows: Sequence[Mapping[str, Any]],
    *,
    preview_limit: int | None = None,
    row_count: int | None = None,
    next_cursor: str | None = None,
    warnings: Sequence[ToolWarning] = (),
) -> QueryPreviewOutput:
    limit = normalize_query_preview_limit(preview_limit)
    total = len(rows) if row_count is None else row_count
    preview_rows = [dict(row) for row in rows[:limit]]
    truncated = total > len(preview_rows) or next_cursor is not None
    merged_warnings = list(warnings)
    if truncated and not any(warning.code == "RESULT_TRUNCATED" for warning in merged_warnings):
        merged_warnings.append(result_truncated_warning(total, len(preview_rows)))
    return QueryPreviewOutput(
        rows=preview_rows,
        row_count=total,
        returned_row_count=len(preview_rows),
        truncated=truncated,
        next_cursor=next_cursor,
        warnings=merged_warnings,
    )


def warning_for_datasource_status(status: str) -> list[ToolWarning]:
    if status == "cache_stale":
        return [
            ToolWarning(
                code="CACHE_STALE",
                message="Datasource cache is stale; results may lag the source system.",
                details={"status": status},
            )
        ]
    if status == "source_offline":
        return [
            ToolWarning(
                code="SOURCE_DEGRADED",
                message="Datasource source is offline; serving deterministic cached metadata only.",
                details={"status": status},
            )
        ]
    return []


def result_truncated_warning(row_count: int, returned_row_count: int) -> ToolWarning:
    return ToolWarning(
        code="RESULT_TRUNCATED",
        message="Inline rows were truncated to the preview limit.",
        details={"row_count": row_count, "returned_row_count": returned_row_count},
    )


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(value.lower()))


def _stringify_search_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        return " ".join(_stringify_search_value(item) for item in value)
    return str(value)


def fuzzy_candidates(
    query: str,
    records: Sequence[Mapping[str, Any]],
    *,
    kind: str,
    searchable_fields: Sequence[str] = (
        "id",
        "name",
        "title",
        "label",
        "description",
        "tags",
        "field_names",
    ),
) -> list[MatchCandidate]:
    """Score deterministic fuzzy candidates without choosing among ties."""

    normalized_query = query.strip().lower()
    query_tokens = _tokens(normalized_query)
    candidates: list[MatchCandidate] = []
    if not normalized_query:
        return candidates

    for record in records:
        score = 0
        matched_fields: list[str] = []
        for field_name in searchable_fields:
            if field_name not in record:
                continue
            value = _stringify_search_value(record[field_name]).lower()
            if not value:
                continue
            field_tokens = _tokens(value)
            if normalized_query == value:
                score += 1_000 if field_name == "id" else 500
                matched_fields.append(field_name)
            elif normalized_query in value:
                score += 250
                matched_fields.append(field_name)
            token_matches = query_tokens & field_tokens
            if token_matches:
                score += len(token_matches) * 25
                if field_name not in matched_fields:
                    matched_fields.append(field_name)
            if query_tokens and query_tokens.issubset(field_tokens):
                score += 100

        if score > 0:
            label = str(
                record.get("title") or record.get("label") or record.get("name") or record["id"]
            )
            candidates.append(
                MatchCandidate(
                    id=str(record["id"]),
                    kind=kind,
                    label=label,
                    score=score,
                    matched_fields=matched_fields,
                )
            )

    return sorted(
        candidates,
        key=lambda candidate: (-candidate.score, candidate.kind, candidate.label, candidate.id),
    )


def resolve_fuzzy_match(
    query: str,
    records: Sequence[Mapping[str, Any]],
    *,
    kind: str,
    searchable_fields: Sequence[str] = (
        "id",
        "name",
        "title",
        "label",
        "description",
        "tags",
        "field_names",
    ),
) -> MatchCandidate | None:
    """Resolve one deterministic fuzzy match or raise AMBIGUOUS_MATCH for ties."""

    candidates = fuzzy_candidates(query, records, kind=kind, searchable_fields=searchable_fields)
    if not candidates:
        return None
    best_score = candidates[0].score
    tied = [candidate for candidate in candidates if candidate.score == best_score]
    if len(tied) > 1:
        raise AmbiguousMatchError(tied)
    return candidates[0]
