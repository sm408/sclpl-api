# Workflow Studio Architecture

## 1. Canonical Document

The canonical saved workflow is a revisioned document:

```ts
interface WorkflowDocument {
  id: string;
  projectId: string;
  name: string;
  description: string;
  definition: WorkflowDefinition;
  layout: WorkflowLayout;
  revision: number;
  createdAt: string;
  updatedAt: string;
}

interface WorkflowDefinition {
  variables: Record<string, string>;
  steps: WorkflowStep[];
}

interface WorkflowLayout {
  nodes: Record<string, { x: number; y: number; width?: number; isCollapsed?: boolean }>;
  viewport: { x: number; y: number; zoom: number };
  groups: Array<{ id: string; label: string; stepIds: string[] }>;
}
```

`WorkflowStep` mirrors the Python domain model: ID, name, step type, request/function reference, config, dependencies, retry, condition, output variable, semaphore, foreach fields, and repeat count. Pydantic becomes the authoritative transport schema and generated TypeScript prevents frontend drift.

Dependencies exist only in `step.dependsOn`. Vue Flow edges are derived projections with stable IDs `dependency:<source>:<target>`. Moving a node changes layout only. Adding/removing an edge changes dependencies only. Groups are visual organization and never alter execution.

## 2. Canvas Projection

Pure adapters provide:

```ts
toFlowGraph(definition, layout, execution?): { nodes: Node[]; edges: Edge[] }
applyGraphCommand(document, command): WorkflowDocument
validateGraphCommand(document, command): CommandValidation
```

Custom Vue Flow node components render request, function, transformer, export, and delay semantics. Conditions, foreach/repeat, retry, and parallel behavior appear as node badges/sections rather than separate fake execution nodes unless the backend domain later introduces them as real steps.

When a step lacks layout, deterministic placement adds it after its dependencies or in the next available column. This generated placement remains a draft until Save. Opening old workflows must not rewrite layout solely because rendering occurred.

## 3. Editing Commands

All mutations are domain commands with inverse commands where possible:

- `AddStep`, `DuplicateSteps`, `RemoveSteps`
- `UpdateStep`, `RenameStepId`
- `ConnectDependency`, `DisconnectDependency`
- `MoveSteps`, `AlignSteps`, `ApplyAutoLayout`
- `CreateGroup`, `UpdateGroup`, `RemoveGroup`
- `UpdateWorkflowMetadata`, `UpdateVariables`

Commands validate unique IDs, existing references, cycle prevention, required configuration, variable syntax, and project ownership before modifying the draft. The undo stack stores at most 100 semantic command pairs and resets after a source Apply or server Reload because those replace the document baseline.

Renaming a step ID updates all `dependsOn` references and any structurally known references. Free-form expressions containing the old ID are reported for manual review and are not silently rewritten.

## 4. Outline Editor

The outline is a complete alternative editor, not a read-only accessibility view. It provides:

- Ordered step tree with status, type, and dependency summary.
- Add before/after, duplicate, rename, remove, and move controls.
- Multi-select and bulk dependency removal.
- Dependency picker that excludes cyclic/invalid targets and explains disabled entries.
- Inspector access for every step field.
- Variable and validation problem navigation.
- Run selection and output inspection where backend support allows it.

Canvas and outline consume the same draft and commands, so switching loses nothing and produces no synchronization mode.

## 5. Node Palette And Inspector

The palette groups Saved requests, HTTP request, Functions, Transform, Export, and Control. Search matches display name, description, type, and tags. Drag creates a preview; dropping on an edge offers Insert between, which rewires the old dependency only after confirmation.

Inspector sections are Metadata, Operation, Dependencies, Conditions, Looping, Retry/timeout, Output, and Execution result. Sections render only applicable fields but their order remains stable. Validation links focus the precise field. Selecting multiple nodes shows only supported bulk fields such as retry strategy, group, and delete.

References use stable resource IDs. Deleting a referenced request/function is blocked or requires an explicit replacement/unresolved-reference outcome defined by the feature specification; names are display data and can change safely.

