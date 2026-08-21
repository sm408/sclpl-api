"""
@name: Parse Stock Prices
@type: transformer
@version: 1

Parses raw stock price data from Yahoo Finance API response.
"""

import json


def run(ctx):
    raw = ctx.step_outputs.get("fetch_stock_data", {})
    body = raw.get("body", "") if isinstance(raw.get("body"), str) else json.dumps(raw.get("body", ""))

    try:
        data = json.loads(body) if isinstance(body, str) else body
        result = chart = data.get("chart", {}).get("result", [{}])[0]
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {}).get("quote", [{}])[0]
        closes = indicators.get("close", [])

        prices = []
        for ts, close in zip(timestamps, closes):
            if close is not None:
                prices.append({"timestamp": ts, "close": close})

        ctx.workflow_variables["stock_prices"] = json.dumps(prices)
    except (json.JSONDecodeError, IndexError, KeyError):
        ctx.workflow_variables["stock_prices"] = "[]"

    return ctx
