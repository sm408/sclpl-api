"""G2: resume eligibility planning.

Builds a small workflow directly from the IR (no parser needed) and a `db.History`/
`checkpoints.Store` pair standing in for "what a prior run actually left behind",
then checks `plan_resume`'s reuse/rerun/refuse verdicts against every scenario its
own design is meant to handle.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from sclpl.render.reporter import Reporter
from sclpl.run import checkpoints, resume
from sclpl.run.execute import Runtime, _cache_key
from sclpl.run.ir import HttpConfig, LetConfig, Retry, Step, WorkflowDoc
from sclpl.run.preflight import preflight
from sclpl.run.transport import Pool
from sclpl.state import db
from sclpl.values import cache as cache_mod
from sclpl.values.store import ValueStore

Env = tuple[db.History, checkpoints.Store, cache_mod.Cache]


def _doc(**overrides: object) -> WorkflowDoc:
    steps = [
        Step(id="a", kind="http", config=HttpConfig(method="GET", url="https://api.test/base")),
        Step(
            id="b",
            kind="http",
            config=HttpConfig(method="GET", url="https://api.test/detail", query={"id": "@a"}),
        ),
        Step(
            id="c",
            kind="http",
            config=HttpConfig(method="POST", url="https://api.test/submit", body={"v": 1}),
        ),
        Step(
            id="notify",
            kind="http",
            config=HttpConfig(method="POST", url="https://api.test/notify", body={"ref": "@a"}),
        ),
        Step(id="note", kind="let", config=LetConfig(value=1)),
    ]
    defaults: dict[str, object] = {"name": "wf", "steps": steps}
    defaults.update(overrides)
    return WorkflowDoc(**defaults)  # type: ignore[arg-type]


def _step(doc: WorkflowDoc, step_id: str) -> Step:
    found = doc.step(step_id)
    assert found is not None
    return found


async def _real_key(
    step: Step,
    doc: WorkflowDoc,
    variables: dict[str, object],
    upstream: dict[str, object] | None,
    cache: cache_mod.Cache,
) -> str | None:
    """The exact key `plan_resume` itself would compute -- the oracle prior identity
    keys are built from, so a test never hand-hashes something that could drift from
    the real implementation.
    """
    store = ValueStore()
    for name, value in (upstream or {}).items():
        store.put(name, value, readers=99, pinned=True)
    runtime = Runtime(
        doc=doc, store=store, reporter=Reporter([]), pool=Pool(), vars=variables, cache=cache
    )
    return await _cache_key(step, runtime)


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    history = db.History(tmp_path / "history")
    store = checkpoints.Store(tmp_path / "checkpoints")
    cache = cache_mod.Cache(tmp_path / "cache")
    yield history, store, cache
    history.close()
    store.close()
    cache.close()


def _record(history: db.History, run_id: str, workflow: str, steps: list[db.StepRecord]) -> None:
    history.record(
        db.RunRecord(id=run_id, name=run_id, workflow=workflow, status="ok", steps=steps)
    )


async def _plan(
    doc: WorkflowDoc, variables: dict[str, object], run_id: str, env: Env
) -> resume.ResumePlan:
    history, store, cache = env
    report = preflight(doc, check_files=False, require_ports=False)
    assert report.ok, [str(problem) for problem in report.problems]
    return await resume.plan_resume(
        doc, report, variables, run_id, history=history, store=store, cache=cache
    )


def _verdict(plan: resume.ResumePlan, node_id: str) -> resume.StepVerdict:
    matches = [entry for entry in plan.verdicts if entry.node_id == node_id]
    assert matches, f"no verdict for {node_id!r}"
    return matches[0]


# -- everything unchanged: reuse -----------------------------------------------------


async def test_an_unchanged_leaf_step_reuses_its_checkpoint(env: Env) -> None:
    history, store, cache = env
    doc = _doc()
    variables: dict[str, object] = {}
    key = await _real_key(_step(doc, "a"), doc, variables, None, cache)
    assert key is not None
    _record(history, "p1", "wf", [db.StepRecord(step_id="a", status="ok", identity_key=key)])
    store.write("p1", "a", {"body": "hi"})

    plan = await _plan(doc, variables, "p1", env)
    entry = _verdict(plan, "a")
    assert entry.verdict == resume.REUSE


async def test_an_unchanged_dependent_step_reuses_once_its_ancestor_is_rehydrated(
    env: Env,
) -> None:
    history, store, cache = env
    doc = _doc()
    variables: dict[str, object] = {}
    key_a = await _real_key(_step(doc, "a"), doc, variables, None, cache)
    upstream: dict[str, object] = {"a": {"id": 7}}
    key_b = await _real_key(_step(doc, "b"), doc, variables, upstream, cache)
    assert key_a is not None and key_b is not None
    _record(
        history,
        "p1",
        "wf",
        [
            db.StepRecord(step_id="a", status="ok", identity_key=key_a),
            db.StepRecord(step_id="b", status="ok", identity_key=key_b),
        ],
    )
    store.write("p1", "a", {"id": 7})
    store.write("p1", "b", {"detail": "x"})

    plan = await _plan(doc, variables, "p1", env)
    assert _verdict(plan, "a").verdict == resume.REUSE
    assert _verdict(plan, "b").verdict == resume.REUSE


# -- new / missing -------------------------------------------------------------------


async def test_a_step_with_no_prior_record_reruns(env: Env) -> None:
    history, _store, cache = env
    doc = _doc()
    _record(history, "p1", "wf", [])  # nothing recorded at all

    plan = await _plan(doc, {}, "p1", env)
    entry = _verdict(plan, "a")
    assert entry.verdict == resume.RERUN
    assert "new step" in entry.reason


async def test_a_matching_identity_with_no_checkpoint_still_reruns(
    env: Env,
) -> None:
    history, _store, cache = env
    doc = _doc()
    key = await _real_key(_step(doc, "a"), doc, {}, None, cache)
    assert key is not None
    _record(history, "p1", "wf", [db.StepRecord(step_id="a", status="ok", identity_key=key)])
    # deliberately never call store.write -- no checkpoint exists

    plan = await _plan(doc, {}, "p1", env)
    entry = _verdict(plan, "a")
    assert entry.verdict == resume.RERUN
    assert "no valid checkpoint" in entry.reason


# -- drift ----------------------------------------------------------------------------


async def test_a_changed_resolved_input_is_detected_as_drift(
    env: Env,
) -> None:
    history, store, cache = env
    doc = _doc(
        steps=[
            Step(
                id="a",
                kind="http",
                config=HttpConfig(method="GET", url="{{base}}/orders"),
            ),
        ]
    )
    key = await _real_key(_step(doc, "a"), doc, {"base": "https://one.test"}, None, cache)
    assert key is not None
    _record(history, "p1", "wf", [db.StepRecord(step_id="a", status="ok", identity_key=key)])
    store.write("p1", "a", {"body": "hi"})

    plan = await _plan(doc, {"base": "https://two.test"}, "p1", env)
    entry = _verdict(plan, "a")
    assert entry.verdict == resume.RERUN
    assert "changed" in entry.reason


async def test_ancestor_drift_forces_an_idempotent_dependent_to_rerun(
    env: Env,
) -> None:
    history, store, cache = env
    doc = _doc(
        steps=[
            Step(id="a", kind="http", config=HttpConfig(method="GET", url="{{base}}/orders")),
            Step(
                id="b",
                kind="http",
                config=HttpConfig(method="GET", url="https://api.test/detail", query={"id": "@a"}),
            ),
        ]
    )
    old_vars: dict[str, object] = {"base": "https://one.test"}
    key_a = await _real_key(_step(doc, "a"), doc, old_vars, None, cache)
    key_b = await _real_key(_step(doc, "b"), doc, old_vars, {"a": {"id": 1}}, cache)
    assert key_a is not None and key_b is not None
    _record(
        history,
        "p1",
        "wf",
        [
            db.StepRecord(step_id="a", status="ok", identity_key=key_a),
            db.StepRecord(step_id="b", status="ok", identity_key=key_b),
        ],
    )
    store.write("p1", "a", {"id": 1})
    store.write("p1", "b", {"detail": "x"})

    plan = await _plan(doc, {"base": "https://two.test"}, "p1", env)
    assert _verdict(plan, "a").verdict == resume.RERUN
    entry_b = _verdict(plan, "b")
    assert entry_b.verdict == resume.RERUN
    assert "upstream" in entry_b.reason


async def test_ancestor_drift_forces_a_non_idempotent_dependent_write_to_refuse(
    env: Env,
) -> None:
    history, store, cache = env
    doc = _doc(
        steps=[
            Step(id="a", kind="http", config=HttpConfig(method="GET", url="{{base}}/orders")),
            Step(
                id="notify",
                kind="http",
                config=HttpConfig(method="POST", url="https://api.test/notify", body={"ref": "@a"}),
            ),
        ]
    )
    old_vars: dict[str, object] = {"base": "https://one.test"}
    key_a = await _real_key(_step(doc, "a"), doc, old_vars, None, cache)
    key_n = await _real_key(_step(doc, "notify"), doc, old_vars, {"a": {"id": 1}}, cache)
    assert key_a is not None and key_n is not None
    _record(
        history,
        "p1",
        "wf",
        [
            db.StepRecord(step_id="a", status="ok", identity_key=key_a),
            db.StepRecord(step_id="notify", status="ok", identity_key=key_n),
        ],
    )
    store.write("p1", "a", {"id": 1})
    store.write("p1", "notify", {"sent": True})

    plan = await _plan(doc, {"base": "https://two.test"}, "p1", env)
    entry = _verdict(plan, "notify")
    assert entry.verdict == resume.REFUSE
    assert "explicit recovery policy" in entry.reason


# -- non-idempotent writes: uncertain outcome vs. confirmed success ------------------


async def test_a_non_idempotent_write_with_no_successful_prior_attempt_is_refused(
    env: Env,
) -> None:
    history, _store, cache = env
    doc = _doc()
    key_c = await _real_key(_step(doc, "c"), doc, {}, None, cache)
    assert key_c is not None
    _record(history, "p1", "wf", [db.StepRecord(step_id="c", status="failed", identity_key=key_c)])

    plan = await _plan(doc, {}, "p1", env)
    entry = _verdict(plan, "c")
    assert entry.verdict == resume.REFUSE
    assert "did not succeed" in entry.reason


async def test_a_non_idempotent_write_that_already_succeeded_is_reused_not_repeated(
    env: Env,
) -> None:
    """The point of resume: a confirmed-successful POST must never fire twice."""
    history, store, cache = env
    doc = _doc()
    key_c = await _real_key(_step(doc, "c"), doc, {}, None, cache)
    assert key_c is not None
    _record(history, "p1", "wf", [db.StepRecord(step_id="c", status="ok", identity_key=key_c)])
    store.write("p1", "c", {"accepted": True})

    plan = await _plan(doc, {}, "p1", env)
    entry = _verdict(plan, "c")
    assert entry.verdict == resume.REUSE


async def test_a_step_explicitly_marked_idempotent_is_never_refused(
    env: Env,
) -> None:
    history, _store, cache = env
    doc = _doc(
        steps=[
            Step(
                id="c",
                kind="http",
                config=HttpConfig(method="POST", url="https://api.test/submit", body={"v": 1}),
                retry=Retry(idempotent=True),
            ),
        ]
    )
    key_c = await _real_key(_step(doc, "c"), doc, {}, None, cache)
    assert key_c is not None
    _record(history, "p1", "wf", [db.StepRecord(step_id="c", status="failed", identity_key=key_c)])

    plan = await _plan(doc, {}, "p1", env)
    entry = _verdict(plan, "c")
    assert entry.verdict == resume.RERUN


# -- control flow and workflow identity ----------------------------------------------


async def test_control_flow_always_reruns(env: Env) -> None:
    history, store, cache = env
    doc = _doc()
    _record(history, "p1", "wf", [db.StepRecord(step_id="note", status="ok", identity_key="")])
    store.write("p1", "note", 1)

    plan = await _plan(doc, {}, "p1", env)
    entry = _verdict(plan, "note")
    assert entry.verdict == resume.RERUN
    assert "control flow" in entry.reason


async def test_a_different_workflow_refuses_reuse_of_everything(
    env: Env,
) -> None:
    history, store, cache = env
    doc = _doc()
    key = await _real_key(_step(doc, "a"), doc, {}, None, cache)
    assert key is not None
    step_record = db.StepRecord(step_id="a", status="ok", identity_key=key)
    _record(history, "p1", "unrelated-workflow", [step_record])
    store.write("p1", "a", {"body": "hi"})

    plan = await _plan(doc, {}, "p1", env)
    for entry in plan.verdicts:
        assert entry.verdict == resume.RERUN
        assert "different workflow" in entry.reason


async def test_counts_tally_every_verdict(env: Env) -> None:
    history, _store, cache = env
    doc = _doc()
    _record(history, "p1", "wf", [])

    plan = await _plan(doc, {}, "p1", env)
    counts = plan.counts()
    assert sum(counts.values()) == len(plan.verdicts) == len(doc.steps)
