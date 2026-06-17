# PLUGIN_SDK.md

## Purpose

Plugins are the larger-grain extensibility layer above single Python functions.

## Plugin philosophy

Plugins should stay:

- discoverable
- understandable
- lightweight
- explicit about what they extend

SCLPLAPI should not become a dependency maze or app-store-style ecosystem.

## Expected extension points

- exporters
- auth systems
- workflow nodes
- analytics modules
- transformers
- UI panels
- event subscribers

## Plugin model

Each plugin should eventually declare:

- identity
- version
- compatible runtime range
- capabilities
- config schema
- lifecycle hooks

## Lifecycle expectations

- discover
- validate
- register
- activate
- deactivate
- unload

## Compatibility rules

- plugin contracts are versioned
- breaking capability changes require migration notes
- plugins must prefer documented extension points over internal imports

