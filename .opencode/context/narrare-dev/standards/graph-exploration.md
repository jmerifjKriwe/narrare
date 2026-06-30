<!-- Context: narrare-dev/standards/graph-exploration | Priority: critical | Source: AGENTS.md, code-review-graph + codebase-memory-mcp | Updated: 2026-06-30 -->

# Graph Tool Exploration Standard

> **Audience**: ALL Narrare specialists. This is Tier-1 reading.
> **Rule**: ALWAYS query available code knowledge graph tools BEFORE using Read/Glob/Grep.
> **Conditional**: Graph tool availability varies by session. Check availability, choose the right
> tool for your task, then fall back gracefully.

---

## 1. Tool Availability Check

At the start of every session (and before any code exploration), verify which graph tools are available:

### Step 1: Check code-review-graph
```
code-review-graph_list_graph_stats_tool
```
- **Available**: Tool returns valid stats (node count > 0) → proceed with `code-review-graph`
- **Unavailable**: Returns error / timeout → proceed to Step 2

### Step 2: Check codebase-memory-mcp
```
codebase-memory-mcp_search_graph(project="narrare", query="ping")
```
- **Available**: Returns results → proceed with `codebase-memory-mcp`
- **Unavailable**: Returns error → fall back to Read/Glob/Grep

### Step 3: Choose the best tool for your task

Use the **Tool Selection Decision Matrix** (§2) to pick the right tool once you know what's available.

---

## 2. Tool Selection Decision Matrix

Both graph systems have overlapping and unique capabilities. Choose based on your task:

| Task | code-review-graph | codebase-memory-mcp | ✅ Best choice |
|------|:-----------------:|:-------------------:|:-------------:|
| Find code by name/keyword | `semantic_search_nodes_tool` | `search_graph` (BM25 + semantic_query) | **codebase-memory** — richer search |
| Trace calls (callers/callees) | `query_graph_tool` (callers_of/callees_of) | `trace_path` (risk_labels, depth, data_flow) | **codebase-memory** — more features |
| Impact / Blast Radius | `get_impact_radius_tool` ⭐ | — (not available) | **code-review-graph** (only option) |
| Code Review (risk-scored) | `detect_changes_tool` (detailed risk scoring) ⭐ | `detect_changes` (basic) | **code-review-graph** — richer |
| Architecture Overview | `get_architecture_overview_tool` | `get_architecture` (Leiden communities) ⭐ | **codebase-memory** — richer |
| Complex Graph Queries (Cypher) | — (not available) | `query_graph` ⭐ | **codebase-memory** (only option) |
| Read function source code | — (not available) | `get_code_snippet` ⭐ | **codebase-memory** (only option) |
| Refactoring (rename/dead code) | `refactor_tool` ⭐ | — (not available) | **code-review-graph** (only option) |
| Ultra-compact context (<100 tok) | `get_minimal_context_tool` ⭐ | — (not available) | **code-review-graph** (only option) |
| Hub/Bridge/Hotspot Analysis | `get_hub_nodes_tool`, `get_bridge_nodes_tool` ⭐ | — (not available) | **code-review-graph** (only option) |
| Find large functions | `find_large_functions_tool` ⭐ | — (not available) | **code-review-graph** (only option) |
| Cross-project analysis | — (not available) | cross-repo-intelligence ⭐ | **codebase-memory** (only option) |
| Index / Build Status | `list_graph_stats_tool` | `index_status` | Either — both work |
| Graph Traversal | `traverse_graph_tool` | `trace_path` (BFS/DFS limited) | **code-review-graph** — richer |

**Legend:** ⭐ = unique capability (no equivalent in the other system)

---

## 3. Workflow

### 3.1 Build/Update the Graph

The graph does NOT auto-update on file changes. Run before querying:

| System | Command |
|--------|---------|
| code-review-graph | `code-review-graph_build_or_update_graph_tool` (incremental) |
| codebase-memory-mcp | `codebase-memory-mcp_index_repository` (moderate mode) |

Use incremental updates after normal changes. Full rebuilds only when the graph is stale
(e.g., after branch switch, large rebase, or corrupted state).

### 3.2 Explore

Use the Decision Matrix (§2) to choose the right tool for your task.

**Common patterns:**

