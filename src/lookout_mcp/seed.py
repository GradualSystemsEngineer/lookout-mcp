"""Deterministic domain seed data for the offline Lookout mock."""
# ruff: noqa: E501

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lookout_mcp.schemas import (
    ChartType,
    DatasourceFieldRecord,
    DatasourceRecord,
    DatasourceStatus,
    DataType,
    DefaultAggregation,
    ExportRecord,
    QueryResultRecord,
    RenderRecord,
    SemanticRole,
    ViewRecord,
    WorkbookRecord,
    deterministic_id,
)

SEED_TIMESTAMP = "2026-01-15T09:30:00Z"
ExportFormat = Literal["csv", "json"]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    data_type: DataType
    semantic_role: SemanticRole
    description: str
    default_aggregation: DefaultAggregation | None = None
    filterable: bool = True
    sortable: bool = True


@dataclass(frozen=True)
class ViewSpec:
    key: str
    title: str
    chart_type: ChartType
    dimension: str
    measure: str
    description: str
    default_filters: dict[str, str]


@dataclass(frozen=True)
class DatasourceSpec:
    key: str
    label: str
    description: str
    theme: str
    status: DatasourceStatus
    row_count: int
    fields: tuple[FieldSpec, ...]
    views: tuple[ViewSpec, ...]


@dataclass(frozen=True)
class SeedRecords:
    datasources: list[DatasourceRecord]
    datasource_fields: list[DatasourceFieldRecord]
    workbooks: list[WorkbookRecord]
    views: list[ViewRecord]
    query_results: list[QueryResultRecord]
    exports: list[ExportRecord]
    renders: list[RenderRecord]


