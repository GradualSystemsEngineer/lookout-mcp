"""Runtime configuration for Lookout."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


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
    return LookoutConfig(
        db_path=Path(source.get("LOOKOUT_DB_PATH", "./lookout.sqlite3")),
        fs_root=Path(source.get("LOOKOUT_FS_ROOT", "./var")),
        log_level=source.get("LOOKOUT_LOG_LEVEL", "INFO"),
    )
