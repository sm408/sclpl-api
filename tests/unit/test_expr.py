"""The expression language: parsing, evaluation, and the errors it produces."""

from __future__ import annotations

from typing import Any

import pytest

from sclpl import bootstrap
from sclpl.errors import ExpressionError, PathError, TypeDispatchError, UnknownReference
from sclpl.expr import Context, evaluate, parse, parse_interpolated, unparse
from sclpl.expr.ast import Call, Literal, Ref
from sclpl.values import ValueStore

RESPONSE: dict[str, Any] = {
    "body": {
        "items": [
            {"id": 1, "price": 5, "name": "nail"},
            {"id": 2, "price": 15, "name": "hammer"},
            {"id": 3, "price": 30, "name": "saw"},
        ],
        "total": 3,
        "cursor": None,
    },
    "status": 200,
}


@pytest.fixture(autouse=True, scope="module")
def _catalogue() -> None:
    """A few operator names -- join, merge, flatten -- live in the built-in catalogue.

    They mean two things each and the dispatch table cannot tell the shapes apart, so
    one registration owns both. Loading the catalogue is what a run does anyway.
    """
    bootstrap.load(plugins=False)


@pytest.fixture
def ctx() -> Context:
    store = ValueStore()
    store.put("a", RESPONSE, readers=999)
    store.put("count", 7, readers=999)
    return Context(store=store, vars={"env": "prod", "limit": 10})


async def run(source: str, ctx: Context) -> Any:
    return await evaluate(parse(source), ctx)


# -- the exit criterion ----------------------------------------------------------


async def test_the_m1_exit_criterion(ctx: Context) -> None:
    """`@a.body.items[?(price > 10)].id` evaluates."""
    assert await run("@a.body.items[?(price > 10)].id", ctx) == [2, 3]


async def test_a_bad_path_fails_with_a_suggestion(ctx: Context) -> None:
    with pytest.raises(PathError) as caught:
        await run("@a.body.itmes", ctx)
    message = str(caught.value)
    assert "itmes" in message
    assert "did you mean 'items'?" in message


async def test_a_bad_path_never_returns_the_reference_text(ctx: Context) -> None:
    """The old engine returned '{{...}}' here, and it went out in a URL."""
    with pytest.raises(PathError):
        await run("@a.body.nothing", ctx)


# -- typed values ----------------------------------------------------------------


async def test_arithmetic_is_arithmetic_not_concatenation(ctx: Context) -> None:
    """Invariant 2. The old engine produced '51' for this."""
    assert await run("@a.body.total + 1", ctx) == 4
    assert isinstance(await run("@a.body.total + 1", ctx), int)


async def test_comparison_sees_numbers(ctx: Context) -> None:
    assert await run("@a.status == 200", ctx) is True
    assert await run("@a.status > 199", ctx) is True


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("1 + 2 * 3", 7),
        ("(1 + 2) * 3", 9),
        ("2 ** 3 ** 2", 512),  # right-associative
        ("10 / 4", 2.5),
        ("10 // 4", 2),
        ("10 % 3", 1),
        ("-5 + 2", -3),
        ("'a' + 'b'", "ab"),
        ("[1, 2] + [3]", [1, 2, 3]),
        ("true and false", False),
        ("true or false", True),
        ("not true", False),
        ("1 == 1 and 2 == 2", True),
        ("3 > 2 ? 'yes' : 'no'", "yes"),
        ("'yes' if 3 > 2 else 'no'", "yes"),
        ("2 in [1, 2, 3]", True),
        ("5 in [1, 2, 3]", False),
        ("'ell' in 'hello'", True),
        ("{'a': 1}.a", 1),
        ("[1, 2, 3][1]", 2),
        ("[1, 2, 3][-1]", 3),
        ("[1, 2, 3, 4][1:3]", [2, 3]),
    ],
)
async def test_evaluation(source: str, expected: Any) -> None:
    assert await evaluate(parse(source)) == expected


async def test_division_by_zero_is_an_error_not_infinity() -> None:
    with pytest.raises(TypeDispatchError) as caught:
        await evaluate(parse("1 / 0"))
    assert "division by zero" in str(caught.value)


async def test_and_short_circuits() -> None:
    """The right side must not evaluate, or a guard is not a guard."""
    assert await evaluate(parse("false and (1 / 0)")) is False


async def test_or_short_circuits() -> None:
    assert await evaluate(parse("true or (1 / 0)")) is True


