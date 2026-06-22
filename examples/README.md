# Examples

This directory contains example workflows demonstrating SCLPLAPI features.

## Available Examples

| Example | Description | Steps |
|---------|-------------|-------|
| [weather_pipeline](weather_pipeline/) | Fetch weather data, extract, and export | 5 |
| [getting-started](getting-started/) | Beginner-friendly workflow with all features | 8 |
| [api-testing](api-testing/) | Test multiple API endpoints in parallel | 6 |
| [data-pipeline](data-pipeline/) | Fetch from multiple sources, merge, and report | 7 |

## Running Examples

### Using the TUI

```bash
python -m app
# Press R to run a workflow, select an example
```

### Using the CLI

```bash
# Run a workflow
python -m app.core.engine.sclpll_cli run examples/weather_pipeline/weather-pipeline.sclpll

# Validate a workflow
python -m app.core.engine.sclpll_cli validate examples/getting-started/getting-started.sclpll

# Compile SCLPLL to JSON
python -m app.core.engine.sclpll_cli compile examples/getting-started/getting-started.sclpll
```

## Example Structure

Each example contains:
- `workflow.json` — Compiled workflow definition
- `*.sclpll` — SCLPLL script (human-readable)
- `README.md` — Example description (optional)

## Creating Your Own

1. Create a new directory in `examples/`
2. Write a `.sclpll` file or `workflow.json`
3. Run it with `python -m app` or the CLI

See [SCLPLL Language Reference](../docs/SCLPLL_LANGUAGE.md) for syntax details.
