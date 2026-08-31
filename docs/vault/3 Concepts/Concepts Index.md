---
tags:
  - concept
  - moc
---

# Concepts Index

Every idea in `sclpl` that has a name.

## The document

- [[The IR]] — the one representation, and the two surfaces over it
- [[SCLPLL Reference]] — the whitespace-significant surface
- [[Modes and Ports]] — subsetting a workflow, and binding it to files

## The graph

- [[The DAG]] — inferred from references, never declared
- [[The Scheduler]] — a ready queue, ordered semaphores, no barrier waves
- [[Lanes]] — the loop, a thread, or a process, and how one is chosen
- [[Control Flow]] — `foreach`, `if`, `while`, `parallel`, `gate` as injected subgraphs
- [[Step Kinds]] — the eight things a step can be

## Values

- [[Typed Values]] — the invariant, and where it is enforced
- [[The Value Store]] — refcounts, liveness, freeing
- [[Memory and Spilling]] — watermarks, and finishing rather than dying
- [[The Cache]] — what is keyed, what is never cached, and the five flags
- [[Expressions]] — the allowlisted AST, paths, and dispatch
- [[Tables and Flattening]] — the reference semantics for nested JSON

## The outside world

- [[Transport]] — pooled clients, breakers, retries
- [[Pagination]] — five strategies, one loop
- [[The Terminal Layer]] — events, the single writer, the ladder
- [[Errors and Exit Codes]] — what each code means and who should act on it

## Extending

- [[Extending sclpl]] — functions, connectors, plugins
- [[The Line Budget]] — the size gate, and why it exists
