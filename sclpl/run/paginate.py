"""Following a paginated source: five strategies, one loop.

A paginator's whole job is to answer one question -- *given what the last page said,
what is the next request, and is there one at all?* Everything else about paging is the
same regardless of strategy, so everything else lives in `follow()` and each strategy is
a handful of lines.

The five, and what distinguishes them:

| Strategy | Next page comes from | Ends when |
|---|---|---|
| `cursor` | an opaque token in the body, at `cursor_path` | the token is absent or null |
| `token` | the same, sent as a header rather than a query parameter | the token is absent or null |
| `page` | a page *number*, incremented | a page comes back empty |
| `offset` | a row offset, advanced by `size` | a page returns fewer than `size` |
| `link_header` | the `Link:` header, `rel="next"` (RFC 8288) | no `next` link |

`cursor`, `token`, and `link_header` are inherently sequential: page N+1 is unknown
until page N answers. `page` and `offset` are not -- their URLs are computable ahead of
time -- which is why `concurrent` only means anything for those two, and is reported as
ignored rather than silently doing nothing on the other three.

**Stopping is over-determined on purpose.** A run against an API that never stops
saying "there is more" must still end: `max_pages`, an empty page, an unchanged cursor,
and `stop_when` are each sufficient, and the repeated-cursor check is what catches the
API that answers the same page forever.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from sclpl.errors import StepFailed, ValidationError
from sclpl.run.ir import Pagination
from sclpl.tables.flatten import ENVELOPES

#: A safety net, not a policy. `max_pages` is the policy; this stops a workflow that
#: forgot one from paging until the disk fills.
HARD_CEILING = 10_000

#: `Link: <https://x/?page=2>; rel="next", <...>; rel="last"`
_LINK = re.compile(r'<([^>]+)>\s*;\s*rel\s*=\s*"?([^",;]+)"?')


@dataclass(slots=True)
class Page:
    """One fetched page: the decoded body, and what the response said about it."""

    body: Any
    status: int
    headers: dict[str, str]
    url: str
    elapsed_ms: int


@dataclass(slots=True)
class Follow:
    """The result of following a source to its end."""

    pages: list[Page] = field(default_factory=list)
    #: Why paging stopped, for the progress line and for `-vv`.
    reason: str = "exhausted"
    #: True when a ceiling cut it short, which is a different thing from finishing.
    truncated: bool = False

    @property
    def count(self) -> int:
        return len(self.pages)


#: What `follow` calls to fetch one page. Given query overrides, header overrides, and
#: an absolute URL to use instead of the step's own, it returns a `Page`.
Fetch = Callable[[dict[str, Any], dict[str, str], str | None], Awaitable[Page]]

#: What `follow` calls to evaluate `stop_when` against a page. True ends paging.
StopWhen = Callable[[Page], Awaitable[bool]]


async def follow(
    spec: Pagination,
    fetch: Fetch,
    *,
    stop_when: StopWhen | None = None,
    max_pages: int | None = None,
    on_page: Callable[[int, Page], None] | None = None,
) -> Follow:
    """Fetch pages until the source, or a ceiling, says to stop.

    ``max_pages`` from the caller (a mode's `limit`, or `--max-pages`) overrides the
    one on the spec when it is lower. A mode that says "one page" must mean it even if
    the workflow says forty.
    """
    ceiling = _ceiling(spec, max_pages)
    result = Follow()
    state = _state_for(spec)
    seen: set[str] = set()

    query, headers, url = state.first()
    for index in range(ceiling):
        page = await fetch(query, headers, url)
        result.pages.append(page)
        if on_page is not None:
            on_page(index + 1, page)

        if stop_when is not None and await stop_when(page):
            result.reason = "stop_when"
            return result

        step = state.advance(page)
        if step is None:
            result.reason = state.reason
            return result

        query, headers, url = step
        marker = f"{url}|{sorted(query.items())}|{sorted(headers.items())}"
        if marker in seen:
            # The API answered "there is more" and then handed back the same request.
            # Believing it is an infinite loop; saying so is a bug report for them.
            result.reason = "repeated page"
            return result
        seen.add(marker)

    result.reason = f"max_pages ({ceiling})"
    result.truncated = True
    return result


def merge(pages: Sequence[Page], into: str | None, extract: Callable[[Any, str], Any]) -> Any:
    """Combine page bodies into the value the step produces.

    Three cases, in the order they are tried:

    1. `into` names where the items are -- concatenate exactly those.
    2. Every body is a list -- concatenate them.
    3. Every body wraps its list under the same envelope key -- concatenate under that
       key and keep the first page's other fields. `@fetch.body.data` then means what it
       meant on page one, which is the point: paging should not change the shape.

    Anything else becomes the list of bodies, because inventing a merge for a shape we
    do not recognise would be guessing with the user's data.
    """
    bodies = [page.body for page in pages]
    if not bodies:
        return []
    if len(bodies) == 1 and into is None:
        return bodies[0]

    if into is not None:
        items: list[Any] = []
        for body in bodies:
            found = extract(body, into)
            items.extend(found if isinstance(found, list) else [found])
        return items

    if all(isinstance(body, list) for body in bodies):
        return [item for body in bodies for item in body]

    if all(isinstance(body, dict) for body in bodies):
        key = _common_envelope(bodies)
        if key is not None:
            merged = dict(bodies[0])
            merged[key] = [item for body in bodies for item in body.get(key, [])]
            return merged

    return bodies


def _common_envelope(bodies: list[Any]) -> str | None:
    """The one envelope key every page has a list under, if there is exactly one."""
    shared = [key for key in ENVELOPES if all(isinstance(body.get(key), list) for body in bodies)]
    return shared[0] if len(shared) == 1 else None


def _ceiling(spec: Pagination, override: int | None) -> int:
    limits = [HARD_CEILING]
    if spec.max_pages is not None:
        limits.append(spec.max_pages)
    if override is not None:
        limits.append(override)
    return max(1, min(limits))


# -- the strategies ---------------------------------------------------------------
#
# Each holds whatever it needs between pages and answers `advance`. Returning None
# means there is no next page, and `reason` says why -- which is what the progress line
# and `-vv` report, so "the cursor ran out" and "the page came back empty" stay
# distinguishable after the fact.

_Step = tuple[dict[str, Any], dict[str, str], str | None]


class _Strategy:
    reason = "exhausted"

    def first(self) -> _Step:
        return {}, {}, None

    def advance(self, page: Page) -> _Step | None:
        raise NotImplementedError


class _Cursor(_Strategy):
    """An opaque token in the body, sent back as a query parameter."""

    def __init__(self, spec: Pagination, *, in_header: bool = False) -> None:
        self._path = spec.cursor_path or "next_cursor"
        self._param = spec.param or ("X-Next-Token" if in_header else "cursor")
        self._in_header = in_header

    def advance(self, page: Page) -> _Step | None:
        token = dig(page.body, self._path)
        if token is None or token == "":
            self.reason = "no cursor"
            return None
        if self._in_header:
            return {}, {self._param: str(token)}, None
        return {self._param: token}, {}, None


class _Page(_Strategy):
    """A page number, incremented until a page comes back empty."""

    def __init__(self, spec: Pagination) -> None:
        self._param = spec.param or "page"
        self._size = spec.size
        self._number = 1

    def first(self) -> _Step:
        return {self._param: self._number}, {}, None

    def advance(self, page: Page) -> _Step | None:
        if _items_in(page.body) == 0:
            self.reason = "empty page"
            return None
        if self._size is not None and _items_in(page.body) < self._size:
            self.reason = "short page"
            return None
        self._number += 1
        return {self._param: self._number}, {}, None


class _Offset(_Strategy):
    """A row offset, advanced by the page size."""

    def __init__(self, spec: Pagination) -> None:
        if spec.size is None:
            raise ValidationError(
                "offset pagination needs to know the page size",
                remedies=["add size=<n> to the paginate line"],
            )
        self._param = spec.param or "offset"
        self._size = spec.size
        self._offset = 0

    def first(self) -> _Step:
        return {self._param: 0}, {}, None

    def advance(self, page: Page) -> _Step | None:
        seen = _items_in(page.body)
        if seen < self._size:
            self.reason = "short page" if seen else "empty page"
            return None
        self._offset += self._size
        return {self._param: self._offset}, {}, None


class _LinkHeader(_Strategy):
    """The `Link:` header, `rel="next"` (RFC 8288). GitHub's convention, and others'."""

    def advance(self, page: Page) -> _Step | None:
        header = page.headers.get("link") or page.headers.get("Link") or ""
        for url, rel in _LINK.findall(header):
            if rel.strip().lower() == "next":
                return {}, {}, url
        self.reason = "no next link"
        return None


def _state_for(spec: Pagination) -> _Strategy:
    match spec.strategy:
        case "cursor":
            return _Cursor(spec)
        case "token":
            return _Cursor(spec, in_header=True)
        case "page":
            return _Page(spec)
        case "offset":
            return _Offset(spec)
        case "link_header":
            return _LinkHeader()
        case _:  # pragma: no cover - the IR's Literal already refuses anything else
            raise ValidationError(f"unknown pagination strategy {spec.strategy!r}")


# -- helpers ----------------------------------------------------------------------


def dig(body: Any, path: str) -> Any:
    """Follow a dotted path into a decoded body, tolerating a missing branch.

    A cursor that is not there is how paging ends, so an absent path is an answer
    rather than an error -- unlike a path in an expression, where it is a typo.
    """
    current = body
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _items_in(body: Any) -> int:
    """How many records a page carried, for the strategies that stop on an empty one."""
    if isinstance(body, list):
        return len(body)
    if isinstance(body, dict):
        for key in ENVELOPES:
            nested = body.get(key)
            if isinstance(nested, list):
                return len(nested)
        return 1
    return 0 if body is None else 1


def unsupported_concurrency(spec: Pagination) -> str | None:
    """Why `concurrent` cannot be honoured, when it cannot.

    Three of the five strategies cannot know page N+1 before page N answers, so asking
    for concurrency is asking for something impossible rather than something slow. Said
    out loud, because a `concurrent=8` that quietly does nothing is a lie the user pays
    for in wall-clock time.
    """
    if spec.concurrent <= 1:
        return None
    if spec.strategy in ("page", "offset"):
        return None
    return (
        f"{spec.strategy} pagination is sequential -- the next page is unknown until the "
        f"current one answers -- so concurrent={spec.concurrent} is ignored"
    )


def check(spec: Pagination) -> None:
    """Preflight: everything about a paginate line that can be wrong before running."""
    if spec.strategy == "offset" and spec.size is None:
        raise ValidationError(
            "offset pagination needs to know the page size",
            remedies=["add size=<n> to the paginate line"],
        )
    if spec.strategy in ("cursor", "token") and spec.cursor_path is None:
        raise ValidationError(
            f"{spec.strategy} pagination needs to know where the next token is",
            remedies=[
                "add cursor_path=<path>, e.g. cursor_path=meta.next",
                "use `paginate link_header` if the API uses a Link header instead",
            ],
        )


def failed(step: str, error: Exception, page: int) -> StepFailed:
    """A paging failure that says which page, because page 1 and page 37 differ."""
    return StepFailed(
        f"step {step!r} failed on page {page}: {error}",
        remedies=[
            "max_pages=<n> on the paginate line caps how far it goes",
            "the pages already fetched are discarded -- the step produces all or nothing",
        ],
    )
