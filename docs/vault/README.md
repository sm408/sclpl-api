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

## Conventions

- A note describes **one** thing. If it needs two headings that could each be a note,
  it is two notes.
- Every claim about behaviour names the file it lives in, as `path.py:symbol`.
- Anything decided rather than derived goes in [[Decision Log]] with its reasoning.
- `#todo` marks something known to be missing. `#wip` marks a note that is ahead of the
  code.
