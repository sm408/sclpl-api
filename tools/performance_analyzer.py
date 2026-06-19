"""
Performance Analyzer for SCLPLAPI

Analyzes execution stats from output/execution_stats.json:
- Identifies bottlenecks (slowest steps)
- Suggests parallelization opportunities
- Reports total vs sequential time

Usage:
    python tools/performance_analyzer.py [execution_stats.json]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def load_stats(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_dependency_graph(steps: list[dict]) -> tuple[dict[str, list[str]], dict[str, int]]:
    graph: dict[str, list[str]] = defaultdict(list)
    durations: dict[str, int] = {}

    for step in steps:
        sid = step.get("id", step.get("step_id", ""))
        durations[sid] = step.get("duration_ms", 0)
        for dep in step.get("depends_on", []):
            graph[dep].append(sid)

    return graph, durations


def compute_critical_path(steps: list[dict]) -> tuple[list[str], int]:
    graph, durations = build_dependency_graph(steps)
    step_ids = {s.get("id", s.get("step_id", "")) for s in steps}

    dist: dict[str, int] = {sid: 0 for sid in step_ids}
    pred: dict[str, str | None] = {sid: None for sid in step_ids}

    in_degree: dict[str, int] = defaultdict(int)
    for step in steps:
        sid = step.get("id", step.get("step_id", ""))
        for dep in step.get("depends_on", []):
            if dep in step_ids:
                in_degree[sid] += 1

    from collections import deque

    queue = deque(sid for sid in step_ids if in_degree[sid] == 0)
    topo_order: list[str] = []

    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for neighbor in graph[node]:
            new_dist = dist[node] + durations.get(node, 0)
            if new_dist > dist[neighbor]:
                dist[neighbor] = new_dist
                pred[neighbor] = node
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if not topo_order:
        return [], 0

    end_node = max(topo_order, key=lambda n: dist[n] + durations.get(n, 0))
    critical_path: list[str] = []
    current: str | None = end_node
    while current is not None:
        critical_path.append(current)
        current = pred[current]
    critical_path.reverse()

    total = dist[end_node] + durations.get(end_node, 0)
    return critical_path, total


def find_parallelization_opportunities(steps: list[dict]) -> list[dict]:
    graph, durations = build_dependency_graph(steps)
    step_ids = {s.get("id", s.get("step_id", "")) for s in steps}
    step_map = {s.get("id", s.get("step_id", "")): s for s in steps}

    in_degree: dict[str, int] = defaultdict(int)
    for step in steps:
        sid = step.get("id", step.get("step_id", ""))
        for dep in step.get("depends_on", []):
            if dep in step_ids:
                in_degree[sid] += 1

    levels: dict[str, int] = {}
    from collections import deque

    queue = deque(sid for sid in step_ids if in_degree[sid] == 0)
    temp_in = dict(in_degree)

    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            levels[neighbor] = max(levels.get(neighbor, 0), levels.get(node, 0) + 1)
            temp_in[neighbor] -= 1
            if temp_in[neighbor] == 0:
                queue.append(neighbor)

    for sid in step_ids:
        if sid not in levels:
            levels[sid] = 0

    level_groups: dict[int, list[str]] = defaultdict(list)
    for sid, level in levels.items():
        level_groups[level].append(sid)

    opportunities: list[dict] = []
    for level, sids in sorted(level_groups.items()):
        if len(sids) > 1:
            total_time = sum(durations.get(s, 0) for s in sids)
            max_time = max(durations.get(s, 0) for s in sids)
            savings = total_time - max_time
            opportunities.append({
                "level": level,
                "steps": sids,
                "total_sequential_ms": total_time,
                "parallel_ms": max_time,
                "savings_ms": savings,
            })

    return opportunities


def find_bottlenecks(steps: list[dict], top_n: int = 5) -> list[dict]:
    sorted_steps = sorted(
        steps,
        key=lambda s: s.get("duration_ms", 0),
        reverse=True,
    )
    return [
        {
            "id": s.get("id", s.get("step_id", "")),
            "name": s.get("name", s.get("step_name", "")),
            "duration_ms": s.get("duration_ms", 0),
            "type": s.get("type", s.get("step_type", "")),
        }
        for s in sorted_steps[:top_n]
    ]


def analyze_stats(data: dict) -> str:
    lines: list[str] = []

    steps = data.get("steps", data.get("step_results", []))
    if not steps:
        return "No step data found in stats file."

    total_duration = sum(s.get("duration_ms", 0) for s in steps)
    critical_path, critical_ms = compute_critical_path(steps)
    parallel_opportunities = find_parallelization_opportunities(steps)
    bottlenecks = find_bottlenecks(steps)

    lines.append("=" * 60)
    lines.append("  SCLPLAPI Performance Analysis")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Total steps:        {len(steps)}")
    lines.append(f"  Total duration:     {total_duration}ms (sum of all steps)")
    lines.append(f"  Critical path:      {critical_ms}ms")
    lines.append(f"  Parallelism gain:   {total_duration - critical_ms}ms saved")
    lines.append("")

    lines.append("-" * 60)
    lines.append("  BOTTLENECKS (slowest steps)")
    lines.append("-" * 60)
    for i, b in enumerate(bottlenecks, 1):
        pct = (b["duration_ms"] / total_duration * 100) if total_duration else 0
        lines.append(f"  {i}. {b['id']:30s}  {b['duration_ms']:>8}ms  ({pct:.1f}%)")
    lines.append("")

    if parallel_opportunities:
        lines.append("-" * 60)
        lines.append("  PARALLELIZATION OPPORTUNITIES")
        lines.append("-" * 60)
        for opp in parallel_opportunities:
            lines.append(f"  Level {opp['level']}: {', '.join(opp['steps'])}")
            lines.append(
                f"    Sequential: {opp['total_sequential_ms']}ms -> "
                f"Parallel: {opp['parallel_ms']}ms "
                f"(save {opp['savings_ms']}ms)"
            )
        lines.append("")

    if critical_path:
        lines.append("-" * 60)
        lines.append("  CRITICAL PATH")
        lines.append("-" * 60)
        for i, sid in enumerate(critical_path):
            duration = next(
                (s.get("duration_ms", 0) for s in steps
                 if s.get("id", s.get("step_id", "")) == sid),
                0,
            )
            prefix = "  " if i == 0 else "  -> "
            lines.append(f"  {prefix}{sid} ({duration}ms)")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> None:
    default_path = Path("output/execution_stats.json")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    if not path.exists():
        print(f"ERROR: Stats file not found: {path}", file=sys.stderr)
        print(f"  Expected location: {default_path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = load_stats(path)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    report = analyze_stats(data)
    print(report)


if __name__ == "__main__":
    main()
