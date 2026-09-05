"""History never persists credentials passed through ordinary CLI syntax."""

from __future__ import annotations

from sclpl.state.safe_args import REDACTED, render


def test_keeps_normal_replay_arguments() -> None:
    assert render(["run", "orders", "--mode", "quick"]) == "run orders --mode quick"


def test_redacts_secret_options_and_key_value_overrides() -> None:
    saved = render(["run", "orders", "--token", "top-secret", "api_key=also-secret"])
    assert "top-secret" not in saved
    assert "also-secret" not in saved
    assert saved.count(REDACTED) == 2
