"""I4: routing reporter events to configured notifiers."""

from __future__ import annotations

import asyncio

import pytest

from sclpl.notifications import delivery
from sclpl.notifications import sink as sink_module
from sclpl.notifications.config import NotificationConfig
from sclpl.notifications.sink import NotificationSink
from sclpl.render.events import LogRecord, RunFinished, StepFinished


def _config(name: str, on: frozenset[str], *, enabled: bool = True) -> NotificationConfig:
    return NotificationConfig(name, "webhook", enabled, on, url="https://example.com/hook")


@pytest.fixture(autouse=True)
def fake_deliver(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, object]]]:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake(
        config: NotificationConfig, payload: dict[str, object], *, key: str
    ) -> delivery.DeliveryReceipt:
        calls.append((config.name, payload))
        return delivery.DeliveryReceipt(config.name, "delivered", 1)

    monkeypatch.setattr(sink_module, "deliver", fake)
    return calls


@pytest.mark.parametrize(
    ("on", "enabled", "event", "expect_dispatch"),
    [
        (frozenset({"run_finished"}), True, RunFinished(status="ok", duration_ms=10), True),
        (frozenset({"run_started"}), True, RunFinished(status="ok", duration_ms=10), False),
        (frozenset({"run_finished"}), False, RunFinished(status="ok", duration_ms=10), False),
        (
            frozenset({"step_failed"}),
            True,
            StepFinished(id="a", status="ok", duration_ms=1),
            False,
        ),
        (
            frozenset({"step_failed"}),
            True,
            StepFinished(id="a", status="failed", duration_ms=1),
            True,
        ),
        (
            frozenset({"run_started", "run_finished", "step_failed"}),
            True,
            LogRecord(level="info", message="hello"),
            False,
        ),
    ],
)
async def test_dispatch_matches_configured_events(
    fake_deliver: list[tuple[str, dict[str, object]]],
    on: frozenset[str],
    enabled: bool,
    event: RunFinished | StepFinished | LogRecord,
    expect_dispatch: bool,
) -> None:
    notifier = NotificationSink((_config("n", on, enabled=enabled),), run_id="r1", workflow="demo")
    notifier.handle(event)
    await notifier.wait()
    assert bool(fake_deliver) is expect_dispatch


async def test_two_notifiers_can_watch_the_same_event_independently(
    fake_deliver: list[tuple[str, dict[str, object]]],
) -> None:
    notifier = NotificationSink(
        (
            _config("webhook-a", frozenset({"run_finished"})),
            _config("webhook-b", frozenset({"run_finished"})),
        ),
        run_id="r1",
        workflow="demo",
    )
    notifier.handle(RunFinished(status="ok", duration_ms=10))
    await notifier.wait()
    assert {name for name, _ in fake_deliver} == {"webhook-a", "webhook-b"}


async def test_payload_carries_run_id_and_workflow_name(
    fake_deliver: list[tuple[str, dict[str, object]]],
) -> None:
    notifier = NotificationSink(
        (_config("n", frozenset({"run_finished"})),), run_id="run-xyz", workflow="my_workflow"
    )
    notifier.handle(RunFinished(status="ok", duration_ms=10, exit_code=0))
    await notifier.wait()
    _, payload = fake_deliver[0]
    assert payload["run_id"] == "run-xyz"
    assert payload["workflow"] == "my_workflow"
    assert payload["status"] == "ok"


async def test_wait_with_nothing_scheduled_returns_immediately() -> None:
    notifier = NotificationSink((), run_id="r1", workflow="demo")
    assert await notifier.wait() == []


async def test_wait_times_out_a_slow_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    async def hangs(
        config: NotificationConfig, payload: dict[str, object], *, key: str
    ) -> delivery.DeliveryReceipt:
        await asyncio.sleep(10)
        return delivery.DeliveryReceipt(config.name, "delivered", 1)

    monkeypatch.setattr(sink_module, "deliver", hangs)
    notifier = NotificationSink(
        (_config("slow", frozenset({"run_finished"})),), run_id="r1", workflow="demo"
    )
    notifier.handle(RunFinished(status="ok", duration_ms=10))
    receipts = await notifier.wait(timeout=0.05)
    assert receipts[0].status == "failed"
