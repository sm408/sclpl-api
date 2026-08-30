"""Format dispatch: reading and writing by extension.

One place that knows what a file extension means, so `read_csv` and a bound input port
and the spill path all agree. The format is always resolvable from the path; passing it
explicitly is for when the extension is wrong or absent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sclpl.run.errors import ValidationError, did_you_mean
from sclpl.run.ports import BY_EXTENSION
from sclpl.tables.base import Table, as_table
from sclpl.tables.flatten import flatten_records, records_of

#: Formats that hold tabular data. `json` and `ndjson` can be either, and are decided
#: by what is actually in the file.
TABULAR = frozenset({"csv", "parquet", "xlsx"})

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
    """Write a value out, coercing it to the shape the format needs."""
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
