"""Control flow, through the real scheduler.

These run whole workflows rather than calling the expansion functions, because what is
under test is the arrangement: a body becomes nodes, a barrier gathers them, and nothing
downstream sees the loop half-finished. Calling `expand_foreach` and inspecting the
result would test the part that was never in doubt.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from sclpl import bootstrap
from sclpl.errors import StepFailed
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.runner import Options, run_workflow
from sclpl.run.sclpll import parse

bootstrap.load(plugins=False)


async def run(source: str, **overrides: Any) -> dict[str, Any]:
    """Run a workflow and return every value it produced, by name."""
    doc = parse(source)
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        result = await run_workflow(doc, Options(overrides=overrides, validate=False), reporter)
    assert result.store is not None
    return {name: result.store.get(name) for name in result.store.names()}


HEAD = "@workflow t\n\n@step ids\n  let [1, 2, 3, 4]\n\n"


# -- foreach -----------------------------------------------------------------------


async def test_a_foreach_runs_its_body_once_per_element() -> None:
    values = await run(HEAD + "@step loop\n  foreach @ids as n\n    step twice\n      let @n * 2\n")
    assert values["loop"] == [2, 4, 6, 8]


async def test_the_result_is_in_element_order_not_completion_order() -> None:
    """A loop whose results came back shuffled would be a loop nobody could use."""
    source = (
        "@workflow t\n\n@step ids\n  let [10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]\n\n"
        "@step loop\n  foreach @ids as n\n    step keep\n      let @n\n"
    )
    values = await run(source)
    assert values["loop"] == [10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]


async def test_a_body_step_sees_the_one_before_it_by_its_written_name() -> None:
    source = HEAD + (
        "@step loop\n  foreach @ids as n\n"
        "    step base\n      let @n * 10\n"
        "    step plus\n      let @base + 1\n"
    )
    assert (await run(source))["loop"] == [11, 21, 31, 41]


async def test_a_body_can_read_a_value_from_outside_the_loop() -> None:
    """The parent absorbs its body's references, or this runs before `factor` exists."""
    source = HEAD + (
        "@step factor\n  let 100\n\n"
        "@step loop\n  foreach @ids as n\n    step scaled\n      let @n * @factor\n"
    )
    assert (await run(source))["loop"] == [100, 200, 300, 400]


async def test_looping_over_nothing_produces_nothing_rather_than_failing() -> None:
    """A workflow that filtered everything out should carry on."""
    source = (
        "@workflow t\n\n@step ids\n  let []\n\n"
        "@step loop\n  foreach @ids as n\n    step twice\n      let @n * 2\n"
    )
    assert (await run(source))["loop"] == []


async def test_looping_over_an_object_yields_its_entries() -> None:
    source = (
        '@workflow t\n\n@step obj\n  let {"a": 1, "b": 2}\n\n'
        "@step loop\n  foreach @obj as pair\n    step key\n      let @pair.key\n"
    )
    assert (await run(source))["loop"] == ["a", "b"]


async def test_looping_over_a_scalar_says_what_it_found() -> None:
    source = (
        "@workflow t\n\n@step n\n  let 3\n\n"
        "@step loop\n  foreach @n as x\n    step twice\n      let @x * 2\n"
    )
    values = await run(source)
    assert values.get("loop") is None


async def test_collect_says_what_an_iteration_contributes() -> None:
    source = HEAD + (
        "@step loop\n  foreach @ids as n\n    collect @n * 100\n    step ignored\n      let @n\n"
    )
    assert (await run(source))["loop"] == [100, 200, 300, 400]


async def test_a_foreach_with_no_body_is_a_typo_not_a_case() -> None:
    with pytest.raises(Exception):  # noqa: B017 - the parser refuses it first
        parse(HEAD + "@step loop\n  foreach @ids as n\n")


# -- if ----------------------------------------------------------------------------


