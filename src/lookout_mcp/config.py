"""Runtime configuration for Lookout."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class ConfigError(ValueError):
    """Raised when required local configuration is missing or invalid."""

    def __init__(self, message: str, *, missing: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing = missing or []


class LookoutConfig(BaseModel):
    """Validated process configuration loaded from environment variables."""

    db_path: Path = Field(default=Path("./lookout.sqlite3"))
    fs_root: Path = Field(default=Path("./var"))
    log_level: str = Field(default="INFO")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            msg = f"LOOKOUT_LOG_LEVEL must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    def ensure_filesystem_root(self) -> None:
        self.fs_root.mkdir(parents=True, exist_ok=True)
        for child in ("renders", "exports", "cache"):
            (self.fs_root / child).mkdir(parents=True, exist_ok=True)


def load_config(environ: dict[str, str] | None = None) -> LookoutConfig:
    """Load Lookout configuration from environment variables."""

    source = os.environ if environ is None else environ
    missing = [
        key for key in ("LOOKOUT_DB_PATH", "LOOKOUT_FS_ROOT") if not source.get(key, "").strip()
    ]
    if missing:
        joined = ", ".join(missing)
        raise ConfigError(
            f"Missing required Lookout configuration: {joined}. "
            "Create .env from .env.example or set the variables in the environment.",
            missing=missing,
        )
    return LookoutConfig(
        db_path=Path(source["LOOKOUT_DB_PATH"]),
        fs_root=Path(source["LOOKOUT_FS_ROOT"]),
        log_level=source.get("LOOKOUT_LOG_LEVEL", "INFO"),
    )
