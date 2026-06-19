from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.storage.db import Database


class FullImportService:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def import_all(self, export_dir: str | Path) -> dict:
        base = Path(export_dir)
        manifest_path = base / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No manifest.json in {base}")

        results = {}
        results["workflows"] = await self.import_workflows(base)
        results["functions"] = await self.import_functions(base)
        results["history"] = await self.import_history(base)
        results["environments"] = await self.import_environments(base)
        results["collections"] = await self.import_collections(base)
        return results

    async def import_workflows(self, export_dir: str | Path) -> int:
        wf_dir = Path(export_dir) / "workflows"
        if not wf_dir.exists():
            return 0

        count = 0
        json_files = list(wf_dir.glob("*.json"))
        json_files = [f for f in json_files if f.name != "_versions.json"]

        for jf in json_files:
            data = json.loads(jf.read_text(encoding="utf-8"))
            wf_id = data.get("id", str(uuid.uuid4()))

            existing = await self._db.fetch_one(
                "SELECT id FROM workflows WHERE id = ?", (wf_id,)
            )

            steps = json.dumps(data.get("steps", []))
            variables = json.dumps(data.get("variables", {}))
            now = datetime.now(timezone.utc).isoformat()

            if existing:
                await self._db.execute(
                    """UPDATE workflows SET name=?, description=?, steps=?, variables=?, updated_at=?
                    WHERE id=?""",
                    (data["name"], data.get("description", ""), steps, variables, now, wf_id),
                )
            else:
                await self._db.execute(
                    """INSERT INTO workflows (id, name, description, steps, variables, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (wf_id, data["name"], data.get("description", ""), steps, variables, now, now),
                )
            count += 1

        versions_path = wf_dir / "_versions.json"
        if versions_path.exists():
            versions = json.loads(versions_path.read_text(encoding="utf-8"))
            for ver in versions:
                vid = ver.get("id", str(uuid.uuid4()))
                existing = await self._db.fetch_one(
                    "SELECT id FROM workflow_versions WHERE id = ?", (vid,)
                )
                if not existing:
                    await self._db.execute(
                        """INSERT INTO workflow_versions (id, workflow_id, version, sclpll_source, json_source, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (vid, ver["workflow_id"], ver["version"],
                         ver.get("sclpll_source", ""), ver.get("json_source", "{}"),
                         ver.get("created_at", now)),
                    )

        await self._db.commit()
        return count

    async def import_functions(self, export_dir: str | Path) -> int:
        func_dir = Path(export_dir) / "functions"
        if not func_dir.exists():
            return 0

        dest = Path("functions")
        count = 0
        for py_file in func_dir.rglob("*.py"):
            rel = py_file.relative_to(func_dir)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(py_file, target)
            count += 1

        return count

    async def import_history(self, export_dir: str | Path) -> int:
        hist_path = Path(export_dir) / "history" / "history.json"
        if not hist_path.exists():
            return 0

        entries = json.loads(hist_path.read_text(encoding="utf-8"))
        count = 0
        now = datetime.now(timezone.utc).isoformat()

        for entry in entries:
            existing = await self._db.fetch_one(
                "SELECT id FROM history WHERE id = ?", (entry["id"],)
            )
            if not existing:
                await self._db.execute(
                    """INSERT INTO history
                    (id, request_id, request_name, method, url, status, status_code,
                     response_body, response_headers, duration_ms, error_message,
                     environment_id, variables_used, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry["id"],
                        entry.get("request_id"),
                        entry["request_name"],
                        entry["method"],
                        entry["url"],
                        entry["status"],
                        entry.get("status_code"),
                        entry.get("response_body"),
                        entry.get("response_headers", "{}"),
                        entry.get("duration_ms", 0),
                        entry.get("error_message"),
                        entry.get("environment_id"),
                        entry.get("variables_used", "{}"),
                        entry.get("created_at", now),
                    ),
                )
                count += 1

        await self._db.commit()
        return count

    async def import_environments(self, export_dir: str | Path) -> int:
        env_path = Path(export_dir) / "environments" / "environments.json"
        if not env_path.exists():
            return 0

        envs = json.loads(env_path.read_text(encoding="utf-8"))
        count = 0
        now = datetime.now(timezone.utc).isoformat()

        for env in envs:
            existing = await self._db.fetch_one(
                "SELECT id FROM environments WHERE id = ?", (env["id"],)
            )
            if existing:
                await self._db.execute(
                    "UPDATE environments SET name=?, is_active=?, updated_at=? WHERE id=?",
                    (env["name"], int(env.get("is_active", 0)), now, env["id"]),
                )
            else:
                await self._db.execute(
                    "INSERT INTO environments (id, name, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (env["id"], env["name"], int(env.get("is_active", 0)), now, now),
                )

            await self._db.execute(
                "DELETE FROM variables WHERE environment_id = ?", (env["id"],)
            )
            for var in env.get("variables", []):
                await self._db.execute(
                    "INSERT INTO variables (environment_id, key, value, scope, is_secret, enabled) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        env["id"],
                        var["key"],
                        var["value"],
                        var.get("scope", "environment"),
                        int(var.get("is_secret", 0)),
                        int(var.get("enabled", 1)),
                    ),
                )
            count += 1

        await self._db.commit()
        return count

    async def import_collections(self, export_dir: str | Path) -> int:
        col_path = Path(export_dir) / "collections" / "collections.json"
        if not col_path.exists():
            return 0

        collections = json.loads(col_path.read_text(encoding="utf-8"))
        count = 0
        now = datetime.now(timezone.utc).isoformat()

        for col in collections:
            existing = await self._db.fetch_one(
                "SELECT id FROM collections WHERE id = ?", (col["id"],)
            )
            if existing:
                await self._db.execute(
                    "UPDATE collections SET name=?, description=?, updated_at=? WHERE id=?",
                    (col["name"], col.get("description", ""), now, col["id"]),
                )
            else:
                await self._db.execute(
                    "INSERT INTO collections (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (col["id"], col["name"], col.get("description", ""), col.get("created_at", now), now),
                )

            for req in col.get("requests", []):
                req_existing = await self._db.fetch_one(
                    "SELECT id FROM requests WHERE id = ?", (req["id"],)
                )
                if not req_existing:
                    await self._db.execute(
                        """INSERT INTO requests
                        (id, name, method, url, headers, query_params, body, body_type,
                         auth_type, auth_config, collection_id, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            req["id"], req["name"], req["method"], req["url"],
                            req.get("headers", "[]"), req.get("query_params", "[]"),
                            req.get("body"), req.get("body_type"),
                            req.get("auth_type"), req.get("auth_config", "{}"),
                            req.get("collection_id"), req.get("created_at", now), now,
                        ),
                    )
            count += 1

        await self._db.commit()
        return count
