"""Shared error response helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def error_envelope(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the standard Lookout error envelope."""

    envelope = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, details=details or {}),
    )
    return envelope.model_dump()
