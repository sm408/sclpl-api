"""Tests for app.utils module."""

import json

from app.core.models.context import ExecutionContext
from app.utils.response_parser import (
    get_nested,
    parse_body,
    parse_step_output,
    parse_workflow_variable,
)
from app.utils.workflow_runner import load_workflow


class TestLoadWorkflow:
    """Tests for load_workflow function."""

    def test_load_valid_workflow(self, tmp_path):
        workflow_file = tmp_path / "workflow.json"
        workflow_file.write_text(json.dumps({
            "id": "test",
            "name": "Test Workflow",
            "description": "A test",
            "steps": [
                {"id": "s1", "name": "Step 1", "type": "request",
                 "config": {"inline_request": {"method": "GET", "url": "http://example.com"}}}
            ],
            "variables": {"base_url": "http://example.com"}
        }))

        workflow = load_workflow(workflow_file)
        assert workflow.id == "test"
        assert workflow.name == "Test Workflow"
        assert len(workflow.steps) == 1
        assert workflow.variables["base_url"] == "http://example.com"

    def test_load_workflow_with_dependencies(self, tmp_path):
        workflow_file = tmp_path / "workflow.json"
        workflow_file.write_text(json.dumps({
            "id": "test",
            "name": "Test",
            "steps": [
                {"id": "s1", "type": "request", "config": {"inline_request": {"method": "GET", "url": "http://example.com"}}},
                {"id": "s2", "type": "function", "depends_on": ["s1"],
                 "config": {"function_name": "Test"}}
            ]
        }))

        workflow = load_workflow(workflow_file)
        assert workflow.steps[1].depends_on == ["s1"]

    def test_load_workflow_with_new_fields(self, tmp_path):
        workflow_file = tmp_path / "workflow.json"
        workflow_file.write_text(json.dumps({
            "id": "test",
            "name": "Test",
            "steps": [
                {"id": "s1", "type": "request",
                 "config": {"inline_request": {"method": "GET", "url": "http://example.com"}},
                 "semaphore": 3, "condition": "{{x}} == 1"}
            ]
        }))

        workflow = load_workflow(workflow_file)
        assert workflow.steps[0].semaphore == 3
        assert workflow.steps[0].condition == "{{x}} == 1"


class TestResponseParser:
    """Tests for response_parser functions."""

    def test_parse_step_output_with_dict(self):
        ctx = ExecutionContext()
        ctx.step_outputs["s1"] = {"status_code": 200, "body": "ok"}
        result = parse_step_output(ctx, "s1")
        assert result == {"status_code": 200, "body": "ok"}

    def test_parse_step_output_with_json_string(self):
        ctx = ExecutionContext()
        ctx.step_outputs["s1"] = '{"status_code": 200}'
        result = parse_step_output(ctx, "s1")
        assert result == {"status_code": 200}

    def test_parse_step_output_missing(self):
        ctx = ExecutionContext()
        result = parse_step_output(ctx, "nonexistent")
        assert result == {}

    def test_parse_body_dict(self):
        ctx = ExecutionContext()
        ctx.step_outputs["s1"] = {"body": {"users": [1, 2, 3]}}
        result = parse_body(ctx, "s1")
        assert result == {"users": [1, 2, 3]}

    def test_parse_body_json_string(self):
        ctx = ExecutionContext()
        ctx.step_outputs["s1"] = {"body": '{"users": [1, 2, 3]}'}
        result = parse_body(ctx, "s1")
        assert result == {"users": [1, 2, 3]}

    def test_parse_body_missing(self):
        ctx = ExecutionContext()
        result = parse_body(ctx, "s1")
        assert result == {}

    def test_get_nested_simple(self):
        data = {"user": {"name": "John"}}
        assert get_nested(data, "user.name") == "John"

    def test_get_nested_deep(self):
        data = {"a": {"b": {"c": {"d": 42}}}}
        assert get_nested(data, "a.b.c.d") == 42

    def test_get_nested_list_index(self):
        data = {"items": [10, 20, 30]}
        assert get_nested(data, "items.1") == 20

    def test_get_nested_missing(self):
        data = {"user": {"name": "John"}}
        assert get_nested(data, "user.age", default=0) == 0

    def test_get_nested_none(self):
        data = {"user": None}
        assert get_nested(data, "user.name", default="N/A") == "N/A"

    def test_parse_workflow_variable_json(self):
        ctx = ExecutionContext()
        ctx.workflow_variables["data"] = '{"key": "value"}'
        result = parse_workflow_variable(ctx, "data")
        assert result == {"key": "value"}

    def test_parse_workflow_variable_string(self):
        ctx = ExecutionContext()
        ctx.workflow_variables["name"] = "hello"
        result = parse_workflow_variable(ctx, "name")
        assert result == "hello"

    def test_parse_workflow_variable_missing(self):
        ctx = ExecutionContext()
        result = parse_workflow_variable(ctx, "missing")
        assert result == ""
