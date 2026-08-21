"""
@name: Normalize Provider B
@type: transformer
@version: 1

Normalizes data from Provider B into a standard format.
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("fetch_provider_b", {})
    body = raw.get("body", "") if isinstance(raw.get("body"), str) else json.dumps(raw.get("body", ""))

    try:
        data = json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError:
        data = {}

    items = data if isinstance(data, list) else data.get("items", data.get("data", [data]))

    normalized = []
    for item in (items if isinstance(items, list) else [items]):
        normalized.append({
            "source": "provider_b",
            "id": item.get("id", item.get("key", "")),
            "name": item.get("name", item.get("label", "")),
            "value": item.get("value", item.get("total", 0)),
            "raw": item,
        })

    ctx.workflow_variables["provider_b_normalized"] = json.dumps(normalized)
    return ctx
