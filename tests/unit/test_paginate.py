"""The five paginators, and the several ways paging is made to stop.

Every strategy is exercised against a fake `fetch` rather than a server: what is under
test is the decision "is there another page, and what is it", which is the whole of what
a paginator does. The transport is tested elsewhere.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from sclpl.errors import ValidationError
from sclpl.run import paginate
from sclpl.run.ir import Pagination

TOTAL = 95
SIZE = 10


def rows(start: int, count: int = SIZE) -> list[dict[str, int]]:
    return [{"id": n} for n in range(start, min(start + count, TOTAL))]


def fetcher(shape: str) -> tuple[paginate.Fetch, list[dict[str, Any]]]:
    """A `fetch` that answers like one of the real API shapes, and a log of its calls."""
    seen: list[dict[str, Any]] = []

    async def fetch(
        query: dict[str, Any], headers: dict[str, str], url: str | None
    ) -> paginate.Page:
        seen.append({"query": dict(query), "headers": dict(headers), "url": url})
        response: dict[str, Any] = {}
        extra: dict[str, str] = {}

        if shape == "cursor":
            start = int(query.get("cursor", 0))
            nxt = start + SIZE
            response = {"data": rows(start), "next_cursor": nxt if nxt < TOTAL else None}
        elif shape == "token":
            start = int(headers.get("X-Next-Token", 0))
            nxt = start + SIZE
            response = {"data": rows(start), "meta": {"next": nxt if nxt < TOTAL else None}}
        elif shape == "page":
            page = int(query.get("page", 1))
            response = {"data": rows((page - 1) * SIZE)}
        elif shape == "offset":
            response = {"data": rows(int(query.get("offset", 0)))}
        elif shape == "link":
            page = int((url or "?p=1").rsplit("p=", 1)[-1])
            response = {"data": rows((page - 1) * SIZE)}
            if page * SIZE < TOTAL:
                extra["link"] = (
                    f'<https://x/?p={page + 1}>; rel="next", <https://x/?p=9>; rel="last"'
                )
        elif shape == "stuck":
            response = {"data": rows(0), "next_cursor": 0}

        return paginate.Page(
            body=response, status=200, headers=extra, url=url or "https://x/", elapsed_ms=1
        )

    return fetch, seen


def gathered(followed: paginate.Follow) -> list[dict[str, int]]:
    merged = paginate.merge(followed.pages, None, paginate.dig)
    if isinstance(merged, dict):
        return cast(list[dict[str, int]], merged["data"])
    return cast(list[dict[str, int]], merged)


# -- each strategy reaches the end -------------------------------------------------


@pytest.mark.parametrize(
    ("shape", "spec"),
    [
        ("cursor", Pagination(strategy="cursor", cursor_path="next_cursor", param="cursor")),
        ("token", Pagination(strategy="token", cursor_path="meta.next", param="X-Next-Token")),
        ("page", Pagination(strategy="page", param="page", size=SIZE)),
        ("offset", Pagination(strategy="offset", param="offset", size=SIZE)),
        ("link", Pagination(strategy="link_header")),
    ],
)
async def test_a_strategy_follows_a_source_to_its_end(shape: str, spec: Pagination) -> None:
    fetch, _ = fetcher(shape)
    followed = await paginate.follow(spec, fetch, max_pages=40)
    assert len(gathered(followed)) == TOTAL
    assert not followed.truncated


async def test_the_token_strategy_sends_a_header_not_a_parameter() -> None:
    fetch, seen = fetcher("token")
    spec = Pagination(strategy="token", cursor_path="meta.next", param="X-Next-Token")
    await paginate.follow(spec, fetch, max_pages=40)
    assert seen[1]["headers"] == {"X-Next-Token": "10"}
    assert seen[1]["query"] == {}


async def test_the_link_strategy_follows_the_url_it_was_given() -> None:
    fetch, seen = fetcher("link")
    await paginate.follow(Pagination(strategy="link_header"), fetch, max_pages=40)
    assert seen[1]["url"] == "https://x/?p=2"


# -- stopping ----------------------------------------------------------------------


async def test_max_pages_truncates_and_says_so() -> None:
    fetch, _ = fetcher("cursor")
    spec = Pagination(strategy="cursor", cursor_path="next_cursor", param="cursor", max_pages=3)
    followed = await paginate.follow(spec, fetch)
    assert followed.count == 3
    assert followed.truncated
    assert "max_pages" in followed.reason


async def test_the_callers_ceiling_wins_when_it_is_lower() -> None:
    """A mode that says one page must mean it, even if the workflow says forty."""
    fetch, _ = fetcher("cursor")
    spec = Pagination(strategy="cursor", cursor_path="next_cursor", param="cursor", max_pages=40)
    followed = await paginate.follow(spec, fetch, max_pages=1)
    assert followed.count == 1


async def test_a_repeated_request_ends_paging() -> None:
    """An API that claims more and hands back the same page is a bug report, not a loop."""
    fetch, _ = fetcher("stuck")
    spec = Pagination(strategy="cursor", cursor_path="next_cursor", param="cursor", max_pages=40)
    followed = await paginate.follow(spec, fetch)
    assert followed.count == 2
    assert followed.reason == "repeated page"
    assert not followed.truncated


async def test_stop_when_ends_paging() -> None:
    fetch, _ = fetcher("cursor")
    spec = Pagination(strategy="cursor", cursor_path="next_cursor", param="cursor", max_pages=40)

    async def stop(page: paginate.Page) -> bool:
        return len(page.body["data"]) > 0 and page.body["data"][0]["id"] >= 20

    followed = await paginate.follow(spec, fetch, stop_when=stop)
    assert followed.count == 3
    assert followed.reason == "stop_when"


async def test_progress_is_reported_per_page() -> None:
    fetch, _ = fetcher("cursor")
    spec = Pagination(strategy="cursor", cursor_path="next_cursor", param="cursor", max_pages=40)
    numbers: list[int] = []
    await paginate.follow(spec, fetch, on_page=lambda n, _page: numbers.append(n))
    assert numbers == list(range(1, 11))


# -- merging -----------------------------------------------------------------------


def page_of(body: Any) -> paginate.Page:
    return paginate.Page(body=body, status=200, headers={}, url="https://x/", elapsed_ms=1)


def test_pages_keep_the_shape_one_page_had() -> None:
    """`@fetch.body.data` must mean on page 40 what it meant on page 1."""
    pages = [page_of({"data": [1, 2], "total": 4}), page_of({"data": [3, 4], "total": 4})]
    merged = paginate.merge(pages, None, paginate.dig)
    assert merged == {"data": [1, 2, 3, 4], "total": 4}


def test_bare_lists_concatenate() -> None:
    merged = paginate.merge([page_of([1, 2]), page_of([3])], None, paginate.dig)
    assert merged == [1, 2, 3]


def test_into_names_where_the_items_are() -> None:
    pages = [page_of({"result": {"rows": [1]}}), page_of({"result": {"rows": [2]}})]
    assert paginate.merge(pages, "result.rows", paginate.dig) == [1, 2]


def test_a_shape_we_do_not_recognise_becomes_the_list_of_bodies() -> None:
    """Inventing a merge would be guessing with someone's data."""
    pages = [page_of({"a": 1}), page_of({"b": 2})]
    assert paginate.merge(pages, None, paginate.dig) == [{"a": 1}, {"b": 2}]


