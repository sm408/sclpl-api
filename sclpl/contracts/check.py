"""A small, strict JSON-compatible contract evaluator for recorded values."""

from __future__ import annotations

from typing import Any

from sclpl.errors import AssertionFailed


def check(value: Any, contract: dict[str, Any], *, path: str = "$") -> None:
    """Validate a value against the supported contract subset with useful paths."""
    wanted = contract.get("type")
    if wanted is not None and not _matches(value, wanted):
        raise AssertionFailed(f"{path}: expected {wanted}, found {_type(value)}")
    if isinstance(value, dict):
        required = contract.get("required", [])
        for name in required:
            if name not in value:
                raise AssertionFailed(f"{path}: missing required field {name!r}")
        properties = contract.get("properties", {})
        if isinstance(properties, dict):
            for name, nested in properties.items():
                if name in value and isinstance(nested, dict):
                    check(value[name], nested, path=f"{path}.{name}")
    if isinstance(value, list) and isinstance(contract.get("items"), dict):
        for index, item in enumerate(value):
            check(item, contract["items"], path=f"{path}[{index}]")
    if "enum" in contract and value not in contract["enum"]:
        raise AssertionFailed(f"{path}: expected one of {contract['enum']!r}, found {value!r}")
    if "minimum" in contract and (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < contract["minimum"]
    ):
        raise AssertionFailed(f"{path}: expected at least {contract['minimum']}, found {value!r}")
    if "maximum" in contract and (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value > contract["maximum"]
    ):
        raise AssertionFailed(f"{path}: expected at most {contract['maximum']}, found {value!r}")


def _matches(value: Any, wanted: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(wanted, False)


def _type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__
