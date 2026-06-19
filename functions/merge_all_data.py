"""
@name: Merge All Data
@type: transformer
@version: 1

Demonstrates merging data from multiple parallel steps.
Combines users, posts, and todos into a unified dataset.
"""

import json


def run(ctx):
    # Parse all step outputs
    users_raw = ctx.step_outputs.get("fetch_users", {})
    posts_raw = ctx.step_outputs.get("fetch_posts", {})
    todos_raw = ctx.step_outputs.get("fetch_todos", {})

    users = json.loads(users_raw.get("body", "[]")) if isinstance(users_raw.get("body"), str) else users_raw.get("body", [])
    posts = json.loads(posts_raw.get("body", "[]")) if isinstance(posts_raw.get("body"), str) else posts_raw.get("body", [])
    todos = json.loads(todos_raw.get("body", "[]")) if isinstance(todos_raw.get("body"), str) else todos_raw.get("body", [])

    # Build user lookup
    user_map = {u["id"]: u for u in users}

    # Count posts per user
    posts_per_user = {}
    for post in posts:
        uid = post.get("userId", 0)
        posts_per_user[uid] = posts_per_user.get(uid, 0) + 1

    # Count todos per user
    todos_per_user = {}
    completed_per_user = {}
    for todo in todos:
        uid = todo.get("userId", 0)
        todos_per_user[uid] = todos_per_user.get(uid, 0) + 1
        if todo.get("completed"):
            completed_per_user[uid] = completed_per_user.get(uid, 0) + 1

    # Merge into unified dataset
    merged = []
    for user in users:
        uid = user["id"]
        total_todos = todos_per_user.get(uid, 0)
        completed = completed_per_user.get(uid, 0)

        merged.append({
            "user_id": uid,
            "name": user.get("name"),
            "email": user.get("email"),
            "company": user.get("company", {}).get("name", ""),
            "city": user.get("address", {}).get("city", ""),
            "post_count": posts_per_user.get(uid, 0),
            "todo_count": total_todos,
            "completed_todos": completed,
            "completion_rate": round(completed / total_todos * 100, 1) if total_todos > 0 else 0,
        })

    # Sort by post count
    merged.sort(key=lambda x: x["post_count"], reverse=True)

    ctx.workflow_variables["merged_data"] = json.dumps(merged, indent=2)
    ctx.workflow_variables["total_users"] = str(len(users))
    ctx.workflow_variables["total_posts"] = str(len(posts))
    ctx.workflow_variables["total_todos"] = str(len(todos))

    return ctx
