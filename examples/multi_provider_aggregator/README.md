# Multi-Provider Price Aggregator

A multi-step parallel pipeline example demonstrating nested data processing and result aggregation in SCLPLAPI.

## Overview

This pipeline fetches data from three endpoints of the JSONPlaceholder API simultaneously, processes each dataset in parallel with specialized transformers, and aggregates all results into a comprehensive comparison report with cross-source insights.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      PARALLEL EXECUTION                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │1. Users  │  │2. Posts  │  │3. Todos  │   Phase 1: Fetch     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                      │
│       │              │              │                            │
│  ┌────▼─────┐  ┌─────▼────┐  ┌─────▼────┐                      │
│  │4. Process│  │5. Process│  │6. Process│   Phase 2: Transform  │
│  │Providers │  │Content   │  │Tasks     │                       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                      │
│       │              │              │                            │
│       └──────────────┼──────────────┘                            │
│                      │                                          │
│               ┌──────▼──────┐                                   │
│               │7. Aggregate │              Phase 3: Report      │
│               │  & Compare  │                                   │
│               └─────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Execution Flow

### Phase 1: Parallel Fetch (Steps 1-3)
All three API calls run concurrently since they have no dependencies:
- Fetch users from `/users` — treated as provider/product data
- Fetch posts from `/posts` — treated as content/listing data
- Fetch todos from `/todos` — treated as task/completion data

### Phase 2: Parallel Processing (Steps 4-6)
Three processing steps run concurrently, each handling one data source:
- **Process Provider Data**: Extracts provider profiles, calculates location and company metrics
- **Process Content Data**: Analyzes post titles, groups by user, extracts word frequency
- **Process Task Data**: Calculates completion rates per user, classifies productivity tiers

### Phase 3: Aggregation (Step 7)
Combines all processed data into a unified report:
- Cross-source user profiles (content + tasks per provider)
- Executive summary with metrics from all three sources
- Generated insights that correlate data across sources

## Running

```bash
python examples/multi_provider_aggregator/run.py
```

## Output

The pipeline generates:
- Console output with execution timeline and summary
- `output/comparison_report.json` — Full comparison report

## Key Patterns Demonstrated

1. **Parallel fetches**: Three independent API calls run concurrently
2. **Parallel processing**: Each processor handles a different data structure
3. **Nested data extraction**: Functions traverse nested JSON (address.geo, company.name)
4. **Aggregation**: Final step merges heterogeneous data by user ID
5. **Cross-source insights**: Report generation correlates metrics across all sources
6. **Safe JSON parsing**: All functions handle both string and pre-parsed bodies
7. **Edge case handling**: Empty data, missing fields, and division-by-zero guards

## Functions

| Function | File | Purpose |
|---|---|---|
| Process Provider Data | `functions/process_provider_data.py` | Extract provider profiles from user data |
| Process Content Data | `functions/process_content_data.py` | Analyze posts, group by user, extract metrics |
| Process Task Data | `functions/process_task_data.py` | Calculate task completion rates and tiers |
| Generate Comparison Report | `functions/generate_comparison_report.py` | Aggregate all sources into final report |

## API Used

[JSONPlaceholder](https://jsonplaceholder.typicode.com/) — Free fake REST API for testing.
Single base URL with multiple endpoints: `/users`, `/posts`, `/todos`.
