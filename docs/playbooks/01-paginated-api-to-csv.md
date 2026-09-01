# Paginated API → CSV

The thing this tool is for. Ten minutes from nothing to a file.

The workflow below is `examples/playbook-01.sclpll`, and it runs in CI against the mock
server — so if this page is wrong, the build fails.

## 1. One request

```bash
sclpl call GET https://api.example.com/orders | head
```

`call` writes the body to **stdout** and progress to **stderr**, so it pipes.

## 2. Make it a workflow

```
@workflow orders "Every order, as a CSV"

@var base = "https://api.example.com"

@output report:csv

@step fetch
  get {{base}}/orders
  query limit=100

@step write -> report
  save_csv @fetch.body
```

```bash
sclpl validate orders.sclpll     # no network, no writes
sclpl run orders.sclpll out.csv
```

`save_csv` flattens nested objects into underscore columns and reaches one level through
a `{"data": […]}` envelope, so `@fetch.body` usually does the right thing without you
saying how.

## 3. Get every page

```
@step fetch
  get {{base}}/orders
  query limit=100
  paginate cursor cursor_path=next_cursor param=cursor max_pages=40
```

`@fetch.body` is now every page merged, **with the same shape one page had** — so
nothing downstream changes.

If your API pages differently:

| It sends | Use |
|---|---|
| a cursor in the body | `paginate cursor cursor_path=next param=cursor` |
| a token in a header | `paginate token cursor_path=meta.next param=X-Next-Token` |
| page numbers | `paginate page param=page size=100` |
| row offsets | `paginate offset param=offset size=100` |
| a `Link:` header | `paginate link_header` |

`sclpl validate` catches a paginate line missing what its strategy needs — before the
first request.

## 4. Check it before you trust it

```
@rule fetched_ok = @fetch.status == 200

@step fetch
  get {{base}}/orders
  assert fetched_ok

@step checked
  assert_rowcount @fetch.body.data min=1
```

An assertion failure exits **4**, not 1. A script can tell "the data was wrong" from "the
request failed" — two problems with entirely different responses.

## 5. Authenticate

```bash
sclpl secret set api-token
```

Prompted without echo, so it stays out of your shell history. Stored in the OS keyring.

```
@step fetch
  get {{base}}/orders
  header Authorization: Bearer {{secret('api-token')}}
```

The token is redacted from every log, label, and trace, because redaction happens in the
reporter rather than at each call site.

## 6. Run it for real

```bash
sclpl run orders.sclpll out.csv
sclpl run orders.sclpll --out report=- | head    # or pipe it
```

## What to read next

- Something is wrong → [Debugging](04-debugging.md)
- Two sources to combine → [Joining](02-joining-sources.md)
- Run it every night → [Automating](03-automating.md)
