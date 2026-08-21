"""
@name: Post Analytics
@type: transformer
@version: 1

Calculates analytics from posts and comments data.
Takes context from fetch_posts and fetch_comments steps.
"""

import json
from collections import Counter


def run(ctx):
    posts_raw = ctx.step_outputs.get("fetch_posts", {})
    comments_raw = ctx.step_outputs.get("fetch_comments", {})

    posts = json.loads(posts_raw.get("body", "[]")) if isinstance(posts_raw.get("body"), str) else posts_raw.get("body", [])
    comments = json.loads(comments_raw.get("body", "[]")) if isinstance(comments_raw.get("body"), str) else comments_raw.get("body", [])

    # Count comments per post
    comments_per_post = Counter()
    for comment in comments:
        comments_per_post[comment["postId"]] += 1

    # Calculate statistics
    total_posts = len(posts)
    total_comments = len(comments)
    avg_comments = total_comments / total_posts if total_posts > 0 else 0

    # Find most commented posts
    top_posts = comments_per_post.most_common(5)
    top_post_details = []
    for post_id, count in top_posts:
        post = next((p for p in posts if p["id"] == post_id), None)
        if post:
            top_post_details.append({
                "post_id": post_id,
                "title": post["title"][:60] + "..." if len(post["title"]) > 60 else post["title"],
                "comment_count": count,
                "author_id": post["userId"],
            })

    # Posts per user
    posts_per_user = Counter()
    for post in posts:
        posts_per_user[post["userId"]] += 1

    # Title word analysis
    word_counter = Counter()
    for post in posts:
        words = post["title"].lower().split()
        word_counter.update(words)

    common_words = word_counter.most_common(10)

    result = {
        "summary": {
            "total_posts": total_posts,
            "total_comments": total_comments,
            "avg_comments_per_post": round(avg_comments, 2),
            "unique_authors": len(posts_per_user),
        },
        "top_commented_posts": top_post_details,
        "posts_per_user": dict(posts_per_user.most_common(5)),
        "common_title_words": [{"word": w, "count": c} for w, c in common_words],
    }

    # Store in workflow variables for downstream steps
    ctx.workflow_variables["analytics_result"] = json.dumps(result, indent=2)
    return ctx
