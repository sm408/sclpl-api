"""
@name: Generate Comparison Report
@type: transformer
@version: 1

Generates a comprehensive comparison report by aggregating processed data
from all three parallel processing steps (providers, content, tasks).

Input: processed_providers, processed_content, processed_tasks workflow variables
Output: Final comparison report with cross-source insights
"""

import json
from datetime import datetime


def run(ctx):
    # Retrieve outputs from all parallel processing steps
    providers_raw = ctx.workflow_variables.get("processed_providers", "{}")
    content_raw = ctx.workflow_variables.get("processed_content", "{}")
    tasks_raw = ctx.workflow_variables.get("processed_tasks", "{}")

    # Safely parse each source
    providers = _safe_parse(providers_raw)
    content = _safe_parse(content_raw)
    tasks = _safe_parse(tasks_raw)

    provider_summary = providers.get("summary", {})
    content_summary = content.get("summary", {})
    task_summary = tasks.get("summary", {})

    # Build cross-source correlation
    provider_list = providers.get("providers", [])
    user_content = content.get("user_content", [])
    user_tasks = tasks.get("user_tasks", [])

    # Index by user_id for correlation
    provider_by_id = {p["provider_id"]: p for p in provider_list}
    content_by_id = {u["user_id"]: u for u in user_content}
    task_by_id = {u["user_id"]: u for u in user_tasks}

    # Build unified user profiles
    all_user_ids = sorted(set(
        list(provider_by_id.keys()) +
        list(content_by_id.keys()) +
        list(task_by_id.keys())
    ))

    user_profiles = []
    for uid in all_user_ids:
        provider = provider_by_id.get(uid, {})
        content_info = content_by_id.get(uid, {})
        task_info = task_by_id.get(uid, {})

        user_profiles.append({
            "user_id": uid,
            "name": provider.get("name", f"User {uid}"),
            "company": provider.get("company", {}).get("name", ""),
            "city": provider.get("location", {}).get("city", ""),
            "content": {
                "post_count": content_info.get("post_count", 0),
                "total_words": content_info.get("total_words", 0),
                "avg_words_per_post": content_info.get("avg_words_per_post", 0),
            },
            "tasks": {
                "total": task_info.get("total_tasks", 0),
                "completed": task_info.get("completed", 0),
                "completion_rate": task_info.get("completion_rate", 0),
                "tier": task_info.get("productivity_tier", "unknown"),
            },
        })

    # Sort by combined engagement (posts + tasks)
    user_profiles.sort(
        key=lambda x: x["content"]["post_count"] + x["tasks"]["total"],
        reverse=True,
    )

    # Build the final report
    report = {
        "report_metadata": {
            "generated_at": datetime.now().isoformat(),
            "pipeline": "Multi-Provider Price Aggregator",
            "version": "1.0",
            "data_sources": ["users", "posts", "todos"],
        },
        "executive_summary": {
            "total_providers": provider_summary.get("total", 0),
            "total_content_items": content_summary.get("total", 0),
            "total_tasks": task_summary.get("total", 0),
            "overall_completion_rate": task_summary.get("overall_completion_rate", 0),
            "avg_posts_per_user": content_summary.get("avg_posts_per_user", 0),
            "unique_cities": provider_summary.get("unique_cities", 0),
            "unique_companies": provider_summary.get("unique_companies", 0),
        },
        "provider_overview": {
            "total": provider_summary.get("total", 0),
            "top_cities": provider_summary.get("top_cities", []),
            "top_companies": provider_summary.get("top_companies", []),
            "with_website": provider_summary.get("providers_with_website", 0),
            "with_phone": provider_summary.get("providers_with_phone", 0),
        },
        "content_analysis": {
            "total_posts": content_summary.get("total", 0),
            "avg_title_length": content_summary.get("avg_title_length", 0),
            "avg_body_word_count": content_summary.get("avg_body_word_count", 0),
            "top_title_words": content_summary.get("top_title_words", [])[:5],
            "most_prolific_users": content_summary.get("most_prolific_users", [])[:3],
        },
        "task_productivity": {
            "total_tasks": task_summary.get("total", 0),
            "completed": task_summary.get("completed", 0),
            "pending": task_summary.get("pending", 0),
            "overall_rate": task_summary.get("overall_completion_rate", 0),
            "distribution": task_summary.get("productivity_distribution", {}),
            "top_performers": task_summary.get("top_performers", [])[:3],
            "needs_attention": task_summary.get("needs_attention", [])[:3],
        },
        "cross_source_insights": _build_insights(provider_summary, content_summary, task_summary, user_profiles),
        "top_user_profiles": user_profiles[:5],
    }

    ctx.workflow_variables["final_report"] = json.dumps(report, indent=2)
    return ctx


def _safe_parse(raw):
    """Safely parse a JSON string, returning empty dict on failure."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


def _build_insights(provider_summary, content_summary, task_summary, user_profiles):
    """Generate cross-source insights from aggregated data."""
    insights = []

    total_providers = provider_summary.get("total", 0)
    total_posts = content_summary.get("total", 0)
    total_tasks = task_summary.get("total", 0)
    completion_rate = task_summary.get("overall_completion_rate", 0)

    # Content volume insight
    if total_providers > 0:
        avg_posts = total_posts / total_providers
        insights.append(
            f"Average of {avg_posts:.1f} content items per provider across {total_providers} providers"
        )

    # Task completion insight
    insights.append(
        f"Overall task completion rate is {completion_rate}% "
        f"({task_summary.get('completed', 0)}/{total_tasks})"
    )

    # Top performer insight
    if user_profiles:
        top = user_profiles[0]
        insights.append(
            f"Top engaged user: {top['name']} with "
            f"{top['content']['post_count']} posts and "
            f"{top['tasks']['completion_rate']}% task completion"
        )

    # Geographic distribution
    unique_cities = provider_summary.get("unique_cities", 0)
    if unique_cities > 0:
        insights.append(
            f"Providers span {unique_cities} unique cities, "
            f"demonstrating wide geographic distribution"
        )

    # Productivity distribution
    dist = task_summary.get("productivity_distribution", {})
    if dist:
        high = dist.get("high", 0)
        low = dist.get("low", 0)
        if high > low:
            insights.append("Majority of users show high productivity (80%+ completion)")
        elif low > high:
            insights.append("Majority of users need productivity support (<50% completion)")
        else:
            insights.append("Productivity is evenly distributed across tiers")

    return insights
