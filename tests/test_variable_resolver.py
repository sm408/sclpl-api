from app.core.engine.variable_resolver import DefaultVariableResolver
from app.core.models.context import ExecutionContext
from app.core.models.environment import Environment, Variable, VariableScope


def test_resolve_simple_variable():
    resolver = DefaultVariableResolver()
    ctx = ExecutionContext(variables={"host": "localhost", "port": "8080"})
    result = resolver.resolve("http://{{host}}:{{port}}/api", ctx)
    assert result == "http://localhost:8080/api"


def test_resolve_missing_variable():
    resolver = DefaultVariableResolver()
    ctx = ExecutionContext(variables={"host": "localhost"})
    result = resolver.resolve("http://{{host}}:{{port}}/api", ctx)
    assert result == "http://localhost:{{port}}/api"


def test_resolve_no_variables():
    resolver = DefaultVariableResolver()
    ctx = ExecutionContext()
    result = resolver.resolve("http://example.com/api", ctx)
    assert result == "http://example.com/api"


def test_extract_variable_keys():
    resolver = DefaultVariableResolver()
    keys = resolver.extract_variable_keys("http://{{host}}:{{port}}/{{path}}")
    assert keys == ["host", "port", "path"]


def test_resolve_all_with_environment():
    resolver = DefaultVariableResolver()
    env = Environment(
        id="e1",
        name="dev",
        variables=[
            Variable(key="host", value="dev.example.com"),
            Variable(key="token", value="abc123", is_secret=True),
        ],
    )
    ctx = ExecutionContext(environment=env, variables={"host": "dev.example.com", "token": "abc123"})
    resolved = resolver.resolve_all(ctx)
    keys = [r.key for r in resolved]
    assert "host" in keys
    assert "token" in keys


def test_build_variable_map():
    resolver = DefaultVariableResolver()
    env = Environment(
        id="e1",
        name="dev",
        variables=[Variable(key="host", value="dev.example.com")],
    )
    ctx = ExecutionContext(
        environment=env,
        workflow_variables={"wf_var": "wf_val"},
        batch_row={"batch_col": "batch_val"},
    )
    merged = resolver.build_variable_map(ctx)
    assert merged["host"] == "dev.example.com"
    assert merged["wf_var"] == "wf_val"
    assert merged["batch_col"] == "batch_val"
