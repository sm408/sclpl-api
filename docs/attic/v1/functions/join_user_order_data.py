"""
@name: Join User Order Data
@type: transformer
@version: 1

Joins enriched user and order data into a unified view.
"""

import json


def run(ctx):
    users_raw = ctx.workflow_variables.get("enriched_users", "[]")
    orders_raw = ctx.workflow_variables.get("enriched_orders", "[]")

    try:
        users = json.loads(users_raw) if isinstance(users_raw, str) else users_raw
    except json.JSONDecodeError:
        users = []

    try:
        orders = json.loads(orders_raw) if isinstance(orders_raw, str) else orders_raw
    except json.JSONDecodeError:
        orders = []

    user_map = {u.get("id", ""): u for u in users if isinstance(u, dict)}

    joined = []
    for order in orders:
        if not isinstance(order, dict):
            continue
        user_id = order.get("user_id", order.get("userId", ""))
        user = user_map.get(user_id, {})
        joined.append({
            "user_name": user.get("display_name", "Unknown"),
            "user_email": user.get("email", ""),
            "order_id": order.get("id", ""),
            "item_count": order.get("item_count", 0),
            "total": order.get("total", order.get("amount", 0)),
        })

    ctx.workflow_variables["joined_data"] = json.dumps(joined)
    return ctx
