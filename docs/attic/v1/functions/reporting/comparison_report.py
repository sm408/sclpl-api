"""
@name: comparison_report
@type: report
@version: 1
@description: Compare two data sets and produce a difference report

Config via workflow_variables: compare_source_a, compare_source_b,
compare_key (field to match records), compare_fields (comma-separated).
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
    source_a = ctx.workflow_variables.get("compare_source_a", "")
    source_b = ctx.workflow_variables.get("compare_source_b", "")
    compare_key = ctx.workflow_variables.get("compare_key", "")
    compare_fields_raw = ctx.workflow_variables.get("compare_fields", "")

    data_a = ctx.step_outputs.get(source_a, []) if source_a else []
    data_b = ctx.step_outputs.get(source_b, []) if source_b else []

    if isinstance(data_a, str):
        try:
            data_a = json.loads(data_a)
        except (json.JSONDecodeError, TypeError):
            data_a = []
    if isinstance(data_b, str):
        try:
            data_b = json.loads(data_b)
        except (json.JSONDecodeError, TypeError):
            data_b = []

    if not isinstance(data_a, list):
        data_a = [data_a]
    if not isinstance(data_b, list):
        data_b = [data_b]

    compare_fields = [f.strip() for f in compare_fields_raw.split(",") if f.strip()] if compare_fields_raw else []

    if compare_key:
        index_a = {}
        for item in data_a:
            if isinstance(item, dict):
                key = str(_get_nested(item, compare_key))
                index_a[key] = item

        index_b = {}
        for item in data_b:
            if isinstance(item, dict):
                key = str(_get_nested(item, compare_key))
                index_b[key] = item

        keys_a = set(index_a.keys())
        keys_b = set(index_b.keys())

        added = keys_b - keys_a
        removed = keys_a - keys_b
        common = keys_a & keys_b

        changed = []
        for key in common:
            item_a = index_a[key]
            item_b = index_b[key]
            diffs = {}

            fields_to_check = compare_fields or list(set(list(item_a.keys()) + list(item_b.keys())))
            for field in fields_to_check:
                val_a = _get_nested(item_a, field)
                val_b = _get_nested(item_b, field)
                if val_a != val_b:
                    diffs[field] = {"from": val_a, "to": val_b}

            if diffs:
                changed.append({"key": key, "diffs": diffs})

        report = {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(common) - len(changed),
            "added_keys": list(added),
            "removed_keys": list(removed),
            "changes": changed,
        }
    else:
        report = {
            "count_a": len(data_a),
            "count_b": len(data_b),
            "difference": len(data_b) - len(data_a),
        }

    ctx.workflow_variables["comparison"] = json.dumps(report, default=str)

    return {
        "success": True,
        "report": report,
    }
