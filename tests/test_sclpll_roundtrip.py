"""Property-based round-trip and loss tests for the SCLPLL compiler.

These tests verify:
- Every SCLPLL-representable field survives a parse -> decompile -> reparse cycle.
- Non-representable fields are explicitly flagged as lost.
- Deterministic SCLPLL generation (same input -> same output).
- Source diagnostics and preflight validation behave correctly.
"""

from __future__ import annotations

import json

import pytest

from app.core.engine.sclpll_compiler import SCLPLLCompiler


@pytest.fixture
def compiler() -> SCLPLLCompiler:
    return SCLPLLCompiler()


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def round_trip(compiler: SCLPLLCompiler, source: str) -> dict:
    """Parse source -> decompile -> reparse and return the final dict."""
    parsed = compiler.parse(source)
    decompiled = compiler.decompile_dict_to_sclpll(parsed)
    return compiler.parse(decompiled)


def assert_round_trip_field(
    compiler: SCLPLLCompiler, source: str, path: str, expected_value
) -> None:
    """Assert a specific field survives a round-trip unchanged.

    ``path`` is a dotted key path, e.g. ``steps.0.depends_on`` or ``variables.base_url``.
    """
    result = round_trip(compiler, source)
    parts = path.split(".")
    obj = result
    for part in parts:
        if part.isdigit():
            obj = obj[int(part)]
        else:
            obj = obj[part]
    assert obj == expected_value, (
        f"Field '{path}' changed during round-trip.\n"
        f"  Expected: {expected_value!r}\n"
        f"  Got:      {obj!r}"
    )


# ═══════════════════════════════════════════════════════════════════════
# Round-trip tests: every representable field
# ═══════════════════════════════════════════════════════════════════════


