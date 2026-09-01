"""Preflight: everything that can be checked without running anything.

Runs by default on every `run`; `--no-validate` opts out (decision 3). **No network and
no writes** -- that constraint is what makes it safe to run automatically, and what
makes a green preflight mean something.

The point is to move failures earlier. A missing pandas discovered forty seconds into a
paginated fetch has already spent the time and the rate limit; discovered here it costs
nothing and says exactly which `pip install` fixes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sclpl.errors import ValidationError, did_you_mean
from sclpl.run import paginate
from sclpl.run.compile_plan import compile_plan, function_names, hosts
from sclpl.run.ir import WorkflowDoc
from sclpl.run.modes import Resolved, resolve
from sclpl.run.plan import Plan
from sclpl.run.ports import Bindings, bind, check_readable, check_writable


@dataclass(slots=True)
class Report:
    """What preflight found. A clean report has no problems and may have notes."""

    workflow: str
    mode: str | None = None
    plan: Plan | None = None
    resolved: Resolved | None = None
    bindings: Bindings | None = None
    problems: list[ValidationError] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: Outputs that already exist. The caller decides whether to confirm.
    will_overwrite: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def raise_if_bad(self) -> None:
        if self.problems:
            raise self.problems[0]

    def summary(self) -> str:
        if not self.plan:
            return f"{self.workflow}: not runnable"
        total = len(self.plan)
        pruned = len(self.resolved.pruned) if self.resolved else 0
        parts = [f"{total} step{'' if total == 1 else 's'}"]
        if pruned:
            parts.append(f"{pruned} pruned")
        if self.bindings:
            bound = sum(1 for binding in self.bindings.all() if binding.bound)
            if bound:
                parts.append(f"{bound} file{'' if bound == 1 else 's'}")
        return ", ".join(parts)


def preflight(
    doc: WorkflowDoc,
    *,
    mode: str | None = None,
    named_in: dict[str, str] | None = None,
    named_out: dict[str, str] | None = None,
    positional: list[str] | None = None,
    from_cache: bool = False,
    check_files: bool = True,
    require_ports: bool = True,
) -> Report:
    """Check a workflow end to end without executing it.

    Stops at the first failure in each phase rather than pressing on: a workflow whose
    ports do not bind cannot have its graph meaningfully checked, and reporting the
    consequences alongside the cause makes the cause harder to find.
    """
    report = Report(workflow=doc.name, mode=mode)

    # 1. Ports. Everything else depends on knowing what is bound.
    #
    # `require_ports` separates two different questions. `validate <wf>` asks whether
    # the workflow is well-formed, which is true or false regardless of which files
    # today's invocation happens to bind; `run` asks whether *this* invocation can
    # proceed, which needs every required port bound.
    try:
        report.bindings = bind(
            doc,
            named_in=named_in,
            named_out=named_out,
            positional=positional,
            optional=_unwritten_ports(doc, mode),
        )
    except ValidationError as error:
        if require_ports:
            report.problems.append(error)
            return report
        report.notes.append(f"ports unbound: {error.diagnostic.message}")
        report.bindings = None

    # Unbound ports still count as available when we are not checking an invocation:
    # a declared port is a promise the runner will keep.
    available = (
        report.bindings.names()
        if report.bindings is not None
        else {port.name for port in (*doc.inputs, *doc.outputs)}
    )
    if from_cache:
        report.notes.append("cache may satisfy pruned producers")

    # 2. Mode resolution and the closure check.
    try:
        report.resolved = resolve(doc, mode, available=available)
    except ValidationError as error:
        report.problems.append(error)
        return report

    # 3. The graph: references resolve, no cycles.
    try:
        report.plan = compile_plan(doc, keep=report.resolved.keep, available=available)
    except ValidationError as error:
        report.problems.append(error)
        return report

    # 4. Expressions parse.
    report.problems.extend(_check_expressions(doc, report.resolved))

    # 5. Every step's own configuration is coherent: the function exists, the `-> port`
    #    names a declared output, and each paginator has what its strategy needs.
    report.problems.extend(_check_functions(doc, report.resolved))
    report.problems.extend(_check_writes(doc, report.resolved))
    report.problems.extend(_check_pagination(doc, report.resolved))

    # 6. Files: inputs readable, output directories present. Never writes.
    if check_files and report.bindings is not None:
        try:
            check_readable(report.bindings)
            report.will_overwrite = check_writable(report.bindings)
        except ValidationError as error:
            report.problems.append(error)

    # 7. Optional extras the workflow will need.
    report.notes.extend(_check_extras(doc, report.resolved))

    if hosts(doc):
        report.notes.append(f"hosts: {', '.join(hosts(doc))}")
    return report


def _unwritten_ports(doc: WorkflowDoc, mode: str | None) -> set[str]:
    """Output ports whose only writer this mode pruned.

    Ports are bound before the mode resolves -- everything downstream needs to know what
    is available -- so this resolves the mode once, cheaply, just to ask which writers
    survive. A port some kept step still writes stays required.

    Only ports a step *claims* with `-> port` are considered. A workflow whose steps
    write literal paths has told us nothing about who writes what, and guessing there
    would relax a requirement the author meant.
    """
    claimed = {step.writes for step in doc.all_steps() if step.writes}
    if not claimed:
        return set()
    try:
        kept = resolve(
            doc, mode, available={port.name for port in (*doc.inputs, *doc.outputs)}
        ).keep
    except ValidationError:
        # The mode is broken; that is reported properly a few lines later. Relaxing
        # nothing here means the error the reader sees is the mode's, not a port's.
        return set()
    still_written = {step.writes for step in doc.all_steps() if step.writes and step.id in kept}
    return {name for name in claimed if name not in still_written and name is not None}


def _check_expressions(doc: WorkflowDoc, resolved: Resolved) -> list[ValidationError]:
    """Every expression parses. A malformed one is a typo, found now rather than later."""
    from sclpl.expr import parse, parse_interpolated

    problems: list[ValidationError] = []
    for name, rule in doc.rules.items():
        try:
            parse(rule)
        except ValidationError as error:
            problems.append(
                ValidationError(
                    f"rule {name!r} does not parse: {error.diagnostic.message}",
                    where=error.diagnostic.where,
                    remedies=error.diagnostic.remedies,
                )
            )

    for step in doc.all_steps():
        if step.id not in resolved.keep:
            continue
        for label, clause in (
            ("assert", step.assert_),
            ("skip_if", step.skip_if),
            ("retry_if", step.retry_if),
        ):
            if not clause:
                continue
            if clause in doc.rules:
                continue  # a named rule, already checked above
            try:
                parse(clause)
            except ValidationError as error:
                problems.append(
                    ValidationError(
                        f"step {step.id!r}: {label} does not parse: {error.diagnostic.message}",
                        where=error.diagnostic.where,
                        remedies=error.diagnostic.remedies
                        + [f"if you meant a named rule, declare it: @rule {clause} = …"],
                    )
                )
        for text in _strings(step):
            if "{{" not in text:
                continue
            try:
                parse_interpolated(text)
            except ValidationError as error:
                problems.append(
                    ValidationError(
                        f"step {step.id!r}: {error.diagnostic.message}",
                        where=error.diagnostic.where,
                        remedies=error.diagnostic.remedies,
                    )
                )
    return problems


def _strings(step: object) -> list[str]:
    out: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
        elif hasattr(value, "model_dump"):
            visit(value.model_dump())

    visit(getattr(step, "config", None))
    return out


def _check_functions(doc: WorkflowDoc, resolved: Resolved) -> list[ValidationError]:
    """Every function a kept step calls is registered."""
    from sclpl.expr import dispatch

    problems: list[ValidationError] = []
    kept = {step.id for step in doc.all_steps() if step.id in resolved.keep}
    for step in doc.all_steps():
        if step.id not in kept:
            continue
        name = getattr(step.config, "name", None)
        if not isinstance(name, str) or step.kind != "fn":
            continue
        if dispatch.has(name):
            continue
        remedies = []
        suggestion = did_you_mean(name, dispatch.names())
        if suggestion:
            remedies.append(suggestion)
        remedies.append("run 'sclpl fn list' to see what is available")
        remedies.append("a plugin may provide it -- 'sclpl plugin list'")
        problems.append(
            ValidationError(
                f"step {step.id!r} calls {name!r}, which is not registered", remedies=remedies
            )
        )
    return problems


def _check_pagination(doc: WorkflowDoc, resolved: Resolved) -> list[ValidationError]:
    """Every `paginate` line has what its strategy needs to follow anything.

    An offset paginator with no page size cannot advance, and a cursor paginator with
    no path cannot find its token. Both fail identically at runtime -- one page, then
    nothing -- which reads as "the API only had one page" rather than as a mistake.
    """
    problems: list[ValidationError] = []
    for step in doc.all_steps():
        if step.id not in resolved.keep:
            continue
        spec = getattr(step.config, "paginate", None)
        if spec is None:
            continue
        try:
            paginate.check(spec)
        except ValidationError as error:
            problems.append(
                ValidationError(
                    f"step {step.id!r}: {error.diagnostic.message}",
                    remedies=error.diagnostic.remedies,
                )
            )
    return problems


def _check_writes(doc: WorkflowDoc, resolved: Resolved) -> list[ValidationError]:
    """Every `-> port` on a kept step names a declared output port."""
    declared = [port.name for port in doc.outputs]
    problems: list[ValidationError] = []
    for step in doc.all_steps():
        if step.id not in resolved.keep or not step.writes or step.writes in declared:
            continue
        remedies = []
        suggestion = did_you_mean(step.writes, declared)
        if suggestion:
            remedies.append(suggestion)
        remedies.append(
            f"declared outputs: {', '.join(declared)}"
            if declared
            else "this workflow declares no outputs"
        )
        problems.append(
            ValidationError(
                f"step {step.id!r} writes to {step.writes!r}, which is not an output port",
                remedies=remedies,
            )
        )
    return problems


def _check_extras(doc: WorkflowDoc, resolved: Resolved) -> list[str]:
    """Optional dependencies the run will need, reported now rather than mid-pipeline.

    Decision 3: missing extras are a preflight note with the exact `pip install`. A
    pipeline that dies at the write step, after every request has been paid for, is the
    thing this prevents.
    """
    notes: list[str] = []
    formats = {
        binding.format
        for binding in (*doc.inputs, *doc.outputs)
        if getattr(binding, "format", "auto") != "auto"
    }
    del resolved

    if "xlsx" in formats and not _installed("openpyxl"):
        notes.append("xlsx needs the data extra: pip install 'sclpl[data]'")
    if formats & {"parquet"} and not _installed("pyarrow"):
        notes.append("parquet needs pyarrow: pip install pyarrow")
    if _needs_pandas(doc) and not _installed("pandas"):
        notes.append("table operations need the data extra: pip install 'sclpl[data]'")
    return notes


def _needs_pandas(doc: WorkflowDoc) -> bool:
    table_functions = {"join", "merge", "pivot", "group_agg", "to_table", "read_excel"}
    return bool(function_names(doc) & table_functions)


def _installed(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None
