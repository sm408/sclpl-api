"""
@name: json_transformer
@type: transformer
@version: 1
@description: Transform JSON data using field mapping, filtering, and renaming

Config via workflow_variables: transform_source (step output key),
transform_mapping (JSON object: {"old_key": "new_key"}),
transform_include (comma-separated fields to keep),
transform_exclude (comma-separated fields to drop).
"""

import json


def _get_nested(data, path):
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _set_nested(data, path, value):
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def run(ctx):
    source_key = ctx.workflow_variables.get("transform_source", "")
    mapping_raw = ctx.workflow_variables.get("transform_mapping", "{}")
    include_raw = ctx.workflow_variables.get("transform_include", "")
    exclude_raw = ctx.workflow_variables.get("transform_exclude", "")

    data = ctx.workflow_variables.get(source_key) if source_key else None
    if data is None:
        data = ctx.step_outputs.get(source_key, {}) if source_key else {}

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "Source data is not valid JSON"}

    try:
        mapping = json.loads(mapping_raw)
    except (json.JSONDecodeError, TypeError):
        mapping = {}

    include_fields = {f.strip() for f in include_raw.split(",") if f.strip()} if include_raw else None
    exclude_fields = {f.strip() for f in exclude_raw.split(",") if f.strip()} if exclude_raw else set()

    def transform_item(item):
        if not isinstance(item, dict):
            return item

        result = {}
        for key, value in item.items():
            if exclude_fields and key in exclude_fields:
                continue
            if include_fields and key not in include_fields:
                continue
            new_key = mapping.get(key, key)
            result[new_key] = value
        return result

    if isinstance(data, list):
        transformed = [transform_item(item) for item in data]
    elif isinstance(data, dict):
        transformed = transform_item(data)
    else:
        return {"success": False, "error": "Unsupported data type for transformation"}

    return {
        "success": True,
        "transformed": transformed,
        "record_count": len(transformed) if isinstance(transformed, list) else 1,
    }
