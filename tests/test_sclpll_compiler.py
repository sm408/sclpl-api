from __future__ import annotations

import json

import pytest

from app.core.engine.sclpll_compiler import SCLPLLCompiler, SCLPLLParseError


@pytest.fixture
def compiler() -> SCLPLLCompiler:
    return SCLPLLCompiler()


VALID_MINIMAL = '@workflow test1 "Test Workflow"\n'


class TestSCLPLLCompilerParse:
    """Tests for SCLPLLCompiler.parse() with valid and invalid inputs."""

    def test_parse_minimal_workflow(self, compiler: SCLPLLCompiler) -> None:
        """A minimal @workflow directive produces a valid dict with id and name."""
        result = compiler.parse(VALID_MINIMAL)
        assert result["id"] == "test1"
        assert result["name"] == "Test Workflow"
        assert result["steps"] == []
        assert result["variables"] == {}

    def test_parse_workflow_without_quoted_name(self, compiler: SCLPLLCompiler) -> None:
        """When no quoted name is given, name defaults to the id."""
        result = compiler.parse("@workflow myflow\n")
        assert result["id"] == "myflow"
        assert result["name"] == "myflow"

    def test_parse_workflow_with_description(self, compiler: SCLPLLCompiler) -> None:
        """Indented lines after @workflow become the description (flushed by a blank line)."""
        source = '@workflow wf1 "My Flow"\n    This is a description\n    on two lines\n\n'
        result = compiler.parse(source)
        assert result["description"] == "This is a description on two lines"

    def test_parse_base_url(self, compiler: SCLPLLCompiler) -> None:
        """@base_url is stored in variables dict."""
        source = '@workflow wf1\n@base_url https://api.example.com\n'
        result = compiler.parse(source)
        assert result["variables"]["base_url"] == "https://api.example.com"

    def test_parse_variables(self, compiler: SCLPLLCompiler) -> None:
        """@var key = value entries are stored in variables dict."""
        source = '@workflow wf1\n@var token = abc123\n@var host = localhost\n'
        result = compiler.parse(source)
        assert result["variables"]["token"] == "abc123"
        assert result["variables"]["host"] == "localhost"

    def test_parse_step_with_inline_request(self, compiler: SCLPLLCompiler) -> None:
        """A @step with indented request produces a request step with inline config."""
        source = '@workflow wf1\n@step fetch_data\n    request GET https://example.com/api\n'
        result = compiler.parse(source)
        assert len(result["steps"]) == 1
        step = result["steps"][0]
        assert step["id"] == "fetch_data"
        assert step["type"] == "request"
        assert step["config"]["inline_request"]["method"] == "GET"
        assert step["config"]["inline_request"]["url"] == "https://example.com/api"

    def test_parse_step_with_post_method(self, compiler: SCLPLLCompiler) -> None:
        """POST method is correctly captured."""
        source = '@workflow wf1\n@step create\n    request POST https://example.com/items\n'
        result = compiler.parse(source)
        assert result["steps"][0]["config"]["inline_request"]["method"] == "POST"

    def test_parse_step_with_headers(self, compiler: SCLPLLCompiler) -> None:
        """Indented header lines are added to the inline request headers dict."""
        source = (
            '@workflow wf1\n'
            '@step api_call\n'
            '    request GET https://example.com\n'
            '    header Content-Type: application/json\n'
            '    header Accept: text/html\n'
        )
        result = compiler.parse(source)
        headers = result["steps"][0]["config"]["inline_request"]["headers"]
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "text/html"

    def test_parse_step_with_body(self, compiler: SCLPLLCompiler) -> None:
        """Indented body line is stored in the inline request config."""
        source = (
            '@workflow wf1\n'
            '@step post_data\n'
            '    request POST https://example.com\n'
            '    body {"key": "value"}\n'
        )
        result = compiler.parse(source)
        body = result["steps"][0]["config"]["inline_request"]["body"]
        assert body == '{"key": "value"}'

    def test_parse_step_with_function(self, compiler: SCLPLLCompiler) -> None:
        """A step with func directive becomes a function step."""
        source = '@workflow wf1\n@step transform\n    func my_transform\n'
        result = compiler.parse(source)
        step = result["steps"][0]
        assert step["type"] == "function"
        assert step["config"]["function_name"] == "my_transform"

    def test_parse_step_with_dependencies(self, compiler: SCLPLLCompiler) -> None:
        """The <- syntax parses comma-separated dependency list."""
        source = '@workflow wf1\n@step c <- a, b\n    request GET https://example.com\n'
        result = compiler.parse(source)
        assert result["steps"][0]["depends_on"] == ["a", "b"]

    def test_parse_step_with_output_variable(self, compiler: SCLPLLCompiler) -> None:
        """The -> syntax parses the output variable name."""
        source = '@workflow wf1\n@step fetch -> result\n    request GET https://example.com\n'
        result = compiler.parse(source)
        assert result["steps"][0]["output_variable"] == "result"

    def test_parse_step_with_deps_and_output(self, compiler: SCLPLLCompiler) -> None:
        """Combined <- and -> syntax works."""
        source = '@workflow wf1\n@step merge <- a, b -> output\n    request GET https://example.com\n'
        result = compiler.parse(source)
        step = result["steps"][0]
        assert step["depends_on"] == ["a", "b"]
        assert step["output_variable"] == "output"

    def test_parse_multiple_steps(self, compiler: SCLPLLCompiler) -> None:
        """Multiple @step directives are collected in order."""
        source = (
            '@workflow wf1\n'
            '@step a\n    request GET https://a.com\n'
            '@step b <- a\n    request GET https://b.com\n'
        )
        result = compiler.parse(source)
        assert len(result["steps"]) == 2
        assert result["steps"][0]["id"] == "a"
        assert result["steps"][1]["id"] == "b"

    def test_parse_comments_and_blanks_ignored(self, compiler: SCLPLLCompiler) -> None:
        """Comment and blank lines do not cause errors."""
        source = (
            '# comment\n'
            '\n'
            '@workflow wf1\n'
            '# another comment\n'
            '\n'
            '@step s1\n'
            '    request GET https://example.com\n'
        )
        result = compiler.parse(source)
        assert result["id"] == "wf1"
        assert len(result["steps"]) == 1