DATA_SOURCES: tuple[DatasourceSpec, ...] = (
    DatasourceSpec(
        key="retail_sales",
        label="Retail Sales",
        description="Order-level retail revenue, margin, product, channel, and region metrics.",
        theme="retail sales",
        status="available",
        row_count=482_400,
        fields=(
            FieldSpec("order_id", "Order ID", "string", "identifier", "Stable order key."),
            FieldSpec("order_date", "Order Date", "date", "temporal", "Date the order closed."),
            FieldSpec("region", "Region", "string", "dimension", "Sales reporting region."),
            FieldSpec(
                "channel", "Channel", "string", "dimension", "Store, ecommerce, or partner channel."
            ),
            FieldSpec(
                "category", "Category", "string", "dimension", "Product merchandising category."
            ),
            FieldSpec("revenue", "Revenue", "decimal", "measure", "Net booked revenue.", "sum"),
            FieldSpec(
                "gross_margin",
                "Gross Margin",
                "decimal",
                "measure",
                "Revenue less product cost.",
                "sum",
            ),
            FieldSpec(
                "order_value", "Order Value", "decimal", "measure", "Individual order value.", "avg"
            ),
        ),
        views=(
            ViewSpec(
                "q1_revenue_region",
                "Q1 Revenue by Region",
                "bar",
                "region",
                "revenue",
                "Compare Q1 revenue across regions.",
                {"quarter": "Q1"},
            ),
            ViewSpec(
                "category_mix",
                "Product Category Mix",
                "pie",
                "category",
                "revenue",
                "Show revenue share by merchandising category.",
                {"period": "last_quarter"},
            ),
            ViewSpec(
                "monthly_revenue",
                "Monthly Revenue Trend",
                "line",
                "order_date",
                "revenue",
                "Track month-over-month revenue movement.",
                {"period": "last_12_months"},
            ),
            ViewSpec(
                "category_region_tree",
                "Category Revenue Treemap",
                "treemap",
                "category",
                "gross_margin",
                "Spot high-margin category concentration.",
                {"period": "year_to_date"},
            ),
            ViewSpec(
                "order_value_histogram",
                "Order Value Distribution",
                "histogram",
                "order_value",
                "order_value",
                "Bucket order values for basket analysis.",
                {"period": "last_90_days"},
            ),
        ),
    ),
    DatasourceSpec(
        key="store_performance",
        label="Store Performance",
        description="Store KPI snapshots including same-store growth, traffic, labor, and shrink.",
        theme="store performance",
        status="cache_stale",
        row_count=37_200,
        fields=(
            FieldSpec("store_id", "Store ID", "string", "identifier", "Stable store key."),
            FieldSpec("month", "Month", "date", "temporal", "Store reporting month."),
            FieldSpec("region", "Region", "string", "dimension", "Store operating region."),
            FieldSpec(
                "store_format",
                "Store Format",
                "string",
                "dimension",
                "Mall, outlet, flagship, or neighborhood.",
            ),
            FieldSpec("sales", "Sales", "decimal", "measure", "Monthly store sales.", "sum"),
            FieldSpec(
                "same_store_growth",
                "Same-store Sales Growth",
                "decimal",
                "measure",
                "Comparable store growth rate.",
                "avg",
            ),
            FieldSpec(
                "foot_traffic",
                "Foot Traffic",
                "integer",
                "measure",
                "Monthly visitor count.",
                "sum",
            ),
            FieldSpec(
                "labor_hours",
                "Labor Hours",
                "decimal",
                "measure",
                "Scheduled store labor hours.",
                "sum",
            ),
        ),
        views=(
            ViewSpec(
                "top_store_growth",
                "Top Stores by Same-store Growth",
                "bar",
                "store_id",
                "same_store_growth",
                "Pull top stores by same-store sales growth last month.",
                {"period": "last_month"},
            ),
            ViewSpec(
                "format_sales_mix",
                "Sales by Store Format",
                "pie",
                "store_format",
                "sales",
                "Compare store-format contribution to sales.",
                {"period": "last_month"},
            ),
            ViewSpec(
                "traffic_trend",
                "Foot Traffic Trend",
                "line",
                "month",
                "foot_traffic",
                "Track traffic recovery over time.",
                {"period": "last_12_months"},
            ),
            ViewSpec(
                "region_sales_tree",
                "Regional Store Sales Treemap",
                "treemap",
                "region",
                "sales",
                "Locate regional concentration in store sales.",
                {"period": "year_to_date"},
            ),
            ViewSpec(
                "labor_hours_histogram",
                "Labor Hours Distribution",
                "histogram",
                "labor_hours",
                "labor_hours",
                "Understand store labor-hour spread.",
                {"period": "last_quarter"},
            ),
        ),
    ),
    DatasourceSpec(
        key="sales_pipeline",
        label="Sales Pipeline",
        description="Opportunity pipeline facts for stage health, bookings forecast, and aging analysis.",
        theme="sales pipeline",
        status="available",
        row_count=64_800,
        fields=(
            FieldSpec(
                "opportunity_id",
                "Opportunity ID",
                "string",
                "identifier",
                "Stable CRM opportunity key.",
            ),
            FieldSpec(
                "close_date", "Close Date", "date", "temporal", "Expected or actual close date."
            ),
            FieldSpec("segment", "Segment", "string", "dimension", "Customer segment."),
            FieldSpec("stage", "Stage", "string", "dimension", "Current pipeline stage."),
            FieldSpec("owner_region", "Owner Region", "string", "dimension", "Sales owner region."),
            FieldSpec(
                "pipeline_amount",
                "Pipeline Amount",
                "decimal",
                "measure",
                "Open opportunity amount.",
                "sum",
            ),
            FieldSpec(
                "weighted_amount",
                "Weighted Amount",
                "decimal",
                "measure",
                "Probability-weighted pipeline.",
                "sum",
            ),
            FieldSpec(
                "age_days", "Age Days", "integer", "measure", "Opportunity age in days.", "avg"
            ),
        ),
        views=(
            ViewSpec(
                "pipeline_stage_health",
                "Pipeline Health by Stage",
                "bar",
                "stage",
                "pipeline_amount",
                "Export raw rows behind a pipeline health chart.",
                {"period": "current_quarter"},
            ),
            ViewSpec(
                "segment_pipeline_mix",
                "Pipeline Mix by Segment",
                "pie",
                "segment",
                "weighted_amount",
                "Compare segment share of weighted pipeline.",
                {"period": "current_quarter"},
            ),
            ViewSpec(
                "forecast_trend",
                "Forecast Trend",
                "line",
                "close_date",
                "weighted_amount",
                "Track forecast movement by close month.",
                {"period": "next_two_quarters"},
            ),
            ViewSpec(
                "region_pipeline_tree",
                "Pipeline by Owner Region",
                "treemap",
                "owner_region",
                "pipeline_amount",
                "Highlight regional pipeline concentration.",
                {"period": "current_quarter"},
            ),
            ViewSpec(
                "opportunity_age_histogram",
                "Opportunity Age Distribution",
                "histogram",
                "age_days",
                "age_days",
                "Bucket opportunity age for pipeline hygiene.",
                {"stage": "open"},
            ),
        ),
    ),
    DatasourceSpec(
        key="marketing_spend",
        label="Marketing Spend",
        description="Campaign spend, impressions, conversions, and acquisition cost by channel.",
        theme="marketing spend",
        status="source_offline",
        row_count=118_500,
        fields=(
            FieldSpec("campaign_id", "Campaign ID", "string", "identifier", "Stable campaign key."),
            FieldSpec("date", "Date", "date", "temporal", "Campaign delivery date."),
            FieldSpec("channel", "Channel", "string", "dimension", "Marketing delivery channel."),
            FieldSpec("audience", "Audience", "string", "dimension", "Target audience cohort."),
            FieldSpec("spend", "Spend", "decimal", "measure", "Media spend.", "sum"),
            FieldSpec(
                "impressions",
                "Impressions",
                "integer",
                "measure",
                "Delivered ad impressions.",
                "sum",
            ),
            FieldSpec(
                "conversions", "Conversions", "integer", "measure", "Attributed conversions.", "sum"
            ),
            FieldSpec(
                "cac",
                "Customer Acquisition Cost",
                "decimal",
                "measure",
                "Spend per acquired customer.",
                "avg",
            ),
        ),
        views=(
            ViewSpec(
                "spend_by_channel",
                "Spend by Channel",
                "bar",
                "channel",
                "spend",
                "Compare marketing spend across channels.",
                {"period": "last_quarter"},
            ),
            ViewSpec(
                "audience_conversion_mix",
                "Conversions by Audience",
                "pie",
                "audience",
                "conversions",
                "Show conversion share by audience.",
                {"period": "last_quarter"},
            ),
            ViewSpec(
                "cac_trend",
                "CAC Trend",
                "line",
                "date",
                "cac",
                "Track acquisition cost over time.",
                {"period": "last_12_months"},
            ),
            ViewSpec(
                "channel_spend_tree",
                "Channel Spend Treemap",
                "treemap",
                "channel",
                "spend",
                "Spot concentrated media investment.",
                {"period": "year_to_date"},
            ),
            ViewSpec(
                "campaign_spend_histogram",
                "Campaign Spend Distribution",
                "histogram",
                "spend",
                "spend",
                "Bucket campaign spend levels.",
                {"period": "last_quarter"},
            ),
        ),
    ),
    DatasourceSpec(
        key="customer_support",
        label="Customer Support",
        description="Support tickets, response times, SLA attainment, backlog, and satisfaction signals.",
        theme="customer support",
        status="available",
        row_count=211_900,
        fields=(
            FieldSpec(
                "ticket_id", "Ticket ID", "string", "identifier", "Stable support ticket key."
            ),
            FieldSpec("created_date", "Created Date", "date", "temporal", "Ticket creation date."),
            FieldSpec("priority", "Priority", "string", "dimension", "Ticket priority."),
            FieldSpec(
                "product_area",
                "Product Area",
                "string",
                "dimension",
                "Product area associated with the ticket.",
            ),
            FieldSpec("tickets", "Tickets", "integer", "measure", "Ticket count.", "sum"),
            FieldSpec(
                "first_response_minutes",
                "First Response Minutes",
                "integer",
                "measure",
                "Minutes to first response.",
                "avg",
            ),
            FieldSpec("sla_met", "SLA Met", "boolean", "dimension", "Whether the ticket met SLA."),
            FieldSpec("csat", "CSAT", "decimal", "measure", "Customer satisfaction score.", "avg"),
        ),
        views=(
            ViewSpec(
                "tickets_by_priority",
                "Tickets by Priority",
                "bar",
                "priority",
                "tickets",
                "Compare support load by ticket priority.",
                {"period": "last_month"},
            ),
            ViewSpec(
                "product_area_mix",
                "Tickets by Product Area",
                "pie",
                "product_area",
                "tickets",
                "Show ticket mix by product area.",
                {"period": "last_month"},
            ),
            ViewSpec(
                "csat_trend",
                "CSAT Trend",
                "line",
                "created_date",
                "csat",
                "Track satisfaction over time.",
                {"period": "last_12_months"},
            ),
            ViewSpec(
                "area_backlog_tree",
                "Backlog Treemap by Product Area",
                "treemap",
                "product_area",
                "tickets",
                "Identify backlog concentration.",
                {"status": "open"},
            ),
            ViewSpec(
                "response_time_histogram",
                "First Response Distribution",
                "histogram",
                "first_response_minutes",
                "first_response_minutes",
                "Bucket first response times.",
                {"period": "last_month"},
            ),
        ),
    ),
    DatasourceSpec(
        key="inventory_supply_chain",
        label="Inventory Supply Chain",
        description="Inventory positions, vendor fill rates, stockouts, turns, and reorder risk.",
        theme="inventory supply chain",
        status="cache_stale",
        row_count=93_600,
        fields=(
            FieldSpec("sku", "SKU", "string", "identifier", "Stock keeping unit."),
            FieldSpec(
                "snapshot_date", "Snapshot Date", "date", "temporal", "Inventory snapshot date."
            ),
            FieldSpec("category", "Category", "string", "dimension", "Inventory category."),
            FieldSpec("vendor", "Vendor", "string", "dimension", "Primary supplier."),
            FieldSpec(
                "on_hand_units",
                "On-hand Units",
                "integer",
                "measure",
                "Units currently on hand.",
                "sum",
            ),
            FieldSpec(
                "stockout_events",
                "Stockout Events",
                "integer",
                "measure",
                "Count of stockout events.",
                "sum",
            ),
            FieldSpec(
                "inventory_value",
                "Inventory Value",
                "decimal",
                "measure",
                "Inventory value at cost.",
                "sum",
            ),
            FieldSpec(
                "days_of_supply",
                "Days of Supply",
                "decimal",
                "measure",
                "Projected days of supply.",
                "avg",
            ),
        ),
        views=(
            ViewSpec(
                "stockouts_by_category",
                "Stockouts by Category",
                "bar",
                "category",
                "stockout_events",
                "Compare stockout pressure by category.",
                {"period": "last_month"},
            ),
            ViewSpec(
                "vendor_inventory_mix",
                "Inventory by Vendor",
                "pie",
                "vendor",
                "inventory_value",
                "Show inventory value share by vendor.",
                {"period": "current_snapshot"},
            ),
            ViewSpec(
                "supply_trend",
                "Days of Supply Trend",
                "line",
                "snapshot_date",
                "days_of_supply",
                "Track supply coverage over time.",
                {"period": "last_12_months"},
            ),
            ViewSpec(
                "inventory_risk_tree",
                "Inventory Risk Treemap",
                "treemap",
                "category",
                "inventory_value",
                "Spot categories with concentrated inventory risk.",
                {"risk": "elevated"},
            ),
            ViewSpec(
                "supply_histogram",
                "Days of Supply Distribution",
                "histogram",
                "days_of_supply",
                "days_of_supply",
                "Bucket supply coverage levels.",
                {"period": "current_snapshot"},
            ),
        ),
    ),
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _allowed_operators(data_type: DataType) -> list[str]:
    if data_type in {"integer", "decimal"}:
        return ["eq", "neq", "gt", "gte", "lt", "lte", "between"]
    if data_type in {"date", "datetime"}:
        return ["eq", "gte", "lte", "between"]
    if data_type == "boolean":
        return ["eq", "neq"]
    return ["eq", "neq", "in", "contains"]


def _chart_config(view: ViewSpec) -> dict[str, str | int]:
    if view.chart_type == "histogram":
        return {
            "chart_type": view.chart_type,
            "bin_field": view.measure,
            "bins": 12,
            "measure": "record_count",
        }
    return {
        "chart_type": view.chart_type,
        "dimension": view.dimension,
        "measure": view.measure,
        "aggregation": "sum" if view.chart_type != "line" else "monthly_sum",
    }


def _query_spec(datasource_id: str, view: ViewSpec) -> dict[str, object]:
    if view.chart_type == "histogram":
        return {
            "datasource_id": datasource_id,
            "operation": "histogram",
            "field": view.measure,
            "bins": 12,
            "filters": view.default_filters,
            "limit": 500,
        }
    return {
        "datasource_id": datasource_id,
        "operation": "aggregate",
        "group_by": [view.dimension],
        "metrics": [{"field": view.measure, "aggregation": "sum"}],
        "filters": view.default_filters,
        "sort": [{"field": view.measure, "direction": "desc"}],
        "limit": 100,
    }


def _preview_rows(view: ViewSpec) -> list[dict[str, object]]:
    labels = {
        "region": ["Northeast", "Southeast", "West"],
        "category": ["Apparel", "Home", "Electronics"],
        "stage": ["Qualified", "Proposal", "Commit"],
        "channel": ["Paid Search", "Lifecycle", "Retail"],
        "priority": ["P1", "P2", "P3"],
        "vendor": ["Northstar", "Apex", "Blue River"],
    }
    dimension_values = labels.get(view.dimension, ["A", "B", "C"])
    if view.chart_type == "histogram":
        return [
            {
                "bucket_start": index * 10,
                "bucket_end": (index + 1) * 10,
                "record_count": 120 - index * 17,
            }
            for index in range(3)
        ]
    return [
        {view.dimension: label, view.measure: 100_000 - index * 18_500}
        for index, label in enumerate(dimension_values)
    ]


def _view_record(
    *,
    datasource_id: str,
    workbook_id: str,
    datasource: DatasourceSpec,
    view: ViewSpec,
    name_suffix: str,
    title_prefix: str,
    position: int,
) -> ViewRecord:
    natural_key = f"view:{datasource.key}:{name_suffix}:{view.key}"
    return ViewRecord(
        id=deterministic_id("view", natural_key),
        workbook_id=workbook_id,
        datasource_id=datasource_id,
        name=_slug(f"{name_suffix}_{view.key}"),
        title=f"{title_prefix}{view.title}",
        description=view.description,
        chart_type=view.chart_type,
        chart_config=_chart_config(view),
        query_spec=_query_spec(datasource_id, view),
        default_filters=view.default_filters,
        visual_config={"palette": "lookout-default", "legend": "auto", "labels": "compact"},
        position=position,
    )


def build_seed_records() -> SeedRecords:
    """Build deterministic domain records without touching the filesystem or database."""

    datasources: list[DatasourceRecord] = []
    datasource_fields: list[DatasourceFieldRecord] = []
    workbooks: list[WorkbookRecord] = []
    views: list[ViewRecord] = []
    query_results: list[QueryResultRecord] = []
    exports: list[ExportRecord] = []
    renders: list[RenderRecord] = []
    query_results_by_key: dict[str, QueryResultRecord] = {}

    for datasource in DATA_SOURCES:
        datasource_id = deterministic_id("ds", f"datasource:{datasource.key}")
        datasources.append(
            DatasourceRecord(
                id=datasource_id,
                name=datasource.key,
                label=datasource.label,
                description=datasource.description,
                theme=datasource.theme,
                status=datasource.status,
                connection_type="sqlite_cache",
                tags=[datasource.theme, datasource.status, "seeded"],
                default_filters={"period": "last_12_months"},
                row_count=datasource.row_count,
                cache_updated_at="2026-01-15T08:00:00Z",
                source_updated_at=None
                if datasource.status == "source_offline"
                else "2026-01-15T07:45:00Z",
            )
        )

        for ordinal, field in enumerate(datasource.fields, start=1):
            datasource_fields.append(
                DatasourceFieldRecord(
                    id=deterministic_id("fld", f"field:{datasource.key}:{field.name}"),
                    datasource_id=datasource_id,
                    name=field.name,
                    label=field.label,
                    data_type=field.data_type,
                    semantic_role=field.semantic_role,
                    description=field.description,
                    default_aggregation=field.default_aggregation,
                    is_filterable=field.filterable,
                    is_sortable=field.sortable,
                    allowed_operators=_allowed_operators(field.data_type),
                    ordinal=ordinal,
                )
            )

        for view in datasource.views:
            workbook_key = f"{datasource.key}_{view.key}_analysis"
            workbook_id = deterministic_id("wb", f"workbook:{workbook_key}")
            workbooks.append(
                WorkbookRecord(
                    id=workbook_id,
                    name=workbook_key,
                    title=f"{datasource.label}: {view.title}",
                    description=f"Focused analysis workbook for {view.description.lower()}",
                    project="Seeded BI Analysis",
                    owner="lookout-demo",
                    tags=[datasource.theme, view.chart_type, "analysis"],
                    default_filters=view.default_filters,
                )
            )
            analysis_view = _view_record(
                datasource_id=datasource_id,
                workbook_id=workbook_id,
                datasource=datasource,
                view=view,
                name_suffix="analysis",
                title_prefix="",
                position=1,
            )
            views.append(analysis_view)

            if view.key in {
                "q1_revenue_region",
                "top_store_growth",
                "pipeline_stage_health",
                "tickets_by_priority",
                "stockouts_by_category",
            }:
                query_result = QueryResultRecord(
                    id=deterministic_id("run", f"query:{datasource.key}:{view.key}"),
                    datasource_id=datasource_id,
                    view_id=analysis_view.id,
                    query_spec=analysis_view.query_spec,
                    row_count=10,
                    preview_rows=_preview_rows(view),
                    status="completed",
                    warnings=[]
                    if datasource.status == "available"
                    else [
                        f"Datasource status is {datasource.status}; served from deterministic cache."
                    ],
                    executed_at=SEED_TIMESTAMP,
                )
                query_results.append(query_result)
                query_results_by_key[f"{datasource.key}:{view.key}"] = query_result

        dashboard_key = f"{datasource.key}_executive_dashboard"
        dashboard_id = deterministic_id("wb", f"workbook:{dashboard_key}")
        workbooks.append(
            WorkbookRecord(
                id=dashboard_id,
                name=dashboard_key,
                title=f"{datasource.label} Executive Dashboard",
                description=f"Executive dashboard combining seeded {datasource.theme} views.",
                project="Executive Dashboards",
                owner="lookout-demo",
                tags=[datasource.theme, "dashboard", "executive"],
                default_filters={"period": "last_12_months"},
            )
        )
        for position, view in enumerate(datasource.views, start=1):
            views.append(
                _view_record(
                    datasource_id=datasource_id,
                    workbook_id=dashboard_id,
                    datasource=datasource,
                    view=view,
                    name_suffix="dashboard",
                    title_prefix="Dashboard: ",
                    position=position,
                )
            )
        render_id = deterministic_id("rnd", f"render:{dashboard_key}")
        renders.append(
            RenderRecord(
                id=render_id,
                workbook_id=dashboard_id,
                artifact_path=f"renders/{render_id}.svg",
                width=1440,
                height=960,
                status="ready",
                warnings=[]
                if datasource.status == "available"
                else [f"Rendered from cached metadata because datasource is {datasource.status}."],
                visual_config={"layout": "dashboard_grid", "view_count": len(datasource.views)},
                created_at=SEED_TIMESTAMP,
            )
        )

    export_specs: tuple[tuple[str, ExportFormat], ...] = (
        ("retail_sales:q1_revenue_region", "csv"),
        ("sales_pipeline:pipeline_stage_health", "csv"),
        ("customer_support:tickets_by_priority", "json"),
        ("inventory_supply_chain:stockouts_by_category", "csv"),
    )
    for query_key, export_format in export_specs:
        query_result = query_results_by_key[query_key]
        export_id = deterministic_id("exp", f"export:{query_key}:{export_format}")
        exports.append(
            ExportRecord(
                id=export_id,
                query_result_id=query_result.id,
                view_id=query_result.view_id,
                format=export_format,
                artifact_path=f"exports/{export_id}.{export_format}",
                row_count=query_result.row_count,
                status="ready",
                metadata={"seeded": True, "source_query": query_key},
                created_at=SEED_TIMESTAMP,
            )
        )

    return SeedRecords(
        datasources=datasources,
        datasource_fields=datasource_fields,
        workbooks=workbooks,
        views=views,
        query_results=query_results,
        exports=exports,
        renders=renders,
    )


def _safe_artifact_path(fs_root: Path, relative_path: str) -> Path:
    root = fs_root.resolve()
    target = (root / relative_path).resolve()
    target.relative_to(root)
    return target


def write_seed_artifacts(
    fs_root: Path,
    exports: list[ExportRecord],
    renders: list[RenderRecord],
) -> None:
    """Write tiny deterministic artifacts referenced by seeded export/render metadata."""

    for export in exports:
        target = _safe_artifact_path(fs_root, export.artifact_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if export.format == "json":
            target.write_text(
                json.dumps(
                    [{"seed_export_id": export.id, "row_count": export.row_count}],
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        else:
            target.write_text(
                f"seed_export_id,row_count\n{export.id},{export.row_count}\n",
                encoding="utf-8",
            )

    for render in renders:
        target = _safe_artifact_path(fs_root, render.artifact_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="960">'
            f"<title>{render.id}</title></svg>\n",
            encoding="utf-8",
        )
