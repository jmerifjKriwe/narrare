# Narrare — Current State

> This document is the live status of the project.
> Every agent reads this at the start of every session.

---

## Last Updated

Date: 2026-06-03 (Session 2)
Session: Audit Review-05 Umsetzung — 9 Tasks aus Review-05-Release in 4 Wellen abgeschlossen. CI-Permissions minimiert (read-only Defaults). SSOT-Hierarchie in CONSTRAINTS.md §8 etabliert. Gate-Konformitäts-Audit (check_locale_sync blocking, check_streaming schon blocking). System-Health-Metrik (0.73 DEGRADED). Release-SBOM generiert. Observability-Trace-Kette dokumentiert + 22 Integration-Tests. Q-011 Distribution-Strategie dokumentiert. Ausnahmen-Sync CONSTRAINTS.md ↔ pyproject.toml.

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

### Stats (verified 2026-06-03)

- Knowledge Graph: 15,407 nodes, 112,382 edges, risk medium
- Backend tests: 4,273 (3,750 unit + 495 integration) across 396 test files
- Frontend tests: ~5,000 across 165 test files (Vitest + MSW)
- Total tests: ~9,200+
- Architecture rules: 22 rules (RULE-01 through RULE-21, plus RULE-01b)
- ADRs: 24+ (ADR-001 through ADR-023, plus ADR-027 AI Feature Stabilization Gates)
- Feature specs: 75 individual files + INDEX.md
- Open questions: 11 (Q-001 through Q-011)

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
- `architecture/questions/`: 11 questions in 6 files (INDEX.md)
- `features/`: 76 feature spec files (INDEX.md with status tracking)
- **WIKI-001** — LLM Wiki (Precomputed Context Layer, fully implemented) ✅
- **PLAN-004** — Timeline Management (vollständig: DB → CRUD → AI analysis → SSE extraction → confirm endpoint → DurationImpossibilityCheck → LLM consistency via bundled prompt → character ages → visualization, 44 files, DoD-100%) ✅
- `mvp/`: Product roadmap (Phases 0–6 + Post-MVP)

### Infrastructure

- `scripts/check_architecture.py` — CI-enforced constraint validation
- `scripts/check_system_health.py` — Aggregierte System-Health-Metrik (HEALTHY/DEGRADED/CRITICAL)
- `scripts/health_types.py` + `health_format.py` — Health-Score-Typen und Formatierer
- `apps/api/narrare/_app/observability.py` — Zentraler Trace-Context-Helper
- `docs/development/observability-guide.md` — End-to-End Observability-Trace-Kette dokumentiert
- `.github/workflows/` — CI (gated: 16 blocking, 1 warning coverage), architecture check, release (mit SBOM), promptfoo evals (nightly)
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
33. ✅ WIKI-001 frontend: WikiOverviewPanel (entity summaries + status overview), WikiChapterSummaryPanel (chapter wiki in editor), KBCategorySidebar wiki tab, WorldBuilding wiki mode, 22 i18n keys (en/de/fr), 16 Vitest tests
34. ✅ PLAN-004 vollständig und komplett — alle Phase 1–3 DoD-Lücken geschlossen: DurationImpossibilityCheck (3 Checks: same-character-location, death-before-birth, impossibly-fast-travel), POST /{novel_id}/extract SSE streaming, POST /{novel_id}/extract/confirm endpoint, LLM consistency via bundled prompt (RULE-02 fix), Frontend ExtractionReview mit SSE+Confirm (kein createEvent mehr), timeline_contracts.py (RULE-04), duration_check.py + age_check.py extrahiert. 44 Files, +3k Zeilen, +4 RULE-04 Modularisierungen.

---

## What's Next

1. ❌ **Backend-Unit-Failures beheben (AUFG-02-01)** — 7 Test-Failures in Prompt-Integrity und Streaming-Compliance müssen vor dem Freeze-Lift behoben werden.
2. ❌ **Prompt-Warnungen abbauen (AUFG-03-01)** — 79 Prompt-Structure-Warnungen auf dem Weg zu Score ≥0.85.
3. ❌ **KB-Adoption über 0.85 (AUFG-03-02)** — KB-Score von 0.78 auf ≥0.85 heben.
4. ❌ **Frontend-Hubs modularisieren (AUFG-01-02)** — EditorView, TipTapEditor, GhostText, API-Clients.
5. ❌ **Frontend-Tests beschleunigen (AUFG-02-03)** — Vitest von 213s auf <120s.
6. ⏳ **E2E test patterns**
7. ⏳ **ANAL-005: Coreference Analysis** — resumes only after INFRA-011 stabilization gates pass or an explicit Architecture-reviewed exception is approved.

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
| ADR-022 | LLM Wiki — Precomputed Context Layer: core/wiki/ module, TaskIQ-generated WikiSummaries, Prompt versioning, stale/fresh/pending, 9 repository methods, 6 API endpoints, 4 background tasks, 4 event listeners, wiki-optimized token budget. WIKI-001 Feature Spec. | ✅ Implemented (full stack) |
| ADR-023 | Co-Author Change Engine | ✅ Implemented |
| ADR-027 | AI Feature Stabilization Gates | ✅ Accepted — new AI features frozen until INFRA-011 gates pass and freeze-lift review completes |

Full details: `docs/architecture/decisions/INDEX.md`

---

## Open Questions

| ID | Question | Status |
|----|---------|--------|
| Q-001 | MCP auth strategy | 🟡 Open |
| Q-002 | A2A streaming requirement | 🟡 Open |
| Q-003 | Embedding provider abstraction | ✅ → ADR-020 |
| Q-004 | Celery vs arq | ✅ → TaskIQ |
| Q-005 | GLM/Z.AI compatibility | ✅ → OpenAI-compatible |
| Q-006 | Configurable Model Routing | ✅ → Runtime cascade |
| Q-007 | Writing context data loader | ✅ → WritingContextAssembler |
| Q-008 | Auth store hydration | ✅ → AuthProvider.tsx |
| Q-009 | Chat conversations: project-scoped vs user-scoped | 🟡 Open |
| Q-010 | Chat prompt i18n: EN-only v1 vs full i18n | 🟡 Open |
| Q-011 | Distribution strategy for non-technical users | 🟡 Open |

Full details: `docs/architecture/questions/INDEX.md`

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Python 3.14 missing type stubs | Low | Documented in pyproject.toml |
| TipTap v3 API changes | Medium | Pin exact version |
| Editor h-full in flex container | Low | Follow DashboardView pattern |
| System Health Score 0.73 (DEGRADED) | Medium | CI-Check (warning-only bei DEGRADED, fail bei CRITICAL). Baseline-Items abbauen für ≥0.85 |
| 6 offene Audit-Tasks (AUFG-02-01, -03-01, -03-02, -01-02, -02-03) | Medium | Blockieren Freeze-Lift. Separate Sprints nötig |

---

> Maintained by: Coordinator, updated at session end
