# Security Model

SCLPLAPI is a local-first developer tool, but it still needs explicit security boundaries.

## Threat areas

- secret handling
- arbitrary function execution
- plugin loading
- export artifacts containing sensitive data
- unsafe workspace sharing

## Security rules

- secrets remain local by default
- credentials are redacted in logs and reports unless explicitly exported
- plugins and functions operate within declared contracts
- dangerous operations require explicit user intent

## Practical posture

- favor transparency over obscure sandbox promises
- make secret usage visible
- provide safe defaults for exports and diagnostics

Primary references:

- `FUNCTION_SYSTEM.md`
- `PLUGIN_SDK.md`
- `EXPORT_ENGINE.md`
