"""Offline, isolated execution of validated project test manifests."""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sclpl.catalog import resolve as catalog
from sclpl.contracts import check as check_contract
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
    if result.exit_code == 0:
        _assert(manifest, result)
    return Outcome(manifest, result, state_dir)


def _assert(manifest: Manifest, result: Result) -> None:
    if result.store is None:
        raise AssertionFailed(f"{manifest.path}: successful run produced no value store")
    for assertion in manifest.assertions:
        step = assertion["step"]
        try:
            value = result.store.get(step)
        except KeyError as error:
            raise AssertionFailed(
                f"{manifest.path}: assertion step {step!r} was not produced"
            ) from error
        contract_path = (manifest.path.parent / assertion["contract"]).resolve()
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AssertionFailed(
                f"{manifest.path}: invalid assertion contract {contract_path}"
            ) from error
        if not isinstance(contract, dict):
            raise AssertionFailed(f"{manifest.path}: assertion contract must be an object")
        check_contract(value, contract, path=f"${step}", source=contract_path)
    for step, expected_path in manifest.expected_outputs.items():
        try:
            actual = result.store.get(step)
            path = manifest.path.parent / expected_path
            expected = json.loads(path.read_text(encoding="utf-8"))
        except (KeyError, OSError, json.JSONDecodeError) as error:
            raise AssertionFailed(
                f"{manifest.path}: invalid expected output for {step!r}"
            ) from error
        if actual != expected:
            raise AssertionFailed(f"${step}: expected output differs from {expected_path}")