| Query Type | code-review-graph | codebase-memory-mcp |
|------------|-------------------|---------------------|
| Find a function/class | `semantic_search_nodes_tool` (keyword) | `search_graph` (BM25 + semantic_query) |
| Who calls this? | `query_graph_tool callers_of` | `trace_path` (inbound) |
| What does this call? | `query_graph_tool callees_of` | `trace_path` (outbound) |
| Tests for X | `query_graph_tool tests_for` | `search_graph` + label filter |
| Imports of X | `query_graph_tool imports_of` | `query_graph` (Cypher) |
| Architecture overview | `get_architecture_overview_tool` | `get_architecture` |

### 3.3 Analyze

| Analysis Type | code-review-graph | codebase-memory-mcp |
|---------------|-------------------|---------------------|
| Code Review | `detect_changes_tool` | `detect_changes` |
| Blast Radius | `get_impact_radius_tool` ⭐ | — |
| Affected Flows | `get_affected_flows_tool` ⭐ | — |
| Hub/Bridge/Hotspot | `get_hub_nodes_tool`, `get_bridge_nodes_tool` ⭐ | — |
| Knowledge Gaps | `get_knowledge_gaps_tool` ⭐ | — |
| Surprising Connections | `get_surprising_connections_tool` ⭐ | — |
| Community Structure | `list_communities_tool` | `get_architecture` (Leiden) |
| Large Functions | `find_large_functions_tool` ⭐ | — |

---

## 4. Fallback Chain

```
code-review-graph verfügbar?
├─→ Ja → Nutze Matrix (§2) für Tool-Wahl
│   └─→ Fehlt data? → codebase-memory-mcp versuchen (§2)
│       └─→ Fehlt data? → Read/Glob/Grep (§5)
│
└─→ Nein → codebase-memory-mcp verfügbar?
    ├─→ Ja → Nutze Matrix (§2) für Tool-Wahl
    │   └─→ Fehlt data? → Read/Glob/Grep (§5)
    │
    └─→ Nein → Read/Glob/Grep (§5)
```

**Key principle:** Never jump directly to Read/Glob/Grep — always try the other graph tool first.

---

## 5. When to Fall Back to Read/Glob/Grep

Use Read/Glob/Grep **only** when:

1. **Both graph tools** are unavailable or unresponsive
2. **Both graph tools** lack coverage for a specific area (e.g., new file not yet indexed)
3. You need exact file contents (the graph stores metadata, not full content)
4. You need to read a specific config, documentation, or non-code file
5. The graph lacks the specific relationship type you need

Even then: try to narrow down with what the graph does provide, then use Read for specifics.

---

## 6. Common Patterns

### Before writing code in a module:
```
1. check_available_tools()  → determine which graph systems are live
2. search_graph / semantic_search_nodes_tool → find existing patterns
3. trace_path / query_graph_tool → understand call chains
4. Read → read specific files identified above
```

### Before code review:
```
1. build_or_update_graph_tool / index_repository (incremental)
2. detect_changes_tool / detect_changes
3. get_affected_flows_tool (if crg available)
4. query_graph_tool / search_graph for tests
```

### Before refactoring:
```
1. get_impact_radius_tool(changed_files=[...], max_depth=3)  (crg only)
2. refactor_tool(mode="rename", ...)  (crg only)
3. apply_refactor_tool(refactor_id="...")  (crg only)
4. query_graph_tool / trace_path for dependency verification
```

---

## 7. Session Startup Check

At the beginning of every session, check graph availability:

```
# Check code-review-graph
code-review-graph_list_graph_stats_tool
# OR check codebase-memory-mcp
codebase-memory-mcp_search_graph(project="narrare", query="ping")
```

If one is down, try the other. If both are down, proceed with Read/Glob/Grep
and note the gap in your session summary.

**The standard remains: graph-tool-first, then fallback.** The graph is the
preferred path, but not mandatory — adapt to what's available.

---

**Reference**: `AGENTS.md` (MCP Tools section), code-review-graph + codebase-memory-mcp documentation
**Related**: narrare-dev/processes/graph-fallback-process · narrare-dev/constraints/rules · narrare-dev/domain/module-map
**Predecessor**: `code-graph-first.md` (replaced — this document supersedes it)
