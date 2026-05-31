<!-- Context: narrare-dev/standards/code-graph-first | Priority: critical | Source: AGENTS.md (MCP Tools section) | Updated: 2026-05-31 -->

# Code Graph-First Standard

> **Audience**: ALL Narrare specialists. This is Tier-1 reading.
> **Rule**: ALWAYS query the code knowledge graph BEFORE using Read/Glob/Grep.

---

## The Rule

The project has a code knowledge graph via `code-review-graph` MCP tools. Every exploration, every search, every impact analysis must start with the graph. Fall back to Read/Glob/Grep **only** when the graph lacks the data you need.

**Why**: The graph is faster, cheaper (fewer tokens), and provides structural context (callers, dependents, test coverage) that file scanning cannot.

---

## Tool Selection Guide

| Need | Use | NOT |
|------|-----|-----|
| Find code | `semantic_search_nodes_tool` | Grep |
| Who calls X? | `query_graph_tool callers_of` | Read + scan |
| Impact analysis | `get_impact_radius_tool` | Manual tracing |
| Architecture | `get_architecture_overview_tool` | Directory listing |
| Review changes | `detect_changes_tool` | Reading full files |
| Tests for X | `query_graph_tool tests_for` | Glob |
| Quick context | `get_minimal_context_tool` | Multiple reads |
| Find large files | `find_large_functions_tool` | wc -l |
| Find dead code | `refactor_tool dead_code` | Manual inspection |

---

## Workflow

### Step 1: Build/Update

The graph does NOT auto-update on file changes. Run before querying:

```
code-review-graph_build_or_update_graph_tool
```

For incremental updates after changes. Use `full_rebuild=True` only when the graph is stale.

### Step 2: Query

| Query Type | Tool | Example |
|------------|------|---------|
| Find a function/class | `semantic_search_nodes_tool` | query="ChapterWritingService" |
| Who calls this? | `query_graph_tool callers_of` | target="write_chapter" |
| What does this call? | `query_graph_tool callees_of` | target="ChapterWritingService" |
| Tests for X | `query_graph_tool tests_for` | target="writing_service" |
| Files in a module | `query_graph_tool children_of` | target="apps/api/narrare/writing" |
| Imports of X | `query_graph_tool imports_of` | target="service.py" |

### Step 3: Analyze

| Analysis Type | Tool | Use When |
|---------------|------|----------|
| `detect_changes_tool` | Reviewing code changes |
| `get_impact_radius_tool` | Understanding blast radius |
| `get_affected_flows_tool` | Finding impacted execution paths |
| `get_review_context_tool` | Need source snippets for review |
| `get_hub_nodes_tool` | Finding architectural hotspots |
| `get_bridge_nodes_tool` | Finding chokepoints |
| `get_knowledge_gaps_tool` | Finding untested/isolated code |

---

## When to Fall Back

Use Read/Glob/Grep **only** when:

1. The graph has not been built yet for a new file
2. You need exact file contents (the graph stores metadata, not full content)
3. You need to read a specific config or documentation file
4. The graph lacks coverage for a specific area

Even then: query the graph first to narrow down, then use Read for the specific file.

---

## Common Patterns

### Before writing code in a module:
```
1. get_minimal_context_tool(task="implementing X in writing module")
2. query_graph_tool(pattern="children_of", target="apps/api/narrare/writing")
3. query_graph_tool(pattern="callers_of", target="WritingService")
```

### Before code review:
```
1. build_or_update_graph_tool
2. detect_changes_tool
3. get_affected_flows_tool
4. query_graph_tool(pattern="tests_for", target="changed_function")
```

### Before refactoring:
```
1. get_impact_radius_tool(changed_files=[...], max_depth=3)
2. refactor_tool(mode="rename", old_name="X", new_name="Y")
3. apply_refactor_tool(refactor_id="...")
```

---

**Reference**: `AGENTS.md` (MCP Tools section), code-review-graph documentation
**Related**: narrare-dev/constraints/rules · narrare-dev/domain/module-map
