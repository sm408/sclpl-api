# SCLPLAPI Cheatsheet

> Quick reference for SCLPLAPI.

---

## Launch

```bash
python -m app                    # Launch Textual TUI
python -m app --legacy-tui       # Launch legacy Rich TUI
python -m app --setup            # Run setup wizard
python -m app --reset            # Reset settings
```

---

## SCLPLL Commands

```bash
python -m app.core.engine.sclpll_cli run script.sclpll       # Run workflow
python -m app.core.engine.sclpll_cli compile script.sclpll   # Compile to JSON
python -m app.core.engine.sclpll_cli validate script.sclpll  # Check syntax
python -m app.core.engine.sclpll_cli decompile workflow.json  # Back to .sclpll
```

---

## TUI Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+P | Command Palette |
| Ctrl+T | New Request |
| Ctrl+R | Run Request |
| Ctrl+W | Close Tab |
| Ctrl+B | Batch Mode |
| Ctrl+M | Monitors |
| F1 | Help |
| F2 | Toggle Theme |
| F5 | Refresh |
| Esc | Cancel |

---

## SCLPLL Syntax

```sclpll
@workflow id "Name"              # Define workflow
@base_url https://api.example.com  # Set base URL
@var key = value                 # Define variable

@step id -> var                  # HTTP request step
    request GET {{base_url}}/path

@step id <- dep1, dep2 -> var   # Function step with dependencies
    func Function Name

@step id -> var                  # POST with body
    request POST {{base_url}}/path
    header Content-Type application/json
    body {"key": "value"}
```

---

## Monitor Conditions

```
status == 200                    # Check status code
body.price > 100                 # Check JSON field
body.status == "active"          # Check string value
body.items.length > 0            # Check array length
```

---

## Testing

```bash
pytest tests/ -v                 # All tests
pytest tests/test_textual_tui.py -v  # TUI tests
```
