from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from lookout_mcp.config import LookoutConfig
from lookout_mcp.db import connect, migrate, seed
from lookout_mcp.schemas import validate_prefixed_id

EXPECTED_COUNTS = {
    "datasources": 6,
    "datasource_fields": 48,
    "workbooks": 36,
    "views": 60,
    "query_results": 5,
    "exports": 4,
    "renders": 6,
}


def _config(tmp_path: Path) -> LookoutConfig:
    return LookoutConfig(
        db_path=tmp_path / "lookout.sqlite3",
        fs_root=tmp_path / "var",
        log_level="INFO",
    )


@pytest.mark.integration
def test_migrate_creates_core_schema_and_records_migration(tmp_path: Path) -> None:
    config = _config(tmp_path)

    migrate(config)

    with connect(config.db_path) as connection:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        migration_versions = [
            str(row["version"])
            for row in connection.execute(
                "SELECT version FROM _lookout_migrations ORDER BY version"
            ).fetchall()
        ]

    assert {
        "datasources",
        "datasource_fields",
        "workbooks",
        "views",
        "query_results",
        "exports",
        "renders",
    }.issubset(tables)
    assert migration_versions == ["001_core_domain_model"]


@pytest.mark.unit
def test_prefixed_id_validation_accepts_only_expected_shape() -> None:
    assert validate_prefixed_id("ds_0123abcdef89", "ds") == "ds_0123abcdef89"

    with pytest.raises(ValueError, match="Expected ID format"):
        validate_prefixed_id("ds_0123ABCDEF89", "ds")

    with pytest.raises(ValueError, match="Expected ID format"):
        validate_prefixed_id("wb_0123abcdef89", "ds")


@pytest.mark.integration
def test_sql_id_check_constraints_reject_bad_prefixes(tmp_path: Path) -> None:
    config = _config(tmp_path)
    migrate(config)

    with connect(config.db_path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
                INSERT INTO datasources (
                    id, name, label, description, theme, status, connection_type,
                    tags, default_filters, row_count
                )
                VALUES (
                    'bad_0123abcdef89', 'bad', 'Bad', 'Bad datasource', 'test',
                    'available', 'sqlite_cache', '[]', '{}', 0
                )
                """
        )


@pytest.mark.integration
def test_seed_is_deterministic_and_has_expected_counts(tmp_path: Path) -> None:
    config = _config(tmp_path)

    first_counts = seed(config)
    with connect(config.db_path) as connection:
        first_ids = {
            table_name: [
                str(row["id"])
                for row in connection.execute(f"SELECT id FROM {table_name} ORDER BY id").fetchall()
            ]
            for table_name in EXPECTED_COUNTS
        }

    second_counts = seed(config)
    with connect(config.db_path) as connection:
        second_ids = {
            table_name: [
                str(row["id"])
                for row in connection.execute(f"SELECT id FROM {table_name} ORDER BY id").fetchall()
            ]
            for table_name in EXPECTED_COUNTS
        }

    assert first_counts == EXPECTED_COUNTS
    assert second_counts == EXPECTED_COUNTS
    assert second_ids == first_ids


@pytest.mark.integration
def test_seed_integrity_relationships_statuses_and_chart_types(tmp_path: Path) -> None:
    config = _config(tmp_path)
    seed(config)

    with connect(config.db_path) as connection:
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        statuses = {
            str(row["status"])
            for row in connection.execute("SELECT DISTINCT status FROM datasources").fetchall()
        }
        chart_types = {
            str(row["chart_type"])
            for row in connection.execute("SELECT DISTINCT chart_type FROM views").fetchall()
        }
        fields_without_operators = int(
            connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM datasource_fields
                WHERE json_array_length(allowed_operators) = 0
                """
            ).fetchone()["count"]
        )
        workbook_orphans = int(
            connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM workbooks
                WHERE id NOT IN (SELECT DISTINCT workbook_id FROM views)
                """
            ).fetchone()["count"]
        )

    assert foreign_key_errors == []
    assert statuses == {"available", "cache_stale", "source_offline"}
    assert chart_types == {"bar", "pie", "treemap", "line", "histogram"}
    assert fields_without_operators == 0
    assert workbook_orphans == 0


@pytest.mark.integration
def test_seeded_artifacts_stay_under_filesystem_root(tmp_path: Path) -> None:
    config = _config(tmp_path)
    seed(config)

    with connect(config.db_path) as connection:
        artifact_paths = [
            str(row["artifact_path"])
            for row in connection.execute("SELECT artifact_path FROM exports").fetchall()
        ]
        artifact_paths.extend(
            str(row["artifact_path"])
            for row in connection.execute("SELECT artifact_path FROM renders").fetchall()
        )

    id_pattern = re.compile(r"^(exports/exp|renders/rnd)_[0-9a-f]{12}\.(csv|json|svg)$")
    for artifact_path in artifact_paths:
        assert id_pattern.fullmatch(artifact_path)
        resolved = (config.fs_root / artifact_path).resolve()
        assert resolved.relative_to(config.fs_root.resolve())
        assert resolved.is_file()
