---
tags:
  - concept
---

# The Cache

`values/cache.py`. Not doing the same work twice.

## The key

Everything that could change the answer, and nothing else:

```
blake2b(step_kind, method, resolved_url, sorted_query, body_digest,
        headers_minus_volatile, function_name, function_version,
        input_value_digests, plugin_version, engine_version,
        credential_identity_salt)
```

The **"nothing else"** is the part that takes care.

**Mode is deliberately absent.** A key including it would mean a `partial` run and a
`full` run never share the fetch they have in common — which is most of the value a
cache has in a workflow tool.

**Volatile headers are excluded** — `Date`, `Authorization`, `User-Agent`, a request id,
a trace parent. Including them would make every key unique, which is a cache that never
hits.

**The credential is a salt, not a value.** Two people running the same workflow with
different tokens must not read each other's entries — they may be different tenants —
but the token itself has no business being part of a filename. What goes in is a hash
*of* it.

**`function_version` participates**, so changing what a function computes invalidates
the results that came from the old one rather than silently mixing them.

## The five flags

| Flag | Read | Write | On a miss |
|---|:-:|:-:|---|
| *(default)* | ✅ | ✅ | do the work |
| `--refresh` | ❌ | ✅ | do the work, replace what was there |
| `--no-cache` | ❌ | ❌ | do the work |
| `--offline` | ✅ | ❌ | **exit 5** |
| `--http-cache` | ✅ | ✅ | revalidate with ETag; a 304 counts as a hit |

Exit **5** rather than 1 because the work was *refused*, not attempted and failed. A
script running `--offline` on purpose wants to tell those apart.
→ [[Errors and Exit Codes]]

## What is never cached

**Control flow.** A `foreach` produces a graph, not a value; a cached loop would skip
the work its own body was the point of.

**Anything touching a file.** Two different reasons, one rule:

- a **writer** has an effect a hit cannot reproduce — it would report a path it did not
  write to
- a **reader** is keyed on its path, and a path is not its contents. Caching it would
  serve yesterday's file from today's name, which is the worst kind of wrong because it
  looks right

Keying a reader on mtime and size would fix the second, but a local file read is neither
slow nor rate-limited, and the cache exists for things that are.

**Anything a step turned off** with `cache off`.

## An assertion still runs on a hit

A cached value that no longer satisfies an assertion is exactly the case the assertion
exists for. The value is reused; the check is not skipped.

## Storage

Content-addressed blobs, plus a SQLite index over them.

The blob's name is the digest of its own contents, which buys two things: two steps
producing the same value share one file, and a half-written blob can never be mistaken
for a good one — its name would not match. Writes go beside and rename.

The **index is the source of truth** about what exists. A blob with no row is garbage
from an interrupted write, collected on the next prune. A row with no blob is a miss,
which is safe — the work is simply done again.

TTL defaults to a day; the size cap to 2 GB with LRU eviction. Pruning happens at the
*end* of a run: eviction is bookkeeping, and doing it mid-pipeline spends time the
pipeline wanted.

## Where it lives

`$SCLPL_CACHE_DIR`, else `%LOCALAPPDATA%\sclpl\cache` or `$XDG_CACHE_HOME/sclpl` or
`~/.cache/sclpl`. The platform's convention rather than an invented one, so it is where
a user's cleanup tools already look.

→ [[Memory and Spilling]], [[Step Kinds]]
