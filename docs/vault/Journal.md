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

**This vault created**, at the user's request, and to be kept current on every major
decision from here.

→ [[Maintaining This Vault]]

---

## Earlier

The record before this session lives in commit messages and in [[Decision Log]]. The
milestones and their commits are in [[Milestone Status]].
