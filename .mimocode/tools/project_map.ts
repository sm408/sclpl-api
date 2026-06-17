import { tool } from "@mimocode/cli/plugin"

const MAP: Record<
  string,
  {
    goal: string
    files: string[]
    guardrails: string[]
  }
> = {
  request_engine: {
    goal: "Build the MVP request engine, environment handling, and history support.",
    files: [
      "FEATURES.md",
      "requirements/functional_requirements.md",
      "requirements/mvp_requirements.md",
      "docs/architecture/core.md",
      "docs/subsystems/VARIABLE_SYSTEM.md",
    ],
    guardrails: [
      "Do not jump into visual workflow work.",
      "Keep request execution out of the UI layer.",
      "Environment switching must not mutate request definitions.",
    ],
  },
  workflow_engine: {
    goal: "Build graph-capable workflow runtime foundations with sequential chains first.",
    files: [
      "WORKFLOW_ENGINE.md",
      "ARCHITECTURE.md",
      "docs/subsystems/workflows.md",
      "docs/subsystems/VARIABLE_SYSTEM.md",
    ],
    guardrails: [
      "Runtime first, visual builder later.",
      "Preserve explicit runtime context.",
      "Graph-aware internals even for sequential MVP.",
    ],
  },
  extensibility: {
    goal: "Implement low-ceremony Python function and plugin extension points.",
    files: [
      "FUNCTION_SYSTEM.md",
      "PLUGIN_SDK.md",
      "requirements/extensibility_requirements.md",
      "docs/subsystems/PLUGIN_SPEC.md",
    ],
    guardrails: [
      "Keep discovery filesystem-driven.",
      "Treat contracts as stable user-facing APIs.",
      "Functions are a first-class platform capability.",
    ],
  },
  exports: {
    goal: "Implement transformation-aware export behavior without UI coupling.",
    files: [
      "EXPORT_ENGINE.md",
      "docs/subsystems/import_export.md",
      "FEATURES.md",
      "docs/subsystems/GRAPH_REPORT.md",
    ],
    guardrails: [
      "Exports are pipelines, not utility buttons.",
      "Do not bury transformation logic in the UI layer.",
      "Operate on normalized intermediate dataset models.",
    ],
  },
  storage: {
    goal: "Implement SQLite-first persistence with versioned migrations.",
    files: [
      "DATABASE_AND_MIGRATIONS.md",
      "docs/architecture/STORAGE_MODEL.md",
      "docs/architecture/storage.md",
    ],
    guardrails: [
      "SQLite is the default backend.",
      "All schema changes must be versioned.",
      "User data must be migratable.",
    ],
  },
  event_bus: {
    goal: "Implement lightweight in-process event bus for runtime lifecycle and analytics.",
    files: [
      "docs/subsystems/EVENT_BUS.md",
      "docs/architecture/RUNTIME_MODEL.md",
      "ARCHITECTURE.md",
    ],
    guardrails: [
      "In-process first, no distributed infrastructure.",
      "No business logic hidden inside subscribers.",
      "Execution remains correct even if observers fail.",
    ],
  },
}

export default tool({
  description: "Return the SCLPLAPI implementation map for a named architecture area.",
  args: {
    area: tool.schema
      .enum(["request_engine", "workflow_engine", "extensibility", "exports", "storage", "event_bus"])
      .describe("Architecture area to map"),
  },
  async execute(args) {
    const item = MAP[args.area]
    return [
      `Goal: ${item.goal}`,
      `Files: ${item.files.join(", ")}`,
      `Guardrails: ${item.guardrails.join(" | ")}`,
    ].join("\n")
  },
})
