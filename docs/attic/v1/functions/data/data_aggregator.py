"""
@name: data_aggregator
@type: transformer
@version: 1
@description: Aggregate data with group-by, sum, count, avg, min, max operations

Config via workflow_variables: aggregate_source (step output key),
aggregate_group_by (field name), aggregate_operation (sum/count/avg/min/max),
aggregate_field (field to aggregate).
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


def run(ctx):
    source_key = ctx.workflow_variables.get("aggregate_source", "")
    group_by = ctx.workflow_variables.get("aggregate_group_by", "")
    operation = ctx.workflow_variables.get("aggregate_operation", "count")
    agg_field = ctx.workflow_variables.get("aggregate_field", "")

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

    groups: dict[str, list] = {}
    for item in data:
        if isinstance(item, dict):
            key = str(_get_nested(item, group_by) if group_by else "all")
        else:
            key = "all"
        groups.setdefault(key, []).append(item)

    results = []
    for group_key, items in groups.items():
        if operation == "count":
            value = len(items)
        elif operation in ("sum", "avg", "min", "max"):
            values = []
            for item in items:
                if isinstance(item, dict):
                    v = _get_nested(item, agg_field)
                    if v is not None:
                        try:
                            values.append(float(v))
                        except (TypeError, ValueError):
                            pass
            if operation == "sum":
                value = sum(values)
            elif operation == "avg":
                value = sum(values) / len(values) if values else 0
            elif operation == "min":
                value = min(values) if values else 0
            else:
                value = max(values) if values else 0
        else:
            value = len(items)

        entry = {"group": group_key, "value": value, "count": len(items)}
        results.append(entry)

    ctx.workflow_variables["aggregated"] = json.dumps(results)

    return {
        "success": True,
        "results": results,
        "group_count": len(results),
    }
