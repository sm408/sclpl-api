"""
@name: Enrich Order Data
@type: transformer
@version: 1

Enriches raw order data with computed fields.
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("fetch_orders", {})
    body = raw.get("body", "") if isinstance(raw.get("body"), str) else json.dumps(raw.get("body", ""))

    try:
        data = json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError:
        data = {}

    orders = data if isinstance(data, list) else data.get("orders", data.get("data", []))

    enriched = []
    for order in (orders if isinstance(orders, list) else []):
        enriched.append({
            **order,
            "has_items": bool(order.get("items")),
            "item_count": len(order.get("items", [])),
            "source": "orders",
        })

    ctx.workflow_variables["enriched_orders"] = json.dumps(enriched)
    return ctx
