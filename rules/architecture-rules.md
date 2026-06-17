# Architecture Rules

- Keep `ui -> services -> core -> storage` directional boundaries intact.
- Treat workflow runtime, function contracts, and export contracts as first-class architecture, not side utilities.
- Prefer graph-capable internals even when the visible UI is simpler.
- Do not let plugins or functions depend on undocumented internals.

