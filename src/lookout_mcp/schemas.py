"""Pydantic schemas shared by MCP tools and local tests."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class HealthCheckResult(BaseModel):
    """Output returned by the bootstrap health check."""

    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    db_path: Path
    fs_root: Path
    log_level: str
