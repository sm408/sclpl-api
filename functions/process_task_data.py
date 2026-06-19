"""
@name: Process Task Data
@type: transformer
@version: 1

Processes todos data from JSONPlaceholder as simulated task/completion data.
Calculates completion rates per user and identifies productivity patterns.

Input: fetch_todos step output (list of todo objects)
Output: Task completion analysis with per-user rates and overall metrics
"""

import json
from collections import Counter, defaultdict


def run(ctx):
    todos_raw = ctx.step_outputs.get("fetch_todos", {})

    # Parse the JSON body
    body = todos_raw.get("body", "[]")
    if isinstance(body, str):
        try:
            todos = json.loads(body)
        except json.JSONDecodeError:
            todos = []
    else:
        todos = body if isinstance(body, list) else []

    if not todos:
        ctx.workflow_variables["processed_tasks"] = json.dumps({
            "error": "No todo data received",
            "tasks": [],
            "summary": {"total": 0},
        }, indent=2)
        return ctx

    # Group todos by user
    user_tasks = defaultdict(lambda: {"total": 0, "completed": 0, "pending": 0, "titles": []})
    for todo in todos:
        user_id = todo.get("userId")
        is_complete = todo.get("completed", False)
        user_tasks[user_id]["total"] += 1
        if is_complete:
            user_tasks[user_id]["completed"] += 1
        else:
            user_tasks[user_id]["pending"] += 1
        # Keep sample titles for context
        if len(user_tasks[user_id]["titles"]) < 3:
            user_tasks[user_id]["titles"].append(todo.get("title", ""))

    # Build per-user summaries
    user_summaries = []
    for user_id, stats in sorted(user_tasks.items()):
        total = stats["total"]
        completed = stats["completed"]
        completion_rate = round((completed / total * 100) if total > 0 else 0, 1)

        user_summaries.append({
            "user_id": user_id,
            "total_tasks": total,
            "completed": completed,
            "pending": stats["pending"],
            "completion_rate": completion_rate,
            "sample_titles": stats["titles"],
            "productivity_tier": _classify_productivity(completion_rate),
        })

    # Sort by completion rate descending
    user_summaries.sort(key=lambda x: x["completion_rate"], reverse=True)

    # Overall statistics
    total_todos = len(todos)
    completed_todos = sum(1 for t in todos if t.get("completed"))
    overall_rate = round((completed_todos / total_todos * 100) if total_todos > 0 else 0, 1)

    # Productivity tier distribution
    tier_counts = Counter(u["productivity_tier"] for u in user_summaries)

    summary = {
        "total": total_todos,
        "completed": completed_todos,
        "pending": total_todos - completed_todos,
        "overall_completion_rate": overall_rate,
        "unique_users": len(user_summaries),
        "avg_tasks_per_user": round(total_todos / len(user_summaries), 1) if user_summaries else 0,
        "productivity_distribution": dict(tier_counts),
        "top_performers": [
            {"user_id": u["user_id"], "rate": u["completion_rate"]}
            for u in user_summaries[:5]
        ],
        "needs_attention": [
            {"user_id": u["user_id"], "rate": u["completion_rate"]}
            for u in user_summaries if u["completion_rate"] < 50
        ][:5],
    }

    result = {
        "user_tasks": user_summaries,
        "summary": summary,
    }

    ctx.workflow_variables["processed_tasks"] = json.dumps(result, indent=2)
    return ctx


def _classify_productivity(rate):
    """Classify a user into a productivity tier based on completion rate."""
    if rate >= 80:
        return "high"
    elif rate >= 50:
        return "medium"
    else:
        return "low"
