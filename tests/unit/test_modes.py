"""Modes and ports: selection, pruning, the closure check, and binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl.run.errors import ValidationError
from sclpl.run.ir import WorkflowDoc
from sclpl.run.modes import resolve
from sclpl.run.ports import bind, check_readable
from sclpl.run.sclpll import parse

SOURCE = """
@workflow orders

@input customers:csv
@output report:csv

@mode partial
  include fetch_* shape_*

@mode tagged
  include tag:api

@mode without_extras all
  exclude enrich_*

@mode narrow
  extends partial
  exclude shape_extra

@step fetch_orders
  get https://api.test/orders
  tag api

@step fetch_extra
  get https://other.test/extra
  tag api

@step shape_orders
  let @fetch_orders.body

@step shape_extra
  let @fetch_extra.body

@step enrich_totals
  let count(@shape_orders)

@step enrich_names
  let @shape_extra
"""


@pytest.fixture
def doc() -> WorkflowDoc:
    return parse(SOURCE)


# -- selection -------------------------------------------------------------------


def test_no_mode_keeps_everything(doc: WorkflowDoc) -> None:
    resolved = resolve(doc, None)
    assert len(resolved.keep) == 6
    assert resolved.is_full


def test_a_glob_selects_a_family(doc: WorkflowDoc) -> None:
    resolved = resolve(doc, "partial")
    assert resolved.keep == {"fetch_orders", "fetch_extra", "shape_orders", "shape_extra"}
    assert resolved.pruned == {"enrich_totals", "enrich_names"}


def test_a_tag_selector_works(doc: WorkflowDoc) -> None:
    resolved = resolve(doc, "tagged")
    assert resolved.keep == {"fetch_orders", "fetch_extra"}


def test_all_then_exclude(doc: WorkflowDoc) -> None:
    resolved = resolve(doc, "without_extras")
    assert "enrich_totals" not in resolved.keep
    assert "fetch_orders" in resolved.keep


def test_extends_inherits_and_narrows(doc: WorkflowDoc) -> None:
    resolved = resolve(doc, "narrow")
    assert "shape_orders" in resolved.keep
    assert "shape_extra" not in resolved.keep


def test_an_unknown_mode_suggests(doc: WorkflowDoc) -> None:
    with pytest.raises(ValidationError) as caught:
        resolve(doc, "partal")
    assert "did you mean 'partial'?" in str(caught.value)


def test_a_selector_that_matches_nothing_is_an_error() -> None:
    """Treating it as an empty selection would silently run the wrong subset."""
    doc = parse("@workflow x\n@mode m\n  include nosuch*\n\n@step a\n  let 1\n")
    with pytest.raises(ValidationError) as caught:
        resolve(doc, "m")
    assert "matches no step" in str(caught.value)


def test_a_mistyped_selector_suggests() -> None:
    doc = parse("@workflow x\n@mode m\n  include fetsh\n\n@step fetch\n  let 1\n")
    with pytest.raises(ValidationError) as caught:
        resolve(doc, "m")
    assert "did you mean 'fetch'?" in str(caught.value)


def test_a_mode_extends_loop_is_refused() -> None:
    doc = parse("@workflow x\n@mode a\n  extends b\n\n@mode b\n  extends a\n\n@step s\n  let 1\n")
    with pytest.raises(ValidationError) as caught:
        resolve(doc, "a")
    assert "loop" in str(caught.value)


# -- the closure check -----------------------------------------------------------


CLOSURE = """
@workflow orders

@mode broken
  include downstream

@mode fine
  include producer downstream

@mode stubbed
  include downstream
  stub producer=42

@step producer
  get https://api.test/thing

@step downstream
  let @producer.body
"""


def test_pruning_a_needed_producer_fails_at_validate_time() -> None:
    """The M4 exit criterion's second half."""
    doc = parse(CLOSURE)
    with pytest.raises(ValidationError) as caught:
        resolve(doc, "broken")
    message = str(caught.value)
    assert "prunes 'producer'" in message
    assert "still reads it" in message


def test_the_closure_error_names_all_three_remedies() -> None:
    doc = parse(CLOSURE)
    with pytest.raises(ValidationError) as caught:
        resolve(doc, "broken")
    message = str(caught.value)
    assert "include list" in message
    assert "input port" in message
    assert "stub" in message


def test_keeping_the_producer_is_fine() -> None:
    assert resolve(parse(CLOSURE), "fine").keep == {"producer", "downstream"}


def test_a_stub_satisfies_the_closure_check() -> None:
    resolved = resolve(parse(CLOSURE), "stubbed")
    assert resolved.keep == {"downstream"}
    assert resolved.stubs == {"producer": 42}


def test_an_input_port_satisfies_the_closure_check() -> None:
    doc = parse(
        "@workflow x\n@input producer\n\n@mode m\n  include downstream\n\n"
        "@step producer\n  get https://api.test/a\n\n@step downstream\n  let @producer\n"
    )
    assert resolve(doc, "m", available={"producer"}).keep == {"downstream"}


# -- ports -----------------------------------------------------------------------


