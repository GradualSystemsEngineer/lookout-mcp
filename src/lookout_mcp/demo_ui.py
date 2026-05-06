"""Dev-only HTTP adapter for the optional Lookout Explorer UI.

This module is intentionally separate from the MCP transport. It exposes a small JSON API for the
local evaluator demo and delegates Lookout behavior to the same callable backend used by MCP tools.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import socketserver
from collections.abc import Callable, Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from lookout_mcp.config import LookoutConfig, load_config
from lookout_mcp.db import connect
from lookout_mcp.errors import error_envelope
from lookout_mcp.server import health_check
from lookout_mcp.tools import api

JsonPayload = dict[str, Any]


def _json_loads(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _record_from_row(row: Any) -> dict[str, Any]:
    data = dict(zip(row.keys(), row, strict=True))
    for key in ("warnings", "metadata", "visual_config"):
        if key in data:
            data[key] = _json_loads(data[key])
    return data


def _artifact_metadata(config: LookoutConfig) -> dict[str, Any]:
    with connect(config.db_path) as connection:
        exports = [
            _record_from_row(row)
            for row in connection.execute(
                """
                SELECT
                    exports.*,
                    views.title AS view_title,
                    datasources.label AS datasource_label
                FROM exports
                LEFT JOIN query_results ON query_results.id = exports.query_result_id
                LEFT JOIN views ON views.id = exports.view_id
                LEFT JOIN datasources ON datasources.id = query_results.datasource_id
                ORDER BY exports.created_at DESC, exports.id
                """
            ).fetchall()
        ]
        renders = [
            _record_from_row(row)
            for row in connection.execute(
                """
                SELECT
                    renders.*,
                    views.title AS view_title,
                    workbooks.title AS workbook_title
                FROM renders
                LEFT JOIN views ON views.id = renders.view_id
                LEFT JOIN workbooks ON workbooks.id = renders.workbook_id
                ORDER BY renders.created_at DESC, renders.id
                """
            ).fetchall()
        ]
    return {"exports": exports, "renders": renders, "warnings": []}


def _safe_file(config: LookoutConfig, relative_path: str) -> Path:
    root = config.fs_root.resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Artifact path escapes LOOKOUT_FS_ROOT.") from exc
    return target


class DemoRequestHandler(BaseHTTPRequestHandler):
    """Small stdlib JSON handler for local-only demo use."""

    server: DemoServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        if self.server.verbose:
            super().log_message(format, *args)

    def do_OPTIONS(self) -> None:
        self._send_empty(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/files" and method == "GET":
                self._send_file(parse_qs(parsed.query).get("path", [""])[0])
                return
            if not parsed.path.startswith("/api/"):
                self._send_json(
                    error_envelope("NOT_FOUND", "Demo UI route was not found.", {}),
                    HTTPStatus.NOT_FOUND,
                )
                return
            result = self._route(method, parsed.path, parse_qs(parsed.query))
            status = HTTPStatus.BAD_REQUEST if "error" in result else HTTPStatus.OK
            self._send_json(result, status)
        except ValueError as exc:
            self._send_json(
                error_envelope("INVALID_INPUT", str(exc), {}),
                HTTPStatus.BAD_REQUEST,
            )
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._send_json(
                error_envelope("INTERNAL_ERROR", "Demo UI adapter failed.", {"reason": str(exc)}),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _route(
        self,
        method: str,
        path: str,
        query: Mapping[str, list[str]],
    ) -> JsonPayload:
        segments = [unquote(segment) for segment in path.strip("/").split("/")]
        body = self._read_body() if method == "POST" else {}

        if method == "GET" and path == "/api/health":
            return health_check(self.server.config)
        if method == "GET" and path == "/api/datasources":
            return api.list_datasources(
                query=_first(query, "query"),
                status=_first(query, "status"),
                page_size=25,
                _config=self.server.config,
            )
        if method == "GET" and len(segments) == 3 and segments[:2] == ["api", "datasources"]:
            return api.get_datasource(datasource=segments[2], _config=self.server.config)
        if method == "GET" and path == "/api/workbooks":
            return api.list_workbooks(
                query=_first(query, "query"),
                datasource=_first(query, "datasource"),
                page_size=25,
                _config=self.server.config,
            )
        if method == "GET" and len(segments) == 3 and segments[:2] == ["api", "workbooks"]:
            return api.get_workbook(workbook=segments[2], _config=self.server.config)
        if method == "GET" and path == "/api/views":
            return api.list_views(
                query=_first(query, "query"),
                workbook=_first(query, "workbook"),
                datasource=_first(query, "datasource"),
                chart_type=_first(query, "chart_type"),
                page_size=25,
                _config=self.server.config,
            )
        if method == "GET" and len(segments) == 3 and segments[:2] == ["api", "views"]:
            return api.get_view(view=segments[2], _config=self.server.config)
        if method == "POST" and len(segments) == 4 and segments[:2] == ["api", "views"]:
            return self._view_action(segments[2], segments[3], body)
        if method == "POST" and path == "/api/query":
            return api.query_datasource(
                datasource=str(body.get("datasource", "")),
                query_spec=dict(body.get("query_spec") or {}),
                preview_limit=_int_or_none(body.get("preview_limit")),
                _config=self.server.config,
            )
        if (
            method == "POST"
            and len(segments) == 4
            and segments[:2] == ["api", "query-results"]
            and segments[3] == "export"
        ):
            return api.export_query_result(
                query_result_id=segments[2],
                format=str(body.get("format") or "csv"),
                _config=self.server.config,
            )
        if method == "GET" and path == "/api/artifacts":
            return _artifact_metadata(self.server.config)
        return error_envelope("NOT_FOUND", "Demo UI route was not found.", {"path": path})

    def _view_action(self, view: str, action: str, body: Mapping[str, Any]) -> JsonPayload:
        if action == "data":
            filter_overrides = body.get("filter_overrides") or []
            return api.get_view_data(
                view=view,
                filter_overrides=filter_overrides,
                preview_limit=_int_or_none(body.get("preview_limit")),
                _config=self.server.config,
            )
        if action == "render":
            filter_overrides = body.get("filter_overrides") or []
            return api.render_view_image(
                view=view,
                filter_overrides=filter_overrides,
                width=int(body.get("width") or 960),
                height=int(body.get("height") or 540),
                _config=self.server.config,
            )
        if action == "export":
            return api.export_view_data(
                view=view,
                format=str(body.get("format") or "csv"),
                _config=self.server.config,
            )
        return error_envelope("NOT_FOUND", "View action was not found.", {"action": action})

    def _read_body(self) -> JsonPayload:
        length = int(self.headers.get("Content-Length") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return dict(json.loads(raw))

    def _send_empty(self, status: HTTPStatus) -> None:
        self.send_response(status)
        self._send_common_headers()
        self.end_headers()

    def _send_json(self, payload: Mapping[str, Any], status: HTTPStatus) -> None:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, relative_path: str) -> None:
        target = _safe_file(self.server.config, relative_path)
        if not target.is_file():
            self._send_json(
                error_envelope(
                    "NOT_FOUND",
                    "Artifact file was not found.",
                    {"path": relative_path},
                ),
                HTTPStatus.NOT_FOUND,
            )
            return
        content = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(target.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


class DemoServer(ThreadingHTTPServer):
    """Threading HTTP server with Lookout configuration attached."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = int(port)

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: Callable[..., BaseHTTPRequestHandler],
        *,
        config: LookoutConfig,
        verbose: bool,
    ) -> None:
        super().__init__(server_address, handler)
        self.config = config
        self.verbose = verbose


def _first(query: Mapping[str, list[str]], key: str) -> str | None:
    value = query.get(key, [""])[0]
    return value or None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def main() -> None:
    parser = argparse.ArgumentParser(prog="lookout-demo-ui")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = load_config()
    config.ensure_filesystem_root()
    server = DemoServer(
        (args.host, args.port),
        DemoRequestHandler,
        config=config,
        verbose=args.verbose,
    )
    print(f"Lookout Explorer API listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
