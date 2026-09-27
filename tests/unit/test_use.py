"""`use`: another workflow as a step, through the real preflight and scheduler."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from sclpl import bootstrap
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.ir import WorkflowDoc
from sclpl.run.preflight import preflight
from sclpl.run.runner import Options, Result, run_workflow
from sclpl.run.sclpll import parse
from sclpl.run.sclpll.emit import emit

bootstrap.load(plugins=False)

CHILD = """@workflow scale

@var factor = 10
@input numbers
@output total:json

@step fetch
  let @numbers

@step join
  let sum(@fetch) * factor

@step write -> total
  save_json @join
"""


def write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


async def run(path: Path, **options: Any) -> Result:
    doc = parse(path.read_text(encoding="utf-8"), origin=str(path))
    async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
        return await run_workflow(
            doc, Options(validate=False, record=False, origin=path, **options), reporter
        )


def values(result: Result) -> dict[str, Any]:
    assert result.store is not None
    return {name: result.store.get(name) for name in result.store.names()}


def check(path: Path) -> list[str]:
    doc = parse(path.read_text(encoding="utf-8"), origin=str(path))
    report = preflight(doc, check_files=False, require_ports=False, origin=path)
    return [problem.diagnostic.message for problem in report.problems]


async def test_a_parent_using_a_child_twice_gets_both_results(tmp_path: Path) -> None:
    write(tmp_path, "scale.sclpll", CHILD)
    parent = write(
        tmp_path,
        "parent.sclpll",
        "@workflow parent\n\n"
        "@step fetch\n  let 1000\n\n"
        "@step small\n  use scale.sclpll numbers=[1, 2]\n\n"
        "@step big\n  use scale.sclpll numbers=[1, 2] factor=100\n\n"
        "@step both\n  let [@small.total, @big.total, @fetch]\n",
    )
    result = await run(parent)
    assert result.exit_code == 0
    # The child's own `fetch` did not see, or clobber, the parent's.
    assert values(result)["both"] == [30, 300, 1000]
    # The child's steps ran as nodes of the parent's run, under decorated names.
    assert result.outcome is not None
    assert "small::use::join" in result.outcome.succeeded
    assert not (tmp_path / "total").exists()


async def test_arguments_are_resolved_in_the_parent_scope(tmp_path: Path) -> None:
    write(tmp_path, "scale.sclpll", CHILD)
    parent = write(
        tmp_path,
        "parent.sclpll",
        "@workflow parent\n\n@step nums\n  let [4, 5]\n\n"
        "@step scaled\n  use scale numbers=@nums factor=2\n",
    )
    assert values(await run(parent))["scaled"] == {"total": 18}


async def test_a_child_without_outputs_produces_its_last_step(tmp_path: Path) -> None:
    write(tmp_path, "plain.sclpll", "@workflow plain\n@var x = 1\n\n@step a\n  let x + 1\n")
    parent = write(tmp_path, "p.sclpll", "@workflow p\n\n@step one\n  use plain x=41\n")
    assert values(await run(parent))["one"] == 42


async def test_a_used_workflow_can_loop_and_use_another(tmp_path: Path) -> None:
    write(tmp_path, "scale.sclpll", CHILD)
    write(
        tmp_path,
        "middle.sclpll",
        "@workflow middle\n@input rows\n\n"
        "@step loop\n  foreach @rows as r\n    step twice\n      let @r * 2\n\n"
        "@step inner\n  use scale numbers=@loop factor=1\n\n"
        "@step answer\n  let @inner.total\n",
    )
    parent = write(tmp_path, "p.sclpll", "@workflow p\n\n@step m\n  use middle rows=[1, 2, 3]\n")
    assert values(await run(parent))["m"] == 12


async def test_a_use_inside_a_foreach_runs_once_per_element(tmp_path: Path) -> None:
    write(tmp_path, "scale.sclpll", CHILD)
    parent = write(
        tmp_path,
        "p.sclpll",
        "@workflow p\n\n@step ids\n  let [1, 2, 3]\n\n"
        "@step loop\n  foreach @ids as n\n    step one\n      use scale numbers=@ids factor=@n\n",
    )
    assert values(await run(parent))["loop"] == [{"total": 6}, {"total": 12}, {"total": 18}]


async def test_the_childs_mode_prunes_its_steps(tmp_path: Path) -> None:
    write(
        tmp_path,
        "moded.sclpll",
        "@workflow moded\n\n@mode quick\n  include a\n\n"
        "@step a\n  let 1\n\n@step b\n  let @a + 1\n",
    )
    parent = write(tmp_path, "p.sclpll", "@workflow p\n\n@step q\n  use moded mode=quick\n")
    result = await run(parent)
    assert values(result)["q"] == 1
    assert result.outcome is not None
    assert "q::use::b" not in result.outcome.started


def test_validation_names_the_step_that_misses_a_child_input(tmp_path: Path) -> None:
    write(tmp_path, "scale.sclpll", CHILD)
    parent = write(tmp_path, "p.sclpll", "@workflow p\n\n@step s\n  use scale factor=2\n")
    assert check(parent) == ["step 's' uses scale without its required input 'numbers'"]


def test_validation_names_the_step_that_passes_an_unknown_argument(tmp_path: Path) -> None:
    write(tmp_path, "scale.sclpll", CHILD)
    parent = write(tmp_path, "p.sclpll", "@workflow p\n\n@step s\n  use scale numbrs=[1]\n")
    [message] = check(parent)
    assert message.startswith("step 's' passes 'numbrs' to scale")


def test_validation_rejects_a_cycle_and_names_the_step(tmp_path: Path) -> None:
    a = write(tmp_path, "a.sclpll", "@workflow a\n\n@step to_b\n  use b\n")
    write(tmp_path, "b.sclpll", "@workflow b\n\n@step to_a\n  use a\n")
    [message] = check(a)
    assert message.startswith("step 'to_b' uses 'b': step 'to_a' uses 'a', which leads back")
    assert "a -> b -> a" in message


def test_validation_rejects_a_workflow_using_itself(tmp_path: Path) -> None:
    me = write(tmp_path, "me.sclpll", "@workflow me\n\n@step again\n  use me.sclpll\n")
    [message] = check(me)
    assert message == "step 'again' uses 'me.sclpll', which leads back to itself: me -> me"


def test_validation_reports_a_missing_workflow(tmp_path: Path) -> None:
    parent = write(tmp_path, "p.sclpll", "@workflow p\n\n@step s\n  use nowhere_at_all\n")
    [message] = check(parent)
    assert message.startswith("step 's' uses 'nowhere_at_all':")


def test_the_childs_mode_closure_check_is_reported(tmp_path: Path) -> None:
    write(
        tmp_path,
        "moded.sclpll",
        "@workflow moded\n\n@mode broken\n  include b\n\n"
        "@step a\n  let 1\n\n@step b\n  let @a + 1\n",
    )
    parent = write(tmp_path, "p.sclpll", "@workflow p\n\n@step q\n  use moded mode=broken\n")
    [message] = check(parent)
    assert message.startswith("step 'q' uses 'moded': moded: mode 'broken' prunes 'a'")


def test_a_pruned_use_step_is_not_resolved(tmp_path: Path) -> None:
    parent = write(
        tmp_path,
        "p.sclpll",
        "@workflow p\n\n@mode lite\n  exclude s\n\n@step a\n  let 1\n\n@step s\n  use missing\n",
    )
    doc = parse(parent.read_text(encoding="utf-8"))
    report = preflight(doc, mode="lite", check_files=False, require_ports=False, origin=parent)
    assert report.ok


@pytest.mark.parametrize(
    "line",
    [
        "use scale",
        "use scale numbers=@nums factor=2",
        'use "sub dir/scale.sclpll" mode=quick numbers=[1,2]',
    ],
)
def test_use_round_trips_through_fmt(line: str) -> None:
    doc = parse(f"@workflow p\n\n@step s\n  {line}\n")
    assert isinstance(doc, WorkflowDoc)
    assert f"  {line}" in emit(doc)
    assert parse(emit(doc)) == doc


def test_use_without_a_workflow_is_a_parse_error() -> None:
    from sclpl.errors import ValidationError

    with pytest.raises(ValidationError, match="use needs a workflow"):
        parse("@workflow p\n\n@step s\n  use numbers=[1]\n")
