"""The IR and its two surfaces: JSON and SCLPLL v2."""

from __future__ import annotations

import json

import pytest

from sclpl.errors import ValidationError
from sclpl.run import compile_json
from sclpl.run.ir import HttpConfig, WorkflowDoc
from sclpl.run.sclpll import emit, parse

SOURCE = """
@workflow orders "Fetch and shape orders"

@var base = "https://api.test"
@var page_size = 100

@input customers:csv
@output report:xlsx?

@limits concurrency=8 timeout=15

@rule healthy = @fetch.status == 200

@mode partial "Only the fetch"
  include fetch
  limit max_pages=1

@mode full all

@step fetch
  get {{base}}/orders
  header Authorization: Bearer {{token}}
  query limit={{page_size}} active=true
  paginate cursor cursor_path=next param=cursor max_pages=40
  retry 3 base_delay=1
  tag api
  assert healthy

@step total <- fetch
  let count(@fetch.body)
"""


@pytest.fixture
def doc() -> WorkflowDoc:
    return parse(SOURCE, origin="test.sclpll")


# -- the model -------------------------------------------------------------------


def test_a_typo_in_a_field_name_is_refused() -> None:
    """A setting that silently does nothing is the failure worth being strict about."""
    with pytest.raises(ValidationError) as caught:
        compile_json.from_dict({"name": "x", "stpes": []})
    assert "unknown field" in str(caught.value)


def test_a_near_miss_field_name_suggests() -> None:
    with pytest.raises(ValidationError) as caught:
        compile_json.from_dict({"name": "x", "step": []})
    assert "did you mean 'steps'?" in str(caught.value)


def test_a_default_mode_that_is_not_declared_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        compile_json.from_dict({"name": "x", "default_mode": "nope"})
    assert "not a declared mode" in str(caught.value)


def test_a_config_that_does_not_match_its_kind_is_refused() -> None:
    with pytest.raises(ValidationError):
        compile_json.from_dict(
            {"name": "x", "steps": [{"id": "a", "kind": "http", "config": {"name": "f"}}]}
        )


def test_duplicate_step_ids_are_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        compile_json.from_dict(
            {
                "name": "x",
                "steps": [
                    {"id": "a", "kind": "let", "config": {"expr": "1"}},
                    {"id": "a", "kind": "let", "config": {"expr": "2"}},
                ],
            }
        )
    assert "duplicate step id" in str(caught.value)


def test_a_bad_step_id_is_refused() -> None:
    with pytest.raises(ValidationError):
        compile_json.from_dict(
            {"name": "x", "steps": [{"id": "9lives", "kind": "let", "config": {"expr": "1"}}]}
        )


def test_nested_steps_are_reachable(doc: WorkflowDoc) -> None:
    nested = compile_json.from_dict(
        {
            "name": "x",
            "steps": [
                {
                    "id": "loop",
                    "kind": "foreach",
                    "config": {
                        "over": "@rows",
                        "body": [{"id": "inner", "kind": "let", "config": {"expr": "1"}}],
                    },
                }
            ],
        }
    )
    assert nested.step("inner") is not None
    assert [step.id for step in nested.all_steps()] == ["loop", "inner"]
    del doc


def test_canonical_omits_defaults(doc: WorkflowDoc) -> None:
    """What makes `fmt` stable: an unset field is absent, not written as its default."""
    canonical = doc.canonical()
    assert "cache" not in canonical["steps"][0]
    assert canonical["steps"][0]["kind"] == "http"


# -- the SCLPLL surface ----------------------------------------------------------


def test_directives_parse(doc: WorkflowDoc) -> None:
    assert doc.name == "orders"
    assert doc.description == "Fetch and shape orders"
    assert doc.vars == {"base": "https://api.test", "page_size": 100}
    assert doc.limits.concurrency == 8
    assert doc.limits.timeout == 15
    assert doc.rules == {"healthy": "@fetch.status == 200"}


def test_ports_parse(doc: WorkflowDoc) -> None:
    assert doc.inputs[0].name == "customers"
    assert doc.inputs[0].format == "csv"
    assert doc.inputs[0].required is True
    assert doc.outputs[0].format == "xlsx"
    assert doc.outputs[0].required is False


