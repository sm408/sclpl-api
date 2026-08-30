# `render/`

Budget 1,300. Everything the user sees, and nothing else writes to a terminal.

| File | Job |
|---|---|
| `events.py` | Nine event types plus the verbosity policy |
| `reporter.py` | The single-writer queue, fan-out, redaction |
| `term.py` | Capability probe, the descend-only ladder, triple restore |
| `live.py` | The live region — DECSTBM scroll region, bars, spinners |
| `human.py` | The default sink: step rows, aggregate bar, instrument line |
| `plain.py` | One line per event, no escapes |
| `jsonl.py` | NDJSON events on stderr |
| `redact.py` | Secret redaction, applied in the reporter |

The design and its two hard-won bug fixes are in [[The Terminal Layer]].

`HumanSink.descend()` is the ladder's only live implementation; the reporter calls it
when a sink raises. Any new sink must keep that contract: a write failure descends one
rung, never climbs, never goes silent.
