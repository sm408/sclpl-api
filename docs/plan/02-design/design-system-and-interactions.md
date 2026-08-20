# Design System And Interaction Specification

## 1. Design Thesis

SCLPLAPI should feel like an instrument panel for API execution: precise, calm, information-dense, and visibly alive only when work is running. The structure borrows the proven activity-rail pattern from communication workspaces, but the visual language comes from request traces, dependency graphs, code editors, and execution signals.

The distinctive device is the **execution signal spine**. A two-pixel semantic line appears at the active rail item, continues through the active workbench tab, and maps into running workflow nodes and the activity panel. It is static for idle selection, pulses once when execution begins, advances by discrete state changes, and never runs as ambient decoration.

## 2. Tokens

### Dark theme

| Token | Value | Use |
|---|---|---|
| `--surface-canvas` | `#0B1020` | App and workflow background |
| `--surface-panel` | `#12192A` | Rail, explorer, editors |
| `--surface-raised` | `#192235` | Menus, cards, selected rows |
| `--surface-hover` | `#202B41` | Hover only |
| `--border-subtle` | `#2A3650` | Dividers and inactive controls |
| `--border-strong` | `#40506F` | Active resizers and emphasized boundaries |
| `--text-primary` | `#F1F4FA` | Main text |
| `--text-secondary` | `#AAB4C8` | Supporting text |
| `--text-muted` | `#7C889F` | Metadata that still passes contrast at its size |
| `--accent-primary` | `#7C8CFF` | Focus, selection, primary action |
| `--accent-live` | `#35C6D0` | Running/streaming state |
| `--status-success` | `#39C58A` | Successful execution |
| `--status-warning` | `#F2B84B` | Risk, waiting, skipped |
| `--status-danger` | `#F16F7A` | Failure and destructive action |

### Light theme

Use canvas `#F5F7FB`, panel `#FFFFFF`, raised `#EEF2F8`, border `#CDD5E3`, primary text `#152033`, secondary text `#4E5D75`, primary accent `#5265D8`, live accent `#087F8C`, success `#177A52`, warning `#8A5A00`, and danger `#B42335`. Components consume semantic tokens only; they do not branch on theme names.

### Typography

- IBM Plex Sans: UI, labels, prose, tables, and headings.
- IBM Plex Mono: code, URLs, methods, identifiers, timings, variable names, and response data.
- Base UI size is 14px comfortable and 13px compact, with line heights of 20px and 18px.
- Page heading: 20/28 semibold. Section heading: 15/22 semibold. Labels: 12/16 medium. Metadata: 12/16 regular.
- Uppercase is limited to HTTP methods and established protocol tokens. Letter-spaced decorative eyebrows are prohibited.

### Geometry

- Spacing scale: `4, 8, 12, 16, 20, 24, 32, 40` pixels.
- Control heights: 32px compact, 36px comfortable, 40px primary URL bar.
- Radius: 4px controls, 6px menus/dialogs, 8px large empty-state surfaces. Pills are reserved for tags and statuses.
- Shadows appear only on overlays. Persistent panels use borders and surface contrast.
- Focus ring: 2px primary accent plus 2px canvas offset, visible in both themes.

## 3. Shell Components

### Activity rail item

States: default, hover, focus, active, badge, running, disabled. The icon remains 20px. Expanded labels truncate with a tooltip. Badges show counts up to 99 and `99+` beyond. Running status cannot replace notification count; it uses the signal spine.

### Explorer tree

Rows include disclosure control, type icon, label, optional status, and trailing context action revealed on hover and focus. Indentation is 16px per level and capped visually after four levels. Dragging is enabled only where reparenting is valid. Keyboard controls follow the ARIA tree pattern.

### Workbench tabs

Tabs are horizontally scrollable with an overflow list. Middle click closes a clean tab. The close button is always keyboard reachable. Dirty, conflict, validation, and running indicators have separate icons and accessible names. Tabs never shrink below 112px or grow beyond 240px.

### Resizable panels

Resizer hit targets are at least 8px while visible strokes remain 1px. Arrow keys resize by 8px; Shift+Arrow resizes by 32px. Double-click resets to the feature default. Sizes are constrained so the workbench always retains at least 480px on desktop.

### Command palette

The palette groups navigation, creation, active-resource actions, run actions, and settings. Results include label, category, context, and shortcut. Disabled commands remain searchable when explaining why they are unavailable is useful. Recent successful commands rank above fuzzy matches but cannot reorder exact matches.

