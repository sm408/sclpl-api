# SCLPLAPI Enthusiast Showcase

This guide is for the builder who wants to push SCLPLAPI to its limits — building complex integration platforms, mastering advanced patterns, and contributing back to the project.

---

## Table of Contents

1. [Showcase: Building a Full API Integration Platform](#showcase-building-a-full-api-integration-platform)
2. [Advanced Patterns](#advanced-patterns)
3. [Real-World Use Case: Multi-Provider Data Aggregation](#real-world-use-case-multi-provider-data-aggregation)
4. [Performance Optimization Tips](#performance-optimization-tips)
5. [Extending SCLPLAPI at the Core](#extending-sclplapi-at-the-core)
6. [Building Custom Exporters](#building-custom-exporters)
7. [Community Contribution Guide](#community-contribution-guide)
8. [Project Roadmap](#project-roadmap)

---

## Showcase: Building a Full API Integration Platform

### The Vision

Imagine building a personal API integration platform that:

- Aggregates data from 10+ providers
- Runs daily on a schedule
- Produces consolidated reports
- Alerts on anomalies
- All defined in readable `.sclpll` files

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SCLPLAPI Platform                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Weather    │  │   Finance    │  │   Social     │  │
│  │   Pipeline   │  │   Pipeline   │  │   Pipeline   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│         └─────────────────┼─────────────────┘           │
│                           │                             │
│                    ┌──────▼───────┐                     │
│                    │  Aggregator  │                     │
│                    │   Function   │                     │
│                    └──────┬───────┘                     │
│                           │                             │
│              ┌────────────┼────────────┐                │
│              │            │            │                │
│       ┌──────▼─────┐ ┌───▼────┐ ┌─────▼──────┐        │
│       │ JSON Report│ │  CSV   │ │  Dashboard  │        │
│       │            │ │ Export │ │   Export    │        │
│       └────────────┘ └────────┘ └────────────┘         │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Event Bus (in-process)               │   │
│  │  workflow.completed → trigger_next → alert        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Step-by-Step Build

#### Phase 1: Define Your Data Sources

Create a SCLPLL script for each data domain:

**weather_pipeline.sclpll**:
```sclpll
@workflow weather "Weather Data Pipeline"
    Fetches weather for multiple cities in parallel.

@base_url https://wttr.in

@step fetch_nyc -> nyc_data
    request GET {{base_url}}/NewYork?format=j1

@step fetch_london -> london_data
    request GET {{base_url}}/London?format=j1

@step fetch_tokyo -> tokyo_data
    request GET {{base_url}}/Tokyo?format=j1

@step extract_all <- fetch_nyc, fetch_london, fetch_tokyo -> weather_summary
    func Extract Multi-City Weather

@step export <- weather_summary -> output
    func Export Weather Report
```

**finance_pipeline.sclpll**:
```sclpll
@workflow finance "Financial Data Pipeline"
    Fetches crypto and stock data in parallel.

@base_url https://api.coingecko.com/api/v3

@step fetch_btc -> btc_data
    request GET {{base_url}}/simple/price?ids=bitcoin&vs_currencies=usd,eur

@step fetch_eth -> eth_data
    request GET {{base_url}}/simple/price?ids=ethereum&vs_currencies=usd,eur

@step fetch_sol -> sol_data
    request GET {{base_url}}/simple/price?ids=solana&vs_currencies=usd,eur

@step merge <- fetch_btc, fetch_eth, fetch_sol -> crypto_prices
    func Merge Crypto Prices

@step analyze <- crypto_prices -> analysis
    func Analyze Crypto Trends

@step export <- analysis -> output
    func Export Finance Report
```

#### Phase 2: Build Your Function Library

**functions/transformers/extract_multi_city.py**:
```python
"""
@name: Extract Multi-City Weather
@type: transformer
@version: 1
"""

def run(ctx):
    cities = ["nyc", "london", "tokyo"]
    summary = {}

    for city in cities:
        raw = ctx.runtime.get(f"fetch_{city}", {})
        current = raw.get("current_condition", [{}])[0]
        summary[city] = {
            "temp_c": current.get("temp_C", "N/A"),
            "humidity": current.get("humidity", "N/A"),
            "description": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
            "wind_kmph": current.get("windspeedKmph", "N/A"),
        }

    ctx.workflow_variables["weather_summary"] = summary
    return ctx
```

**functions/transformers/merge_crypto.py**:
```python
"""
@name: Merge Crypto Prices
@type: transformer
@version: 1
"""

from datetime import datetime

def run(ctx):
    btc = ctx.runtime.get("fetch_btc", {})
    eth = ctx.runtime.get("fetch_eth", {})
    sol = ctx.runtime.get("fetch_sol", {})

    merged = {
        "timestamp": datetime.utcnow().isoformat(),
        "bitcoin": {
            "usd": btc.get("bitcoin", {}).get("usd", 0),
            "eur": btc.get("bitcoin", {}).get("eur", 0),
        },
        "ethereum": {
            "usd": eth.get("ethereum", {}).get("usd", 0),
            "eur": eth.get("ethereum", {}).get("eur", 0),
        },
        "solana": {
            "usd": sol.get("solana", {}).get("usd", 0),
            "eur": sol.get("solana", {}).get("eur", 0),
        },
    }

    ctx.workflow_variables["crypto_prices"] = merged
    return ctx
```

**functions/transformers/analyze_crypto.py**:
```python
"""
@name: Analyze Crypto Trends
@type: transformer
@version: 1
"""

def run(ctx):
    prices = ctx.workflow_variables.get("crypto_prices", {})

    btc_usd = prices.get("bitcoin", {}).get("usd", 0)
    eth_usd = prices.get("ethereum", {}).get("usd", 0)

    analysis = {
        "btc_eth_ratio": round(btc_usd / eth_usd, 2) if eth_usd else 0,
        "total_market_usd": sum(
            v.get("usd", 0) for v in [prices.get("bitcoin", {}), prices.get("ethereum", {}), prices.get("solana", {})]
        ),
        "price_tiers": {
            "premium": btc_usd > 50000,
            "mid_range": 1000 < eth_usd < 5000,
        },
    }

    ctx.workflow_variables["crypto_analysis"] = analysis
    return ctx
```

#### Phase 3: Create a Master Runner

```python
# run_platform.py
import asyncio
from pathlib import Path

async def run_all_pipelines():
    pipelines = [
        "weather_pipeline.sclpll",
        "finance_pipeline.sclpll",
    ]

    tasks = []
    for pipeline in pipelines:
        script_path = Path("scripts") / pipeline
        if script_path.exists():
            tasks.append(run_pipeline(script_path))

    # Run all pipelines in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for pipeline, result in zip(pipelines, results):
        if isinstance(result, Exception):
            print(f"[FAIL] {pipeline}: {result}")
        else:
            print(f"[OK]   {pipeline}: completed")

if __name__ == "__main__":
    asyncio.run(run_all_pipelines())
```

#### Phase 4: Schedule It

```bash
# Daily at 6 AM
0 6 * * * cd /path/to/sclpl-api && python run_platform.py >> logs/platform.log 2>&1
```

---

## Advanced Patterns

### Pattern 1: Conditional Branching

Execute different steps based on response data:

```python
"""
@name: Conditional Router
@type: transformer
@version: 1
"""

def run(ctx):
    data = ctx.response.json()
    temperature = data.get("current_condition", [{}])[0].get("temp_C", "0")

    if int(temperature) > 30:
        ctx.workflow_variables["next_action"] = "send_heat_alert"
    elif int(temperature) < 0:
        ctx.workflow_variables["next_action"] = "send_cold_alert"
    else:
        ctx.workflow_variables["next_action"] = "log_normal"

    return ctx
```

### Pattern 2: Retry with Backoff

```python
"""
@name: Resilient Fetcher
@type: pre_request
@version: 1
"""

import time

def run(ctx):
    retry_count = ctx.runtime.get("retry_count", 0)
    if retry_count > 0:
        wait = min(2 ** retry_count, 30)  # Exponential backoff, max 30s
        time.sleep(wait)

    ctx.runtime["retry_count"] = retry_count + 1
    return ctx
```

### Pattern 3: Data Normalization Pipeline

Chain multiple transformers to normalize messy API responses:

```sclpll
@workflow normalize-pipeline "Data Normalization"

@step fetch_source_a -> raw_a
    request GET https://api-a.com/users

@step fetch_source_b -> raw_b
    request GET https://api-b.com/contacts

@step normalize_a <- raw_a -> norm_a
    func Normalize Source A

@step normalize_b <- raw_b -> norm_b
    func Normalize Source B

@step merge <- norm_a, norm_b -> unified
    func Merge Normalized Data

@step validate <- unified -> validated
    func Validate Schema

@step export <- validated -> output
    func Export Unified Dataset
```

### Pattern 4: Incremental Processing

Process data in batches, accumulating results:

```python
"""
@name: Incremental Accumulator
@type: transformer
@version: 1
"""

import json
from pathlib import Path

def run(ctx):
    state_file = Path("data/accumulator_state.json")

    # Load previous state
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
    else:
        state = {"processed_ids": [], "accumulated": []}

    # Get new data
    new_data = ctx.response.json()

    # Filter already-processed items
    new_items = [
        item for item in new_data
        if item["id"] not in state["processed_ids"]
    ]

    # Accumulate
    state["processed_ids"].extend(item["id"] for item in new_items)
    state["accumulated"].extend(new_items)

    # Save state
    state_file.parent.mkdir(exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    ctx.workflow_variables["new_items"] = new_items
    ctx.workflow_variables["total_processed"] = len(state["processed_ids"])
    return ctx
```

### Pattern 5: Webhook-Triggered Pipelines

```python
"""
@name: Webhook Handler
@type: post_response
@version: 1
"""

import json
from pathlib import Path

def run(ctx):
    # Write trigger event to a queue file
    queue_dir = Path("data/webhook_queue")
    queue_dir.mkdir(exist_ok=True)

    event = {
        "source": ctx.request.get("url"),
        "payload": ctx.response.json(),
        "timestamp": ctx.metadata.get("execution_time"),
    }

    event_file = queue_dir / f"event_{ctx.metadata.get('step_id', 'unknown')}.json"
    with open(event_file, "w") as f:
        json.dump(event, f, indent=2)

    return ctx
```

---

## Real-World Use Case: Multi-Provider Data Aggregation

### Problem

You need to build a unified product catalog by aggregating data from 3 different supplier APIs, each with different schemas, rate limits, and response formats.

### Solution Architecture

```
Supplier A (REST/JSON)  ──┐
                           ├──▶ Normalize ──▶ Merge ──▶ Validate ──▶ Export
Supplier B (REST/XML)   ──┤
                           │
Supplier C (GraphQL)     ──┘
```

### Implementation

**Step 1: Define the workflow**

```sclpll
@workflow product-catalog "Unified Product Catalog"
    Aggregates products from 3 suppliers into a single catalog.

@var supplier_a_url = https://api.supplier-a.com/v2/products
@var supplier_b_url = https://api.supplier-b.com/v1/catalog
@var supplier_c_url = https://api.supplier-c.com/graphql

@step fetch_supplier_a -> raw_a
    request GET {{supplier_a_url}}
    header Accept: application/json

@step fetch_supplier_b -> raw_b
    request GET {{supplier_b_url}}
    header Accept: application/xml

@step fetch_supplier_c -> raw_c
    request POST {{supplier_c_url}}
    header Content-Type: application/json
    body {"query": "{ products { id name price currency } }"}

@step normalize_a <- raw_a -> products_a
    func Normalize Supplier A

@step normalize_b <- raw_b -> products_b
    func Normalize Supplier B

@step normalize_c <- raw_c -> products_c
    func Normalize Supplier C

@step merge <- normalize_a, normalize_b, normalize_c -> all_products
    func Merge Product Catalogs

@step validate <- merge -> validated
    func Validate Product Schema

@step dedup <- validate -> unique
    func Deduplicate Products

@step export <- dedup -> catalog
    func Export Product Catalog
```

**Step 2: Write normalizers**

Each normalizer maps the supplier's schema to a common format:

```python
# functions/transformers/normalize_supplier_a.py
"""
@name: Normalize Supplier A
@type: transformer
@version: 1
"""

def run(ctx):
    raw = ctx.response.json()
    products = []
    for item in raw.get("items", []):
        products.append({
            "id": f"A-{item['sku']}",
            "name": item["title"],
            "price": item["pricing"]["amount"],
            "currency": item["pricing"]["currency"],
            "supplier": "supplier-a",
            "category": item.get("category", "uncategorized"),
        })
    ctx.workflow_variables["products_a"] = products
    return ctx
```

**Step 3: Write the deduplicator**

```python
# functions/transformers/deduplicate.py
"""
@name: Deduplicate Products
@type: transformer
@version: 1
"""

from collections import defaultdict

def run(ctx):
    products = ctx.workflow_variables.get("validated_products", [])

    # Group by normalized name
    by_name = defaultdict(list)
    for p in products:
        key = p["name"].lower().strip()
        by_name[key].append(p)

    # Keep the cheapest version of each product
    deduped = []
    for name, variants in by_name.items():
        cheapest = min(variants, key=lambda x: x["price"])
        cheapest["variants"] = len(variants)
        deduped.append(cheapest)

    ctx.workflow_variables["unique_products"] = deduped
    return ctx
```

**Step 4: Run and iterate**

```bash
python -m app.core.engine.sclpll_cli run product_catalog.sclpll --verbose
```

---

## Performance Optimization Tips

### 1. Maximize Parallelism

Structure workflows so independent steps have no dependencies:

```sclpll
# GOOD: All 4 fetches run in parallel
@step fetch_a -> data_a
@step fetch_b -> data_b
@step fetch_c -> data_c
@step fetch_d -> data_d

# BAD: Sequential when parallel is possible
@step fetch_a -> data_a
@step fetch_b <- fetch_a -> data_b  # Unnecessary dependency!
```

### 2. Minimize Data in Context

Only pass what downstream steps need:

```python
# GOOD: Extract only needed fields
def run(ctx):
    full_response = ctx.response.json()
    ctx.workflow_variables["user_count"] = len(full_response["users"])
    return ctx

# BAD: Store entire response when you only need a count
def run(ctx):
    ctx.workflow_variables["full_users"] = ctx.response.json()
    return ctx
```

### 3. Use Streaming for Large Responses

```python
"""
@name: Stream Large Dataset
@type: post_response
@version: 1
"""

import json

def run(ctx):
    # Process in chunks instead of loading everything into memory
    data = ctx.response.json()
    chunk_size = 1000
    processed = []

    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        processed.extend(transform_chunk(chunk))

    ctx.workflow_variables["processed"] = processed
    return ctx
```

### 4. Cache Expensive Computations

```python
"""
@name: Cached Transformer
@type: transformer
@version: 1
"""

import json
import hashlib
from pathlib import Path

def run(ctx):
    cache_dir = Path("data/cache")
    cache_dir.mkdir(exist_ok=True)

    # Create cache key from input
    input_data = json.dumps(ctx.response.json(), sort_keys=True)
    cache_key = hashlib.md5(input_data.encode()).hexdigest()
    cache_file = cache_dir / f"{cache_key}.json"

    if cache_file.exists():
        with open(cache_file) as f:
            ctx.workflow_variables["cached_result"] = json.load(f)
        return ctx

    # Expensive computation
    result = expensive_transform(ctx.response.json())

    with open(cache_file, "w") as f:
        json.dump(result, f)

    ctx.workflow_variables["cached_result"] = result
    return ctx
```

### 5. Connection Pooling

For workflows with many requests to the same host, reuse connections:

```python
import httpx

# Reuse client across requests
client = httpx.AsyncClient(
    base_url="https://api.example.com",
    timeout=30.0,
    limits=httpx.Limits(max_connections=10),
)
```

---

## Extending SCLPLAPI at the Core

### Adding a New Execution Strategy

The workflow engine supports pluggable execution strategies:

```python
# app/core/engine/strategies/batch_strategy.py
from app.core.contracts.execution_strategy import ExecutionStrategy

class BatchExecutionStrategy(ExecutionStrategy):
    """Execute steps in fixed-size batches."""

    def __init__(self, batch_size: int = 5):
        self.batch_size = batch_size

    async def execute(self, graph, ctx):
        while graph.has_pending():
            ready = graph.get_ready_steps()[:self.batch_size]
            results = await asyncio.gather(*[
                self.execute_step(step, ctx) for step in ready
            ])
            for step, result in zip(ready, results):
                ctx.set_step_output(step.id, result)
                graph.mark_complete(step.id)
```

### Adding a New Variable Source

```python
# app/core/variable_sources/vault_source.py
from app.core.contracts.variable_source import VariableSource

class VaultVariableSource(VariableSource):
    """Read variables from a secrets vault."""

    def __init__(self, vault_path: str):
        self.vault_path = vault_path

    def get(self, key: str) -> str | None:
        # Implement vault lookup
        ...
```

### Adding a New Event Type

```python
# app/core/events/custom_events.py
from dataclasses import dataclass

@dataclass
class StepRetryEvent:
    step_id: str
    attempt: int
    max_attempts: int
    error: str

# Emit in engine
bus.emit("step.retrying", StepRetryEvent(
    step_id=step.id,
    attempt=retry_count,
    max_attempts=max_retries,
    error=str(exc),
))
```

---

## Building Custom Exporters

### Export to Markdown Report

```python
"""
@name: Export Markdown Report
@type: exporter
@version: 1
"""

from datetime import datetime
from pathlib import Path

def run(ctx):
    data = ctx.workflow_variables.get("analysis", {})
    output_dir = Path("output/reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    report = f"""# Analysis Report
Generated: {datetime.now().isoformat()}

## Summary
- Total items: {data.get('total_items', 0)}
- Processed: {data.get('processed', 0)}
- Errors: {data.get('errors', 0)}

## Details
| Metric | Value |
|--------|-------|
| Avg Response Time | {data.get('avg_response_ms', 'N/A')} ms |
| Success Rate | {data.get('success_rate', 'N/A')}% |
| Data Points | {data.get('data_points', 0)} |

## Recommendations
{chr(10).join(f'- {r}' for r in data.get('recommendations', []))}
"""

    report_path = output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_path, "w") as f:
        f.write(report)

    ctx.workflow_variables["report_path"] = str(report_path)
    return ctx
```

### Export to SQLite

```python
"""
@name: Export to SQLite
@type: exporter
@version: 1
"""

import sqlite3
from pathlib import Path

def run(ctx):
    data = ctx.workflow_variables.get("final_data", [])
    db_path = Path("data/exports.db")

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            source TEXT,
            data TEXT
        )
    """)

    for item in data:
        conn.execute(
            "INSERT INTO exports (timestamp, source, data) VALUES (?, ?, ?)",
            (item.get("timestamp"), item.get("source"), str(item))
        )

    conn.commit()
    conn.close()

    ctx.workflow_variables["db_path"] = str(db_path)
    return ctx
```

---

## Community Contribution Guide

### How to Contribute

1. **Fork the repository**
2. **Pick an issue** from the roadmap or propose a new feature
3. **Follow the layer rules** (UI -> Services -> Core -> Storage)
4. **Write tests** for your changes
5. **Update documentation** if architecture changes
6. **Submit a PR** with a clear description

### Contribution Areas

| Area | Difficulty | Impact |
|------|-----------|--------|
| New SCLPLL keywords | Medium | High |
| Additional step types | Medium | High |
| Export formats | Easy | Medium |
| Function examples | Easy | High |
| Test coverage | Easy | High |
| Documentation | Easy | Medium |
| Performance optimization | Hard | Medium |
| UI components | Hard | Medium |

### Code Review Checklist

- [ ] Layer direction respected (no upward imports)
- [ ] Core remains UI-independent
- [ ] Typed contracts used (dataclasses/Pydantic)
- [ ] Async discipline followed (no blocking in async)
- [ ] Tests written and passing
- [ ] Documentation updated if needed
- [ ] File size under 700 LOC (soft limit)

### Getting Help

- Read `AGENTS.md` for project rules
- Read `ARCHITECTURE.md` for layer model
- Read `CODING_STANDARDS.md` for formatting and style
- Check `examples/` for working pipeline patterns

---

## Project Roadmap

### Current State

- Documentation-first repository
- Architecture fully defined
- SCLPLL language specified
- 3 working example pipelines
- Core contracts and models designed

### Near-Term Priorities

1. Full workflow engine implementation
2. SQLite persistence with migrations
3. CLI with 13+ commands
4. Function discovery system
5. Export engine (JSON, CSV)

### Medium-Term Goals

1. Visual workflow builder (deferred until runtime is stable)
2. Plugin ecosystem
3. Analytics pane
4. Secrets vault
5. Headless mode for CI/CD

### Long-Term Vision

1. Distributed execution
2. Remote sync
3. Enterprise role systems
4. Marketplace for workflow templates

---

## Next Steps

- **Get Started**: [User Guide](../user/README.md)
- **Contribute**: [Developer Guide](../developer/README.md)
- **Position**: [Sales & Marketing Guide](../sales-marketing/README.md)
- **Deep Dive**: [Workflow Engine](../../../WORKFLOW_ENGINE.md)
- **Architecture**: [ARCHITECTURE.md](../../../ARCHITECTURE.md)
- **Examples**: `examples/` directory (weather, job tracker, financial)
