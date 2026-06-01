# Narrare — Current State

> This document is the live status of the project.
> Every agent reads this at the start of every session.

---

## Last Updated

Date: 2026-06-01
Session: Phase 6 extension — ANAL-003 (Readability), ANAL-004 (POV) full stack implemented, contracts modularized for RULE-04

---

## Project Phase

Phase 0: Repository Foundation     ✅ COMPLETE
Phase 1: Core Infrastructure       ✅ COMPLETE
Phase 2: API Foundation            ✅ COMPLETE
Phase 3: Setup Wizard Backend      ✅ COMPLETE
Phase 4: Frontend Foundation       ✅ COMPLETE
Phase 5: Integration & Polish      ✅ COMPLETE
Phase 6: Post-MVP Features         ⏳ IN PROGRESS

---

## Codebase Overview

### Stats (verified 2026-05-29)

- Knowledge Graph: 12,613 nodes, 92,243 edges, 1,241 files, 5,932 test nodes
- Backend tests: 4,273 (3,750 unit + 495 integration) across 396 test files
- Frontend tests: ~5,000 across 165 test files (Vitest + MSW)
- Total tests: ~9,200+
- Architecture rules: 22 rules (RULE-01 through RULE-21, plus RULE-01b)
- ADRs: 23 (ADR-001 through ADR-023, inkl. ADR-022 LLM Wiki — Accepted, ADR-023 Co-Author Change Engine — Implemented)
- Feature specs: 75 individual files + INDEX.md
- Open questions: 8 (Q-001 through Q-008)

### Core (`packages/core/narrare_core/`)

17 submodules: agents, analysis, cache, context, embeddings, events, kb, llm, memory, nlp, planning, prompts, schemas, shared, templates, writing

18 AI agents (pydantic-ai): beta_reader, character_arc, consistency, draft, extraction, inline_suggest, kb, kb_assist, kb_improve, merge (KBMergeAgent), outline, pov_detection, preference_analysis, readability, review, summary, timeline, worldbuilding

### Backend (`apps/api/narrare/`)

20 domain modules: analysis, auth, chapters, consistency, embeddings, events, generation, kb, memory, metrics, novels, planning, prompts, settings, setup, tasks, templates, volumes, writing (+ _app infrastructure)

38 router files covering all CRUD + SSE + WebSocket endpoints

Alembic migrations 0001 through ~0023

### Frontend (`packages/web/`)

- Next.js 16 App Router with TipTap v3 editor
- 3 demo novels (de: "Im stillen Wald", en: "Echoes of the Thornwall", en: "Dead Signal")
- Key UI areas: Dashboard, Setup Wizard (5-step), Editor (full TipTap + chapters + context panel), Settings, Worldbuilding (3-column KB browser), Storyboard, Generation, Analysis panels
- Custom TipTap extensions: NarrareDocument, SceneBreak, DialogueMark, Autosave, GhostText (inline suggestions), AIAnnotation (modify tracking)
- State: TanStack Query (server) + Zustand (UI) + useState (ephemeral)
- i18n: 3 locales (en, de, fr) via next-intl

### Documentation (`docs/`)

- `_shared/`: CONSTRAINTS.md (22 rules), TECH_STACK.md, GLOSSARY.md, CURRENT_STATE.md
- `development/`: coding-standards, testing-standards, ui-principles, deployment-guide, orchestrator
- `architecture/decisions/`: 22 ADRs + 2 implementation plans (inkl. ADR-022 LLM Wiki — Accepted) (INDEX.md)
- `architecture/questions/`: 8 questions in 5 files (INDEX.md)
- `features/`: 76 feature spec files (INDEX.md with status tracking)
- **WIKI-001** — LLM Wiki (Precomputed Context Layer, backend implemented, frontend pending)
- `mvp/`: Product roadmap (Phases 0–6 + Post-MVP)

### Infrastructure

