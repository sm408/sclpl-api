"""The built-in function catalogue, and the registry that derives it from signatures.

Everything here goes through `evaluate` rather than calling the Python function
directly, because the path that matters is the one a workflow takes: parse, dispatch,
coerce, call. A function that works when imported and fails when called from SCLPLL is
a function that does not work.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sclpl import bootstrap
from sclpl.errors import AssertionFailed, TypeDispatchError, ValidationError
from sclpl.expr import Context, evaluate, parse
from sclpl.ext import functions as registry
from sclpl.tables import Table
from sclpl.values import ValueStore

bootstrap.load(plugins=False)

ORDERS: list[dict[str, Any]] = [
    {"id": 1, "city": "London", "total": 20, "customer": {"name": "Ada"}},
    {"id": 2, "city": "Baltimore", "total": 240, "customer": {"name": "Grace"}},
    {"id": 3, "city": "London", "total": 7, "customer": {"name": "Alan"}},
]

REPS = [{"id": 1, "rep": "kay"}, {"id": 2, "rep": "lee"}]


@pytest.fixture
def ctx() -> Context:
    store = ValueStore()
    store.put("orders", ORDERS, readers=999)
    store.put("reps", REPS, readers=999)
    store.put("wrapped", {"data": ORDERS, "total": 3}, readers=999)
    store.put("names", ["Ada", "Grace"], readers=999)
    return Context(store=store, vars={})


async def run(source: str, ctx: Context) -> Any:
    return await evaluate(parse(source), ctx)


def rows(value: Any) -> list[dict[str, Any]]:
    return value.to_records() if isinstance(value, Table) else value


# -- the registry -----------------------------------------------------------------


def test_every_builtin_is_registered_once() -> None:
    names = registry.names(builtin=True)
    assert len(names) == len(set(names))
    assert "save_csv" in names


def test_the_signature_is_read_off_the_annotations() -> None:
    assert registry.lookup("head").signature() == "head(data, n=10)"


def test_the_schema_comes_from_the_type_hints() -> None:
    schema = registry.lookup("head").schema()
    assert schema["properties"]["n"]["type"] == "integer"
    assert schema["required"] == ["data"]


def test_a_misspelled_function_is_corrected() -> None:
    with pytest.raises(TypeDispatchError) as caught:
        registry.lookup("save_cvs")
    assert "save_csv" in str(caught.value)


async def test_a_misspelled_keyword_names_the_signature(ctx: Context) -> None:
    with pytest.raises(TypeDispatchError) as caught:
        await run("assert_rowcount(@orders, mn=1)", ctx)
    assert "min" in str(caught.value)


async def test_a_string_from_a_workflow_file_is_coerced_to_the_int_wanted(
    ctx: Context,
) -> None:
    """A workflow file has no types beyond JSON's; the annotations supply the rest."""
    assert len(rows(await run("head(@orders, '2')", ctx))) == 2


def test_loading_twice_does_not_double_register() -> None:
    before = registry.names()
    bootstrap.load(plugins=False)
    assert registry.names() == before


# -- one name, two shapes ---------------------------------------------------------


async def test_join_of_a_list_and_a_separator_is_a_string(ctx: Context) -> None:
    assert await run("join(@names, ' & ')", ctx) == "Ada & Grace"


async def test_join_of_two_record_sets_on_a_key_is_a_table(ctx: Context) -> None:
    joined = await run("join(@orders, @reps, 'id')", ctx)
    assert joined.row_count == 2
    assert "rep" in joined.columns


async def test_joining_tables_without_a_key_says_which_shape_it_wanted(ctx: Context) -> None:
    with pytest.raises(ValidationError) as caught:
        await run("join(@orders, @reps)", ctx)
    assert "column to join on" in str(caught.value)


async def test_an_unknown_join_type_lists_the_known_ones(ctx: Context) -> None:
    with pytest.raises(ValidationError) as caught:
        await run("join(@orders, @reps, 'id', how='sideways')", ctx)
    assert "outer" in str(caught.value)


async def test_flatten_of_nested_lists_collapses_them(ctx: Context) -> None:
    assert await run("flatten([[1], [2, 3]])", ctx) == [1, 2, 3]


async def test_flatten_of_records_makes_columns(ctx: Context) -> None:
    assert "customer_name" in (await run("flatten(@orders)", ctx))[0]


async def test_merge_of_objects_lets_the_later_one_win(ctx: Context) -> None:
    assert await run("merge({'a': 1}, {'a': 2, 'b': 3})", ctx) == {"a": 2, "b": 3}


async def test_merge_of_record_sets_stacks_them(ctx: Context) -> None:
    assert len(rows(await run("merge(@orders, @orders)", ctx))) == 6


# -- shaping ----------------------------------------------------------------------


