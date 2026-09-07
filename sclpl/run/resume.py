"""G2: resume eligibility planning.

Walks a workflow's static plan against a specific prior run and decides, for every
step, whether its checkpointed value is safe to reuse, must rerun, or -- for a
non-idempotent write whose prior outcome cannot be trusted -- needs an explicit
recovery policy before it can safely rerun at all. Nothing here executes a step,
issues a request, or writes anything; it only reads history and checkpoints, so a
plan is always safe to produce before a real resume (G3) touches anything.

The whole thing rests on one propagation rule: a step's identity only means
something if everything it was built from is itself trustworthy. A step with no
step dependencies is compared directly, by recomputing the exact key `execute._cache_key`
would compute today and checking it against what the prior run recorded. A step that
reads another step's output is compared the same way -- but only once that ancestor's
own verdict is `"reuse"`, at which point its checkpointed value is rehydrated into a
throwaway store so the *real* interpolation and cache-key logic can resolve the
reference, rather than this module re-deriving an approximation of it. An ancestor
that will rerun poisons everything downstream of it by construction: nothing here
recomputes what that ancestor's fresh output would be, so nothing built from it can
be trusted unchanged either. That is what satisfies "drift and missing artifacts
invalidate affected steps and descendants" without a bespoke case for it.

Dynamic control flow (`foreach`/`while`/`if`/`parallel`/`gate`/`use`) is a single
opaque node in the static plan -- its body is not (`compile_plan.py`'s own docstring:
"a nested body step is not a node... It becomes one when its parent runs"). Such a
node, and everything statically downstream of it, always plans as `"rerun"`: there is
no static way to know a loop's per-iteration identity without evaluating it, and
guessing would be exactly the kind of speculative correctness this module exists to
avoid. G3, which actually re-expands the loop, can check each iteration's own
checkpoint directly at that point, the same way this module checks a static step's.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from sclpl.render.reporter import Reporter
from sclpl.run import checkpoints
from sclpl.run.execute import Runtime, _cache_key
from sclpl.run.ir import HttpConfig, Step, WorkflowDoc
from sclpl.run.preflight import Report
from sclpl.run.retry import IDEMPOTENT_METHODS
from sclpl.run.transport import Pool
from sclpl.state import db
from sclpl.values import cache as cache_mod
from sclpl.values.store import ValueStore

#: A checkpointed value exists, its identity matches, and it is safe to reuse as-is.
REUSE = "reuse"
#: The step must execute again -- no ambiguity about a prior side effect either way.
RERUN = "rerun"
#: A non-idempotent write whose prior outcome cannot be trusted; rerunning it blindly
#: risks repeating an effect that may already have happened. Needs an operator decision
#: G2 does not make on its own.
REFUSE = "refuse"


@dataclass(frozen=True, slots=True)
class StepVerdict:
    """One step's resume disposition, and why."""

    node_id: str
    verdict: str
    reason: str


@dataclass(slots=True)
class ResumePlan:
    """Every step's verdict, in the order the plan would run them."""

    parent_run_id: str
    verdicts: list[StepVerdict] = field(default_factory=list)

    def by_verdict(self, verdict: str) -> list[StepVerdict]:
        return [entry for entry in self.verdicts if entry.verdict == verdict]

    def counts(self) -> dict[str, int]:
        counts = {REUSE: 0, RERUN: 0, REFUSE: 0}
        for entry in self.verdicts:
            counts[entry.verdict] += 1
        return counts


