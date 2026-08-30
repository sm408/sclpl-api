# Maintaining This Vault

## The standing instruction

> Keep the vault updated as the work goes on, on **every major decision**.

In practice that means: when something is decided rather than derived, it gets an entry
in [[Decision Log]] *in the same change that decides it* — not later, and not only in a
commit message. A commit message is read once; a note is read when someone is about to
undo the decision.

## What counts as a major decision

- A behaviour chosen between two defensible options
- A bug whose fix reveals something about the design
- Anything that changes a [[Locked Decisions|locked decision]] — which also needs an ADR
- A budget change — which also needs an ADR
- A milestone landing

If the answer to "why is it like this" would be non-obvious in three months, it is major.

## Where things go

| Kind of change | Goes in |
|---|---|
| A decision, with its reasoning | [[Decision Log]] |
| How a mechanism works | The concept note for that mechanism |
| A new file or package | [[Package Map]] and the package note |
| Milestone progress | [[Milestone Status]] and the milestone note |
| A rule that is now enforced | [[Invariants]] or [[Locked Decisions]] |

## Rules the vault holds itself to

- **One note, one thing.** If it needs two headings that could each be a note, it is two
  notes.
- **Name the file.** Every claim about behaviour cites `path.py:symbol`, so a reader can
  check it and a stale claim is findable.
- **Say what it replaced.** A decision without the alternative it beat is an assertion.
- **`#todo` for a known gap, `#wip` for a note ahead of the code.** Both are searchable.
- **The [[SPEC]] wins.** If a note contradicts it, the note is stale.

## Checking the links

```python
import pathlib, re
V = pathlib.Path("docs/vault")
notes = {p.stem for p in V.rglob("*.md")}
for p in V.rglob("*.md"):
    for t in re.findall(r"\[\[([^\]|#]+)", p.read_text(encoding="utf-8")):
        if t.strip() not in notes:
            print(f"{p.stem}: [[{t.strip()}]]")
```

Unresolved links are not errors — they mark notes worth writing. But an unresolved link
that has sat there for a milestone is a gap, not an intention.
