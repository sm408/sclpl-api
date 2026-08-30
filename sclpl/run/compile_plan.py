"""IR to Plan: collect every reference, and hand the graph to the scheduler.

This is where invariant 3 becomes concrete. Every string in a step's configuration is
scanned for `@name` references, and their union with the declared `needs` is what the
DAG is built from. A step that reads `@orders` depends on `orders` whether or not
anybody wrote it down.
"""

from __future__ import annotations

from typing import Any

import httpx

from sclpl.expr.refs import refs_in_value
from sclpl.run.ir import (
    FnConfig,
    ForeachConfig,
    HttpConfig,
    IfConfig,
    Step,
    WhileConfig,
    WorkflowDoc,
)
from sclpl.run.plan import Plan, StepSpec, build

#: Rough cost of one step of each kind, for critical-path weighting. Only the ratios
#: matter: an HTTP request dominates a local expression by orders of magnitude, and
#: scheduling should reflect that before it has any measurements to go on.
WEIGHTS: dict[str, float] = {
    "http": 10.0,
    "fn": 2.0,
    "use": 10.0,
    "let": 0.1,
    "foreach": 5.0,
    "if": 0.1,
    "while": 5.0,
    "do_while": 5.0,
    "gate": 0.1,
    "parallel": 1.0,
}


def compile_plan(
    doc: WorkflowDoc,
    *,
    keep: set[str] | None = None,
    available: set[str] | None = None,
) -> Plan:
    """Build the executable graph for ``doc``, restricted to ``keep`` if given.

    A nested body step is *not* a node. It becomes one when its parent runs and knows
    how many copies of it there are -- once per element for a `foreach`, once per
    iteration for a `while`, not at all for the branch an `if` did not take. The parent
    stands in for it in the graph, which is why `_spec` records the body's names under
    `produces`: a later step reading `@double` waits for the loop, which is the only
    honest answer before the loop has run.
    """
    nested = {child.id for step in doc.all_steps() for child in step.children()}
    steps = [
        step
        for step in doc.all_steps()
        if step.id not in nested and (keep is None or step.id in keep)
    ]
    external = set(available or set()) | set(doc.vars) | set(doc.rules)

    specs = [_spec(step, doc) for step in steps]
    return build(specs, available=external)


def _spec(step: Step, doc: WorkflowDoc) -> StepSpec:
    del doc
    return StepSpec(
        id=step.id,
        reads=frozenset(references(step)),
        needs=frozenset(step.needs),
        tags=frozenset(step.tags),
        host=host_of(step),
        lane=step.lane,
        weight=WEIGHTS.get(step.kind, 1.0),
        produces=frozenset(descendants(step)),
    )


def descendants(step: Step) -> set[str]:
    """Every name produced inside a step's body, at any depth."""
    out: set[str] = set()
    for child in step.children():
        out.add(child.id)
        out |= descendants(child)
    return out


def references(step: Step) -> set[str]:
    """Every `@name` a step needs before it can run, its body included.

    A body step is not a node of its own (see `compile_plan`), so its references are the
    parent's references -- otherwise `foreach @ids` whose body reads `@config` would run
    before `config` existed, and invariant 3 would hold only for steps that happen not
    to be nested.

    Two kinds of name are subtracted, because the body supplies them itself: the loop
    variable, and the ids of sibling steps inside the same body.
    """
    found: set[str] = set()
    _scan(_config_without_bodies(step), found)
    for clause in (step.assert_, step.skip_if, step.retry_if):
        if clause:
            _scan(clause, found)

    inner: set[str] = set()
    for child in step.children():
        inner |= references(child)
    return (found | inner) - descendants(step) - _bound_by(step)


def _bound_by(step: Step) -> set[str]:
    """Names a control-flow step binds for its own body."""
    match step.config:
        case ForeachConfig() as config:
            return {config.var, "index"}
        case _:
            return set()


def _config_without_bodies(step: Step) -> Any:
    """The step's config with nested step lists removed."""
    match step.config:
        case ForeachConfig() as config:
            return {"over": config.over, "collect": config.collect}
        case WhileConfig() as config:
            return {"condition": config.condition}
        case IfConfig() as config:
            return {"condition": config.condition}
        case _:
            return step.config.model_dump()


def _scan(value: Any, found: set[str]) -> None:
    found.update(refs_in_value(value))


def host_of(step: Step) -> str | None:
    """The remote a step talks to, for per-host concurrency.

    A URL built from an interpolation has no host until the value is known. Guessing
    would put the step in the wrong bucket, so it goes in the unbucketed one and is
    governed by the global ceiling alone.
    """
    if not isinstance(step.config, HttpConfig):
        return None
    url = step.config.url
    if "{{" in url:
        prefix = url.split("{{", 1)[0]
        if "://" not in prefix:
            return None
        url = prefix
    try:
        return httpx.URL(url).host or None
    except (httpx.InvalidURL, ValueError):
        return None


def hosts(doc: WorkflowDoc) -> tuple[str, ...]:
    found = {host for host in (host_of(step) for step in doc.all_steps()) if host}
    return tuple(sorted(found))


def function_names(doc: WorkflowDoc) -> set[str]:
    """Every function or connector the workflow calls. Preflight checks they exist."""
    return {step.config.name for step in doc.all_steps() if isinstance(step.config, FnConfig)}
