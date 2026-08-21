"""
@name: Generate Monitor Report
@type: transformer
@version: 1

Generates a social media monitoring report from sentiment analysis data.
"""

import json
from datetime import datetime, timezone


def run(ctx):
    sentiment_raw = ctx.workflow_variables.get("sentiment_analysis", "{}")
    sentiment = json.loads(sentiment_raw) if isinstance(sentiment_raw, str) else sentiment_raw

    breakdown = sentiment.get("sentiment_breakdown", {})
    tweets = sentiment.get("tweets", [])

    top_positive = sorted(
        [t for t in tweets if t.get("sentiment") == "positive"],
        key=lambda t: t.get("confidence", 0),
        reverse=True,
    )[:5]

    top_negative = sorted(
        [t for t in tweets if t.get("sentiment") == "negative"],
        key=lambda t: t.get("confidence", 0),
        reverse=True,
    )[:5]

    report = {
        "report_title": "Social Media Sentiment Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_posts_analyzed": sentiment.get("total_analyzed", 0),
            "overall_sentiment": sentiment.get("overall", "unknown"),
            "positive_pct": sentiment.get("positive_pct", 0),
            "negative_pct": sentiment.get("negative_pct", 0),
            "neutral_pct": sentiment.get("neutral_pct", 0),
        },
        "breakdown": breakdown,
        "highlights": {
            "most_positive": [
                {"user": t.get("user"), "text": t.get("text"), "score": t.get("confidence")}
                for t in top_positive
            ],
            "most_negative": [
                {"user": t.get("user"), "text": t.get("text"), "score": t.get("confidence")}
                for t in top_negative
            ],
        },
        "recommendation": (
            "Engagement is mostly positive. Keep up the current content strategy."
            if sentiment.get("overall") == "positive"
            else "Negative sentiment detected. Review flagged posts and address concerns."
            if sentiment.get("overall") == "negative"
            else "Sentiment is neutral. Consider more engaging content to drive interaction."
        ),
    }

    ctx.workflow_variables["monitor_report"] = json.dumps(report, indent=2)
    return ctx
