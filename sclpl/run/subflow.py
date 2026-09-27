"""`use`: another workflow as a step, injected into the same graph.

A used workflow is not run by a second scheduler. Its kept steps become nodes of the
parent's graph under a decorated prefix -- `filtered::use::fetch` -- exactly the way a
`foreach` body does (see `control.py`), so the parent's concurrency, host, and tag
ceilings govern the child's requests too, and history records the child's steps as part
of the parent's run.

**Scope.** The child sees only what it was given: its own steps, its `@var`s (with any
argument overriding the default), and its `@input`s, bound to the argument values. It
does not see the parent's values, and the parent does not see the child's intermediate
steps. That is why its expressions are evaluated against an empty store of their own
and a frame with no parent: a child step called `fetch` must not resolve to the
parent's `fetch`.

**Result.** A child that declares outputs produces `{port: value}` -- the value its
`-> port` step would have written. A used workflow never writes its own outputs; the
caller decides what to do with them. A child that declares none produces the value of
its last step.

**Validation.** Resolved and checked at preflight, recursively: the child exists, every
argument names an input or `@var`, every required input is given, the child's mode
resolves (its closure check included), and no chain of `use` leads back to a workflow
already on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sclpl.errors import SclplError, ValidationError, did_you_mean
from sclpl.run.control import MARK, Expansion, Injected
from sclpl.run.ir import Step, UseConfig, WorkflowDoc
from sclpl.run.schedule import ExpandSpec
from sclpl.values.store import Frame, ValueStore

if TYPE_CHECKING:  # pragma: no cover - preflight imports this module
    from sclpl.run.modes import Resolved
    from sclpl.run.preflight import Report

#: The segment between a `use` step's id and its child's step ids. A child step named
#: `join` would otherwise decorate to `filtered::join`, the scheduler's own barrier.
KEY = "use"


@dataclass(slots=True)
class Child:
    """A used workflow, located and checked, ready to expand."""

    doc: WorkflowDoc
    path: Path
    report: Report


def check(
    doc: WorkflowDoc,
    resolved: Resolved,
    origin: Path | None,
    stack: tuple[tuple[Path, str], ...],
) -> tuple[dict[str, Child], list[ValidationError]]:
    """Locate and validate every kept `use` step's workflow, by step id."""
    children: dict[str, Child] = {}
    problems: list[ValidationError] = []
    for step in doc.all_steps():
        if step.id not in resolved.keep or not isinstance(step.config, UseConfig):
            continue
        try:
            children[step.id] = _load(step, step.config, origin, stack)
        except ValidationError as error:
            problems.append(error)
    return children, problems


def _load(
    step: Step, config: UseConfig, origin: Path | None, stack: tuple[tuple[Path, str], ...]
) -> Child:
    from sclpl.run.preflight import preflight

    doc, path = _locate(step, config.workflow, origin)
    key = path.resolve()
    if any(seen == key for seen, _ in stack):
        chain = " -> ".join([*(name for _, name in stack), doc.name])
        raise ValidationError(
            f"step {step.id!r} uses {config.workflow!r}, which leads back to itself: {chain}",
            remedies=["a workflow cannot use itself, directly or through another one"],
        )
    _check_arguments(step, config, doc)
    report = preflight(
        doc,
        mode=config.mode,
        check_files=False,
        require_ports=False,
        origin=path,
        stack=(*stack, (key, doc.name)),
    )
    if report.problems:
        first = report.problems[0]
        message = first.diagnostic.message
        if not message.startswith("step "):
            message = f"{doc.name}: {message}"
        raise ValidationError(
            f"step {step.id!r} uses {config.workflow!r}: {message}",
            where=first.diagnostic.where,
            remedies=first.diagnostic.remedies,
        )
    return Child(doc=doc, path=path, report=report)