# -- paths -----------------------------------------------------------------------


async def test_projection_flattens_one_level(ctx: Context) -> None:
    assert await run("@a.body.items[*].id", ctx) == [1, 2, 3]


async def test_field_read_maps_over_a_list_of_objects(ctx: Context) -> None:
    """`@items.name` is what people write; it should mean what it looks like."""
    assert await run("@a.body.items.name", ctx) == ["nail", "hammer", "saw"]


async def test_filter_resolves_bare_names_against_the_element(ctx: Context) -> None:
    result = await run("@a.body.items[?(name == 'saw')].id", ctx)
    assert result == [3]


async def test_filters_compose(ctx: Context) -> None:
    assert await run("@a.body.items[?(price > 5)][?(price < 30)].id", ctx) == [2]


async def test_out_of_range_index_says_the_length(ctx: Context) -> None:
    with pytest.raises(PathError) as caught:
        await run("@a.body.items[99]", ctx)
    assert "3 elements" in str(caught.value)


async def test_reading_through_null_says_so(ctx: Context) -> None:
    with pytest.raises(PathError) as caught:
        await run("@a.body.cursor.next", ctx)
    assert "null" in str(caught.value)


async def test_an_unknown_reference_names_what_is_available(ctx: Context) -> None:
    with pytest.raises(UnknownReference) as caught:
        await run("@orders.id", ctx)
    assert "@orders" in str(caught.value)


async def test_a_field_typo_inside_a_filter_suggests(ctx: Context) -> None:
    with pytest.raises(PathError) as caught:
        await run("@a.body.items[?(pric > 10)]", ctx)
    assert "did you mean 'price'" in str(caught.value)


# -- operators -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("count([1, 2, 3])", 3),
        ("sum([1, 2, 3])", 6),
        ("avg([2, 4])", 3),
        ("min([3, 1, 2])", 1),
        ("max([3, 1, 2])", 3),
        ("median([1, 3, 2])", 2),
        ("first([1, 2])", 1),
        ("last([1, 2])", 2),
        ("unique([1, 1, 2])", [1, 2]),
        ("reverse([1, 2])", [2, 1]),
        ("sort([3, 1, 2])", [1, 2, 3]),
        ("take([1, 2, 3], 2)", [1, 2]),
        ("chunk([1, 2, 3], 2)", [[1, 2], [3]]),
        ("flatten([[1], [2, 3]])", [1, 2, 3]),
        ("upper('ab')", "AB"),
        ("lower('AB')", "ab"),
        ("trim('  x  ')", "x"),
        ("split('a,b', ',')", ["a", "b"]),
        ("join(['a', 'b'], '-')", "a-b"),
        ("replace('aaa', 'a', 'b', 1)", "baa"),
        ("starts_with('hello', 'he')", True),
        ("matches('a1', '[a-z][0-9]')", True),
        ("slug('Hello World!')", "hello-world"),
        ("number('42')", 42),
        ("number('1,234')", 1234),
        ("number('12.5%')", 0.125),
        ("bool('yes')", True),
        ("type_of([])", "list"),
        ("coalesce(null, null, 3)", 3),
        ("default('', 'fallback')", "fallback"),
        ("is_null(null)", True),
        ("abs(-3)", 3),
        ("round(2.567, 1)", 2.6),
        ("clamp(15, 0, 10)", 10),
        ("keys({'a': 1, 'b': 2})", ["a", "b"]),
        ("pick({'a': 1, 'b': 2}, 'a')", {"a": 1}),
        ("omit({'a': 1, 'b': 2}, 'a')", {"b": 2}),
        ("merge({'a': 1}, {'a': 2, 'b': 3})", {"a": 2, "b": 3}),
    ],
)
async def test_operators(source: str, expected: Any) -> None:
    assert await evaluate(parse(source)) == expected


async def test_pluck_and_group(ctx: Context) -> None:
    assert await run("pluck(@a.body.items, 'id')", ctx) == [1, 2, 3]
    grouped = await run("group_by([{'k': 'a'}, {'k': 'b'}, {'k': 'a'}], 'k')", ctx)
    assert set(grouped) == {"a", "b"}
    assert len(grouped["a"]) == 2


async def test_the_pipe_reads_left_to_right(ctx: Context) -> None:
    assert await run("@a.body.items | pluck('id') | count()", ctx) == 3


