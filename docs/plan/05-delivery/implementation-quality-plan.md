# Web Studio Delivery And Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking and each task ends in an independently reviewable result.

**Goal:** Implement and release the complete SCLPLAPI local web studio specified by the sibling planning documents.

**Architecture:** Build project-aware Python services and a versioned FastAPI boundary first, then deliver the Vue shell and feature slices against the stable gateway. Each slice includes backend, frontend, migration/contract changes, tests, and documentation rather than leaving integration to the end.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, SQLite/aiosqlite, Vue 3.5, TypeScript, Vite, PrimeVue unstyled, Vue Flow, Monaco, TanStack Vue Query, Pinia, pytest, Vitest, Playwright.

## Global Constraints

- Follow every locked decision and global constraint in `docs/plan/README.md`.
- Preserve unrelated user changes and keep the existing CLI/TUI operational after every task.
- Use schema migrations with backup and rollback; never rewrite an existing database ad hoc.
- Add dependencies only for an identified requirement and record license/version in the inventory.
- No feature is complete without loading, empty, error, conflict, keyboard, and project-isolation coverage.
- Use small reviewable commits following the suggested commit boundary for each task.

---

## Task 1: Project Domain And Migration

**Files:** modify `app/storage/db.py`, add the next numbered migration, add project model/repository/service modules, and add focused project/migration tests.

**Produces:** `Project`, project-aware repository contracts, Default project resolution, managed project roots, revision columns, and transactional migration from all supported schemas.

- [ ] Add failing migration tests using fixture databases for empty, populated, orphan-sensitive, and interrupted cases; assert backup, row counts, foreign keys, indexes, Default project, and rollback.
- [ ] Add failing service tests proving same IDs/names can exist in separate projects where allowed and wrong-project reads return no resource.
- [ ] Implement the project migration and repository/service operations without moving Default project files.
- [ ] Thread `project_id` through existing collection, request, environment, history, workflow, monitor, plugin, export, and import services.
- [ ] Update CLI/TUI construction to resolve Default project when no explicit project is supplied, preserving current commands.
- [ ] Run `pytest tests/test_database.py tests/test_projects.py tests/test_full_export.py tests/test_tui*.py -v` and the full suite.
- [ ] Commit as `feat: add project-scoped workspace model`.

## Task 2: FastAPI Foundation And Contract

**Files:** create `app/web/server.py`, `app/web/api/`, DTO/error modules, API tests, and deterministic OpenAPI generation tooling.

**Produces:** application factory, lifecycle, `/health`, `/api/v1/projects`, common errors/pagination, security headers, same-origin policy, static fallback contract, and generated OpenAPI artifact.

- [ ] Write API tests for lifecycle, health, projects, camelCase aliases, errors, validation, host/origin rejection, SPA fallback exclusions, and shutdown.
- [ ] Implement dependency injection for the existing application/service container; route handlers may not instantiate databases or engines.
- [ ] Implement common correlation ID, exception translation, pagination DTOs, response headers, and loopback validation.
- [ ] Add OpenAPI generation and snapshot comparison with stable ordering.
- [ ] Run targeted API tests, `ruff check app tests`, and the full Python suite.
- [ ] Commit as `feat: establish versioned web API`.

## Task 3: Operations And Event Streaming

**Files:** add operation registry/service, SSE router/serializer, cancellation integration, and event tests.

**Produces:** revisioned `ExecutionOperation`, bounded per-project replay, typed event envelopes, heartbeat, reconnect/reset behavior, and idempotent cancellation.

- [ ] Test state transitions, illegal transitions, project isolation, cancellation races, replay, duplicate IDs, sequence gaps, heartbeat, and redaction.
- [ ] Adapt the existing event bus into explicit public event schemas; do not stream arbitrary internal event dictionaries.
- [ ] Implement operation retention and artifact cleanup settings with bounded memory/disk behavior.
- [ ] Run concurrency tests repeatedly and verify shutdown cancels or drains tasks according to operation type.
- [ ] Commit as `feat: add observable background operations`.

## Task 4: Vue Workspace And Gateway

**Files:** create `web/`, frontend build configuration, generated API types, gateway contracts/adapters, test harness, and Python package asset configuration.

**Produces:** mock and HTTP modes, typed gateway, no-direct-fetch lint boundary, local asset build, and FastAPI static serving.

- [ ] Scaffold Vue/TypeScript/Vite with pnpm and record all dependency licenses.
- [ ] Define gateway interfaces and deterministic mock fixtures for every resource family and operation state.
- [ ] Implement HTTP normalization, abort handling, `StudioError`, and SSE subscription/reconnect.
- [ ] Add type-generation drift check and tests demonstrating identical feature behavior through mock and HTTP adapters.
- [ ] Build the SPA, package it in a wheel, install the wheel in a clean environment, and verify `sclplapi web` serves it.
- [ ] Commit as `feat: add decoupled Vue web workspace`.

