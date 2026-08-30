"""SCLPLL v2 emitter: IR out to canonical source.

Canonical means: stable ordering, two-space indent, one blank line between steps, no
optional value written when it equals the default. `parse(emit(doc)) == doc` is a
property test, and `fmt` twice must be a no-op.

Writing only non-defaults is what makes the round-trip byte-identical. Emitting
`retry 0` for a step that never asked for retries would survive a parse but would not
survive a second `fmt`, and the file would churn on every save.
"""

from __future__ import annotations

from typing import Any

from sclpl.run.ir import (
    FnConfig,
    ForeachConfig,
    GateConfig,
    HttpConfig,
    IfConfig,
    LetConfig,
    ParallelConfig,
    Step,
    UseConfig,
    WhileConfig,
    WorkflowDoc,
)

INDENT = "  "


def emit(doc: WorkflowDoc) -> str:
    """Render a workflow as canonical SCLPLL v2."""
    lines: list[str] = []

    header = f"@workflow {doc.name}"
    if doc.description:
        header += f" {_quote(doc.description)}"
    lines.append(header)

    if doc.version != 1:
        lines.append(f"@version {doc.version}")

    if doc.vars:
        lines.append("")
        lines.extend(f"@var {name} = {_value(value)}" for name, value in doc.vars.items())

    if doc.rules:
        lines.append("")
        lines.extend(f"@rule {name} = {expression}" for name, expression in doc.rules.items())

    if doc.inputs or doc.outputs:
        lines.append("")
        lines.extend(_port("input", port) for port in doc.inputs)
        lines.extend(_port("output", port) for port in doc.outputs)

    limits = doc.limits.model_dump(exclude_defaults=True)
    if limits:
        lines.append("")
        rendered = " ".join(f"{key}={_value(value)}" for key, value in limits.items())
        lines.append(f"@limits {rendered}")

    for name, mode in doc.modes.items():
        lines.append("")
        lines.extend(_mode(name, mode))

    if doc.default_mode:
        lines.append("")
        lines.append(f"@default_mode {doc.default_mode}")

    for step in doc.steps:
        lines.append("")
        lines.extend(_step(step, depth=0))

    return "\n".join(lines).rstrip("\n") + "\n"


def _port(kind: str, port: Any) -> str:
    spec = port.name
    if port.format != "auto":
        spec += f":{port.format}"
    if not port.required:
        spec += "?"
    line = f"@{kind} {spec}"
    if port.default:
        line += f" default={_quote(port.default)}"
    if port.description:
        line += f" description={_quote(port.description)}"
    return line


def _mode(name: str, mode: Any) -> list[str]:
    lines = [f"@mode {name}" + (" all" if mode.all else "")]
    if mode.description:
        lines.append(f"{INDENT}describe {_quote(mode.description)}")
    if mode.extends:
        lines.append(f"{INDENT}extends {mode.extends}")
    if mode.include:
        lines.append(f"{INDENT}include {' '.join(mode.include)}")
    if mode.exclude:
        lines.append(f"{INDENT}exclude {' '.join(mode.exclude)}")
    for label, mapping in (("var", mode.vars), ("limit", mode.limit), ("stub", mode.stub)):
        if mapping:
            rendered = " ".join(f"{key}={_value(value)}" for key, value in mapping.items())
            lines.append(f"{INDENT}{label} {rendered}")
    return lines


