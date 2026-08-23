"""A local HTTP server for the integration tests.

SPEC section 18: no network in CI except this. It is a stdlib server on an ephemeral
port rather than a mocked transport, so the tests exercise the real socket path,
connection reuse included.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PAYLOAD = {"slideshow": {"title": "Sample", "slides": [{"title": "one"}, {"title": "two"}]}}


#: Per-path attempt counters, so a route can fail the first N times and then succeed.
ATTEMPTS: dict[str, int] = {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length) if length else b""
        self._respond(201, json.dumps({"received": payload.decode("utf-8", "replace")}).encode())

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        if self.path.startswith("/flaky/"):
            # /flaky/<n> fails with 503 n times, then succeeds. Exercises the retry
            # path without a sleep or a real outage.
            budget = int(self.path.rsplit("/", 1)[1])
            seen = ATTEMPTS.get(self.path, 0)
            ATTEMPTS[self.path] = seen + 1
            if seen < budget:
                self._respond(503, b"try again", "text/plain")
            else:
                self._respond(200, json.dumps({"attempts": seen + 1}).encode())
            return
        if self.path == "/slow":
            time.sleep(0.5)
            self._respond(200, b"{}")
            return
        if self.path == "/rate-limited":
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/not-json":
            # Claims JSON, is not. The decoder must say so rather than pass a string on.
            body = b"<html>gateway error</html>"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/json":
            self._respond(200, json.dumps(PAYLOAD).encode())
        elif self.path == "/boom":
            self._respond(500, b"server error", "text/plain")
        elif self.path == "/echo-header":
            value = self.headers.get("X-Probe", "")
            self._respond(200, json.dumps({"x-probe": value}).encode())
        elif self.path == "/empty":
            self._respond(204, b"")
        else:
            self._respond(404, b"not found", "text/plain")

    def _respond(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default stderr logging; it would pollute the assertions."""


@pytest.fixture(autouse=True)
def _reset_attempt_counters() -> Iterator[None]:
    """Each test gets the flaky routes back at attempt zero."""
    ATTEMPTS.clear()
    yield
    ATTEMPTS.clear()


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
