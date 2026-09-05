"""A small, strict JSON-compatible contract evaluator for recorded values."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sclpl.errors import AssertionFailed, ValidationError


def generate(value: Any) -> dict[str, Any]:
    """Infer a conservative candidate contract from one local sample value."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "required": sorted(value),
            "properties": {name: generate(item) for name, item in sorted(value.items())},
        }
    if isinstance(value, list):
        if not value:
            return {"type": "array"}
        return {"type": "array", "items": _merge([generate(item) for item in value])}
    return {"type": _type(value)}


def check(
    value: Any,
    contract: dict[str, Any],
    *,
    path: str = "$",
    source: Path | None = None,
) -> None:
    """Validate a value against the supported contract subset with useful paths."""
    document = _document(contract, source)
    contract, source = _resolve(contract, source, document, source.parent if source else None)
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
                    check(value[name], nested, path=f"{path}.{name}", source=source)
    if isinstance(value, list) and isinstance(contract.get("items"), dict):
        for index, item in enumerate(value):
            check(item, contract["items"], path=f"{path}[{index}]", source=source)
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


def _merge(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep only constraints supported by every observed array element."""
    if not candidates or any(
        candidate.get("type") != candidates[0].get("type") for candidate in candidates
    ):
        return {}
    first = candidates[0]
    if first.get("type") != "object":
        return first
    properties: dict[str, dict[str, Any]] = {}
    names = set().union(*(set(candidate.get("properties", {})) for candidate in candidates))
    for name in names:
        present = [
            candidate["properties"][name]
            for candidate in candidates
            if name in candidate.get("properties", {})
        ]
        properties[name] = _merge(present)
    required = sorted(
        set.intersection(*(set(candidate.get("required", [])) for candidate in candidates))
    )
    return {"type": "object", "required": required, "properties": dict(sorted(properties.items()))}


def _resolve(
    contract: dict[str, Any], source: Path | None, document: dict[str, Any], root: Path | None
) -> tuple[dict[str, Any], Path | None]:
    reference = contract.get("$ref")
    if reference is None:
        return contract, source
    if not isinstance(reference, str):
        raise ValidationError("$ref must be a string")
    if reference.startswith(("http:", "https:")):
        raise ValidationError("remote contract references are disabled")
    target, fragment = reference.split("#", 1) if "#" in reference else (reference, "")
    if target:
        if source is None or root is None:
            raise ValidationError("external $ref needs a local contract file")
        resolved = (source.parent / target).resolve()
        if not resolved.is_relative_to(root):
            raise ValidationError("contract reference escapes its root")
        try:
            loaded = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValidationError(f"invalid local contract reference {target!r}") from error
        if not isinstance(loaded, dict):
            raise ValidationError("referenced contract must be an object")
        contract, source, document = loaded, resolved, loaded
    if fragment:
        if not fragment.startswith("/"):
            raise ValidationError("$ref fragments must be JSON pointers")
        current: Any = document
        for token in fragment.removeprefix("/").split("/"):
            if not isinstance(current, dict) or token not in current:
                raise ValidationError(f"unknown contract reference {reference!r}")
            current = current[token]
        if not isinstance(current, dict):
            raise ValidationError("referenced contract must be an object")
        contract = current
    return contract, source


def _document(contract: dict[str, Any], source: Path | None) -> dict[str, Any]:
    if source is None:
        return contract
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"invalid local contract file {source}") from error
    if not isinstance(document, dict):
        raise ValidationError("contract root must be an object")
    return document
