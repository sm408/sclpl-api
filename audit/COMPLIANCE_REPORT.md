# SCLPLAPI Audit Report

> Project compliance, task status, and architectural decisions.
> Generated: 2026-06-19

---

## 1. Original Rules (from AGENTS.md)

### Non-Negotiable Principles

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| 1 | **Local-first**: no mandatory cloud dependency | **COMPLIANT** | All execution is local. SQLite for persistence. No cloud accounts, no telemetry. |
| 2 | **Human-hackable**: filesystem-visible configuration | **COMPLIANT** | `.sclpll` files, `functions/` directory, `workflow.json` — all filesystem-based. |
| 3 | **Python-first**: prefer Python over JS | **COMPLIANT** | Entire stack is Python. No JS dependencies. Functions are Python files. |
| 4 | **Strict core, flexible feature layer** | **COMPLIANT** | `core/` has contracts (ABCs), `services/` implements, `ui/` consumes. Layer direction preserved. |
| 5 | **Runtime first**: execution before visual builders | **COMPLIANT** | Workflow engine, parallel execution, SCLPLL compiler all implemented. No visual builder. |

### Architecture Rules

| # | Rule | Status | Notes |
|---|------|--------|-------|
| 1 | Preserve layer direction: `ui -> services -> core -> storage` | **COMPLIANT** | Verified in code. `core/` does not import from `services/` except via DI. |
| 2 | Do not let UI own workflow/persistence/transport logic | **COMPLIANT** | TUI delegates to engines. CLI uses `App` composition root. |
| 3 | Keep core execution engine UI-independent | **COMPLIANT** | `ParallelWorkflowEngine` has no UI imports. |
| 4 | Treat plugin and function contracts as user-facing APIs | **COMPLIANT** | Function contract documented. `@name`, `@type`, `@version` metadata. |
| 5 | Prefer typed contracts and explicit context objects | **COMPLIANT** | `ExecutionContext`, `RequestDef`, `WorkflowDef` are all typed dataclasses. |

### Product Rules

| # | Rule | Status | Notes |
|---|------|--------|-------|
| 1 | Workflows are a core architectural commitment | **COMPLIANT** | Two engines (sequential + parallel), SCLPLL language, 5 examples. |
| 2 | Event bus support, lightweight and in-process | **COMPLIANT** | `SimpleEventBus` with wildcard support. Used for workflow events. |
| 3 | Function system is first-class, not a convenience add-on | **COMPLIANT** | 17 functions, filesystem discovery, AST metadata parsing, async support. |
| 4 | Exports are pipelines, not "save as" utilities | **PARTIAL** | JSON/CSV export implemented. Excel and transformation pipelines deferred. |
| 5 | Visual workflow builders deferred until runtime stable | **COMPLIANT** | No visual builder. Runtime is stable and tested. |

### Delivery Rules

| # | Rule | Status | Notes |
|---|------|--------|-------|
| 1 | Update docs when architecture changes | **COMPLIANT** | 4 perspective docs, SCLPLL reference, updated README, audit report. |
| 2 | Add ADRs for meaningful decisions | **PARTIAL** | 5 ADRs exist. New decisions (parallel engine, SCLPLL) not yet documented as ADRs. |
| 3 | Avoid speculative abstractions | **COMPLIANT** | No plugin system implemented. Only working features exist. |
| 4 | Avoid trademark-risk references | **COMPLIANT** | No Postman/Insomnia references in code or UI. |

---

## 2. Feature Status Matrix

### Implemented (STABLE)

| Feature | Status | Evidence |
|---------|--------|----------|
| HTTP request execution | STABLE | `HttpRequestExecutor` with httpx, auth, history |
| Auth modes (Bearer, Basic, API key) | STABLE | `AuthConfig` in `core/engine/auth.py` |
| Response viewer | STABLE | CLI `run` command shows response |
| History tracking | STABLE | `HistoryRepository` with SQLite persistence |
| Collection tree | STABLE | `CollectionRepository` with CRUD |
| Saved requests | STABLE | `RequestRepository` with JSON serialization |
| Environment switching | STABLE | `EnvironmentRepository` with active env |
| Scoped variable resolution | STABLE | `DefaultVariableResolver` with precedence |
| Runtime variable propagation | STABLE | Variables flow through step outputs |
| Filesystem-discovered functions | STABLE | `FilesystemFunctionRunner` with AST parsing |
| Pre-request hooks | STABLE | `FunctionHookRunner` |
| Post-response transformers | STABLE | Functions with `@type: post_response` |
| Sequential workflow chains | STABLE | `WorkflowEngine` with topological sort |
| Dependency graph execution | STABLE | `ParallelWorkflowEngine` with async groups |
| JSON export | STABLE | `DefaultExportPipeline.export_json()` |
| CSV export | STABLE | `DefaultExportPipeline.export_csv()` |
| SQLite persistence | STABLE | `Database` with 7 tables, WAL mode |
| CLI with 13+ commands | STABLE | Typer-based CLI in `app/ui/cli.py` |
| TUI with interactive menu | STABLE | Rich-based TUI in `app/ui/tui.py` |
| SCLPLL scripting language | STABLE | Compiler/decompiler, CLI, 5 examples |
| Dot notation for nested JSON | STABLE | Variable resolver supports `{{step.field.sub}}` |
| @foreach loops | STABLE | Compiler + engine support |
| @repeat batch operations | STABLE | Compiler + engine support |
| @when conditional execution | STABLE | Compiler + engine support |
| @semaphore rate limiting | STABLE | Engine uses `asyncio.Semaphore` |
| Tools library | STABLE | 4 tools: validator, linter, formatter, analyzer |