async def plan_resume(
    doc: WorkflowDoc,
    report: Report,
    variables: dict[str, object],
    parent_run_id: str,
    *,
    history: db.History,
    store: checkpoints.Store,
    cache: cache_mod.Cache,
) -> ResumePlan:
    """Explain reuse/rerun/refusal for every step of ``doc``, against ``parent_run_id``.

    ``variables`` is the same resolved `vars`/`--var` mapping a real run would build
    (`doc.vars` + `report.resolved.vars` + CLI overrides) -- what a step with no
    upstream step dependency is compared against directly. ``cache`` is never read
    from or written to here -- `_cache_key` only consults its *policy*, the same
    gate a real run uses to decide a step is cacheable at all, so a step a real run
    would never have checkpointed (`--no-cache`, or `cache off` on the step) is
    never claimed reusable here either.
    """
    assert report.plan is not None
    plan = report.plan
    parent = history.find(parent_run_id)

    if parent["workflow"] != doc.name:
        return ResumePlan(
            parent_run_id,
            [
                StepVerdict(node_id, RERUN, "parent run is a different workflow")
                for node_id in plan.topological()
            ],
        )

    prior_steps = {row["step_id"]: row for row in history.steps_of(parent_run_id)}
    runtime = Runtime(
        doc=doc,
        store=ValueStore(),
        reporter=Reporter([]),
        pool=Pool(),
        vars=dict(variables),
        cache=cache,
    )

    verdicts: dict[str, StepVerdict] = {}
    for node_id in plan.topological():
        step = doc.step(node_id)
        if step is None:  # pragma: no cover - plan nodes are always declared steps
            continue
        node = plan.nodes[node_id]
        prior = prior_steps.get(node_id)
        blocked = any(verdicts[need].verdict != REUSE for need in node.needs)

        if step.kind not in ("http", "fn"):
            entry = StepVerdict(
                node_id, RERUN, "control flow is always re-planned at execution time"
            )
        elif prior is None:
            entry = StepVerdict(node_id, RERUN, "new step, no prior record")
        elif blocked:
            entry = _blocked_verdict(node_id, step)
        else:
            entry = await _compare(node_id, step, prior, runtime, parent_run_id, store)
            if entry.verdict == REUSE:
                value = store.read(parent_run_id, node_id)
                runtime.store.put(
                    node.publishes, value, readers=plan.readers_of(node.publishes), pinned=True
                )

        verdicts[node_id] = entry

    return ResumePlan(parent_run_id, [verdicts[node_id] for node_id in plan.topological()])


def _blocked_verdict(node_id: str, step: Step) -> StepVerdict:
    if _needs_explicit_policy(step):
        return StepVerdict(
            node_id,
            REFUSE,
            "an upstream step will rerun; a non-idempotent write cannot safely follow it "
            "without an explicit recovery policy",
        )
    return StepVerdict(
        node_id, RERUN, "an upstream step will rerun, so this step's inputs are not trustworthy"
    )


async def _compare(
    node_id: str,
    step: Step,
    prior: sqlite3.Row,
    runtime: Runtime,
    parent_run_id: str,
    store: checkpoints.Store,
) -> StepVerdict:
    try:
        key = await _cache_key(step, runtime)
    except Exception:  # noqa: BLE001 - a planning pass must never crash because this
        # run's inputs cannot yet resolve an expression the way real execution would.
        key = None
    if key is None:
        return StepVerdict(node_id, RERUN, "not a checkpointed step (writer, or cache disabled)")
    if prior["status"] != "ok":
        return _uncertain(node_id, step, f"prior attempt did not succeed ({prior['status']})")
    if prior["identity_key"] != key:
        return _uncertain(
            node_id, step, "step definition or resolved inputs changed since the prior run"
        )
    if not store.exists(parent_run_id, node_id):
        return _uncertain(node_id, step, "no valid checkpoint to reuse")
    return StepVerdict(node_id, REUSE, "identity and checkpoint match")


def _uncertain(node_id: str, step: Step, reason: str) -> StepVerdict:
    if _needs_explicit_policy(step):
        return StepVerdict(
            node_id,
            REFUSE,
            f"{reason}; a non-idempotent write needs an explicit recovery policy before rerunning",
        )
    return StepVerdict(node_id, RERUN, reason)


def _needs_explicit_policy(step: Step) -> bool:
    """A non-idempotent HTTP write, per SPEC's G3 refusal criterion.

    Scoped to HTTP: a local `fn` side effect (writing a file) is deterministic and
    safe to simply redo, with no remote server that might have already received a
    request this run cannot confirm.
    """
    config = step.config
    if not isinstance(config, HttpConfig):
        return False
    return config.method not in IDEMPOTENT_METHODS and not step.retry.idempotent
