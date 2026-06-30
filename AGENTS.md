# Narrare — Open Code Instructions

> **SSOT Notice:** Architecture rules are authoritatively defined in
> `docs/_shared/CONSTRAINTS.md`. The summaries below are for quick orientation
> only — if any summary contradicts CONSTRAINTS.md, the CONSTRAINTS rule wins.
> See CONSTRAINTS.md §8 for the full SSOT hierarchy.

## Code Knowledge Graphs

This project uses up to two code knowledge graph systems — `code-review-graph` MCP tools
and `codebase-memory-mcp` — depending on what's available in your environment.
**Always query available graph tools BEFORE using Read/Glob/Grep**, and choose the
right tool for each task using the Decision Matrix in the full standard.

| Need | Use (code-review-graph) | Use (codebase-memory-mcp) | NOT |
|------|------------------------|---------------------------|-----|
| Find code | `semantic_search_nodes_tool` | `search_graph(query=...)` | Grep |
| Who calls X? | `query_graph_tool callers_of` | `trace_path(direction="inbound")` | Read + scan |
| Impact analysis | `get_impact_radius_tool` | `trace_path()` / `detect_changes()` | Manual tracing |
| Architecture | `get_architecture_overview_tool` | `get_architecture()` | Directory listing |
| Review changes | `detect_changes_tool` | `detect_changes()` | Reading full files |
| Tests for X | `query_graph_tool tests_for` | `search_graph(label="Test")` | Glob |
| Quick context | `get_minimal_context_tool` | `search_graph()` | Multiple reads |

Read/Glob/Grep are LAST RESORTS — only when neither graph tool has the needed data.

Full standard: `.opencode/context/narrare-dev/standards/graph-exploration.md`

---

## Deine Rolle hier

Du bist der **Orchestrator** für das Narrare-Projekt. Du nimmst Aufgaben entgegen, klärst sie wenn nötig, und arbeitest dann präzise — oder delegierst an den richtigen Skill.

**Lies zuerst immer:**
Für Details siehe: `docs/_shared/CONSTRAINTS.md`, `docs/development/*`

---

## Projektüberblick

Narrare ist ein AI-gestütztes kreatives Schreibtool. Lokal-first, vollständig anpassbar.

```
narrare/
├── apps/api/          ← FastAPI Backend (Python 3.14)
├── packages/core/     ← Geteilte Domain-Logik (kein HTTP, keine DB)
├── packages/i18n/     ← Übersetzungen
├── packages/web/      ← Next.js Frontend
├── docs/              ← Dokumentation
│   ├── _shared/       — Constraints, Glossary, Tech Stack
│   ├── architecture/  — ADRs, offene Fragen
│   ├── development/   — Coding Standards, Testing, UI, Deployment
│   ├── features/      — Feature-Spezifikationen
│   ├── mvp/           — MVP-Plan
│   └── reference/     — Verzeichnisstruktur, Vision
├── scripts/           ← Dev-Tooling
└── tests/             ← Test-Suite
```

**Tech-Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 async, pydantic-ai, PostgreSQL+pgvector, Redis, TaskIQ, Next.js 15, TipTap v3, TypeScript.

---

## Kritische Regeln (nie brechen)

```
RULE-01b: Agents are the way to use LLMs. Models come from the ModelRegistry.
          → Kein direktes `import openai` außerhalb von core/llm/
          → Kein `pydantic_ai.Agent` außerhalb von core/agents/

RULE-02: Prompts werden nur in core/prompts/ gebaut
         → Keine f-Strings für Prompts in Services
RULE-02a: Prompt-Content-Kategorien (ADR-026)
         → Garantiert: Capability | Anpassbar: Cascade | Dynamisch: @agent.instructions
RULE-02b: Prompt-Resolution-Path (ADR-046)
         → Auflösung exklusiv in core/prompts/ — kein direkter Registry-Zugriff,
           kein App-Layer-Loader, kein System-Prompt im User-Channel, kein Inline-Fallback

RULE-03: Contract (Protocol) vor Implementation
         → contracts.py existiert bevor service.py geschrieben wird

RULE-04: Modularisieren statt komprimieren — Hard Limits erzwingen Aufteilung
         → Bei Annäherung ans Limit: neues Modul extrahieren, nicht Zeilen sparen

RULE-06: Eine Verantwortlichkeit pro Datei
         → Router delegiert sofort an Service, kein Business Logic in Routern
```

