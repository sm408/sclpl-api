"""
@name: Merge Crypto Prices
@type: transformer
@version: 1

Merges Bitcoin and Ethereum price data into a combined view.
Takes context from fetch_bitcoin and fetch_ethereum steps.
"""

import json


def run(ctx):
    btc_raw = ctx.step_outputs.get("fetch_bitcoin", {})
    eth_raw = ctx.step_outputs.get("fetch_ethereum", {})

    btc_body = json.loads(btc_raw.get("body", "{}")) if isinstance(btc_raw.get("body"), str) else btc_raw.get("body", {})
    eth_body = json.loads(eth_raw.get("body", "{}")) if isinstance(eth_raw.get("body"), str) else eth_raw.get("body", {})

    btc = btc_body.get("bitcoin", {})
    eth = eth_body.get("ethereum", {})

    result = {
        "bitcoin": {
            "price_usd": btc.get("usd", 0),
            "change_24h": round(btc.get("usd_24h_change", 0), 2),
            "market_cap": btc.get("usd_market_cap", 0),
        },
        "ethereum": {
            "price_usd": eth.get("usd", 0),
            "change_24h": round(eth.get("usd_24h_change", 0), 2),
            "market_cap": eth.get("usd_market_cap", 0),
        },
        "eth_btc_ratio": round(eth.get("usd", 0) / btc.get("usd", 1), 6) if btc.get("usd") else 0,
        "total_market_cap": btc.get("usd_market_cap", 0) + eth.get("usd_market_cap", 0),
    }

    ctx.workflow_variables["merged_prices"] = json.dumps(result, indent=2)
    return ctx
