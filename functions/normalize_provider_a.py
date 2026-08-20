"""
@name: Normalize Provider A
@type: transformer
@version: 1

Normalizes data from Provider A into a standard format.
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("fetch_provider_a", {})
    body = raw.get("body", "") if isinstance(raw.get("body"), str) else json.dumps(raw.get("body", ""))

    try:
        data = json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError:
        data = {}

    items = data if isinstance(data, list) else data.get("items", data.get("data", [data]))

    normalized = []
    for item in (items if isinstance(items, list) else [items]):
        normalized.append({
            "source": "provider_a",
            "id": item.get("id", ""),
            "name": item.get("name", item.get("title", "")),
            "value": item.get("value", item.get("amount", 0)),
            "raw": item,
        })

    ctx.workflow_variables["provider_a_normalized"] = json.dumps(normalized)
    return ctx
