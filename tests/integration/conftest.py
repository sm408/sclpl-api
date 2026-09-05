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

#: client_id -> number of tokens issued, so auth tests can prove a cached/shared
#: token means one issuance rather than one per request.
OAUTH_ISSUED: dict[str, int] = {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length) if length else b""
        if self.path.startswith("/oauth/token"):
            self._oauth_token(payload)
            return
        self._respond(201, json.dumps({"received": payload.decode("utf-8", "replace")}).encode())

    def _oauth_token(self, payload: bytes) -> None:
        from urllib.parse import parse_qs, urlsplit

        fields = {k: v[0] for k, v in parse_qs(payload.decode()).items()}
        query = parse_qs(urlsplit(self.path).query)
        if fields.get("client_id") != "client-a" or fields.get("client_secret") != "secret-a":
            self._respond(401, json.dumps({"error": "invalid_client"}).encode())
            return
        OAUTH_ISSUED[fields["client_id"]] = OAUTH_ISSUED.get(fields["client_id"], 0) + 1
        ttl = int(query.get("ttl", ["3600"])[0])
        body = {
            "access_token": f"tok-{OAUTH_ISSUED[fields['client_id']]}",
            "expires_in": ttl,
        }
        self._respond(200, json.dumps(body).encode())

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
        if self.path.split("?")[0] == "/paged":
            # A cursor source of 30 items in pages of 10, for the fan-out tests.
            query = dict(
                part.split("=", 1) for part in self.path.partition("?")[2].split("&") if "=" in part
            )
            start = int(query.get("cursor", 0))
            rows = [{"id": n} for n in range(start, min(start + 10, 30))]
            nxt = start + 10
            self._respond(
                200,
                json.dumps({"data": rows, "next": nxt if nxt < 30 else None}).encode(),
            )
            return
        if self.path.split("?")[0] == "/echo":
            query = dict(
                part.split("=", 1) for part in self.path.partition("?")[2].split("&") if "=" in part
            )
            self._respond(200, json.dumps({"n": int(query.get("n", -1))}).encode())
            return
        if self.path == "/json":
            self._respond(200, json.dumps(PAYLOAD).encode())
        elif self.path == "/boom":
            self._respond(500, b"server error", "text/plain")
        elif self.path == "/echo-header":
            value = self.headers.get("X-Probe", "")
            self._respond(200, json.dumps({"x-probe": value}).encode())
        elif self.path == "/auth-once":
            # Rejects exactly once per test, regardless of who is asking, so an
            # oauth-backed step can prove it refreshed and retried after a 401.
            seen = ATTEMPTS.get("/auth-once", 0)
            ATTEMPTS["/auth-once"] = seen + 1
            if seen == 0:
                self.send_response(401)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            value = self.headers.get("Authorization", "")
            self._respond(200, json.dumps({"authorization": value}).encode())
        elif self.path == "/echo-auth":
            self._respond(
                200,
                json.dumps(
                    {
                        "authorization": self.headers.get("Authorization", ""),
                        "x-api-key": self.headers.get("X-Api-Key", ""),
                        "x-signature": self.headers.get("X-Signature", ""),
                        "x-timestamp": self.headers.get("X-Timestamp", ""),
                    }
                ).encode(),
            )
        elif self.path.split("?")[0] == "/redirect":
            query = dict(
                part.split("=", 1) for part in self.path.partition("?")[2].split("&") if "=" in part
            )
            from urllib.parse import unquote

            self.send_response(302)
            self.send_header("Location", unquote(query["to"]))
            self.send_header("Content-Length", "0")
            self.end_headers()
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
    OAUTH_ISSUED.clear()
    yield
    ATTEMPTS.clear()
    OAUTH_ISSUED.clear()


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
