from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.core.engine.function_runner import FilesystemFunctionRunner
from app.core.models.context import ExecutionContext


@pytest.fixture
def functions_dir(tmp_path: Path) -> Path:
    """Create a temporary functions directory with test function files."""
    funcs = tmp_path / "functions"
    funcs.mkdir()

    # Sync function with metadata
    (funcs / "greet.py").write_text(textwrap.dedent('''\
        """\
        @name: greet
        @type: utility
        @description: Returns a greeting
        """

        def run(ctx):
            return "hello world"
    '''))

    # Async function
    (funcs / "async_fn.py").write_text(textwrap.dedent('''\
        """\
        @name: async_fn
        @type: utility
        @description: An async function
        """

        async def run(ctx):
            return "async result"
    '''))

    # Function that raises an error
    (funcs / "broken.py").write_text(textwrap.dedent('''\
        """\
        @name: broken
        @type: utility
        @description: Always fails
        """

        def run(ctx):
            raise ValueError("intentional error")
    '''))

    # Function without run() entrypoint
    (funcs / "no_run.py").write_text(textwrap.dedent('''\
        """\
        @name: no_run
        @type: utility
        @description: Missing run()
        """

        def helper():
            return 42
    '''))

    # File with underscore prefix (should be skipped by discover)
    (funcs / "_private.py").write_text(textwrap.dedent('''\
        """\
        @name: private
        @type: utility
        """

        def run(ctx):
            return "private"
    '''))

    # File without metadata docstring
    (funcs / "plain.py").write_text(textwrap.dedent('''\
        def run(ctx):
            return "plain"
    '''))

    # Subdirectory with a function
    sub = funcs / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text(textwrap.dedent('''\
        """\
        @name: deep
        @type: utility
        @description: In a subdirectory
        """

        def run(ctx):
            return "deep result"
    '''))

    return tmp_path


class TestFilesystemFunctionRunnerDiscover:
    """Tests for FilesystemFunctionRunner.discover()."""

    def test_discover_finds_functions_with_metadata(self, functions_dir: Path) -> None:
        """discover() returns functions that have @name in their docstring."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        discovered = runner.discover()
        names = [f["name"] for f in discovered]
        assert "greet" in names
        assert "async_fn" in names
        assert "broken" in names
        assert "no_run" in names

    def test_discover_skips_underscore_files(self, functions_dir: Path) -> None:
        """Files starting with _ are excluded from discover results."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        discovered = runner.discover()
        names = [f["name"] for f in discovered]
        assert "private" not in names

    def test_discover_skips_files_without_metadata(self, functions_dir: Path) -> None:
        """Files without a @name in the docstring are excluded."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        discovered = runner.discover()
        names = [f["name"] for f in discovered]
        assert "plain" not in names

    def test_discover_includes_subdirectory_functions(self, functions_dir: Path) -> None:
        """discover() uses rglob so it finds functions in subdirectories."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        discovered = runner.discover()
        names = [f["name"] for f in discovered]
        assert "deep" in names

    def test_discover_with_explicit_directory(self, functions_dir: Path) -> None:
        """Passing an explicit directory overrides the base_dir."""
        runner = FilesystemFunctionRunner(functions_dir / "functions" / "sub")
        discovered = runner.discover()
        names = [f["name"] for f in discovered]
        assert "deep" in names
        assert len(discovered) == 1

    def test_discover_nonexistent_directory(self, functions_dir: Path) -> None:
        """discover() returns empty list for non-existent directory."""
        runner = FilesystemFunctionRunner(functions_dir / "nonexistent")
        assert runner.discover() == []

    def test_discover_metadata_contains_path_and_type(self, functions_dir: Path) -> None:
        """Each discovered function dict includes path and type keys."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        discovered = runner.discover()
        greet = next(f for f in discovered if f["name"] == "greet")
        assert "path" in greet
        assert greet["type"] == "utility"
        assert greet["description"] == "Returns a greeting"


class TestFilesystemFunctionRunnerRun:
    """Tests for FilesystemFunctionRunner.run()."""

    async def test_run_sync_function(self, functions_dir: Path) -> None:
        """run() executes a synchronous function and returns the result."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        result = await runner.run("greet", ExecutionContext())
        assert result.success
        assert result.return_value == "hello world"
        assert result.duration_ms >= 0

    async def test_run_async_function(self, functions_dir: Path) -> None:
        """run() handles async run() functions via asyncio.iscoroutine."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        result = await runner.run("async_fn", ExecutionContext())
        assert result.success
        assert result.return_value == "async result"

    async def test_run_function_that_raises(self, functions_dir: Path) -> None:
        """run() catches exceptions and returns an error FunctionResult."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        result = await runner.run("broken", ExecutionContext())
        assert not result.success
        assert "intentional error" in (result.error or "")

    async def test_run_function_without_run_entrypoint(self, functions_dir: Path) -> None:
        """run() returns an error if the module has no run() function."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        result = await runner.run("no_run", ExecutionContext())
        assert not result.success
        assert "no run(ctx) entrypoint" in (result.error or "")

    async def test_run_nonexistent_function(self, functions_dir: Path) -> None:
        """run() returns an error for a function name that doesn't exist."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        result = await runner.run("does_not_exist", ExecutionContext())
        assert not result.success
        assert "not found" in (result.error or "")

    async def test_run_subdirectory_function(self, functions_dir: Path) -> None:
        """run() finds functions in subdirectories via rglob."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        result = await runner.run("deep", ExecutionContext())
        assert result.success
        assert result.return_value == "deep result"

    async def test_run_passes_context(self, functions_dir: Path) -> None:
        """run() passes the ExecutionContext to the function."""
        funcs = functions_dir / "functions"
        (funcs / "ctx_reader.py").write_text(textwrap.dedent('''\
            """\
            @name: ctx_reader
            @type: utility
            """

            def run(ctx):
                return ctx.workflow_variables.get("key", "missing")
        '''))
        runner = FilesystemFunctionRunner(funcs)
        ctx = ExecutionContext(workflow_variables={"key": "found"})
        result = await runner.run("ctx_reader", ctx)
        assert result.success
        assert result.return_value == "found"


class TestFilesystemFunctionRunnerParseMetadata:
    """Tests for _parse_metadata internal method."""

    def test_parse_metadata_returns_dict(self, functions_dir: Path) -> None:
        """_parse_metadata extracts @key: value pairs from the docstring."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        meta = runner._parse_metadata(functions_dir / "functions" / "greet.py")
        assert meta is not None
        assert meta["name"] == "greet"
        assert meta["type"] == "utility"
        assert meta["description"] == "Returns a greeting"

    def test_parse_metadata_returns_none_for_no_docstring(self, functions_dir: Path) -> None:
        """_parse_metadata returns None when there's no docstring."""
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        meta = runner._parse_metadata(functions_dir / "functions" / "plain.py")
        assert meta is None

    def test_parse_metadata_returns_none_for_no_name(self, functions_dir: Path) -> None:
        """_parse_metadata returns None when @name is not in the docstring."""
        no_name = functions_dir / "functions" / "no_name.py"
        no_name.write_text('"""\\n@type: utility\\n"""\\ndef run(ctx): pass\\n')
        runner = FilesystemFunctionRunner(functions_dir / "functions")
        meta = runner._parse_metadata(no_name)
        assert meta is None
