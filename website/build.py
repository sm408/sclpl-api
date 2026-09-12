"""Build the dependency-free static site from the repository documentation.

Run from the repository root with: C:\\Python312\\python.exe website\\build.py
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "website"
OUTPUT = SOURCE / "dist"

# Maintainer-facing material (decision logs, rebuild planning, archived drafts,
# vault housekeeping) has no place in user-facing docs -- that's what the
# GitHub repo is for. This site is for people using or evaluating sclpl, not
# for people maintaining or contributing to it.
INTERNAL_DOC_PREFIXES = (
    "docs/adr/",
    "docs/cli-rebuild/",
    "docs/attic/",
    "docs/vault/4 Packages/",
    "docs/vault/6 Decisions/",
    "docs/vault/7 Milestones/",
    "docs/vault/8 Meta/",
)
INTERNAL_DOC_FILES = (
    "docs/vault/2 Architecture/Architecture Measured.md",
    "docs/vault/2 Architecture/Package Map.md",
)
# Playbooks are curated to the three role-based ones; the generic task-based
# drafts they grew out of stay in git history, not on the site.
EXCLUDED_PLAYBOOKS = (
    "docs/playbooks/01-paginated-api-to-csv.md",
    "docs/playbooks/02-joining-sources.md",
    "docs/playbooks/03-automating.md",
    "docs/playbooks/04-debugging.md",
)

# Folder names get a proper display label instead of their raw slug -- used
# both for section labels and for turning a bare "README.md" into something
# a reader would actually recognize.
FOLDER_LABELS = {
    "guide": "Guide",
    "vault": "Vault",
    "sclpll-extras": "SCLPLL Extras",
    "playbooks": "Playbooks",
    "reference": "Reference",
}


def _is_public(relative: str) -> bool:
    posix = relative.replace("\\", "/")
    if posix in INTERNAL_DOC_FILES or posix in EXCLUDED_PLAYBOOKS:
        return False
    return not posix.startswith(INTERNAL_DOC_PREFIXES)


def _title_for(relative: str, source: Path) -> str:
    if source.stem.lower() != "readme":
        stem = re.sub(r"^\d+[-_.\s]+", "", source.stem)  # "05-analyst" -> "analyst"
        return stem.replace("-", " ").replace("_", " ").title()
    parent = Path(relative.replace("\\", "/")).parent
    parent_str = str(parent).replace("\\", "/")
    if parent_str in (".", ""):
        return "SCLPL"
    label = FOLDER_LABELS.get(parent.name.lower(), parent.name.replace("-", " ").replace("_", " ").title())
    return f"{label} Overview"


PUBLIC_DOCS = (
    "README.md",
    *(
        str(path.relative_to(ROOT))
        for path in (ROOT / "docs").rglob("*.md")
        if _is_public(str(path.relative_to(ROOT)))
    ),
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
                "title": _title_for(relative, source),
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
