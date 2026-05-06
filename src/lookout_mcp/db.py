"""SQLite migration and deterministic seed commands for Lookout."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from lookout_mcp.config import LookoutConfig, load_config
from lookout_mcp.seed import SeedRecords, build_seed_records, write_seed_artifacts

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a Lookout SQLite connection with production pragmas enabled."""

    path = load_config().db_path if db_path is None else db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _migration_files(migrations_dir: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(migrations_dir.glob("*.sql"))


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS _lookout_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _applied_migrations(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT version FROM _lookout_migrations").fetchall()
    return {str(row["version"]) for row in rows}


def migrate(config: LookoutConfig | None = None) -> None:
    """Apply pending SQLite migrations to the configured database."""

    loaded = load_config() if config is None else config
    loaded.db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(loaded.db_path) as connection:
        _ensure_migration_table(connection)
        applied = _applied_migrations(connection)
        for migration_file in _migration_files():
            version = migration_file.stem
            if version in applied:
                continue
            connection.executescript(migration_file.read_text())
            connection.execute(
                "INSERT INTO _lookout_migrations (version) VALUES (?)",
                (version,),
            )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _delete_seeded_rows(connection: sqlite3.Connection) -> None:
    for table_name in (
        "renders",
        "exports",
        "query_results",
        "views",
        "workbooks",
        "datasource_fields",
        "datasources",
    ):
        connection.execute(f"DELETE FROM {table_name}")


def _insert_datasources(connection: sqlite3.Connection, records: SeedRecords) -> None:
    connection.executemany(
        """
        INSERT INTO datasources (
            id, name, label, description, theme, status, connection_type, tags,
            default_filters, row_count, cache_updated_at, source_updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                item.id,
                item.name,
                item.label,
                item.description,
                item.theme,
                item.status,
                item.connection_type,
                _json(item.tags),
                _json(item.default_filters),
                item.row_count,
                item.cache_updated_at,
                item.source_updated_at,
            )
            for item in records.datasources
        ),
    )


def _insert_datasource_fields(connection: sqlite3.Connection, records: SeedRecords) -> None:
    connection.executemany(
        """
        INSERT INTO datasource_fields (
            id, datasource_id, name, label, data_type, semantic_role, description,
            default_aggregation, is_filterable, is_sortable, allowed_operators, ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                item.id,
                item.datasource_id,
                item.name,
                item.label,
                item.data_type,
                item.semantic_role,
                item.description,
                item.default_aggregation,
                int(item.is_filterable),
                int(item.is_sortable),
                _json(item.allowed_operators),
                item.ordinal,
            )
            for item in records.datasource_fields
        ),
    )


def _insert_workbooks(connection: sqlite3.Connection, records: SeedRecords) -> None:
    connection.executemany(
        """
        INSERT INTO workbooks (
            id, name, title, description, project, owner, tags, default_filters
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                item.id,
                item.name,
                item.title,
                item.description,
                item.project,
                item.owner,
                _json(item.tags),
                _json(item.default_filters),
            )
            for item in records.workbooks
        ),
    )


def _insert_views(connection: sqlite3.Connection, records: SeedRecords) -> None:
    connection.executemany(
        """
        INSERT INTO views (
            id, workbook_id, datasource_id, name, title, description, chart_type,
            chart_config, query_spec, default_filters, visual_config, position
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                item.id,
                item.workbook_id,
                item.datasource_id,
                item.name,
                item.title,
                item.description,
                item.chart_type,
                _json(item.chart_config),
                _json(item.query_spec),
                _json(item.default_filters),
                _json(item.visual_config),
                item.position,
            )
            for item in records.views
        ),
    )


def _insert_query_results(connection: sqlite3.Connection, records: SeedRecords) -> None:
    connection.executemany(
        """
        INSERT INTO query_results (
            id, datasource_id, view_id, query_spec, row_count, preview_rows,
            status, warnings, executed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                item.id,
                item.datasource_id,
                item.view_id,
                _json(item.query_spec),
                item.row_count,
                _json(item.preview_rows),
                item.status,
                _json(item.warnings),
                item.executed_at,
            )
            for item in records.query_results
        ),
    )


def _insert_exports(connection: sqlite3.Connection, records: SeedRecords) -> None:
    connection.executemany(
        """
        INSERT INTO exports (
            id, query_result_id, view_id, format, artifact_path, row_count,
            status, metadata, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                item.id,
                item.query_result_id,
                item.view_id,
                item.format,
                item.artifact_path,
                item.row_count,
                item.status,
                _json(item.metadata),
                item.created_at,
            )
            for item in records.exports
        ),
    )


def _insert_renders(connection: sqlite3.Connection, records: SeedRecords) -> None:
    connection.executemany(
        """
        INSERT INTO renders (
            id, workbook_id, view_id, chart_type, artifact_path, width, height,
            status, warnings, visual_config, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                item.id,
                item.workbook_id,
                item.view_id,
                item.chart_type,
                item.artifact_path,
                item.width,
                item.height,
                item.status,
                _json(item.warnings),
                _json(item.visual_config),
                item.created_at,
            )
            for item in records.renders
        ),
    )


def _insert_seed_records(connection: sqlite3.Connection, records: SeedRecords) -> None:
    for insert_records in (
        _insert_datasources,
        _insert_datasource_fields,
        _insert_workbooks,
        _insert_views,
        _insert_query_results,
        _insert_exports,
        _insert_renders,
    ):
        insert_records(connection, records)


def _count_rows(connection: sqlite3.Connection, table_names: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in table_names:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        counts[table_name] = int(row["count"])
    return counts


def seed(config: LookoutConfig | None = None) -> dict[str, int]:
    """Reset and load deterministic BI seed data."""

    loaded = load_config() if config is None else config
    loaded.ensure_filesystem_root()
    migrate(loaded)
    records = build_seed_records()
    with connect(loaded.db_path) as connection:
        _delete_seeded_rows(connection)
        _insert_seed_records(connection, records)
        counts = _count_rows(
            connection,
            (
                "datasources",
                "datasource_fields",
                "workbooks",
                "views",
                "query_results",
                "exports",
                "renders",
            ),
        )
    write_seed_artifacts(loaded.fs_root, records.exports, records.renders)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(prog="lookout-db")
    parser.add_argument("command", choices=("migrate", "seed"))
    args = parser.parse_args()

    if args.command == "migrate":
        migrate()
    else:
        seed()


if __name__ == "__main__":
    main()
