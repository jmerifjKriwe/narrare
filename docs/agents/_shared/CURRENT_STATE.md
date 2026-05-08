# Narrare — Current State

> **This document is the live status of the project.**
> Every agent reads this at the start of every session.
> Updated at the end of every session by the responsible agent.
>
> Location: `docs/agents/_shared/CURRENT_STATE.md`

---

## Last Updated

Date: project-init+1
Updated by: Architecture Agent
Session summary: Q-004 (arq) and Q-005 (Z.AI) resolved. German demo content
confirmed. Documentation Agent defined. CODING_STANDARDS created. All 6
initial agents complete. ADR-007 added.

---

## Project Phase

```
Phase 0: Repository Foundation     ← NEXT — unblocked
Phase 1: Core Infrastructure       · not started
Phase 2: API Foundation            · not started
Phase 3: Setup Wizard Backend      · not started
Phase 4: Frontend Foundation       · not started
Phase 5: Integration & Polish      · not started
```

---

## What Exists Right Now

### Documentation (complete)

**Shared Foundation (`docs/agents/_shared/`):**
- `CONSTRAINTS.md` — 13 rules, CI-enforced
- `PROJECT_VISION.md` — why, what, for whom
- `TECH_STACK.md` — canonical technology decisions (Celery → arq updated)
- `GLOSSARY.md` — shared vocabulary
- `MVP_PLAN.md` — 5-phase plan for first running version
- `CURRENT_STATE.md` — this file
- `DIRECTORY_STRUCTURE.md` — canonical file locations

**Agents (`docs/agents/`):**
- `orchestrator/ORCHESTRATOR_AGENT.md` — thinking partner + router
- `architecture/AGENT.md` — system architect, guardian of constraints
- `implementation/IMPLEMENTATION_AGENT.md` — writes production code
- `implementation/CODING_STANDARDS.md` — Python 3.14 + TypeScript standards
- `testing/TESTING_AGENT.md` — owns test quality and coverage
- `ui/UI_AGENT.md` — frontend, UX consistency
- `deployment/DEPLOYMENT_AGENT.md` — CI/CD, dev environment, release
- `documentation/DOCUMENTATION_AGENT.md` — feature docs, UI help texts, changelog

**ADRs (`docs/agents/architecture/decisions/`):**
- `INDEX.md`
- `ADR-001` LLM Gateway
- `ADR-002` Unified Prompt System
- `ADR-003` Protocol-First Development
- `ADR-004` Hard File Size Limits
- `ADR-005` Directory Structure
- `ADR-006` Technology Stack
- `ADR-007` arq for Background Tasks ← new

**Open Questions (`docs/agents/architecture/questions/`):**
- `INDEX.md`
- `Q-001` MCP auth strategy (🟡 open — not blocking MVP)
- `Q-002` A2A streaming (🟡 open — not blocking MVP)
- `Q-003` Embedding provider abstraction (🟡 open — not blocking MVP)
- `Q-004` Celery vs arq (✅ resolved → arq, see ADR-007)
- `Q-005` GLM/pydantic-ai/Z.AI (✅ resolved → OpenAI-compatible, no custom adapter)

**Feature Registry (`docs/features/`):**
- `INDEX.md` — 40+ features catalogued
- `_TEMPLATE.md`
- `SETUP-001` Setup Wizard — fully specified
- `SETUP-002` Demo Projects — fully specified, German content confirmed
- `WRITE-001` Writing Editor — fully specified with extension architecture

### Demo Content (partial)

**German demo ("Im stillen Wald") — confirmed exists:**
- Chapter 1: "Das Flüstern im Wald" (~680 words) ✅
- KB: Der Waldgeist (draft) ✅
- KB: Das Försterhaus (draft) ✅
- KB: Anna Müller — notes exist, structured entry needed 📋
- KB: Johann Bauer — notes exist, structured entry needed 📋
- KB: Der stille Wald — to be written 📋
- Chapter 2 — to be written 📋

**Fantasy demo ("Echoes of the Thornwall")** — not yet created 📋
**SciFi demo ("Dead Signal")** — not yet created 📋

### Code

None. Repository has not been initialized.

---

## What Is In Progress

Nothing. Documentation phase complete. Ready for Phase 0.

---

## What Is Blocked

Nothing blocking Phase 0.

Phase 3 (Setup Wizard Backend) will need complete demo content before it
can be finished — but Phase 0–2 can proceed without it.

---

## Resolved Since Last Update

| Item | Resolution |
|------|-----------|
| Q-004 Celery vs arq | → arq. ADR-007 created. TECH_STACK.md to be updated. |
| Q-005 GLM/Z.AI/pydantic-ai | → OpenAI-compatible endpoints. Factory function in `core/llm/_providers/zai.py`. |

---

## Decisions Made (full log in ADR files)

| ADR | Decision | Status |
|-----|---------|--------|
| ADR-001 | Single LLM Gateway | ✅ |
| ADR-002 | Unified Prompt System | ✅ |
| ADR-003 | Protocol-First Development | ✅ |
| ADR-004 | Hard File Size Limits | ✅ |
| ADR-005 | Directory Structure & Module Ownership | ✅ |
| ADR-006 | Technology Stack | ✅ |
| ADR-007 | arq for Background Tasks | ✅ |

---

## Open Questions (summary)

| ID | Question | Status | Blocks |
|----|---------|--------|--------|
| Q-001 | MCP auth strategy | 🟡 Open | apps/mcp/ |
| Q-002 | A2A streaming requirement | 🟡 Open | apps/a2a/ |
| Q-003 | Embedding provider abstraction | 🟡 Open | core/llm/embeddings.py |
| Q-004 | Celery vs arq | ✅ Resolved | — |
| Q-005 | GLM/Z.AI compatibility | ✅ Resolved | — |

---

## Next Session Should Start With

**Deployment Agent leads Phase 0: Repository Foundation**

Checklist for Phase 0 (nothing is done until all items are checked):
```
□ Monorepo directory structure matches DIRECTORY_STRUCTURE.md exactly
□ pyproject.toml — Python 3.14, all deps with current versions, pyright config
□ pnpm workspace configured
□ justfile — all commands from DEPLOYMENT_AGENT.md implemented
□ .pre-commit-config.yaml — all hooks including check_architecture.py
□ .devcontainer/ — Dockerfile + devcontainer.json + post-create.sh
□ docker-compose.dev.yml — postgres (pgvector/pgvector:pg17) + redis:8-alpine
□ release-please configuration
□ .github/workflows/ci.yml — full pipeline
□ .github/workflows/architecture.yml — fast constraint check
□ .github/workflows/release-please.yml
□ scripts/check_architecture.py — full implementation
□ pyrightconfig.json
□ .env.example
□ Initial CHANGELOG.md
□ README.md with setup instructions
□ `just dev-setup` runs clean on empty machine
□ `just check` passes (nothing to check yet, but pipeline works)
```

**Architecture Agent reviews directory structure** before Phase 0 is marked complete.

---

## Known Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Python 3.14 missing type stubs for some deps | Low | Low | `reportMissingTypeStubs = false` in pyrightconfig |
| TipTap v3 extension API changes before Phase 4 | Low | Medium | Pin exact version in package.json |
| German demo chapter 2 quality | Medium | Low | Can be improved post-MVP without affecting architecture |
| Fantasy/SciFi demo content not ready for Phase 3 | Medium | Low | German demo alone is sufficient for MVP testing |