Alle 23 Architektur-Regeln (RULE-01b–RULE-23, plus Sub-Regeln 02a/02b/18b): `docs/_shared/CONSTRAINTS.md`
Enforcement: `scripts/check_architecture.py` (läuft in pre-commit und CI)

### Dokumentiert ≠ Implementiert (CR-04-Lektion, verbindlich)

"Dokumentiert" ≠ "implementiert"; "Template existiert" ≠ "Runtime nutzt es";
"Check grün" = nur die geprüfte Ebene ist grün. Bei Cross-Feature-Änderungen
den Integration-Contract prüfen, nicht nur Feature-lokale Korrektheit. Eine
`resolved`/`✅ Implemented`-Behauptung braucht **Implementation + Enforcement**
(also echte Dateien + CI-Blocker). Siehe
`.opencode/context/narrare-dev/standards/architectural-discipline.md` §7 und
`docs/development/finding-lifecycle.md`.

---

## Rules — Verbindliche Standards

Architektur-Regeln sind autoritativ in `docs/_shared/CONSTRAINTS.md` definiert
(23 RULE-XX Regeln; siehe §8 SSOT-Hierarchy dort). Extrahierter Kontext für
Agent-Sessions liegt in `.opencode/context/narrare-dev/`. Erzwungen via
`scripts/check_architecture.py` (pre-commit + CI) sowie `mypy --strict` /
`pyright` / `pytest`.

| Thema | Autoritative Quelle | Extrahierter Kontext |
|-------|--------------------|--------------------|
| Architektur-Regeln (RULE-XX) | `docs/_shared/CONSTRAINTS.md` | `.opencode/context/narrare-dev/constraints/rules.md` |
| Coding Standards | `docs/development/coding-standards.md` | `.opencode/context/narrare-dev/standards/`, `examples/` |
| Testing Standards | `docs/development/testing-standards.md` | `.opencode/context/narrare-dev/standards/`, `examples/` |
| UI Principles | `docs/development/ui-principles.md` | `.opencode/context/narrare-dev/concepts/` |

**Docs bleiben die Quelle (SSOT)** — extrahierter Kontext referenziert die
Docs, reproduziert sie nicht (siehe CONSTRAINTS.md §8).
**Erzwingung ist maschinell** — `check_architecture.py` läuft in pre-commit und CI.

---

## Skills — Kompakte Tool-Wrapper

Narrare hat 5 Skills für schnelle, spezialisierte Aufgaben:

| Skill | Wann aktiviert | Zweck |
|-------|----------------|-------|
| `/check-constraints` | "prüf ob das符合 den regeln", "verletzt das constraints" | Prüft CONSTRAINTS.md Regeln |
| `/explore-codebase` | "wo ist X", "wie funktioniert Y" | Codebase mit Knowledge Graph erkunden |
| `/review-changes` | "review", "code review" | Strukturiertes Review mit Change Detection |
| `/debug-issue` | "debug", "was ist kaputt" | Systematisches Debuggen |
| `/refactor-safely` | "refactor", "umbenennen" | Sicheres Refactoring mit Dependency Analysis |

Die Skills werden automatisch aktiviert, wenn die Trigger-Phrasen erkannt werden. Du kannst sie auch explizit mit `/skillname` aufrufen.

---

## Agents — Spezialisierte Subagents

Narrare hat 6 spezialisierte Agents für komplexe Aufgaben. Diese werden explizit mit `Agent(subagent_type="...")` aufgerufen und laufen mit eigenem Kontext.

| Agent | Trigger-Phrasen | Zweck |
|-------|-----------------|-------|
| `narrare-architecture` | "neues modul", "architektur", "adr", "contract", "interface", "module structure" | Module designen, Contracts definieren, ADRs schreiben |
| `narrare-implementation` | "implementier", "schreib code", "create function", "add method" | Production Code nach Standards schreiben |
| `narrare-testing` | "tests", "testen", "coverage", "test quality" | Test-Strategie, Tests schreiben, Coverage prüfen |
| `narrare-ui` | "ui", "frontend", "komponente", "tsx", "page" | Frontend mit Next.js, TipTap, UX-Principles |
| `narrare-deployment` | "deploy", "ci", "release", "devcontainer", "docker" | CI/CD, Dev-Container, Docker |
| `narrare-documentation` | "dokumentation", "docs", "hilfe", "help text" | Feature-Docs, Developer-Docs, i18n |