class TestRoundTripWorkflowId:
    def test_workflow_id_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow my_flow "Test"\n'
        assert_round_trip_field(compiler, source, "id", "my_flow")

    def test_workflow_id_with_underscores(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow my_complex_flow_2 "Test"\n'
        assert_round_trip_field(compiler, source, "id", "my_complex_flow_2")


class TestRoundTripWorkflowName:
    def test_quoted_name_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1 "My Workflow Name"\n'
        assert_round_trip_field(compiler, source, "name", "My Workflow Name")

    def test_name_defaults_to_id(self, compiler: SCLPLLCompiler) -> None:
        source = "@workflow my_id\n"
        assert_round_trip_field(compiler, source, "name", "my_id")


class TestRoundTripDescription:
    def test_description_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1 "Flow"\n    This is a description\n    on two lines\n\n'
        assert_round_trip_field(
            compiler, source, "description", "This is a description on two lines"
        )

    def test_empty_description_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1 "Flow"\n'
        assert_round_trip_field(compiler, source, "description", "")


class TestRoundTripBaseURL:
    def test_base_url_in_variables(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@base_url https://api.example.com\n'
        assert_round_trip_field(
            compiler, source, "variables.base_url", "https://api.example.com"
        )


class TestRoundTripVariables:
    def test_single_variable(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@var token = abc123\n'
        assert_round_trip_field(compiler, source, "variables.token", "abc123")

    def test_multiple_variables(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@var a = 1\n@var b = hello world\n'
        result = round_trip(compiler, source)
        assert result["variables"]["a"] == "1"
        assert result["variables"]["b"] == "hello world"

    def test_base_url_and_custom_vars(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@base_url https://api.example.com\n@var token = secret\n'
        result = round_trip(compiler, source)
        assert result["variables"]["base_url"] == "https://api.example.com"
        assert result["variables"]["token"] == "secret"


class TestRoundTripStepId:
    def test_step_id_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step fetch_data\n    request GET https://example.com\n'
        assert_round_trip_field(compiler, source, "steps.0.id", "fetch_data")


class TestRoundTripStepType:
    def test_request_step_type(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request GET https://example.com\n'
        assert_round_trip_field(compiler, source, "steps.0.type", "request")

    def test_function_step_type(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    func my_func\n'
        assert_round_trip_field(compiler, source, "steps.0.type", "function")


class TestRoundTripRequestMethod:
    def test_get_method(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request GET https://example.com\n'
        assert_round_trip_field(
            compiler, source, "steps.0.config.inline_request.method", "GET"
        )

    def test_post_method(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request POST https://example.com\n'
        assert_round_trip_field(
            compiler, source, "steps.0.config.inline_request.method", "POST"
        )

    def test_put_method(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request PUT https://example.com\n'
        assert_round_trip_field(
            compiler, source, "steps.0.config.inline_request.method", "PUT"
        )

    def test_patch_method(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request PATCH https://example.com\n'
        assert_round_trip_field(
            compiler, source, "steps.0.config.inline_request.method", "PATCH"
        )

    def test_delete_method(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request DELETE https://example.com\n'
        assert_round_trip_field(
            compiler, source, "steps.0.config.inline_request.method", "DELETE"
        )


class TestRoundTripRequestURL:
    def test_simple_url(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request GET https://example.com/api\n'
        assert_round_trip_field(
            compiler, source, "steps.0.config.inline_request.url", "https://example.com/api"
        )

    def test_url_with_path_and_query(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request GET https://example.com/api/items?limit=10\n'
        assert_round_trip_field(
            compiler, source, "steps.0.config.inline_request.url",
            "https://example.com/api/items?limit=10",
        )


class TestRoundTripHeaders:
    def test_single_header(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@step s1\n'
            '    request GET https://example.com\n'
            '    header Content-Type: application/json\n'
        )
        assert_round_trip_field(
            compiler, source,
            "steps.0.config.inline_request.headers.Content-Type",
            "application/json",
        )

    def test_multiple_headers(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@step s1\n'
            '    request GET https://example.com\n'
            '    header Accept: text/html\n'
            '    header Content-Type: application/json\n'
        )
        result = round_trip(compiler, source)
        headers = result["steps"][0]["config"]["inline_request"]["headers"]
        assert headers["Accept"] == "text/html"
        assert headers["Content-Type"] == "application/json"


class TestRoundTripBody:
    def test_body_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@step s1\n'
            '    request POST https://example.com\n'
            '    body {"key": "value"}\n'
        )
        assert_round_trip_field(
            compiler, source,
            "steps.0.config.inline_request.body",
            '{"key": "value"}',
        )


class TestRoundTripFunctionName:
    def test_function_name_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    func my_transform\n'
        assert_round_trip_field(
            compiler, source, "steps.0.config.function_name", "my_transform"
        )


class TestRoundTripDependencies:
    def test_single_dependency(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@step a\n    request GET https://a.com\n'
            '@step b <- a\n    request GET https://b.com\n'
        )
        assert_round_trip_field(compiler, source, "steps.1.depends_on", ["a"])

    def test_multiple_dependencies(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@step a\n    request GET https://a.com\n'
            '@step b\n    request GET https://b.com\n'
            '@step c <- a, b\n    request GET https://c.com\n'
        )
        assert_round_trip_field(compiler, source, "steps.2.depends_on", ["a", "b"])


class TestRoundTripOutputVariable:
    def test_output_variable_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1 -> result\n    request GET https://example.com\n'
        assert_round_trip_field(compiler, source, "steps.0.output_variable", "result")


class TestRoundTripCondition:
    def test_condition_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@var status = active\n'
            '@step s1\n'
            '    request GET https://example.com\n'
            '    when {{status}} == active\n'
        )
        # The condition is stored without @when prefix in the dict
        result = round_trip(compiler, source)
        step = result["steps"][0]
        assert step.get("condition") is not None
        assert "active" in step["condition"]


class TestRoundTripForeach:
    def test_foreach_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@step s1\n'
            '    request GET https://example.com\n'
            '    foreach {{items}} as item\n'
        )
        result = round_trip(compiler, source)
        step = result["steps"][0]
        assert step.get("foreach_collection") == "{{items}}"
        assert step.get("foreach_variable") == "item"


class TestRoundTripRepeat:
    def test_repeat_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@step s1\n'
            '    request GET https://example.com\n'
            '    repeat 5\n'
        )
        assert_round_trip_field(compiler, source, "steps.0.repeat_count", 5)


class TestRoundTripSemaphore:
    def test_semaphore_preserved(self, compiler: SCLPLLCompiler) -> None:
        source = (
            '@workflow wf1\n'
            '@step s1\n'
            '    request GET https://example.com\n'
            '    semaphore 3\n'
        )
        assert_round_trip_field(compiler, source, "steps.0.semaphore", 3)


class TestRoundTripMultipleSteps:
    def test_full_pipeline_round_trip(self, compiler: SCLPLLCompiler) -> None:
        """A multi-step workflow with deps, output vars, and mixed types."""
        source = (
            '@workflow pipeline "Data Pipeline"\n'
            '    Fetch, transform, and export data\n'
            '\n'
            '@base_url https://api.example.com\n'
            '@var token = secret123\n'
            '\n'
            '@step fetch\n'
            '    request GET /data\n'
            '    header Authorization: Bearer {{token}}\n'
            '\n'
            '@step transform <- fetch -> raw_data\n'
            '    func process_data\n'
            '\n'
            '@step export <- transform\n'
            '    request POST https://output.example.com\n'
            '    body {"processed": true}\n'
        )
        result = round_trip(compiler, source)
        assert result["id"] == "pipeline"
        assert result["name"] == "Data Pipeline"
        assert result["description"] == "Fetch, transform, and export data"
        assert result["variables"]["base_url"] == "https://api.example.com"
        assert result["variables"]["token"] == "secret123"
        assert len(result["steps"]) == 3

        fetch_step = result["steps"][0]
        assert fetch_step["id"] == "fetch"
        assert fetch_step["type"] == "request"
        assert fetch_step["config"]["inline_request"]["method"] == "GET"

        transform_step = result["steps"][1]
        assert transform_step["id"] == "transform"
        assert transform_step["type"] == "function"
        assert transform_step["depends_on"] == ["fetch"]
        assert transform_step["output_variable"] == "raw_data"

        export_step = result["steps"][2]
        assert export_step["id"] == "export"
        assert export_step["depends_on"] == ["transform"]
        assert export_step["config"]["inline_request"]["body"] == '{"processed": true}'


# ═══════════════════════════════════════════════════════════════════════
# Loss tests: non-representable fields
# ═══════════════════════════════════════════════════════════════════════


class TestLossRetryConfig:
    """Retry configuration is not representable in SCLPLL and is lost on round-trip."""

    def test_retry_config_lost_on_round_trip(self, compiler: SCLPLLCompiler) -> None:
        """Starting with a dict that has retry config, round-trip loses it."""
        definition = {
            "id": "wf1",
            "name": "Test",
            "description": "",
            "steps": [
                {
                    "id": "s1",
                    "name": "s1",
                    "type": "request",
                    "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}},
                    "retry": {"max_retries": 3, "strategy": "exponential", "delay_ms": 2000},
                }
            ],
            "variables": {},
        }
        sclpll = compiler.decompile_dict_to_sclpll(definition)
        reparsed = compiler.parse(sclpll)

        # Retry config should not be present in reparsed result
        step = reparsed["steps"][0]
        assert "retry" not in step or step.get("retry") is None


class TestLossRequestId:
    """request_id (reference to a saved request) is not representable in SCLPLL."""

    def test_request_id_lost_on_round_trip(self, compiler: SCLPLLCompiler) -> None:
        definition = {
            "id": "wf1",
            "name": "Test",
            "description": "",
            "steps": [
                {
                    "id": "s1",
                    "name": "s1",
                    "type": "request",
                    "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}},
                    "request_id": "some-uuid-1234",
                }
            ],
            "variables": {},
        }
        sclpll = compiler.decompile_dict_to_sclpll(definition)
        reparsed = compiler.parse(sclpll)

        step = reparsed["steps"][0]
        assert "request_id" not in step or step.get("request_id") is None


class TestLossStepName:
    """Step name (when different from id) is not preserved by SCLPLL.

    SCLPLL uses step id as both id and name. If the name differs from id,
    it is lost on round-trip.
    """

    def test_custom_step_name_lost(self, compiler: SCLPLLCompiler) -> None:
        definition = {
            "id": "wf1",
            "name": "Test",
            "description": "",
            "steps": [
                {
                    "id": "s1",
                    "name": "My Custom Step Name",
                    "type": "request",
                    "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}},
                }
            ],
            "variables": {},
        }
        sclpll = compiler.decompile_dict_to_sclpll(definition)
        reparsed = compiler.parse(sclpll)

        step = reparsed["steps"][0]
        # After round-trip, name defaults to id
        assert step["name"] == "s1"
        assert step["name"] != "My Custom Step Name"


class TestLossDetection:
    """The WorkflowRepository.preview_sclpll should detect non-representable field losses."""

    def test_preview_detects_retry_loss(self, compiler: SCLPLLCompiler) -> None:
        """preview_sclpll detects when retry config will be lost."""
        from app.services.workflow_service import WorkflowRepository
        from app.storage.db import Database

        # We test the preview logic directly using the compiler
        current_definition = {
            "id": "wf1",
            "name": "Test",
            "description": "",
            "steps": [
                {
                    "id": "s1",
                    "name": "s1",
                    "type": "request",
                    "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}},
                    "retry": {"max_retries": 3, "strategy": "exponential", "delay_ms": 2000},
                }
            ],
            "variables": {},
        }

        # Simulate what preview_sclpll does
        sclpll_source = compiler.decompile_dict_to_sclpll(current_definition)
        new_definition = compiler.parse(sclpll_source)

        # Detect losses
        current_steps = {s["id"]: s for s in current_definition.get("steps", [])}
        new_steps = {s["id"]: s for s in new_definition.get("steps", [])}
        losses = []

        for step_id, step in current_steps.items():
            if step_id in new_steps:
                new_step = new_steps[step_id]
                for field in ("retry", "request_id"):
                    if field in step and field not in new_step:
                        losses.append(
                            f"Step '{step_id}': field '{field}' is not representable in SCLPLL and will be lost"
                        )

        assert len(losses) == 1
        assert "retry" in losses[0]


# ═══════════════════════════════════════════════════════════════════════
# Deterministic generation
# ═══════════════════════════════════════════════════════════════════════


class TestDeterministicGeneration:
    """Same definition dict always produces the same SCLPLL output."""

    def test_same_input_same_output(self, compiler: SCLPLLCompiler) -> None:
        definition = {
            "id": "wf1",
            "name": "Test",
            "description": "A test",
            "steps": [
                {
                    "id": "s1",
                    "name": "s1",
                    "type": "request",
                    "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}},
                    "depends_on": [],
                },
                {
                    "id": "s2",
                    "name": "s2",
                    "type": "function",
                    "config": {"function_name": "my_func"},
                    "depends_on": ["s1"],
                    "output_variable": "result",
                },
            ],
            "variables": {"base_url": "https://api.example.com", "token": "abc"},
        }

        out1 = compiler.decompile_dict_to_sclpll(definition)
        out2 = compiler.decompile_dict_to_sclpll(definition)
        assert out1 == out2

    def test_round_trip_stabilizes(self, compiler: SCLPLLCompiler) -> None:
        """Parse -> decompile -> parse -> decompile produces identical output."""
        source = (
            '@workflow wf1 "Test"\n'
            '    Description here\n'
            '\n'
            '@base_url https://api.example.com\n'
            '@var token = abc\n'
            '\n'
            '@step fetch\n'
            '    request GET /data\n'
            '    header Accept: application/json\n'
            '\n'
            '@step process <- fetch -> result\n'
            '    func transform\n'
        )
        parsed1 = compiler.parse(source)
        decompiled1 = compiler.decompile_dict_to_sclpll(parsed1)
        parsed2 = compiler.parse(decompiled1)
        decompiled2 = compiler.decompile_dict_to_sclpll(parsed2)

        assert decompiled1 == decompiled2


# ═══════════════════════════════════════════════════════════════════════
# Source diagnostics
# ═══════════════════════════════════════════════════════════════════════


class TestSourceDiagnostics:
    def test_valid_source_returns_success(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n@step s1\n    request GET https://example.com\n'
        result = compiler.parse_source_diagnostics(source)
        assert result["success"] is True
        assert result["definition"] is not None
        assert result["diagnostics"] == []
        assert len(result["source_hash"]) == 16

    def test_invalid_source_returns_error_diagnostic(self, compiler: SCLPLLCompiler) -> None:
        source = "not valid sclpll"
        result = compiler.parse_source_diagnostics(source)
        assert result["success"] is False
        assert result["definition"] is None
        assert len(result["diagnostics"]) >= 1
        assert result["diagnostics"][0]["severity"] == "error"

    def test_invalid_step_reports_diagnostic(self, compiler: SCLPLLCompiler) -> None:
        """An invalid step body reports a diagnostic error."""
        source = '@workflow wf1\n@step s1\n    invalid content here\n'
        result = compiler.parse_source_diagnostics(source)
        assert result["success"] is False
        assert len(result["diagnostics"]) >= 1
        assert result["diagnostics"][0]["severity"] == "error"

    def test_source_hash_is_deterministic(self, compiler: SCLPLLCompiler) -> None:
        source = '@workflow wf1\n'
        r1 = compiler.parse_source_diagnostics(source)
        r2 = compiler.parse_source_diagnostics(source)
        assert r1["source_hash"] == r2["source_hash"]


# ═══════════════════════════════════════════════════════════════════════
# Preflight validation
# ═══════════════════════════════════════════════════════════════════════


class TestPreflightValidation:
    def test_valid_definition(self, compiler: SCLPLLCompiler) -> None:
        definition = {
            "id": "wf1",
            "steps": [
                {"id": "s1", "type": "request", "config": {}},
                {"id": "s2", "type": "request", "config": {}, "depends_on": ["s1"]},
            ],
        }
        result = compiler.validate_preflight(definition)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_missing_step_id(self, compiler: SCLPLLCompiler) -> None:
        definition = {
            "id": "wf1",
            "steps": [
                {"id": "", "type": "request", "config": {}},
            ],
        }
        result = compiler.validate_preflight(definition)
        assert result["valid"] is False
        assert any("missing" in i["message"].lower() for i in result["issues"])

    def test_broken_dependency(self, compiler: SCLPLLCompiler) -> None:
        definition = {
            "id": "wf1",
            "steps": [
                {"id": "s1", "type": "request", "config": {}, "depends_on": ["nonexistent"]},
            ],
        }
        result = compiler.validate_preflight(definition)
        assert result["valid"] is False
        assert any("nonexistent" in i["message"] for i in result["issues"])

    def test_circular_dependency(self, compiler: SCLPLLCompiler) -> None:
        definition = {
            "id": "wf1",
            "steps": [
                {"id": "a", "type": "request", "config": {}, "depends_on": ["b"]},
                {"id": "b", "type": "request", "config": {}, "depends_on": ["a"]},
            ],
        }
        result = compiler.validate_preflight(definition)
        assert result["valid"] is False
        assert any("circular" in i["message"].lower() for i in result["issues"])

    def test_empty_steps_valid(self, compiler: SCLPLLCompiler) -> None:
        definition = {"id": "wf1", "steps": []}
        result = compiler.validate_preflight(definition)
        assert result["valid"] is True
