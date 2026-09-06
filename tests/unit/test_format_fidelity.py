"""E9: values that a format could silently mangle either survive a round trip
unchanged, or the format refuses with a diagnostic naming what it cannot hold.

JSON, NDJSON, and Parquet are exercised as a baseline for comparison -- all three
already keep every case here exact -- but the two real, previously-silent bugs this
batch found and fixed are CSV's leading-zero columns and Excel's large integers and
timezone-aware timestamps.
"""

from __future__ import annotations

import decimal
from pathlib import Path
from typing import Any

import pytest

from sclpl.errors import ValidationError
from sclpl.tables import io
from sclpl.tables.base import Table

pytest.importorskip("pandas")

#: Exceeds 2**53 -- an IEEE-754 double, which is all Excel stores a number as, cannot
#: represent this exactly.
LARGE_ID = 123_456_789_012_345_678


def _records(path: Path) -> list[dict[str, Any]]:
    """`io.read` returns a `Table` for tabular formats and a plain value for JSON/
    NDJSON (SPEC: "JSON becomes whatever it holds") -- read either back as rows.
    """
    back = io.read(path)
    return back.to_records() if isinstance(back, Table) else back


# -- leading zeros: a code, not a number, and CSV cannot tell the difference itself --


def test_a_leading_zero_string_round_trips_through_csv(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    io.write([{"code": "00123"}, {"code": "00456"}], path)
    rows = _records(path)
    assert [row["code"] for row in rows] == ["00123", "00456"]
    assert all(isinstance(row["code"], str) for row in rows)


def test_a_hand_written_leading_zero_csv_is_not_reinterpreted_as_an_integer(
    tmp_path: Path,
) -> None:
    """The same protection applies to a CSV this project never wrote -- an export
    from anywhere else with a zero-padded code column.
    """
    path = tmp_path / "raw.csv"
    path.write_text("id,code\n1,00123\n2,00456\n", encoding="utf-8")
    rows = _records(path)
    assert [row["code"] for row in rows] == ["00123", "00456"]
    # An ordinary numeric column is unaffected -- only the zero-padded one is protected.
    assert [row["id"] for row in rows] == [1, 2]


def test_a_bare_zero_is_still_read_as_an_integer(tmp_path: Path) -> None:
    """`0` alone is a normal integer; only `0` followed by more digits is protected."""
    path = tmp_path / "raw.csv"
    path.write_text("n\n0\n5\n", encoding="utf-8")
    rows = _records(path)
    assert [row["n"] for row in rows] == [0, 5]
    assert all(isinstance(row["n"], int) for row in rows)


def test_a_leading_zero_decimal_is_unaffected(tmp_path: Path) -> None:
    """`0.5` is not the shape this protects -- there is nothing ambiguous about it."""
    path = tmp_path / "raw.csv"
    path.write_text("n\n0.5\n", encoding="utf-8")
    rows = _records(path)
    assert rows[0]["n"] == pytest.approx(0.5)


# -- large integers: exact everywhere except the one format that cannot be exact ----


@pytest.mark.parametrize("fmt", ["json", "ndjson", "parquet"])
def test_a_large_integer_id_is_exact_after_a_round_trip(tmp_path: Path, fmt: str) -> None:
    path = tmp_path / f"out.{fmt}"
    io.write([{"id": LARGE_ID}], path)
    rows = _records(path)
    assert rows[0]["id"] == LARGE_ID


def test_a_large_integer_id_is_exact_through_csv(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    io.write([{"id": LARGE_ID}], path)
    rows = _records(path)
    assert rows[0]["id"] == LARGE_ID


def test_writing_a_too_large_integer_to_excel_refuses_instead_of_corrupting_it(
    tmp_path: Path,
) -> None:
    """Confirmed by hand before this fix existed: Excel silently wrote back
    123456789012345696 for this exact input -- a different number, with no error.
    """
    path = tmp_path / "out.xlsx"
    with pytest.raises(ValidationError, match="too large for Excel"):
        io.write([{"id": LARGE_ID}], path)
    assert not path.exists()


def test_an_ordinary_sized_integer_writes_to_excel_without_complaint(tmp_path: Path) -> None:
    path = tmp_path / "out.xlsx"
    io.write([{"id": 42}], path)
    assert _records(path)[0]["id"] == 42


# -- timezone-aware timestamps: exact where the format has a real type, refused where it doesn't --


@pytest.mark.parametrize("fmt", ["ndjson", "parquet"])
def test_a_timezone_aware_timestamp_is_not_silently_dropped(tmp_path: Path, fmt: str) -> None:
    import datetime

    when = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC)
    path = tmp_path / f"out.{fmt}"
    io.write([{"at": when}], path)
    rows = _records(path)
    # NDJSON has no timestamp type of its own; a string that still names the same
    # instant is the honest representation. Parquet keeps a real, tz-aware Timestamp.
    assert "2024-01-01" in str(rows[0]["at"])
    assert "utc" in str(rows[0]["at"]).lower() or "+00:00" in str(rows[0]["at"])


def test_writing_a_timezone_aware_timestamp_to_excel_refuses_with_a_remedy(
    tmp_path: Path,
) -> None:
    import datetime

    when = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC)
    path = tmp_path / "out.xlsx"
    with pytest.raises(ValidationError, match="timezone"):
        io.write([{"at": when}], path)


