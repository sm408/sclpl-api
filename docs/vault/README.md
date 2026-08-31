---
tags:
  - meta
---

# The sclpl vault

This directory is an [Obsidian](https://obsidian.md) vault. Open Obsidian, choose
**Open folder as vault**, and point it at `docs/vault/`.

It works as plain Markdown in any editor or on GitHub, but Obsidian gives you the two
things it was built for: the `[[wikilink]]` graph, and backlinks. Start at
[[Start Here]].

## What this is, and what it is not

| | |
|---|---|
| **This vault** | How the thing works, why it is shaped this way, and what was decided |
| [[SPEC]] (`docs/cli-rebuild/SPEC.md`) | **Normative.** What to build. Wins any disagreement with this vault |
| [[HANDOFF]] (`docs/cli-rebuild/HANDOFF.md`) | Where the work stands right now |
| `docs/reference/` | Generated. Hand-editing it fails CI |

If a note here contradicts the SPEC, the SPEC is right and the note is stale. Say so in
[[Decision Log]] and fix it.

## Layout

| Folder | What is in it |
|---|---|
| `1 Start` | Where to begin, and why this exists at all |
| `2 Architecture` | The shape of the whole thing, including a **measured** one |
| `3 Concepts` | One note per idea that has a name |
| `4 Packages` | One note per package in `sclpl/` |
| `5 Guides` | How to do a thing |
| `6 Decisions` | Invariants, locked decisions, and the log of what was decided |
| `7 Milestones` | M0 through M9 |
| `8 Meta` | The vault about the vault |

Folders are for humans. Obsidian resolves `[[links]]` by filename, so a note can move
without breaking anything.

> [!tip] If the graph looks like a hairball
> It is showing how the *notes* link, not how the code depends. Those are different
> graphs. [[Graph View]] explains it and [[Architecture Measured]] has the real one.

## Conventions

- A note describes **one** thing. If it needs two headings that could each be a note,
  it is two notes.
- Every claim about behaviour names the file it lives in, as `path.py:symbol`.
- Anything decided rather than derived goes in [[Decision Log]] with its reasoning.
- `#todo` marks something known to be missing. `#wip` marks a note that is ahead of the
  code.
- Every note carries a `tags:` line matching its folder. A hub that links to everything
  is additionally `#moc`, so the graph can hide it.

```bash
python scripts/check_vault.py       # every wikilink resolves
python scripts/check_layering.py    # the code has no import cycles
```
