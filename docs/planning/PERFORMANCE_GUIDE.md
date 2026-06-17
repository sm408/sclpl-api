# Performance Guide

SCLPLAPI performance work focuses on correctness first, then predictable local responsiveness.

## Primary hotspots

- variable resolution
- request batching and retries
- workflow graph scheduling
- plugin/function execution overhead
- export generation for large runs

## Guidelines

- optimize core runtime paths before UI polish
- avoid hidden synchronous bottlenecks in async flows
- cache only when invalidation is explicit
- prefer incremental recomputation over full reloads
- measure graph execution and export time separately

## Targets

- small request runs feel immediate
- medium workflows remain comfortably interactive
- long-running jobs surface progress and cancellation

Primary references:

- `WORKFLOW_ENGINE.md`
- `RUNTIME_MODEL.md`
- `TESTING_STRATEGY.md`
