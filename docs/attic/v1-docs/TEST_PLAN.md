# TUI Test Plan

## Purpose

Validate every TUI feature before release. Every new UI component must add tests here.

---

## Startup

* Launch application.
* Verify no errors.
* Default layout loads.
* Sidebar, workspace, status bar visible.
* URL field focused.
* Resize terminal (80x24 minimum) and confirm layout adapts.

---

## Navigation

Verify keyboard-only operation.

Shortcuts:

* Ctrl+T: New tab
* Ctrl+W: Close tab
* Ctrl+P: Command Palette
* Ctrl+Shift+P: Plugin Search
* Ctrl+R: Execute Request
* Ctrl+B: Batch View
* Ctrl+F: Search
* Esc: Cancel
* ?: Help

Ensure no focus traps.

---

## Request Workspace

Test:

* URL editing
* Variables (`{{var}}`)
* All HTTP methods
* Query params
* Headers
* Cookies
* JSON/Raw/Form/Binary bodies
* Request validation

Expected: Smooth editing with no UI lag.

---

## Authentication

Verify:

* None
* API Key
* Basic
* Bearer
* Plugin Auth

Switching methods must not lose request data.

---

## Collections

Test:

* Create
* Rename
* Duplicate
* Move
* Delete
* Nested folders
* Search
* Import large collections

Expected: Lazy loading and smooth scrolling.

---

## Tabs

Verify:

* Create
* Duplicate
* Rename
* Close
* Dirty indicator
* Independent state

---

## Plugin Browser

Verify:

* Built-in plugins
* User plugins
* Reload plugins
* Invalid plugin handling
* Config schema rendering
* Metadata display

Invalid plugins should fail gracefully.

---

## Response Viewer

Verify:

* Status
* Headers
* Cookies
* Timing
* Size
* Pretty JSON
* Raw response
* Collapse/expand JSON
* Large response rendering

Expected: No freezing.

---

## Batch Execution

Verify:

* CSV import
* Variable substitution
* Sequential mode
* Concurrent mode
* Progress
* ETA
* Retry/failure handling

---

## Workflows

Verify:

* Dependency tree
* Execution order
* Live status updates

---

## Environment Manager

Verify:

* Create
* Edit
* Duplicate
* Delete
* Activate
* Variable resolution

---

## Export Builder

Verify:

* JSON
* CSV
* Excel
* Field mapping
* Column ordering
* Computed fields
* Live preview

---

## Diff Viewer

Load two responses.

Expected:

* Correct difference highlighting.

---

## History

Verify:

* Timestamp
* Endpoint
* Status
* Duration
* Cleanup policy

---

## Logs

Verify:

* Request logs
* Workflow logs
* Plugin logs
* Export logs
* Filtering
* Search

---

## Notifications

Trigger:

* Export complete
* Plugin loaded
* Request failure

Expected: Toast appears and auto-dismisses.

---

## Search

Verify instant filtering for:

* Collections
* Workflows
* Plugins
* Commands

---

## Themes

Switch themes.

Expected: Entire UI updates correctly.

---

## Error Handling

Test:

* Offline requests
* Invalid JSON
* Invalid variables
* Plugin failures

Expected: Clear errors without crashes.

---

## Performance

Verify:

* 100 tabs
* 10,000 imported requests
* 500-row batch
* Continuous logging
* Rapid tab switching

UI must remain responsive.

---

## Persistence

Restart application.

Verify persistence of:

* Collections
* Settings
* Environments
* History
* Open tabs (if enabled)

---

## Event Bus

Trigger:

* request.started
* response.received
* workflow.finished
* export.finished
* plugin.loaded

Expected: UI updates via events without polling.

---

## Release Checklist

* Startup
* Navigation
* Requests
* Auth
* Collections
* Tabs
* Plugins
* Batch
* Workflows
* Exports
* Diff
* History
* Logs
* Notifications
* Search
* Themes
* Persistence
* Performance
* No crashes
