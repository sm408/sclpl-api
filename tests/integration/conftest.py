"""A local HTTP server for the integration tests.

SPEC section 18: no network in CI except this. It is a stdlib server on an ephemeral
port rather than a mocked transport, so the tests exercise the real socket path,
connection reuse included.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PAYLOAD = {"slideshow": {"title": "Sample", "slides": [{"title": "one"}, {"title": "two"}]}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        if self.path == "/json":
            self._respond(200, json.dumps(PAYLOAD).encode())
        elif self.path == "/boom":
            self._respond(500, b"server error")
        elif self.path == "/echo-header":
            value = self.headers.get("X-Probe", "")
            self._respond(200, json.dumps({"x-probe": value}).encode())
        elif self.path == "/empty":
            self._respond(204, b"")
        else:
            self._respond(404, b"not found")

    def _respond(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default stderr logging; it would pollute the assertions."""


@pytest.fixture(scope="session")
def server_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    hostname = host.decode() if isinstance(host, bytes) else str(host)
    try:
        yield f"http://{hostname}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
