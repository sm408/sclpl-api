"""
@name: Generate Receipt
@type: transformer
@version: 1

Generates a formatted receipt from order, payment, and inventory data.
"""

import json


def run(ctx):
    order_raw = ctx.workflow_variables.get("order", "{}")
    payment_raw = ctx.step_outputs.get("process_payment", {})
    inventory_raw = ctx.workflow_variables.get("inventory_update", "{}")

    order = json.loads(order_raw) if isinstance(order_raw, str) else order_raw
    payment_body = json.loads(payment_raw.get("body", "{}")) if isinstance(payment_raw.get("body"), str) else payment_raw.get("body", {})
    inventory = json.loads(inventory_raw) if isinstance(inventory_raw, str) else inventory_raw

    receipt = {
        "receipt_number": f"RCP-{order.get('order_id', 'UNKNOWN')}",
        "order_id": order.get("order_id"),
        "date": order.get("created_at"),
        "items": [
            {
                "name": item.get("title", "Unknown"),
                "price": item.get("price", 0),
                "qty": item.get("quantity", 1),
                "total": item.get("item_total", 0),
            }
            for item in order.get("items", [])
        ],
        "subtotal": order.get("subtotal", 0),
        "tax": order.get("tax", 0),
        "total": order.get("total", 0),
        "payment": {
            "status": payment_body.get("status", "unknown"),
            "transaction_id": payment_body.get("id", "N/A"),
            "method": "credit_card",
        },
        "inventory_status": "all_fulfilled" if inventory.get("all_in_stock") else "partial_fulfillment",
        "categories": order.get("categories_used", []),
    }

    ctx.workflow_variables["receipt"] = json.dumps(receipt, indent=2)
    return ctx
