"""
@name: Merge Provider Data
@type: transformer
@version: 1

Merges normalized data from multiple providers into a unified list.
"""

import json


def run(ctx):
    a_raw = ctx.workflow_variables.get("provider_a_normalized", "[]")
    b_raw = ctx.workflow_variables.get("provider_b_normalized", "[]")

    try:
        a_data = json.loads(a_raw) if isinstance(a_raw, str) else a_raw
    except json.JSONDecodeError:
        a_data = []

    try:
        b_data = json.loads(b_raw) if isinstance(b_raw, str) else b_raw
    except json.JSONDecodeError:
        b_data = []

    merged = (a_data if isinstance(a_data, list) else []) + (b_data if isinstance(b_data, list) else [])

    summary = {
        "total_items": len(merged),
        "provider_a_count": len(a_data) if isinstance(a_data, list) else 0,
        "provider_b_count": len(b_data) if isinstance(b_data, list) else 0,
        "items": merged,
    }

    ctx.workflow_variables["merged_providers"] = json.dumps(summary, indent=2)
    return ctx
