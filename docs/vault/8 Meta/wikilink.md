---
tags:
  - meta
---

# wikilink

A note that exists so `[[wikilink]]` in the README is a live example rather than a broken
link. Meta, but the README claims the graph is the point, and a broken link in the first
paragraph would undercut it.

## The convention in this vault

- `[[Note Name]]` — link to a note
- `[[Note Name#Heading]]` — link to a heading within it
- `[[Note Name|display text]]` — link with different text

Obsidian resolves these by **filename**, so note names are unique across the vault and
directories are for humans rather than for resolution.

## Two habits worth keeping

**Link liberally.** A link to a note that does not exist yet is not an error — it marks
something worth writing. Obsidian shows unresolved links in a different colour and lists
them, which makes the vault's own gaps visible.

**Backlinks do the indexing.** There is no need to maintain "see also" sections by hand;
open a note's backlinks pane and the graph has already done it. That is why
[[Concepts Index]] and [[Package Map]] are maps of content rather than exhaustive
indexes.

## Checking

`docs/vault/` has no build step, but a link check is one short script — see
[[Maintaining This Vault]].
