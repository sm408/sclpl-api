from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.storage.db import Database


class FullExportService:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def export_all(self, output_dir: str | Path) -> Path:
        base = Path(output_dir)
        base.mkdir(parents=True, exist_ok=True)

        await self.export_projects(base / "projects")
        await self.export_workflows(base / "workflows")
        await self.export_functions(base / "functions")
        await self.export_plugins(base / "plugins")
        await self.export_history(base / "history")
        await self.export_environments(base / "environments")
        await self.export_collections(base / "collections")
        await self.export_database(base / "database")
        self._write_manifest(base)
        self._write_import_script(base)

        return base

    async def export_projects(self, output_dir: str | Path) -> int:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        rows = await self._db.fetch_all("SELECT * FROM projects")
        (out / "projects.json").write_text(
            json.dumps(rows, indent=2, default=str), encoding="utf-8"
        )
        return len(rows)

    async def export_workflows(self, output_dir: str | Path) -> int:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        rows = await self._db.fetch_all("SELECT * FROM workflows")
        for wf in rows:
            sclpll = wf.get("sclpll_source", "")
            steps = wf.get("steps", "[]")
            variables = wf.get("variables", "{}")
            name = wf["name"]

            if sclpll:
                (out / f"{name}.sclpll").write_text(sclpll, encoding="utf-8")

            json_data = {
                "id": wf["id"],
                "name": name,
                "description": wf.get("description", ""),
                "steps": json.loads(steps) if isinstance(steps, str) else steps,
                "variables": json.loads(variables) if isinstance(variables, str) else variables,
                "created_at": wf.get("created_at", ""),
                "updated_at": wf.get("updated_at", ""),
            }
            (out / f"{name}.json").write_text(
                json.dumps(json_data, indent=2), encoding="utf-8"
            )

        versions = await self._db.fetch_all("SELECT * FROM workflow_versions")
        if versions:
            (out / "_versions.json").write_text(
                json.dumps(versions, indent=2, default=str), encoding="utf-8"
            )

        return len(rows)

    async def export_functions(self, output_dir: str | Path) -> int:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        func_dir = Path("functions")
        if not func_dir.exists():
            return 0

        count = 0
        for py_file in func_dir.rglob("*.py"):
            rel = py_file.relative_to(func_dir)
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(py_file, dest)
            count += 1

        return count

    async def export_plugins(self, output_dir: str | Path) -> int:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        rows = await self._db.fetch_all("SELECT * FROM plugins")
        for plugin in rows:
            plugin_dir = out / plugin["name"]
            plugin_dir.mkdir(parents=True, exist_ok=True)

            manifest = json.loads(plugin.get("manifest_json", "{}"))
            manifest["id"] = plugin["id"]
            manifest["name"] = plugin["name"]
            manifest["version"] = plugin["version"]
            manifest["description"] = plugin.get("description", "")
            manifest["author"] = plugin.get("author", "")

            (plugin_dir / "plugin.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

            variables = await self._db.fetch_all(
                "SELECT key, value FROM plugin_variables WHERE plugin_id = ?",
                (plugin["id"],),
            )
            if variables:
                (plugin_dir / "variables.json").write_text(
                    json.dumps({v["key"]: v["value"] for v in variables}, indent=2),
                    encoding="utf-8",
                )

        return len(rows)

    async def export_history(self, output_dir: str | Path) -> int:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        rows = await self._db.fetch_all("SELECT * FROM history ORDER BY created_at DESC")
        (out / "history.json").write_text(
            json.dumps(rows, indent=2, default=str), encoding="utf-8"
        )
        return len(rows)

    async def export_environments(self, output_dir: str | Path) -> int:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        envs = await self._db.fetch_all("SELECT * FROM environments")
        for env in envs:
            env["variables"] = await self._db.fetch_all(
                "SELECT key, value, scope, is_secret, enabled FROM variables WHERE environment_id = ?",
                (env["id"],),
            )

        (out / "environments.json").write_text(
            json.dumps(envs, indent=2, default=str), encoding="utf-8"
        )
        return len(envs)

    async def export_collections(self, output_dir: str | Path) -> int:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        collections = await self._db.fetch_all("SELECT * FROM collections")
        for col in collections:
            col["requests"] = await self._db.fetch_all(
                "SELECT * FROM requests WHERE collection_id = ?", (col["id"],)
            )

        (out / "collections.json").write_text(
            json.dumps(collections, indent=2, default=str), encoding="utf-8"
        )
        return len(collections)

    async def export_database(self, output_dir: str | Path) -> Path:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        db_path = self._db._path
        dest = out / db_path.name
        if db_path.exists():
            shutil.copy2(db_path, dest)
        return dest

    def _write_manifest(self, base: Path) -> None:
        manifest = {
            "format": "sclplapi-full-export",
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "export_id": str(uuid.uuid4()),
            "sections": [
                "projects",
                "workflows",
                "functions",
                "plugins",
                "history",
                "environments",
                "collections",
                "database",
            ],
        }
        (base / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def _write_import_script(self, base: Path) -> None:
        script = '''#!/usr/bin/env python3
"""Restore SCLPLAPI data from this export directory."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    from app.storage.db import Database
    from app.services.full_import_service import FullImportService

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/sclplapi.db"
    db = Database(db_path)
    await db.connect()
    await db.initialize()

    importer = FullImportService(db)
    result = await importer.import_all(Path(__file__).parent)
    print(f"Import complete: {result}")
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
'''
        (base / "import.py").write_text(script, encoding="utf-8")
