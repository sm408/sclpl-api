# Job Application Tracker Pipeline

A multi-step async pipeline example demonstrating parallel execution in SCLPLAPI.

## Overview

This pipeline fetches data from multiple endpoints of the JSONPlaceholder API (single base URL), processes it in parallel where possible, and generates a comprehensive report.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      PARALLEL EXECUTION                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 1. Users │  │ 2. Posts │  │3. Comments│  │ 4. Todos │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │              │             │
│       └──────────────┼──────────────┼──────────────┘             │
│                      │              │                            │
│  ┌───────────────────┼──────────────┼───────────────────┐       │
│  │           DEPENDENCY RESOLUTION                      │       │
│  └───────────────────┼──────────────┼───────────────────┘       │
│                      │              │                            │
│       ┌──────────────┼──────────────┼──────────────┐            │
│       │              │              │              │            │
│  ┌────▼─────┐  ┌─────▼────┐  ┌─────▼────┐        │            │
│  │5. Merge  │  │6. Analyt.│  │7. Todos  │        │            │
│  │User+Post │  │Post+Comm.│  │User+Todo │        │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘        │            │
│       │              │              │              │            │
│       └──────────────┼──────────────┘              │            │
│                      │                             │            │
│  ┌───────────────────┼─────────────────────────────┘            │
│  │           DEPENDENCY RESOLUTION                              │
│  └───────────────────┼─────────────────────────────┘            │
│                      │                                          │
│                 ┌────▼─────┐                                    │
│                 │8. Report │                                    │
│                 │ (Final)  │                                    │
│                 └──────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Execution Flow

### Phase 1: Parallel Fetch (Steps 1-4)
All four API calls run concurrently since they have no dependencies:
- Fetch users from `/users`
- Fetch posts from `/posts`
- Fetch comments from `/comments`
- Fetch todos from `/todos`

### Phase 2: Parallel Processing (Steps 5-7)
Three processing steps run concurrently, each waiting only for their specific dependencies:
- **Step 5**: Merge user + post data (waits for Steps 1, 2)
- **Step 6**: Calculate post analytics (waits for Steps 2, 3)
- **Step 7**: User todo summary (waits for Steps 1, 4)

### Phase 3: Final Report (Step 8)
Generates comprehensive report by combining all processed data:
- Waits for Steps 5, 6, 7 to complete
- Merges insights from all sources
- Outputs structured JSON report

## Running

```bash
python examples/job_tracker_pipeline/run.py
```

## Output

The pipeline generates:
- Console output with execution timeline
- `output/pipeline_report.json` - Final analysis report
- `output/execution_stats.json` - Performance metrics

## Key Features

1. **Parallel Execution**: Independent steps run concurrently
2. **Dependency Graph**: Steps wait only for their specific dependencies
3. **Data Merging**: Functions combine data from multiple sources
4. **Execution Timeline**: Visual representation of parallel execution
5. **Performance Metrics**: Speedup calculation vs sequential execution

## API Used

[JSONPlaceholder](https://jsonplaceholder.typicode.com/) - Free fake REST API for testing.
Single base URL with multiple endpoints: `/users`, `/posts`, `/comments`, `/todos`.
