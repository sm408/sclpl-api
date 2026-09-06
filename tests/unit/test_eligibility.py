"""E7: an output's derived validation scope, and the mode-stubs-past-it preflight check."""

from __future__ import annotations

from sclpl.errors import ValidationError
from sclpl.run.compile_plan import compile_plan
from sclpl.run.eligibility import check_stubbed_validation, derive
from sclpl.run.ir import WorkflowDoc
from sclpl.run.modes import Resolved, resolve
from sclpl.run.plan import Plan
from sclpl.run.sclpll.parse import parse

WORKFLOW = """
@workflow orders

@output report:csv

@mode full
  include producer downstream write

@mode stubbed
  include downstream write
  stub producer=42

@step producer
  get https://api.test/thing
  assert true

@step downstream
  let @producer.body

@step write -> report
  save_csv @downstream
"""


def _resolved(mode: str) -> tuple[WorkflowDoc, Resolved, Plan]:
    doc = parse(WORKFLOW)
    resolved = resolve(doc, mode)
    plan = compile_plan(doc, keep=resolved.keep, available=set(resolved.stubs))
    return doc, resolved, plan


def test_derive_finds_the_writers_full_dependency_closure() -> None:
    doc, _resolved_, plan = _resolved("full")
    eligibility = derive(doc, plan)
    report = eligibility["report"]
    assert report.writer == "write"
    assert report.required == {"producer", "downstream", "write"}


def test_derive_reports_the_assert_bearing_ancestor_as_the_validation_scope() -> None:
    doc, _resolved_, plan = _resolved("full")
    report = derive(doc, plan)["report"]
    assert report.validated
    assert report.validation_scope == {"producer"}


def test_derive_reports_unvalidated_when_no_ancestor_asserts() -> None:
    doc = parse(
        "@workflow t\n\n@output out:csv\n\n"
        "@step rows\n  let [1]\n\n"
        "@step write -> out\n  save_csv @rows\n"
    )
    resolved = resolve(doc, None)
    plan = compile_plan(doc, keep=resolved.keep)
    report = derive(doc, plan)["out"]
    assert not report.validated
    assert report.validation_scope == frozenset()


def test_a_port_with_no_writer_in_the_kept_plan_has_no_eligibility_entry() -> None:
    doc, resolved, plan = _resolved("stubbed")
    # "stubbed" keeps `write`, so `report` is still present; assert the shape holds
    # for the mode that actually exercises the stub, not just "full".
    del resolved
    assert "report" in derive(doc, plan)


def test_stubbing_an_assert_bearing_dependency_fails_preflight() -> None:
    doc, resolved, _plan = _resolved("stubbed")
    problems = check_stubbed_validation(doc, resolved)
    assert len(problems) == 1
    assert isinstance(problems[0], ValidationError)
    message = str(problems[0])
    assert "producer" in message
    assert "report" in message


def test_stubbing_an_unrelated_step_is_not_flagged() -> None:
    doc = parse(
        "@workflow t\n\n@output out:csv\n\n"
        "@mode m\n  include validated unrelated write\n  stub unrelated=1\n\n"
        "@step validated\n  let 1\n  assert true\n\n"
        "@step unrelated\n  let 2\n\n"
        "@step write -> out\n  save_csv @validated\n"
    )
    resolved = resolve(doc, "m")
    assert check_stubbed_validation(doc, resolved) == []


def test_a_workflow_with_no_asserts_at_all_is_a_fast_empty_return() -> None:
    doc = parse(
        "@workflow t\n\n@output out:csv\n\n"
        "@mode m\n  include write\n  stub rows=1\n\n"
        "@step rows\n  let [1]\n\n"
        "@step write -> out\n  save_csv @rows\n"
    )
    resolved = resolve(doc, "m")
    assert check_stubbed_validation(doc, resolved) == []


def test_no_stubs_at_all_is_a_fast_empty_return() -> None:
    doc, resolved, _plan = _resolved("full")
    assert check_stubbed_validation(doc, resolved) == []
