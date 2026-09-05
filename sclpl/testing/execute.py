"""Offline, isolated execution of validated project test manifests."""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sclpl.catalog import resolve as catalog
from sclpl.errors import AssertionFailed
from sclpl.project.context import ProjectContext
from sclpl.render.plain import QuietSink
from sclpl.render.reporter import Reporter
from sclpl.run.runner import Options, Result, run_workflow
from sclpl.testing.manifest import Manifest


@dataclass(frozen=True, slots=True)
class Outcome:
    """The isolated directory and result of one declared test."""

    manifest: Manifest
    result: Result
    state_dir: Path


def run(manifest: Manifest, project: ProjectContext) -> Outcome:
    """Run one manifest without history, live HTTP, cache, or shared scratch data."""
    located = catalog.resolve(manifest.workflow, extra_dirs=project.workflow_dirs)
    state_root = project.root / ".sclpl" / "tests"
    state_root.mkdir(parents=True, exist_ok=True)
    state_dir = Path(tempfile.mkdtemp(prefix=f"{manifest.path.stem}-", dir=state_root))
    options = Options(
        overrides=manifest.inputs,
        env=manifest.environment or project.environment,
        fixture_root=manifest.fixture,
        record=False,
        no_cache=True,
        offline=True,
        scratch_dir=state_dir,
    )

    async def execute() -> Result:
        async with Reporter([QuietSink(silent=True)]) as reporter:
            return await run_workflow(located.doc, options, reporter)

    result = asyncio.run(execute())
    if result.exit_code != manifest.expected_exit:
        raise AssertionFailed(
            f"{manifest.path}: expected exit {manifest.expected_exit}, got {result.exit_code}"
        )
    return Outcome(manifest, result, state_dir)
