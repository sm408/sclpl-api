"""
@name: Merge User Posts
@type: transformer
@version: 1

Merges user data with their posts to create a user-post mapping.
Takes context from fetch_users and fetch_posts steps.
"""

import json


def run(ctx):
    users_raw = ctx.step_outputs.get("fetch_users", {})
    posts_raw = ctx.step_outputs.get("fetch_posts", {})

    # Parse JSON bodies
    users = json.loads(users_raw.get("body", "[]")) if isinstance(users_raw.get("body"), str) else users_raw.get("body", [])
    posts = json.loads(posts_raw.get("body", "[]")) if isinstance(posts_raw.get("body"), str) else posts_raw.get("body", [])

    # Build user lookup
    user_map = {u["id"]: u for u in users}

    # Group posts by user
    user_posts = {}
    for post in posts:
        user_id = post["userId"]
        if user_id not in user_posts:
            user_posts[user_id] = []
        user_posts[user_id].append({
            "id": post["id"],
            "title": post["title"],
            "body_preview": post["body"][:100] + "..." if len(post["body"]) > 100 else post["body"],
        })

    # Merge data
    merged = []
    for user in users:
        user_data = {
            "user_id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "company": user["company"]["name"],
            "city": user["address"]["city"],
            "post_count": len(user_posts.get(user["id"], [])),
            "posts": user_posts.get(user["id"], []),
        }
        merged.append(user_data)

    # Sort by post count descending
    merged.sort(key=lambda x: x["post_count"], reverse=True)

    result = {
        "total_users": len(merged),
        "total_posts": len(posts),
        "users": merged[:5],  # Top 5 users by post count
    }

    # Store in workflow variables for downstream steps
    ctx.workflow_variables["user_posts_merged"] = json.dumps(result, indent=2)
    return ctx