class TestSCLPLLCompilerParseErrors:
    """Tests for parse error cases."""

    def test_missing_workflow_directive(self, compiler: SCLPLLCompiler) -> None:
        """Source without @workflow raises SCLPLLParseError."""
        with pytest.raises(SCLPLLParseError, match="Missing @workflow directive"):
            compiler.parse("@step s1\n")

    def test_duplicate_workflow_directive(self, compiler: SCLPLLCompiler) -> None:
        """Duplicate @workflow raises SCLPLLParseError."""
        source = '@workflow a\n@workflow b\n'
        with pytest.raises(SCLPLLParseError, match="Duplicate @workflow"):
            compiler.parse(source)

    def test_unknown_directive(self, compiler: SCLPLLCompiler) -> None:
        """An unknown @ directive raises SCLPLLParseError."""
        source = '@workflow wf1\n@unknown foo\n'
        with pytest.raises(SCLPLLParseError, match="Unknown directive"):
            compiler.parse(source)

    def test_unknown_step_body_syntax(self, compiler: SCLPLLCompiler) -> None:
        """Unrecognized indented content under a step raises SCLPLLParseError."""
        source = '@workflow wf1\n@step s1\n    garbage line\n'
        with pytest.raises(SCLPLLParseError, match="Unknown step body syntax"):
            compiler.parse(source)

    def test_invalid_step_syntax(self, compiler: SCLPLLCompiler) -> None:
        """Malformed @step line raises SCLPLLParseError."""
        source = '@workflow wf1\n@step\n'
        with pytest.raises(SCLPLLParseError):
            compiler.parse(source)

    def test_unexpected_line_outside_step(self, compiler: SCLPLLCompiler) -> None:
        """A non-directive, non-indented line outside a step raises error."""
        source = '@workflow wf1\nrandom text\n'
        with pytest.raises(SCLPLLParseError, match="Unexpected line"):
            compiler.parse(source)


class TestSCLPLLCompilerCompileToJson:
    """Tests for compile_to_json."""

    def test_compile_to_json_produces_valid_json(self, compiler: SCLPLLCompiler) -> None:
        """compile_to_json returns parseable JSON matching the parsed dict."""
        source = '@workflow wf1 "Test"\n@step s1\n    request GET https://example.com\n'
        json_str = compiler.compile_to_json(source)
        data = json.loads(json_str)
        assert data["id"] == "wf1"
        assert len(data["steps"]) == 1

    def test_compile_to_json_includes_all_fields(self, compiler: SCLPLLCompiler) -> None:
        """JSON output includes variables, description, steps."""
        source = (
            '@workflow wf1 "Flow"\n'
            '    A test flow\n'
            '\n'
            '@var token = abc\n'
            '@step s1\n'
            '    request GET https://example.com\n'
        )
        data = json.loads(compiler.compile_to_json(source))
        assert data["description"] == "A test flow"
        assert data["variables"]["token"] == "abc"


