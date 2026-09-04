# Data Engineer: Author a Reliable Workflow

This path is for someone who turns a repeatable API or data task into a version-controlled
workflow. The goal is a small, testable pipeline rather than a one-off script.

## Start from a known example

```bash
sclpl validate examples/persona-data-engineer-api.sclpll
sclpl explain examples/persona-data-engineer-api.sclpll --memory
```

The example reads a local demo API, follows a cursor, flattens records, checks the output
schema, and writes CSV. Replace the `base` variable with the real API only after validation.

## The authoring pattern

```sclpll
@step fetch
  get {{base}}/orders
  paginate cursor cursor_path=next param=cursor max_pages=40

@step shaped
  flatten @fetch.body

@step checked
  assert_schema @shaped {"id": "integer", "customer_name": "string", "amount": "number"}
```

References create dependencies. Because `shaped` reads `@fetch.body`, it waits for `fetch`.
Independent roots are free to run concurrently.

## Run a real public API workflow

```bash
cd "$env:USERPROFILE\\Downloads\\sclpl-live-demos"
python -m sclpl run .\\data-engineer-open-meteo.sclpll .\\delhi-weather.json
```

The matching live demo pack in Downloads calls Open-Meteo without an API key. The repository
example remains deterministic and is intended for validation and CI.

## Add a custom function

Use the public function registry when a transformation is specific to your domain:

```python
from sclpl.ext.functions import function


@function("domain", builtin=False)
def domain(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0]
```

Keep functions typed, deterministic where possible, and covered by a focused unit test.
Use a plugin when the capability needs packaging, discovery, or an external dependency.

## Data engineer checklist

- Give every network step a timeout and an appropriate retry policy.
- Put pagination bounds on every unbounded source.
- Assert the columns and types required by downstream users.
- Keep secrets in `sclpl secret`, never in workflow files.
- Run `validate`, `explain`, tests, and the full quality gates before merging.
