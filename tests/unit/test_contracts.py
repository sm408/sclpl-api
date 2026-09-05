"""Supported contract rules share assertion-style diagnostics."""

from __future__ import annotations

import pytest

from sclpl.contracts import check
from sclpl.errors import AssertionFailed


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
