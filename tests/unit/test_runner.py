"""What `_remember` writes to a failed step's error -- A5's other credential sink.

`safe_args.render` already keeps a live credential off the command line before it
reaches history. A step's own failure message did not get the same treatment: the old
code stored `error=str(error)` verbatim, so an exception that happened to echo a
resolved secret (an auth failure quoting the token it rejected, say) persisted it to
disk unredacted and forever. This pins the fix: a failed step's error is scrubbed
through the same reporter the run itself used, so anything registered via
`Reporter.secret()` -- including what `secret()` itself now registers -- disappears
from it too.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from sclpl.render.plain import PlainSink
from sclpl.render.redact import MASK
from sclpl.render.reporter import Reporter
from sclpl.run.execute import Runtime
from sclpl.run.ir import WorkflowDoc
from sclpl.run.preflight import Report
from sclpl.run.runner import Options, _remember
from sclpl.run.schedule import Outcome
from sclpl.run.transport import Pool
from sclpl.state import db
from sclpl.values.store import ValueStore


@pytest.fixture(autouse=True)
def private_home(tmp_path: Path, monkeypatch: Any) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("SCLPL_HOME", str(home))
    return home


def make_reporter(secrets: list[str] = []) -> Reporter:  # noqa: B006 - never mutated
    reporter = Reporter([PlainSink(io.StringIO(), verbosity=-2)])
    for value in secrets:
        reporter.secret(value)
    return reporter


def _runtime(doc: WorkflowDoc, reporter: Reporter) -> Runtime:
    return Runtime(doc=doc, store=ValueStore(), reporter=reporter, pool=Pool())


def test_a_step_error_containing_a_resolved_secret_is_scrubbed(private_home: Path) -> None:
    doc = WorkflowDoc(name="orders")
    error = ValueError("auth failed with token hunter2-distinctive")
    reporter = make_reporter(["hunter2-distinctive"])
    _remember(
        doc,
        Options(),
        Report(workflow="orders"),
        Outcome(status="failed", failed={"fetch": error}),
        1,
        0.0,
        None,
        reporter,
        _runtime(doc, reporter),
    )

    with db.History() as history:
        run_id = db.run_id("orders", 0.0)
        steps = history.steps_of(run_id)
        assert "hunter2-distinctive" not in steps[0]["error"]
        assert MASK in steps[0]["error"]


def test_a_step_error_with_no_resolved_secrets_is_left_readable(private_home: Path) -> None:
    doc = WorkflowDoc(name="orders")
    error = ValueError("connection refused")
    reporter = make_reporter()
    _remember(
        doc,
        Options(),
        Report(workflow="orders"),
        Outcome(status="failed", failed={"fetch": error}),
        1,
        1.0,
        None,
        reporter,
        _runtime(doc, reporter),
    )

    with db.History() as history:
        run_id = db.run_id("orders", 1.0)
        steps = history.steps_of(run_id)
        assert steps[0]["error"] == "connection refused"