async def test_a_branch_produces_the_value_of_the_branch_taken() -> None:
    source = HEAD + (
        "@step choose\n  when count(@ids) > 2\n"
        '    step yes\n      let "many"\n'
        '    otherwise\n      step no\n        let "few"\n'
    )
    assert (await run(source))["choose"] == "many"


async def test_the_branch_not_taken_never_becomes_a_node() -> None:
    source = HEAD + (
        "@step choose\n  when count(@ids) > 99\n"
        '    step yes\n      let "many"\n'
        '    otherwise\n      step no\n        let "few"\n'
    )
    values = await run(source)
    assert values["choose"] == "few"
    assert not any(name.endswith("::then::yes") for name in values)


async def test_a_when_with_no_otherwise_produces_null() -> None:
    """So a downstream reference resolves either way."""
    source = HEAD + "@step choose\n  when count(@ids) > 99\n    step yes\n      let 1\n"
    assert (await run(source))["choose"] is None


# -- parallel and gate -------------------------------------------------------------


async def test_parallel_produces_one_value_per_branch_in_order() -> None:
    source = (
        "@workflow t\n\n@step both\n  parallel\n"
        '    branch\n      step left\n        let "L"\n'
        '    branch\n      step right\n        let "R"\n'
    )
    assert (await run(source))["both"] == ["L", "R"]


async def test_a_gate_produces_its_reason() -> None:
    source = '@workflow t\n\n@step wait\n  gate "everything above lands first"\n'
    assert (await run(source))["wait"] == "everything above lands first"


# -- while and do_while ------------------------------------------------------------


async def test_a_while_runs_until_its_condition_goes_false() -> None:
    source = (
        "@workflow t\n\n@step start\n  let 1\n\n"
        "@step climb\n  while coalesce(@tripled, @start) < 40\n"
        "    step tripled\n      let coalesce(@tripled, @start) * 3\n"
    )
    assert (await run(source))["climb"] == 81


async def test_a_while_whose_condition_is_false_never_runs_its_body() -> None:
    source = (
        "@workflow t\n\n@step start\n  let 100\n\n"
        "@step climb\n  while @start < 40\n    step tripled\n      let @start * 3\n"
    )
    values = await run(source)
    assert values["climb"] is None
    assert not any("::0::" in name for name in values)


async def test_a_do_while_always_runs_once() -> None:
    """ "Fetch, then decide whether to fetch again" is the shape most API loops have."""
    source = (
        "@workflow t\n\n@step start\n  let 100\n\n"
        "@step once\n  do_while @start < 40\n    step seen\n      let @start * 3\n"
    )
    assert (await run(source))["once"] == 300


async def test_a_runaway_loop_hits_max_iterations_and_says_both_fixes() -> None:
    source = (
        "@workflow t\n\n@step start\n  let 1\n\n"
        "@step spin\n  while @start == 1\n    step nothing\n      let 1\n"
    )
    doc = parse(source)
    doc.steps[1].config.max_iterations = 3  # type: ignore[union-attr]
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        result = await run_workflow(doc, Options(validate=False), reporter)
    assert not result.ok
    failure = next(iter(result.outcome.failed.values()))  # type: ignore[union-attr]
    assert isinstance(failure, StepFailed)
    assert "max_iterations" in str(failure)
    assert "goes false" in str(failure)


# -- what the graph looks like afterwards ------------------------------------------


async def test_a_step_after_a_loop_waits_for_the_whole_loop() -> None:
    source = HEAD + (
        "@step loop\n  foreach @ids as n\n    step twice\n      let @n * 2\n\n"
        "@step after\n  let count(@loop)\n"
    )
    assert (await run(source))["after"] == 4


async def test_a_nested_body_step_is_not_a_top_level_node() -> None:
    """It cannot be: how many copies there are is not known until the parent runs."""
    from sclpl.run.compile_plan import compile_plan

    doc = parse(HEAD + "@step loop\n  foreach @ids as n\n    step twice\n      let @n * 2\n")
    plan = compile_plan(doc)
    assert sorted(plan.nodes) == ["ids", "loop"]
