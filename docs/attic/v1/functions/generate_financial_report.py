"""
@name: Generate Financial Report
@type: transformer
@version: 1

Generates a comprehensive financial report combining all market data.
Takes context from merge_prices and analyze_market steps.
"""

import json
from datetime import datetime


def run(ctx):
    prices_raw = ctx.workflow_variables.get("merged_prices", "{}")
    market_raw = ctx.workflow_variables.get("market_analysis", "{}")

    try:
        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
    except:
        prices = {}

    try:
        market = json.loads(market_raw) if isinstance(market_raw, str) else market_raw
    except:
        market = {}

    report = {
        "report_metadata": {
            "generated_at": datetime.now().isoformat(),
            "pipeline": "Financial Market Analysis",
            "version": "1.0",
            "data_source": "CoinGecko API",
        },
        "executive_summary": {
            "btc_price": prices.get("bitcoin", {}).get("price_usd", 0),
            "btc_change_24h": prices.get("bitcoin", {}).get("change_24h", 0),
            "eth_price": prices.get("ethereum", {}).get("price_usd", 0),
            "eth_change_24h": prices.get("ethereum", {}).get("change_24h", 0),
            "eth_btc_ratio": prices.get("eth_btc_ratio", 0),
            "total_market_cap": market.get("global_market", {}).get("total_market_cap_usd", 0),
            "btc_dominance": market.get("global_market", {}).get("btc_dominance", 0),
            "market_sentiment": market.get("market_sentiment", "unknown"),
        },
        "top_coins": market.get("top_coins", []),
        "market_overview": {
            "total_market_cap": market.get("global_market", {}).get("total_market_cap_usd", 0),
            "total_volume_24h": market.get("global_market", {}).get("total_volume_usd", 0),
            "active_cryptocurrencies": market.get("global_market", {}).get("active_cryptocurrencies", 0),
            "gainers": market.get("gainers_count", 0),
            "losers": market.get("losers_count", 0),
        },
        "insights": [
            f"Bitcoin is trading at ${prices.get('bitcoin', {}).get('price_usd', 0):,.2f} ({prices.get('bitcoin', {}).get('change_24h', 0):+.2f}% 24h)",
            f"Ethereum is trading at ${prices.get('ethereum', {}).get('price_usd', 0):,.2f} ({prices.get('ethereum', {}).get('change_24h', 0):+.2f}% 24h)",
            f"ETH/BTC ratio: {prices.get('eth_btc_ratio', 0):.6f}",
            f"Market sentiment: {market.get('market_sentiment', 'unknown').upper()}",
            f"BTC dominance: {market.get('global_market', {}).get('btc_dominance', 0):.1f}%",
        ],
    }

    ctx.workflow_variables["final_report"] = json.dumps(report, indent=2)
    return ctx
