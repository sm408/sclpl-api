"""
@name: Generate Report
@type: transformer
@version: 1

Generates a comprehensive final report by combining data from all previous steps.
Takes context from merge_user_posts, post_analytics, and user_todo_summary steps.
"""

import json
from datetime import datetime


def run(ctx):
    # Get outputs from previous steps (stored as workflow variables)
    user_posts_raw = ctx.workflow_variables.get("user_posts_merged", "{}")
    analytics_raw = ctx.workflow_variables.get("analytics_result", "{}")
    todo_raw = ctx.workflow_variables.get("todo_summary", "{}")

    # Parse JSON outputs
    try:
        user_posts = json.loads(user_posts_raw) if isinstance(user_posts_raw, str) else user_posts_raw
    except:
        user_posts = {}

    try:
        analytics = json.loads(analytics_raw) if isinstance(analytics_raw, str) else analytics_raw
    except:
        analytics = {}

    try:
        todos = json.loads(todo_raw) if isinstance(todo_raw, str) else todo_raw
    except:
        todos = {}

    # Build comprehensive report
    report = {
        "report_metadata": {
            "generated_at": datetime.now().isoformat(),
            "pipeline": "Job Application Tracker",
            "version": "1.0",
        },
        "executive_summary": {
            "total_users": user_posts.get("total_users", 0),
            "total_posts": user_posts.get("total_posts", 0),
            "total_comments": analytics.get("summary", {}).get("total_comments", 0),
            "avg_comments_per_post": analytics.get("summary", {}).get("avg_comments_per_post", 0),
            "overall_todo_completion": todos.get("overall", {}).get("completion_rate", 0),
        },
        "user_engagement": {
            "top_contributors": [
                {
                    "name": u["name"],
                    "posts": u["post_count"],
                    "company": u["company"],
                }
                for u in user_posts.get("users", [])[:3]
            ],
        },
        "content_analytics": {
            "most_discussed_posts": analytics.get("top_commented_posts", [])[:3],
            "trending_topics": analytics.get("common_title_words", [])[:5],
        },
        "productivity": {
            "top_performers": todos.get("top_performers", [])[:3],
            "needs_attention": todos.get("needs_attention", []),
        },
        "insights": [
            f"Average of {analytics.get('summary', {}).get('avg_comments_per_post', 0)} comments per post indicates strong engagement",
            f"Overall todo completion rate is {todos.get('overall', {}).get('completion_rate', 0)}%",
            f"Top contributor has {user_posts.get('users', [{}])[0].get('post_count', 0)} posts" if user_posts.get("users") else "No user data available",
        ],
    }

    # Store the final report
    ctx.workflow_variables["final_report"] = json.dumps(report, indent=2)
    return ctx
