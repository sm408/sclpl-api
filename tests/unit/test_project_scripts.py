"""The manifest allowlist and integrity gate for executable Python scripts."""

from __future__ import annotations

import asyncio
import hashlib
import io
from collections.abc import Generator
from pathlib import Path
from typing import BinaryIO

import pytest

from sclpl import bootstrap
from sclpl.errors import ValidationError
from sclpl.ext.resources import (
    ResourceCapabilities,
    ResourceInfo,
    clear_resource_providers,
    register_resource_provider,
)
from sclpl.project import context, scripts
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.runner import Options, Result, run_workflow
from sclpl.run.sclpll import parse


class Memory:
    scheme = "memory"

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def capabilities(self) -> ResourceCapabilities:
        return ResourceCapabilities(read=True, revisions=True)

    def normalize(self, uri: str) -> str:
        return uri

    def resolve(self, base_uri: str, reference: str) -> str:
        return f"{base_uri.rstrip('/')}/{reference}"

    def stat(self, uri: str) -> ResourceInfo:
        return ResourceInfo(uri=uri, revision="1")

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def list(self, uri: str) -> list[ResourceInfo]:
        return []

    def download(self, uri: str, target: BinaryIO) -> ResourceInfo:
        target.write(self.objects[uri])
        return ResourceInfo(uri=uri, revision="1")

    def upload(self, source: BinaryIO, uri: str, **_: object) -> ResourceInfo:
        raise NotImplementedError

    def display_uri(self, uri: str) -> str:
        return uri


@pytest.fixture(autouse=True)
def providers() -> Generator[None, None, None]:
    clear_resource_providers()
    yield
    clear_resource_providers()


def _project(
    root: Path, script: str, digest: str, *, remote: bool = False
) -> context.ProjectContext:
    field = "uri" if remote else "path"
    (root / "sclpl.toml").write_text(
        "[project]\nname = 'scripts'\n[environments.default]\n\n"
        "[python.scripts.score]\n"
        f"{field} = '{script}'\nsha256 = '{digest}'\n",
        encoding="utf-8",
    )
    loaded = context.load(root)
    assert loaded is not None
    return loaded


def test_registered_local_script_is_root_safe_and_digest_pinned(tmp_path: Path) -> None:
    source = b"print('safe')\n"
    (tmp_path / "scripts").mkdir()
    path = tmp_path / "scripts" / "score.py"
    path.write_bytes(source)
    project = _project(tmp_path, "scripts/score.py", hashlib.sha256(source).hexdigest())
    assert scripts.materialize(project, "score") == path

    path.write_text("print('changed')\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="does not match"):
        scripts.materialize(project, "score")


def test_registered_remote_script_is_cached_and_digest_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = b"print('remote')\n"
    uri = "memory://scripts/score.py"
    register_resource_provider("memory", Memory({uri: source}))
    project = _project(tmp_path, uri, hashlib.sha256(source).hexdigest(), remote=True)
    monkeypatch.setenv("SCLPL_HOME", str(tmp_path / "state"))
    staged = scripts.materialize(project, "score")
    assert staged.read_bytes() == source

    wrong_digest = _project(tmp_path, uri, "0" * 64, remote=True)
    with pytest.raises(ValidationError, match="does not match"):
        scripts.materialize(wrong_digest, "score")


def test_workflow_executes_a_verified_remote_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the real scheduler path, not only remote-script materialization."""
    source = b"import json, sys\njson.dump(sum(json.load(sys.stdin)), sys.stdout)\n"
    uri = "memory://scripts/score.py"
    register_resource_provider("memory", Memory({uri: source}))
    _project(tmp_path, uri, hashlib.sha256(source).hexdigest(), remote=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCLPL_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("SCLPL_CACHE_DIR", str(tmp_path / "cache"))
    bootstrap.load(plugins=False)
    doc = parse('@workflow remote_script\n@step score\n  python "score" input=[2, 3]\n')

    async def run() -> Result:
        async with Reporter([PlainSink(io.StringIO(), verbosity=-2)]) as reporter:
            return await run_workflow(doc, Options(validate=False, record=False), reporter)

    result = asyncio.run(run())
    assert result.ok


def test_workflow_refuses_an_unregistered_or_dynamic_script_before_execution(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path, "scripts/score.py", "0" * 64)
    unknown = parse('@workflow t\n@step run\n  python "not-registered"\n')
    with pytest.raises(ValidationError, match="unregistered"):
        scripts.check_workflow(unknown, project)

    dynamic = parse("@workflow t\n@var name = 'score'\n@step run\n  python @name\n")
    with pytest.raises(ValidationError, match="must name a registered"):
        scripts.check_workflow(dynamic, project)


def test_remote_registration_requires_a_sha256(tmp_path: Path) -> None:
    (tmp_path / "sclpl.toml").write_text(
        "[project]\n[environments.default]\n[python.scripts.score]\n"
        "uri = 'memory://scripts/score.py'\n",
        encoding="utf-8",
    )
    loaded = context.load(tmp_path)
    assert loaded is not None
    with pytest.raises(ValidationError, match="sha256"):
        scripts.registrations(loaded)
