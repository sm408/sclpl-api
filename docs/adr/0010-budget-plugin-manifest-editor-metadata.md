# ADR 0010: Allow safe editor metadata in `ext`

## Decision

Increase the `sclpl/ext` code budget from 700 to 710 lines.

## Rationale

Plugin manifests now carry optional callable signatures and parameter names. This lets
the separately released SCLPLL language server provide completion and signature help
without importing or executing third-party plugin code. The ten-line increase is a
bounded security and editor-integration cost; no runtime execution behavior changes.