async def test_sum_by_a_field(ctx: Context) -> None:
    assert await run("sum(@a.body.items, by='price')", ctx) == 50


async def test_sorting_by_a_field(ctx: Context) -> None:
    assert await run("sort(@a.body.items, by='price', descending=true)[0].id", ctx) == 3


# -- type errors say what to do --------------------------------------------------


async def test_comparing_a_string_to_a_number_names_both_types() -> None:
    with pytest.raises(TypeDispatchError) as caught:
        await evaluate(parse("'50' > 10"))
    message = str(caught.value)
    assert "str" in message and "int" in message
    assert "number(" in message


async def test_comparing_with_null_suggests_a_guard() -> None:
    with pytest.raises(TypeDispatchError) as caught:
        await evaluate(parse("null > 1"))
    assert "default(" in str(caught.value)


async def test_an_unknown_function_suggests_a_near_one() -> None:
    with pytest.raises(TypeDispatchError) as caught:
        await evaluate(parse("cont([1])"))
    assert "count" in str(caught.value)


async def test_adding_a_number_to_a_string_is_refused() -> None:
    with pytest.raises(TypeDispatchError):
        await evaluate(parse("'a' + 1"))


# -- interpolation ---------------------------------------------------------------


async def test_a_single_hole_keeps_the_type(ctx: Context) -> None:
    """Invariant 2: `{{@a.status}}` alone is the number, not the text of it."""
    result = await evaluate(parse_interpolated("{{@a.status}}"), ctx)
    assert result == 200
    assert isinstance(result, int)


async def test_a_hole_inside_text_stringifies(ctx: Context) -> None:
    result = await evaluate(parse_interpolated("status={{@a.status}}!"), ctx)
    assert result == "status=200!"


async def test_plain_text_needs_no_evaluation() -> None:
    assert await evaluate(parse_interpolated("just text")) == "just text"


async def test_booleans_interpolate_as_json_not_python() -> None:
    assert await evaluate(parse_interpolated("v={{true}}")) == "v=true"


async def test_null_interpolates_as_nothing() -> None:
    assert await evaluate(parse_interpolated("v={{null}}")) == "v="


async def test_an_unterminated_hole_is_an_error() -> None:
    with pytest.raises(ExpressionError):
        parse_interpolated("{{@a.id")


async def test_an_empty_hole_is_an_error() -> None:
    with pytest.raises(ExpressionError):
        parse_interpolated("x{{}}y")


# -- parsing ---------------------------------------------------------------------


def test_infix_lowers_to_a_call() -> None:
    """`a > b` is sugar. The evaluator only ever sees calls."""
    node = parse("1 > 2").node
    assert isinstance(node, Call)
    assert node.name == "gt"


def test_refs_are_collected_for_the_dag() -> None:
    """Invariant 3: the graph comes from the references, not a hand-written list."""
    assert parse("@a.id + @b.total").refs == frozenset({"a", "b"})
    assert parse("@x[?(@y.min > price)]").refs == frozenset({"x", "y"})


def test_interpolated_strings_collect_refs_too() -> None:
    assert parse_interpolated("{{@a.id}}/{{@b.id}}").refs == frozenset({"a", "b"})


@pytest.mark.parametrize(
    "source",
    ["1 +", "(1", "[1, 2", "@", "'unterminated", "1 $ 2", "f(a=1, 2)"],
)
def test_malformed_expressions_are_rejected(source: str) -> None:
    with pytest.raises(ExpressionError):
        parse(source)


def test_a_single_equals_in_a_condition_says_what_to_do() -> None:
    with pytest.raises(ExpressionError) as caught:
        parse("@a.status = 200")
    assert "'=' assigns" in str(caught.value)


def test_unparse_round_trips_through_the_parser() -> None:
    for source in ["@a.b[0].c", "@a.items[*].id", "@a.items[?(price > 10)]", "count(@a) + 1"]:
        rendered = unparse(parse(source).node)
        assert parse(rendered).refs == parse(source).refs


def test_literals_parse_to_python_values() -> None:
    assert parse("null").node == Literal(None)
    assert parse("true").node == Literal(True)
    assert parse("1_000").node == Literal(1000)
    assert parse("1e3").node == Literal(1000.0)


def test_a_ref_is_its_own_node() -> None:
    assert parse("@orders").node == Ref("orders")


def test_comments_are_ignored() -> None:
    assert parse("1 + 2  # add them").node == parse("1 + 2").node
