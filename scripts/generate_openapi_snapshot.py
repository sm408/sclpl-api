#!/usr/bin/env python
"""Generate a stable OpenAPI snapshot from the running FastAPI app.

Run this script whenever the API surface changes and commit the resulting
``openapi_snapshot.json`` alongside the code change.

Usage::

    python scripts/generate_openapi_snapshot.py

The output is written to ``<repo-root>/openapi_snapshot.json`` with sorted
keys and deterministic formatting so that diffs are meaningful.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so ``app`` can be imported.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from app.web.server import create_app  # noqa: E402

_SNAPSHOT_FILE = _REPO_ROOT / "openapi_snapshot.json"


def main() -> None:
    app = create_app(":memory:")
    spec: dict = app.openapi()

    # Write with sorted keys and stable indentation for deterministic diffs.
    text = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    _SNAPSHOT_FILE.write_text(text, encoding="utf-8")
    print(f"OpenAPI snapshot written to {_SNAPSHOT_FILE}")
    print(f"  Paths: {len(spec.get('paths', {}))}")
    print(f"  Schemas: {len(spec.get('components', {}).get('schemas', {}))}")


if __name__ == "__main__":
    main()