- `scripts/check_architecture.py` — CI-enforced constraint validation
- `.github/workflows/` — CI, architecture check, release, promptfoo evals (nightly)
- Docker Compose: PostgreSQL (pgvector) + Redis + pgBouncer (prod profile)
- OpenTelemetry + Langfuse for LLM observability
- promptfoo eval framework (`evals/`) for prompt quality regression

---

## Phase 6 — In Progress

Completed in Phase 6 so far:

1. ✅ WRITE-003: Extend Chapter — ExtendService + SSE + AIAnnotation TipTap
2. ✅ WRITE-004: Rewrite Selection — RewriteService + SSE + AlternativeParser + InlineDiff
3. ✅ INFRA-004: Embedding Store — pgvector embeddings + KB hooks + usage tracking
4. ✅ KB-002: Assisted KB Creation — KBAssistAgent + session flow + SSE
5. ✅ KB-003: AI Improve KB Entry — KBImproveAgent + analyze/apply
6. ✅ KB-005: Proactive Context — ProactiveContextService + hybrid scoring
7. ✅ KB-006a: Worldbuilding View — 3-column KB browser
8. ✅ KB-007: Extraction — ExtractionAgent + endorse/reject UI
9. ✅ WRITE-007: Inline AI Suggestions — InlineSuggestAgent + GhostText TipTap extension
10. ✅ ANAL-001: Beta Reader Simulation — BetaReaderAgent + ScoreRadar + 4-tab panel
11. ✅ ANAL-002: Sentiment Analysis — LexiconSentimentAnalyzer + arc trajectory graphs
12. ✅ CONS-001: Consistency Checker — ConsistencyAgent + rule-based pre-check + actions
13. ✅ SET-005: Configurable Token Limits — 3-layer resolution cascade
14. ✅ CR-01 through CR-04: Prompt quality audits + preference wiring + meta-prompt guardrails
15. ✅ Coverage Uplift: 1,045+ new tests across all layers
16. ✅ ADR-016: Prompt Caching — Implemented across all 4 phases (Phase 0: AgentRegistry, Phase 1: CacheSettings+ModelSettings, Phase 2: Cache Observability, Phase 3: WritingGraph Backend DI)
17. ✅ ADR-017: Embedding Cascade — Implemented
18. ✅ ADR-018: Promptfoo Eval Framework — Implemented
19. ✅ ADR-019: System-Prompt Consistency — Accepted
20. ✅ ADR-020: Embedding Provider Abstraction — Accepted
21. ✅ ADR-021: Deterministic Analysis Strategy — Accepted
22. ✅ ADR-022: LLM Wiki — Precomputed Context Layer (Core: contracts, agent, service, prompt_loader, types; Backend: models, migration, repository (9 methods), schemas (6), API service, router (6 endpoints), tasks (4), listeners (4), DI wiring; Context assembler wiki integration, budget wiki optimization; 35 core + 9 backend unit tests)
23. ✅ WRITE-006 / ADR-023: Co-Author Change Engine — apply_changes (stateless text reconstruction), batch feedback (LEARN-001), SET-005 cascade (word-count validation), per-change accept/reject UI, 34 new tests
24. ✅ PLAN-006: Character Arc Analysis — CharacterArcAgent, CharacterArcService, `POST /planning/character-arc/{novel_id}`, prompts in 3 locales
25. ✅ PLAN-004 Phase 4: Timeline Analysis — TimelineAgent, TimelineService, `GET /planning/timeline/{novel_id}`, timeline prompts in 3 locales, chapter summary gathering
26. ✅ KB-009: KB Entity Merge / Deduplication — KBMergeAgent, KBMergeService, `POST /novels/{novel_id}/kb/merge`, merge prompts in 3 locales
27. ✅ Planning prompt extensions: outline (`{{variant_count}}`), character_arc (`{{character_name}}`, `{{character_current_state}}`, `{{character_goal_state}}`), timeline (`{{chapter_summaries}}`, `{{entity_events}}`)
28. ✅ CI integration: Prompts step added to `just check` (strict mode), check-prompts-de added to `check-full`
29. ✅ WIKI-001: LLM Wiki — Spec updated to stable (all DoD items complete)
30. ✅ ANAL-003: Readability Analysis — FormulaReadabilityAnalyzer (Flesch/Kincaid/Fog) + ReadabilityAgent + ReadabilityService + POST /analysis/readability + ReadabilityPanel + i18n (3 locales)
31. ✅ ANAL-004: POV Analysis — POVDetectionAgent + POVService + POST /analysis/pov + POVPanel + i18n (3 locales)
32. ✅ Contracts modularized for RULE-04: contracts_readability.py, contracts_pov.py, schemas_readability.py, schemas_pov.py, pov_mapper.py