## Task 5: Design System And Application Shell

**Files:** add design tokens/primitives, shell, router, workbench, commands, project feature, and accessibility tests under `web/src/`.

**Produces:** themes, density, activity rail, explorer host, top bar, tabs, inspector/activity panels, command palette, project switching, responsive layouts, and error/disconnection boundaries.

- [ ] Implement token stories/tests for dark, light, high contrast, compact, comfortable, reduced motion, and 200% zoom.
- [ ] Build keyboard-complete rail, tree, tabs, resizers, dialogs, menus, notifications, and command palette from PrimeVue unstyled behavior.
- [ ] Implement typed routes, deep-link resolution, tab restoration, dirty draft registry, close review, and project switch review.
- [ ] Add Home with mock/query-driven operational sections and genuine empty/error states.
- [ ] Run Vitest, axe checks, Playwright shell journeys, and screenshot review at required breakpoints/themes.
- [ ] Commit as `feat: build web studio shell and design system`.

## Task 6: Requests, Collections, Environments, And History

**Files:** extend corresponding Python services/API routers and implement the four frontend feature modules with shared key-value and response components.

**Produces:** the first complete execution slice from persisted request through environment resolution, send/cancel, response, history, rerun, and collection management.

- [ ] Add API contract tests for ordered duplicate headers/params, masked secrets, revisions, execution snapshots, cancellation, pagination, collection moves, and history retention preview/apply.
- [ ] Implement structured request DTO conversion at service boundaries rather than passing database JSON strings to the UI.
- [ ] Implement request editor drafts, variable highlighting, auth/body modes supported by the engine, Save/Save as, and response viewer.
- [ ] Implement environment activation and secret semantics, collection tree CRUD/move/duplicate, and Runs request-history detail/rerun.
- [ ] Add browser journeys for unsaved send, saved send, timeout, network failure, stale revision, environment switch with dirty tabs, and secret non-disclosure.
- [ ] Commit as `feat: deliver request execution workspace`.

## Task 7: Workflow Persistence, Compiler Contract, And Versions

**Files:** add workflow repository/service/API, extend models/migration for layout/revisions/version metadata, and strengthen compiler tests.

**Produces:** canonical WorkflowDocument, authoritative validation, SCLPLL parse result, structural diff, compatibility losses, immutable versions, conflict detection, and execution operations.

- [ ] Write property-based round-trip tests for every SCLPLL-representable field and explicit loss tests for non-representable fields.
- [ ] Implement definition/layout separation, deterministic SCLPLL generation, source diagnostics, preflight validation, version save/compare/restore, and revision conflict payloads.
- [ ] Expose execution snapshots and typed per-step events without changing running data when a workflow is edited.
- [ ] Verify imports/exports preserve new workflow/version data and old exports migrate safely.
- [ ] Commit as `feat: define canonical workflow document contract`.

## Task 8: Visual Workflow Studio

**Files:** implement workflow feature, Vue Flow wrappers/nodes, outline, inspector, source/versions/run modes, and graph tests under `web/src/features/workflows/`.

**Produces:** full visual and keyboard workflow authoring with safe source application and live execution inspection.

- [ ] Implement pure definition/layout projection and semantic command reducer with inverse commands and bounded undo.
- [ ] Build palette, canvas nodes/edges, cycle feedback, minimap/controls, selection, copy/paste, grouping, alignment, and undoable auto-layout.
- [ ] Build the complete outline editor and prove command equivalence with canvas operations.
- [ ] Integrate Monaco Source states, diagnostics, structural preview, warning/loss acknowledgement, and Apply.
- [ ] Implement Versions and Run views with SSE state, cancellation, attempt/output inspection, and historical overlays.
- [ ] Test 500-node performance, keyboard-only creation/run, source loss prevention, disjoint/overlapping conflict, and reconnect sequence gaps.
- [ ] Commit as `feat: deliver visual workflow studio`.

## Task 9: Functions And Plugins

**Files:** add constrained file services/API, extend registry services, and implement Functions/Extensions features.

**Produces:** project file trees, content-hash writes, AST validation, Monaco Python editing, fixture execution, plugin scaffold/edit/enable/reload/export, and trust acknowledgements.

- [ ] Test traversal, absolute paths, Windows reserved names, symlink/junction escape, stale hash, atomic replace, size limit, invalid AST, and cross-project access.
- [ ] Implement project-root-aware discovery and registry reload while preserving existing Default project behavior.
- [ ] Build function tree/editor/metadata/validation/test-run and plugin list/detail/scaffold/manifest/diagnostics.
- [ ] Prove secret/source content is excluded from diagnostics and trust acknowledgement is invalidated when content hash changes.
- [ ] Commit as `feat: add web function and plugin workbenches`.

