---
name: sclplapi-export-engine
description: Use when implementing data transformation, export contracts, reusable transformers, and report/output behavior in SCLPLAPI.
---

## Purpose

Treat exports as reusable transformation pipelines, not simple file writes. Keep transformation logic persistent and reusable. Prevent export logic from leaking into UI code.

## When to use

- JSON/CSV/Excel export implementation
- transformation pipeline design
- field mapping and derived fields
- export preset configuration
- report generation hooks
- dataset model design

## Rules

- exports are pipelines, not save-as utilities
- operate on normalized intermediate dataset models
- transformation logic must be reusable and persistable
- export engine lives in core, not UI

## Key files

- `EXPORT_ENGINE.md`
- `FEATURES.md`
- `docs/subsystems/import_export.md`
- `docs/subsystems/GRAPH_REPORT.md`