def test_a_quoted_string_after_a_mode_name_is_its_description(doc: WorkflowDoc) -> None:
    """Treating it as a selector would silently select nothing."""
    assert doc.modes["partial"].description == "Only the fetch"
    assert doc.modes["partial"].include == ["fetch"]


def test_a_request_step_parses(doc: WorkflowDoc) -> None:
    step = doc.step("fetch")
    assert step is not None
    config = step.config
    assert isinstance(config, HttpConfig)
    assert config.method == "GET"
    assert config.url == "{{base}}/orders"
    assert config.headers["Authorization"] == "Bearer {{token}}"
    assert config.query == {"limit": "{{page_size}}", "active": True}
    assert config.paginate is not None
    assert config.paginate.max_pages == 40
    assert step.retry.max == 3
    assert step.tags == ["api"]
    assert step.assert_ == "healthy"


def test_declared_dependencies_parse(doc: WorkflowDoc) -> None:
    step = doc.step("total")
    assert step is not None
    assert step.needs == ["fetch"]


def test_values_keep_their_type_through_the_parser(doc: WorkflowDoc) -> None:
    """`page_size = 100` is the number, not the string."""
    assert doc.vars["page_size"] == 100
    assert isinstance(doc.vars["page_size"], int)
    assert doc.step("fetch").config.query["active"] is True  # type: ignore[union-attr]


def test_a_missing_workflow_directive_says_so() -> None:
    with pytest.raises(ValidationError) as caught:
        parse("@step a\n  let 1\n")
    assert "no @workflow" in str(caught.value)


def test_an_unknown_directive_suggests() -> None:
    with pytest.raises(ValidationError) as caught:
        parse("@workflow x\n@inputs a\n")
    assert "did you mean 'input'?" in str(caught.value)


def test_dedenting_to_a_column_nobody_opened_is_refused() -> None:
    """A dedent landing between two open blocks is a guess we refuse to make."""
    with pytest.raises(ValidationError) as caught:
        parse("@workflow x\n@step a\n  foreach r in @xs\n      let 1\n    let 2\n")
    assert "does not line up" in str(caught.value)


def test_mixing_tabs_and_spaces_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        parse("@workflow x\n@step a\n  let 1\n@step b\n\tlet 2\n")
    assert "tabs and spaces" in str(caught.value)


def test_an_empty_step_body_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        parse("@workflow x\n@step a\n")
    assert "empty body" in str(caught.value)


def test_an_unknown_clause_suggests() -> None:
    with pytest.raises(ValidationError) as caught:
        parse("@workflow x\n@step a\n  let 1\n  tags api\n")
    assert "did you mean 'tag'?" in str(caught.value)


def test_comments_and_blank_lines_are_ignored() -> None:
    doc = parse("@workflow x\n\n# a comment\n@step a\n  # another\n  let 1\n")
    assert len(doc.steps) == 1


# -- round-tripping --------------------------------------------------------------


def test_sclpll_round_trips_byte_identically(doc: WorkflowDoc) -> None:
    """The property that keeps the two surfaces from becoming two dialects."""
    once = emit(doc)
    twice = emit(parse(once, origin="round2"))
    assert once == twice


def test_the_ir_survives_a_sclpll_round_trip(doc: WorkflowDoc) -> None:
    assert parse(emit(doc)).canonical() == doc.canonical()


def test_json_round_trips(doc: WorkflowDoc) -> None:
    once = compile_json.dumps(doc)
    twice = compile_json.dumps(compile_json.loads(once))
    assert once == twice


def test_the_ir_survives_a_json_round_trip(doc: WorkflowDoc) -> None:
    assert compile_json.loads(compile_json.dumps(doc)).canonical() == doc.canonical()


def test_converting_between_surfaces_is_lossless(doc: WorkflowDoc) -> None:
    """SCLPLL -> JSON -> SCLPLL keeps everything."""
    as_json = compile_json.dumps(doc)
    back = compile_json.loads(as_json)
    assert emit(back) == emit(doc)


