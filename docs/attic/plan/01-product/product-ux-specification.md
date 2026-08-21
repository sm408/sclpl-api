# Product And UX Specification

## 1. Audience And Jobs

### Primary user: API workflow developer

The primary user builds and troubleshoots HTTP integrations locally. They understand methods, headers, JSON, environment variables, and Python, but should not need to understand SCLPLAPI storage internals. Their core jobs are to send a request quickly, turn successful requests into repeatable workflows, insert Python transformations, inspect failures, and rerun work with different environments.

### Secondary user: technical operator

The secondary user runs existing workflows and batches, watches monitors, compares results, exports evidence, and needs clear operational status. They value predictable controls and useful failure recovery over maximal editing density.

### Product language

- Use names that match user-controlled resources: Project, Collection, Request, Workflow, Function, Plugin, Environment, Monitor, Run.
- Use **Run** for workflows and batches, **Send** for a single request, **Start/Stop** for monitors, and **Save** for persistence.
- Use sentence case. Buttons state the action, such as `Create project`, `Apply source changes`, and `Retry failed rows`.
- Errors state what failed, why when known, and the available recovery action. Avoid apology, blame, or generic `Something went wrong` text.
- Do not expose Python class names, database table names, tracebacks, or transport terminology in normal UI copy. Detailed diagnostics belong in an expandable technical section.

## 2. Information Architecture

The application uses four persistent layers from left to right:

```text
+----------+----------------------+--------------------------------------+------------------+
| App rail | Context explorer     | Workbench tabs and active editor     | Inspector        |
| 56/208px | 240-360px resizable  | flexible                             | 280-420px        |
|          |                      |                                      | optional         |
+----------+----------------------+--------------------------------------+------------------+
|                         Activity / response / problems panel                              |
+-------------------------------------------------------------------------------------------+
```

The app rail answers “which activity am I doing?” The explorer answers “which resource am I acting on?” The workbench answers “what is open?” The inspector answers “what properties can I change?” The activity panel answers “what happened?” These roles must remain distinct.

### Primary rail

Top group:

1. Home
2. Requests
3. Workflows
4. Functions
5. Monitors
6. Runs
7. Extensions

Bottom group:

1. Transfer Center
2. Settings
3. Expand/collapse rail

The active item uses position, background, label weight, and an inset indicator; color alone is insufficient. In collapsed mode, hover and keyboard focus show a tooltip after 350ms. The tooltip includes label and shortcut. Expansion is a deliberate click and is remembered locally.

### Global top bar

The top bar contains the project switcher, global search/command trigger, active environment selector, running-operation indicator, and connection status. It does not duplicate local editor actions. Project and environment changes with dirty tabs open require a review dialog listing affected tabs.

### Explorer behavior

Each activity owns its explorer content, search, filters, creation action, and resource tree. The explorer supports keyboard traversal, collapse/expand, context menus, and resizable width. Search filters the current tree without destroying expansion state. Creation controls remain visible when search returns no results.

### Workbench tabs

Tabs represent editable or inspectable resources, not destinations. A tab key is `projectId + resourceType + resourceId + viewMode`, preventing collisions. Tabs show resource icon, concise name, dirty dot, running state, and close action. Closing a dirty tab offers Save, Discard, and Cancel. Closing a running operation detaches the view but never cancels the operation implicitly.

## 3. Navigation And Deep Links

Every resource editor has a stable route:

```text
/projects/:projectId/home
/projects/:projectId/requests/:requestId?
/projects/:projectId/workflows/:workflowId?
/projects/:projectId/functions/:functionPath?
/projects/:projectId/monitors/:monitorId?
/projects/:projectId/runs/:runId?
/projects/:projectId/extensions/:pluginId?
/projects/:projectId/environments/:environmentId?
/projects/:projectId/transfer
/settings
```

Opening a deep link selects the project and activity, expands the containing explorer branch, opens the tab, and focuses the main heading. Missing resources show an in-workbench not-found state with Back to list and Refresh actions. A project mismatch never silently redirects to a similarly named resource in another project.

## 4. Core Journeys

### First launch

