# Analyst: Run and Trust a Workflow

This path is for someone who runs an existing workflow, checks the result, and hands a file
to another person. You do not need to understand the scheduler or write Python.

## Start with the application check

```bash
python -m sclpl doctor
python -m sclpl validate examples/persona-analyst-report.sclpll
```

`validate` does not call a network or write an output. It catches malformed expressions,
missing functions, bad ports, and incomplete workflow graphs first.

## Run the report

```bash
python -m sclpl run examples/persona-analyst-report.sclpll --out report=report.csv --out profile=profile.json
```

The workflow filters paid records, checks their schema, writes `report.csv`, and writes a
small `profile.json` summary. Open the CSV in a spreadsheet or pass it to another command.

## Run a managed remote report

Validate a remote bundle before running it; validation fetches only the workflow definition,
not source datasets or outputs.

```bash
sclpl validate azblob://myaccount/workflows/orders/
sclpl run azblob://myaccount/workflows/orders/ --out report=./orders-review.csv
```

Use a local `--out` override for exploratory review. Do not paste a SAS token into a command,
workflow, or run note; record the workflow URI and run ID with the handoff instead.

## Inspect before changing anything

```bash
python -m sclpl explain examples/persona-analyst-report.sclpll
python -m sclpl runs list
python -m sclpl runs show latest
```

Use `explain` to see the dependency graph and `runs show` to see what actually happened.
The terminal progress is on stderr, so output files and pipelines remain clean.

## When the data is wrong

An assertion failure exits with code `4`. That means the request or workflow ran, but the
data did not satisfy its contract. Check the run output and compare it with the previous run:

```bash
python -m sclpl runs diff latest previous
```

## Analyst checklist

- Validate before running.
- Confirm the output path and format.
- Check row counts and schema warnings.
- Keep the workflow unchanged when only the output destination changes.
- Share the workflow and run report with the data engineer when the API shape changes.
- Keep the remote workflow unchanged when only a one-off output destination changes.
