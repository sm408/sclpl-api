"""I5: rendering test outcomes as JUnit XML, JSON, and HTML."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sclpl.testing.report import CaseResult, to_html, to_json, to_junit_xml

_CASES = [
    CaseResult("one", "tests/one.test.toml", True, 0.125),
    CaseResult("two", "tests/two.test.toml", False, 0.5, "exit 1"),
]


def test_json_report_has_a_stable_schema_and_correct_summary() -> None:
    payload = json.loads(to_json(_CASES))
    assert payload["schema"] == 1
    assert payload["summary"] == {"total": 2, "passed": 1, "failed": 1}
    assert [case["name"] for case in payload["cases"]] == ["one", "two"]
    assert payload["cases"][1]["message"] == "exit 1"


def test_json_report_contains_no_unexpected_keys() -> None:
    payload = json.loads(to_json(_CASES))
    case = payload["cases"][0]
    assert set(case) == {"name", "path", "passed", "duration_s", "message"}


def test_junit_xml_is_well_formed_and_counts_failures() -> None:
    root = ET.fromstring(to_junit_xml(_CASES, suite_name="demo"))
    assert root.tag == "testsuite"
    assert root.get("tests") == "2"
    assert root.get("failures") == "1"
    testcases = root.findall("testcase")
    assert len(testcases) == 2
    assert testcases[1].find("failure") is not None
    assert testcases[0].find("failure") is None


def test_junit_xml_escapes_special_characters_in_names_and_messages() -> None:
    cases = [CaseResult('a "quoted" <name>', "path", False, 0.0, "msg & <stuff>")]
    root = ET.fromstring(to_junit_xml(cases))
    testcase = root.find("testcase")
    failure = root.find("testcase/failure")
    assert testcase is not None and testcase.get("name") == 'a "quoted" <name>'
    assert failure is not None and failure.get("message") == "msg & <stuff>"


def test_html_report_contains_summary_and_rows() -> None:
    rendered = to_html(_CASES, suite_name="demo")
    assert "1/2 passed" in rendered
    assert "one" in rendered and "two" in rendered
    assert 'class="pass"' in rendered
    assert 'class="fail"' in rendered


def test_html_report_escapes_content() -> None:
    cases = [CaseResult("<script>alert(1)</script>", "path", False, 0.0, "<b>bad</b>")]
    rendered = to_html(cases)
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_empty_case_list_still_produces_valid_reports() -> None:
    assert json.loads(to_json([]))["summary"] == {"total": 0, "passed": 0, "failed": 0}
    root = ET.fromstring(to_junit_xml([]))
    assert root.get("tests") == "0"
    assert "0/0 passed" in to_html([])
