"""Utilities for parsing step outputs and API responses."""

from __future__ import annotations

import json
from typing import Any

from app.core.models.context import ExecutionContext


def parse_step_output(ctx: ExecutionContext, step_id: str) -> dict[str, Any]:
    """Parse a step's output, handling both string and dict formats.

    Args:
        ctx: Execution context containing step outputs
        step_id: The step ID to get output from

    Returns:
        Parsed output as a dict (empty dict if not found or invalid)
    """
    raw = ctx.step_outputs.get(step_id, {})
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


def parse_body(ctx: ExecutionContext, step_id: str) -> Any:
    """Parse the 'body' field from a step's output.

    Handles nested parsing: step output -> body field -> JSON parse if string.

    Args:
        ctx: Execution context containing step outputs
        step_id: The step ID to get body from

    Returns:
        Parsed body content (dict, list, or original value)
    """
    output = parse_step_output(ctx, step_id)
    body = output.get("body", {})

    if isinstance(body, str):
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return body
    return body


def get_nested(data: dict | list, path: str, default: Any = None) -> Any:
    """Get a nested value from a dict/list using dot notation.

    Args:
        data: The data structure to traverse
        path: Dot-separated path (e.g., "user.address.city")
        default: Default value if path not found

    Returns:
        The value at the path, or default if not found

    Examples:
        >>> get_nested({"user": {"name": "John"}}, "user.name")
        "John"
        >>> get_nested({"items": [1, 2, 3]}, "items.1")
        2
    """
    keys = path.split(".")
    current = data

    for key in keys:
        if current is None:
            return default

        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(key)]
            except (IndexError, ValueError):
                return default
        else:
            return default

    return current if current is not None else default


def parse_workflow_variable(ctx: ExecutionContext, var_name: str) -> Any:
    """Parse a workflow variable that contains JSON.

    Args:
        ctx: Execution context
        var_name: Variable name to parse

    Returns:
        Parsed value (dict, list, or original string)
    """
    raw = ctx.workflow_variables.get(var_name, "")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    return raw
