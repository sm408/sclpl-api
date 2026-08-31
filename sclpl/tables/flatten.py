"""Flattening nested JSON into columns.

SPEC section 10 makes this the reference behaviour, and it is worth being precise
about, because "flatten this API response into a CSV" is the single most common thing
this tool is asked to do and every ambiguity in it shows up as a wrong column.

The rules:

- Nested objects join with `_`: `{"user": {"id": 1}}` -> `user_id`.
- Column order is **depth-first over first-seen keys**, so two runs over the same data
  produce the same file and a diff is meaningful.
- Arrays are JSON-encoded, unless named in `explode`, which produces one row per
  element.
- A collision suffixes `_2`, `_3`. Silently overwriting the first would lose data with
  no indication.
- `columns="union"` across heterogeneous records: every key any record has becomes a
  column, missing values are null. `columns="intersection"` keeps only shared keys.
"""

from __future__ import annotations

import json
from typing import Any, Literal

SEPARATOR = "_"

#: Beyond this depth a "flattened" name is unreadable and almost certainly not wanted.
MAX_DEPTH = 12

ColumnPolicy = Literal["union", "intersection", "first"]

#: Keys an API commonly wraps its list in. Reaching one level through one of these is
#: what makes `save_csv @response.body` produce rows rather than a single wide record.
ENVELOPES = ("data", "items", "results", "records", "rows")


def records_of(value: Any) -> list[dict[str, Any]]:
    """The records inside whatever a step produced.

    One definition, used by the writers, the function catalogue, and every plugin alike,
    so `save_csv(@x)` and `flatten(@x)` and `sqlite.write(@x)` can never disagree about
    what the rows are.

    A `Table` is recognised by offering `to_records()`, not by its type. `tables/base.py`
    imports this module, so importing it back would be a cycle -- and duck-typing is the
    honest rule anyway: a plugin's own backend is a table if it behaves like one.
    """
    to_records = getattr(value, "to_records", None)
    if callable(to_records):
        rows = to_records()
        return rows if isinstance(rows, list) else []
    if isinstance(value, list):
        return [row if isinstance(row, dict) else {"value": row} for row in value]
    if isinstance(value, dict):
        for key in ENVELOPES:
            nested = value.get(key)
            if isinstance(nested, list):
                return records_of(nested)
        return [value]
    if value is None:
        return []
    return [{"value": value}]


def flatten_record(
    record: dict[str, Any],
    *,
    sep: str = SEPARATOR,
    prefix: str = "",
    max_depth: int = MAX_DEPTH,
    encode_arrays: bool = True,
) -> dict[str, Any]:
    """One nested object, flattened to one flat object."""
    out: dict[str, Any] = {}
    _walk(record, prefix, out, sep, max_depth, encode_arrays, 0)
    return out


def _walk(
    value: Any,
    prefix: str,
    out: dict[str, Any],
    sep: str,
    max_depth: int,
    encode_arrays: bool,
    depth: int,
) -> None:
    if isinstance(value, dict) and depth < max_depth:
        if not value:
            _place(out, prefix, {})
            return
        for key, item in value.items():
            name = f"{prefix}{sep}{key}" if prefix else str(key)
            _walk(item, name, out, sep, max_depth, encode_arrays, depth + 1)
        return

    if isinstance(value, list) and encode_arrays:
        # A list of scalars is more useful joined than JSON-encoded: `tags` reading
        # `a,b,c` in a spreadsheet beats `["a","b","c"]`.
        if value and all(not isinstance(item, (dict, list)) for item in value):
            _place(out, prefix, ",".join("" if item is None else str(item) for item in value))
        else:
            _place(out, prefix, json.dumps(value, default=str) if value else None)
        return

    _place(out, prefix, value)


def _place(out: dict[str, Any], name: str, value: Any) -> None:
    """Write a column, suffixing on collision rather than overwriting."""
    if name not in out:
        out[name] = value
        return
    index = 2
    while f"{name}_{index}" in out:
        index += 1
    out[f"{name}_{index}"] = value


