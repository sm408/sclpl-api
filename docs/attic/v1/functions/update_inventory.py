"""
@name: Update Inventory
@type: transformer
@version: 1

Simulates inventory updates by decrementing stock for ordered items.
"""

import json


def run(ctx):
    order_raw = ctx.workflow_variables.get("order", "{}")
    order = json.loads(order_raw) if isinstance(order_raw, str) else order_raw

    items = order.get("items", [])

    inventory_updates = []
    for item in items:
        product_id = item.get("product_id")
        qty = item.get("quantity", 1)
        new_stock = max(0, 100 - qty)
        inventory_updates.append({
            "product_id": product_id,
            "title": item.get("title", "Unknown"),
            "previous_stock": 100,
            "quantity_sold": qty,
            "new_stock": new_stock,
            "status": "updated" if new_stock > 0 else "out_of_stock",
        })

    result = {
        "order_id": order.get("order_id"),
        "updated_at": order.get("created_at"),
        "items_updated": len(inventory_updates),
        "inventory_changes": inventory_updates,
        "all_in_stock": all(u["status"] == "updated" for u in inventory_updates),
    }

    ctx.workflow_variables["inventory_update"] = json.dumps(result, indent=2)
    return ctx
