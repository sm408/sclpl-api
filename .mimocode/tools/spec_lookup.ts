import { tool } from "@mimocode/cli/plugin"
import fs from "node:fs"
import path from "node:path"

const SPEC_FILES = [
  "AGENTS.md",
  "FEATURES.md",
  "ARCHITECTURE.md",
  "WORKFLOW_ENGINE.md",
  "FUNCTION_SYSTEM.md",
  "PLUGIN_SDK.md",
  "EXPORT_ENGINE.md",
  "DATABASE_AND_MIGRATIONS.md",
  "UI_UX_GUIDE.md",
  "CODING_STANDARDS.md",
  "TESTING_STRATEGY.md",
]

const DOC_FILES = [
  "docs/architecture/API_CONTRACTS.md",
  "docs/architecture/RUNTIME_MODEL.md",
  "docs/architecture/SECURITY_MODEL.md",
  "docs/architecture/STORAGE_MODEL.md",
  "docs/subsystems/EVENT_BUS.md",
  "docs/subsystems/VARIABLE_SYSTEM.md",
  "docs/subsystems/GRAPH_REPORT.md",
  "docs/subsystems/HEADLESS_MODE.md",
  "docs/subsystems/PLUGIN_SPEC.md",
  "docs/subsystems/PLUGIN_REGISTRY.md",
  "docs/planning/ROADMAP.md",
  "docs/planning/DEVELOPMENT.md",
  "docs/planning/NON_GOALS.md",
]

function readFileSafe(filePath: string): string {
  try {
    return fs.readFileSync(filePath, "utf8")
  } catch {
    return ""
  }
}

export default tool({
  description: "Search SCLPLAPI source-of-truth spec and doc files for a concept or requirement.",
  args: {
    query: tool.schema.string().describe("Concept, term, or subsystem to look up"),
    scope: tool.schema
      .enum(["spec", "docs", "all"])
      .optional()
      .describe("Search scope: spec (canonical), docs (supplementary), all (default)"),
  },
  async execute(args, context) {
    const base = context.worktree || context.directory
    const q = args.query.toLowerCase()
    const scope = args.scope || "all"

    const filesToSearch: string[] = []
    if (scope === "spec" || scope === "all") filesToSearch.push(...SPEC_FILES)
    if (scope === "docs" || scope === "all") filesToSearch.push(...DOC_FILES)

    const matches: Array<{ file: string; lines: string[] }> = []

    for (const file of filesToSearch) {
      const full = path.join(base, file)
      const content = readFileSafe(full)
      if (!content) continue

      const lines = content
        .split(/\r?\n/)
        .filter((line) => line.toLowerCase().includes(q))
        .slice(0, 5)

      if (lines.length > 0) {
        matches.push({ file, lines })
      }
    }

    if (matches.length === 0) {
      return `No matches found for "${args.query}".`
    }

    return matches
      .map((match) => `# ${match.file}\n${match.lines.map((line) => `- ${line.trim()}`).join("\n")}`)
      .join("\n\n")
  },
})
