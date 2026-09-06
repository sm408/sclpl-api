"""The pandas backend.

The only place in the engine that imports pandas, and it imports it lazily -- pandas is
the `[data]` extra, and a workflow that never touches a table should not pay a
second of import time for it, nor fail to start without it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sclpl.tables.base import MissingExtra

#: A value like `00123`: unsigned digits with a leading zero, one more than a bare
#: `0`. Read as CSV/NDJSON's default integer inference, this becomes `123` -- a
#: different, shorter value, silently. Nothing else in a CSV cell has this shape by
#: accident: an ordinary ID or count never starts with `0` followed by more digits.
_LEADING_ZERO = re.compile(r"^0\d+$")

#: The largest integer a IEEE-754 double -- what Excel stores every number as, having
#: no separate integer type -- can represent exactly. Above this, two different
#: integers can round to the same float, which is not a rounding *error* so much as
#: writing down the wrong number.
_EXCEL_SAFE_INTEGER = 2**53


def _pandas() -> Any:
    try:
        import pandas
    except ImportError as error:
        raise MissingExtra("tables", "pandas") from error
    return pandas


def _leading_zero_columns(path: Path) -> list[str]:
    """CSV columns holding a value like `00123`, sniffed from the raw text.

    Read before pandas ever sees the file: by the time `read_csv` has inferred a
    dtype, the leading zero is already gone, and there is nothing left to notice.
    """
    import csv

    found: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for column, value in row.items():
                if value and _LEADING_ZERO.match(value):
                    found.add(column)
    return sorted(found)


def _excel_unsafe_integers(frame: Any) -> list[tuple[str, int]]:
    """Columns holding an integer Excel's float64 storage cannot represent exactly.

    One offending value per column is enough to name in the diagnostic; the point is
    to say which column to avoid, not to enumerate every large id in it.
    """
    import math

    offenders: list[tuple[str, int]] = []
    for column in frame.columns:
        for value in frame[column]:
            if isinstance(value, int) and not isinstance(value, bool):
                if abs(value) > _EXCEL_SAFE_INTEGER:
                    offenders.append((str(column), value))
                    break
            elif (
                isinstance(value, float)
                and math.isfinite(value)
                and value.is_integer()
                and abs(value) > _EXCEL_SAFE_INTEGER
            ):
                offenders.append((str(column), int(value)))
                break
    return offenders


class PandasBackend:
    """Tabular operations, implemented over pandas."""

    name = "pandas"

    __slots__ = ()

    # -- construction ------------------------------------------------------------

    def from_records(self, records: list[dict[str, Any]]) -> Any:
        pandas = _pandas()
        if not records:
            return pandas.DataFrame()
        return pandas.DataFrame.from_records(records)

    def to_records(self, frame: Any) -> list[dict[str, Any]]:
        """Rows as plain dicts, with NaN back to None.

        pandas uses NaN for a missing value regardless of the column's type, and NaN
        surviving into JSON produces output no parser accepts. Converting here means no
        caller has to know that.
        """
        if frame.empty:
            return []
        cleaned = frame.astype(object).where(frame.notna(), None)
        records: list[dict[str, Any]] = cleaned.to_dict(orient="records")
        return records

    # -- inspection --------------------------------------------------------------

    def columns(self, frame: Any) -> list[str]:
        return [str(column) for column in frame.columns]

    def row_count(self, frame: Any) -> int:
        return int(len(frame.index))

    def dtypes(self, frame: Any) -> dict[str, str]:
        return {str(name): _friendly(str(dtype)) for name, dtype in frame.dtypes.items()}

    # -- operations --------------------------------------------------------------

    def select(self, frame: Any, columns: list[str]) -> Any:
        return frame[columns]

    def filter(self, frame: Any, mask: list[bool]) -> Any:
        return frame[list(mask)].reset_index(drop=True)

    def sort(self, frame: Any, by: list[str], descending: bool) -> Any:
        return frame.sort_values(by=by, ascending=not descending).reset_index(drop=True)

    def head(self, frame: Any, n: int) -> Any:
        return frame.head(n)

    def concat(self, frames: list[Any]) -> Any:
        pandas = _pandas()
        present = [frame for frame in frames if not frame.empty]
        if not present:
            return pandas.DataFrame()
        return pandas.concat(present, ignore_index=True, sort=False)

    def join(self, left: Any, right: Any, on: list[str], how: str) -> Any:
        missing_left = [key for key in on if key not in left.columns]
        missing_right = [key for key in on if key not in right.columns]
        if missing_left or missing_right:
            from sclpl.errors import ValidationError

            side = "left" if missing_left else "right"
            missing = missing_left or missing_right
            available = list(left.columns) if missing_left else list(right.columns)
            raise ValidationError(
                f"cannot join on {missing[0]!r}: the {side} table has no such column",
                remedies=[f"{side} columns: {', '.join(str(c) for c in available[:8])}"],
            )
        return left.merge(right, on=on, how=how)

    def dedupe(self, frame: Any, subset: list[str] | None) -> Any:
        return frame.drop_duplicates(subset=subset).reset_index(drop=True)

    def rename(self, frame: Any, mapping: dict[str, str]) -> Any:
        return frame.rename(columns=mapping)

    # -- io ----------------------------------------------------------------------

    def read(self, path: Path, fmt: str, **options: Any) -> Any:
        pandas = _pandas()
        match fmt:
            case "csv":
                return self._read_csv(path, **options)
            case "json":
                return self._read_json(path, **options)
            case "ndjson":
                return pandas.read_json(path, lines=True, **options)
            case "parquet":
                return pandas.read_parquet(path, **options)
            case "xlsx":
                try:
                    return pandas.read_excel(path, **options)
                except ImportError as error:
                    raise MissingExtra("reading Excel", "openpyxl") from error
            case _:
                from sclpl.errors import ValidationError

                raise ValidationError(f"cannot read {fmt!r} as a table")

    def _read_csv(self, path: Path, **options: Any) -> Any:
        """`pandas.read_csv`, with leading-zero columns protected from int inference.

        Left to its own defaults, `read_csv` would turn `00123` into `123`: a
        different, shorter value, and a different type, with nothing to say it
        happened. Every such column is forced to `str` before pandas ever infers a
        type for it, so the exact text survives.
        """
        pandas = _pandas()
        protect = _leading_zero_columns(path)
        if protect:
            overrides = dict(options.get("dtype") or {})
            for column in protect:
                overrides.setdefault(column, str)
            options = {**options, "dtype": overrides}
        try:
            return pandas.read_csv(path, **options)
        except pandas.errors.EmptyDataError as error:
            from sclpl.errors import ValidationError

            raise ValidationError(
                f"{path} has no header row to read as a table",
                remedies=[
                    "an empty table written as CSV has no columns to write a header "
                    "from, so this is expected for a zero-row export",
                    "read it as JSON or Parquet instead if the column names matter",
                ],
            ) from error

    def _read_json(self, path: Path, **options: Any) -> Any:
        """Read JSON that may be a list of objects, or an object wrapping one.

        `pandas.read_json` on an API response usually produces one row of nested
        columns, which is never what was wanted. Finding the list first and flattening
        it is what a person means by "read this JSON as a table".
        """
        import json

        from sclpl.tables.flatten import flatten_records

        payload = json.loads(path.read_text(encoding="utf-8"))
        records = _find_records(payload)
        return self.from_records(flatten_records(records, **options))

    def write(self, frame: Any, path: Path, fmt: str, **options: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        match fmt:
            case "csv":
                frame.to_csv(path, index=False, **options)
            case "json":
                import json

                path.write_text(
                    json.dumps(self.to_records(frame), indent=2, default=str),
                    encoding="utf-8",
                )
            case "ndjson":
                import json

                with path.open("w", encoding="utf-8") as handle:
                    for row in self.to_records(frame):
                        handle.write(json.dumps(row, default=str) + "\n")
            case "parquet":
                try:
                    frame.to_parquet(path, index=False, **options)
                except ImportError as error:
                    raise MissingExtra("writing Parquet", "pyarrow") from error
            case "xlsx":
                self._write_excel(frame, path, **options)
            case _:
                from sclpl.errors import ValidationError

                raise ValidationError(f"cannot write {fmt!r}")

    def _write_excel(self, frame: Any, path: Path, **options: Any) -> None:
        """`to_excel`, refusing rather than silently corrupting what it cannot hold.

        Excel has no integer type of its own -- every number is an IEEE-754 double,
        which cannot distinguish some large integers from their neighbors. Writing
        one anyway does not raise; it just answers a different question later than
        the one that was asked. Refusing here is this format's "fail with a loss
        diagnostic" (SPEC E9), the same way an unsupported timezone already refuses
        rather than silently dropping the offset.
        """
        from sclpl.errors import ValidationError

        unsafe = _excel_unsafe_integers(frame)
        if unsafe:
            column, value = unsafe[0]
            raise ValidationError(
                f"column {column!r} has {value}, too large for Excel to store exactly",
                remedies=[
                    "Excel stores every number as a 64-bit float, which cannot tell "
                    f"{value} apart from every other integer near it",
                    "write it as text instead, or use CSV/JSON/Parquet, which keep it exact",
                ],
            )
        try:
            frame.to_excel(path, index=False, **options)
        except ImportError as error:
            raise MissingExtra("writing Excel", "openpyxl") from error
        except ValueError as error:
            if "timezone" not in str(error).lower():
                raise
            raise ValidationError(
                f"{error}",
                remedies=[
                    "convert the column to UTC and drop its tzinfo before writing xlsx",
                    "or use CSV/JSON/Parquet/SQLite, which all keep the timezone",
                ],
            ) from error


def _find_records(payload: Any) -> list[dict[str, Any]]:
    """The list of objects inside a JSON document.

    An API answers `{"data": [...]}` or `{"items": [...]}` at least as often as a bare
    array, so look one level in before giving up. Guessing wrong is visible immediately
    -- the table has the wrong columns -- which is why guessing is acceptable here.
    """
    if isinstance(payload, list):
        return [row if isinstance(row, dict) else {"value": row} for row in payload]
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "records", "rows"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return _find_records(nested)
        for value in payload.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return _find_records(value)
        return [payload]
    return [{"value": payload}]


def _friendly(dtype: str) -> str:
    """pandas dtype names, in the vocabulary the rest of the tool uses."""
    if dtype.startswith("int") or dtype.startswith("uint"):
        return "integer"
    if dtype.startswith("float"):
        return "number"
    if dtype.startswith("bool"):
        return "boolean"
    if dtype.startswith("datetime"):
        return "datetime"
    if dtype in ("object", "string", "str"):
        return "string"
    return dtype
