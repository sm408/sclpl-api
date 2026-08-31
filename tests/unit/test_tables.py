"""Tables, flattening, and format dispatch.

The flattening rules here are the reference behaviour (SPEC section 10). They are
pinned tightly on purpose: column order and separator choices are what a downstream
spreadsheet formula depends on, so a change to either is a breaking change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sclpl.errors import ValidationError
from sclpl.tables import Table, as_table, io
from sclpl.tables.flatten import (
    flatten_record,
    flatten_records,
    infer_schema,
    records_of,
    unflatten_record,
)

NESTED: list[dict[str, Any]] = [
    {
        "id": 1,
        "customer": {"name": "Ada", "address": {"city": "London", "zip": "E1"}},
        "tags": ["rush", "gift"],
        "total": 19.5,
    },
    {
        "id": 2,
        "customer": {"name": "Grace", "address": {"city": "Baltimore"}},
        "tags": [],
        "total": 240.0,
    },
]


# -- flattening: the reference behaviour ------------------------------------------


def test_nested_objects_become_underscore_columns() -> None:
    flat = flatten_record(NESTED[0])
    assert flat["customer_name"] == "Ada"
    assert flat["customer_address_city"] == "London"
    assert "customer" not in flat


def test_column_order_is_depth_first_and_first_seen() -> None:
    """Stable across runs, because a spreadsheet formula refers to column D."""
    assert list(flatten_record(NESTED[0])) == [
        "id",
        "customer_name",
        "customer_address_city",
        "customer_address_zip",
        "tags",
        "total",
    ]


def test_a_list_of_scalars_is_joined_not_json_encoded() -> None:
    """`rush,gift` is readable in a cell; `["rush", "gift"]` is not."""
    assert flatten_record(NESTED[0])["tags"] == "rush,gift"


def test_a_list_of_objects_is_json_encoded() -> None:
    flat = flatten_record({"lines": [{"sku": "a"}, {"sku": "b"}]})
    assert json.loads(flat["lines"]) == [{"sku": "a"}, {"sku": "b"}]


def test_an_empty_list_flattens_to_nothing_rather_than_a_literal() -> None:
    assert flatten_record({"tags": []})["tags"] is None


def test_a_column_collision_is_suffixed_rather_than_overwritten() -> None:
    """Losing a column silently is worse than an ugly name."""
    flat = flatten_record({"a_b": 1, "a": {"b": 2}})
    assert flat["a_b"] == 1
    assert flat["a_b_2"] == 2


def test_the_separator_is_configurable() -> None:
    assert "customer.name" in flatten_record(NESTED[0], sep=".")


def test_depth_is_bounded() -> None:
    deep: dict[str, Any] = {"v": 1}
    for _ in range(20):
        deep = {"n": deep}
    flat = flatten_record(deep, max_depth=3)
    assert len(flat) == 1
    assert "n_n_n" in next(iter(flat))


def test_union_gives_every_record_every_column() -> None:
    rows = flatten_records(NESTED, columns="union")
    assert all(list(row) == list(rows[0]) for row in rows)
    assert rows[1]["customer_address_zip"] is None


def test_intersection_keeps_only_shared_columns() -> None:
    rows = flatten_records(NESTED, columns="intersection")
    assert "customer_address_zip" not in rows[0]
    assert "customer_address_city" in rows[0]


def test_first_takes_the_shape_of_the_first_record() -> None:
    rows = flatten_records(NESTED, columns="first")
    assert list(rows[1]) == list(rows[0])


def test_explode_turns_each_element_into_a_row() -> None:
    rows = flatten_records([{"id": 1, "tags": ["a", "b"]}], explode="tags")
    assert [row["tags"] for row in rows] == ["a", "b"]
    assert all(row["id"] == 1 for row in rows)


def test_exploding_an_empty_list_keeps_the_row_with_a_null() -> None:
    """Dropping the row would lose the parent record, which is rarely what is meant."""
    rows = flatten_records([{"id": 1, "tags": []}], explode="tags")
    assert rows == [{"id": 1, "tags": None}]


def test_unflatten_is_the_inverse_for_objects() -> None:
    record = {"id": 1, "customer": {"name": "Ada"}}
    assert unflatten_record(flatten_record(record)) == record


# -- the envelope rule ------------------------------------------------------------


@pytest.mark.parametrize("key", ["data", "items", "results", "records", "rows"])
def test_a_wrapped_list_is_reached_through(key: str) -> None:
    assert records_of({key: [{"a": 1}]}) == [{"a": 1}]


def test_an_object_without_an_envelope_is_one_record() -> None:
    assert records_of({"a": 1}) == [{"a": 1}]


def test_scalars_become_a_value_column() -> None:
    assert records_of([1, 2]) == [{"value": 1}, {"value": 2}]
    assert records_of(None) == []


# -- schema inference -------------------------------------------------------------


def test_types_are_inferred_and_widened() -> None:
    schema = infer_schema([{"n": 1, "s": "a", "b": True}, {"n": 1.5, "s": None, "b": False}])
    assert schema == {"n": "number", "s": "string", "b": "boolean"}


def test_a_column_that_is_only_null_says_so() -> None:
    assert infer_schema([{"x": None}]) == {"x": "null"}


def test_mixed_types_widen_to_string() -> None:
    assert infer_schema([{"x": 1}, {"x": "a"}]) == {"x": "string"}


# -- the Table wrapper ------------------------------------------------------------


@pytest.fixture
def table() -> Table:
    return Table.from_records(flatten_records(NESTED))


def test_a_table_reports_its_shape(table: Table) -> None:
    assert table.row_count == 2
    assert table.shape == (2, 6)
    assert len(table) == 2
    assert bool(table) is True


def test_an_empty_table_is_falsy() -> None:
    assert not Table.from_records([])


def test_selecting_an_unknown_column_names_the_ones_there_are(table: Table) -> None:
    with pytest.raises(ValidationError) as caught:
        table.select(["custmer_name"])
    assert "customer_name" in str(caught.value)


def test_iterating_a_table_yields_records(table: Table) -> None:
    assert next(iter(table))["customer_name"] == "Ada"


def test_indexing_by_column_gives_the_values(table: Table) -> None:
    assert table["customer_name"] == ["Ada", "Grace"]


def test_indexing_by_position_gives_the_row(table: Table) -> None:
    assert table[0]["id"] == 1


def test_the_digest_follows_content_not_identity(table: Table) -> None:
    """The cache key in M7 depends on this being about the data alone."""
    same = Table.from_records(flatten_records(NESTED))
    assert table.content_digest() == same.content_digest()
    assert table.content_digest() != table.head(1).content_digest()


def test_joining_on_a_shared_column(table: Table) -> None:
    right = Table.from_records([{"id": 1, "rep": "kay"}, {"id": 2, "rep": "lee"}])
    joined = table.join(right, ["id"])
    assert joined.row_count == 2
    assert "rep" in joined.columns


def test_as_table_accepts_what_a_step_produces() -> None:
    assert as_table([{"a": 1}]).row_count == 1
    assert as_table({"a": 1}).row_count == 1
    assert as_table(Table.from_records([{"a": 1}])).row_count == 1


# -- format dispatch --------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("x.csv", "csv"),
        ("x.json", "json"),
        ("x.ndjson", "ndjson"),
        ("x.parquet", "parquet"),
        ("x.xlsx", "xlsx"),
    ],
)
def test_the_extension_decides_the_format(name: str, expected: str) -> None:
    assert io.format_of(Path(name)) == expected


def test_an_unknown_extension_says_how_to_be_explicit() -> None:
    with pytest.raises(ValidationError) as caught:
        io.format_of(Path("x.dat"))
    assert "path.txt:csv" in str(caught.value)


def test_a_misspelled_explicit_format_is_corrected() -> None:
    with pytest.raises(ValidationError) as caught:
        io.format_of(Path("x.dat"), "csvv")
    assert "csv" in str(caught.value)


def test_reading_a_missing_file_points_at_the_step_that_should_have_written_it(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError) as caught:
        io.read(tmp_path / "absent.csv")
    assert "does not exist" in str(caught.value)


@pytest.mark.parametrize("fmt", ["csv", "json", "ndjson", "parquet", "xlsx"])
def test_every_format_round_trips(tmp_path: Path, fmt: str) -> None:
    path = tmp_path / f"out.{fmt}"
    io.write(NESTED, path)
    back = io.read(path)
    rows = back.to_records() if isinstance(back, Table) else back
    assert len(rows) == 2
    # The JSON formats keep the nesting they were given; the tabular ones flatten,
    # because a column called `customer` holding an object is no use to anything.
    if fmt in ("json", "ndjson"):
        assert rows[0]["customer"]["name"] == "Ada"
    else:
        assert rows[0]["customer_name"] == "Ada"


def test_writing_a_wrapped_payload_produces_rows_not_one_wide_record(tmp_path: Path) -> None:
    """`save_csv @response.body` is the common case and must not need unwrapping."""
    path = tmp_path / "out.csv"
    io.write({"data": NESTED, "total": 2}, path)
    assert io.read(path).row_count == 2


def test_writing_creates_the_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "nested" / "out.csv"
    io.write([{"a": 1}], path)
    assert path.exists()


def test_sqlite_points_at_the_plugin(tmp_path: Path) -> None:
    """Locked decision 8: SQLite is a plugin, and the core says so rather than failing."""
    with pytest.raises(ValidationError) as caught:
        io.write([{"a": 1}], tmp_path / "out.sqlite")
    assert "plugin" in str(caught.value)
