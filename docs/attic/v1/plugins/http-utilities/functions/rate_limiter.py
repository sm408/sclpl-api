"""
@name: rate_limiter
@type: http
@version: 1
@description: Rate limiting for requests using a token bucket algorithm

Config via workflow_variables: rate_limit_max_tokens, rate_limit_refill_rate,
rate_limit_refill_interval_ms.
"""

import time


_buckets: dict[str, dict] = {}


def _get_bucket(bucket_key: str, max_tokens: int, refill_rate: float, refill_interval_ms: float) -> dict:
    if bucket_key not in _buckets:
        _buckets[bucket_key] = {
            "tokens": max_tokens,
            "max_tokens": max_tokens,
            "refill_rate": refill_rate,
            "refill_interval_ms": refill_interval_ms,
            "last_refill": time.monotonic(),
        }
    return _buckets[bucket_key]


def _refill(bucket: dict) -> None:
    now = time.monotonic()
    elapsed_ms = (now - bucket["last_refill"]) * 1000
    intervals = elapsed_ms / bucket["refill_interval_ms"]
    new_tokens = intervals * bucket["refill_rate"]
    bucket["tokens"] = min(bucket["max_tokens"], bucket["tokens"] + new_tokens)
    bucket["last_refill"] = now


def run(ctx):
    max_tokens = int(ctx.workflow_variables.get("rate_limit_max_tokens", "10"))
    refill_rate = float(ctx.workflow_variables.get("rate_limit_refill_rate", "1"))
    refill_interval_ms = float(ctx.workflow_variables.get("rate_limit_refill_interval_ms", "1000"))
    bucket_key = ctx.workflow_variables.get("rate_limit_bucket", "default")

    bucket = _get_bucket(bucket_key, max_tokens, refill_rate, refill_interval_ms)
    _refill(bucket)

    if bucket["tokens"] >= 1:
        bucket["tokens"] -= 1
        return {
            "success": True,
            "allowed": True,
            "remaining_tokens": int(bucket["tokens"]),
        }

    wait_ms = bucket["refill_interval_ms"] / bucket["refill_rate"]
    return {
        "success": True,
        "allowed": False,
        "remaining_tokens": 0,
        "retry_after_ms": int(wait_ms),
        "message": "Rate limit exceeded",
    }
