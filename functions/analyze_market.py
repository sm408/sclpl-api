"""
@name: Analyze Market
@type: transformer
@version: 1

Analyzes top coins and global market data.
Takes context from fetch_top_coins and fetch_global_market steps.
"""

import json


def run(ctx):
    coins_raw = ctx.step_outputs.get("fetch_top_coins", {})
    global_raw = ctx.step_outputs.get("fetch_global_market", {})

    coins_body = coins_raw.get("body", "[]")
    if isinstance(coins_body, str):
        coins_body = json.loads(coins_body)

    global_body = global_raw.get("body", "{}")
    if isinstance(global_body, str):
        global_body = json.loads(global_body)

    # Handle case where body might be wrapped in an object
    if isinstance(coins_body, dict):
        coins_body = coins_body.get("data", coins_body)

    global_data = global_body.get("data", global_body)

    top_coins = []
    if isinstance(coins_body, list):
        for coin in coins_body[:5]:
            top_coins.append({
                "name": coin.get("name", ""),
                "symbol": coin.get("symbol", "").upper(),
                "price": coin.get("current_price", 0),
                "change_24h": round(coin.get("price_change_percentage_24h", 0), 2),
                "market_cap": coin.get("market_cap", 0),
                "volume_24h": coin.get("total_volume", 0),
            })

    gainers = [c for c in top_coins if c["change_24h"] > 0]
    losers = [c for c in top_coins if c["change_24h"] < 0]

    result = {
        "global_market": {
            "total_market_cap_usd": global_data.get("total_market_cap", {}).get("usd", 0),
            "total_volume_usd": global_data.get("total_volume", {}).get("usd", 0),
            "btc_dominance": round(global_data.get("market_cap_percentage", {}).get("btc", 0), 2),
            "eth_dominance": round(global_data.get("market_cap_percentage", {}).get("eth", 0), 2),
            "active_cryptocurrencies": global_data.get("active_cryptocurrencies", 0),
        },
        "top_coins": top_coins,
        "gainers_count": len(gainers),
        "losers_count": len(losers),
        "market_sentiment": "bullish" if len(gainers) > len(losers) else "bearish" if len(losers) > len(gainers) else "neutral",
    }

    ctx.workflow_variables["market_analysis"] = json.dumps(result, indent=2)
    return ctx
