from __future__ import annotations

from lookout_mcp.server import health_check


def main() -> None:
    result = health_check()
    if result["status"] != "ok":
        raise SystemExit(f"Unexpected health status: {result}")
    print(f"{result['service']} status={result['status']}")


if __name__ == "__main__":
    main()