## Task 10: Monitors And Operational Runs

**Files:** extend monitor services/API/events and implement monitor list/editor/detail, charts, events, and compare integration.

**Produces:** monitor CRUD/start/stop/run-once, validated conditions, health summaries, event pagination, response inspection, chart/table alternatives, and bulk outcomes.

- [ ] Test project scoping, state transitions, invalid conditions, background behavior after UI disconnect, event retention, bulk partial failure, and redaction.
- [ ] Build monitor forms, status list, timeline, duration/status charts with accessible tables, event detail, body compare, clear, and export.
- [ ] Add browser journeys for trigger, failure, stop race, disconnect/reconnect, and event comparison.
- [ ] Commit as `feat: deliver monitor operations workspace`.

## Task 11: Batch And Transfer Center

**Files:** extend batch/import/export services and APIs; implement batch and transfer features with upload/download handling.

**Produces:** CSV validation/mapping/sequential execution/cancellation/retry/export and preview-token-based import/export/OpenAPI workflows.

- [ ] Test encoding, duplicate/empty headers, row/size limits, cancellation with partial results, retry lineage, import token expiry/tampering, conflict policies, rollback, and code trust warnings.
- [ ] Implement server-owned artifacts and downloads; never accept arbitrary output paths from the browser.
- [ ] Build CSV preview/mapping/progress/results and Transfer Center preview/diff/conflict/apply/result journeys.
- [ ] Rehearse full export from pre-project schema and restore into a clean current schema.
- [ ] Commit as `feat: add batch and transfer workflows`.

## Task 12: Compare, Logs, Settings, And Parity Closure

**Files:** implement remaining contextual editors/features, settings API expansion, command registrations, and parity tests/documentation.

**Produces:** Monaco/structured compare, log panel/export, settings, license view, keyboard help, updater status where safely supported, and every traceability row closed.

- [ ] Add compare size/type fallbacks and ensure HTML/binary content cannot execute.
- [ ] Add log filtering/pause/copy/redacted export and distinguish clear-view from persistent deletion.
- [ ] Implement appearance/editor/history/startup settings with restart-required messaging.
- [ ] Generate command help from the command registry and dependency licenses from the lockfile.
- [ ] Execute the parity matrix against the TUI/CLI capability inventory and file issues for no missing behavior; blockers must be resolved before release.
- [ ] Commit as `feat: complete web studio feature parity`.

## Task 13: Hardening, Packaging, And Release

**Files:** CI workflows/configuration, packaging metadata, startup scripts, user docs, performance/accessibility reports, and release notes.

**Produces:** reproducible release artifact with verified migration, offline operation, accessibility, performance, and clean installation.

- [ ] Run full Python, frontend unit, integration, E2E, axe, type, lint, contract drift, migration, and package-install suites on Windows, Linux, and macOS.
- [ ] Enforce shell bundle below 250KB gzip excluding lazy chunks, cold interaction below two seconds on the reference machine, local list reads below 150ms p95, saves below 300ms p95, and responsive 500-node canvas interaction.
- [ ] Manually verify NVDA/Firefox, VoiceOver/Safari, Windows high contrast, reduced motion, keyboard-only workflows, 200% zoom, and narrow operational journeys.
- [ ] Verify no runtime network dependency, secret leakage, path escape, source-map serving, database corruption, or remote binding.
- [ ] Install the built wheel into a clean Python environment, run migration against a copy of real pre-release data, launch `sclplapi web`, complete smoke journeys, and uninstall cleanly.
- [ ] Publish release notes covering migration backup, trusted-code model, browser support, known limits, and rollback.
- [ ] Commit as `release: prepare web studio v1`.

## Continuous Quality Gates

Every pull request must pass relevant Python tests, frontend typecheck/lint/unit tests, API type drift, and focused Playwright journeys. Changes to shared shell, gateway, project scoping, workflow document, secrets, operations, or migrations require the full integration suite.

Code review must explicitly check ownership boundaries, project filtering, revision behavior, cancellation, redaction, keyboard access, loading/error states, and dependency/license changes. Screenshot approval never substitutes for interaction and accessibility verification.

## Release Acceptance

- All tasks above are complete with no skipped acceptance criteria.
- `docs/plan/README.md` traceability has no uncovered capability.
- All planning documents match shipped names, routes, contracts, and behavior.
- Zero critical/high security findings and zero critical accessibility findings remain.
- Migration backup and rollback instructions are exercised, not merely documented.
- The Default project preserves existing CLI/TUI data and workflows.
- Mock mode supports productive frontend development without Python.
- HTTP mode and packaged static mode pass identical core browser journeys.