def _step(step: Step, depth: int) -> list[str]:
    pad = INDENT * depth
    header = f"{pad}@step {step.id}" if depth == 0 else f"{pad}step {step.id}"
    if step.needs:
        header += " <- " + " ".join(step.needs)
    if step.writes:
        header += f" -> {step.writes}"
    lines = [header]
    body = INDENT * (depth + 1)

    match step.config:
        case HttpConfig() as config:
            lines.append(f"{body}{config.method.lower()} {config.url}")
            lines.extend(f"{body}header {name}: {value}" for name, value in config.headers.items())
            if config.query:
                rendered = " ".join(f"{k}={_value(v)}" for k, v in config.query.items())
                lines.append(f"{body}query {rendered}")
            if config.body is not None:
                lines.append(f"{body}body {_value(config.body)}")
            if config.auth:
                lines.append(f"{body}auth {config.auth}")
            if config.timeout is not None:
                lines.append(f"{body}timeout {_number(config.timeout)}")
            if config.extract:
                lines.append(f"{body}extract {config.extract}")
            if config.paginate is not None:
                spec = config.paginate.model_dump(exclude_defaults=True)
                strategy = spec.pop("strategy", config.paginate.strategy)
                rendered = " ".join(f"{k}={_value(v)}" for k, v in spec.items())
                lines.append(f"{body}paginate {strategy} {rendered}".rstrip())
        case FnConfig() as config:
            args = [_value(arg) for arg in config.args]
            args.extend(f"{key}={_value(value)}" for key, value in config.kwargs.items())
            lines.append(f"{body}{config.name} {' '.join(args)}".rstrip())
        case LetConfig() as config:
            source = config.expr if config.expr is not None else _value(config.value)
            lines.append(f"{body}let {source}")
        case ForeachConfig() as config:
            lines.append(f"{body}foreach {config.var} in {config.over}")
            if config.concurrency is not None:
                lines.append(f"{body}concurrency={config.concurrency}")
            for child in config.body:
                lines.extend(_step(child, depth + 2))
        case IfConfig() as config:
            lines.append(f"{body}when {config.condition}")
            for child in config.then:
                lines.extend(_step(child, depth + 2))
            if config.otherwise:
                lines.append(f"{body}otherwise")
                for child in config.otherwise:
                    lines.extend(_step(child, depth + 2))
        case WhileConfig() as config:
            lines.append(f"{body}while {config.condition}")
            for child in config.body:
                lines.extend(_step(child, depth + 2))
        case ParallelConfig() as config:
            lines.append(f"{body}parallel")
            for branch in config.branches:
                for child in branch:
                    lines.extend(_step(child, depth + 2))
        case UseConfig() as config:
            suffix = f" mode={config.mode}" if config.mode else ""
            lines.append(f"{body}use {config.workflow}{suffix}")
        case GateConfig() as config:
            lines.append(f"{body}gate {_quote(config.reason)}" if config.reason else f"{body}gate")

    lines.extend(_clauses(step, body))
    return lines


def _clauses(step: Step, body: str) -> list[str]:
    """The clauses common to every kind, in a fixed order so `fmt` is stable."""
    lines: list[str] = []
    if step.tags:
        lines.append(f"{body}tag {' '.join(step.tags)}")
    if step.lane:
        lines.append(f"{body}lane {step.lane}")
    if step.skip_if:
        lines.append(f"{body}skip_if {step.skip_if}")
    if step.retry_if:
        lines.append(f"{body}retry_if {step.retry_if}")
    retry = step.retry.model_dump(exclude_defaults=True)
    if retry:
        maximum = retry.pop("max", None)
        parts = [str(maximum)] if maximum is not None else []
        parts.extend(f"{key}={_value(value)}" for key, value in retry.items())
        lines.append(f"{body}retry {' '.join(parts)}")
    cache = step.cache.model_dump(exclude_defaults=True)
    if cache:
        if cache.get("enabled") is False:
            lines.append(f"{body}cache off")
        else:
            cache.pop("enabled", None)
            rendered = " ".join(f"{key}={_value(value)}" for key, value in cache.items())
            lines.append(f"{body}cache {rendered}")
    if step.assert_:
        lines.append(f"{body}assert {step.assert_}")
    if step.keep:
        lines.append(f"{body}keep")
    return lines


def _value(value: Any) -> str:
    """Render a value the way `_literal` in the parser will read it back."""
    match value:
        case None:
            return "null"
        case bool():
            return "true" if value else "false"
        case int():
            return str(value)
        case float():
            return _number(value)
        case str():
            return _quote(value) if _needs_quoting(value) else value
        case list() | dict():
            import json

            return json.dumps(value, separators=(",", ":"))
        case _:
            return str(value)


def _number(value: float) -> str:
    """Trim a float that is really an integer, so 30.0 emits as 30."""
    if value == int(value):
        return str(int(value))
    return repr(value)


def _needs_quoting(text: str) -> bool:
    """Quote when the bare form would parse back as something else."""
    if not text:
        return True
    if any(char.isspace() for char in text):
        return True
    if text.lower() in ("true", "false", "null", "none"):
        return True
    try:
        float(text)
    except ValueError:
        return False
    return True


def _quote(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
