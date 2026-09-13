"""I2: turning one operation of a local OpenAPI 3.x document into a workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sclpl import bootstrap
from sclpl.errors import ValidationError
from sclpl.importers import openapi
from sclpl.run.preflight import preflight
from sclpl.run.sclpll.parse import parse as parse_sclpll

bootstrap.load(plugins=False)

_SPEC: dict[str, object] = {
    "openapi": "3.0.3",
    "servers": [{"url": "https://api.example.com"}],
    "components": {
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
        "schemas": {
            "Order": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "total": {"type": "number"}},
            }
        },
    },
    "paths": {
        "/orders/{order_id}": {
            "get": {
                "operationId": "getOrder",
                "parameters": [
                    {
                        "name": "order_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "expand",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "default": "items"},
                    },
                ],
                "security": [{"bearerAuth": []}],
            }
        },
        "/orders": {
            "post": {
                "operationId": "createOrder",
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Order"}}
                    }
                },
            },
            "get": {
                "operationId": "listOrders",
                "parameters": [
                    {
                        "name": "status",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
            },
        },
        "/webhooks": {
            "post": {
                "operationId": "registerWebhook",
                "callbacks": {"onEvent": {"{$request.body#/callbackUrl}": {}}},
            }
        },
    },
}


def _write_spec(tmp_path: Path, spec: dict[str, object] = _SPEC) -> Path:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_load_rejects_yaml() -> None:
    with pytest.raises(ValidationError, match="YAML"):
        openapi.load(Path("spec.yaml"))


def test_load_rejects_an_unsupported_version(tmp_path: Path) -> None:
    path = _write_spec(tmp_path, {**_SPEC, "openapi": "2.0"})
    with pytest.raises(ValidationError, match="unsupported OpenAPI version"):
        openapi.load(path)


def test_load_parses_every_operation(tmp_path: Path) -> None:
    document = openapi.load(_write_spec(tmp_path))
    ids = {op.operation_id for op in document.operations}
    assert ids == {"getOrder", "createOrder", "listOrders", "registerWebhook"}
    assert document.base_url == "https://api.example.com"


def test_path_parameter_becomes_a_required_var(tmp_path: Path) -> None:
    document = openapi.load(_write_spec(tmp_path))
    result = openapi.render(document, "getOrder", name="get_order")
    assert '@var order_id = "<order_id>"' in result.workflow
    assert "/orders/{{order_id}}" in result.workflow


def test_query_default_is_used_as_a_literal(tmp_path: Path) -> None:
    document = openapi.load(_write_spec(tmp_path))
    result = openapi.render(document, "getOrder", name="get_order")
    assert 'query expand="items"' in result.workflow


def test_required_query_without_default_becomes_a_var(tmp_path: Path) -> None:
    document = openapi.load(_write_spec(tmp_path))
    result = openapi.render(document, "listOrders", name="list_orders")
    assert '@var status = "<status>"' in result.workflow
    assert "query status={{status}}" in result.workflow


def test_security_scheme_becomes_an_auth_reference(tmp_path: Path) -> None:
    document = openapi.load(_write_spec(tmp_path))
    result = openapi.render(document, "getOrder", name="get_order")
    assert "auth bearerAuth" in result.workflow


def test_local_ref_in_request_body_resolves_to_an_example(tmp_path: Path) -> None:
    document = openapi.load(_write_spec(tmp_path))
    result = openapi.render(document, "createOrder", name="create_order")
    assert "body " in result.workflow
    assert '"id"' in result.workflow


def test_callbacks_are_reported_as_unsupported(tmp_path: Path) -> None:
    document = openapi.load(_write_spec(tmp_path))
    result = openapi.render(document, "registerWebhook", name="register_webhook")
    assert any("callbacks" in warning for warning in result.warnings)


def test_remote_ref_is_refused_outright(tmp_path: Path) -> None:
    spec = {
        **_SPEC,
        "paths": {
            "/x": {
                "post": {
                    "operationId": "x",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "https://evil.example/schema.json"}
                            }
                        }
                    },
                }
            }
        },
    }
    with pytest.raises(ValidationError, match="non-local"):
        openapi.load(_write_spec(tmp_path, spec))


def test_unknown_operation_id_is_a_clear_error(tmp_path: Path) -> None:
    document = openapi.load(_write_spec(tmp_path))
    with pytest.raises(ValidationError, match="no operation"):
        openapi.render(document, "doesNotExist", name="x")


@pytest.mark.parametrize("operation_id", ["getOrder", "createOrder", "listOrders"])
def test_rendered_workflow_passes_real_preflight(tmp_path: Path, operation_id: str) -> None:
    document = openapi.load(_write_spec(tmp_path))
    result = openapi.render(document, operation_id, name="imported")
    doc = parse_sclpll(result.workflow)
    report = preflight(doc, check_files=False, require_ports=False)
    assert report.ok, report.problems[0].diagnostic.message if report.problems else "unknown"