## 4. Domain Components

### HTTP method badge

Methods use text plus a restrained color: GET cyan, POST green, PUT amber, PATCH violet, DELETE red, HEAD blue-gray, OPTIONS gray. Badges maintain identical dimensions and never convey method only by color.

### Key-value editor

Headers, parameters, and variables use a virtualized row editor with enabled checkbox, key, value, description, secret marker where applicable, drag handle, and row menu. Enter adds a row, Tab advances cells, and paste supports tab/newline matrices. Duplicate keys are warnings unless the protocol context allows them.

### Status presentation

Use consistent terms and icons: Queued, Running, Succeeded, Failed, Cancelled, Timed out, Skipped, Paused. Every status component can render compact icon-only, row badge, and detailed summary variants from one semantic model.

### Workflow node

Node anatomy: semantic type strip, icon and name, concise operation summary, input handles, output handle, validation/status icon, and duration during/after runs. Selected nodes use border and elevation; running nodes use the live accent; success/failure colors appear only after completion. Node width defaults to 248px and can expand for long summaries without changing handle positions.

### Monaco editor wrapper

The wrapper owns model URIs, theme mapping, dirty state, diagnostics, read-only state, resize observation, and accessible toolbar actions. It must dispose models when their final tab closes. Large response bodies default to read-only and can switch between formatted and raw models without duplicating content unnecessarily.

### Data tables

Tables use sticky headers, keyboard row selection, column visibility, sorting, filters, pagination or virtualization, and explicit empty states. Row menus are not the only path to common actions. Numeric timing/status columns align consistently. Tables never use alternating colors as the sole row boundary.

## 5. Workflow Interactions

- Pointer users add nodes through drag-and-drop or double-click palette actions.
- Keyboard users add the selected palette item after the current outline node or at the workflow end.
- Connecting nodes creates a dependency only after cycle validation; invalid targets show reason text.
- Delete removes selected nodes only after warning about downstream dependencies. Edges can be removed without deleting nodes.
- Multi-select, copy, paste, duplicate, undo, redo, fit view, zoom, align, and auto-layout are commands shared by canvas and menus.
- Auto-layout is an explicit operation and remains undoable; it never runs automatically after each edit.
- Canvas minimap, controls, and background can be hidden independently for reduced clutter.
- The outline view exposes step order, dependencies, condition, retries, output variable, and execution status without relying on spatial position.

## 6. Feedback And Motion

- Hover transitions: 80ms. Panel transitions: 140ms. Dialog entry: 160ms. No transition exceeds 200ms during normal work.
- Beginning an operation causes one signal-spine sweep. Ongoing progress uses state changes rather than continuous glowing animation.
- Toasts report completed background actions and recoverable failures. Field validation, destructive warnings, and long error messages remain inline.
- Success toasts disappear after four seconds; warnings after eight; errors persist until dismissed or resolved.
- With reduced motion, movement becomes opacity or immediate state change, and the signal spine does not pulse.

## 7. Accessibility Contract

- Apply WCAG 2.2 AA contrast to text, icons, focus, selected states, graphs, and status components.
- Every icon-only control has an accessible name and tooltip; tooltip content is supplemental, not required to understand the control.
- Dialogs trap focus, name their purpose, describe irreversible impact, close with Escape when safe, and restore focus to the invoker.
- Toast announcements use polite live regions except blocking execution/security failures, which use assertive announcements once.
- Monaco actions are mirrored in surrounding controls where browser/editor shortcuts are ambiguous.
- Canvas selection and node state changes announce through a dedicated polite status region.
- Charts have text summaries and accessible data tables. Color series also use symbols or line patterns.
- Test at 200% browser zoom, Windows high contrast, dark/light themes, reduced motion, keyboard only, NVDA/Firefox, and VoiceOver/Safari.

## 8. Design Review Checklist

- Does each screen have one obvious primary action?
- Does the explorer contain resources while the rail contains activities?
- Can every status be understood without color?
- Are empty, loading, error, conflict, disconnected, and partial-success states designed?
- Can the task be completed without a pointer or graph canvas?
- Are Monaco, tables, and charts loaded only when needed?
- Does copy use the same verb before, during, and after an action?
- Has decoration unrelated to execution, hierarchy, or feedback been removed?

