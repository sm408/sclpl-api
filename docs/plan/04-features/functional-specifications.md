# Functional Specifications

## 1. Home And Projects

### Home

Home is an operational launch surface, not an analytics landing page. It shows recent editable resources, recent runs, running operations, monitor health, active environment, and contextual next actions. Cards use real project data and disappear when irrelevant. No vanity totals or decorative charts are permitted.

Actions: New request, New workflow, Import OpenAPI, Create project, Resume recent tab, Open failed run, and View triggered monitor. A new project shows guided empty-state actions. A failed summary query leaves other sections usable.

### Projects

Users can create, rename, describe, switch, export, and delete non-default projects. Project creation provisions managed directories and an empty database scope atomically. A provisioning failure removes partial directories or reports the retained recovery location.

Project switch behavior:

- Clean tabs from the old project close and are remembered for later restoration.
- Dirty tabs trigger a review listing Save, Discard, or Stay for each draft.
- Running operations continue and remain accessible after returning to the project.
- The selected environment, explorer state, tabs, and panel layout are remembered per project.
- Default project cannot be deleted. Deleting another project requires its exact name and shows counts plus filesystem impact.

## 2. Requests And Collections

### Explorer

The Requests explorer contains collections and their saved requests. It supports create, rename, duplicate, export, and delete collection; create, duplicate, move, rename, and delete request; search by name, URL, method, and collection; and method/status filters. Uncollected requests appear under a stable `Loose requests` group.

Deleting a non-empty collection requires choosing Delete contained requests or Move requests to Loose requests. Duplication deep-copies requests with new IDs and adds `Copy` naming deterministically.

### Request editor

The URL row contains method, URL, environment indicator, Send/Cancel, and Save. Structured tabs are Params, Headers, Body, Auth, Scripts/Hooks, and Settings.

- Params and Headers use the shared key-value editor and preserve order and duplicate entries.
- Body types: none, raw JSON, raw text, form URL encoded, and multipart when backend support is added in the same slice. Unsupported current engine modes are disabled with explanation rather than faked.
- Auth types initially match the engine: none, bearer, basic, and API key. Secret values are masked and omitted from loaded DTOs.
- Settings expose timeout and redirect behavior only when the backend implements them; defaults are visible.
- Variable references `{{name}}` are highlighted and hover reveals scope without revealing secret values.

Send validates the editor snapshot, creates an operation, and opens Response. It does not silently save. Save validates persistence fields and includes revision. Save as creates a new resource and asks for collection/name. Cancel targets only the active request operation.

### Response viewer

Summary shows status, duration, byte size, content type, and timestamp. Tabs are Body, Headers, Request, Timeline, and Tests/Logs when available. Body modes include formatted JSON tree, raw text, preview for safe supported media, and download. HTML is never executed in the application origin.

Formatting errors fall back to raw with a clear explanation. Truncation states exact captured/total size when known and offers artifact download. Copy actions identify whether they copy formatted body, raw body, headers, or cURL. A generated cURL command redacts secrets unless the user explicitly reveals and confirms inclusion.

## 3. Environments And Variables

The global environment selector shows project environments and `No environment`. The editor supports create, rename, duplicate, activate, delete, import, and export. Variables include enabled, key, value, scope, secret, and description when schema support is introduced.

Secret behavior:

- Existing secret values display `Saved secret`, never placeholder bullets that could be resubmitted as data.
- Reveal requests a fresh server read only if the chosen secret backend supports it; otherwise replacement is the only action.
- Changing secret status warns about export/history implications.
- Copy is unavailable for masked values.

Deleting an environment shows references from monitors, requests, workflow defaults, and runs. Active environment deletion requires selecting a replacement or No environment. Duplicate copies non-secret values; secret copying requires explicit confirmation.

## 4. Workflow Studio

Workflow behavior follows `03-architecture/workflow-studio.md`. The explorer supports create blank, create from selected requests, duplicate, rename, export JSON/SCLPLL, version history, and delete. Search covers name, description, step, request, and function.

Workbench modes are Canvas, Outline, Source, Versions, and Run. A persistent toolbar provides Save, Run, Validate, undo/redo, view controls, and mode switch. Inspector and bottom panel are shared across modes.

Deletion displays referencing monitors or plugin contributions. Duplicating produces new workflow and step IDs where externally safe. Import always runs validation and conflict preview. Examples open as copies rather than editing shipped example files.

## 5. Functions

The Functions explorer displays project files by directory plus plugin-provided read-only functions in a distinct group. Search covers metadata, path, type, and description. Filters cover pre-request, post-response, transformer, auth token, exporter, invalid metadata, and plugin source.

Supported operations for project functions: create from a contract-valid template, open, edit, validate, Save, Save as, rename/move within root, duplicate, delete, and reload discovery. Monaco uses Python language support without claiming full server-side type analysis.

Validation parses AST without executing the module and checks required metadata, allowed type, `run(ctx)` existence, path rules, syntax, and known dangerous/import patterns as warnings only. Save requires valid syntax but may allow contract warnings after acknowledgement. Plugin-owned functions are read-only unless the plugin itself is opened in its project directory editor.

Test function opens a fixture editor for ExecutionContext fields, clearly states trusted-code execution, creates an operation, and shows returned context, stdout/stderr capture where implemented, duration, and exception. There is no fake sandbox. First execution of newly imported or edited code requires trusted-code acknowledgement per content hash.

## 6. Extensions And Plugins

Extensions lists filesystem plugins with status: Active, Disabled, Invalid, or Load failed. Detail includes manifest, version, description, author, path, contributed functions/workflows, variables, hooks, load diagnostics, and last reload.

