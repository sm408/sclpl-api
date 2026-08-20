"""
@name: Process Content Data
@type: transformer
@version: 1

Processes posts data from JSONPlaceholder as simulated content/product listings.
Analyzes titles, groups by user, and extracts content metrics.

Input: fetch_posts step output (list of post objects)
Output: Content analysis with per-user grouping and title insights
"""

import json
import re
from collections import Counter


def run(ctx):
    posts_raw = ctx.step_outputs.get("fetch_posts", {})

    # Parse the JSON body
    body = posts_raw.get("body", "[]")
    if isinstance(body, str):
        try:
            posts = json.loads(body)
        except json.JSONDecodeError:
            posts = []
    else:
        posts = body if isinstance(body, list) else []

    if not posts:
        ctx.workflow_variables["processed_content"] = json.dumps({
            "error": "No post data received",
            "posts": [],
            "summary": {"total": 0},
        }, indent=2)
        return ctx

    # Group posts by user (provider)
    posts_by_user = {}
    for post in posts:
        user_id = post.get("userId")
        if user_id not in posts_by_user:
            posts_by_user[user_id] = []
        posts_by_user[user_id].append({
            "post_id": post.get("id"),
            "title": post.get("title", ""),
            "body_preview": _truncate(post.get("body", ""), 120),
            "word_count": len(post.get("body", "").split()),
        })

    # Analyze title patterns
    all_titles = [p.get("title", "") for p in posts]
    title_lengths = [len(t) for t in all_titles]
    word_freq = Counter()
    for title in all_titles:
        words = re.findall(r'\b[a-z]{3,}\b', title.lower())
        word_freq.update(words)

    # Per-user content summary
    user_content_summaries = []
    for user_id, user_posts in sorted(posts_by_user.items()):
        total_words = sum(p["word_count"] for p in user_posts)
        avg_title_len = sum(len(p["title"]) for p in user_posts) / len(user_posts) if user_posts else 0
        user_content_summaries.append({
            "user_id": user_id,
            "post_count": len(user_posts),
            "total_words": total_words,
            "avg_words_per_post": round(total_words / len(user_posts), 1) if user_posts else 0,
            "avg_title_length": round(avg_title_len, 1),
            "posts": user_posts[:5],  # Keep top 5 posts per user for brevity
        })

    # Sort by post count descending
    user_content_summaries.sort(key=lambda x: x["post_count"], reverse=True)

    summary = {
        "total": len(posts),
        "unique_users": len(posts_by_user),
        "avg_posts_per_user": round(len(posts) / len(posts_by_user), 1) if posts_by_user else 0,
        "avg_title_length": round(sum(title_lengths) / len(title_lengths), 1) if title_lengths else 0,
        "avg_body_word_count": round(sum(p.get("word_count", 0) for p in posts) / len(posts), 1) if posts else 0,
        "top_title_words": word_freq.most_common(10),
        "most_prolific_users": [
            {"user_id": u["user_id"], "post_count": u["post_count"]}
            for u in user_content_summaries[:5]
        ],
    }

    result = {
        "user_content": user_content_summaries,
        "summary": summary,
    }

    ctx.workflow_variables["processed_content"] = json.dumps(result, indent=2)
    return ctx


def _truncate(text, max_len):
    """Truncate text to max_len characters, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."
