# TESTING_STRATEGY.md

## Testing priorities

Highest-value coverage should target:

1. variable resolution
2. workflow execution
3. function execution contracts
4. plugin loading and compatibility checks
5. exporters and transformations
6. migrations
7. retry and timeout behavior

## Test philosophy

- test determinism over UI cosmetics
- test behavior at boundaries
- isolate async and cancellation behavior
- prefer focused subsystem tests over fake end-to-end theater

## Coverage guidance

- core engine: high coverage
- workflow runtime: very high coverage
- storage and migrations: high coverage
- UI: minimal sanity coverage where needed

