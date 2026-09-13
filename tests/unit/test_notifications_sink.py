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


async def test_run_finished_dispatches_to_a_matching_notifier(fake_deliver: list[tuple[str, dict[str, object]]]) -> None:
    notifier = NotificationSink(
        (_config("n", frozenset({"run_finished"})),), run_id="r1", workflow="demo"
    )
    notifier.handle(RunFinished(status="ok", duration_ms=10))
    await notifier.wait()
    assert len(fake_deliver) == 1
    assert fake_deliver[0][0] == "n"


async def test_events_not_configured_in_on_are_ignored(fake_deliver: list[tuple[str, dict[str, object]]]) -> None:
    notifier = NotificationSink(
        (_config("n", frozenset({"run_started"})),), run_id="r1", workflow="demo"
    )
    notifier.handle(RunFinished(status="ok", duration_ms=10))
    await notifier.wait()
    assert fake_deliver == []


async def test_disabled_notifiers_never_fire(fake_deliver: list[tuple[str, dict[str, object]]]) -> None:
    notifier = NotificationSink(
        (_config("n", frozenset({"run_finished"}), enabled=False),), run_id="r1", workflow="demo"
    )
    notifier.handle(RunFinished(status="ok", duration_ms=10))
    await notifier.wait()
    assert fake_deliver == []


async def test_a_successful_step_is_not_a_step_failed_event(fake_deliver: list[tuple[str, dict[str, object]]]) -> None:
    notifier = NotificationSink(
        (_config("n", frozenset({"step_failed"})),), run_id="r1", workflow="demo"
    )
    notifier.handle(StepFinished(id="a", status="ok", duration_ms=1))
    await notifier.wait()
    assert fake_deliver == []


async def test_a_failed_step_matches_step_failed(fake_deliver: list[tuple[str, dict[str, object]]]) -> None:
    notifier = NotificationSink(
        (_config("n", frozenset({"step_failed"})),), run_id="r1", workflow="demo"
    )
    notifier.handle(StepFinished(id="a", status="failed", duration_ms=1))
    await notifier.wait()
    assert len(fake_deliver) == 1


async def test_unrelated_event_types_are_ignored(fake_deliver: list[tuple[str, dict[str, object]]]) -> None:
    notifier = NotificationSink(
        (_config("n", frozenset({"run_started", "run_finished", "step_failed"})),),
        run_id="r1",
        workflow="demo",
    )
    notifier.handle(LogRecord(level="info", message="hello"))
    await notifier.wait()
    assert fake_deliver == []


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
