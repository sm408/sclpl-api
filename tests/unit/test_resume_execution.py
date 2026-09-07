"""G3: `runner._resume` -- turning G2's plan into what `run_workflow` actually
needs to resume: a pruned execution plan, rehydrated stubs, propagated
completeness, or a refusal. `tests/integration/test_resume_e2e.py` proves the
real CLI wiring; this covers behavior that is awkward to trigger through a real
HTTP round trip, most of all completeness propagation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sclpl.errors import PolicyDenied
from sclpl.render.reporter import Reporter
from sclpl.run import checkpoints
from sclpl.run.execute import Runtime, _cache_key
from sclpl.run.ir import HttpConfig, Step, WorkflowDoc
from sclpl.run.preflight import preflight
from sclpl.run.runner import _resume
from sclpl.run.transport import Pool
from sclpl.state import db
from sclpl.values import cache as cache_mod
from sclpl.values.store import ValueStore


@pytest.fixture(autouse=True)
def private_home(tmp_path: Path, monkeypatch: Any) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("SCLPL_HOME", str(home))
    monkeypatch.setenv("SCLPL_CACHE_DIR", str(home / "cache"))
    return home


def _doc(**overrides: object) -> WorkflowDoc:
    steps = [
        Step(id="a", kind="http", config=HttpConfig(method="GET", url="https://api.test/base")),
        Step(
            id="b",
            kind="http",
            config=HttpConfig(method="GET", url="https://api.test/detail", query={"id": "@a"}),
        ),
    ]
    defaults: dict[str, object] = {"name": "wf", "steps": steps}
    defaults.update(overrides)
    return WorkflowDoc(**defaults)  # type: ignore[arg-type]


def _step(doc: WorkflowDoc, step_id: str) -> Step:
    found = doc.step(step_id)
    assert found is not None
    return found


async def _real_key(step: Step, doc: WorkflowDoc, variables: dict[str, object]) -> str:
    runtime = Runtime(
        doc=doc,
        store=ValueStore(),
        reporter=Reporter([]),
        pool=Pool(),
        vars=variables,
        cache=cache_mod.Cache(cache_mod.default_root()),
    )
    key = await _cache_key(step, runtime)
    assert key is not None
    return key


def _record(workflow: str, run_id: str, completeness: str, steps: list[db.StepRecord]) -> None:
    with db.History() as history:
        history.record(
            db.RunRecord(
                id=run_id,
                name=run_id,
                workflow=workflow,
                status="ok",
                completeness=completeness,
                steps=steps,
            )
        )


async def test_a_partial_parent_makes_the_resumed_run_no_better_than_partial() -> None:
    doc = _doc()
    key = await _real_key(_step(doc, "a"), doc, {})
    _record("wf", "p1", "partial", [db.StepRecord(step_id="a", status="ok", identity_key=key)])
    with checkpoints.Store() as store:
        store.write("p1", "a", {"id": 1})

    report = preflight(doc, check_files=False, require_ports=False)
    assert report.ok
    resumed = await _resume(doc, report, {}, "p1", frozenset())

    assert resumed.problem is None
    assert resumed.completeness == ["partial"]


async def test_a_complete_parent_propagates_no_completeness_penalty() -> None:
    doc = _doc()
    key = await _real_key(_step(doc, "a"), doc, {})
    _record("wf", "p1", "complete", [db.StepRecord(step_id="a", status="ok", identity_key=key)])
    with checkpoints.Store() as store:
        store.write("p1", "a", {"id": 1})

    report = preflight(doc, check_files=False, require_ports=False)
    assert report.ok
    resumed = await _resume(doc, report, {}, "p1", frozenset())

    assert resumed.problem is None
    assert resumed.completeness == []


async def test_resume_prunes_the_execution_plan_to_exclude_reused_steps() -> None:
    doc = _doc()
    variables: dict[str, object] = {}
    key_a = await _real_key(_step(doc, "a"), doc, variables)
    with checkpoints.Store() as store:
        store.write("p1", "a", {"id": 7})
    _record("wf", "p1", "complete", [db.StepRecord(step_id="a", status="ok", identity_key=key_a)])

    report = preflight(doc, mode=None, check_files=False, require_ports=False)
    assert report.ok and report.plan is not None
    resumed = await _resume(doc, report, variables, "p1", frozenset())

    assert resumed.problem is None
    assert "a" not in resumed.plan.nodes
    assert "b" in resumed.plan.nodes
    assert len(resumed.plan) == len(report.plan) - 1
    assert resumed.stubs["a"] == {"id": 7}


async def test_a_refusal_names_the_step_and_asks_for_force_resume() -> None:
    doc = _doc(
        steps=[
            Step(
                id="submit",
                kind="http",
                config=HttpConfig(method="POST", url="https://api.test/submit", body={"v": 1}),
            ),
        ]
    )
    key = await _real_key(_step(doc, "submit"), doc, {})
    _record(
        "wf", "p1", "complete", [db.StepRecord(step_id="submit", status="failed", identity_key=key)]
    )

    report = preflight(doc, check_files=False, require_ports=False)
    assert report.ok
    resumed = await _resume(doc, report, {}, "p1", frozenset())

    assert isinstance(resumed.problem, PolicyDenied)
    assert "submit" in str(resumed.problem)
    assert "--force-resume" in str(resumed.problem)


async def test_force_resume_lifts_the_refusal_for_that_step() -> None:
    doc = _doc(
        steps=[
            Step(
                id="submit",
                kind="http",
                config=HttpConfig(method="POST", url="https://api.test/submit", body={"v": 1}),
            ),
        ]
    )
    key = await _real_key(_step(doc, "submit"), doc, {})
    _record(
        "wf", "p1", "complete", [db.StepRecord(step_id="submit", status="failed", identity_key=key)]
    )

    report = preflight(doc, check_files=False, require_ports=False)
    assert report.ok
    resumed = await _resume(doc, report, {}, "p1", frozenset({"submit"}))

    assert resumed.problem is None
    # Refused, not reused: still not a valid checkpoint to reuse -- it simply
    # reruns, exactly like an ordinary miss, once the refusal itself is lifted.
    assert "submit" in resumed.plan.nodes
