---
tags:
  - meta
---

# Journal

A running record of what happened, session by session. Shorter than [[Decision Log]] and
in a different key: the log says *what was decided*, this says *what was done and what it
cost*.

---

## 2026-08-31 — M5 landed, M6 started, this vault created

**M5 committed** (`86b9efa`). Tables, 37 built-ins, and the `-> port` binding M4 had left
in the grammar but not in code.

The method worth repeating: the M4 exit criterion was only *actually* checkable once M5's
functions existed, so it was run for real against a live mock server. It found five bugs
no unit test had — including a form that was in the SPEC grammar and in no code at all.
**Running the example is a different test from testing the units.**

→ [[M5 Functions and Tables]]

**Budget revised** (ADR 0002). `run/` went 54 over, and 866 of its lines turned out to be
a lexer, parser, and emitter. Splitting `run/sclpll/` out made the gate sharper rather
than slacker — two numbers where there was one means grammar growth and engine growth
are now visible separately.

→ [[The Line Budget]]

**M6 in progress.** All five paginators work, verified against a mock serving 95 rows in
10-row pages. `foreach`, `if`, `parallel`, and `gate` expand into the graph and join
correctly. `while` and `do_while` expand but hit a refcount bug.

The one open blocker: `Plan.readers_of` counts nodes that exist at plan time, so a value
read only by an injected node is freed before that node runs.

→ [[M6 Control Flow and Pagination]]

**M7 finished.** The governor, the lanes, and the cache.

Both halves of the exit criterion are numbers rather than claims. Six 65 MB intermediates
against a 150 MB budget: completed, exit 0, right answer. A 40,000-row join in PID 21772
while the parent was 20544; a one-row join on the loop.

Three things found while building it, all in [[Decision Log]]. The one worth repeating:
**`read_json` was about to be cached on its path.** Every `fn` step was cacheable and a
reader's key is its arguments -- so a second run would have served yesterday's file from
today's name. That is the worst class of bug, because nothing looks wrong.

The Windows RSS probe also took three attempts, and the failure mode is instructive: it
returned 0 rather than raising, and 0 reads as "no memory in use". A governor reading 0
does nothing, quietly, forever.

**M6 finished.** All five paginators, all six control-flow kinds, `concurrency` and
`collect` on a `foreach`, and the exit criterion tested through the real CLI.

The bound is measured rather than claimed: against a server reporting its peak
simultaneous requests, 12 items at `concurrency 3` peaked at 3, and the same workflow
without the clause peaked at 9. That number is the argument for injecting a loop into the
graph instead of calling `gather` inside a step, and it is now a number rather than a
paragraph.

Building it found six bugs, listed in [[M6 Control Flow and Pagination]]. The one worth
repeating: **any workflow containing a `foreach` had never compiled**, because the parent
claimed to produce its body's names and the body's steps were also their own specs. There
was no test with a loop in it, so nothing had noticed.

**The graph looked like a hairball**, which was a fair question and a fair complaint. The
answer had two halves.

The first half was mine and cosmetic: 54 notes in one flat folder, no tags, and six
maps-of-content linking to everything. Obsidian had nothing to cluster by and six hubs
pulling the rest into a ball. Fixed with folders, tags, and a `-tag:#moc` filter shipped
in `.obsidian/graph.json`. → [[Graph View]]

The second half was worth more. The question underneath it — *is this actually
decoupled?* — had only ever been answered by a diagram I drew by hand. Measuring it found
three edges pointing the wrong way:

- `run/errors.py` had **37 importers** across every package, making `run/` look like a
  god-package with fan-in 9. It was one leaf, not the engine.
- Its exit codes came from `cli/options.py` — a real `cli ↔ run` cycle.
- `run/ports.py` owned `BY_EXTENSION`, which `tables/io.py` imported back.

All three are fixed, `scripts/check_layering.py` now refuses a cycle, and the diagram in
[[Architecture Measured]] is generated rather than drawn.

The lesson is the same one M5 taught in a different key: **running the thing tests it in
a way that reasoning about it does not.** There, it was running the example. Here, it was
measuring the imports. Both found bugs that reading had not.

**This vault created**, at the user's request, and to be kept current on every major
decision from here.

→ [[Maintaining This Vault]]

---

## Earlier

The record before this session lives in commit messages and in [[Decision Log]]. The
milestones and their commits are in [[Milestone Status]].
