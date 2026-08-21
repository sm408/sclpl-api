"""
@name: data_filter
@type: transformer
@version: 1
@description: Filter data by criteria: field equality, comparison, regex, and membership

Config via workflow_variables: filter_source (step output key),
filter_field (dot-path), filter_operator (eq/ne/gt/gte/lte/regex/in/nin),
filter_value, filter_mode (include/exclude).
"""

import json
import re


def _get_nested(data, path):
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _matches(item, field, operator, value):
    item_value = _get_nested(item, field) if isinstance(item, dict) else item

    if operator == "eq":
        return str(item_value) == str(value)
    elif operator == "ne":
        return str(item_value) != str(value)
    elif operator == "gt":
        try:
            return float(item_value) > float(value)
        except (TypeError, ValueError):
            return False
    elif operator == "gte":
        try:
            return float(item_value) >= float(value)
        except (TypeError, ValueError):
            return False
    elif operator == "lt":
        try:
            return float(item_value) < float(value)
        except (TypeError, ValueError):
            return False
    elif operator == "lte":
        try:
            return float(item_value) <= float(value)
        except (TypeError, ValueError):
            return False
    elif operator == "regex":
        try:
            return bool(re.search(str(value), str(item_value)))
        except re.error:
            return False
    elif operator == "in":
        values = {v.strip() for v in str(value).split(",")}
        return str(item_value) in values
    elif operator == "nin":
        values = {v.strip() for v in str(value).split(",")}
        return str(item_value) not in values
    return False


def run(ctx):
    source_key = ctx.workflow_variables.get("filter_source", "")
    field = ctx.workflow_variables.get("filter_field", "")
    operator = ctx.workflow_variables.get("filter_operator", "eq")
    value = ctx.workflow_variables.get("filter_value", "")
    mode = ctx.workflow_variables.get("filter_mode", "include")

    data = ctx.workflow_variables.get(source_key) if source_key else None
    if data is None:
        data = ctx.step_outputs.get(source_key, []) if source_key else []

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "Source data is not valid JSON"}

    if not isinstance(data, list):
        data = [data]

    if mode == "include":
        filtered = [item for item in data if _matches(item, field, operator, value)]
    else:
        filtered = [item for item in data if not _matches(item, field, operator, value)]

    return {
        "success": True,
        "filtered": filtered,
        "original_count": len(data),
        "filtered_count": len(filtered),
    }
