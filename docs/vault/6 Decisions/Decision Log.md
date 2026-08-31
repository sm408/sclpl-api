---
tags:
  - decision
  - moc
---

# Decision Log

Every decision that was **made** rather than derived, newest first. A decision that
changes a [[Locked Decisions|locked decision]] needs an ADR in `docs/adr/`; the rest
live here.

Format: what was decided, what it replaced, and *why* — the why is the part that stops
someone undoing it next month.

---

## 2026-09-01 · `records_of` understands a `Table`

**Decided.** It recognises one by `to_records()`, not by type -- `tables/base.py` imports
`flatten.py`, so importing back would be a cycle, and duck-typing is the honest rule
anyway: a plugin's own backend is a table if it behaves like one.

**Replaced.** `records_of(table)` returned `[{"value": "<Table 3x3>"}]` -- the repr, in a
single column. `functions/io_fns.py` had a private wrapper handling tables first, so
nothing inside `sclpl` ever hit it.

**How it was found.** By writing the bundled SQLite plugin, which is exactly what locked
decision 8 says shipping it is for. Only a plugin could hit this, because only a plugin
used the public function directly.

## 2026-09-01 · A dotted name before a paren is a call

**Decided.** `sqlite.write(...)` parses as a call to `sqlite.write`. A chain rooted at a
`@ref` does *not*: `@response.body(...)` would be calling a value.

**Why.** A connector is namespaced by a dot -- that is what lets two plugins both offer
`query` without either being renamed -- so the grammar has to accept a dotted callee.

## 2026-09-01 · A refusal is not overwritten by a later check

**Decided.** `_load` returns immediately if the plugin was already refused.

**Replaced.** A plugin refused for unreadable TOML went on through the ABI and capability
checks and came out reported as "names no module" -- true, a consequence, and pointing at
the wrong line.

## 2026-09-01 · `--deny-capability` is read before the parser runs

**Decided.** `cli/app.py:_denied_capabilities` reads it from `sys.argv`. The parser still
validates it.

**Why.** Loading a plugin *runs* its module. A capability refused after parsing has
already been exercised, so the denial has to precede the import -- and the import
precedes the parser.

## 2026-09-01 · A denial is sticky for the process

**Decided.** `plugins.DENIED` accumulates, so a second `discover()` sees the same
refusals.

**Why.** `plugin list` re-discovers to get a fresh view, and a denial that applied only
to the first discovery would be one `plugin list` could not show.

## 2026-09-01 · `plugin install` prints the command rather than running it

**Decided.** It shows the `pip install` line and exits 2.

**Why.** Running pip would guess at the environment, the index, and whether `--user` was
meant, and be wrong in a way that is hard to unpick. You have a package manager and know
how you like to use it.

## 2026-09-01 · A diagnostic never shows a traceback

**Decided.** `entrypoint` catches `SclplError`, prints it, and exits with its code.

**Replaced.** A diagnostic raised in the root callback -- from a global option, before
routing -- came out as a stack trace with the message buried in it.

## 2026-08-31 · Readers and writers are both uncacheable

**Decided.** `save*`, `read*`, `glob_read`, and `convert` are never cached.

**Why, twice.** A **writer** has an effect a hit cannot reproduce: it would report a path
it did not write to. A **reader** is keyed on its arguments, and a path is not its
contents -- caching it would serve yesterday's file from today's name, which is the worst
kind of wrong because it looks right.

Keying a reader on mtime and size would fix the second. But a local file read is neither
slow nor rate-limited, and the cache exists for things that are.

## 2026-08-31 · Mode is excluded from the cache key

**Decided.** Per SPEC §12, and worth restating because it looks like an omission.

**Why.** A key including the mode means a `partial` run and a `full` run never share the
fetch they have in common -- which is most of the value a cache has in a workflow tool.

## 2026-08-31 · An assertion still runs on a cache hit

**Decided.** A hit reuses the value; it does not skip the check.

**Why.** A cached value that no longer satisfies an assertion is exactly the case the
assertion exists for.

## 2026-08-31 · The credential is a salt, never a value

**Decided.** The key includes a hash *of* the credential.

**Why.** Two people running the same workflow with different tokens must not read each
other's entries -- they may be different tenants. But the token itself has no business
being part of a filename.

## 2026-08-31 · There is always a memory budget

**Decided.** Half the machine when nobody says otherwise, floored at 512 MB.

