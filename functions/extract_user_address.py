"""
@name: Extract User Address
@type: transformer
@version: 1

Demonstrates deep dot notation access into nested objects.
Extracts address details from the first user.
"""

import json


def run(ctx):
    users_raw = ctx.step_outputs.get("fetch_users", {})
    body = users_raw.get("body", "[]")

    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = []

    if body and isinstance(body, list) and len(body) > 0:
        address = body[0].get("address", {})
        geo = address.get("geo", {})

        ctx.workflow_variables["user_street"] = address.get("street", "")
        ctx.workflow_variables["user_suite"] = address.get("suite", "")
        ctx.workflow_variables["user_city"] = address.get("city", "")
        ctx.workflow_variables["user_zipcode"] = address.get("zipcode", "")
        ctx.workflow_variables["user_lat"] = geo.get("lat", "0")
        ctx.workflow_variables["user_lng"] = geo.get("lng", "0")

        # Full address string
        ctx.workflow_variables["user_full_address"] = (
            f"{address.get('street', '')}, {address.get('suite', '')}, "
            f"{address.get('city', '')} {address.get('zipcode', '')}"
        )

    return ctx
