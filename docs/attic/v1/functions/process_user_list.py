"""
@name: Process User List
@type: transformer
@version: 1

Demonstrates @foreach-like processing.
Processes each user in the list, extracting key fields.
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

    processed = []
    for i, user in enumerate(body):
        processed.append({
            "index": i,
            "id": user.get("id"),
            "name": user.get("name"),
            "email": user.get("email"),
            "company": user.get("company", {}).get("name", ""),
            "city": user.get("address", {}).get("city", ""),
            "website": user.get("website", ""),
        })

    ctx.workflow_variables["processed_users"] = json.dumps(processed, indent=2)
    ctx.workflow_variables["user_count"] = str(len(processed))

    # Extract unique cities and companies
    cities = list(set(u["city"] for u in processed if u["city"]))
    companies = list(set(u["company"] for u in processed if u["company"]))

    ctx.workflow_variables["unique_cities"] = json.dumps(cities)
    ctx.workflow_variables["unique_companies"] = json.dumps(companies)

    return ctx