## 6. SCLPLL Synchronization

JSON is authoritative. The Source view has four states:

1. **Generated:** read from the current saved/draft definition.
2. **Edited:** source has an independent unsaved draft.
3. **Validated:** the server parsed source and returned candidate definition, normalized source, diagnostics, and compatibility report.
4. **Applied:** candidate definition replaced the workflow draft; graph and outline project the candidate.

`POST workflows/{id}:parse-sclpll` accepts source and the current workflow revision. It returns:

```ts
interface SclpllParseResult {
  isValid: boolean;
  candidateDefinition: WorkflowDefinition | null;
  normalizedSource: string | null;
  diagnostics: SourceDiagnostic[];
  changes: StructuralChange[];
  losses: CompatibilityLoss[];
}
```

Diagnostics contain severity, code, message, one-based line/column ranges, and optional fix text. Losses identify canonical fields the current DSL cannot represent. Apply is blocked for errors. Warnings require acknowledgement. Losses require explicit `Apply with listed losses` confirmation and create a version before replacement; unsupported values are never silently dropped.

Comments and original formatting are preserved only while source remains the unapplied draft. After Apply, canonical generation produces normalized SCLPLL. The UI states this before application.

## 7. Validation

Validation has three levels:

- **Immediate client checks:** missing names, duplicate IDs, empty URL/function, invalid obvious dependency, and incomplete forms.
- **Authoritative server validation:** complete Pydantic/domain validation, reference resolution, compiler compatibility, expression syntax, and execution constraints.
- **Preflight validation:** active environment, unresolved variables, secret availability, referenced files/plugins, and runtime inputs immediately before Run.

Issues use stable codes and contain severity, workflow/step location, field path, and remediation. Errors block Save only when the document cannot be represented safely; runtime/preflight errors may allow Save but block Run. Warnings never disappear because a panel closes.

## 8. Versioning And Conflicts

Every successful canonical change creates `workflow_versions` content containing definition JSON, layout JSON, generated SCLPLL, source origin, revision, and timestamp. Layout-only saves may be coalesced within a short server-side window, but canonical changes never are.

Version history supports inspect, compare with current, restore as new revision, and export. Restore never deletes later versions. Comparison categorizes metadata, variables, steps, dependencies, configuration, and layout changes.

On revision conflict, compare:

- Base to local draft.
- Base to current server document.
- Layout-only versus canonical overlap.

Automatic merge is allowed only when changed paths do not overlap and both merged documents validate. Otherwise the UI offers Reload server, Save local as copy, or manual source/field reconciliation.

## 9. Execution Visualization

Run creates an operation and freezes an execution snapshot separate from the editable draft. If the draft is dirty, the user chooses Run saved version or Save and run; unsaved execution is not supported in v1.

Events transition nodes through queued, running, succeeded, failed, skipped, cancelled, or timed out. Each transition records sequence and time. Selecting a node shows resolved request/function inputs with secrets redacted, attempts, status, duration, output preview, error, and logs. Large output is fetched on demand.

The canvas remains editable only after the user detaches from live run view. Editing cannot alter the running snapshot. Completed runs can open as overlays on the current compatible workflow or in a read-only historical snapshot when revisions differ.

## 10. Workflow Test Matrix

- Create, duplicate, delete, connect, disconnect, group, align, auto-layout, undo, and redo.
- Cycle rejection, missing references, duplicate IDs, unresolved expressions, and invalid retry/loop settings.
- Canvas/outline command equivalence and keyboard-only creation of dependent steps.
- Definition/layout serialization without edge duplication or render-induced writes.
- JSON to SCLPLL to JSON property tests for every representable field.
- Parse diagnostics positioning, warning acknowledgement, loss prevention, and normalized regeneration.
- Save conflict, disjoint auto-merge, overlapping manual conflict, version compare, and restore.
- SSE ordering, reconnect, duplicate event, sequence gap, cancellation, retry attempt, partial failure, and historical overlay.
- Canvas performance at 100, 250, and 500 nodes with selection, pan, zoom, and event updates.

