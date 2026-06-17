# Narrare — Open Code Instructions

> **SSOT Notice:** Architecture rules are authoritatively defined in
> `docs/_shared/CONSTRAINTS.md`. The summaries below are for quick orientation
> only — if any summary contradicts CONSTRAINTS.md, the CONSTRAINTS rule wins.
> See CONSTRAINTS.md §8 for the full SSOT hierarchy.

## Code Knowledge Graph — MANDATORY

This project has a code knowledge graph via code-review-graph MCP tools.
**ALWAYS query the graph BEFORE using Read/Glob/Grep.**

| Need | Use | NOT |
|------|-----|-----|
| Find code | `code-review-graph_semantic_search_nodes_tool` | Grep |
| Who calls X? | `code-review-graph_query_graph_tool callers_of` | Read + scan |
| Impact analysis | `code-review-graph_get_impact_radius_tool` | Manual tracing |
| Architecture | `code-review-graph_get_architecture_overview_tool` | Directory listing |
| Review changes | `code-review-graph_detect_changes_tool` | Reading full files |
| Tests for X | `code-review-graph_query_graph_tool tests_for` | Glob |
| Quick context | `code-review-graph_get_minimal_context_tool` | Multiple reads |

Read/Glob/Grep are LAST RESORTS — only when the graph lacks the data.

Full standard: `.opencode/context/narrare-dev/standards/code-graph-first.md`

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

Alle 13 Regeln: `docs/_shared/CONSTRAINTS.md`
Enforcement: `scripts/check_architecture.py` (läuft in pre-commit und CI)

---

## Rules — Verbindliche Standards

Narrare verwendet `.claude/rules/` für path-scoped, automatisch geladene Regeln.

| Rule | Scope | Purpose |
|------|-------|---------|
| `constraints.md` | Global | Die 13 RULE-XX Architektur-Regeln |
| `python/code-style.md` | `**/*.py` | Python Syntax, Naming, Imports |
| `python/async.md` | `apps/api/**/*.py`, `core/**/*.py` | Async-Patterns |
| `typescript/code-style.md` | `packages/web/**/*.{ts,tsx}` | TS/React Patterns |
| `ui/principles.md` | `packages/web/**/*.tsx` | UX-Principles |
| `testing/unit.md` | `tests/unit/**/*.py` | Unit-Test Regeln |
| `testing/integration.md` | `tests/integration/**/*.py` | Integration-Test Regeln |

**Rules werden automatisch geladen** — kein manuelles Lesen nötig.
**Docs bleiben die Quelle** — Rules referenzieren docs für Details.

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
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `code-review-graph_semantic_search_nodes_tool` or `code-review-graph_query_graph_tool` instead of Grep
- **Understanding impact**: `code-review-graph_get_impact_radius_tool` instead of manually tracing imports
- **Code review**: `code-review-graph_detect_changes_tool` + `code-review-graph_get_review_context_tool` instead of reading entire files
- **Finding relationships**: `code-review-graph_query_graph_tool` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `code-review-graph_get_architecture_overview_tool` + `code-review-graph_list_communities_tool`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

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

### Workflow

1. The graph does NOT auto-updates on file changes. You MUST run `code-review-graph_build_or_update_graph_tool` or
`code-review-graph_detect_changes_tool` to update the graph with recent edits before querying it.
2. Use `code-review-graph_detect_changes_tool` for code review.
3. Use `code-review-graph_get_affected_flows_tool` to understand impact.
4. Use `code-review-graph_query_graph_tool` pattern="tests_for" to check coverage.
