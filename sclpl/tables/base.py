"""The Table wrapper and the backend protocol.

`Table` is a thin, backend-agnostic handle on tabular data. Everything the engine does
with a table goes through the protocol below, so the pandas backend is one
implementation rather than an assumption baked into every operator.

Why a wrapper at all, when the invariant says no abstraction until the second caller:
the second caller already exists. `values/ref.py` spills tables to Parquet without
importing pandas, `expr/ops` dispatches on the type, and `preflight` reports the missing
extra by name. All three need a stable identity for "a table" that does not require
pandas to be installed to talk about.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from sclpl.run.errors import SclplError


class MissingExtra(SclplError):
    """A table operation needs an optional dependency that is not installed.

    Reported by preflight before anything runs (decision 3), so a pipeline never dies
    at the write step after every request has already been paid for.
    """

    def __init__(self, feature: str, package: str, extra: str = "data") -> None:
        super().__init__(
            f"{feature} needs {package}, which is not installed",
            remedies=[f"pip install 'sclpl[{extra}]'", f"or: pip install {package}"],
        )


@runtime_checkable
class TableBackend(Protocol):
    """What a backend has to be able to do.

    Deliberately small. Anything expressible as a composition of these lives in
    `expr/ops` or `functions/`, not here -- a wide protocol is a backend nobody else
    can implement.
    """

    name: str

    def from_records(self, records: list[dict[str, Any]]) -> Any: ...

    def to_records(self, frame: Any) -> list[dict[str, Any]]: ...

    def columns(self, frame: Any) -> list[str]: ...

    def row_count(self, frame: Any) -> int: ...

    def select(self, frame: Any, columns: list[str]) -> Any: ...

    def filter(self, frame: Any, mask: list[bool]) -> Any: ...

    def sort(self, frame: Any, by: list[str], descending: bool) -> Any: ...

    def head(self, frame: Any, n: int) -> Any: ...

    def concat(self, frames: list[Any]) -> Any: ...

    def join(self, left: Any, right: Any, on: list[str], how: str) -> Any: ...

    def dedupe(self, frame: Any, subset: list[str] | None) -> Any: ...

    def rename(self, frame: Any, mapping: dict[str, str]) -> Any: ...

    def dtypes(self, frame: Any) -> dict[str, str]: ...

    def read(self, path: Path, fmt: str, **options: Any) -> Any: ...

    def write(self, frame: Any, path: Path, fmt: str, **options: Any) -> None: ...


class Table:
    """Tabular data, with a backend behind it.

    Wrapping rather than subclassing a DataFrame is deliberate: the engine's contract
    is this class's methods, and a step that reaches past them into pandas is a step
    that stops working when the backend changes.
    """

    __slots__ = ("_frame", "_backend")

    def __init__(self, frame: Any, backend: TableBackend | None = None) -> None:
        self._frame = frame
        self._backend = backend if backend is not None else default_backend()

    # -- construction ------------------------------------------------------------

    @classmethod
    def from_records(
        cls, records: list[dict[str, Any]], backend: TableBackend | None = None
    ) -> Table:
        engine = backend if backend is not None else default_backend()
        return cls(engine.from_records(records), engine)

    @classmethod
    def read(
        cls, path: Path, fmt: str, backend: TableBackend | None = None, **options: Any
    ) -> Table:
        engine = backend if backend is not None else default_backend()
        return cls(engine.read(path, fmt, **options), engine)

    # -- inspection --------------------------------------------------------------

    @property
    def frame(self) -> Any:
        """The backend's native object. For a backend-specific function only."""
        return self._frame

    @property
    def backend(self) -> TableBackend:
        return self._backend

    @property
    def columns(self) -> list[str]:
        return self._backend.columns(self._frame)

    @property
    def row_count(self) -> int:
        return self._backend.row_count(self._frame)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.row_count, len(self.columns))

    @property
    def empty(self) -> bool:
        return self.row_count == 0

    def dtypes(self) -> dict[str, str]:
        return self._backend.dtypes(self._frame)

    def to_records(self) -> list[dict[str, Any]]:
        return self._backend.to_records(self._frame)

    # -- operations --------------------------------------------------------------

    def select(self, columns: list[str]) -> Table:
        missing = [column for column in columns if column not in self.columns]
        if missing:
            from sclpl.run.errors import ValidationError, did_you_mean

            remedies = []
            suggestion = did_you_mean(missing[0], self.columns)
            if suggestion:
                remedies.append(suggestion)
            remedies.append(f"columns: {', '.join(self.columns[:8])}")
            raise ValidationError(
                f"no column named {missing[0]!r}",
                remedies=remedies,
            )
        return Table(self._backend.select(self._frame, columns), self._backend)

    def filter(self, mask: list[bool]) -> Table:
        return Table(self._backend.filter(self._frame, mask), self._backend)

    def sort(self, by: list[str], descending: bool = False) -> Table:
        return Table(self._backend.sort(self._frame, by, descending), self._backend)

    def head(self, n: int) -> Table:
        return Table(self._backend.head(self._frame, n), self._backend)

    def concat(self, other: Table) -> Table:
        return Table(self._backend.concat([self._frame, other._frame]), self._backend)

    def join(self, other: Table, on: list[str], how: str = "inner") -> Table:
        return Table(self._backend.join(self._frame, other._frame, on, how), self._backend)

    def dedupe(self, subset: list[str] | None = None) -> Table:
        return Table(self._backend.dedupe(self._frame, subset), self._backend)

    def rename(self, mapping: dict[str, str]) -> Table:
        return Table(self._backend.rename(self._frame, mapping), self._backend)

    # -- output ------------------------------------------------------------------

    def write(self, path: Path, fmt: str, **options: Any) -> None:
        self._backend.write(self._frame, path, fmt, **options)

    def to_parquet(self, path: Path) -> None:
        """Used by the spill path in `values/ref.py`, which looks for this by name."""
        self._backend.write(self._frame, path, "parquet")

    def content_digest(self) -> str:
        """A digest of the contents, for the cache key.

        Shape plus column names plus the records. Not cheap for a large table, which is
        why `values/digest.py` only reaches for it when it has nothing better.
        """
        from sclpl.values.digest import digest

        return digest({"columns": self.columns, "rows": self.to_records()})

    # -- protocol ----------------------------------------------------------------

    def __len__(self) -> int:
        return self.row_count

    def __bool__(self) -> bool:
        return self.row_count > 0

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.to_records())

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            return [row.get(key) for row in self.to_records()]
        if isinstance(key, list):
            return self.select(key)
        if isinstance(key, int):
            return self.to_records()[key]
        if isinstance(key, slice):
            return Table.from_records(self.to_records()[key], self._backend)
        raise TypeError(f"cannot index a table with {type(key).__name__}")

    def __repr__(self) -> str:
        rows, columns = self.shape
        return f"<Table {rows}x{columns} {self.columns[:5]}>"


