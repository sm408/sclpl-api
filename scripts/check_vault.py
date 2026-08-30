"""Check the Obsidian vault's wikilinks resolve.

Not a CI gate. An unresolved link is not an error -- it marks a note worth writing, and
Obsidian shows them in a different colour for exactly that reason. This script is for
noticing when one has sat unresolved long enough to be a gap rather than an intention.

Links inside code spans and fenced blocks are skipped: `[[Note Name]]` written as an
example of the syntax is not a link, and treating it as one would make the vault's own
documentation of its conventions unfixable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent / "docs" / "vault"

_LINK = re.compile(r"\[\[([^\]|#]+)")
_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"`[^`]*`")


def targets(text: str) -> list[str]:
    """Every wikilink target in a note, ignoring code."""
    found: list[str] = []
    fenced = False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        found.extend(name.strip() for name in _LINK.findall(_CODE_SPAN.sub("``", line)))
    return [name for name in found if name]


def main() -> int:
    if not VAULT.is_dir():
        print(f"no vault at {VAULT}", file=sys.stderr)
        return 1

    notes = {path.stem for path in VAULT.rglob("*.md")}
    missing: dict[str, set[str]] = {}
    links = 0

    for path in sorted(VAULT.rglob("*.md")):
        for target in targets(path.read_text(encoding="utf-8")):
            links += 1
            if target not in notes:
                missing.setdefault(target, set()).add(path.stem)

    print(f"{len(notes)} notes, {links} links")
    if not missing:
        print("every wikilink resolves")
        return 0

    print(f"\n{len(missing)} unresolved:")
    for target, sources in sorted(missing.items()):
        print(f"  [[{target}]]  <- {', '.join(sorted(sources))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
