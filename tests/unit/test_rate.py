"""Rate budgets (ADR 0017): parsing, the sliding window, Retry-After, and the transport."""

from __future__ import annotations

import asyncio
import io

import httpx
import pytest

from sclpl.errors import ValidationError
from sclpl.render.events import StepThrottled, as_dict, event_name, visible_at
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run import compile_json
from sclpl.run.rate import ACCEPTED, Budgets, parse_rate
from sclpl.run.retry import Clock, Retry
from sclpl.run.sclpll import emit, parse
from sclpl.run.transport import Pool, Profile

SOURCE = """\
@workflow limited

@limits concurrency=8 rate=api.example.com:3/s rate=api.example.com:120/m
@limits rate=tag:api:10/s

@step fetch
  get https://api.example.com/orders
  tag api
"""


class VirtualClock:
    """Time moves only when someone sleeps: a sleep jumps the shared timeline forward.

    Every sleeper therefore wakes at or after the deadline it asked for, which is all
    `asyncio.sleep` promises too, and a window check against it means what it would
    mean against real time.
    """

    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    async def sleep(self, delay: float) -> None:
        self.t += delay
        await asyncio.sleep(0)

    def clock(self) -> Clock:
        return Clock(now=self.now, sleep=self.sleep, jitter=lambda: 0.0)


def most_in_any_window(stamps: list[float], window: float) -> int:
    """The largest number of stamps inside any half-open interval [t, t + window)."""
    ordered = sorted(stamps)
    best = 0
    for index, start in enumerate(ordered):
        inside = [stamp for stamp in ordered[index:] if stamp < start + window]
        best = max(best, len(inside))
    return best


# -- the spec ----------------------------------------------------------------------


def test_a_host_and_a_tag_spec_parse() -> None:
    host = parse_rate("API.Example.com:3/s")
    assert (host.key, host.count, host.window) == ("api.example.com", 3, 1.0)
    tag = parse_rate("tag:Api:120/m")
    assert (tag.key, tag.count, tag.window) == ("tag:Api", 120, 60.0)
    assert parse_rate("h:5000/d").window == 86400.0
    assert parse_rate("h:1/h").window == 3600.0


@pytest.mark.parametrize(
    "bad",
    ["api.example.com", "api.example.com:3", "api.example.com:0/s", "api.example.com:3/w",
     ":3/s", "tag::3/s", "api.example.com:8443:3/s", "api.example.com:-1/s", "a b:3/s",
     "api.example.com:1.5/s"],
)  # fmt: skip
def test_a_malformed_spec_names_the_accepted_forms(bad: str) -> None:
    with pytest.raises(ValueError) as caught:
        parse_rate(bad)
    assert ACCEPTED in str(caught.value)


def test_sclpll_rejects_a_malformed_rate_with_the_accepted_forms() -> None:
    with pytest.raises(ValidationError) as caught:
        parse("@workflow w\n\n@limits rate=api.example.com:3/sec\n\n@step a\n  let 1\n")
    assert "HOST:N/UNIT or tag:NAME:N/UNIT" in str(caught.value)


def test_json_rejects_a_malformed_rate_with_the_accepted_forms() -> None:
    raw = '{"name": "w", "limits": {"rate": ["tag:api:ten/s"]}, "steps": []}'
    with pytest.raises(ValidationError) as caught:
        compile_json.loads(raw)
    assert "HOST:N/UNIT or tag:NAME:N/UNIT" in str(caught.value)


# -- the surfaces --------------------------------------------------------------------


def test_every_rate_is_kept_across_lines_in_order() -> None:
    doc = parse(SOURCE)
    assert doc.limits.rate == [
        "api.example.com:3/s",
        "api.example.com:120/m",
        "tag:api:10/s",
    ]
    assert doc.limits.concurrency == 8


def test_rates_round_trip_through_fmt_and_convert() -> None:
    doc = parse(SOURCE)
    once = emit(doc)
    assert "rate=api.example.com:3/s rate=api.example.com:120/m rate=tag:api:10/s" in once
    assert emit(parse(once)) == once
    as_json = compile_json.dumps(doc)
    assert compile_json.dumps(compile_json.loads(as_json)) == as_json
    assert emit(compile_json.loads(as_json)) == once


def test_a_workflow_without_rate_emits_as_before() -> None:
    doc = parse("@workflow w\n\n@limits concurrency=4\n\n@step a\n  let 1\n")
    assert "rate" not in emit(doc)
    assert "rate" not in compile_json.dumps(doc)


# -- the window ----------------------------------------------------------------------


async def test_no_window_ever_holds_more_than_its_count() -> None:
    virtual = VirtualClock()
    budgets = Budgets(["h:3/s"], clock=virtual.clock())
    stamps = []
    for _ in range(10):
        await budgets.take("h")
        stamps.append(virtual.now())
    assert most_in_any_window(stamps, 1.0) == 3
    # And it is not slower than it has to be: three a second, from the first.
    assert stamps == [0, 0, 0, 1, 1, 1, 2, 2, 2, 3]


