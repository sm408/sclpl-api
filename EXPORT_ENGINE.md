# EXPORT_ENGINE.md

## Purpose

Exports are a core subsystem, not a utility menu item.

## Philosophy

SCLPLAPI exports should behave like reusable transformation pipelines that end in a report, dataset, or file output.

## Required capabilities

- JSON export
- CSV export
- Excel workbook generation
- flattening
- field mapping
- formulas / derived fields
- grouping and aggregation hooks
- reusable transformer chains

## Dataset model direction

The export engine should operate on a normalized intermediate dataset model rather than ad hoc response objects.

## Sticky transformers

Transformation logic should be reusable and persistable so users do not rewrite mapping logic repeatedly.

## Deferred capabilities

- polished report templating
- dashboards
- heavy BI behavior

