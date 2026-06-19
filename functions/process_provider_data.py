"""
@name: Process Provider Data
@type: transformer
@version: 1

Processes user data from JSONPlaceholder as simulated provider/product data.
Extracts key fields, calculates metrics, and structures data for aggregation.

Input: fetch_users step output (list of user objects)
Output: Processed provider profiles with contact and company metrics
"""

import json
from collections import Counter


def run(ctx):
    users_raw = ctx.step_outputs.get("fetch_users", {})

    # Parse the JSON body, handling both string and pre-parsed formats
    body = users_raw.get("body", "[]")
    if isinstance(body, str):
        try:
            users = json.loads(body)
        except json.JSONDecodeError:
            users = []
    else:
        users = body if isinstance(body, list) else []

    if not users:
        ctx.workflow_variables["processed_providers"] = json.dumps({
            "error": "No user data received",
            "providers": [],
            "summary": {"total": 0},
        }, indent=2)
        return ctx

    # Process each user as a provider
    providers = []
    for user in users:
        # Extract nested address data safely
        address = user.get("address", {})
        geo = address.get("geo", {})
        company = user.get("company", {})

        # Build provider profile
        provider = {
            "provider_id": user.get("id"),
            "name": user.get("name", "Unknown"),
            "username": user.get("username", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "website": user.get("website", ""),
            "location": {
                "city": address.get("city", ""),
                "street": address.get("street", ""),
                "suite": address.get("suite", ""),
                "zipcode": address.get("zipcode", ""),
                "lat": _safe_float(geo.get("lat")),
                "lng": _safe_float(geo.get("lng")),
            },
            "company": {
                "name": company.get("name", ""),
                "catchphrase": company.get("catchPhrase", ""),
                "bs": company.get("bs", ""),
            },
        }
        providers.append(provider)

    # Calculate aggregate metrics
    cities = Counter(p["location"]["city"] for p in providers)
    companies = Counter(p["company"]["name"] for p in providers)

    summary = {
        "total": len(providers),
        "unique_cities": len(cities),
        "unique_companies": len(companies),
        "top_cities": cities.most_common(5),
        "top_companies": companies.most_common(5),
        "providers_with_website": sum(1 for p in providers if p["website"]),
        "providers_with_phone": sum(1 for p in providers if p["phone"]),
    }

    result = {
        "providers": providers,
        "summary": summary,
    }

    ctx.workflow_variables["processed_providers"] = json.dumps(result, indent=2)
    return ctx


def _safe_float(value):
    """Safely convert a value to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