async def test_an_envelope_is_reached_through_without_being_named(ctx: Context) -> None:
    assert len(rows(await run("head(@wrapped, 10)", ctx))) == 3


async def test_sorting_descending(ctx: Context) -> None:
    sorted_rows = rows(await run("sort_by(@orders, 'total', descending=true)", ctx))
    assert [row["id"] for row in sorted_rows] == [2, 1, 3]


async def test_sorting_by_a_column_that_is_not_there_suggests_one(ctx: Context) -> None:
    with pytest.raises(ValidationError) as caught:
        await run("sort_by(@orders, 'totl')", ctx)
    assert "total" in str(caught.value)


async def test_grouping_without_an_aggregate_counts(ctx: Context) -> None:
    grouped = rows(await run("group_agg(@orders, 'city')", ctx))
    assert {row["city"]: row["count"] for row in grouped} == {"London": 2, "Baltimore": 1}


async def test_grouping_with_an_aggregate(ctx: Context) -> None:
    grouped = rows(await run("group_agg(@orders, 'city', agg={'total': 'sum'})", ctx))
    assert {row["city"]: row["total_sum"] for row in grouped} == {"London": 27, "Baltimore": 240}


async def test_summing_a_text_column_says_what_it_found(ctx: Context) -> None:
    with pytest.raises(TypeDispatchError) as caught:
        await run("group_agg(@orders, 'id', agg={'city': 'sum'})", ctx)
    assert "cast_schema" in str(caught.value)


async def test_an_unknown_aggregate_lists_the_known_ones(ctx: Context) -> None:
    with pytest.raises(ValidationError) as caught:
        await run("group_agg(@orders, 'city', agg={'total': 'mode'})", ctx)
    assert "median" not in str(caught.value)
    assert "avg" in str(caught.value)


async def test_pivot_turns_values_into_columns(ctx: Context) -> None:
    table = await run("pivot(@orders, index='city', column='id', value='total')", ctx)
    assert set(table.columns) >= {"city", "1", "2", "3"}


async def test_select_keeps_only_what_was_asked_for(ctx: Context) -> None:
    assert list(rows(await run("select(@orders, 'id', 'city')", ctx))[0]) == ["id", "city"]


async def test_rename(ctx: Context) -> None:
    assert "order_id" in rows(await run("rename(@orders, {'id': 'order_id'})", ctx))[0]


async def test_dedupe_by_a_column(ctx: Context) -> None:
    assert len(rows(await run("dedupe(@orders, by='city')", ctx))) == 2


async def test_cast_schema_coerces_the_named_columns(ctx: Context) -> None:
    cast = rows(await run("cast_schema(@orders, {'total': 'string'})", ctx))
    assert cast[0]["total"] == "20"
    assert cast[0]["id"] == 1


async def test_casting_to_an_unknown_type_lists_the_known_ones(ctx: Context) -> None:
    with pytest.raises(ValidationError) as caught:
        await run("cast_schema(@orders, {'total': 'decimal'})", ctx)
    assert "integer" in str(caught.value)


# -- record helpers ----------------------------------------------------------------


async def test_pluck_returns_one_column_in_order(ctx: Context) -> None:
    assert await run("pluck(@orders, 'city')", ctx) == ["London", "Baltimore", "London"]


async def test_filter_rows_combines_checks(ctx: Context) -> None:
    kept = await run("filter_rows(@orders, 'total', minimum=10, maximum=100)", ctx)
    assert [row["id"] for row in rows(kept)] == [1]


async def test_fill_nulls_replaces_missing_and_null_values(ctx: Context) -> None:
    filled = await run("fill_nulls([{'a': null}, {'b': 2}], {'a': 0})", ctx)
    assert filled == [{"a": 0}, {"b": 2, "a": 0}]


async def test_row_number_preserves_table_shape(ctx: Context) -> None:
    numbered = await run("row_number(to_table(@orders), column='line', start=10)", ctx)
    assert isinstance(numbered, Table)
    assert numbered.to_records()[0]["line"] == 10


# -- diagnostics ------------------------------------------------------------------


async def test_a_passing_assertion_returns_the_data_so_it_can_sit_mid_pipeline(
    ctx: Context,
) -> None:
    assert len(rows(await run("assert_rowcount(@orders, min=3)", ctx))) == 3


async def test_a_missing_column_says_which_ones_are_present(ctx: Context) -> None:
    with pytest.raises(AssertionFailed) as caught:
        await run("assert_schema(@orders, {'nope': 'string'})", ctx)
    assert "present:" in str(caught.value)


async def test_an_integer_column_satisfies_number(ctx: Context) -> None:
    """Widening never loses information; the reverse would."""
    await run("assert_schema(@orders, {'total': 'number'})", ctx)


async def test_a_number_column_does_not_satisfy_integer(ctx: Context) -> None:
    with pytest.raises(AssertionFailed):
        await run("assert_schema([{'x': 1.5}], {'x': 'integer'})", ctx)


