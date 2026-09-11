---
tags:
  - guide
---

# Writing a Workflow

A worked example, from one request to a joined report. Every fragment below is real
syntax — see [[SCLPLL Reference]] for the full grammar.

## The smallest thing that works

```
@workflow hello

@step fetch
  get https://api.example.com/orders
```

```bash
sclpl run hello.sclpll
```

Nothing is written, because nothing said to write anything. Add that:

```
@workflow hello

@output report:csv

@step fetch
  get https://api.example.com/orders

@step write -> report
  save_csv @fetch.body
```

```bash
sclpl run hello.sclpll orders.csv     # or --out report=-  to pipe it
```

`@fetch.body` is a real Python object, not text ([[Typed Values]]). `save_csv` flattens
nested objects into underscore columns and reaches one level through a `{"data": […]}`
envelope ([[Tables and Flattening]]).

## Variables and interpolation

```
@var base = "https://api.example.com"
@var page_size = 100

@step fetch
  get {{base}}/orders
  query limit={{page_size}}
```

`--var base=http://localhost:8000` overrides at the command line. `{{ }}` produces a
string; a bare `@ref` keeps its type.

## Dependencies are not declared

```
@step fetch
  get {{base}}/orders

@step count
  let count(@fetch.body.data)
```

`count` waits for `fetch` because it says `@fetch` — [[Invariants#3 The DAG is inferred from references]].
There is no `needs:` list to keep in sync. Steps can appear in any order in the file.

## Checking the data

```
@rule fetched_ok = @fetch.status == 200

@step fetch
  get {{base}}/orders
  assert fetched_ok

@step checked
  assert_rowcount @fetch.body.data min=1
```

An assertion failure exits **4**, not 1, so a script can tell "the data was wrong" from
"the request failed" ([[Errors and Exit Codes]]).

## Pagination

```
@step fetch
  get {{base}}/orders
  paginate cursor cursor_path=next_cursor param=cursor max_pages=40
```

`@fetch.body` is now every page merged, with the same shape one page had.
→ [[Pagination]]

## Joining two sources

```
@step orders
  get {{base}}/orders

@step customers
  get {{base}}/customers

@step shaped_orders
  flatten @orders.body

@step shaped_customers
  flatten @customers.body

@step joined
  join @shaped_orders @shaped_customers customer_id how=left
```

`orders` and `customers` run **at the same time** — nothing connects them until `joined`.

## Looping

```
@step ids
  let @fetch.body.data[*].id

@step details
  foreach @ids as id
    step one
      get {{base}}/orders/{{id}}
```

`@details` is the list of results, in element order. The iterations are real graph nodes,
so the concurrency ceiling still holds — twenty of them against a host limited to four
run four at a time. → [[Control Flow]]

## Modes

```
@mode smoke "One page, fetch only"
  include fetch
  limit max_pages=1
```

```bash
sclpl run hello.sclpll -m smoke
```

A mode can only **subtract**. Pruning something a kept step needs is caught at validate
time with the fix named. → [[Modes and Ports]]

## Calling an ordinary Python script

```
@step scored
  python "score" args=["--model", "v2"] input=@checked
```

`args` remains the script's normal command line. `input` is JSON on stdin, and JSON stdout is
the `@scored` value. Put logging on stderr. Register `score` with a local `path` or provider
`uri` plus SHA-256 in `sclpl.toml`; it can then run by itself with `sclpl python score --model v2`
and shares SCLPL's active Python environment.

The boundary is for trusted code, not sandboxing. The alias and digest prevent arbitrary or
silently changed scripts from running. Package and declare a plugin when callers need discovery
or capability policy.

## Before you run it

```bash
sclpl validate hello.sclpll     # no network, no writes
sclpl explain hello.sclpll -m smoke
sclpl fmt hello.sclpll          # canonical form
```

`explain` shows the plan, what the mode pruned, the critical path, and how many roots
can start at once.