1. The server migrates or initializes storage before serving a usable shell.
2. The UI opens the Default project and detects whether resources exist.
3. A populated project shows recent requests, workflows, monitor health, and runs.
4. An empty project shows three concrete starts: create a request, import OpenAPI, or open an example workflow.
5. A migration failure blocks editing and offers diagnostic copy, backup location, and Retry. It never presents an apparently empty workspace.

### Create and send a request

1. Select Requests and create a request in an existing or new collection.
2. Enter method and URL; unresolved variables are highlighted before sending.
3. Configure parameters, headers, body, and authentication through structured tabs.
4. Select an environment and press Send.
5. The response panel opens immediately with pending status and cancellation.
6. Completion shows status, duration, size, headers, formatted body, raw body, and request details.
7. Save persists the request; Send does not require Save and history records the executed snapshot.

### Build and run a workflow

1. Create a blank workflow or start from selected saved requests.
2. Drag a node from the palette or add it from the keyboard-accessible outline.
3. Configure the node in the inspector and connect dependencies.
4. Validation continuously reports structural problems without blocking unrelated edits.
5. Save creates a new immutable version when canonical data changed.
6. Run prompts for environment and input variables when required.
7. The execution signal spine, node states, and activity panel reflect progress from SSE events.
8. Selecting a completed node shows its resolved inputs, output, logs, timing, and error.

### Edit SCLPLL safely

1. Switch the workflow workbench from Canvas to Source.
2. Source initially reflects the last saved canonical definition.
3. Editing creates a source draft and does not mutate the graph.
4. `Preview changes` parses the source and shows diagnostics plus a structural diff.
5. `Apply to workflow` is enabled only when parsing succeeds and no unsupported-loss warning remains unresolved.
6. Applying replaces the canonical draft, regenerates the graph, and records source origin on Save.

### Recover from a conflict

1. Save includes the revision loaded by the editor.
2. A `409 REVISION_CONFLICT` opens a comparison view rather than overwriting either version.
3. The user can reload current server content, keep their draft in a new copy, or manually merge supported text resources.
4. Workflow conflicts compare canonical definitions and layout separately so layout-only changes are identifiable.

## 5. Cross-Cutting UX States

### Loading

- Show skeleton structure only for the first load of a view.
- Retain previous list content during background refresh and show a subtle refresh indicator.
- Operations longer than 500ms show status text. Indeterminate spinners without a task label are prohibited.

### Empty

- Explain what belongs in the area and provide one primary creation/import action.
- Search empties say `No workflows match “query”` and provide Clear search.
- Permission or loading failures must never masquerade as an empty list.

### Failure

- Inline field errors attach to fields and participate in screen-reader error summaries.
- Resource-load failures replace only the failed region and include Retry.
- Execution failures retain all available response, logs, and preceding successful node output.
- Unexpected errors include a correlation ID and Copy diagnostics, with secrets redacted server-side.

### Offline or server disconnected

The local browser can lose its server through shutdown, sleep, or port changes. The top bar shows Disconnected, mutations are disabled, drafts remain intact, and reconnection uses bounded exponential retry. Once reconnected, queries refresh and stale drafts undergo normal revision checks.

### Destructive actions

- Delete request/monitor/history entry: named confirmation with Cancel focused.
- Delete collection/environment/workflow/project: impact summary including child/reference counts.
- Default project cannot be deleted.
- Clearing all history and replacing data during import require typed confirmation.
- Stop and cancel actions state whether partial results remain available.

## 6. Responsive Rules

- `>=1440px`: rail, explorer, workbench, optional inspector, and bottom panel can coexist.
- `1024-1439px`: inspector overlays or replaces the explorer; rail defaults collapsed.
- `768-1023px`: one secondary panel at a time; canvas remains available with simplified controls.
- `<768px`: browse, inspect, send, run, monitor, and stop remain usable; complex graph layout editing directs the user to a wider viewport while the outline editor remains functional.
- Browser zoom to 200% must not hide primary actions or trap focus.

## 7. Success Measures

- A new user can create and send a GET request without documentation.
- An existing TUI user can locate every current work area through the rail, command palette, or contextual tools.
- A keyboard-only user can create a three-step dependent workflow, validate it, save it, and run it.
- Switching projects never exposes resources, environment values, events, or open resource identifiers from the previous project.
- No destructive operation occurs from closing a panel, changing a route, or losing a connection.

