"""Supported contract rules share assertion-style diagnostics."""

from pathlib import Path

import pytest

from sclpl.contracts import check, generate
from sclpl.errors import AssertionFailed, ValidationError


def test_nested_contract_accepts_a_compatible_value() -> None:
    check(
        {"id": 1, "tags": ["a"]},
        {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
    )


def test_generation_creates_a_reviewable_nested_candidate() -> None:
    candidate = generate({"id": 1, "items": [{"name": "Ada"}]})
    assert candidate["required"] == ["id", "items"]
    assert candidate["properties"]["items"]["items"]["properties"]["name"]["type"] == "string"


def test_contract_uses_a_local_reference(tmp_path: Path) -> None:
    shared = tmp_path / "shared.json"
    shared.write_text('{"$defs":{"id":{"type":"integer"}}}', encoding="utf-8")
    root = tmp_path / "root.json"
    root.write_text('{"$ref":"shared.json#/$defs/id"}', encoding="utf-8")
    check(3, {"$ref": "shared.json#/$defs/id"}, source=root)


def test_contract_uses_an_internal_reference(tmp_path: Path) -> None:
    root = tmp_path / "root.json"
    root.write_text(
        '{"$defs":{"id":{"type":"integer"}},"properties":{"id":{"$ref":"#/$defs/id"}}}',
        encoding="utf-8",
    )
    check({"id": 3}, {"properties": {"id": {"$ref": "#/$defs/id"}}}, source=root)


def test_contract_refuses_remote_reference() -> None:
    with pytest.raises(ValidationError, match="remote"):
        check(3, {"$ref": "https://example.test/contract.json"})


@pytest.mark.parametrize(
    ("value", "contract", "expected"),
    [
        ({}, {"type": "object", "required": ["id"]}, "missing required"),
        (True, {"type": "number"}, "expected number"),
        (3, {"maximum": 2}, "expected at most"),
        ("x", {"enum": ["a"]}, "expected one of"),
    ],
)
def test_contract_failures_name_the_path(
    value: object, contract: dict[str, object], expected: str
) -> None:
    with pytest.raises(AssertionFailed, match=expected):
        check(value, contract)
