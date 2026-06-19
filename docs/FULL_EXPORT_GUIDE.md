# Full Export Guide

## Overview

SCLPLAPI provides a complete export/import system for backing up and migrating all your data between machines or environments.

## Quick Backup

```bash
sclplapi export-all ./my-backup
```

This creates a timestamped directory containing:

```
my-backup/
├── workflows/          # All workflow definitions (.json + .sclpll)
├── functions/          # All Python function files
├── plugins/            # Plugin manifests and configurations
├── history/            # Full execution history
├── environments/       # All environments and variables
├── collections/        # All collections and saved requests
├── database/           # Raw SQLite database copy
├── manifest.json       # Export metadata
└── import.py           # Standalone restore script
```

## Restoring a Backup

```bash
sclplapi import-all ./my-backup
```

The import handles idempotency — existing records are updated, new ones are inserted. Running import twice won't create duplicates.

## Selective Export

Export specific sections only:

```bash
sclplapi export-selective workflows ./output
sclplapi export-selective functions ./output
sclplapi export-selective history ./output
sclplapi export-selective environments ./output
sclplapi export-selective collections ./output
```

## Migrating Between Machines

1. On the source machine:
   ```bash
   sclplapi export-all ./migration-data
   ```

2. Copy `migration-data/` to the target machine (USB, SCP, etc.)

3. On the target machine:
   ```bash
   sclplapi import-all ./migration-data
   ```

## Programmatic Usage

```python
from app.storage.db import Database
from app.services.full_export_service import FullExportService
from app.services.full_import_service import FullImportService

async def backup():
    db = Database("data/sclplapi.db")
    await db.connect()
    await db.initialize()

    exporter = FullExportService(db)
    await exporter.export_all("./backups/daily")

    await db.close()

async def restore():
    db = Database("data/sclplapi.db")
    await db.connect()
    await db.initialize()

    importer = FullImportService(db)
    result = await importer.import_all("./backups/daily")
    print(result)

    await db.close()
```

## Automation

### Daily backup with cron (Linux/macOS)

```cron
0 2 * * * cd /path/to/sclpl-api && python -c "
import asyncio
from app.storage.db import Database
from app.services.full_export_service import FullExportService
from datetime import datetime

async def main():
    db = Database('data/sclplapi.db')
    await db.connect()
    await db.initialize()
    exporter = FullExportService(db)
    date = datetime.now().strftime('%Y-%m-%d')
    await exporter.export_all(f'./backups/{date}')
    await db.close()

asyncio.run(main())
"
```

### Windows Task Scheduler

Create a batch file `backup-sclplapi.bat`:

```bat
@echo off
cd C:\path\to\sclpl-api
python -c "import asyncio; from app.storage.db import Database; from app.services.full_export_service import FullExportService; from datetime import datetime; asyncio.run(FullExportService(Database('data/sclplapi.db')).export_all(f'./backups/{datetime.now().strftime(\"%%Y-%%m-%%d\")}'))"
```

Schedule it with Task Scheduler to run daily.

## Standalone Import Script

Each export includes an `import.py` that works without the CLI:

```bash
python import.py                          # Default: data/sclplapi.db
python import.py /custom/path/sclplapi.db  # Custom database path
```

## What Gets Exported

| Section       | Format           | Contains                                  |
|---------------|------------------|-------------------------------------------|
| workflows     | JSON + SCLPLL    | Definitions, steps, variables, versions   |
| functions     | Python files     | All `.py` files from `functions/`         |
| plugins       | JSON             | Manifests, variables, metadata            |
| history       | JSON             | All execution records with responses      |
| environments  | JSON             | Environments with all variables           |
| collections   | JSON             | Collections with nested requests          |
| database      | SQLite           | Raw database file for direct restore      |