async def test_every_applicable_window_must_have_room() -> None:
    virtual = VirtualClock()
    budgets = Budgets(["h:3/s", "h:5/m", "tag:api:2/s"], clock=virtual.clock())
    stamps = []
    for _ in range(6):
        await budgets.take("H", {"api"})
        stamps.append(virtual.now())
    assert stamps[:2] == [0, 0]  # the tag's 2/s binds first
    assert stamps[5] == 60.0  # then the host's 5/m
    # A request outside the tag is held only by the host's own windows.
    assert await budgets.take("other.test", {"unrelated"}) == (0.0, "")


async def test_retry_after_closes_the_host_until_then() -> None:
    virtual = VirtualClock()
    budgets = Budgets(["h:100/s"], clock=virtual.clock())
    budgets.close_until("h", 7.5)
    waited, reason = await budgets.take("h")
    assert (waited, reason) == (7.5, "h Retry-After")
    # A host with no budget of its own is untouched: rate is purely additive.
    budgets.close_until("elsewhere", 30)
    assert await budgets.take("elsewhere") == (0.0, "")


async def test_stats_show_what_is_left_and_what_was_waited() -> None:
    virtual = VirtualClock()
    budgets = Budgets(["h:2/s"], clock=virtual.clock())
    for _ in range(3):
        await budgets.take("h")
    stats = budgets.stats()["h:2/s"]
    assert stats == {"limit": 2, "window_s": 1.0, "remaining": 1, "waits": 1, "waited_s": 1.0}


# -- the transport, against a stub server that records when each request arrived ------


def stub_pool(virtual: VirtualClock, specs: list[str], handler: object) -> Pool:
    clock = virtual.clock()
    pool = Pool(rates=Budgets(specs, clock=clock), clock=clock, adaptive=False)
    stub = httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    pool._clients[Profile.of("https://api.example.com/")] = stub
    return pool


@pytest.mark.parametrize("concurrency", [1, 3, 10])
async def test_sixty_requests_at_three_a_second_never_exceed_three_in_any_second(
    concurrency: int,
) -> None:
    """Issue #8's acceptance: with and without concurrency above the rate."""
    virtual = VirtualClock()
    arrived: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        arrived.append(virtual.now())
        return httpx.Response(200, json={})

    gate = asyncio.Semaphore(concurrency)

    async def one(pool: Pool) -> None:
        async with gate:
            await pool.request("GET", "https://api.example.com/x")

    async with stub_pool(virtual, ["api.example.com:3/s"], handler) as pool:
        await asyncio.gather(*(one(pool) for _ in range(60)))
        assert len(arrived) == 60
        assert most_in_any_window(arrived, 1.0) <= 3
        assert max(arrived) <= 20.0
        assert pool.stats()["rates"]["api.example.com:3/s"]["limit"] == 3


async def test_a_429_with_retry_after_holds_every_request_to_that_host() -> None:
    virtual = VirtualClock()
    arrived: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        arrived.append(virtual.now())
        if len(arrived) == 1:
            return httpx.Response(429, headers={"Retry-After": "5"})
        return httpx.Response(200, json={})

    async with stub_pool(virtual, ["api.example.com:100/s"], handler) as pool:
        first = await pool.request("GET", "https://api.example.com/a", retry=Retry(max=0))
        assert first.response.status_code == 429
        await pool.request("GET", "https://api.example.com/b")
    assert arrived == [0.0, 5.0]


async def test_waiting_is_reported_as_an_event() -> None:
    virtual = VirtualClock()
    stream = io.StringIO()
    reporter = Reporter([PlainSink(stream, verbosity=3)])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with reporter, stub_pool(virtual, ["tag:api:1/m"], handler) as pool:
        for _ in range(2):
            await pool.request(
                "GET",
                "https://api.example.com/x",
                reporter=reporter,
                step="s",
                tags=frozenset({"api"}),
            )
        await reporter.drain()
    assert "wait s 60.0s for rate tag:api:1/m" in stream.getvalue()


def test_the_throttle_event_is_verbose_and_serialisable() -> None:
    event = StepThrottled(id="s", budget="h:3/s", delay_s=0.5)
    assert event_name(event) == "step_throttled"
    assert as_dict(event) == {"id": "s", "budget": "h:3/s", "delay_s": 0.5}
    assert not visible_at(event, 0)
    assert visible_at(event, 1)


async def test_a_pool_without_rates_never_waits() -> None:
    virtual = VirtualClock()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with stub_pool(virtual, [], handler) as pool:
        for _ in range(20):
            await pool.request("GET", "https://api.example.com/x")
        assert pool.stats()["rates"] == {}
    assert virtual.now() == 0.0
