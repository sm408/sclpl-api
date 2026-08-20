"""
@name: Process Order
@type: transformer
@version: 1

Processes an order by combining product and category data,
simulating order creation with calculated totals.
"""

import json
from datetime import datetime, timezone


def run(ctx):
    products_raw = ctx.step_outputs.get("fetch_products", {})
    categories_raw = ctx.step_outputs.get("fetch_categories", {})

    products_body = json.loads(products_raw.get("body", "[]")) if isinstance(products_raw.get("body"), str) else products_raw.get("body", [])
    categories_body = json.loads(categories_raw.get("body", "[]")) if isinstance(categories_raw.get("body"), str) else categories_raw.get("body", [])

    if not isinstance(products_body, list):
        products_body = []
    if not isinstance(categories_body, list):
        categories_body = []

    selected_products = products_body[:3] if len(products_body) >= 3 else products_body

    order_items = []
    total = 0.0
    for product in selected_products:
        price = float(product.get("price", 0))
        qty = 1
        item_total = price * qty
        total += item_total
        order_items.append({
            "product_id": product.get("id"),
            "title": product.get("title", "Unknown"),
            "price": price,
            "quantity": qty,
            "item_total": round(item_total, 2),
        })

    category_map = {c.get("id"): c.get("name", "Unknown") for c in categories_body if isinstance(c, dict)}

    order = {
        "order_id": f"ORD-{int(datetime.now(timezone.utc).timestamp())}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": order_items,
        "item_count": len(order_items),
        "subtotal": round(total, 2),
        "tax": round(total * 0.08, 2),
        "total": round(total * 1.08, 2),
        "categories_used": list({category_map.get(p.get("categoryId"), "Unknown") for p in selected_products}),
    }

    ctx.workflow_variables["order"] = json.dumps(order, indent=2)
    return ctx
