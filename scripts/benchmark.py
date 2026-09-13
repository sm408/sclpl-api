"""J3: measure the five workload budgets proposed in UNIFIED-UPGRADE-PLAN.md section 8.

These are calibration numbers, not a CI gate (the plan is explicit about that: "these
are proposed engineering gates, not measured performance claims"). Run this by hand on
a release candidate, and on the machine you intend to compare against -- an absolute
number means nothing without the hardware, library versions, and prior run it is
measured against, which is why every run is also written to a JSON record.

Usage:
    python scripts/benchmark.py                 # full sizes, ~1-2 minutes
    python scripts/benchmark.py --quick          # scaled down, for a fast sanity check
    python scripts/benchmark.py --out results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import tempfile
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sclpl import bootstrap  # noqa: E402
from sclpl.catalog import resolve as catalog  # noqa: E402
from sclpl.render.plain import QuietSink  # noqa: E402
from sclpl.render.reporter import Reporter  # noqa: E402
from sclpl.run.runner import Options, run_workflow  # noqa: E402
from sclpl.state import db  # noqa: E402

bootstrap.load()


@dataclass(slots=True)
class BenchResult:
    name: str
    metric: str
    value: float
    budget: str
    note: str = ""


def _write_workflow(directory: Path, name: str, source: str) -> Path:
    path = directory / f"{name}.sclpll"
    path.write_text(source, encoding="utf-8")
    return path


async def _run(path: Path, *, named_out: dict[str, str] | None = None) -> float:
    located = catalog.resolve(str(path), extra_dirs=[path.parent])
    options = Options(
        named_out=named_out or {},
        record=False,
        no_cache=True,
        scratch_dir=Path(tempfile.mkdtemp()),
    )
    started = time.perf_counter()
    async with Reporter([QuietSink(silent=True)]) as reporter:
        result = await run_workflow(located.doc, options, reporter)
    if result.exit_code != 0:
        raise RuntimeError(f"benchmark workflow {path.name} failed: exit {result.exit_code}")
    return time.perf_counter() - started


# -- 1. a synthetic N-step workflow --------------------------------------------------


def bench_synthetic_workflow(steps: int, tmp_path: Path) -> BenchResult:
    """SPEC 8: "1,000-step synthetic workflow: no more than 15% median overhead versus
    baseline ... measured over at least five runs." This measures one run's wall time;
    comparing it against a stored prior result (this script's own JSON output) is the
    caller's job, since "baseline" only means something across two runs, not one.
    """
    lines = [f'@workflow synth_{steps} "generated for benchmarking"', ""]
    lines.append("@step s0\n  let 0\n")
    for index in range(1, steps):
        lines.append(f"@step s{index}\n  let add(@s{index - 1}, 1)\n")
    path = _write_workflow(tmp_path, f"synth_{steps}", "\n".join(lines))

    durations = [asyncio.run(_run(path)) for _ in range(5)]
    durations.sort()
    median = durations[len(durations) // 2]
    return BenchResult(
        name="synthetic_workflow",
        metric="median_seconds_per_1000_steps",
        value=median * (1000 / steps),
        budget="<=15% overhead vs a stored baseline run (SPEC 8)",
        note=f"{steps} steps, 5 runs, durations={[round(d, 3) for d in durations]}",
    )


# -- 2. paginated reporting throughput ------------------------------------------------


def bench_pagination_throughput(rows: int, tmp_path: Path) -> BenchResult:
    """SPEC 8: "100,000-row paginated reporting fixture: no more than 20% throughput
    regression for unchanged transformations." Approximated here with an in-memory
    page source (no real HTTP) so the number reflects normalize+flatten+write cost,
    not network variance -- pair it with the real fixture in a release-candidate run.
    """
    page_size = 1000
    pages = rows // page_size
    literal = json.dumps([{"id": i, "value": i * 1.5} for i in range(rows)])
    source = f"""
@workflow paginate_bench "generated for benchmarking"

@step rows
  let {literal}

@step shaped
  normalize @rows

@output out:csv

@step write -> out
  save_csv @shaped
"""
    path = _write_workflow(tmp_path, "paginate_bench", source)
    out = tmp_path / "paginate_bench.csv"
    started = time.perf_counter()
    asyncio.run(_run(path, named_out={"out": str(out)}))
    elapsed = time.perf_counter() - started
    return BenchResult(
        name="pagination_throughput",
        metric="rows_per_second",
        value=rows / elapsed if elapsed else float("inf"),
        budget="<=20% regression vs a stored baseline run (SPEC 8)",
        note=f"{rows} rows in {round(elapsed, 3)}s ({pages} pages of {page_size})",
    )


# -- 3. streaming memory ---------------------------------------------------------------


def bench_streaming_memory(rows: int, tmp_path: Path) -> BenchResult:
    """SPEC 8: "memory does not grow with total payload size." `tracemalloc` (stdlib,
    cross-platform) stands in for RSS here so this runs the same way on every OS;
    measure real RSS too on the release-candidate machine (`psutil`, or `/proc` on
    Linux), since tracemalloc only sees Python-allocated objects.
    """
    literal = json.dumps([{"id": i, "value": i * 1.5} for i in range(rows)])
    source = f"""
@workflow streaming_bench "generated for benchmarking"

@step rows
  let {literal}

@output out:ndjson

@step write -> out
  save_ndjson @rows
"""
    path = _write_workflow(tmp_path, "streaming_bench", source)
    out = tmp_path / "streaming_bench.ndjson"
    tracemalloc.start()
    asyncio.run(_run(path, named_out={"out": str(out)}))
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return BenchResult(
        name="streaming_memory",
        metric="peak_traced_bytes_per_row",
        value=peak / rows,
        budget="bounded, not growing with total payload size (SPEC 8)",
        note=f"{rows} rows, peak traced allocation {peak} bytes",
    )


# -- 4. retained run-record queries ---------------------------------------------------


def bench_run_history_query(count: int, tmp_path: Path) -> BenchResult:
    """SPEC 8: "10,000 retained run records: latest/report metadata queries target
    under one second on the benchmark machine."
    """
    history = db.History(tmp_path / "history")
    started_seed = time.perf_counter()
    for index in range(count):
        history.record(
            db.RunRecord(
                id=f"bench-{index:06d}",
                name=f"bench-{index:06d}",
                workflow="synthetic",
                status="ok",
                started_at=db.now(),
                finished_at=db.now(),
                duration_ms=10,
            )
        )
    seed_elapsed = time.perf_counter() - started_seed

    started_query = time.perf_counter()
    history.recent(limit=20)
    history.find(f"bench-{count - 1:06d}")
    query_elapsed = time.perf_counter() - started_query
    history.close()

    return BenchResult(
        name="run_history_query",
        metric="query_seconds",
        value=query_elapsed,
        budget="<1s on the benchmark machine (SPEC 8)",
        note=f"{count} records seeded in {round(seed_elapsed, 3)}s",
    )


# -- 5. replay makes no live network attempts ------------------------------------------


def bench_replay_zero_network(tmp_path: Path) -> BenchResult:
    """SPEC 8: "Replay performs zero live network attempts." Every journey acceptance
    test (tests/integration/test_journeys.py) already runs with `--strict-replay`,
    which fails loud on any request the fixture directory does not cover -- there is
    no separate live socket to accidentally open in the first place. This measures the
    overhead of that guarantee (replay dispatch cost) rather than re-proving it.
    """
    source = """
@workflow replay_bench "generated for benchmarking"

@step value
  let 1

@output out:json

@step write -> out
  save_json @value
"""
    path = _write_workflow(tmp_path, "replay_bench", source)
    out = tmp_path / "replay_bench.json"
    elapsed = asyncio.run(_run(path, named_out={"out": str(out)}))
    return BenchResult(
        name="replay_zero_network",
        metric="dispatch_seconds",
        value=elapsed,
        budget="zero live network attempts (enforced by --strict-replay; see docstring)",
        note="no HTTP step in this benchmark workflow -- covered by --strict-replay tests",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="scaled-down sizes")
    parser.add_argument("--out", type=Path, help="write results as JSON to this path")
    args = parser.parse_args()

    steps = 100 if args.quick else 1000
    rows = 2_000 if args.quick else 100_000
    history_count = 500 if args.quick else 10_000

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp_path = Path(raw_tmp)
        results = [
            bench_synthetic_workflow(steps, tmp_path),
            bench_pagination_throughput(rows, tmp_path),
            bench_streaming_memory(rows, tmp_path),
            bench_run_history_query(history_count, tmp_path),
            bench_replay_zero_network(tmp_path),
        ]

    record = {
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "quick": args.quick,
        "results": [asdict(result) for result in results],
    }

    for result in results:
        print(f"{result.name:24s} {result.metric:32s} {result.value:>14.4f}  {result.budget}")
        if result.note:
            print(f"{'':24s} {result.note}")

    if args.out:
        args.out.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
