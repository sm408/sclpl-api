"""
E2E tests for SCLPLAPI example workflows.

Tests that all 4 examples can be validated, compiled, and their
workflow.json files are structurally correct.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EXAMPLES = [
    "weather_pipeline",
    "financial_pipeline",
    "job_tracker_pipeline",
    "multi_provider_aggregator",
    "advanced_logic",
]


def _find_sclpll(examples_dir: Path, example: str) -> Path:
    """Find the first .sclpll file in an example directory."""
    matches = sorted((examples_dir / example).glob("*.sclpll"))
    assert matches, f"No .sclpll file found in {example}"
    return matches[0]


class TestExampleWorkflows:
    """Test all example workflow.json files are valid."""

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_workflow_json_exists(self, examples_dir: Path, example: str) -> None:
        workflow_path = examples_dir / example / "workflow.json"
        assert workflow_path.exists(), f"Missing workflow.json in {example}"

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_workflow_json_parseable(self, examples_dir: Path, example: str) -> None:
        workflow_path = examples_dir / example / "workflow.json"
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        assert "id" in data
        assert "name" in data
        assert "steps" in data
        assert len(data["steps"]) > 0

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_workflow_steps_have_ids(self, examples_dir: Path, example: str) -> None:
        workflow_path = examples_dir / example / "workflow.json"
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            assert "id" in step, f"Step missing 'id' in {example}"
            assert "type" in step, f"Step missing 'type' in {example}"

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_workflow_no_duplicate_ids(self, examples_dir: Path, example: str) -> None:
        workflow_path = examples_dir / example / "workflow.json"
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        ids = [s["id"] for s in data["steps"]]
        assert len(ids) == len(set(ids)), f"Duplicate step IDs in {example}"

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_workflow_deps_reference_valid_steps(self, examples_dir: Path, example: str) -> None:
        workflow_path = examples_dir / example / "workflow.json"
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        step_ids = {s["id"] for s in data["steps"]}
        for step in data["steps"]:
            for dep in step.get("depends_on", []):
                assert dep in step_ids, f"Step '{step['id']}' in {example} depends on unknown step '{dep}'"

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_workflow_no_cycles(self, examples_dir: Path, example: str) -> None:
        workflow_path = examples_dir / example / "workflow.json"
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        steps = data["steps"]
        step_ids = {s["id"] for s in steps}
        in_degree = {sid: 0 for sid in step_ids}
        dependents: dict[str, list[str]] = {}

        for step in steps:
            for dep in step.get("depends_on", []):
                if dep in step_ids:
                    in_degree[step["id"]] += 1
            dependents[step["id"]] = []

        for step in steps:
            for dep in step.get("depends_on", []):
                if dep in step_ids:
                    dependents[dep].append(step["id"])

        from collections import deque

        queue = deque(sid for sid, deg in in_degree.items() if deg == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in dependents[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        assert visited == len(step_ids), f"Circular dependency detected in {example}"


class TestExampleSCLPLL:
    """Test all example .sclpll files can be validated."""

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_sclpll_exists(self, examples_dir: Path, example: str) -> None:
        sclpll_path = _find_sclpll(examples_dir, example)
        assert sclpll_path.exists(), f"Missing .sclpll file in {example}"

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_sclpll_compiles(self, run_sclpll_cli, examples_dir: Path, example: str, tmp_path: Path) -> None:
        sclpll_path = _find_sclpll(examples_dir, example)
        result = run_sclpll_cli(["validate", str(sclpll_path)])
        assert result.returncode == 0, f"SCLPLL validation failed for {example}: {result.stderr}"

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_sclpll_compile_to_json(self, run_sclpll_cli, examples_dir: Path, example: str, tmp_path: Path) -> None:
        sclpll_path = _find_sclpll(examples_dir, example)
        result = run_sclpll_cli(["compile", str(sclpll_path), "--output-dir", str(tmp_path / example)])
        assert result.returncode == 0, f"SCLPLL compile failed for {example}: {result.stderr}"
        assert (tmp_path / example / "workflow.json").exists()


class TestExampleFunctions:
    """Test that functions referenced by examples exist."""

    @pytest.mark.parametrize("example", EXAMPLES)
    def test_referenced_functions_exist(self, examples_dir: Path, functions_dir: Path, example: str) -> None:
        workflow_path = examples_dir / example / "workflow.json"
        data = json.loads(workflow_path.read_text(encoding="utf-8"))

        from app.core.engine.function_runner import FilesystemFunctionRunner

        runner = FilesystemFunctionRunner(str(functions_dir))
        discovered = runner.discover()
        known_names = {f.get("name") for f in discovered if f.get("name")}

        for step in data["steps"]:
            if step.get("type") == "function":
                fname = step.get("config", {}).get("function_name", "")
                if fname:
                    assert fname in known_names, (
                        f"Function '{fname}' referenced in {example} not found in functions/"
                    )


class TestExampleOutputDirectories:
    """Test that examples with output directories have expected structure."""

    @pytest.mark.parametrize("example", ["weather_pipeline", "job_tracker_pipeline"])
    def test_output_dir_exists(self, examples_dir: Path, example: str) -> None:
        output_dir = examples_dir / example / "output"
        assert output_dir.exists(), f"Missing output/ in {example}"


class TestToolsValidation:
    """Test that the tools can validate all example workflows."""

    def test_validate_all_examples(self, run_tool, examples_dir: Path) -> None:
        for example in EXAMPLES:
            workflow_path = examples_dir / example / "workflow.json"
            result = run_tool("workflow_validator.py", [str(workflow_path)])
            assert result.returncode == 0, f"Validation failed for {example}: {result.stdout}"

    def test_lint_all_functions(self, run_tool, functions_dir: Path) -> None:
        result = run_tool("function_linter.py", [str(functions_dir)])
        assert result.returncode == 0, f"Linting failed: {result.stdout}"

    def test_formatter_produces_output(self, run_tool, examples_dir: Path) -> None:
        for example in EXAMPLES:
            sclpll_path = _find_sclpll(examples_dir, example)
            result = run_tool("sclpll_formatter.py", [str(sclpll_path)])
            assert result.returncode == 0, f"Formatter crashed on {example}: {result.stderr}"
            assert "@workflow" in result.stdout, f"Formatter output missing @workflow for {example}"
            assert "@step" in result.stdout, f"Formatter output missing @step for {example}"