def _locate(step: Step, target: str, origin: Path | None) -> tuple[WorkflowDoc, Path]:
    """The same rules as `sclpl run`, plus the using workflow's own directory first."""
    from sclpl.catalog import resolve as catalog

    extra: list[Path] = []
    try:
        if origin is not None:
            base = origin.parent
            near = base / target
            if not Path(target).is_absolute() and near.is_file():
                return catalog.load(near), near
            extra = [base, base / "workflows"]
        located = catalog.resolve(target, extra_dirs=extra)
    except ValidationError as error:
        raise ValidationError(
            f"step {step.id!r} uses {target!r}, which does not parse: {error.diagnostic.message}",
            where=error.diagnostic.where,
            remedies=error.diagnostic.remedies,
        ) from error
    except SclplError as error:
        raise ValidationError(
            f"step {step.id!r} uses {target!r}: {error.diagnostic.message}",
            remedies=error.diagnostic.remedies,
        ) from error
    return located.doc, located.path


def _check_arguments(step: Step, config: UseConfig, child: WorkflowDoc) -> None:
    accepted = [*child.vars, *(port.name for port in child.inputs)]
    for name in config.inputs:
        if name in accepted:
            continue
        remedies = []
        suggestion = did_you_mean(name, accepted)
        if suggestion:
            remedies.append(suggestion)
        remedies.append(
            f"{child.name} accepts: {', '.join(accepted)}"
            if accepted
            else f"{child.name} declares no inputs or @vars"
        )
        raise ValidationError(
            f"step {step.id!r} passes {name!r} to {child.name}, "
            "which declares no such input or @var",
            remedies=remedies,
        )
    for port in child.inputs:
        if port.required and port.default is None and port.name not in config.inputs:
            raise ValidationError(
                f"step {step.id!r} uses {child.name} without its required input {port.name!r}",
                remedies=[f"pass it: use {config.workflow} {port.name}=@…"],
            )


def expand(step: Step, node_id: str, child: Child, args: dict[str, Any]) -> Expansion:
    """The child's kept steps as nodes beneath ``node_id``, wired by its own plan."""
    doc, report = child.doc, child.report
    assert report.plan is not None and report.resolved is not None
    resolved = report.resolved

    given_vars = {name: value for name, value in args.items() if name in doc.vars}
    inputs = {port.name: None for port in doc.inputs}
    inputs.update({name: value for name, value in args.items() if name not in doc.vars})
    frame = Frame(values={**resolved.stubs, **inputs})
    scope: dict[str, Any] = {
        "doc": doc,
        "vars": {**doc.vars, **resolved.vars, **given_vars},
        "store": ValueStore(),
        "children": report.children,
        "outputs": {},
    }

    plan = report.plan
    prefix = f"{node_id}{MARK}{KEY}{MARK}"
    ids = {name: f"{prefix}{name}" for name in plan.order}
    expansion = Expansion(produces="outputs" if doc.outputs else "one")
    for name in plan.order:
        node = plan.nodes[name]
        body = doc.step(name)
        assert body is not None
        expansion.specs.append(
            ExpandSpec(
                id=ids[name],
                # Only the child's own nodes, decorated: that is both its edges and the
                # store names it holds open. A plain name would retain or release the
                # parent's value of the same name.
                reads=frozenset(ids[need] for need in node.needs if need in ids),
                tags=node.tags,
                host=node.host,
                lane=node.lane,
                weight=node.weight,
            )
        )
        expansion.injected[ids[name]] = Injected(
            step=body, frame=frame, parent=step.id, scope=scope
        )

    if not plan.order:
        expansion.has_value = True
        expansion.value = {port.name: None for port in doc.outputs} if doc.outputs else None
        return expansion

    if doc.outputs:
        writers = {doc.step(name).writes: name for name in plan.order}  # type: ignore[union-attr]
        for port in doc.outputs:
            writer = writers.get(port.name)
            # An output whose writer the child's mode pruned is null, not missing:
            # `@filtered.report` should resolve either way.
            expansion.results[port.name] = ids[writer] if writer else ""
            if writer:
                expansion.injected[ids[writer]].result_of = port.name
    else:
        last = ids[plan.order[-1]]
        expansion.results["result"] = last
        expansion.injected[last].result_of = "result"
    return expansion
