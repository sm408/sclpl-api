"""
@name: Analyze Data
@type: transformer
@version: 1

Demonstrates advanced analysis with dot notation access.
Analyzes merged data and processed users for insights.
"""

import json


def run(ctx):
    merged_raw = ctx.workflow_variables.get("merged_data", "[]")
    processed_raw = ctx.workflow_variables.get("processed_users", "[]")

    try:
        merged = json.loads(merged_raw) if isinstance(merged_raw, str) else merged_raw
    except (json.JSONDecodeError, TypeError):
        merged = []

    try:
        processed = json.loads(processed_raw) if isinstance(processed_raw, str) else processed_raw
    except (json.JSONDecodeError, TypeError):
        processed = []

    # Calculate statistics
    total_users = len(merged)
    total_posts = sum(u.get("post_count", 0) for u in merged)
    total_todos = sum(u.get("todo_count", 0) for u in merged)
    completed_todos = sum(u.get("completed_todos", 0) for u in merged)

    # Top contributors
    top_contributors = merged[:3] if merged else []

    # City distribution
    city_counts = {}
    for u in merged:
        city = u.get("city", "Unknown")
        city_counts[city] = city_counts.get(city, 0) + 1

    # Company distribution
    company_counts = {}
    for u in merged:
        company = u.get("company", "Unknown")
        company_counts[company] = company_counts.get(company, 0) + 1

    # Completion rates
    completion_rates = [u.get("completion_rate", 0) for u in merged]
    avg_completion = sum(completion_rates) / len(completion_rates) if completion_rates else 0

    analytics = {
        "summary": {
            "total_users": total_users,
            "total_posts": total_posts,
            "total_todos": total_todos,
            "completed_todos": completed_todos,
            "avg_completion_rate": round(avg_completion, 1),
            "avg_posts_per_user": round(total_posts / total_users, 1) if total_users > 0 else 0,
        },
        "top_contributors": [
            {"name": u["name"], "posts": u["post_count"], "company": u["company"]}
            for u in top_contributors
        ],
        "city_distribution": dict(sorted(city_counts.items(), key=lambda x: x[1], reverse=True)),
        "company_distribution": dict(sorted(company_counts.items(), key=lambda x: x[1], reverse=True)),
    }

    ctx.workflow_variables["analytics"] = json.dumps(analytics, indent=2)

    return ctx
