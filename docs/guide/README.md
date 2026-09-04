# Workflow Guide

This is the public manual for writing and operating `sclpl` workflows. Read it in order the
first time; use the reference pages later as a lookup.

## Choose a path

| You are... | Start here |
|---|---|
| Running an existing workflow | [Analyst guide](../playbooks/05-analyst.md) |
| Authoring workflows and functions | [Data engineer guide](../playbooks/06-data-engineer.md) |
| Extending the runtime | [Software engineer guide](../playbooks/07-software-engineer.md) |

## Core pages

| Page | Answers |
|---|---|
| [Workflow anatomy](workflow-anatomy.md) | What each section and line changes |
| [SCLPLL reference](sclpll-reference.md) | Complete file syntax and supported clauses |
| [Glossary](glossary.md) | What workflow terms mean in plain language |
| [Examples](../../examples/) | Runnable files, from one request to plugins |

## The shortest mental model

```text
workflow file
  -> parse and validate
  -> infer references into a dependency graph
  -> schedule ready steps
  -> preserve typed values between steps
  -> write declared outputs
```

There are two workflow surfaces: SCLPLL is the hand-written form and JSON is the generated or
programmatic form. Both compile to the same internal representation.

## Basic commands

```bash
python -m sclpl validate workflow.sclpll
python -m sclpl explain workflow.sclpll
python -m sclpl run workflow.sclpll output.csv
python -m sclpl run workflow.sclpll --out report=output.csv
python -m sclpl fmt workflow.sclpll
python -m sclpl convert workflow.sclpll workflow.json
```

`validate` is the safe first command: it does not call the network or write workflow outputs.
`explain` shows the graph, roots, pruning, and memory decisions. `run` executes it.

