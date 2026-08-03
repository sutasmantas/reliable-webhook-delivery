"""Local evidence server for the DeliveryGuard recovery console."""

from __future__ import annotations

import argparse
import json
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from deliveryguard.cli import run_demo

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

VIEWER_ROOT = Path(__file__).parent / "viewer"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def _handler(database: Path) -> type[BaseHTTPRequestHandler]:
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/api/demo":
                self._json(run_demo(database))
                return
            static = STATIC_FILES.get(path)
            if static is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            filename, content_type = static
            self._respond((VIEWER_ROOT / filename).read_bytes(), content_type)

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/api/demo":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._json(run_demo(database))

        def _json(self, value: object) -> None:
            self._respond(
                json.dumps(value, sort_keys=True).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _respond(self, content: bytes, content_type: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return ViewerHandler


def create_viewer_server(
    database: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8768,
    server_factory: Callable[..., ThreadingHTTPServer] = ThreadingHTTPServer,
) -> ThreadingHTTPServer:
    return server_factory((host, port), _handler(database))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="deliveryguard-viewer")
    result.add_argument("--host", default="127.0.0.1")
    result.add_argument("--port", type=int, default=8768)
    result.add_argument("--database", type=Path)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.database is None:
        temporary = tempfile.TemporaryDirectory(prefix="deliveryguard-viewer-")
        database = Path(temporary.name) / "delivery.sqlite3"
    else:
        temporary = None
        database = arguments.database
    server = create_viewer_server(database, host=arguments.host, port=arguments.port)
    print(f"DeliveryGuard viewer: http://{arguments.host}:{arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        if temporary is not None:
            temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
