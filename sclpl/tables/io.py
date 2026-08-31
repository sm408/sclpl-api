"""Format dispatch: reading and writing by extension.

One place that knows what a file extension means, so `read_csv` and a bound input port
and the spill path all agree. The format is always resolvable from the path; passing it
explicitly is for when the extension is wrong or absent.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal, TypeAlias

from sclpl.errors import ValidationError, did_you_mean
from sclpl.tables.base import Table, as_table
from sclpl.tables.flatten import flatten_records, records_of

STDIO = "-"

#: The formats `sclpl` reads and writes. `auto` means "work it out from the path".
Format: TypeAlias = Literal["csv", "json", "ndjson", "parquet", "xlsx", "sqlite", "auto"]

#: What a bare path means when no `:format` is given. Lives here rather than in
#: `run/ports.py` because it is a fact about formats; binding a port is one of its
#: consumers, not its owner.
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

#: Formats that hold tabular data. `json` and `ndjson` can be either, and are decided
#: by what is actually in the file.
TABULAR = frozenset({"csv", "parquet", "xlsx"})

#: Formats whose bytes are not readable in a terminal.
_BINARY = frozenset({"parquet", "xlsx", "sqlite"})

FORMATS = frozenset(BY_EXTENSION.values()) | {"json", "ndjson"}


def format_of(path: Path, explicit: str | None = None) -> str:
    """The format for a path: the explicit one, or what the extension implies."""
    if explicit and explicit != "auto":
        if explicit not in FORMATS:
            remedies = []
            suggestion = did_you_mean(explicit, sorted(FORMATS))
            if suggestion:
                remedies.append(suggestion)
            remedies.append(f"known formats: {', '.join(sorted(FORMATS))}")
            raise ValidationError(f"unknown format {explicit!r}", remedies=remedies)
        return explicit

    inferred = BY_EXTENSION.get(path.suffix.lower())
    if inferred is None:
        raise ValidationError(
            f"cannot tell what format {path.name} is",
            remedies=[
                "name it with a known extension, or say so: path.txt:csv",
                f"known formats: {', '.join(sorted(FORMATS))}",
            ],
        )
    return inferred


def read(path: Path, fmt: str | None = None, **options: Any) -> Any:
    """Read a file into the most useful Python value it can be.

    Tabular formats become a `Table`. JSON becomes whatever it holds -- a list of
    objects, an object, a scalar -- because a JSON file is not necessarily a table and
    forcing one on the caller loses the shape they wrote.
    """
    resolved = format_of(path, fmt)
    if not path.exists():
        raise ValidationError(
            f"{path} does not exist",
            remedies=["check the path, or the step that was meant to write it"],
        )

    match resolved:
        case "json":
            return json.loads(path.read_text(encoding="utf-8"))
        case "ndjson":
            return [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        case "sqlite":
            raise ValidationError(
                "reading SQLite is provided by the bundled sqlite plugin",
                remedies=["use the sqlite.query connector"],
            )
        case _:
            return Table.read(path, resolved, **options)


def write(value: Any, path: Path, fmt: str | None = None, **options: Any) -> Path:
    """Write a value out, coercing it to the shape the format needs.

    A path of `-` means stdout, which is the other half of invariant 1: progress goes to
    stderr precisely so that this can be piped.
    """
    if str(path) == STDIO:
        return _to_stdout(value, path, fmt, **options)

    resolved = format_of(path, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)

    match resolved:
        case "json":
            payload = value.to_records() if isinstance(value, Table) else value
            path.write_text(
                json.dumps(payload, indent=options.get("indent", 2), default=str),
                encoding="utf-8",
            )
        case "ndjson":
            rows = value.to_records() if isinstance(value, Table) else records_of(value)
            with path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, default=str) + "\n")
        case "sqlite":
            raise ValidationError(
                "writing SQLite is provided by the bundled sqlite plugin",
                remedies=["use the sqlite.write connector"],
            )
        case _:
            _tabular(value, **options).write(path, resolved, **_write_options(options))
    return path


def _to_stdout(value: Any, path: Path, fmt: str | None, **options: Any) -> Path:
    """Write to stdout, in the format the caller named.

    `-` carries no extension, so the format has to come from somewhere else: `save_csv`
    and a port declared `:csv` both supply it. Without one there is nothing to infer
    from, and guessing JSON would be a silent choice about someone's data.
    """
    if not fmt or fmt == "auto":
        raise ValidationError(
            "writing to stdout needs the format named -- '-' has no extension to read",
            remedies=[
                "use a format-specific writer: save_csv(@rows, '-')",
                "or declare it on the port: @output report:csv",
            ],
        )
    resolved = format_of(path, fmt)

    if resolved in _BINARY and sys.stdout.isatty():
        raise ValidationError(
            f"{resolved} is binary and stdout is a terminal",
            remedies=["redirect it: sclpl run … --out report=- > out." + resolved],
        )

    buffer = io.BytesIO()
    if resolved == "json":
        payload = value.to_records() if isinstance(value, Table) else value
        text = json.dumps(payload, indent=options.get("indent", 2), default=str) + "\n"
        buffer.write(text.encode("utf-8"))
    elif resolved == "ndjson":
        rows = value.to_records() if isinstance(value, Table) else records_of(value)
        for row in rows:
            buffer.write((json.dumps(row, default=str) + "\n").encode("utf-8"))
    else:
        with tempfile.TemporaryDirectory() as scratch:
            # The table backends write to a path, not a handle. A scratch file keeps
            # that contract rather than making every backend learn about streams.
            staged = Path(scratch) / f"out.{resolved}"
            _tabular(value, **options).write(staged, resolved, **_write_options(options))
            buffer.write(staged.read_bytes())

    sys.stdout.buffer.write(buffer.getvalue())
    sys.stdout.buffer.flush()
    return path


def _tabular(value: Any, **options: Any) -> Table:
    """Coerce a value into a table, flattening nested records on the way.

    This is what makes `save_csv @response.body` do the obvious thing with an API
    payload rather than producing one column of JSON.
    """
    if isinstance(value, Table):
        return value
    if not isinstance(value, (list, dict)):
        return as_table(value)
    return Table.from_records(
        flatten_records(
            records_of(value),
            sep=options.get("sep", "_"),
            explode=options.get("explode"),
            columns=options.get("columns", "union"),
        )
    )


def _write_options(options: dict[str, Any]) -> dict[str, Any]:
    """Only the options the backend's writer understands."""
    ours = {"sep", "explode", "columns", "indent"}
    return {key: value for key, value in options.items() if key not in ours}


def read_parquet_file(path: Path) -> Table:
    """The rehydrator registered with `values/ref.py` for spilled tables."""
    return Table.read(path, "parquet")