def flatten_records(
    records: list[dict[str, Any]],
    *,
    sep: str = SEPARATOR,
    explode: list[str] | str | None = None,
    columns: ColumnPolicy = "union",
    max_depth: int = MAX_DEPTH,
) -> list[dict[str, Any]]:
    """Flatten a list of nested objects into a list of flat ones."""
    if not records:
        return []

    exploded = _explode(records, explode) if explode else records
    flattened = [
        flatten_record(record, sep=sep, max_depth=max_depth)
        if isinstance(record, dict)
        else {"value": record}
        for record in exploded
    ]
    return _align(flattened, columns)


def _explode(records: list[dict[str, Any]], explode: list[str] | str) -> list[dict[str, Any]]:
    """One row per element of the named array field, repeating the other columns."""
    fields = [explode] if isinstance(explode, str) else list(explode)
    current = records
    for field in fields:
        # Objects in the array become `field_key` columns; scalars stay under `field`.
        # Which of the two happened decides what an empty array leaves behind, so it is
        # settled before the rows are built -- otherwise a record with no elements adds
        # an all-null `field` column beside the `field_key` ones, in every output.
        elements = [
            item
            for record in current
            if isinstance(record, dict) and isinstance(record.get(field), list)
            for item in record[field]
        ]
        prefixed = any(isinstance(item, dict) for item in elements)
        bare = any(not isinstance(item, dict) for item in elements)

        expanded: list[dict[str, Any]] = []
        for record in current:
            value = record.get(field) if isinstance(record, dict) else None
            if isinstance(value, list) and value:
                for item in value:
                    row = {key: item_value for key, item_value in record.items() if key != field}
                    if isinstance(item, dict):
                        row.update({f"{field}{SEPARATOR}{k}": v for k, v in item.items()})
                    else:
                        row[field] = item
                    expanded.append(row)
            else:
                # An empty or missing array keeps the row, with the field cleared. The
                # alternative -- dropping it -- loses records with no explanation.
                row = dict(record)
                if prefixed and not bare:
                    row.pop(field, None)
                else:
                    row[field] = None
                expanded.append(row)
        current = expanded
    return current


def _align(records: list[dict[str, Any]], policy: ColumnPolicy) -> list[dict[str, Any]]:
    """Give every record the same columns, in a deterministic order."""
    if not records:
        return []

    ordered: list[str] = []
    for record in records:
        for key in record:
            if key not in ordered:
                ordered.append(key)

    match policy:
        case "first":
            wanted = [key for key in ordered if key in records[0]]
        case "intersection":
            shared = set(records[0])
            for record in records[1:]:
                shared &= set(record)
            wanted = [key for key in ordered if key in shared]
        case _:
            wanted = ordered

    return [{key: record.get(key) for key in wanted} for record in records]


def unflatten_record(record: dict[str, Any], *, sep: str = SEPARATOR) -> dict[str, Any]:
    """The inverse, for writing a flat table back to nested JSON.

    Best-effort: a column named `user_id` could have come from `{"user": {"id": …}}` or
    from a field literally called `user_id`, and nothing in the flat form distinguishes
    them. Nesting is the more useful guess for round-tripping an API payload.
    """
    out: dict[str, Any] = {}
    for key, value in record.items():
        parts = key.split(sep)
        cursor = out
        for part in parts[:-1]:
            existing = cursor.get(part)
            if not isinstance(existing, dict):
                existing = {}
                cursor[part] = existing
            cursor = existing
        cursor[parts[-1]] = value
    return out


def infer_schema(records: list[dict[str, Any]]) -> dict[str, str]:
    """The column types a list of flat records implies.

    Used by `assert_schema` and by `data schema`. A column that is null everywhere is
    reported as `null` rather than guessed at.
    """
    schema: dict[str, str] = {}
    for record in records:
        for key, value in record.items():
            observed = _type_name(value)
            current = schema.get(key)
            if current is None or current == "null":
                schema[key] = observed
            elif observed != "null" and observed != current:
                schema[key] = _widen(current, observed)
    return schema


def _type_name(value: Any) -> str:
    match value:
        case None:
            return "null"
        case bool():
            return "boolean"
        case int():
            return "integer"
        case float():
            return "number"
        case str():
            return "string"
        case list():
            return "list"
        case dict():
            return "object"
        case _:
            return type(value).__name__


def _widen(left: str, right: str) -> str:
    """The type that admits both. Mixed types end at `string`, which always does."""
    if {left, right} == {"integer", "number"}:
        return "number"
    return "string"
