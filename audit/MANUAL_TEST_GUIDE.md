# SCLPLAPI Manual Test Guide

> For human testers. Check off each item as you verify it.

---

## Prerequisites

- Python 3.10+
- `pip install -e .` from repo root
- Terminal with Unicode support (Windows Terminal recommended)

---

## Test Suite 1: TUI

### 1.1 Launch TUI

- [ ] Run: `python -m app tui`
- [ ] Logo displays correctly (ASCII art, no broken characters)
- [ ] Main menu shows all options (R, L, F, H, E, V, Q)
- [ ] Press **Q** to quit — exits cleanly

### 1.2 Run Workflow

- [ ] Press **R**
- [ ] Select a workflow (e.g., `examples/financial_pipeline/script.sclpll`)
- [ ] Steps execute with status indicators (OK/FAIL)
- [ ] Timing shows for each step (e.g., `448ms`)
- [ ] PASSED/FAILED shows at end with total time

### 1.3 Browse Functions

- [ ] Press **F**
- [ ] List shows all functions from `functions/` directory
- [ ] Name, type, version columns visible

### 1.4 View History

- [ ] Press **H**
- [ ] History entries display in a table
- [ ] Method and status colors work (green for 2xx, red for errors)

### 1.5 Validate Script

- [ ] Press **V**
- [ ] Enter a valid `.sclpll` path — shows "Valid"
- [ ] Enter an invalid script — shows error with line number

### 1.6 Manage Environments

- [ ] Press **E**
- [ ] List shows existing environments
- [ ] Can create/activate an environment

---

## Test Suite 2: Web GUI

> **Status: Planned** — These tests apply when the Web GUI is implemented.

### 2.1 Launch Web GUI

- [ ] Run: `python -m app web`
- [ ] Browser opens automatically at `http://localhost:8000`
- [ ] Page loads without console errors
- [ ] Sidebar visible with navigation links

### 2.2 Home Dashboard

- [ ] Welcome message shows
- [ ] Dashboard cards visible (requests, collections, workflows, functions)
- [ ] Stats counters show numbers
- [ ] Click any card navigates to that section

### 2.3 Request Editor

- [ ] Click **Request Editor** in sidebar
- [ ] Method selector works (GET / POST / PUT / DELETE / PATCH)
- [ ] URL input accepts text
- [ ] Params tab works — add key/value pairs
- [ ] Headers tab works — add key/value pairs
- [ ] Body tab works — enter JSON
- [ ] Send button triggers request
- [ ] Response shows status code, time, size
- [ ] Response body formatted as JSON

### 2.4 Collections

- [ ] Click **Collections** in sidebar
- [ ] Collections list shows
- [ ] Create new collection works
- [ ] Delete collection works (with confirmation)
- [ ] Click collection to expand and see requests

### 2.5 Workflows

- [ ] Click **Workflows** in sidebar
- [ ] List of `.sclpll` workflows shows
- [ ] Run button triggers execution
- [ ] Progress shows during execution
- [ ] Step timing displays

### 2.6 Flow Builder

- [ ] Click **Flow Builder** in sidebar
- [ ] Canvas renders
- [ ] Nodes display with colors (HTTP = blue, Function = green)
- [ ] Connections show between nodes
- [ ] Click node to see details panel
- [ ] Drag to reposition nodes

### 2.7 Functions

- [ ] Click **Functions** in sidebar
- [ ] Function list shows all discovered functions
- [ ] Click function to see source code
- [ ] Search/filter by name works

### 2.8 History

- [ ] Click **History** in sidebar
- [ ] History table shows past requests
- [ ] Method colors: GET = green, POST = blue, PUT = orange, DELETE = red
- [ ] Status colors: 2xx = green, 4xx = yellow, 5xx = red
- [ ] Filter by method works

### 2.9 Settings

- [ ] Click **Settings** in sidebar
- [ ] Base URL field is editable
- [ ] Theme selector works (light / dark)
- [ ] Timeout field accepts numbers

---

## Test Suite 3: CLI Commands

### 3.1 SCLPLL Commands

- [ ] `python -m app.core.engine.sclpll_cli compile examples/financial_pipeline/script.sclpll` — generates `workflow.json` + `run.py`
- [ ] `python -m app.core.engine.sclpll_cli validate examples/financial_pipeline/script.sclpll` — outputs "Valid"
- [ ] `python -m app.core.engine.sclpll_cli run examples/financial_pipeline/script.sclpll` — executes workflow
- [ ] `python -m app.core.engine.sclpll_cli decompile workflow.json` — reconstructs `.sclpll`

### 3.2 Plugin Commands

- [ ] `python -m app plugins list` — shows installed plugins
- [ ] `python -m app plugins info sample-api-plugin` — shows plugin details

### 3.3 Export Commands

- [ ] `python -m app export-all output/` — exports data to directory
- [ ] `python -m app import-all output/` — imports data from directory

---

## Test Suite 4: Examples

### 4.1 Weather Pipeline

- [ ] `python -m app.core.engine.sclpll_cli run examples/weather_pipeline/script.sclpll`
- [ ] All 5 steps pass
- [ ] Output shows weather data

### 4.2 Job Tracker Pipeline

- [ ] `python -m app.core.engine.sclpll_cli run examples/job_tracker_pipeline/script.sclpll`
- [ ] Parallel steps run concurrently (check timing overlap)
- [ ] Merge step waits for all dependencies

### 4.3 Financial Pipeline

- [ ] `python -m app.core.engine.sclpll_cli run examples/financial_pipeline/script.sclpll`
- [ ] BTC and ETH prices fetched in parallel
- [ ] Report generated

### 4.4 Advanced Logic

- [ ] `python -m app.core.engine.sclpll_cli run examples/advanced_logic/script.sclpll`
- [ ] Loops execute correct number of times
- [ ] Conditional steps skip when condition is false
- [ ] Semaphore limits concurrency

---

## Test Suite 5: Edge Cases

### 5.1 Error Handling

- [ ] Invalid SCLPLL shows line number and error message
- [ ] Missing function shows "Function not found" with function name
- [ ] Network timeout handled gracefully (no crash)
- [ ] Invalid JSON in response handled (no crash)

### 5.2 Performance

- [ ] Parallel steps run concurrently (verify with timing — should overlap, not serialize)
- [ ] Large workflows (10+ steps) complete without error
- [ ] Multiple rapid requests don't crash the server

### 5.3 Data Persistence

- [ ] Run a workflow, quit TUI, relaunch — history preserved
- [ ] Create an environment, quit, relaunch — environment preserved
- [ ] Export data, delete database, import — data restored

---

## Test Suite 6: Cross-Platform

### 6.1 Windows

- [ ] TUI renders correctly in Windows Terminal
- [ ] Unicode characters display (logo, status indicators)
- [ ] Paths with spaces work

### 6.2 macOS / Linux

- [ ] TUI renders correctly in Terminal.app / GNOME Terminal
- [ ] All examples run without modification

---

## Sign-off

| Field | Value |
|-------|-------|
| Tester | |
| Date | |
| Python Version | |
| OS | |
| Result | PASS / FAIL |
| Notes | |
