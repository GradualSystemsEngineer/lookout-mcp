"""MCP server entrypoint for Lookout."""

from __future__ import annotations

from typing import Any

from lookout_mcp.config import LookoutConfig, load_config
from lookout_mcp.schemas import HealthCheckResult


def health_check(config: LookoutConfig | None = None) -> dict[str, Any]:
    """Return a local smoke-check payload for tests and MCP clients."""

    loaded = load_config() if config is None else config
    loaded.ensure_filesystem_root()
    return HealthCheckResult(
        status="ok",
        service="lookout-mcp",
        db_path=loaded.db_path,
        fs_root=loaded.fs_root,
        log_level=loaded.log_level,
    ).model_dump(mode="json")


def create_mcp_server() -> Any:
    """Create the FastMCP server with bootstrap tools registered."""

    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("lookout")

    @mcp.tool(
        name="health_check",
        description="Return local Lookout service status and resolved configuration paths.",
    )
    def _health_check() -> dict[str, Any]:
        return health_check()

    return mcp


def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
