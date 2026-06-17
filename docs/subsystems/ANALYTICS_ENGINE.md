# Analytics Engine

The SCLPLAPI analytics engine turns request, workflow, and export execution into queryable local reports.

## Scope

- execution duration summaries
- workflow node outcome aggregation
- retry and failure pattern summaries
- export success and artifact generation metrics
- local trend views for developer use

## Non-scope

- remote telemetry
- user tracking
- mandatory cloud reporting

## Inputs

- workflow run records
- request execution events
- export job events
- error and retry counters

## Outputs

- per-run summaries
- per-workflow rollups
- failure hot spots
- export/report usage statistics

## Design rules

- analytics stays local by default
- raw execution data remains available for deeper inspection
- metrics derive from the runtime event model, not ad hoc UI state
- analytics never becomes a blocking dependency for execution

Primary references:

- `EVENT_BUS.md`
- `RUNTIME_MODEL.md`
- `GRAPH_REPORT.md`
- `DATABASE_AND_MIGRATIONS.md`
