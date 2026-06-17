# API Contracts

SCLPLAPI relies on explicit contracts between UI, services, core runtime, storage, plugins, and functions.

## Core contracts

- request definition contract
- environment and variable resolution contract
- workflow node contract
- execution context contract
- export job contract

## Rules

- boundaries are typed and versioned
- boundary validation happens at system edges
- core models remain UI-agnostic
- plugins and functions use stable public context objects only
- storage schemas do not leak directly into UI-facing contracts

## Required contract families

### Request definitions

- method
- URL template
- headers
- auth strategy reference
- body strategy
- timeout and retry policy

### Workflow nodes

- node id
- node type
- declared inputs
- declared outputs
- failure behavior
- execution policy

### Function/plugin execution

- context object
- input payload
- structured result
- typed error channel

## Enforcement

- document contracts before implementation
- preserve backward compatibility where feasible
- route breaking changes through ADRs

Primary references:

- `ARCHITECTURE.md`
- `FUNCTION_SYSTEM.md`
- `PLUGIN_SDK.md`
- `WORKFLOW_ENGINE.md`
