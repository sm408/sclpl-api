# Workflow Glossary

| Term | Meaning |
|---|---|
| Binding | A named typed value produced by a step and available as `@step_id`. |
| Body | The indented lines beneath a step or control-flow construct. |
| Cache | Stored step output reused when its inputs and policy still match. |
| Catalogue | The local registry used to import, list, show, remove, and resolve workflows, functions, and plugins. |
| Control flow | A step that expands or selects other steps: `foreach`, `when`, loops, `parallel`, or `gate`. |
| DAG | The directed acyclic graph of workflow dependencies. |
| Dependency | A value or step that must be available before another step can start. References infer these automatically. |
| Expression | A parsed value or computation such as `@orders.body.data` or `count(@rows)`. |
| Function | A registered transformation, assertion, reader, writer, or utility call. |
| Input port | A named file supplied by the caller. |
| Lane | The execution placement for a step: async event loop, thread, process, or serial. |
| Mode | A validated partial workflow that removes steps and may override scalar limits. |
| Output port | A named file declared by the workflow and bound to a caller-provided path. |
| Pagination | Repeated HTTP requests merged into one logical response. |
| Plugin | Trusted, capability-declared code that contributes functions, connectors, operators, or backends. |
| Preflight | Validation performed before network or output work begins. |
| Reference | The `@name` syntax used to read values and infer dependencies. |
| Run | One execution, recorded in local SQLite history and an NDJSON event log. |
| SCLPLL | The hand-written, line-oriented workflow language. |
| Table | A typed record collection backed by the optional data backend. |
| Typed value | A Python object preserved between steps rather than stringified. |
| Value store | The runtime store that tracks bindings, lifetimes, spilling, and rehydration. |
| Workflow | A file describing inputs, requests, transformations, checks, control flow, and outputs. |

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful run |
| 1 | A step failed |
| 2 | Invalid command-line usage |
| 3 | Preflight rejected the workflow; nothing ran |
| 4 | An assertion found invalid data |
| 5 | Offline mode had a cache miss |
| 6 | Workflow was not found |