_BACKEND: list[TableBackend] = []


def default_backend() -> TableBackend:
    """The backend in use. pandas today; the protocol is what makes that replaceable."""
    if not _BACKEND:
        from sclpl.tables.pandas_backend import PandasBackend

        _BACKEND.append(PandasBackend())
    return _BACKEND[0]


def set_backend(backend: TableBackend) -> None:
    _BACKEND.clear()
    _BACKEND.append(backend)


def is_table(value: Any) -> bool:
    return isinstance(value, Table)


def as_table(value: Any) -> Table:
    """Coerce a value into a table, or say why it cannot be one."""
    if isinstance(value, Table):
        return value
    if isinstance(value, list):
        if not value:
            return Table.from_records([])
        if all(isinstance(item, dict) for item in value):
            return Table.from_records(value)
        # A list of scalars is a one-column table; naming the column `value` is a
        # choice, but an unnamed column is worse for everything downstream.
        return Table.from_records([{"value": item} for item in value])
    if isinstance(value, dict):
        return Table.from_records([value])
    from sclpl.run.errors import TypeDispatchError

    raise TypeDispatchError(
        f"cannot read {type(value).__name__} as a table",
        remedies=[
            "a table comes from a list of objects, or from read_csv / read_json",
            "use flatten() first if the objects are nested",
        ],
    )
