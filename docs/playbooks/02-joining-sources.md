# Joining two sources

An API and a database, or two APIs, or a file and an API. The join is the same either
way, because everything is records by the time it gets there.

`examples/playbook-02.sclpll` runs this in CI.

## Two fetches run at once

```
@workflow enriched

@var base = "https://api.example.com"

@output report:csv

@step orders
  get {{base}}/orders
  paginate cursor cursor_path=next param=cursor

@step customers
  get {{base}}/customers
```

Nothing connects them, so they run **at the same time**. You did not ask for that and
you cannot turn it off by accident: the graph is inferred from references, and there are
none between these two.

## Flatten, then join

```
@step shaped_orders
  flatten @orders.body

@step shaped_customers
  flatten @customers.body

@step joined
  join @shaped_orders @shaped_customers customer_id how=left
```

`how` is `inner`, `left`, `right`, or `outer`. A join key that is not in one of the
tables says which side is missing it and lists the columns that *are* there.

> Nested objects flatten to underscore columns, so `{"customer": {"id": 1}}` joins on
> `customer_id`, not `id`. If the names do not line up, `rename` one side:
> `rename @shaped_regions {"region_id": "customer_region_id"}`.

## Bring in a database

```
@step local
  sqlite.query orders.sqlite "select id, note from annotations"

@step merged
  join @local @shaped_orders id how=left

@step store
  sqlite.write @merged orders.sqlite enriched
```

SQLite ships as a bundled plugin. No configuration, no connection string, no driver to
install — `sqlite3` is in the standard library.

`sqlite.write` takes the **union** of the columns across all records, so a field some
rows omit is not dropped for everybody. It widens an existing table rather than failing
when a new field appears.

## Aggregate

```
@step by_city
  group_agg @joined city agg={"total": "sum", "id": "count"}

@step ranked
  sort_by @by_city total_sum descending=true
```

## Check the shape before writing

```
@step verified
  assert_schema @joined {"id": "integer", "customer_name": "string", "total": "number"}
```

An extra column is fine unless you pass `strict=true` — an API adding a field should not
break a workflow that ignores it. An integer column satisfies `number`, because that
widening never loses information.

## What to read next

- It is slow, or wrong → [Debugging](04-debugging.md)
- Run it on a schedule → [Automating](03-automating.md)