PORTS = """
@workflow orders

@input customers:csv
@input extra:json?
@output report:csv

@step a
  let 1
"""


def test_positional_binding_is_inputs_then_outputs() -> None:
    doc = parse(PORTS)
    bound = bind(doc, positional=["in.csv", "extra.json", "out.csv"])
    assert bound.inputs["customers"].path == Path("in.csv")
    assert bound.inputs["extra"].path == Path("extra.json")
    assert bound.outputs["report"].path == Path("out.csv")


def test_named_binding_beats_positional() -> None:
    doc = parse(PORTS)
    bound = bind(doc, named_in={"customers": "named.csv"}, positional=["out.csv"])
    assert bound.inputs["customers"].path == Path("named.csv")
    # The positional went to the required output, not the optional input.
    assert bound.outputs["report"].path == Path("out.csv")
    assert not bound.inputs["extra"].bound


def test_required_ports_are_filled_before_optional_ones() -> None:
    """`orders in.csv out.csv` means the input and the output, not the optional extra."""
    doc = parse(PORTS)
    bound = bind(doc, positional=["in.csv", "out.csv"])
    assert bound.inputs["customers"].path == Path("in.csv")
    assert bound.outputs["report"].path == Path("out.csv")
    assert not bound.inputs["extra"].bound


def test_naming_a_port_frees_a_positional_for_the_optional_one() -> None:
    doc = parse(PORTS)
    bound = bind(doc, named_out={"report": "r.csv"}, positional=["in.csv", "extra.json"])
    assert bound.inputs["customers"].path == Path("in.csv")
    assert bound.inputs["extra"].path == Path("extra.json")
    assert bound.outputs["report"].path == Path("r.csv")


def test_a_missing_required_port_lists_the_usage() -> None:
    doc = parse(PORTS)
    with pytest.raises(ValidationError) as caught:
        bind(doc, positional=[])
    message = str(caught.value)
    assert "customers" in message
    assert "usage: sclpl orders" in message


def test_extra_arguments_are_refused() -> None:
    doc = parse(PORTS)
    with pytest.raises(ValidationError) as caught:
        bind(doc, positional=["a", "b", "c", "d"])
    assert "extra argument" in str(caught.value)


def test_an_unknown_port_name_suggests() -> None:
    doc = parse(PORTS)
    with pytest.raises(ValidationError) as caught:
        bind(doc, named_in={"customer": "x.csv"}, positional=["a", "b"])
    assert "did you mean 'customers'?" in str(caught.value)


def test_stdio_binds_to_a_dash() -> None:
    doc = parse(PORTS)
    bound = bind(doc, positional=["-", "-", "-"])
    assert bound.inputs["customers"].is_stdio
    assert bound.outputs["report"].is_stdio


def test_the_format_comes_from_the_extension() -> None:
    doc = parse("@workflow x\n@input data\n@output out\n\n@step a\n  let 1\n")
    bound = bind(doc, positional=["rows.parquet", "result.xlsx"])
    assert bound.inputs["data"].format == "parquet"
    assert bound.outputs["out"].format == "xlsx"


def test_an_explicit_format_overrides_the_extension() -> None:
    doc = parse("@workflow x\n@input data\n@output out\n\n@step a\n  let 1\n")
    bound = bind(doc, positional=["rows.txt:csv", "out.txt:json"])
    assert bound.inputs["data"].format == "csv"


def test_a_declared_default_is_used_when_nothing_is_given() -> None:
    doc = parse('@workflow x\n@input data default="rows.csv"\n\n@step a\n  let 1\n')
    assert bind(doc).inputs["data"].path == Path("rows.csv")


def test_a_missing_input_file_is_reported(tmp_path: Path) -> None:
    doc = parse("@workflow x\n@input data\n\n@step a\n  let 1\n")
    bound = bind(doc, positional=[str(tmp_path / "nope.csv")])
    with pytest.raises(ValidationError) as caught:
        check_readable(bound)
    assert "does not exist" in str(caught.value)


def test_a_directory_given_as_an_input_is_reported(tmp_path: Path) -> None:
    doc = parse("@workflow x\n@input data\n\n@step a\n  let 1\n")
    bound = bind(doc, positional=[str(tmp_path)])
    with pytest.raises(ValidationError) as caught:
        check_readable(bound)
    assert "is a directory" in str(caught.value)


def test_a_glob_binds_a_sorted_list(tmp_path: Path) -> None:
    for name in ("c.csv", "a.csv", "b.csv"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    doc = parse("@workflow x\n@input data\n\n@step a\n  let 1\n")
    bound = bind(doc, positional=[str(tmp_path / "*.csv")])
    assert [path.name for path in bound.inputs["data"].paths] == ["a.csv", "b.csv", "c.csv"]


def test_a_glob_that_matches_nothing_is_reported(tmp_path: Path) -> None:
    doc = parse("@workflow x\n@input data\n\n@step a\n  let 1\n")
    with pytest.raises(ValidationError) as caught:
        bind(doc, positional=[str(tmp_path / "*.nope")])
    assert "matched no files" in str(caught.value)
