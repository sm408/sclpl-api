"""Build the dependency-free static site from the repository documentation.

Run from the repository root with: C:\\Python312\\python.exe website\\build.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "website"
OUTPUT = SOURCE / "dist"
PUBLIC_DOCS = (
    "README.md",
    *(str(path.relative_to(ROOT)) for path in (ROOT / "docs").rglob("*.md")),
    "sclpll-extras/README.md",
    *(str(path.relative_to(ROOT)) for path in (ROOT / "sclpll-extras" / "docs").rglob("*.md")),
)


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()

    for name in ("index.html", "downloads.html", "docs.html", "links.html", "site.css", "site.js", "favicon.svg"):
        copy_file(SOURCE / name, OUTPUT / name)

    records: list[dict[str, str]] = []
    for relative in sorted(set(PUBLIC_DOCS)):
        source = ROOT / relative
        if not source.exists():
            continue
        destination = OUTPUT / "content" / relative
        copy_file(source, destination)
        records.append(
            {
                "path": relative.replace("\\", "/"),
                "title": source.stem.replace("-", " ").replace("_", " ").title(),
                "section": relative.split("/", 2)[1] if "/" in relative else "start",
            }
        )

    for example in (ROOT / "examples").glob("*.sclpll"):
        copy_file(example, OUTPUT / "content" / "examples" / example.name)

    downloads = OUTPUT / "downloads"
    downloads.mkdir()
    for asset in [*ROOT.glob("dist/*.whl"), ROOT / "sclpl-language-tools-1.0.1.vsix"]:
        if asset.exists():
            copy_file(asset, downloads / asset.name)

    (OUTPUT / "content" / "index.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8"
    )
    print(f"Built {OUTPUT} with {len(records)} public documentation pages.")


if __name__ == "__main__":
    main()
