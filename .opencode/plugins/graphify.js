// graphify OpenCode plugin (OpenCode v2 plugin API)
// Injects a knowledge graph reminder before bash tool calls when the graph exists.
//
// IMPORTANT: keep the reminder string free of backticks and $(...) constructs.
// The hook prepends `echo "<reminder>" ; <cmd>` to the user's bash command;
// backticks inside the double-quoted echo trigger bash command substitution,
// which both corrupts tool output and silently executes the very graphify
// command we are only suggesting. Plain words render fine in opencode's TUI.
import { existsSync } from "fs";
import { join } from "path";

export default {
  id: "narrare.graphify-reminder",
  async setup(ctx) {
    let reminded = false;

    await ctx.tool.hook("execute.before", (event) => {
      if (reminded) return;
      if (event.tool !== "bash") return;
      if (!existsSync(join(ctx.location.directory, "graphify-out", "graph.json"))) return;

      const input = event.input;
      if (typeof input?.command !== "string") return;
      // ';' not '&&' — Windows PowerShell 5.1 rejects '&&' as a statement
      // separator, breaking the first bash command of the session (#1646).
      input.command =
        'echo "[graphify] knowledge graph at graphify-out/. For focused questions, run graphify query with your question (scoped subgraph, usually much smaller than GRAPH_REPORT.md) instead of grepping raw files. Read GRAPH_REPORT.md only for broad architecture context." ; ' +
        input.command;
      reminded = true;
    });
  },
};
