"""Bounded-retry delivery for webhook/Slack (HTTP) and SMTP notifications."""

from __future__ import annotations

import hashlib
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

import httpx

from sclpl.notifications.config import NotificationConfig
from sclpl.run.retry import REAL_CLOCK, Clock

MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 0.5


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    name: str
    status: str  # "delivered" | "failed"
    attempts: int
    error: str | None = None


def idempotency_key(run_id: str, notifier_name: str, event: str) -> str:
    """A stable key a receiver can use to deduplicate a resent delivery.

    Deterministic from (run, notifier, event): retrying the *same* delivery
    (this process, or a rerun of the same run id) produces the same key, so a
    receiver that already saw it can discard the duplicate.
    """
    seed = f"{run_id}:{notifier_name}:{event}".encode()
    return hashlib.sha256(seed).hexdigest()[:32]


async def deliver(
    config: NotificationConfig,
    payload: dict[str, Any],
    *,
    key: str,
    clock: Clock = REAL_CLOCK,
) -> DeliveryReceipt:
    """Attempt delivery up to `MAX_ATTEMPTS` times with jittered backoff.

    Never raises: a receipt with `status="failed"` is the worst case, so a
    notification problem is visible without ever propagating into the run's
    own result.
    """
    if config.kind in ("webhook", "slack"):
        return await _deliver_http(config, payload, key=key, clock=clock)
    return await _deliver_smtp(config, payload, key=key, clock=clock)


async def _deliver_http(
    config: NotificationConfig, payload: dict[str, Any], *, key: str, clock: Clock
) -> DeliveryReceipt:
    assert config.url is not None
    body = {"text": summary_line(payload)} if config.kind == "slack" else payload
    last_error: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    config.url, json=body, headers={"Idempotency-Key": key}
                )
                response.raise_for_status()
            return DeliveryReceipt(config.name, "delivered", attempt)
        except httpx.HTTPError as error:
            last_error = str(error)
            if attempt < MAX_ATTEMPTS:
                await clock.sleep(_BACKOFF_SECONDS * clock.jitter() * (2 ** (attempt - 1)))
    return DeliveryReceipt(config.name, "failed", MAX_ATTEMPTS, last_error)


async def _deliver_smtp(
    config: NotificationConfig, payload: dict[str, Any], *, key: str, clock: Clock
) -> DeliveryReceipt:
    assert config.to and config.from_address and config.smtp_host
    message = EmailMessage()
    message["Subject"] = (
        f"sclpl {payload.get('workflow', 'run')}: {payload.get('status', 'update')}"
    )
    message["From"] = config.from_address
    message["To"] = ", ".join(config.to)
    message["X-Idempotency-Key"] = key
    message.set_content(summary_line(payload))

    last_error: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            _send_smtp(config, message)
            return DeliveryReceipt(config.name, "delivered", attempt)
        except OSError as error:
            last_error = str(error)
            if attempt < MAX_ATTEMPTS:
                await clock.sleep(_BACKOFF_SECONDS * clock.jitter() * (2 ** (attempt - 1)))
    return DeliveryReceipt(config.name, "failed", MAX_ATTEMPTS, last_error)


def _send_smtp(config: NotificationConfig, message: EmailMessage) -> None:
    assert config.smtp_host is not None
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10.0) as client:
        client.send_message(message)


def summary_line(payload: dict[str, Any]) -> str:
    """A sanitized one-line summary -- payload fields are already-redacted
    reporter event data (status, counts, timings), never a raw response body.
    """
    return (
        f"sclpl {payload.get('workflow', 'run')}: {payload.get('status', 'unknown')} "
        f"in {payload.get('duration_ms', 0)}ms (exit {payload.get('exit_code', 0)})"
    )
