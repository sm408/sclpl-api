"""Port binding: declared files, and the paths bound to them.

Precedence, highest first (SPEC section 8):

1. `--in name=path` / `--out name=path`
2. Positional arguments, in declaration order -- inputs first, then outputs
3. The port's declared default

`-` means stdin or stdout. A glob binds a sorted list of paths. `path:format` overrides
the format the extension implies. A count mismatch is a preflight error that lists the
ports, because "expected 3 arguments, got 2" without saying which three is a puzzle.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sclpl.run.errors import ValidationError, did_you_mean
from sclpl.run.ir import Format, Port, WorkflowDoc

STDIO = "-"

#: Extension -> format. What a bare path means when no `:format` is given.
BY_EXTENSION: dict[str, Format] = {
    ".csv": "csv",
    ".tsv": "csv",
    ".json": "json",
    ".ndjson": "ndjson",
    ".jsonl": "ndjson",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".db": "sqlite",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
}


@dataclass(slots=True)
class Binding:
    """One port, bound to somewhere concrete."""

    name: str
    direction: str
    #: Empty when an optional port went unbound.
    paths: list[Path] = field(default_factory=list)
    format: Format = "auto"
    is_stdio: bool = False
    required: bool = True

    @property
    def path(self) -> Path | None:
        return self.paths[0] if self.paths else None

    @property
    def bound(self) -> bool:
        return bool(self.paths) or self.is_stdio

    def describe(self) -> str:
        if self.is_stdio:
            return "stdin" if self.direction == "in" else "stdout"
        if not self.paths:
            return "(unbound)"
        if len(self.paths) == 1:
            return str(self.paths[0])
        return f"{len(self.paths)} files"


@dataclass(slots=True)
class Bindings:
    inputs: dict[str, Binding] = field(default_factory=dict)
    outputs: dict[str, Binding] = field(default_factory=dict)

    def names(self) -> set[str]:
        """Every bound port name -- what the closure check counts as available."""
        return {name for name, binding in {**self.inputs, **self.outputs}.items() if binding.bound}

    def all(self) -> list[Binding]:
        return [*self.inputs.values(), *self.outputs.values()]


def bind(
    doc: WorkflowDoc,
    *,
    named_in: dict[str, str] | None = None,
    named_out: dict[str, str] | None = None,
    positional: list[str] | None = None,
) -> Bindings:
    """Bind every declared port, or raise saying which one could not be."""
    named_in = dict(named_in or {})
    named_out = dict(named_out or {})
    positional = list(positional or [])

    _check_names(doc, named_in, "in")
    _check_names(doc, named_out, "out")

    # Positional arguments fill the unnamed ports in declaration order -- but an
    # optional port only takes one when enough remain to cover the required ports
    # after it. Given `<customers> <extra?> <report>`:
    #
    #   orders in.csv out.csv              -> customers, report   (extra skipped)
    #   orders in.csv extra.json out.csv   -> all three, in order
    #
    # Filling strictly in order would hand `out.csv` to `extra` and then complain that
    # `report` is missing; filling required-first would scramble the three-argument
    # case. Looking ahead gets both right.
    queue = list(positional)
    ordered = [(port, "in") for port in doc.inputs] + [(port, "out") for port in doc.outputs]
    assigned: dict[str, str] = {}

    for index, (port, direction) in enumerate(ordered):
        named = named_in if direction == "in" else named_out
        if port.name in named:
            assigned[port.name] = named[port.name]
            continue
        if not queue:
            continue
        if not port.required:
            still_required = sum(
                1
                for later, later_direction in ordered[index + 1 :]
                if later.required
                and later.name not in (named_in if later_direction == "in" else named_out)
            )
            if len(queue) <= still_required:
                continue
        assigned[port.name] = queue.pop(0)

    inputs = {port.name: _make(port, assigned.get(port.name), "in") for port in doc.inputs}
    outputs = {port.name: _make(port, assigned.get(port.name), "out") for port in doc.outputs}

    if queue:
        raise ValidationError(
            f"{len(queue)} extra argument(s): {', '.join(queue)}",
            remedies=[_port_summary(doc)],
        )

    missing = [
        binding.name
        for binding in (*inputs.values(), *outputs.values())
        if binding.required and not binding.bound
    ]
    if missing:
        raise ValidationError(
            f"no file given for: {', '.join(missing)}",
            remedies=[
                _port_summary(doc),
                "bind by name with --in name=path / --out name=path",
            ],
        )
    return Bindings(inputs=inputs, outputs=outputs)


def _make(port: Port, spec: str | None, direction: str) -> Binding:
    if spec is None:
        spec = port.default
    if spec is None:
        return Binding(name=port.name, direction=direction, required=port.required)

    path_text, fmt = _split_format(spec)
    if path_text == STDIO:
        return Binding(
            name=port.name,
            direction=direction,
            format=fmt or (port.format if port.format != "auto" else "json"),
            is_stdio=True,
            required=port.required,
        )

    paths = _expand(path_text, direction)
    resolved = fmt or (
        port.format if port.format != "auto" else _infer(paths[0] if paths else None)
    )
    return Binding(
        name=port.name,
        direction=direction,
        paths=paths,
        format=resolved,
        required=port.required,
    )


def _split_format(spec: str) -> tuple[str, Format | None]:
    """`data.txt:csv` -> ('data.txt', 'csv'). A Windows drive letter is not a format."""
    head, separator, tail = spec.rpartition(":")
    if not separator or not head:
        return spec, None
    if tail in BY_EXTENSION.values():
        return head, tail  # type: ignore[return-value]
    return spec, None


def _expand(text: str, direction: str) -> list[Path]:
    """Resolve a path or a glob.

    Globs are only expanded for inputs: a glob as an output is almost certainly a
    quoting mistake, and creating a file literally named `*.csv` is not a kindness.
    """
    if any(char in text for char in "*?[") and direction == "in":
        base = Path(text)
        root = base.parent if base.parent != Path("") else Path()
        matches = (
            sorted(root.glob(base.name)) if base.parent != Path("") else sorted(Path().glob(text))
        )
        if not matches:
            raise ValidationError(
                f"the pattern {text!r} matched no files",
                remedies=["check the directory, or quote the pattern if the shell expanded it"],
            )
        return matches
    return [Path(text)]


def _infer(path: Path | None) -> Format:
    if path is None:
        return "auto"
    return BY_EXTENSION.get(path.suffix.lower(), "auto")


def _check_names(doc: WorkflowDoc, named: dict[str, str], direction: str) -> None:
    declared = [port.name for port in (doc.inputs if direction == "in" else doc.outputs)]
    for name in named:
        if name in declared:
            continue
        remedies = []
        suggestion = did_you_mean(name, declared)
        if suggestion:
            remedies.append(suggestion)
        remedies.append(
            f"declared {direction}puts: {', '.join(declared)}" if declared else _port_summary(doc)
        )
        raise ValidationError(f"{doc.name} has no {direction}put port {name!r}", remedies=remedies)


def _port_summary(doc: WorkflowDoc) -> str:
    """The usage line for this workflow: what it takes, in order."""
    inputs = " ".join(f"<{port.name}>" for port in doc.inputs)
    outputs = " ".join(f"<{port.name}>" for port in doc.outputs)
    parts = [part for part in (inputs, outputs) if part]
    if not parts:
        return f"{doc.name} declares no ports"
    return f"usage: sclpl {doc.name} [mode] {' '.join(parts)}"


def check_readable(bindings: Bindings) -> None:
    """Preflight: every bound input exists and can be opened. No writes, no network."""
    for binding in bindings.inputs.values():
        if binding.is_stdio or not binding.bound:
            continue
        for path in binding.paths:
            if not path.exists():
                raise ValidationError(
                    f"input {binding.name!r}: {path} does not exist",
                    remedies=["check the path, or bind a different file"],
                )
            if path.is_dir():
                raise ValidationError(
                    f"input {binding.name!r}: {path} is a directory",
                    remedies=["give a file, or a glob like 'data/*.csv'"],
                )
            try:
                with path.open("rb"):
                    pass
            except OSError as error:
                raise ValidationError(
                    f"input {binding.name!r}: cannot read {path}: {error.strerror}"
                ) from error


def check_writable(bindings: Bindings, *, overwrite: bool = False) -> list[Path]:
    """Preflight: every output's directory exists and is writable.

    Returns the paths that already exist, so the caller can confirm before clobbering
    something. Deciding that here would put a prompt inside a library.
    """
    existing: list[Path] = []
    for binding in bindings.outputs.values():
        if binding.is_stdio or not binding.bound:
            continue
        for path in binding.paths:
            parent = path.parent if str(path.parent) else Path()
            if not parent.exists():
                raise ValidationError(
                    f"output {binding.name!r}: the directory {parent} does not exist",
                    remedies=[f"create it first: mkdir -p {parent}"],
                )
            if path.exists():
                if path.is_dir():
                    raise ValidationError(f"output {binding.name!r}: {path} is a directory")
                existing.append(path)
    del overwrite
    return existing


def open_input(binding: Binding) -> Any:
    if binding.is_stdio:
        return sys.stdin.buffer
    if binding.path is None:
        raise ValidationError(f"input {binding.name!r} is not bound")
    return binding.path.open("rb")


def open_output(binding: Binding) -> Any:
    if binding.is_stdio:
        return sys.stdout.buffer
    if binding.path is None:
        raise ValidationError(f"output {binding.name!r} is not bound")
    return binding.path.open("wb")
