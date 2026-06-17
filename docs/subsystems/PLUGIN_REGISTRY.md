# Plugin Registry

The plugin registry tracks discoverable plugins available to a SCLPLAPI workspace.

## Registry responsibilities

- discover plugins
- validate plugin manifests
- expose enabled/disabled state
- coordinate loading boundaries

## Discovery sources

- local workspace plugin directories
- explicitly configured plugin paths

## Rules

- local-first discovery is the default
- plugin metadata loads before runtime activation
- invalid plugins fail closed with clear diagnostics
- plugin loading must not require core changes

Primary references:

- `PLUGIN_SDK.md`
- `PLUGINS.md`
