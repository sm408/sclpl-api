"""I4: bounded-retry delivery, verified against a real local HTTP receiver."""

from __future__ import annotations

import asyncio
import json
import smtplib
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sclpl.notifications.config import NotificationConfig
from sclpl.notifications.delivery import DeliveryReceipt, deliver, idempotency_key
from sclpl.run.retry import Clock

#: Instant, deterministic clock: no real sleeping and no timing flakiness in CI.
FAST_CLOCK = Clock(now=lambda: 0.0, sleep=lambda _seconds: asyncio.sleep(0), jitter=lambda: 0.01)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    received: list[dict[str, object]] = []
    fail_first_n = 0

    def do_POST(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        _Handler.received.append(
            {
                "path": self.path,
                "idempotency_key": self.headers.get("Idempotency-Key"),
                "body": json.loads(body) if body else {},
            }
        )
        if len(_Handler.received) <= _Handler.fail_first_n:
            self._respond(503)
            return
        self._respond(200)

    def _respond(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object) -> None:  # silence per-request stderr noise
        pass


@pytest.fixture
def receiver() -> Iterator[str]:
    _Handler.received = []
    _Handler.fail_first_n = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _webhook(url: str, **overrides: object) -> NotificationConfig:
    fields: dict[str, object] = {
        "name": "n",
        "kind": "webhook",
        "enabled": True,
        "on": frozenset({"run_finished"}),
        "url": url,
    }
    fields.update(overrides)
    return NotificationConfig(**fields)  # type: ignore[arg-type]


async def test_successful_delivery_reaches_the_real_receiver(receiver: str) -> None:
    config = _webhook(receiver)
    payload = {"workflow": "demo", "status": "ok", "duration_ms": 12, "exit_code": 0}
    key = idempotency_key("run-1", "n", "run_finished")

    result = await deliver(config, payload, key=key, clock=FAST_CLOCK)

    assert result == DeliveryReceipt("n", "delivered", 1)
    assert _Handler.received[0]["body"] == payload
    assert _Handler.received[0]["idempotency_key"] == key


async def test_retries_and_recovers_within_max_attempts(receiver: str) -> None:
    _Handler.fail_first_n = 2
    config = _webhook(receiver)
    result = await deliver(
        config,
        {"workflow": "demo"},
        key=idempotency_key("r", "n", "run_finished"),
        clock=FAST_CLOCK,
    )
    assert result.status == "delivered"
    assert result.attempts == 3
    assert len(_Handler.received) == 3


async def test_exhausting_retries_reports_failed_not_raised(receiver: str) -> None:
    _Handler.fail_first_n = 99
    config = _webhook(receiver)
    result = await deliver(
        config,
        {"workflow": "demo"},
        key=idempotency_key("r", "n", "run_finished"),
        clock=FAST_CLOCK,
    )
    assert result.status == "failed"
    assert result.attempts == 3
    assert result.error is not None


async def test_same_run_notifier_event_produces_the_same_key() -> None:
    a = idempotency_key("run-1", "webhook-a", "run_finished")
    b = idempotency_key("run-1", "webhook-a", "run_finished")
    c = idempotency_key("run-1", "webhook-a", "step_failed")
    assert a == b
    assert a != c


async def test_slack_kind_wraps_the_summary_in_a_text_field(receiver: str) -> None:
    config = _webhook(receiver, kind="slack")
    payload = {"workflow": "demo", "status": "ok", "duration_ms": 5, "exit_code": 0}
    await deliver(config, payload, key=idempotency_key("r", "n", "run_finished"), clock=FAST_CLOCK)
    body = _Handler.received[0]["body"]
    assert isinstance(body, dict)
    assert "demo" in body["text"]


async def test_smtp_delivery_uses_the_configured_host_and_recovers_after_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []
    attempts = {"n": 0}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            self.host, self.port = host, port

        def __enter__(self) -> FakeSMTP:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise OSError("connection refused")
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def send_message(self, message: object) -> None:
            sent.append({"host": self.host, "port": self.port, "message": message})

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    config = NotificationConfig(
        name="email",
        kind="smtp",
        enabled=True,
        on=frozenset({"run_finished"}),
        to=("ops@example.com",),
        from_address="sclpl@example.com",
        smtp_host="smtp.example.invalid",
    )
    result = await deliver(
        config,
        {"workflow": "demo", "status": "failed", "duration_ms": 1, "exit_code": 1},
        key=idempotency_key("r", "email", "run_finished"),
        clock=FAST_CLOCK,
    )

    assert result.status == "delivered"
    assert result.attempts == 2
    assert sent[0]["host"] == "smtp.example.invalid"
