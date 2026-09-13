# Known Limitations

The core workflow runner is complete, but a few capabilities remain deliberately out of scope
for the current release:

- `use` does not invoke another workflow; it raises a named error.
- Process-lane table transfer is pickle-backed rather than Arrow IPC zero-copy transfer.
- Lane selection does not yet learn from previous run history.
- `--http-cache` stores validators but does not yet perform conditional revalidation requests.
- Large fan-out runs currently report one progress row per iteration.
- On Windows, a graceful `CTRL_BREAK_EVENT` (the only console control event that can
  target a process outside the sender's own group) is not recognized as an interrupt:
  Python does not auto-raise `KeyboardInterrupt` for the underlying `SIGBREAK` the way
  it does for `SIGINT`, so it currently reaches the OS's own unhandled-signal
  termination instead of `sclpl`'s normal cleanup-and-`EXIT_INTERRUPTED` path. A local
  Ctrl-C (`SIGINT`/`CTRL_C_EVENT` in the same console) is unaffected.

These are explicit follow-up areas, not silent stubs. Behaviour that is advertised by `--help`,
the README, or the generated reference is implemented and covered by tests.

