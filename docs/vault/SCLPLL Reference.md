# SCLPLL Reference

Whitespace-significant, line-oriented. Directives start with `@` at column 0; step
bodies are indented. v2 is a clean break — there is no v1 converter
([[Locked Decisions#4 SCLPLL v2 is a clean break]]).

The other surface is JSON, and the two are equivalent because both go through
[[The IR]]. `sclpl convert` moves between them; `sclpl fmt` rewrites in canonical form
(stable ordering, two-space indent, one blank line between steps).

## Directives

| Directive | Form |
|---|---|
| `@workflow` | `@workflow name ["description"]` |
| `@version` | `@version 2` |
| `@description` | `@description "..."` |
| `@default_mode` | `@default_mode partial` |
| `@var` | `@var name = value` |
| `@rule` | `@rule name = expression` |
| `@input` | `@input name[:format][?]` — `?` means optional |
| `@output` | `@output name[:format]` |
| `@limits` | `@limits concurrency=8 host_concurrency=4 timeout=20` |
| `@mode` | `@mode name ["description"]` + indented clauses |
| `@step` | `@step id [<- deps] [-> port]` + indented body |

## Steps

```
@step name <- explicit_dep -> output_port
  <verb> <args>
  <clause> <args>
```

`<-` **adds** an edge; it can never remove one inferred from a reference.
`->` names the output port this step writes ([[Modes and Ports#Writing to a port]]).

The **first line decides the kind**:

| First verb | Kind |
|---|---|
| `get` `post` `put` `patch` `delete` `head` `options` | `http` |
| `let` | `let` |
| `foreach` | `foreach` |
| `when` | `if` |
| `while` / `do_while` | `while` / `do_while` |
| `parallel` | `parallel` |
| `gate` | `gate` |
| anything else | `fn` — resolved against the function and connector registries |

That last row is what keeps the grammar small while plugins stay first-class: an unknown
verb is not a parse error, it is a lookup.

## Request clauses

```
@step fetch
  get {{base}}/orders
  header Authorization: Bearer {{@auth.token}}
  query limit=100 status=open
  body {"note": "hello"}
  timeout 30
  paginate cursor cursor_path=next param=cursor max_pages=40
  extract @response.body.data
```

## Clauses on any step

```
  tag api slow
  assert fetched_ok
  when @flag == true          # skip unless
  retry_if @fetch.status == 503
  retry 3
  lane process
  keep
  cache ttl=3600
```

## Control flow

```
@step loop
  foreach row in @rows        # also: foreach @rows as row, or foreach @rows
    step one
      get {{base}}/x/{{row.id}}
    step two
      let @one.body.value

@step choose
  when count(@rows) > 10
    step big
      let "many"
    otherwise
      step small
        let "few"

@step climb
  do_while @page.body.has_more
    step page
      get {{base}}/next

@step both
  parallel
    branch
      step left
        let "L"
    branch
      step right
        let "R"

@step barrier
  gate "everything above must land first"
```

A body is a **sequence**: each step waits for the one before it. → [[Control Flow]]

## Modes

```
@mode partial "Skip the reporting half"
  include fetch_* shape_*      # id, glob, or tag:name
  exclude fetch_slow
  limit max_pages=1
  vars page_size=10
  stub enrichment={"total": 0}

@mode full all
@mode nightly
  extends full
```

## Literals

Numbers, `true`, `false`, `null`, quoted strings, JSON arrays and objects.

```
  let [1, 2, 3]
  rename @products {"sku": "code"}
```

A JSON literal is **one** argument even though it contains spaces —
`rename @p {"a": "b"}` is two arguments, not three. `{{` is read as interpolation before
a bare `{`, so an object literal cannot start with another object; write `{ {"a": 1} }`
in the rare case it must.

## `let` and `=`

`let total = sum(@rows)` and `let sum(@rows)` mean the same thing — the step id is the
name either way. The `=` only separates a name when what precedes it is a bare
identifier and the `=` stands alone, so `let sum(@rows, by="total")` and
`let count(@rows) == 3` both keep their whole expression.
