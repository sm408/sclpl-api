"""
@name: User Todo Summary
@type: transformer
@version: 1

Summarizes todo completion status per user.
Takes context from fetch_users and fetch_todos steps.
"""

import json
from collections import Counter


def run(ctx):
    users_raw = ctx.step_outputs.get("fetch_users", {})
    todos_raw = ctx.step_outputs.get("fetch_todos", {})

    users = json.loads(users_raw.get("body", "[]")) if isinstance(users_raw.get("body"), str) else users_raw.get("body", [])
    todos = json.loads(todos_raw.get("body", "[]")) if isinstance(todos_raw.get("body"), str) else todos_raw.get("body", [])

    # Build user lookup
    user_map = {u["id"]: u["name"] for u in users}

    # Analyze todos per user
    user_todos = {}
    for todo in todos:
        user_id = todo["userId"]
        if user_id not in user_todos:
            user_todos[user_id] = {"total": 0, "completed": 0, "pending": 0}
        user_todos[user_id]["total"] += 1
        if todo["completed"]:
            user_todos[user_id]["completed"] += 1
        else:
            user_todos[user_id]["pending"] += 1

    # Calculate completion rates
    user_summaries = []
    for user_id, stats in user_todos.items():
        completion_rate = (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        user_summaries.append({
            "user_id": user_id,
            "name": user_map.get(user_id, f"User {user_id}"),
            "total_todos": stats["total"],
            "completed": stats["completed"],
            "pending": stats["pending"],
            "completion_rate": round(completion_rate, 1),
        })

    # Sort by completion rate
    user_summaries.sort(key=lambda x: x["completion_rate"], reverse=True)

    # Overall statistics
    total_todos = len(todos)
    completed_todos = sum(1 for t in todos if t["completed"])
    overall_rate = (completed_todos / total_todos * 100) if total_todos > 0 else 0

    result = {
        "overall": {
            "total_todos": total_todos,
            "completed": completed_todos,
            "pending": total_todos - completed_todos,
            "completion_rate": round(overall_rate, 1),
        },
        "top_performers": user_summaries[:5],
        "needs_attention": [u for u in user_summaries if u["completion_rate"] < 50][:3],
    }

    # Store in workflow variables for downstream steps
    ctx.workflow_variables["todo_summary"] = json.dumps(result, indent=2)
    return ctx