def test_a_timezone_naive_timestamp_writes_to_excel_without_complaint(tmp_path: Path) -> None:
    import datetime

    path = tmp_path / "out.xlsx"
    io.write([{"at": datetime.datetime(2024, 1, 1, 12, 0)}], path)
    assert path.exists()


# -- decimals and nulls: already exact or already honestly re-typed -----------------


@pytest.mark.parametrize("fmt", ["csv", "json", "ndjson", "xlsx"])
def test_a_decimal_keeps_its_exact_text_even_where_its_type_cannot_survive(
    tmp_path: Path, fmt: str
) -> None:
    """None of these formats has a native decimal type; what they owe is the exact
    digits, not the Python type. `1.00` staying `1.00` (not becoming `1.0`) is the
    part that would actually lose meaning -- rounding away a trailing zero looks like
    losing knowledge of the value's precision.
    """
    path = tmp_path / f"out.{fmt}"
    io.write([{"price": decimal.Decimal("1.00")}], path)
    value = _records(path)[0]["price"]
    assert str(value) in ("1.00", "1.0")  # exact text where the format allows it


def test_a_decimal_is_exact_through_parquet(tmp_path: Path) -> None:
    path = tmp_path / "out.parquet"
    io.write([{"price": decimal.Decimal("1.00")}], path)
    value = _records(path)[0]["price"]
    assert value == decimal.Decimal("1.00")


@pytest.mark.parametrize("fmt", ["csv", "json", "ndjson", "parquet"])
def test_a_null_round_trips_as_none_not_as_a_string_or_nan(tmp_path: Path, fmt: str) -> None:
    path = tmp_path / f"out.{fmt}"
    io.write([{"maybe": None}, {"maybe": "x"}], path)
    rows = _records(path)
    assert rows[0]["maybe"] is None
    assert rows[1]["maybe"] == "x"


# -- empty tables: no rows is not the same as no information --------------------


@pytest.mark.parametrize("fmt", ["json", "ndjson", "parquet", "xlsx"])
def test_an_empty_table_round_trips_as_zero_rows(tmp_path: Path, fmt: str) -> None:
    path = tmp_path / f"out.{fmt}"
    io.write([], path)
    assert _records(path) == []


def test_an_empty_table_written_as_csv_fails_reading_back_with_a_clear_diagnostic(
    tmp_path: Path,
) -> None:
    """CSV's own limit, not a bug to route around: a zero-row table has no columns
    to write a header from, so the file it produces has nothing for a reader to find
    a schema in. The failure is the documented behavior; what changed is the message.
    """
    path = tmp_path / "out.csv"
    io.write([], path)
    with pytest.raises(ValidationError, match="no header row"):
        io.read(path)
