---
name: sclplapi-security
description: Use when handling secrets, credential redaction, plugin safety boundaries, and export artifact sensitivity.
---

## Purpose

Maintain explicit security boundaries in a local-first tool. Handle secrets, credential redaction, plugin/function safety, and export sensitivity deliberately.

## When to use

- secret storage and masking
- credential redaction in logs/reports
- plugin and function safety boundaries
- export artifact sensitivity controls
- workspace sharing safety

## Rules

- secrets remain local by default
- credentials redacted in logs and reports unless explicitly exported
- plugins and functions operate within declared contracts
- dangerous operations require explicit user intent
- trusted local execution is the default posture

## Key files

- `docs/architecture/SECURITY_MODEL.md`
- `FUNCTION_SYSTEM.md`
- `PLUGIN_SDK.md`
- `requirements/non_functional_requirements.md`