**Why.** A governor that only exists when asked for is a governor that is missing exactly
when a run turns out to be bigger than expected.

## 2026-08-31 · The RSS probe is injected

**Decided.** `Governor.probe` defaults to the module's `rss()` and can be replaced.

**Replaced.** `sample()` called the global directly, so the watermark policy could not be
tested without a process that happened to be the right size.

**Why.** It is also what lets a platform where the probe does not work supply its own,
rather than having the governor silently do nothing there.

## 2026-08-31 · A lane is an optimisation, and falls back

**Decided.** A process pool that cannot be created, a payload that will not pickle, or a
pool that breaks all fall back to a thread, with the reason logged at `-vv`. A broken
pool is discarded rather than retried.

**Why.** The answer does not depend on where it was computed, only the time does. A run
that fails because a closure would not pickle has lost something real to save something
that was only ever a preference. And one dead pool should not fail every step after it.

## 2026-08-31 · A loop's concurrency is a per-tag ceiling

**Decided.** `foreach ... concurrency 4` registers a tag ceiling under a private name
and puts that tag on every copy.

**Why.** The gate already acquires global, then host, then tags in sorted order, and that
fixed order is the entire deadlock argument. A fourth kind of semaphore would have to
make that argument again. Reusing tags means a bounded loop cannot introduce a new way to
deadlock, by construction.

**Measured, not assumed.** 12 items at `concurrency 3` peaked at 3 simultaneous requests;
without the clause, 9. Ceilings were 16 in both.

## 2026-08-31 · `concurrency` is a literal, not a template

**Decided.** `concurrency {{limit}}` is a parse error, with a message saying why.

**Why.** The limit is read when the file is parsed, before any value exists to
interpolate. Accepting it and ignoring it would be worse; a message that says only
"needs a number" would leave the reader thinking they had mistyped.

## 2026-08-31 · Refcounts are raised at injection

**Decided.** `Scheduler.expand` calls `ValueStore.retain` for everything the new nodes
read, before they can run.

**Replaced.** `Plan.readers_of` counts nodes that exist at plan time. A loop body is not
a node then, so a value read *only* by a body was freed the moment the loop's parent
settled — and the body failed on a name plainly there in the file.

## 2026-08-31 · An empty control body is a parse error

**Decided.** `foreach`, `while`, `do_while`, and `when` with no `step` under them fail at
parse time.

**Replaced.** They failed at runtime, where there is no line number and the message
arrives after the requests before it have been paid for. A body with nothing in it is a
typo, and a typo should be caught where it was typed.

## 2026-08-31 · `errors.py` moves to the top of the package

**Decided.** `run/errors.py` → `sclpl/errors.py`, and the `EXIT_*` codes move there from
`cli/options.py`.

**Replaced.** 37 files across every package imported `sclpl.run.errors`, which made
`run/` look like a god-package with a fan-in of 9. And `run/errors.py` imported the exit
codes from `cli/options.py` — the engine reaching into the command line for the numbers
it exits with, which was a real `cli ↔ run` cycle.

**Why.** What the tree depended on was not the engine, it was one leaf: a shared
vocabulary for going wrong. An exit code is a property of a *kind of failure*, not of the
surface that reports it. `run/`'s fan-in is now 3 and the cycle is gone.

**How it was found.** By measuring, while writing the architecture notes. The intention
diagram in [[Architecture Overview]] had been drawn by hand and was wrong.

→ [[Architecture Measured]]

## 2026-08-31 · `BY_EXTENSION`, `STDIO`, and `Format` move to `tables/io.py`

**Decided.** The extension-to-format map, the `-` convention, and the `Format` alias move
out of `run/ports.py` and `run/ir.py` into `tables/io.py`.

**Replaced.** A `run ↔ tables` cycle: path binding owned a fact about formats, and the
format module imported it back.

**Why.** What an extension means is a fact about formats. `run/ports.py` is one of its
consumers, not its owner. The measured graph now has no cycles at all.

## 2026-08-31 · The layering is checked, not asserted

**Decided.** `scripts/check_layering.py` reads every import in `sclpl/`, reports fan-in
and fan-out per package, refuses a cycle, and emits the Mermaid diagram the vault embeds.

**Why.** A claim like "decoupled" is worth exactly as much as the thing that checks it.
The hand-drawn diagram was wrong in three places; a generated one cannot be.

Two exclusions, both deliberate: the package root is the entry point, so cycles through
`sclpl/__init__` are not coupling; and an import inside a function body is a deferral.

