"""I4: parsing and validating `[notifications.<name>]` project manifest tables."""

from __future__ import annotations

import pytest

from sclpl.errors import ValidationError
from sclpl.notifications import config


def test_no_notifications_table_is_empty() -> None:
    assert config.parse({}, where="x") == ()


@pytest.mark.parametrize(
    ("table", "match"),
    [
        ({"n": {"kind": "webhook"}}, "url is required"),
        ({"n": {"kind": "smtp", "to": []}}, "needs a non-empty 'to'"),
        ({"n": {"kind": "carrier-pigeon"}}, "kind must be one of"),
        (
            {"n": {"kind": "webhook", "url": "https://x", "on": ["not_a_real_event"]}},
            "unknown event",
        ),
    ],
)
def test_an_invalid_table_is_refused(table: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        config.parse({"notifications": table}, where="x")


def test_valid_webhook_parses_with_defaults() -> None:
    (result,) = config.parse(
        {"notifications": {"n": {"kind": "webhook", "url": "https://example.com/hook"}}},
        where="x",
    )
    assert result.name == "n"
    assert result.kind == "webhook"
    assert result.enabled is False
    assert result.on == {"run_finished"}


def test_valid_smtp_parses() -> None:
    (result,) = config.parse(
        {
            "notifications": {
                "n": {
                    "kind": "smtp",
                    "to": ["ops@example.com"],
                    "from": "sclpl@example.com",
                    "smtp_host": "smtp.example.com",
                }
            }
        },
        where="x",
    )
    assert result.to == ("ops@example.com",)
    assert result.smtp_port == 587


def test_enabled_and_on_are_respected() -> None:
    (result,) = config.parse(
        {
            "notifications": {
                "n": {
                    "kind": "slack",
                    "url": "https://hooks.slack.com/x",
                    "enabled": True,
                    "on": ["run_started", "step_failed"],
                }
            }
        },
        where="x",
    )
    assert result.enabled is True
    assert result.on == {"run_started", "step_failed"}
