"""The pandas backend.

The only place in the engine that imports pandas, and it imports it lazily -- pandas is
the `[data]` extra, and a workflow that never touches a table should not pay a
second of import time for it, nor fail to start without it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sclpl.tables.base import MissingExtra


def _pandas() -> Any:
    try:
        import pandas
    except ImportError as error:
        raise MissingExtra("tables", "pandas") from error
    return pandas


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
                return pandas.read_csv(path, **options)
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
                try:
                    frame.to_excel(path, index=False, **options)
                except ImportError as error:
                    raise MissingExtra("writing Excel", "openpyxl") from error
            case _:
                from sclpl.errors import ValidationError

                raise ValidationError(f"cannot write {fmt!r}")


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
