# SCLPLAPI Tools

Development utilities for validating, linting, and analyzing SCLPLAPI projects.

## Tools

### `workflow_validator.py`

Validates `workflow.json` files for structural correctness.

**Checks:**
- Required fields (`id`, `name`, `steps`)
- Circular dependency detection (topological sort)
- Duplicate step IDs
- Missing dependency references
- Step type validation (`request`, `function`, `transformer`, `export`, `delay`)
- Function reference verification against discovered functions
- Variable usage analysis (undeclared/unused variables)

**Usage:**
```bash
python tools/workflow_validator.py examples/weather_pipeline/workflow.json
python tools/workflow_validator.py workflow.json --functions-dir functions
```

**Exit codes:** 0 = valid, 1 = errors found

---

### `function_linter.py`

Lints Python function files for proper metadata and style.

**Checks:**
- Metadata docstring with `@name`, `@type`, `@version`
- `run(ctx)` entrypoint exists and accepts `ctx` parameter
- Return statement present in `run()`
- Bare `except:` clauses
- Line length (120 chars)
- Unused imports

**Usage:**
```bash
python tools/function_linter.py functions/generate_report.py
python tools/function_linter.py functions/
python tools/function_linter.py --functions-dir functions
```

**Exit codes:** 0 = clean, 1 = errors found

---

### `sclpll_formatter.py`

Formats `.sclpll` files consistently.

**Features:**
- Topological sort of steps by dependency order
- Consistent arrow alignment (`<-` and `->`)
- Preserves comments and workflow header
- Normalizes indentation to 4 spaces

**Usage:**
```bash
python tools/sclpll_formatter.py examples/weather_pipeline/script.sclpll
python tools/sclpll_formatter.py script.sclpll --check    # check only, no output
python tools/sclpll_formatter.py script.sclpll --write    # write formatted file
```

**Exit codes:** 0 = formatted/ok, 1 = needs formatting (with `--check`)

---

### `performance_analyzer.py`

Analyzes execution statistics from workflow runs.

**Analysis:**
- Identifies bottleneck steps (slowest by duration)
- Computes critical path through the workflow DAG
- Suggests parallelization opportunities by execution level
- Reports total vs parallel execution time savings

**Usage:**
```bash
python tools/performance_analyzer.py                          # reads output/execution_stats.json
python tools/performance_analyzer.py path/to/stats.json       # custom path
```

**Expected input format:**
```json
{
  "steps": [
    {
      "id": "fetch_data",
      "name": "Fetch Data",
      "type": "request",
      "duration_ms": 250,
      "depends_on": []
    }
  ]
}
```

## Running all tools

```bash
# Validate all example workflows
for f in examples/*/workflow.json; do python tools/workflow_validator.py "$f"; done

# Lint all functions
python tools/function_linter.py functions/

# Check formatting of all SCLPLL files
for f in examples/*/script.sclpll; do python tools/sclpll_formatter.py "$f" --check; done
```