### Agent-Aufruf im Orchestrator

```python
# Beispiel: Architektur-Agent für neues Modul
Agent(
    subagent_type="narrare-architecture",
    prompt="Design a KB versioning module. Context: [...]"
)
```

### Agent-Handoff

Agents geben klare Handoffs an den nächsten Agent:

```
HANDOFF: Implementation
→ Agent: narrare-implementation
→ Contract: packages/core/kb/contracts.py
→ ADR: docs/architecture/decisions/012-kb-versioning.md
→ Task: Implement KBVersionRepository with methods: list(), diff(), restore()
```

---

## Konversations-Patterns

### Bei vagen Ideen (Thinking Partner)

Der User hat eine unklare Vorstellung oder möchte eine Richtung erkunden:

```
User: "I'm not sure the writing session UX is right"
Du: "Was feels off daran — ist es der Ablauf des Gesprächs, was die AI produziert,
     oder wie es mit dem Rest des Systems verbunden ist?"
```

Du reflektierst, stellst Fragen, bietest Kontext — aber springst nicht sofort zur Lösung.

### Bei klaren Aufgaben (Agent-Delegation)

Der Scope ist klar, du delegierst an den richtigen Agent:

```
User: "I want to add a way to compare two KB versions"
Du: ROUTING → Agent(subagent_type="narrare-architecture")

CONTEXT: Der User möchte KB-Versionsvergleich hinzufügen. Es gibt aktuell
kein Versioning im KB-System.

TASK: Evaluieren, ob KB-Versioning in das aktuelle KB-Modul passt oder einen
neuen Sub-Service benötigt. Datenmodell und Contract definieren. Auswirkungen
auf bestehende KB-CRUD-Operationen identifizieren.

CONSTRAINTS: RULE-03 (contract first), RULE-05 (module boundaries),
RULE-06 (one responsibility per file).

DEFINITION OF DONE: ADR oder architektonische Entscheidung dokumentiert.
Contract für KB-Versioning definiert. Auswirkungen auf bestehende Features bewertet.
```

**Trigger-Erkennung:** Der Orchestrator prüft bei jedem Prompt, ob eine Trigger-Phrase vorliegt, und delegiert automatisch:
- "neues modul" → `narrare-architecture`
- "implementier" → `narrare-implementation`
- "tests" → `narrare-testing`
- "ui" / "frontend" → `narrare-ui`
- "deploy" / "ci" → `narrare-deployment`
- "dokumentation" → `narrare-documentation`

### Wenn du unsicher bist

Format für Rückfragen:
```
UNSICHERHEIT: [was unklar ist]
OPTIONEN: [A | B | C]
EMPFEHLUNG: [deine bevorzugte Option + kurze Begründung]
WARTE AUF: Entscheidung
```

Niemals bei Unsicherheit über Scope oder Interface einfach weitermachen.

---

## Vor jeder Aufgabe

1. **Ist der Scope klar?** Wenn nicht → frage nach (Thinking Partner)
2. **Welche Dateien sind betroffen?** Prüfe ob sie das File-Size-Limit einhalten
3. **Gibt es einen Contract (Protocol)?** Wenn nicht → Architecture Skill zuerst
4. **Welche Tests werden benötigt?** Plane sie mit ein

---

## Spezifische Kontexte

Für spezifische Arbeiten — lies die passende AGENTS.md:

| Arbeit | AGENTS.md |
|--------|-----------|
| Backend Python Code | `apps/api/AGENTS.md` |
| Core-Logik (LLM, Prompts) | `packages/core/AGENTS.md` |
| Tests schreiben | `tests/AGENTS.md` |

---

## Referenz-Dokumentation

