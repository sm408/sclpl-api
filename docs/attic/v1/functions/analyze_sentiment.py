"""
@name: Analyze Sentiment
@type: transformer
@version: 1

Performs basic keyword-based sentiment analysis on fetched tweets.
Classifies each tweet as positive, negative, or neutral.
"""

import json
import re


POSITIVE_WORDS = {
    "good", "great", "awesome", "excellent", "love", "amazing", "wonderful",
    "fantastic", "happy", "best", "brilliant", "perfect", "beautiful", "enjoy",
    "excited", "thanks", "thank", "nice", "cool", "superb", "outstanding",
}

NEGATIVE_WORDS = {
    "bad", "terrible", "hate", "awful", "worst", "horrible", "ugly", "boring",
    "disappointed", "angry", "sad", "poor", "annoying", "stupid", "fail",
    "broken", "sucks", "waste", "ridiculous", "pathetic",
}


def _score_text(text):
    words = set(re.findall(r"[a-z]+", text.lower()))
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos > neg:
        return "positive", pos - neg
    elif neg > pos:
        return "negative", neg - pos
    return "neutral", 0


def run(ctx):
    tweets_raw = ctx.step_outputs.get("fetch_tweets", {})
    users_raw = ctx.step_outputs.get("fetch_users", {})

    tweets_body = json.loads(tweets_raw.get("body", "[]")) if isinstance(tweets_raw.get("body"), str) else tweets_raw.get("body", [])
    users_body = json.loads(users_raw.get("body", "[]")) if isinstance(users_raw.get("body"), str) else users_raw.get("body", [])

    if not isinstance(tweets_body, list):
        tweets_body = []
    if not isinstance(users_body, list):
        users_body = []

    user_map = {u.get("id"): u.get("name", "Unknown") for u in users_body if isinstance(u, dict)}

    analyzed = []
    counts = {"positive": 0, "negative": 0, "neutral": 0}

    for tweet in tweets_body:
        title = tweet.get("title", "")
        body = tweet.get("body", "")
        full_text = f"{title} {body}"
        sentiment, score = _score_text(full_text)
        counts[sentiment] += 1

        analyzed.append({
            "tweet_id": tweet.get("id"),
            "user": user_map.get(tweet.get("userId"), "Unknown"),
            "text": full_text.strip()[:120],
            "sentiment": sentiment,
            "confidence": score,
        })

    total = len(analyzed) or 1
    result = {
        "total_analyzed": len(analyzed),
        "sentiment_breakdown": {
            "positive": counts["positive"],
            "negative": counts["negative"],
            "neutral": counts["neutral"],
        },
        "positive_pct": round(counts["positive"] / total * 100, 1),
        "negative_pct": round(counts["negative"] / total * 100, 1),
        "neutral_pct": round(counts["neutral"] / total * 100, 1),
        "overall": "positive" if counts["positive"] > counts["negative"] else "negative" if counts["negative"] > counts["positive"] else "neutral",
        "tweets": analyzed,
    }

    ctx.workflow_variables["sentiment_analysis"] = json.dumps(result, indent=2)
    return ctx
