"""Offline, isolated execution of validated project test manifests."""

from __future__ import annotations

import asyncio
import json
import os
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
    #: Expected-output files rewritten by `--update-snapshots`, if any.
    updated: tuple[Path, ...] = ()


def run(manifest: Manifest, project: ProjectContext, *, update_snapshots: bool = False) -> Outcome:
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
    updated: tuple[Path, ...] = ()
    if result.exit_code == 0:
        updated = _assert(manifest, result, update_snapshots=update_snapshots)
    return Outcome(manifest, result, state_dir, updated)


def _assert(manifest: Manifest, result: Result, *, update_snapshots: bool) -> tuple[Path, ...]:
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

    updated: list[Path] = []
    for step, expected_path in manifest.expected_outputs.items():
        try:
            actual = result.store.get(step)
        except KeyError as error:
            raise AssertionFailed(
                f"{manifest.path}: assertion step {step!r} was not produced"
            ) from error
        path = manifest.path.parent / expected_path
        if update_snapshots:
            if _write_snapshot(path, actual):
                updated.append(path)
            continue
        try:
            expected = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AssertionFailed(
                f"{manifest.path}: invalid expected output for {step!r}"
            ) from error
        if actual != expected:
            raise AssertionFailed(
                f"${step}: expected output differs from {expected_path}",
                remedies=["rerun with --update-snapshots if the new value is correct"],
            )
    return tuple(updated)


def _write_snapshot(path: Path, value: object) -> bool:
    """Write ``value`` to ``path`` as JSON, atomically. False when it was unchanged.

    Compared as parsed values, not raw bytes: a snapshot written by hand, or by an
    older version of this formatting, still counts as "already correct" if it means
    the same thing, so a run does not touch a file nothing actually asked to change.

    Written beside the destination and renamed into place, so a crash mid-write can
    never leave a snapshot half-written where the next run would trust it as done.
    """
    try:
        if json.loads(path.read_text(encoding="utf-8")) == value:
            return False
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    scratch.write_text(payload, encoding="utf-8")
    os.replace(scratch, path)
    return True
