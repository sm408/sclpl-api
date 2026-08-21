"""
@name: data_deduplicator
@type: transformer
@version: 1
@description: Remove duplicate entries from data based on specified fields or full object matching

Config via workflow_variables: dedupe_source (step output key),
dedupe_key (field name or comma-separated fields for composite key),
dedupe_strategy (first/last/merge).
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


def _make_key(item, key_field):
    if not key_field:
        return json.dumps(item, sort_keys=True, default=str)

    fields = [f.strip() for f in key_field.split(",")]
    parts = []
    for f in fields:
        val = _get_nested(item, f) if isinstance(item, dict) else item
        parts.append(str(val))
    return "|".join(parts)


def run(ctx):
    source_key = ctx.workflow_variables.get("dedupe_source", "")
    key_field = ctx.workflow_variables.get("dedupe_key", "")
    strategy = ctx.workflow_variables.get("dedupe_strategy", "first")

    data = ctx.workflow_variables.get(source_key) if source_key else None
    if data is None:
        data = ctx.step_outputs.get(source_key, []) if source_key else []

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "Source data is not valid JSON"}

    if not isinstance(data, list):
        return {"success": False, "error": "Data must be a list"}

    seen: dict[str, int] = {}
    result = []

    for i, item in enumerate(data):
        key = _make_key(item, key_field)
        if key in seen:
            if strategy == "last":
                result[seen[key]] = item
            elif strategy == "merge" and isinstance(item, dict) and isinstance(result[seen[key]], dict):
                result[seen[key]].update(item)
        else:
            seen[key] = len(result)
            result.append(item)

    removed = len(data) - len(result)

    ctx.workflow_variables["deduplicated"] = json.dumps(result, default=str)

    return {
        "success": True,
        "deduplicated": result,
        "original_count": len(data),
        "result_count": len(result),
        "removed": removed,
    }
