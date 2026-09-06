"""E7: publication eligibility -- what each declared output actually depends on.

Two things, both worth doing before anything is written:

1. `derive()`: for every declared output with a writer step, the full transitive set
   of steps it depends on in the *kept* plan, and which of those declare their own
   `assert` -- the output's "validation scope". This is analysis only, meant for
   `run`/`validate` to report and for a later staged-publication mechanism (SPEC
   batch E8) to gate on; it does not defer or block a write itself.

2. `check_stubbed_validation()`: an actual preflight failure. Mode resolution's own
   closure check (`modes._check_closure`) accepts a pruned step whose value a stub or
   a bound input satisfies -- correct for ordinary data, but wrong for validation: a
   stub does not run the `assert` it stands in for. A mode that prunes an
   assert-bearing step which a declared output's writer still transitively depends
   on, papering over the gap with a stub, silently ships unvalidated data under an
   output whose declaration implies it was checked. That is the concrete,
   statically-checkable half of "an assertion cannot be bypassed" that this batch's
   accept criteria name -- bypassed by mode selection rather than outrun by a faster
   sibling. The other half -- a genuinely concurrent independent branch physically
   writing before a sibling's assertion is even evaluated -- cannot be closed by any
   static check; closing it means deferring the write itself, which SPEC batch E8
   ("no destination changes before E7 passes") does, not this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from sclpl.errors import ValidationError
from sclpl.run.ir import Step, WorkflowDoc
from sclpl.run.modes import Resolved
from sclpl.run.plan import Plan


@dataclass(frozen=True, slots=True)
class Eligibility:
    """What a declared output's writer step actually depends on, in the kept plan."""

    port: str
    writer: str
    #: Every kept step the writer transitively depends on, itself included.
    required: frozenset[str]
    #: The subset of `required` that declares its own `assert` clause.
    validation_scope: frozenset[str]

    @property
    def validated(self) -> bool:
        return bool(self.validation_scope)


def derive(doc: WorkflowDoc, plan: Plan) -> dict[str, Eligibility]:
    """One `Eligibility` per declared output port whose writer survived pruning."""
    asserted = {step.id for step in doc.all_steps() if step.assert_}
    result: dict[str, Eligibility] = {}
    for step in doc.all_steps():
        if not step.writes or step.id not in plan:
            continue
        required = _plan_ancestors(plan, step.id)
        result[step.writes] = Eligibility(
            port=step.writes,
            writer=step.id,
            required=frozenset(required),
            validation_scope=frozenset(required & asserted),
        )
    return result


def _plan_ancestors(plan: Plan, node_id: str) -> set[str]:
    """Every kept step `node_id` transitively needs, itself included."""
    seen = {node_id}
    stack = [node_id]
    while stack:
        current = stack.pop()
        node = plan.nodes.get(current)
        if node is None:
            continue
        for need in node.needs:
            if need not in seen:
                seen.add(need)
                stack.append(need)
    return seen


def check_stubbed_validation(doc: WorkflowDoc, resolved: Resolved) -> list[ValidationError]:
    """Fail when a mode stubs past an assertion a declared output still depends on.

    Walks the *full* declared graph, not the pruned plan -- a step the mode removed
    has no node in the pruned `Plan` at all, and seeing it is the entire point.
    """
    if not resolved.stubs:
        return []
    asserted = {step.id for step in doc.all_steps() if step.assert_}
    if not asserted:
        return []
    by_id = {step.id: step for step in doc.all_steps()}
    problems: list[ValidationError] = []
    for step in doc.all_steps():
        if not step.writes or step.id not in resolved.keep:
            continue
        bypassed = sorted(
            candidate
            for candidate in _declared_ancestors(by_id, step.id) & asserted
            if candidate in resolved.stubs
        )
        if not bypassed:
            continue
        plural = len(bypassed) != 1
        problems.append(
            ValidationError(
                f"mode {resolved.name!r} stubs {', '.join(bypassed)} instead of running "
                f"{'them' if plural else 'it'}, but output {step.writes!r} still depends "
                f"on {'their' if plural else 'its'} data",
                remedies=[
                    f"keep it: add {bypassed[0]!r} to the mode's include list",
                    "or stub the value this output actually needs, not the step validating it",
                ],
            )
        )
    return problems


def _declared_ancestors(by_id: dict[str, Step], node_id: str) -> set[str]:
    """Every step `node_id` needs, transitively, over the whole declared graph --
    unlike `_plan_ancestors`, pruning is not applied: a pruned step is exactly what
    this has to still be able to see.
    """
    from sclpl.expr.refs import refs_in, refs_in_value

    seen = {node_id}
    stack = [node_id]
    while stack:
        current = stack.pop()
        step = by_id.get(current)
        if step is None:
            continue
        references = set(refs_in_value(step.config)) | set(step.needs)
        for clause in (step.assert_, step.skip_if, step.retry_if):
            if clause:
                references.update(refs_in(clause))
        for need in references:
            if need in by_id and need not in seen:
                seen.add(need)
                stack.append(need)
    return seen