async def test_an_extra_column_is_fine_unless_strict(ctx: Context) -> None:
    """An API adding a field should not break a workflow that ignores it."""
    await run("assert_schema(@orders, {'id': 'integer'})", ctx)
    with pytest.raises(AssertionFailed):
        await run("assert_schema(@orders, {'id': 'integer'}, strict=true)", ctx)


async def test_too_few_rows_mentions_the_usual_cause(ctx: Context) -> None:
    with pytest.raises(AssertionFailed) as caught:
        await run("assert_rowcount(@orders, min=10)", ctx)
    assert "filter matched nothing" in str(caught.value)


async def test_duplicates_are_shown_not_just_counted(ctx: Context) -> None:
    with pytest.raises(AssertionFailed) as caught:
        await run("assert_unique(@orders, 'city')", ctx)
    assert "London" in str(caught.value)


async def test_nulls_are_reported_per_column(ctx: Context) -> None:
    with pytest.raises(AssertionFailed) as caught:
        await run("assert_no_nulls([{'a': null, 'b': 1}], 'a')", ctx)
    assert "a (1)" in str(caught.value)


async def test_profile_summarises(ctx: Context) -> None:
    summary = await run("profile(@orders)", ctx)
    assert summary["rows"] == 3
    assert summary["schema"]["total"] == "integer"


async def test_describe_gives_statistics_for_numeric_columns(ctx: Context) -> None:
    described = await run("describe(@orders)", ctx)
    assert described["total"]["max"] == 240
    assert described["city"]["distinct"] == 2
    assert "max" not in described["city"]


async def test_sample_spreads_through_the_data_rather_than_taking_the_front(
    ctx: Context,
) -> None:
    picked = await run("sample(@orders, 2)", ctx)
    assert [row["id"] for row in picked] == [1, 3]


# -- io -------------------------------------------------------------------------


async def test_the_exit_criterion_nested_json_to_flat_csv_to_excel(
    ctx: Context, tmp_path: Path
) -> None:
    """M5's exit: nested JSON in, flattened CSV out, then Excel, checked on the way."""
    source = tmp_path / "in.json"
    source.write_text(json.dumps({"data": ORDERS}), encoding="utf-8")
    csv_path = (tmp_path / "out.csv").as_posix()
    xlsx_path = (tmp_path / "out.xlsx").as_posix()

    await run(f"save_csv(read_json('{source.as_posix()}'), '{csv_path}')", ctx)
    header = (tmp_path / "out.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "id,city,total,customer_name"

    await run(
        f"save_excel(assert_schema(read_csv('{csv_path}'), "
        "{'id': 'integer', 'customer_name': 'string', 'total': 'number'}), "
        f"'{xlsx_path}')",
        ctx,
    )
    back = await run(f"read_excel('{xlsx_path}')", ctx)
    assert back.row_count == 3
    assert back.to_records()[0]["customer_name"] == "Ada"


async def test_a_writer_returns_its_path_so_a_later_step_can_use_it(
    ctx: Context, tmp_path: Path
) -> None:
    path = (tmp_path / "out.json").as_posix()
    assert await run(f"save_json(@orders, '{path}')", ctx) == str(tmp_path / "out.json")


async def test_convert_reads_one_format_and_writes_another(ctx: Context, tmp_path: Path) -> None:
    source = tmp_path / "in.json"
    source.write_text(json.dumps(ORDERS), encoding="utf-8")
    await run(f"convert('{source.as_posix()}', '{(tmp_path / 'out.csv').as_posix()}')", ctx)
    assert (tmp_path / "out.csv").exists()


async def test_glob_read_concatenates(ctx: Context, tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"part{index}.json").write_text(json.dumps([{"n": index}]), encoding="utf-8")
    read = await run(f"glob_read('{(tmp_path / '*.json').as_posix()}')", ctx)
    assert sorted(row["n"] for row in rows(read)) == [0, 1, 2]


async def test_a_glob_that_matches_nothing_mentions_shell_quoting(
    ctx: Context, tmp_path: Path
) -> None:
    with pytest.raises(ValidationError) as caught:
        await run(f"glob_read('{(tmp_path / '*.absent').as_posix()}')", ctx)
    assert "quote the pattern" in str(caught.value)


async def test_explode_gives_each_element_its_own_row(ctx: Context) -> None:
    exploded = await run("explode([{'id': 1, 'tags': ['a', 'b']}], 'tags')", ctx)
    assert [row["tags"] for row in exploded] == ["a", "b"]


async def test_saving_by_extension_alone(ctx: Context, tmp_path: Path) -> None:
    await run(f"save(@orders, '{(tmp_path / 'out.ndjson').as_posix()}')", ctx)
    assert len((tmp_path / "out.ndjson").read_text(encoding="utf-8").strip().splitlines()) == 3
