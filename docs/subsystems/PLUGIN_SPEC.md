# Plugin Spec

This document defines the stable plugin-facing surface for SCLPLAPI.

## A plugin may provide

- request helpers
- variable providers
- transformers
- exporters
- workflow nodes

## A plugin must provide

- manifest metadata
- declared capabilities
- versioned compatibility information
- a predictable entrypoint

## Hard rules

- plugins do not import internal core modules directly
- plugins operate through public contracts only
- plugin errors are isolated and reported clearly

Primary references:

- `PLUGIN_SDK.md`
- `PLUGIN_REGISTRY.md`
- `API_CONTRACTS.md`