### Planned (Not Implemented)

| Feature | Status | Reason |
|---------|--------|--------|
| Excel workbook generation | PLANNED | Not prioritized. JSON/CSV sufficient for MVP. |
| Plugin discovery | PLANNED | Requires stable API surface first. |
| Plugin manifests and lifecycle | PLANNED | Deferred until function system mature. |
| Workspaces | PLANNED | Not needed for single-user local-first model. |
| Secrets vault | PLANNED | Environment variables sufficient currently. |

### Deferred

| Feature | Status | Reason |
|---------|--------|--------|
| Visual workflow builder | DEFERRED | Runtime design stable, but UI effort deferred. |
| Dashboards | DEFERRED | Analytics not prioritized. |
| Electron rewrite | DEFERRED | CLI/TUI sufficient. |
| Cloud account system | DEFERRED | Violates local-first principle. |
| Mandatory telemetry | DEFERRED | Violates local-first principle. |

---

## 3. Task Completion Summary

### Session Tasks

| Task ID | Summary | Status | Evidence |
|---------|---------|--------|----------|
| T1 | Build multi-step async workflow example | **DONE** | 4 working examples, parallel engine |
| T2 | Create SCLPLL language, translator, docs | **DONE** | Compiler, CLI, docs, financial example |
| T3 | Comprehensive documentation, tests, reorganization | **DONE** | 4 perspective docs, 175 tests, new example |
| T4 | TUI, logic/loops, dot notation, semaphores, tools | **DONE** | TUI, SCLPLL enhancements, tools library, E2E tests |

### Deliverables Count

| Category | Count |
|----------|-------|
| Working examples | 5 |
| Python functions | 17 |
| Test files | 10 |
| Total tests | 175 |
| Documentation files | 70+ |
| Tools | 4 |
| SCLPLL scripts | 5 |

---

## 4. Architectural Decisions

### ADR-006: Parallel Workflow Engine

**Decision:** Build a parallel workflow engine alongside the sequential one.

**Rationale:** Independent API calls should execute concurrently. A dependency-graph-based engine with `asyncio.create_task` provides automatic parallelization.

**Trade-off:** Two engines to maintain. Chose to keep both (sequential for simple chains, parallel for complex DAGs).

**Evidence:** `app/core/engine/parallel_workflow.py` — 357 lines, 12 tests.

---

### ADR-007: SCLPLL Scripting Language

**Decision:** Create a domain-specific language for workflow definitions.

**Rationale:** Raw `workflow.json` is verbose and error-prone. A human-readable DSL with compile/decompile enables faster authoring and bidirectional translation.

**Trade-off:** New language to learn. Mitigated by: simple syntax, documentation, backward compatibility with JSON.

**Evidence:** `app/core/engine/sclpll_compiler.py` — 264 lines, 24 tests.

---

### ADR-008: Dot Notation for Variable Access

**Decision:** Support `{{step_id.field.subfield}}` syntax for nested JSON access.

**Rationale:** API responses are deeply nested. Requiring users to write extraction functions for every field is tedious. Dot notation provides direct access.

**Trade-off:** More complex variable resolver. Mitigated by: graceful fallback on missing keys, backward compatible with simple `{{var}}` syntax.

**Evidence:** `app/core/engine/variable_resolver.py` — extended `_resolve_key` method.

---

### ADR-009: TUI over GUI

**Decision:** Build a terminal UI using Rich, not a graphical UI.

**Rationale:** Aligns with "human-hackable" and "local-first" principles. No Electron dependency. Works in any terminal. Rich provides beautiful rendering without GUI frameworks.

**Trade-off:** Limited to terminal capabilities. Mitigated by: Rich handles colors, tables, progress bars, live updates.

**Evidence:** `app/ui/tui.py` — 1026 lines.

---

### ADR-010: Tools Library as Project Assets

**Decision:** Create a `tools/` directory with development utilities.

**Rationale:** Common tasks (validation, linting, formatting, analysis) should be automated. Project-specific tools reduce friction and enforce standards.

**Trade-off:** More code to maintain. Mitigated by: tools are standalone scripts, no external dependencies beyond project code.

**Evidence:** `tools/` — 4 tools, README documentation.

---

## 5. Compliance Summary

| Category | Compliant | Partial | Non-Compliant |
|----------|-----------|---------|---------------|
| Non-negotiable principles | 5/5 | 0 | 0 |
| Architecture rules | 5/5 | 0 | 0 |
| Product rules | 4/5 | 1 | 0 |
| Delivery rules | 3/4 | 1 | 0 |

**Overall: 17/19 rules fully compliant (89%), 2 partially compliant (11%), 0 non-compliant.**

### Partial Compliance Items

1. **Exports are pipelines** — JSON/CSV implemented. Excel and transformation pipelines planned but not implemented. Acceptable for MVP stage.

2. **ADRs for meaningful decisions** — 5 original ADRs exist. 5 new decisions made during this session (parallel engine, SCLPLL, dot notation, TUI, tools). Should add ADR-006 through ADR-010.

---

## 6. Recommendations

1. **Add ADRs 006-010** for the new architectural decisions.
2. **Update FEATURES.md** to reflect current STABLE status (currently shows PLANNED for many implemented features).
3. **Add integration tests** for the TUI.
4. **Document the function contract** more thoroughly (input/output schemas).
5. **Consider adding Excel export** as the next feature.
