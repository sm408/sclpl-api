# SCLPLAPI Web Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Track work through the checklists in `05-delivery/implementation-quality-plan.md`.

**Goal:** Deliver a polished, local-first Vue web studio with complete functional parity with the existing Textual interface, a visual workflow builder, project isolation, and a stable boundary around the Python engine.

**Architecture:** A Vue single-page application communicates only through a typed gateway. In production that gateway calls a versioned FastAPI REST and SSE interface; in development it can use deterministic mocks. Python services remain the sole owners of persistence, filesystem access, HTTP execution, workflows, plugins, functions, monitors, imports, and exports.

**Tech Stack:** Vue 3.5, TypeScript, Vite, Vue Router, Pinia, TanStack Vue Query, PrimeVue unstyled primitives, Vue Flow, Monaco Editor, FastAPI, Pydantic, SQLite, Vitest, Playwright, pytest.

## Global Constraints

- The production server binds to loopback and assumes one trusted local user.
- The CLI and Textual UI remain supported and use the same project-aware services.
- All current TUI work areas must have functional web equivalents before v1 release.
- Workflow definition JSON is canonical; graph layout is separate and SCLPLL changes use explicit parse, preview, and apply steps.
- Browser code cannot directly access SQLite, arbitrary filesystem paths, Python modules, or secrets.
- All production frontend packages must use permissive open-source licenses and be recorded in the dependency inventory.
- No runtime CDN is allowed; fonts, icons, workers, and application assets ship locally.
- The interface meets WCAG 2.2 AA and provides non-canvas keyboard access to every workflow operation.
- Generated files, migrations, API contracts, tests, and user documentation ship with the feature that requires them.

---

## 1. Product Position

SCLPLAPI is a programmable API workbench for developers and technical operators who need to build, inspect, automate, and monitor HTTP workflows without surrendering control of data or Python execution to a hosted service. The web studio is not a decorative wrapper around the TUI. It is the primary visual workbench while the CLI and TUI remain efficient alternate clients.

The product has four defining properties:

1. **Local authority:** data and execution stay on the user's machine.
2. **Two authoring modes:** structured visual authoring and explicit SCLPLL/Python source editing.
3. **Inspectable execution:** requests, dependencies, variables, retries, output, and failures remain visible.
4. **Python extensibility:** functions and plugins are first-class project resources rather than hidden configuration.

## 2. Locked Decisions

| Area | Decision | Consequence |
|---|---|---|
| Delivery | Local browser application started by `sclplapi web` | Cross-platform delivery without a desktop runtime in v1 |
| User model | Single trusted local user | No accounts, roles, remote collaboration, or cloud synchronization |
| Release scope | Complete current TUI parity | All areas are implemented, tested, and documented before v1 |
| Workspace model | Project-scoped resources | Existing data migrates into a protected Default project |
| Workflow truth | Typed `WorkflowDef` JSON | Canvas and outline edit JSON; SCLPLL applies only after validation |
| Visual direction | Technical dark-first | Dense graphite workbench with indigo/cyan execution accents and full light theme |
| Transport | REST for state and commands; SSE for events | Simple reconnectable one-way progress stream; cancellation remains REST |
| Frontend state | Query cache for server state; Pinia for UI state | No duplicated resource stores or implicit background saves |
| Component strategy | PrimeVue unstyled plus SCLPLAPI tokens | Accessible behavior without inheriting a generic theme |
| Security | Loopback, same-origin, trusted local code | Strict path constraints and secret masking still apply |

Changes to these decisions require an ADR-style entry in this document recording date, reason, alternatives, migration impact, and approver.

## 3. Document Map

