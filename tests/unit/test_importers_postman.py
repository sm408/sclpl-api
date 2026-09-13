"""I3: turning one request of a local Postman v2.1 collection into a workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sclpl import bootstrap
from sclpl.errors import ValidationError
from sclpl.importers import postman
from sclpl.run.preflight import preflight
from sclpl.run.sclpll.parse import parse as parse_sclpll

bootstrap.load(plugins=False)

_COLLECTION: dict[str, object] = {
    "info": {
        "name": "Demo",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [{"key": "base_url", "value": "https://api.example.com"}],
    "item": [
        {
            "name": "Orders",
            "item": [
                {
                    "name": "List Orders",
                    "event": [
                        {"listen": "prerequest", "script": {"exec": ["console.log('evil')"]}},
                        {"listen": "test", "script": {"exec": ["pm.test('ok', () => {})"]}},
                    ],
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json"}],
                        "url": {
                            "raw": "{{base_url}}/orders?status=open",
                            "query": [{"key": "status", "value": "open"}],
                        },
                        "auth": {
                            "type": "bearer",
                            "bearer": [{"key": "token", "value": "sekret-token"}],
                        },
                    },
                },
                {
                    "name": "Create Order",
                    "request": {
                        "method": "POST",
                        "url": {"raw": "{{base_url}}/orders"},
                        "body": {"mode": "raw", "raw": '{"item": "widget"}'},
                    },
                },
            ],
        },
        {
            "name": "Basic Auth Request",
            "request": {
                "method": "GET",
                "url": {"raw": "{{base_url}}/secure"},
                "auth": {
                    "type": "basic",
                    "basic": [
                        {"key": "username", "value": "alice"},
                        {"key": "password", "value": "hunter2"},
                    ],
                },
            },
        },
        {
            "name": "Api Key Request",
            "request": {
                "method": "GET",
                "url": {"raw": "{{base_url}}/keyed"},
                "auth": {
                    "type": "apikey",
                    "apikey": [
                        {"key": "key", "value": "X-Api-Key"},
                        {"key": "value", "value": "abc123"},
                        {"key": "in", "value": "header"},
                    ],
                },
            },
        },
    ],
}


def _write(
    tmp_path: Path, data: dict[str, object] = _COLLECTION, name: str = "collection.json"
) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_rejects_an_unsupported_schema(tmp_path: Path) -> None:
    bad = {
        **_COLLECTION,
        "info": {"name": "x", "schema": "https://schema.getpostman.com/json/collection/v1.0.0/x"},
    }
    with pytest.raises(ValidationError, match="unsupported or missing"):
        postman.load(_write(tmp_path, bad))


def test_load_walks_nested_folders(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    names = {r.name for r in collection.requests}
    assert names == {
        "Orders/List Orders",
        "Orders/Create Order",
        "Basic Auth Request",
        "Api Key Request",
    }


def test_prerequest_and_test_scripts_are_reported_never_executed(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    request = next(r for r in collection.requests if r.name == "Orders/List Orders")
    assert len(request.unsupported) == 2
    assert all("never executed" in item for item in request.unsupported)


def test_bearer_auth_is_extracted(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    request = next(r for r in collection.requests if r.name == "Orders/List Orders")
    assert request.auth is not None
    assert request.auth.kind == "bearer"
    assert request.auth.secret_value == "sekret-token"


def test_basic_auth_is_extracted(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    request = next(r for r in collection.requests if r.name == "Basic Auth Request")
    assert request.auth is not None
    assert request.auth.kind == "basic"
    assert request.auth.username == "alice"
    assert request.auth.secret_value == "hunter2"


def test_api_key_auth_is_extracted(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    request = next(r for r in collection.requests if r.name == "Api Key Request")
    assert request.auth is not None
    assert request.auth.kind == "api_key"
    assert request.auth.header == "X-Api-Key"
    assert request.auth.secret_value == "abc123"


def test_variable_becomes_a_var_declaration(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    result = postman.render(collection, "Orders/Create Order", name="create_order")
    assert '@var base_url = "https://api.example.com"' in result.workflow
    assert "{{base_url}}/orders" in result.workflow


def test_raw_json_body_is_rendered(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    result = postman.render(collection, "Orders/Create Order", name="create_order")
    assert '"item"' in result.workflow


def test_secret_environment_variable_is_never_embedded(tmp_path: Path) -> None:
    environment = tmp_path / "env.json"
    environment.write_text(
        json.dumps({"values": [{"key": "api_token", "value": "top-secret", "type": "secret"}]}),
        encoding="utf-8",
    )
    collection = postman.load(_write(tmp_path), environment=environment)
    assert "api_token" not in collection.variables
    assert collection.secret_variable_names == ("api_token",)
    result = postman.render(collection, "Orders/Create Order", name="create_order")
    assert "top-secret" not in result.workflow
    assert any("api_token" in warning for warning in result.warnings)


def test_auth_manifest_never_contains_the_secret_value(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    result = postman.render(collection, "Orders/List Orders", name="list_orders")
    assert result.auth_manifest is not None
    assert "sekret-token" not in result.auth_manifest
    assert result.extracted_secret == ("IMPORTED_BEARER_TOKEN", "sekret-token")


def test_unknown_request_name_is_a_clear_error(tmp_path: Path) -> None:
    collection = postman.load(_write(tmp_path))
    with pytest.raises(ValidationError, match="no request"):
        postman.render(collection, "Nope", name="x")


@pytest.mark.parametrize(
    "request_name",
    ["Orders/List Orders", "Orders/Create Order", "Basic Auth Request", "Api Key Request"],
)
def test_rendered_workflow_passes_real_preflight(tmp_path: Path, request_name: str) -> None:
    collection = postman.load(_write(tmp_path))
    result = postman.render(collection, request_name, name="imported")
    doc = parse_sclpll(result.workflow)
    report = preflight(doc, check_files=False, require_ports=False)
    assert report.ok, report.problems[0].diagnostic.message if report.problems else "unknown"
