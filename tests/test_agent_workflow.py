from __future__ import annotations

import pytest

from lookout_mcp.schemas import DatasourceRecord
from lookout_mcp.tools.registry import MODEL_VISIBLE_TOOL_DESCRIPTIONS, TOOL_REGISTRY
from lookout_mcp.tools.workflow import (
    LIST_DEFAULT_PAGE_SIZE,
    LIST_MAX_PAGE_SIZE,
    QUERY_PREVIEW_DEFAULT_ROWS,
    QUERY_PREVIEW_MAX_ROWS,
    AmbiguousMatchError,
    InvalidCursorError,
    TokenLimitError,
    bound_query_preview,
    compact_datasource_item,
    compact_list_output,
    decode_cursor,
    encode_cursor,
    filter_hash,
    normalize_list_page_size,
    normalize_query_preview_limit,
    resolve_fuzzy_match,
    result_truncated_warning,
    warning_for_datasource_status,
)

PLANNED_TOOLS = {
    "search_content",
    "list_datasources",
    "get_datasource",
    "get_field_values",
    "list_workbooks",
    "get_workbook",
    "list_views",
    "get_view",
    "get_view_data",
    "query_datasource",
    "compare_periods",
    "render_view_image",
    "render_workbook_image",
    "export_view_data",
    "export_query_result",
}


@pytest.mark.unit
def test_tool_registry_covers_all_planned_tools_with_descriptions_and_contracts() -> None:
    assert set(TOOL_REGISTRY) == PLANNED_TOOLS
    assert set(MODEL_VISIBLE_TOOL_DESCRIPTIONS) == PLANNED_TOOLS

    for name, definition in TOOL_REGISTRY.items():
        assert definition.name == name
        assert definition.description == MODEL_VISIBLE_TOOL_DESCRIPTIONS[name]
        assert definition.input_model.endswith("Input")
        assert definition.output_model.endswith("Output")
        assert definition.common_errors
        assert definition.notes
        assert definition.examples


@pytest.mark.unit
def test_list_page_size_defaults_and_rejects_over_limit() -> None:
    assert normalize_list_page_size(None) == LIST_DEFAULT_PAGE_SIZE
    assert normalize_list_page_size(LIST_MAX_PAGE_SIZE) == LIST_MAX_PAGE_SIZE

    with pytest.raises(TokenLimitError) as exc_info:
        normalize_list_page_size(LIST_MAX_PAGE_SIZE + 1)

    assert exc_info.value.to_envelope()["error"]["code"] == "INVALID_PAGE_SIZE"
    assert exc_info.value.details["max"] == LIST_MAX_PAGE_SIZE


@pytest.mark.unit
def test_query_preview_defaults_and_rejects_over_limit() -> None:
    assert normalize_query_preview_limit(None) == QUERY_PREVIEW_DEFAULT_ROWS
    assert normalize_query_preview_limit(QUERY_PREVIEW_MAX_ROWS) == QUERY_PREVIEW_MAX_ROWS

    with pytest.raises(TokenLimitError) as exc_info:
        normalize_query_preview_limit(QUERY_PREVIEW_MAX_ROWS + 1)

    envelope = exc_info.value.to_envelope()
    assert envelope["error"]["code"] == "QUERY_PREVIEW_LIMIT_EXCEEDED"
    assert (
        envelope["error"]["details"]["recovery_hint"]
        == "Use an export tool for larger result sets."
    )


@pytest.mark.unit
def test_invalid_and_mismatched_cursors_return_invalid_cursor() -> None:
    with pytest.raises(InvalidCursorError) as invalid:
        decode_cursor("not-json")

    assert invalid.value.to_envelope()["error"]["code"] == "INVALID_CURSOR"

    cursor = encode_cursor(
        sort_key="label",
        last_id="ds_0123abcdef89",
        filter_hash_value=filter_hash({"status": "available"}),
    )

    with pytest.raises(InvalidCursorError) as mismatched:
        decode_cursor(
            cursor,
            expected_sort_key="label",
            expected_filter_hash=filter_hash({"status": "cache_stale"}),
        )

    assert mismatched.value.to_envelope()["error"]["code"] == "INVALID_CURSOR"
    assert "expected_filter_hash" in mismatched.value.details


@pytest.mark.unit
def test_compact_datasource_list_shape_omits_verbose_fields() -> None:
    datasource = DatasourceRecord(
        id="ds_0123abcdef89",
        name="retail_sales",
        label="Retail Sales",
        description="Order-level retail revenue and margin metrics.",
        theme="retail sales",
        status="available",
        connection_type="sqlite_cache",
        tags=["retail", "seeded"],
        default_filters={"period": "last_12_months"},
        row_count=482_400,
    )

    item = compact_datasource_item(datasource)
    output = compact_list_output([item], row_count=1)

    assert output.returned_row_count == 1
    assert output.truncated is False
    assert set(output.items[0]) == {"id", "label", "status", "theme", "row_count", "tags"}
    assert "description" not in output.items[0]
    assert "default_filters" not in output.items[0]


@pytest.mark.unit
def test_ambiguous_search_requires_explicit_candidate_choice() -> None:
    records = [
        {
            "id": "view_0123abcdef89",
            "title": "Revenue by Region",
            "description": "Regional revenue.",
            "tags": ["revenue"],
            "field_names": ["region", "revenue"],
        },
        {
            "id": "view_abcdef012389",
            "title": "Revenue by Category",
            "description": "Category revenue.",
            "tags": ["revenue"],
            "field_names": ["category", "revenue"],
        },
    ]

    with pytest.raises(AmbiguousMatchError) as exc_info:
        resolve_fuzzy_match("revenue", records, kind="view")

    envelope = exc_info.value.to_envelope()
    assert envelope["error"]["code"] == "AMBIGUOUS_MATCH"
    assert [candidate["id"] for candidate in envelope["error"]["details"]["candidates"]] == [
        "view_abcdef012389",
        "view_0123abcdef89",
    ]


@pytest.mark.unit
def test_common_warning_helpers_cover_stale_degraded_and_truncated_states() -> None:
    stale = warning_for_datasource_status("cache_stale")
    degraded = warning_for_datasource_status("source_offline")
    truncated = result_truncated_warning(150, 100)

    assert [warning.code for warning in stale] == ["CACHE_STALE"]
    assert [warning.code for warning in degraded] == ["SOURCE_DEGRADED"]
    assert truncated.code == "RESULT_TRUNCATED"
    assert truncated.details == {"row_count": 150, "returned_row_count": 100}


@pytest.mark.unit
def test_query_preview_is_bounded_and_reports_truncation() -> None:
    rows = [{"index": index} for index in range(QUERY_PREVIEW_MAX_ROWS + 500)]

    default_preview = bound_query_preview(rows)
    max_preview = bound_query_preview(rows, preview_limit=QUERY_PREVIEW_MAX_ROWS)

    assert default_preview.returned_row_count == QUERY_PREVIEW_DEFAULT_ROWS
    assert default_preview.row_count == len(rows)
    assert default_preview.truncated is True
    assert [warning.code for warning in default_preview.warnings] == ["RESULT_TRUNCATED"]
    assert max_preview.returned_row_count == QUERY_PREVIEW_MAX_ROWS
    assert len(max_preview.rows) == QUERY_PREVIEW_MAX_ROWS
