"""The ordinary-script bridge, exercised through the registered function path."""

from __future__ import annotations

from pathlib import Path

import pytest

from sclpl import bootstrap
from sclpl.errors import StepFailed
from sclpl.functions.python_fns import run_path

bootstrap.load(plugins=False)


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def test_python_function_passes_json_input_args_and_reads_json_output(tmp_path: Path) -> None:
    script = _write(
        tmp_path / "transform.py",
        "import json, sys\nrows = json.load(sys.stdin)\n"
        "json.dump([row['n'] * int(sys.argv[2]) for row in rows], sys.stdout)\n",
    )
    result = run_path(str(script), args=["--factor", "3"], input=[{"n": 2}])
    assert result == [6]


def test_python_function_keeps_non_json_stdout_as_text(tmp_path: Path) -> None:
    script = _write(tmp_path / "hello.py", "print('hello')\n")
    assert run_path(str(script)) == "hello"


def test_python_function_reports_the_script_failure(tmp_path: Path) -> None:
    script = _write(
        tmp_path / "broken.py",
        "import sys\nprint('details', file=sys.stderr)\nsys.exit(9)\n",
    )
    with pytest.raises(StepFailed, match="status 9: details"):
        run_path(str(script))
