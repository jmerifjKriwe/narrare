# Narrare — Open Code Instructions

> **SSOT:** Architectural rules live in `docs/_shared/CONSTRAINTS.md` (23 RULE-XX).
> If anything below contradicts CONSTRAINTS.md, CONSTRAINTS wins. Load it on demand.

## Project

Narrare is an AI-assisted, local-first creative writing tool. Stack:
Python 3.14 · FastAPI · SQLAlchemy 2.0 async · pydantic-ai · PostgreSQL+pgvector ·
mem0 OSS · Next.js 16 · TipTap v3 · TypeScript · Tailwind v4.
Background jobs run in-process (asyncio), no Redis/TaskIQ (see @docs/_shared/TECH_STACK.md).

```
apps/api/        FastAPI Backend        packages/core/   Domain logic (LLM, Prompts, KB)
packages/web/    Next.js Frontend       packages/i18n/    Translations
docs/            Documentation (SSOT)   scripts/          Dev tooling
```

## Tools: Code Graph & Memory

**graphify** (code knowledge graph) — use it BEFORE Read/Glob/Grep for code questions:
- Find code / understand relationships → `graphify query "<question>"` (MCP tool `query_graph` or CLI)
- Path between two symbols → `graphify path A B` / MCP `shortest_path`
- Explain a symbol → `graphify explain "<name>"` / MCP `get_node` + `get_neighbors`
- Broad architecture overview → `graphify-out/GRAPH_REPORT.md` (if present)
- Graph stale? → `/graph-update` (incremental rebuild, local, no API key for code)

**opencode-mem** (cross-session memory) — project decisions, bug patterns, and preferences
relevant across sessions:
- Store/search immediately → `memory` tool (`mode: add|search|profile|list`)
- Auto-capture runs in the background (no manual call needed)
- Web UI: `http://127.0.0.1:4747`

Read/Glob/Grep are allowed for: string literals, non-code files, config values, or when
the graph does not have the answer. `sed -n` is allowed to read specific lines.

## Hard rules (always)

- **Project language: English.** Write source code, comments, docstrings, tests, `docs/`,
  and `scripts/` in English — regardless of the language you (the dev) use to talk to your
  AI. When you encounter German/other formulations, convert them to English on the fly.
  Exception: i18n message files (`packages/i18n/`). See `@docs/development/coding-standards.md`
  § Project Language.
- **RULE-01b** Agents/ModelRegistry; no direct `import openai` outside `core/llm/`,
  no `pydantic_ai.Agent` outside `core/agents/`.
- **RULE-02/02a/02b** Prompts only in `core/prompts/`, no f-strings in services.
- **RULE-03** Contract (Protocol) before implementation.
- **RULE-04** Modularize instead of compressing (hard limits → new module).
- **RULE-06** One responsibility per file. Router delegates immediately, no logic in the router.
- All 23 rules: `@docs/_shared/CONSTRAINTS.md`

## Working principles

1. **Understand before modifying.** Read code / trace the graph before writing.
2. **Plan non-trivial changes.** Root cause (≥2× "why?"), alternatives, sustainability.
3. **Follow existing patterns.** New patterns only with justification.
4. **Verify.** Tests, lint, typecheck, `scripts/check_architecture.py`.
5. **Review non-trivial changes** (Reviewer subagent, edit: deny).

### Prohibitions (absolute)

- `git commit --no-verify` / `-n` is FORBIDDEN (unless the user approves explicitly + actively).
- Quick fixes, workarounds, symptomatic patches. Every change needs root-cause analysis.
- `git reset --hard`, `git clean -fd`, `git push --force`, `sudo`, `rm -rf /` — blocked in general.
- Implementation without a prior architecture spec for new modules/boundaries.

### Git & escalation

- Git/gh writes (add, commit, push, tag, rebase, `gh *`) **only via NarrarePlatformSpecialist**.
- Command blocked? Coordinator routes to Platform (NOT to `general`).
- `general` is the last-resort escape hatch on `ask` (user approval), not a default path.

## Subagents (via `task`)

| Role | subagent_type | Model |
|------|---------------|-------|
| Coordinator (primary) | `NarrareDevCoordinator` | zai-coding-plan/glm-5.2 |
| Architecture | `NarrareArchitectureSpecialist` | zai-coding-plan/glm-5.2 |
| Core | `NarrareCoreSpecialist` | zai-coding-plan/glm-5.2 |
| Backend | `NarrareBackendSpecialist` | zai-coding-plan/glm-5.2 |
| Frontend | `NarrareFrontendSpecialist` | zai-coding-plan/glm-5.2 |
| Platform (Git/CI) | `NarrarePlatformSpecialist` | zai-coding-plan/glm-5.2 |
| Docs | `NarrareDocsSpecialist` | zai-coding-plan/glm-5-turbo |
| Reviewer (edit: deny) | `NarrareReviewerSpecialist` | zai-coding-plan/glm-5.2 |

Layer order: Architecture → Core → Backend → Frontend → Platform (Tests/CI) → Docs.
Each subagent loads its layer standards via the delegation prompt.

## Knowledge (lazy load on demand)

Load these files only when the task needs them — not preemptively:

- Current state: @docs/_shared/CURRENT_STATE.md
- All architecture rules: @docs/_shared/CONSTRAINTS.md
- Tech stack: @docs/_shared/TECH_STACK.md
- Glossary: @docs/_shared/GLOSSARY.md
- Coding Standards: @docs/development/coding-standards.md
- Testing Standards: @docs/development/testing-standards.md
- UI Principles: @docs/development/ui-principles.md
- Deployment: @docs/development/deployment-guide.md
- ADR index: @docs/architecture/decisions/INDEX.md
- Open Questions: @docs/architecture/questions/INDEX.md
- Feature index: @docs/features/INDEX.md
- Sub-AGENTS: @apps/api/AGENTS.md · @packages/core/AGENTS.md · @tests/AGENTS.md

## Slash commands

`/check-constraints` `/graph-update` `/debug-issue` `/review-changes` `/refactor-safely`
`/verify` `/skills-update` (in `.opencode/commands/`).

## Skills

Process skills (TDD, systematic-debugging, verification, …) live in `.opencode/skills/`
(vendored). Technology skills in `.agents/skills/`. Load them on demand via the `skill`
tool when the task fits — not preemptively.
