# Weather at 5AM Pipeline

A complete SCLPLAPI example that chains two API calls, extracts selective data, and exports results.

## What it does

1. **Fetches today's weather** from `wttr.in` for a given city
2. **Extracts the date** from the response
3. **Fetches hourly weather** for that date
4. **Extracts 5AM temperature** (nearest 3-hour reading)
5. **Exports** filtered data to JSON and CSV

## Run it

```bash
python examples/weather_pipeline/run.py
```

## Output

```
examples/weather_pipeline/output/
  weather_at_5am.json
  weather_at_5am.csv
```

Contains: date, city, temperature, description, humidity, wind speed.

## How it works

### Workflow (`workflow.json`)

```json
{
  "steps": [
    {"id": "get_weather_today", "type": "request", "config": {"inline_request": {"url": "https://wttr.in/{{city}}?format=j1"}}},
    {"id": "extract_date",      "type": "function", "depends_on": ["get_weather_today"], "config": {"function_name": "Extract Date"}},
    {"id": "get_weather_hourly", "type": "request", "depends_on": ["extract_date"], "config": {"inline_request": {"url": "https://wttr.in/{{city}}?format=j1"}}},
    {"id": "extract_weather",   "type": "function", "depends_on": ["get_weather_hourly"], "config": {"function_name": "Extract 5AM Weather"}},
    {"id": "export_data",       "type": "function", "depends_on": ["extract_weather"], "config": {"function_name": "Export Weather Data"}}
  ]
}
```

### Functions (`functions/transformers/`)

- `extract_date.py` — reads step output, extracts date, sets `{{today}}` variable
- `extract_weather.py` — reads hourly data, finds 5AM reading, sets `{{weatherAt5AM_*}}` variables
- `export_weather.py` — writes filtered data to JSON and CSV files

### Key pattern: variable chaining

Each function sets `ctx.workflow_variables` which the next step's URL can reference with `{{var}}` syntax:

```
Step 1 output → extract_date sets {{today}} → Step 3 URL uses {{today}}
Step 3 output → extract_weather sets {{weatherAt5AM_tempC}} → export writes it
```

## Adapting for your own use

1. Change the city: edit `"variables": {"city": "London"}` in `workflow.json`
2. Change the time: edit the `time == "500"` check in `extract_weather.py`
3. Add more fields: add more `ctx.workflow_variables[...]` in the extractor
4. Chain more APIs: add steps to `workflow.json` with `depends_on`