def test_one_page_is_returned_as_itself() -> None:
    assert paginate.merge([page_of({"a": 1})], None, paginate.dig) == {"a": 1}


def test_two_envelope_keys_are_ambiguous_and_left_alone() -> None:
    pages = [page_of({"data": [1], "rows": [2]}), page_of({"data": [3], "rows": [4]})]
    merged = paginate.merge(pages, None, paginate.dig)
    assert isinstance(merged, list)


# -- concurrency, and what can be checked early ------------------------------------


@pytest.mark.parametrize("strategy", ["cursor", "token", "link_header"])
def test_concurrency_on_a_sequential_strategy_is_reported_not_dropped(strategy: str) -> None:
    """A `concurrent=8` that quietly does nothing is a lie paid for in wall-clock time."""
    spec = Pagination(strategy=strategy, cursor_path="x", concurrent=8)  # type: ignore[arg-type]
    message = paginate.unsupported_concurrency(spec)
    assert message is not None
    assert "sequential" in message


@pytest.mark.parametrize("strategy", ["page", "offset"])
def test_concurrency_is_possible_where_the_urls_are_computable(strategy: str) -> None:
    spec = Pagination(strategy=strategy, size=10, concurrent=8)  # type: ignore[arg-type]
    assert paginate.unsupported_concurrency(spec) is None


def test_offset_without_a_size_cannot_advance_and_says_so() -> None:
    with pytest.raises(ValidationError) as caught:
        paginate.check(Pagination(strategy="offset", param="offset"))
    assert "size=" in str(caught.value)


def test_a_cursor_without_a_path_cannot_find_its_token() -> None:
    with pytest.raises(ValidationError) as caught:
        paginate.check(Pagination(strategy="cursor", param="cursor"))
    assert "cursor_path" in str(caught.value)
    assert "link_header" in str(caught.value)


def test_a_complete_spec_passes() -> None:
    paginate.check(Pagination(strategy="cursor", cursor_path="next", param="cursor"))
    paginate.check(Pagination(strategy="page", param="page"))


# -- the path helper ---------------------------------------------------------------


def test_dig_follows_a_dotted_path() -> None:
    assert paginate.dig({"meta": {"next": "abc"}}, "meta.next") == "abc"


def test_dig_returns_none_for_a_missing_branch() -> None:
    """A cursor that is not there is how paging ends, not an error."""
    assert paginate.dig({"meta": {}}, "meta.next") is None
    assert paginate.dig({}, "a.b.c") is None
    assert paginate.dig(None, "a") is None
