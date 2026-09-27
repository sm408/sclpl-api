# Known Limitations

The core workflow runner is complete, but a few capabilities remain deliberately out of scope
for the current release:

- `use` does not invoke another workflow; it raises a named error.
- Process-lane table transfer is pickle-backed rather than Arrow IPC zero-copy transfer.
- Lane selection does not yet learn from previous run history.
- `--http-cache` stores validators but does not yet perform conditional revalidation requests.
- Large fan-out runs currently report one progress row per iteration.

These are explicit follow-up areas, not silent stubs. Behaviour that is advertised by `--help`,
the README, or the generated reference is implemented and covered by tests.