---

## What's Next

1. Editor integration: Wire ReadabilityPanel + POVPanel into editor sidebar analysis tray
2. WIKI-001 frontend: Wiki overview page (entity list with wiki status)
3. ANAL-005: Coreference Analysis
4. E2E test patterns

---

## Decisions (summary)

| ADR | Decision | Status |
|-----|---------|--------|
| ADR-001 | Single LLM Gateway | ✅ Implemented |
| ADR-002 | Unified Prompt System | ✅ Implemented |
| ADR-003 | Protocol-First Development | ✅ Applied |
| ADR-004 | Hard File Size Limits | ✅ Enforced |
| ADR-005 | Directory Structure & Module Ownership | ✅ Applied |
| ADR-006 | Technology Stack | ✅ Applied |
| ADR-007 | TaskIQ for Background Tasks | ✅ Decided |
| ADR-008 | Frontend Stack | ✅ Applied |
| ADR-009 | Security Modernization (argon2 + fastapi-limiter) | ✅ Implemented |
| ADR-010 | Observability (OpenTelemetry + Langfuse) | ✅ Implemented |
| ADR-011 | Content Versioning | ✅ Implemented |
| ADR-012 | Event-Driven Architecture (Redis Pub/Sub) | ✅ Implemented |
| ADR-013 | Internationalization | ✅ Implemented |
| ADR-014 | RULE-14: Model-Migration Consistency | ✅ Enforced |
| ADR-015 | Pydantic-AI Agents as First-Class Citizens | ✅ Accepted |
| ADR-016 | Prompt Caching Strategy | ✅ Implemented (all 4 phases) |
| ADR-017 | Embedding Cascade for mem0 | ✅ Implemented |
| ADR-018 | Promptfoo Eval Framework | ✅ Implemented |
| ADR-019 | System-Prompt Consistency for Agents | ✅ Accepted |
| ADR-020 | Embedding Provider Abstraction | ✅ Accepted |
| ADR-021 | Deterministic Analysis Strategy | ✅ Accepted |
| ADR-022 | LLM Wiki — Precomputed Context Layer: core/wiki/ module, TaskIQ-generated WikiSummaries, Prompt versioning, stale/fresh/pending, 9 repository methods, 6 API endpoints, 4 background tasks, 4 event listeners, wiki-optimized token budget. WIKI-001 Feature Spec. | ✅ Accepted (Full backend implemented, frontend pending) |
| ADR-023 | Co-Author Change Engine | ✅ Implemented |

Full details: `docs/architecture/decisions/INDEX.md`

---

## Open Questions

| ID | Question | Status |
|----|---------|--------|
| Q-001 | MCP auth strategy | 🟡 Open |
| Q-002 | A2A streaming requirement | 🟡 Open |
| Q-003 | Embedding provider abstraction | 🟡 Open |
| Q-004 | Celery vs arq | ✅ → TaskIQ |
| Q-005 | GLM/Z.AI compatibility | ✅ → OpenAI-compatible |
| Q-006 | Configurable Model Routing | ✅ → Runtime cascade |
| Q-007 | Writing context data loader | 🟡 Open |
| Q-008 | Auth store hydration | 🟡 Open |

Full details: `docs/architecture/questions/INDEX.md`

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Python 3.14 missing type stubs | Low | Documented in pyproject.toml |
| TipTap v3 API changes | Medium | Pin exact version |
| Editor h-full in flex container | Low | Follow DashboardView pattern |

---

> Maintained by: Coordinator, updated at session end
