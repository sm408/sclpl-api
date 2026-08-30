# Modes and Ports

Two mechanisms that let one workflow file serve several situations without becoming
several files.

## Modes

A **mode** is a named subset. `run/modes.py`.

```
@mode partial "Skip enrichment and reporting"
  include fetch_* shape_* merge_* write_*
  limit max_pages=1

@mode full all

@mode smoke
  include fetch_orders
  limit max_pages=1
```

Resolution, in order:

1. Resolve the `extends` chain, deepest first; later specs override earlier scalars
2. Start from all steps if `all`, else from `include` matches (id, glob, or `tag:`)
3. Subtract `exclude` matches
4. **Closure check** — for every kept step, every dependency must be kept, bound to an
   input port, available in cache under `--from-cache`, or supplied by `stub`
5. Apply `vars` and `limit` overrides
6. Prune the DAG

Step 4 is the one that earns the feature. Pruning a needed producer is caught **at
validate time** with the missing producer named and all three remedies listed — not at
runtime, forty seconds in.

[[Invariants#6 Modes only subtract steps and override scalars]] is enforced by
validating that the pruned IR is a subgraph of the full IR. A mode can never add a step,
change `needs`, or alter an expression.

> A quoted string straight after the mode name is its **description**. Reading it as an
> include selector would silently select nothing and run the wrong subset — which was a
> real bug.

## Ports

A **port** is a named file the workflow expects, declared rather than hard-coded.

```
@input customers:csv
@input extra:json?          # optional
@output report:csv
```

Binding precedence, highest first (`run/ports.py`):

1. `--in name=path` / `--out name=path`
2. **Positional** arguments, in declaration order: inputs first, then outputs
3. Defaults declared on the port

`-` means stdin/stdout. A glob binds a sorted list of paths. `path:format` overrides
what the extension implies. A count mismatch is a preflight error that **lists the
ports** — "expected 3 arguments, got 2" without saying which three is a puzzle.

### Positional binding

An optional port takes a positional argument only when enough remain to cover the
required ports after it. Given `<customers> <extra?> <report>`:

```
sclpl orders in.csv out.csv              → customers=in.csv, report=out.csv
sclpl orders in.csv extra.json out.csv   → all three
```

Without the look-ahead the first form would bind `out.csv` to `extra`.

### Writing to a port

```
@step write_report -> report
  save_csv @merge_regions
```

The workflow says *what* it writes; the caller says *where*. `run/execute.py:_bind_output`
supplies the bound path when the step did not give one — and a path written in the step
still wins, so naming a port never silently redirects a file someone spelled out.

Preflight checks the port is declared, with a suggestion for a near miss.

### Missing output directories

Refused, with the exact `mkdir`. A step writing a nested literal path creates it; a
*bound* port does not, because `--out report=reprot/out.csv` is a typo worth catching
before any request is paid for.

## `validate` vs `run`

`require_ports` separates two questions. `validate <wf>` asks whether the workflow is
well-formed — true or false regardless of which files today's invocation binds. `run`
asks whether *this* invocation can proceed, which needs every required port bound.
