---
tags:
  - meta
---

# Graph View

If the graph looks like a hairball, this note is why, and what to do about it.

## It is not a picture of the code

This is the thing to get straight first. The Obsidian graph shows how these **notes**
link to each other. The code's dependency graph is a different graph, it is a clean DAG,
and it is measured in [[Architecture Measured]].

Documentation links and code dependencies point in different directions and *should*.
`Pagination` links to `Invariants` because the reader needs the rule; `run/paginate.py`
does not import `sclpl/invariants.py`, because there is no such thing.

## Why it clumped

Three causes, all in how the vault was written rather than in anyone's settings:

**Everything was in one folder.** Obsidian colours graph nodes by group, and a group is
a search query — usually a folder or a tag. With 54 notes in one flat directory and no
tags, there was nothing to colour by, so everything was the same grey.

**Six notes link to nearly everything.** [[Start Here]], [[Concepts Index]],
[[Package Map]], [[Invariants]], [[Locked Decisions]], and [[Decision Log]] are *maps of
content* — hubs whose whole job is to reach the rest. In a force-directed layout a node
with twenty links is dragged to the centre and drags its neighbours with it. Those six
were the large central nodes in the middle of the ball.

**The README says "link liberally"**, and it should — a link to a note that does not
exist yet marks something worth writing. But every concept note linking to
[[Invariants]] is exactly what turns a graph into a ball.

## What was done about it

- Notes are in folders: `1 Start`, `2 Architecture`, `3 Concepts`, `4 Packages`,
  `5 Guides`, `6 Decisions`, `7 Milestones`, `8 Meta`
- Every note has a `tags:` line in its frontmatter matching its folder
- Hubs are additionally tagged `#moc`
- `.obsidian/graph.json` ships with colour groups per tag and the filter `-tag:#moc`

The filter is the one that matters. Hiding six hubs turns one ball into seven clusters,
because what was holding them together was the hubs.

## The settings, if you want to change them

**Graph view → the filter box.** `-tag:#moc` hides the hubs. Clear it to see them; the
ball comes back, which is the demonstration.

**Groups.** One per tag, already configured. Add your own — `path:"3 Concepts"` colours
by folder instead.

**Forces.** Repel 14, link strength 0.65, link distance 190, centre 0.3. Weaker centring
and longer links let clusters separate rather than pile up. The defaults are tuned for
a few dozen notes with few links; this vault has 241.

Nothing here is precious. If a different arrangement reads better, change it — the
settings are in the repo so a good one is shared rather than rediscovered.

## Useful things the graph is actually for

- **Local graph** on a single note, depth 1–2. Far more useful than the global one:
  it shows what one idea touches.
- **Finding orphans.** A note nothing links to is usually a note nobody will find.
- **Finding accidental hubs.** If something has become a hub without being a map of
  content, it is probably two notes.

→ [[Maintaining This Vault]], [[Architecture Measured]]