## 2026-08-31 · The vault gets folders, tags, and a graph filter

**Decided.** Eight folders, a `tags:` line per note matching its folder, `#moc` on the
six hubs, and `.obsidian/graph.json` shipping colour groups plus the filter `-tag:#moc`.

**Replaced.** 54 notes in one flat directory with no tags, which gave Obsidian's graph
nothing to colour by, and six hub notes pulling everything into one ball.

**Why.** The graph is a picture of how the notes link, not of how the code depends. It
should still be readable. Hiding the maps-of-content turns one ball into seven clusters,
because the hubs were what held them together.

→ [[Graph View]]

## 2026-08-31 · Nested body steps are not plan nodes

**Decided.** `compile_plan` excludes a control-flow body's steps from the node list. The
parent stands in for them, recording their names under `produces`; their references are
folded into the parent's, minus the loop variable and sibling ids.

**Replaced.** They were nodes, which meant a workflow with any `foreach` failed to
compile at all — the parent claimed to produce `double` *and* `double` was its own spec,
so `build()` raised "two steps both produce 'double'".

**Why.** A body step's node count is not known until the parent runs: once per element,
once per pass, or not at all for the branch an `if` did not take. Folding references
upward is what keeps [[Invariants#3 The DAG is inferred from references]] true for
nested steps — otherwise `foreach @ids` whose body reads `@config` would run before
`config` existed.

→ [[Control Flow]], [[The DAG#Nested bodies]]

## 2026-08-31 · `while` binds its body's names to null on the first pass

**Decided.** Before pass zero, a loop's condition and its body see the body's own step
ids bound to `null`.

**Why.** A loop body refers to what the previous pass produced — that is how a loop makes
progress. On the first pass there is none, and an unresolved reference would be an error
naming a step written two lines below. A name the body does *not* produce is still
unresolved, so a typo stays a typo.

## 2026-08-31 · `do_while` runs its first pass unconditionally

**Decided.** `do_while` is `while` with the first condition check skipped.

**Why.** "Fetch, then decide whether to fetch again" is the shape most loops against an
API actually have, and it cannot be written as a `while` without the null-binding above
carrying more weight than it should.

## 2026-08-31 · A loop produces its last pass, a fan-out produces a list

**Decided.** `foreach` and `parallel` produce lists in creation order; `while` and
`do_while` produce the last pass's value; `if` produces the taken branch's value.

**Why.** A loop that runs until something is true is asking for the state at the end. The
intermediate states are what it was getting past.

## 2026-08-31 · `-` as an output path means stdout

**Decided.** `tables/io.py:write` treats a path of `-` as stdout, in whatever format was
named. A binary format to a terminal is refused with the redirect spelled out.

**Why.** [[Invariants#1 stdout is data, stderr is interface]] only pays off if something
can actually write there. `--out report=- | jq` is the payoff.

**Note.** The format must be named — `-` has no extension, and guessing JSON would be a
silent choice about someone's data.

## 2026-08-31 · Pagination merges under the same envelope key

**Decided.** Without `into`, pages whose bodies share one envelope key are merged under
that key, keeping the first page's other fields.

**Why.** `@fetch.body.data` should mean on page 40 what it meant on page 1. Paging is not
supposed to change the shape.

## 2026-08-31 · A repeated page ends pagination

**Decided.** If a paginator produces a request it has already made, paging stops with
reason `repeated page`.

**Why.** The API claimed there was more and handed back the same page. Believing it is an
infinite loop; saying so is a bug report for them.

## 2026-08-31 · `concurrent` is reported as ignored, not silently dropped

**Decided.** `concurrent > 1` on `cursor`, `token`, or `link_header` logs a warning
naming the reason.

**Why.** Those three cannot know page N+1 before page N answers, so the request is
impossible rather than slow. A `concurrent=8` that quietly does nothing is a lie the user
pays for in wall-clock time.

## 2026-08-31 · The budget splits `run/sclpll` from `run/` — **ADR 0002**

**Decided.** `run/sclpll/` gets its own 1,200-line budget; `run/` gets 3,600; `expr/`
goes to 1,500. Total 16,000.

**Why.** `run/` went 54 over, and 866 of its lines were a lexer, parser, and emitter — a
language surface that grows with the *grammar*, not with what the runner *does*. The
3,200 was not wrong about the engine; it was measuring two things at once. The gate gets
sharper, not slacker.

→ `docs/adr/0002-budget-the-sclpll-surface-separately.md`, [[The Line Budget]]

## 2026-08-31 · `join`, `flatten`, `merge` are owned by the catalogue

**Decided.** Removed from `expr/ops/` registration; the built-in catalogue registers each
once and picks between the two shapes. Implementations stay as `join_text`,
`flatten_lists`, `merge_objects`.

**Replaced.** `join` collided outright at load. `flatten` was worse: `overload("flatten",
list)` silently shadowed record-flattening for exactly the input it is used on.

**Why.** Each name means two things and the first argument is the same type either way,
so the dispatch table cannot separate them. One owner, disambiguating on the second
argument, is the only honest arrangement.

→ [[Expressions#Three names the catalogue owns]]

## 2026-08-31 · `records_of` is the single definition of "the records"

**Decided.** One function in `tables/flatten.py`, called by the writers and the function
catalogue alike.

**Replaced.** `io.write` treated `{"data": [...]}` as one wide row while `flatten()`
reached through it. Same payload, two answers.

## 2026-08-31 · `@step name -> port` implemented

**Decided.** A step names the output port it fills; the bound path is supplied at call
time. A path written in the step still wins.

**Replaced.** The form was in the SPEC grammar and in no code, so a bound output port
could not reach a writer at all.

**Why.** The workflow says what it writes; the caller says where. That is what a port is
for.

## 2026-08-31 · `let` splits on `=` only for a bare identifier

**Decided.** `_binding` finds the first `=` that is not part of `==`, `!=`, `<=`, `>=`,
and only treats it as a name separator when what precedes it is an identifier.

**Replaced.** Splitting on the first `=` took `by=` out of `sum(@rows, by="total")` and
would have taken `==` out of any comparison.

## 2026-08-31 · `split_args` counts JSON brackets

**Decided.** `{` and `[` open a depth the splitter tracks, so a JSON literal is one
argument. `{{` is still read as interpolation first.

**Replaced.** `rename @p {"a": "b"}` arrived as three arguments.

## 2026-08-31 · Explode settles its column shape before building rows

**Decided.** Whether an exploded field produced `field_key` columns or stayed under
`field` is decided by scanning all elements first.

**Replaced.** A record with an empty array added an all-null `field` column beside the
`field_key` ones, in every output.

## 2026-08-31 · A non-`SclplError` from a function is wrapped

**Decided.** `_fn` wraps anything else with the step id and the function name.

**Why.** A bare `AttributeError: 'str' object has no attribute 'get'` names Python. The
reader needs the workflow.

---

## 2026-08-23 · The budget is revised from 7,150 to 14,200 — **ADR 0001**

**Why.** The original was estimated before any code existed and omitted `expr/ops/` and
`plugins_bundled/` entirely. A correction of an estimate, not a concession.

→ `docs/adr/0001-revise-the-line-budget.md`

## 2026-08-23 · The budget counts code, not docstrings

**Why.** Charging prose against the same budget as implementation buys less of the thing
that is harder to recover later.

## 2026-08-2x · `expr/refs.py` is the single reference scanner

**Replaced.** A scanner that handled `{{}}` and strings *starting* with `@`, so
`let count(@fetch.body)` produced no edge and the step ran before its dependency —
silently.

**Why.** [[Invariants#3 The DAG is inferred from references]] is only true if there is
one place that decides what a reference is.

## 2026-08-2x · Leaves are pinned in the store

**Replaced.** A leaf's refcount was 0, so the run's answer was disposed of on arrival.

**Why.** "No consumer in the graph" is not the same as "nobody wants it".

## 2026-08-2x · Cancellation re-raises outside the `except*` block

**Replaced.** The scheduler returned an `Outcome`, so `asyncio.run` believed the run
finished and Ctrl-C appeared to do nothing. A bare `raise` *inside* `except*` re-wraps it
in a group.

## 2026-08-2x · Nearest-name suggestions use Damerau-Levenshtein

**Replaced.** Plain Levenshtein suggested `id` for `pric`.

**Why.** A transposition is one typo and should cost one edit.

## 2026-08-21 · The whole of `app/` was deleted, not just the UI

**Why.** Not separable: `services/` imported `app.web.errors`, the SCLPLL compiler
imported `app.ui.app`. SPEC §4's target tree contains no `app/`.

→ [[M0 Deletion]]
