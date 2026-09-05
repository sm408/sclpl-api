"""`secret()` and the reporter it is supposed to protect its return value with.

The module docstring in `secrets_fns.py` has always promised that `Reporter.secret()`
does the redacting -- "this can return the real thing and every sink still shows it
redacted." Nothing ever called it, so the promise was aspirational. These pin the fix:
the value a workflow resolves through `secret()` must be unreadable through the same
reporter the instant it comes back, in every place that calls it -- an expression, not
just a step.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from sclpl import bootstrap
from sclpl.expr import Context, evaluate, parse
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter, active_reporter
from sclpl.state import secrets as store
from sclpl.values import ValueStore

bootstrap.load(plugins=False)


@pytest.fixture(autouse=True)
def no_backends(monkeypatch: Any) -> None:
    """Force `secret()` to the `SCLPL_SECRET_*` environment fallback, deterministically."""
    monkeypatch.setattr(store, "_keyring", lambda: None)
    monkeypatch.setattr(store, "_fernet", lambda: None)


async def evaluate_expr(source: str) -> Any:
    return await evaluate(parse(source), Context(store=ValueStore(), vars={}))


async def test_calling_secret_registers_it_with_the_active_reporter(monkeypatch: Any) -> None:
    monkeypatch.setenv("SCLPL_SECRET_TOKEN", "sk-live-distinctive-value")
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        value = await evaluate_expr("secret('token')")
        assert value == "sk-live-distinctive-value"
        assert "sk-live-distinctive-value" not in reporter.scrub(f"used {value} just now")


async def test_no_active_reporter_still_returns_the_secret(monkeypatch: Any) -> None:
    """Outside a run -- a direct call from a test, say -- there is nothing to fail."""
    monkeypatch.setenv("SCLPL_SECRET_TOKEN", "sk-live-distinctive-value")
    assert active_reporter() is None
    assert await evaluate_expr("secret('token')") == "sk-live-distinctive-value"


async def test_a_missing_secret_still_raises_with_the_reporter_active() -> None:
    from sclpl.errors import ValidationError

    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]):
        with pytest.raises(ValidationError):
            await evaluate_expr("secret('does-not-exist')")


async def test_a_secret_too_short_to_redact_does_not_fail_the_call(monkeypatch: Any) -> None:
    """`TooShortToRedact` is `Redactor.add`'s refusal, not a reason to fail a request."""
    monkeypatch.setenv("SCLPL_SECRET_SHORT", "abc")
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]):
        assert await evaluate_expr("secret('short')") == "abc"