Operations: create scaffold, inspect/edit manifest, enable, disable, reload one, reload all, open contributed resource, export, and delete locally created plugin. Install from remote registries is out of v1 because no trusted registry or package verification exists. Importing a plugin archive uses Transfer Center preview and the trusted-code warning.

Create scaffold validates a filesystem-safe plugin ID, human name, and optional examples, then writes a manifest and contract-valid example through the constrained service. Enable/reload failures preserve the previous active registry when possible and expose redacted diagnostics.

## 7. Monitors

The monitor list supports search, status filter, create, duplicate, edit, start, stop, inspect, export events, clear events, and delete. Rows show name, method/URL, interval, status, last result, last run, runs, and triggers. Bulk start/stop is available with per-monitor outcome.

Monitor editor includes request fields, environment, interval with safe minimum, condition expression, notification mode, enabled state, and Run once. Condition validation occurs before Save and server-side before Start. Starting an invalid monitor fails without changing persisted status.

Detail includes health summary, current configuration, event timeline, response/body preview, error history, and charts for duration/status over time. Selecting two events opens Compare. Clear events requires confirmation and does not delete the monitor. A disconnected UI does not imply the server monitor stopped.

## 8. Runs, History, Diff, And Logs

Runs unify request history, workflow executions, batch operations, monitor events, imports, and exports through type filters while preserving domain-specific detail. Filters include time, type, status, resource, environment, and free text; filter state is encoded in the URL.

Run detail includes immutable executed snapshot, summary, steps/attempts where applicable, input variables with secrets redacted, outputs, logs, artifacts, and related resources. Rerun opens a confirmation of current versus historical environment/resource revisions. Users choose current definition or historical snapshot only where execution support is explicit.

Compare accepts compatible response bodies, request snapshots, workflow versions, monitor events, or arbitrary selected text. Monaco Diff handles text/JSON; structured summaries identify added, removed, and changed fields. Binary and oversized artifacts provide metadata comparison instead of loading into Monaco.

Logs live in the activity panel and Runs detail. They support severity/source filter, pause autoscroll, clear view, copy selected, and export redacted text. Clear view does not delete stored history. Tracebacks appear only in an expanded technical section.

History retention supports keep all, 1 day, 7 days, 30 days, and custom days. Preview shows deletion count before Apply. Clear all requires typed confirmation. Retention applies per project unless a clearly labeled global setting is introduced.

## 9. Batch

Batch starts from a saved or current request and a CSV upload. Flow:

1. Select request snapshot.
2. Upload CSV and validate encoding/header/row limits.
3. Preview the first 20 rows and map columns to `batch_row` variables.
4. Select environment and confirm total rows.
5. Start sequential execution to match current engine semantics.
6. View aggregate progress and per-row status.
7. Cancel without discarding completed results.
8. Retry failed rows as a new linked operation or export all/failed results.

The browser uploads content, not a local path string. Duplicate headers, empty CSV, malformed rows, and oversize files receive actionable errors. Closing the tab never stops a batch.

## 10. Transfer Center

Transfer Center covers full workspace backup, selective project export, collections, environments, workflows, functions, plugins, history, OpenAPI import, and restore.

Import is always Preview then Apply. Preview validates manifest/version, parses files, reports code-bearing content, lists creates/updates/conflicts/skips, and requires a conflict policy: keep existing, replace, or create copies. Secrets are excluded by default. Including them requires explicit confirmation and an export format that preserves their classification.

Apply uses the preview token and runs as an operation. Atomic sections roll back on failure; non-atomic file copies report precise partial outcomes and recovery paths. Importing an entire database file is not exposed through the browser while the application database is open.

OpenAPI import accepts JSON/YAML content, selects server/base URL and operations, previews generated collections/requests, and records unsupported constructs as warnings. It never executes example endpoints during import.

## 11. Settings And Commands

Settings sections: Appearance, Editor, Requests, History, Startup, Paths/read-only diagnostics, Updates, and About/licenses. Theme offers System, Dark, Light; density offers Comfortable and Compact. Editor settings include font size, tab size, minimap, word wrap, format-on-request, and reduced motion override only when it further reduces motion.

Default UI can become Web or TUI after backend settings support is extended. Startup browser behavior and loopback port remain server settings and require restart, which the UI states. Settings Save is explicit and reports which values require restart.

The command palette includes all navigation, creation, active editor, run, panel, and theme commands. Commands have stable IDs, context predicates, labels, keywords, and optional shortcuts. Keyboard help is generated from the registry so it cannot drift.

## 12. Notifications And Global Operations

The global operation menu shows running and recent operations across the active project. Each entry names resource, type, status, progress, elapsed time, and permitted action. Completed operations link to result detail. Notification counts distinguish unread completion/failure from currently running work.

Toasts supplement persistent operation state and never become the only record of failure. At most three appear; later notices queue. Repeated monitor notices coalesce with a count. Notification text and operation status use the same action vocabulary.

## 13. Feature Acceptance Matrix

Every work area must demonstrate:

- Create/read/update/delete or the complete valid subset for immutable resources.
- Search/filter and useful empty state.
- Loading, validation, server failure, disconnection, conflict, and partial-success behavior.
- Keyboard completion of its primary journey.
- Project isolation and environment handling.
- Appropriate confirmation and rollback/recovery for destructive actions.
- Deep link restoration and dirty-tab behavior.
- Unit, API integration, browser journey, and accessibility coverage proportionate to risk.

