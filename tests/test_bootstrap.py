from __future__ import annotations

import os
from pathlib import Path

import pytest

from lookout_mcp.config import ConfigError, LookoutConfig, load_config
from lookout_mcp.errors import error_envelope
from lookout_mcp.server import health_check


@pytest.mark.unit
def test_error_envelope_shape() -> None:
    assert error_envelope(
        "INVALID_INPUT",
        "The request is invalid.",
        {"field": "page_size"},
    ) == {
        "error": {
            "code": "INVALID_INPUT",
            "message": "The request is invalid.",
            "details": {"field": "page_size"},
        }
    }


@pytest.mark.unit
def test_load_config_from_environment_values() -> None:
    config = load_config(
        {
            "LOOKOUT_DB_PATH": "/tmp/lookout-test.sqlite3",
            "LOOKOUT_FS_ROOT": "/tmp/lookout-fs",
            "LOOKOUT_LOG_LEVEL": "debug",
        }
    )

    assert str(config.db_path) == "/tmp/lookout-test.sqlite3"
    assert str(config.fs_root) == "/tmp/lookout-fs"
    assert config.log_level == "DEBUG"


@pytest.mark.unit
def test_load_config_requires_local_paths() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_config({})

    assert exc_info.value.missing == ["LOOKOUT_DB_PATH", "LOOKOUT_FS_ROOT"]


@pytest.mark.unit
def test_health_check_returns_graceful_error_when_config_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOOKOUT_DB_PATH", raising=False)
    monkeypatch.delenv("LOOKOUT_FS_ROOT", raising=False)

    result = health_check()

    assert result["error"]["code"] == "CONFIG_MISSING"
    assert result["error"]["details"]["missing"] == ["LOOKOUT_DB_PATH", "LOOKOUT_FS_ROOT"]


@pytest.mark.unit
def test_health_check_creates_local_filesystem_root(tmp_path: Path) -> None:
    config = LookoutConfig(
        db_path=tmp_path / "lookout.sqlite3",
        fs_root=tmp_path / "var",
        log_level="INFO",
    )

    result = health_check(config)

    assert result["status"] == "ok"
    assert result["service"] == "lookout-mcp"
    assert result["fs_root"] == os.fspath(tmp_path / "var")
    assert (tmp_path / "var" / "renders").is_dir()
    assert (tmp_path / "var" / "exports").is_dir()
    assert (tmp_path / "var" / "cache").is_dir()
