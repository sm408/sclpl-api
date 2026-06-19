# ADR-009: TUI over GUI

## Status

Accepted

## Decision

Build a terminal UI using Rich, not a graphical UI.

## Rationale

Aligns with local-first principles. No Electron dependency. Works in any terminal. Rich rendering mitigates the visual limitations of terminal output.
