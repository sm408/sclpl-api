---
tags:
  - concept
---

# Pagination

`run/paginate.py`. Five strategies, one loop.

A paginator answers exactly one question: *given what the last page said, what is the
next request, and is there one at all?* Everything else about paging is the same
regardless of strategy, so everything else lives in `follow()` and each strategy is a
handful of lines.

## The five

| Strategy | Next page comes from | Ends when |
|---|---|---|
| `cursor` | an opaque token in the body, at `cursor_path` | the token is absent or null |
| `token` | the same, sent as a **header** rather than a query parameter | the token is absent or null |
| `page` | a page *number*, incremented | a page comes back empty (or short, if `size` is known) |
| `offset` | a row offset, advanced by `size` | a page returns fewer than `size` |
| `link_header` | the `Link:` header, `rel="next"` (RFC 8288) | no `next` link |

```
paginate cursor cursor_path=next_cursor param=cursor max_pages=40
paginate token  cursor_path=meta.next param=X-Next-Token
paginate page   param=page size=100
paginate offset param=offset size=100
paginate link_header
```

## Stopping is over-determined on purpose

A run against an API that never stops saying "there is more" must still end. Each of
these is sufficient:

1. `max_pages` on the paginate line, or a mode's `limit max_pages=`, whichever is lower
2. `stop_when`, an expression evaluated against each page
3. the strategy's own exhaustion signal
4. **a repeated request** — the API claimed there was more and handed back the same
   page; believing it is an infinite loop, and saying so is a bug report for them
5. `HARD_CEILING` (10,000) — a safety net, not a policy, for a workflow that forgot one

`Follow.reason` records which, so "the cursor ran out" and "the page came back empty"
stay distinguishable after the fact. `truncated` marks the ones that were cut short,
which is a different thing from finishing, and produces a warning.

## Merging pages

`paginate.merge`, in the order it tries them:

1. `into` names where the items are → concatenate exactly those
2. every body is a list → concatenate them
3. every body wraps its list under **the same** envelope key → concatenate under that
   key and keep the first page's other fields

Case 3 is what makes `@fetch.body.data` mean on page 40 what it meant on page 1. Paging
should not change the shape.

Anything else becomes the list of bodies, because inventing a merge for a shape we do
not recognise would be guessing with someone's data.

## Concurrency

`concurrent` only means anything for `page` and `offset`, whose URLs are computable
ahead of time. `cursor`, `token`, and `link_header` cannot know page N+1 before page N
answers.

Asking for concurrency on those three is asking for something impossible rather than
something slow, so it is **reported as ignored**. A `concurrent=8` that quietly does
nothing is a lie the user pays for in wall-clock time.

## Preflight

`paginate.check` catches what can be known before running: `offset` with no `size`
cannot advance, and `cursor`/`token` with no `cursor_path` cannot find their token. Both
fail identically at runtime — one page, then nothing — which reads as "the API only had
one page" rather than as a mistake.