def test_a_minimal_workflow_round_trips() -> None:
    doc = parse("@workflow tiny\n\n@step a\n  let 1\n")
    assert emit(parse(emit(doc))) == emit(doc)


# -- JSON diagnostics ------------------------------------------------------------


def test_malformed_json_says_where() -> None:
    with pytest.raises(ValidationError) as caught:
        compile_json.loads('{"name": "x",}')
    message = str(caught.value)
    assert "not valid JSON" in message
    assert "trailing comma" in message


def test_json_has_no_comments_is_mentioned() -> None:
    with pytest.raises(ValidationError) as caught:
        compile_json.loads('{\n  // a comment\n  "name": "x"\n}')
    assert "SCLPLL has both" in str(caught.value)


def test_a_top_level_array_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        compile_json.loads("[]")
    assert "must be an object" in str(caught.value)


def test_json_output_is_valid_json(doc: WorkflowDoc) -> None:
    assert json.loads(compile_json.dumps(doc))["name"] == "orders"


# -- output ports, JSON arguments, and `let` -------------------------------------


def test_a_step_can_name_the_output_port_it_writes() -> None:
    doc = parse("@workflow w\n\n@output report:csv\n\n@step save -> report\n  save_csv @a\n")
    assert doc.steps[0].writes == "report"


def test_the_written_port_survives_a_round_trip() -> None:
    source = "@workflow w\n\n@output report:csv\n\n@step save -> report\n  save_csv @a\n"
    assert parse(emit(parse(source))).steps[0].writes == "report"


def test_dependencies_and_the_written_port_coexist() -> None:
    doc = parse(
        "@workflow w\n\n@output r:csv\n\n@step b <- a -> r\n  save_csv @a\n@step a\n  let 1\n"
    )
    step = doc.step("b")
    assert step is not None
    assert step.needs == ["a"]
    assert step.writes == "r"


def test_naming_two_output_ports_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        parse("@workflow w\n\n@step save -> one two\n  save_csv @a\n")
    assert "exactly one output port" in str(caught.value)


def test_a_json_object_argument_stays_one_argument() -> None:
    """`rename @p {"a": "b"}` is two arguments; splitting on the space loses the map."""
    doc = parse('@workflow w\n\n@step r\n  rename @p {"a": "b"}\n')
    assert doc.steps[0].config.args == ["@p", {"a": "b"}]  # type: ignore[union-attr]


def test_a_json_list_argument_stays_one_argument() -> None:
    doc = parse("@workflow w\n\n@step s\n  select @p [1, 2]\n")
    assert doc.steps[0].config.args == ["@p", [1, 2]]  # type: ignore[union-attr]


def test_an_interpolation_is_still_opaque_to_the_splitter() -> None:
    doc = parse("@workflow w\n\n@step s\n  get https://x/{{ @a.id }}\n")
    assert doc.steps[0].config.url == "https://x/{{ @a.id }}"  # type: ignore[union-attr]


def test_a_let_keeps_a_keyword_argument_containing_an_equals() -> None:
    """Splitting on the first `=` used to take `by=` out of the expression."""
    doc = parse('@workflow w\n\n@step total\n  let sum(@rows, by="price")\n')
    assert doc.steps[0].config.expr == 'sum(@rows, by="price")'  # type: ignore[union-attr]


def test_a_let_keeps_a_comparison() -> None:
    doc = parse("@workflow w\n\n@step ok\n  let count(@rows) == 3\n")
    assert doc.steps[0].config.expr == "count(@rows) == 3"  # type: ignore[union-attr]


def test_a_let_still_drops_a_leading_name() -> None:
    doc = parse("@workflow w\n\n@step total\n  let total = sum(@rows)\n")
    assert doc.steps[0].config.expr == "sum(@rows)"  # type: ignore[union-attr]


def test_a_named_let_may_still_compare() -> None:
    doc = parse("@workflow w\n\n@step ok\n  let ok = @a.status == 200\n")
    assert doc.steps[0].config.expr == "@a.status == 200"  # type: ignore[union-attr]
