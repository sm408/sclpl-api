"""I1: parsing a curl command into data, then rendering a runnable workflow."""

from __future__ import annotations

import base64

import pytest

from sclpl import bootstrap
from sclpl.errors import ValidationError
from sclpl.importers import curl
from sclpl.run.preflight import preflight
from sclpl.run.sclpll.parse import parse as parse_sclpll

bootstrap.load(plugins=False)


def test_parse_a_simple_get() -> None:
    parsed = curl.parse("curl https://api.example.com/status")
    assert parsed.method == "GET"
    assert parsed.url == "https://api.example.com/status"
    assert parsed.headers == {}
    assert parsed.auth is None


def test_parse_rejects_a_non_curl_command() -> None:
    with pytest.raises(ValidationError, match="not a curl command"):
        curl.parse("wget https://api.example.com/status")


def test_parse_extracts_query_from_the_url() -> None:
    parsed = curl.parse("curl 'https://api.example.com/orders?limit=10&status=open'")
    assert parsed.url == "https://api.example.com/orders"
    assert parsed.query == {"limit": "10", "status": "open"}


def test_parse_infers_post_from_data_without_explicit_method() -> None:
    parsed = curl.parse("curl https://api.example.com/orders -d '{\"a\":1}'")
    assert parsed.method == "POST"
    assert parsed.body == {"a": 1}
    assert parsed.body_kind == "json"


def test_get_flag_promotes_data_to_query_instead_of_body() -> None:
    parsed = curl.parse("curl -G https://api.example.com/orders -d 'limit=5'")
    assert parsed.method == "GET"
    assert parsed.body is None
    assert parsed.query == {"limit": "5"}


def test_explicit_method_is_respected_over_data_inference() -> None:
    parsed = curl.parse("curl -X PUT https://api.example.com/orders/1 -d '{\"a\":1}'")
    assert parsed.method == "PUT"


def test_repeated_headers_with_different_names_are_all_kept() -> None:
    parsed = curl.parse(
        "curl https://api.example.com/x -H 'Accept: application/json' -H 'X-Trace: abc'"
    )
    assert parsed.headers == {"Accept": "application/json", "X-Trace": "abc"}


def test_form_fields_are_modeled_as_an_object_body() -> None:
    parsed = curl.parse("curl https://api.example.com/x -F 'name=widget' -F 'qty=3'")
    assert parsed.body_kind == "form"
    assert parsed.body == {"name": "widget", "qty": "3"}
    assert parsed.method == "POST"


def test_unsupported_flags_are_reported_not_raised() -> None:
    parsed = curl.parse("curl https://api.example.com/x -o out.json -k")
    assert any("-o" in item for item in parsed.unsupported)
    assert any("-k" in item for item in parsed.unsupported)


def test_bearer_token_is_extracted_from_the_authorization_header() -> None:
    parsed = curl.parse("curl https://api.example.com/x -H 'Authorization: Bearer sekret-token'")
    assert "Authorization" not in parsed.headers
    assert parsed.auth is not None
    assert parsed.auth.kind == "bearer"
    assert parsed.auth.secret_value == "sekret-token"


_BASIC_TOKEN = base64.b64encode(b"alice:hunter2").decode()


@pytest.mark.parametrize(
    ("command", "kind", "attrs"),
    [
        (
            "curl https://api.example.com/x -u alice:hunter2",
            "basic",
            {"username": "alice", "secret_value": "hunter2"},
        ),
        (
            f"curl https://api.example.com/x -H 'Authorization: Basic {_BASIC_TOKEN}'",
            "basic",
            {"username": "alice", "secret_value": "hunter2"},
        ),
        (
            "curl https://api.example.com/x -H 'Authorization: Token xyz'",
            "header",
            {"secret_value": "xyz", "prefix": "Token "},
        ),
    ],
)
def test_auth_is_extracted_by_kind(command: str, kind: str, attrs: dict[str, str]) -> None:
    parsed = curl.parse(command)
    assert parsed.auth is not None
    assert parsed.auth.kind == kind
    for field, value in attrs.items():
        assert getattr(parsed.auth, field) == value


@pytest.mark.parametrize(
    "command",
    [
        "curl https://api.example.com/status",
        "curl -X POST https://api.example.com/orders"
        " -H 'Content-Type: application/json' -d '{\"a\":1}'",
        "curl 'https://api.example.com/orders?limit=10&status=open'",
        "curl https://api.example.com/x -H 'Authorization: Bearer sekret'",
        "curl https://api.example.com/x -u alice:hunter2",
        "curl https://api.example.com/x -F 'name=widget'",
    ],
)
def test_rendered_workflow_passes_real_preflight(command: str) -> None:
    """The acceptance bar: the generated text must be a workflow sclpl itself accepts."""
    parsed = curl.parse(command)
    result = curl.render(parsed, name="imported")
    doc = parse_sclpll(result.workflow)
    report = preflight(doc, check_files=False, require_ports=False)
    assert report.ok, report.problems[0].diagnostic.message if report.problems else "unknown"


def test_auth_manifest_never_contains_the_secret_value() -> None:
    parsed = curl.parse("curl https://api.example.com/x -H 'Authorization: Bearer sekret-token'")
    result = curl.render(parsed, name="imported")
    assert result.auth_manifest is not None
    assert "sekret-token" not in result.auth_manifest
    assert result.extracted_secret == ("IMPORTED_BEARER_TOKEN", "sekret-token")


def test_rendered_workflow_never_contains_the_secret_value() -> None:
    parsed = curl.parse("curl https://api.example.com/x -u alice:hunter2")
    result = curl.render(parsed, name="imported")
    assert "hunter2" not in result.workflow
