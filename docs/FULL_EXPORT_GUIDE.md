# Full Export Guide

## Overview

SCLPLAPI provides a complete export/import system for backing up and migrating all your data.

## Using the TUI

1. Press `I` or navigate to Import/Export tab
2. Choose:
   - **Export All** — Full workspace backup
   - **Import All** — Restore from backup
   - **Export/Import Collections** — Collections only
   - **Export/Import Environments** — Environments only
   - **Import OpenAPI** — Import Swagger/OpenAPI spec as collection

## Export Contents

A full export creates:

```
export_backup/
├── workflows/          # Workflow definitions (.json + .sclpll)
├── functions/          # Python function files
├── plugins/            # Plugin manifests
├── history/            # Execution history
├── environments/       # Environments and variables
├── collections/        # Collections and saved requests
├── database/           # SQLite database copy
└── manifest.json       # Export metadata
```

## Manual Export via CLI

```bash
python -m app export-all ./my-backup
python -m app import-all ./my-backup
```

## Selective Export

```bash
python -m app export-selective workflows ./output
python -m app export-selective collections ./output
python -m app export-selective environments ./output
```
