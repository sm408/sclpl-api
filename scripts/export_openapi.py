"""Export the OpenAPI schema from the FastAPI app.

Run from the project root:
    python scripts/export_openapi.py [--output web/openapi.json]

The schema can then be consumed by openapi-typescript to generate
TypeScript types.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.web.server import create_app


def export_schema(output: Path) -> None:
    """Generate and write the OpenAPI schema."""
    app = create_app(":memory:")
    schema = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2))
    print(f"OpenAPI schema written to {output}")
    print(f"  Paths: {len(schema.get('paths', {}))}")
    print(f"  Schemas: {len(schema.get('components', {}).get('schemas', {}))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI schema")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("web/openapi.json"),
        help="Output file path",
    )
    args = parser.parse_args()
    export_schema(args.output)


if __name__ == "__main__":
    main()