class TestSCLPLLCompilerCompileToPy:
    """Tests for compile_to_py."""

    def test_compile_to_py_returns_python_string(self, compiler: SCLPLLCompiler) -> None:
        """compile_to_py returns a string containing Python imports and async main."""
        source = '@workflow wf1\n@step s1\n    request GET https://example.com\n'
        py_code = compiler.compile_to_py(source)
        assert "import asyncio" in py_code
        assert "async def main()" in py_code
        assert "ParallelWorkflowEngine" in py_code

    def test_compile_to_py_validates_source(self, compiler: SCLPLLCompiler) -> None:
        """compile_to_py still parses source to validate it."""
        with pytest.raises(SCLPLLParseError):
            compiler.compile_to_py("invalid source")


class TestSCLPLLCompilerDecompile:
    """Tests for decompile_json_to_sclpll and decompile_dict_to_sclpll."""

    def test_round_trip_minimal(self, compiler: SCLPLLCompiler) -> None:
        """Parse -> decompile round-trips a minimal workflow correctly."""
        source = '@workflow wf1 "Test"\n'
        parsed = compiler.parse(source)
        sclpll = compiler.decompile_dict_to_sclpll(parsed)
        assert "@workflow wf1" in sclpll
        assert "Test" in sclpll

    def test_round_trip_with_steps(self, compiler: SCLPLLCompiler) -> None:
        """Parse -> decompile round-trips steps with dependencies."""
        source = (
            '@workflow wf1 "Flow"\n'
            '@step a\n'
            '    request GET https://example.com\n'
            '@step b <- a\n'
            '    request POST https://example.com\n'
        )
        parsed = compiler.parse(source)
        sclpll = compiler.decompile_dict_to_sclpll(parsed)
        re_parsed = compiler.parse(sclpll)
        assert re_parsed["id"] == parsed["id"]
        assert len(re_parsed["steps"]) == 2
        assert re_parsed["steps"][1]["depends_on"] == ["a"]

    def test_round_trip_with_function_step(self, compiler: SCLPLLCompiler) -> None:
        """Function steps survive a round-trip."""
        source = '@workflow wf1\n@step transform\n    func my_func\n'
        parsed = compiler.parse(source)
        sclpll = compiler.decompile_dict_to_sclpll(parsed)
        re_parsed = compiler.parse(sclpll)
        assert re_parsed["steps"][0]["type"] == "function"
        assert re_parsed["steps"][0]["config"]["function_name"] == "my_func"

    def test_decompile_json_to_sclpll(self, compiler: SCLPLLCompiler) -> None:
        """decompile_json_to_sclpll accepts a JSON string and returns SCLPLL."""
        data = {
            "id": "wf1",
            "name": "Test",
            "description": "",
            "steps": [{"id": "s1", "name": "s1", "type": "request", "config": {"inline_request": {"method": "GET", "url": "https://example.com", "headers": {}}}}],
            "variables": {},
        }
        sclpll = compiler.decompile_json_to_sclpll(json.dumps(data))
        assert "@workflow wf1" in sclpll
        assert "request GET https://example.com" in sclpll

    def test_decompile_with_output_variable(self, compiler: SCLPLLCompiler) -> None:
        """Output variable survives decompilation."""
        source = '@workflow wf1\n@step s1 -> result\n    request GET https://example.com\n'
        parsed = compiler.parse(source)
        sclpll = compiler.decompile_dict_to_sclpll(parsed)
        assert "-> result" in sclpll

    def test_decompile_with_base_url(self, compiler: SCLPLLCompiler) -> None:
        """base_url variable is rendered as @base_url directive."""
        source = '@workflow wf1\n@base_url https://api.example.com\n@step s1\n    request GET /items\n'
        parsed = compiler.parse(source)
        sclpll = compiler.decompile_dict_to_sclpll(parsed)
        assert "@base_url https://api.example.com" in sclpll

    def test_decompile_with_description(self, compiler: SCLPLLCompiler) -> None:
        """Description is rendered as indented text after @workflow."""
        source = '@workflow wf1 "Flow"\n    This is a test\n\n'
        parsed = compiler.parse(source)
        sclpll = compiler.decompile_dict_to_sclpll(parsed)
        assert "This is a test" in sclpll

    def test_decompile_with_headers_and_body(self, compiler: SCLPLLCompiler) -> None:
        """Headers and body survive round-trip."""
        source = (
            '@workflow wf1\n'
            '@step s1\n'
            '    request POST https://example.com\n'
            '    header Content-Type: application/json\n'
            '    body {"key": "value"}\n'
        )
        parsed = compiler.parse(source)
        sclpll = compiler.decompile_dict_to_sclpll(parsed)
        re_parsed = compiler.parse(sclpll)
        inline = re_parsed["steps"][0]["config"]["inline_request"]
        assert inline["headers"]["Content-Type"] == "application/json"
        assert inline["body"] == '{"key": "value"}'
