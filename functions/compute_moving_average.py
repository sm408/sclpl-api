"""
@name: Compute Moving Average
@type: transformer
@version: 1

Computes a 7-day moving average from parsed stock price data.
"""

import json


def run(ctx):
    prices_raw = ctx.workflow_variables.get("stock_prices", "[]")

    try:
        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
    except json.JSONDecodeError:
        prices = []

    closes = [p["close"] for p in prices if "close" in p]
    window = 7
    moving_avgs = []

    for i in range(len(closes)):
        if i < window - 1:
            moving_avgs.append(None)
        else:
            avg = sum(closes[i - window + 1 : i + 1]) / window
            moving_avgs.append(round(avg, 2))

    result = [
        {"timestamp": prices[i]["timestamp"], "close": closes[i], "ma7": moving_avgs[i]}
        for i in range(len(prices))
    ]

    ctx.workflow_variables["moving_averages"] = json.dumps(result)
    return ctx
