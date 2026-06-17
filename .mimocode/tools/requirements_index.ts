import { tool } from "@mimocode/cli/plugin"
import fs from "node:fs"
import path from "node:path"

export default tool({
  description: "List SCLPLAPI requirement documents and return their first paragraph for quick navigation.",
  args: {},
  async execute(_args, context) {
    const base = context.worktree || context.directory
    const dir = path.join(base, "requirements")
    const files = fs
      .readdirSync(dir)
      .filter((name) => name.endsWith(".md") && name !== "README.md")
      .sort()

    return files
      .map((file) => {
        const content = fs.readFileSync(path.join(dir, file), "utf8")
        const lines = content.split(/\r?\n/).filter((line) => line.trim() !== "")
        const title = lines[0]?.replace(/^#\s*/, "") || file
        const summary = lines.slice(1).find((l) => l.trim() && !l.startsWith("#")) || "No summary available"
        return `## ${title}\n${summary}`
      })
      .join("\n\n")
  },
})
