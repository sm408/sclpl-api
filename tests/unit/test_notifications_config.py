"""I4: parsing and validating `[notifications.<name>]` project manifest tables."""

from __future__ import annotations

import pytest

from sclpl.errors import ValidationError
from sclpl.notifications import config


def test_no_notifications_table_is_empty() -> None:
    assert config.parse({}, where="x") == ()


def test_webhook_requires_a_url() -> None:
    with pytest.raises(ValidationError, match="url is required"):
        config.parse({"notifications": {"n": {"kind": "webhook"}}}, where="x")


def test_valid_webhook_parses_with_defaults() -> None:
    (result,) = config.parse(
        {"notifications": {"n": {"kind": "webhook", "url": "https://example.com/hook"}}},
        where="x",
    )
    assert result.name == "n"
    assert result.kind == "webhook"
    assert result.enabled is False
    assert result.on == {"run_finished"}


def test_smtp_requires_to_from_and_host() -> None:
    with pytest.raises(ValidationError, match="needs a non-empty 'to'"):
        config.parse({"notifications": {"n": {"kind": "smtp", "to": []}}}, where="x")


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


def test_unknown_kind_is_refused() -> None:
    with pytest.raises(ValidationError, match="kind must be one of"):
        config.parse({"notifications": {"n": {"kind": "carrier-pigeon"}}}, where="x")


def test_unknown_event_in_on_is_refused() -> None:
    with pytest.raises(ValidationError, match="unknown event"):
        config.parse(
            {
                "notifications": {
                    "n": {"kind": "webhook", "url": "https://x", "on": ["not_a_real_event"]}
                }
            },
            where="x",
        )


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