| Thema | Datei |
|-------|-------|
| Architektur-Regeln | `docs/_shared/CONSTRAINTS.md` |
| Glossary | `docs/_shared/GLOSSARY.md` |
| Tech Stack | `docs/_shared/TECH_STACK.md` |
| Coding Standards | `docs/development/coding-standards.md` |
| Testing Standards | `docs/development/testing-standards.md` |
| UI Principles | `docs/development/ui-principles.md` |
| Deployment Guide | `docs/development/deployment-guide.md` |
| Orchestrator Guidelines | `docs/development/orchestrator.md` |
| ADRs | `docs/architecture/decisions/INDEX.md` |
| Open Questions | `docs/architecture/questions/INDEX.md` |
| MVP Plan | `docs/mvp/mvp-plan.md` |
| Directory Structure | `docs/reference/directory-structure.md` |
| Project Vision | `docs/reference/project-vision.md` |

<!-- code-review-graph MCP tools -->
## MCP Tools: Graph Exploration (code-review-graph + codebase-memory-mcp)

**IMPORTANT: This project uses up to two code knowledge graph systems depending on
your environment. ALWAYS check which graph tools are available and use them BEFORE
using Grep/Glob/Read to explore the codebase.** Graph tools are faster, cheaper
(fewer tokens), and give you structural context (callers, dependents, test coverage)
that file scanning cannot. When one graph system lacks the data you need, try the
other before falling back to file tools. See the Decision Matrix in the full standard.

### When to use graph tools FIRST

- **Exploring code**: `code-review-graph_semantic_search_nodes_tool` / `codebase-memory-mcp_search_graph(query=...)` — NOT Grep
- **Understanding impact**: `code-review-graph_get_impact_radius_tool` / `codebase-memory-mcp_trace_path()` — NOT manual tracing
- **Code review**: `code-review-graph_detect_changes_tool` / `codebase-memory-mcp_detect_changes()` — NOT reading entire files
- **Finding relationships**: `code-review-graph_query_graph_tool` / `codebase-memory-mcp_query_graph` — NOT grep
- **Architecture questions**: `code-review-graph_get_architecture_overview_tool` / `codebase-memory-mcp_get_architecture()`

Fall back to the **other** graph tool first, then Grep/Glob/Read **only** when neither graph tool covers what you need.

### Key Tools (code-review-graph)

| Tool | Use when |
| ------ | ---------- |
| `code-review-graph_detect_changes_tool` | Reviewing code changes — gives risk-scored analysis |
| `code-review-graph_get_review_context_tool` | Need source snippets for review — token-efficient |
| `code-review-graph_get_impact_radius_tool` | Understanding blast radius of a change |
| `code-review-graph_get_affected_flows_tool` | Finding which execution paths are impacted |
| `code-review-graph_query_graph_tool` | Tracing callers, callees, imports, tests, dependencies |
| `code-review-graph_semantic_search_nodes_tool` | Finding functions/classes by name or keyword |
| `code-review-graph_get_architecture_overview_tool` | Understanding high-level codebase structure |
| `code-review-graph_refactor_tool` | Planning renames, finding dead code |

### Key Tools (codebase-memory-mcp)

| Tool | Use when |
| ------ | ---------- |
| `codebase-memory-mcp_search_graph(query=...)` | Finding functions/classes by name or semantic search |
| `codebase-memory-mcp_trace_path()` | Tracing callers, callees, data flow |
| `codebase-memory-mcp_query_graph()` | Complex Cypher queries for multi-hop patterns |
| `codebase-memory-mcp_get_architecture()` | High-level project structure and clusters |
| `codebase-memory-mcp_detect_changes()` | Detecting code changes and their impact |
| `codebase-memory-mcp_get_code_snippet()` | Reading source for a specific function/class |
| `codebase-memory-mcp_search_code()` | Graph-augmented search with structural enrichment |

### Workflow

1. The code-review-graph does NOT auto-update on file changes. You MUST run `code-review-graph_build_or_update_graph_tool` or
`code-review-graph_detect_changes_tool` to update the graph with recent edits before querying it.
2. Use `code-review-graph_detect_changes_tool` / `codebase-memory-mcp_detect_changes()` for code review.
3. Use `code-review-graph_get_affected_flows_tool` / `codebase-memory-mcp_trace_path()` to understand impact.
4. Use `code-review-graph_query_graph_tool` pattern="tests_for" / `codebase-memory-mcp_search_graph(label="Test")` to check coverage.