| Document | Owns | Must not redefine |
|---|---|---|
| `01-product/product-ux-specification.md` | Audience, information architecture, journeys, UX states, language | API wire shapes or database schema |
| `02-design/design-system-and-interactions.md` | Tokens, layout, components, motion, responsive and accessible interaction | Business rules |
| `03-architecture/frontend-architecture.md` | Vue boundaries, routes, state, gateway, drafts, build | Backend implementation details |
| `03-architecture/api-data-and-security.md` | REST/SSE contracts, project schema, revisions, files, secrets | Screen composition |
| `03-architecture/workflow-studio.md` | Workflow representation, canvas mapping, SCLPLL synchronization, execution display | General request editing |
| `04-features/functional-specifications.md` | Complete behavior by work area | Shared token values or transport mechanics |
| `05-delivery/implementation-quality-plan.md` | Task order, tests, budgets, packaging, release gates | Product decisions already locked above |

## 4. Scope Traceability

| Existing capability | Web destination | Primary specification |
|---|---|---|
| Request editor and response viewer | Requests workbench | Functional specifications |
| Collections and saved requests | Requests explorer | Product UX and functional specifications |
| History and rerun | Runs | Functional specifications |
| Workflow listing and execution | Workflow Studio | Workflow Studio specification |
| Environments and variables | Project environment selector and Environments editor | API/data and functional specifications |
| Function source browser | Functions workbench | Functional specifications and security |
| Plugin browser and scaffold/reload | Extensions | Functional specifications and security |
| Live monitors and monitor events | Monitors | Functional specifications |
| CSV batch execution | Batch tool | Functional specifications |
| Import/export and OpenAPI import | Transfer Center | Functional specifications |
| Response diff | Contextual Compare editor | Functional specifications |
| Logs | Bottom activity panel and Runs | Product UX and API/SSE specifications |
| Settings, commands, shortcuts | Settings and command palette | Design and frontend architecture |

## 5. Open-Source Dependency Policy

The implementation begins with the researched baseline below. Exact versions are locked once compatibility tests pass; upgrades require the normal dependency review.

| Package | Role | Baseline | License expectation |
|---|---|---:|---|
| Vue | Component runtime | 3.5.x | MIT |
| Vue Router | Routing and deep links | compatible stable | MIT |
| Pinia | Shell and draft registry state | 3.0.x | MIT |
| TanStack Vue Query | Server cache and mutations | 5.x | MIT |
| PrimeVue | Accessible unstyled primitives | 4.5.x | MIT |
| Vue Flow | Workflow graph interaction | 1.48.x | MIT |
| Monaco Editor | Code, JSON, and diff editing | 0.55.x | MIT |
| Lucide | Interface icons | compatible stable | ISC |
| Apache ECharts | Monitor and run charts | 6.x or compatible stable | Apache-2.0 |
| IBM Plex Sans/Mono | Product typography | locally bundled | SIL OFL-1.1 |
| Vitest / Vue Test Utils | Component and unit tests | compatible stable | MIT |
| Playwright | Browser journeys | compatible stable | Apache-2.0 |
| axe-core | Automated accessibility checks | compatible stable | MPL-2.0 |

Do not add a second component library, state manager, graph package, editor, icon family, or charting package without documenting why the existing dependency cannot satisfy the requirement. Premium templates, hosted design systems, telemetry SDKs, and copyleft runtime dependencies are excluded by default.

## 6. Definition Of Done

The web studio is complete only when:

- `sclplapi web` starts the application, opens a browser when configured, serves hashed assets, and shuts down services cleanly.
- Existing databases migrate into the Default project without data loss and can be backed up before migration.
- Every row in the scope traceability table has an operable web journey rather than a static placeholder.
- A frontend-only developer can run the UI against mock data without installing or starting Python.
- A backend-only developer can validate the OpenAPI contract and SSE events without running a browser.
- All destructive actions name the affected resource, explain impact, and require confirmation appropriate to reversibility.
- Secrets never appear in API responses, browser storage, logs, exports without explicit secret inclusion, or screenshots used by tests.
- Keyboard-only and screen-reader users can create, edit, validate, and run workflows through the outline editor.
- Performance and accessibility budgets in the delivery plan pass in CI.
- The documentation describes actual shipped behavior and contains no `TBD`, `TODO`, or unowned future decisions.

