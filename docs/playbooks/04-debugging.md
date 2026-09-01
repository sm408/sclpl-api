# When something is wrong

In the order worth trying.

## 1. `validate` — costs nothing, catches most of it

```bash
sclpl validate orders.sclpll --mode partial
```

No network, no writes. It checks the ports bind, the mode leaves the graph closed, every
reference resolves, there are no cycles, every expression parses, every function exists,
every `-> port` names a real port, and every paginate line has what its strategy needs.

Every message names the problem *and* what to do about it. A message without a remedy is
a bug in the message.

## 2. `explain` — what will actually happen

```bash
sclpl explain orders.sclpll --mode partial
```

Shows what the mode pruned, what each step waits for, the critical path, and how many
roots can start at once.

**A step running later than you expected almost always has an edge you did not intend** —
usually a reference you forgot was in a string. The graph is inferred, so `explain` is
where you see what it inferred.

```bash
sclpl explain orders.sclpll --memory
```

Where each value is freed. A leaf shows as *held*: nothing reads it, but it is what the
run produced.

## 3. `-v`, `-vv`, `-vvv`

```bash
sclpl -vv run orders.sclpll out.csv
```

`-v` adds per-step detail and pagination progress. `-vv` adds resolved values and freed
bindings. `-vvv` adds every admission decision the scheduler made.

## 4. Read the error

Every diagnostic names what was wrong and what was there instead:

```
error [merge_products]: cannot join on 'sku': the left table has no such column
  - left columns: id, customer_id, total, lines, customer_name
```

A misspelled name gets a suggestion. Damerau-Levenshtein, so a transposition costs one
edit — `pric` suggests `price`, not `id`.

## Common shapes

| Symptom | Usually |
|---|---|
| `nothing produces @x` | A typo. The suggestion is usually right |
| A step ran before its data existed | An edge you did not intend. Check `explain` |
| A CSV with one very wide row | The payload was an envelope. Report it — that should be handled |
| Only one page came back | Check the `paginate` line; `validate` catches a missing `cursor_path` or `size` |
| Exit 4 | The **data** was wrong. The requests were fine |
| Exit 3 | Nothing ran. Fixing and re-running costs nothing |
| A loop produced `[]` | Its collection was empty. That is not an error — `assert_rowcount` if you disagree |
| It is slower than expected | `explain` shows the critical path; `--concurrency` may be capped by `@limits` |

## Getting help from someone else

```bash
sclpl doctor                      # what is installed, and what is missing
sclpl runs export <id> --into bug.json
```

`doctor` checks the secret backend, pandas, HTTP/2, the terminal, memory, the cache
directory, and every plugin — and each line is either fine or names the command that
fixes it.

`runs export` is the whole run: what it did, step by step, with timings and errors. It
contains no secrets, because secrets never reach a log.

## Reproducing yesterday

```bash
sclpl runs list
sclpl runs show <id>
sclpl runs diff <yesterday> <today>
sclpl runs replay <id>          # prints the command; edit it and run it
```

`diff` puts status first and timing last, because a run that failed where the other
succeeded is the answer to "what changed" and a hundred milliseconds is not.
