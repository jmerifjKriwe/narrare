# Narrare — Current State

> This document is the live status of the project.
> Every agent reads this at the start of every session.

---

## Last Updated

Date: 2026-06-04 (Session 6)
Session: Documentation gate coverage expansion + test coverage uplift (sentiment, syllables, spaCy, wiki, memory ADR-030). Phase 1 (Streaming + Prompts): removed deprecated timeline REST wrapper and unused KB sessions SSE endpoint; fixed streaming-compliance checker for nested routers; added streaming pre-commit hook; added required prompt variables to analysis/pov, analysis/readability, planning/temporal_consistency. Phase 2 (Structure): removed RULE-02 f-string exception from KB consistency analyzer (prompt moved to bundled core prompts); modularized EditorView.tsx from 764→146 lines into 14 focused modules; updated exception registers. Phase 3 (Privacy + Observability): changed KB interview resume from localStorage to sessionStorage; added module-level OTel degradation visibility with one-shot warning and health-endpoint status. Streaming compliance now 0 violations. Frontend RULE-04 violations: 38→37. Architecture exceptions: 14→13 (RULE-02 exception #3 removed).

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

### Stats (verified 2026-06-04)

- Knowledge Graph: 15,527 nodes, 112,368 edges, risk medium
- Backend tests: ~4,500 (approx. 3,976 unit + 495 integration) across 405 test files
- Frontend tests: 1,683 across 186 test files (Vitest + MSW)
- Total tests: ~6,200+
- Architecture rules: 22 rules (RULE-01 through RULE-21, plus RULE-01b)
- Architecture exceptions: 13 registered (was 14; RULE-02 exception #3 removed via bundled prompt)
- ADRs: 30 (ADR-001 through ADR-030; ADR-030 MagicMock-to-Fake migration implemented)
- Feature specs: 75 individual files + INDEX.md
- Open questions: 11 (Q-001 through Q-011)

### Core (`packages/core/narrare_core/`)

17 submodules: agents, analysis, cache, context, embeddings, events, kb, llm, memory, nlp, planning, prompts, schemas, shared, templates, writing

18 AI agents (pydantic-ai): beta_reader, character_arc, consistency, draft, extraction, inline_suggest, kb, kb_assist, kb_improve, merge (KBMergeAgent), outline, pov_detection, preference_analysis, readability, review, summary, timeline, worldbuilding

### Backend (`apps/api/narrare/`)

20 domain modules: analysis, auth, chapters, consistency, embeddings, events, generation, kb, memory, metrics, novels, planning, prompts, settings, setup, tasks, templates, volumes, writing (+ _app infrastructure)

37 router files covering all CRUD + SSE + WebSocket endpoints (KB sessions SSE removed — unused)

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
- `architecture/decisions/`: ADR-001 through ADR-029 plus implementation plans (INDEX.md)
- `architecture/questions/`: 11 questions in 6 files (INDEX.md)
- `features/`: 76 feature spec files (INDEX.md with status tracking)
- **WIKI-001** — LLM Wiki (Precomputed Context Layer, fully implemented) ✅
- **PLAN-004** — Timeline Management (vollständig: DB → CRUD → AI analysis → SSE extraction → confirm endpoint → DurationImpossibilityCheck → LLM consistency via bundled prompt → character ages → visualization, 44 files, DoD-100%) ✅
- `mvp/`: Product roadmap (Phases 0–6 + Post-MVP)

### Infrastructure

- `scripts/check_architecture.py` — CI-enforced constraint validation
- `scripts/check_system_health.py` — Aggregierte System-Health-Metrik (HEALTHY/DEGRADED/CRITICAL)
- `scripts/health_types.py` + `health_format.py` — Health-Score-Typen und Formatierer
- `apps/api/narrare/_app/observability.py` — Central Trace-Context-Helper + module-level OTel degradation visibility (`get_observability_status()`, one-shot warning)
- `docs/development/observability-guide.md` — End-to-End Observability-Trace-Kette dokumentiert
- `scripts/architecture/streaming_compliance.py` — Streaming compliance checker with nested router prefix resolution (`build_effective_router_prefixes()`)
- `scripts/check_streaming_compliance.py` — Pre-commit hook for streaming compliance
- `.github/workflows/` — CI is the blocking architecture/setup gate SSOT; release workflow publishes GHCR image + SBOM; Pydantic Evals are the ADR-032 target for AI quality gates
- Docker Compose: PostgreSQL (pgvector) + Redis + pgBouncer (prod profile)
- OpenTelemetry-only trace standard for API and LLM/agent observability (ADR-031)
- Pydantic Evals as the evaluation SSOT for AI runtime quality (ADR-032; implementation migration pending)

### AI Feature Freeze / Post-Freeze Governance

- **Status:** Freeze fully lifted after Architecture freeze-lift review (2026-06-03).
- **Resolved blockers:** AUFG-02-01 backend unit failures `7 → 0`; AUFG-02-03 frontend tests stable under 120s (`112.43s`, `115.04s`, `111.95s`); AUFG-03-01 prompt warnings `79 → 35`; AUFG-03-02 KB adoption `0.78 → 0.90 PASS`.
- **Remaining governed debt:** frontend RULE-04 legacy file-size debt is ratcheted at 37 violations (`53 → 38 → 37`, 16 resolved, 0 new). This is not a freeze blocker.
- **Still blocked by governance:** new prompt/adoption warning growth, new architecture exceptions without ADR/user approval, new frontend file-size violations, REST-only frontend paths for SSE-capable AI backends, and workaround/quick-fix implementations.
- **Streaming compliance:** 0 violations (baseline was 2: unused KB sessions SSE + timeline analysis without frontend consumer; both resolved).
- **Health note:** System Health reflects baseline debt; streaming compliance is now 0 violations and RULE-02 exception count reduced from 1 to 0. DEGRADED is warning-only for freeze status; CRITICAL blocks.

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
17. ⛔ ADR-017: Embedding Cascade — Superseded by ADR-033
18. ⛔ ADR-018: Promptfoo Eval Framework — Superseded by ADR-032
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
35. ✅ ADR-029: VM-first setup cleanup — portable optional DevContainer overlay, explicit host/container service addressing, pinned pnpm, non-mutating frontend check path, CI as single blocking setup/architecture gate owner, release image alignment, `.dockerignore`, and derived-doc SSOT cleanup.
36. ✅ Review-01 Phase 1 (Streaming + Prompts): deprecated timeline REST wrapper removed; unused KB sessions SSE endpoint deleted; streaming-compliance checker fixed for nested FastAPI routers with `build_effective_router_prefixes()`; streaming pre-commit hook added; required prompt variables added to analysis/pov, analysis/readability, planning/temporal_consistency.
37. ✅ Review-01 Phase 2 (Structure): RULE-02 f-string exception removed from KB consistency analyzer (prompt → bundled `core/prompts/_bundled/kb/*/consistency/system.md`); EditorView.tsx modularized from 764→146 lines into 14 focused modules (`editor-view/` directory); exception registers updated in CONSTRAINTS.md and pyproject.toml (14→13).
38. ✅ Review-01 Phase 3 (Privacy + Observability): KB interview resume changed from localStorage→sessionStorage (privacy); module-level OTel degradation visibility with one-shot warning + `get_observability_status()`; health endpoint includes OTel status (`/health` returns `observability` field).
39. ✅ Coverage expansion: LexiconSentimentAnalyzer 19%→99% (40 tests), syllable counting 85%→92% (practical ceiling without pyphen), SpacyNLPProvider 49%→50% (ceiling without spaCy installed); wiki chapter_service 0%→100%, wiki service 18%→100%, wiki system_accessors 62%→100%, overall wiki coverage 74%→87%; memory tests migrated from MagicMock to Fake classes (ADR-030 implemented).

## What's Next

1. ✅ **AI Feature Freeze lifted** — new AI feature work may resume under ratcheted governance.
2. ✅ **Backend-Unit-Failures behoben (AUFG-02-01)** — 7 Failures → 0.
3. ✅ **Prompt-Warnungen reduziert (AUFG-03-01)** — 79 → 35; no-growth ratchet aktiv.
4. ✅ **KB-Adoption über 0.85 (AUFG-03-02)** — 0.78 → 0.90 PASS.
5. ✅ **Frontend-Tests beschleunigt (AUFG-02-03)** — Vitest stabil <120s.
6. ✅ **Streaming Compliance (Review-01 Phase 1)** — 2 violations → 0. KB sessions SSE removed; timeline analysis fixed.
7. ⏳ **Frontend-Hubs weiter modularisieren (AUFG-01-02)** — 37 ratcheted legacy RULE-04 violations remain (was 38; EditorView modularized); no new violations allowed.
8. ⏳ **E2E test patterns**
9. ⏳ **ANAL-005: Coreference Analysis** — may resume after Architecture/Implementation planning under post-freeze governance.

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
| ADR-010 | Observability (OpenTelemetry + Langfuse) | ⛔ Superseded by ADR-031 |
| ADR-011 | Content Versioning | ✅ Implemented |
| ADR-012 | Event-Driven Architecture (Redis Pub/Sub) | ✅ Implemented |
| ADR-013 | Internationalization | ✅ Implemented |
| ADR-014 | RULE-14: Model-Migration Consistency | ✅ Enforced |
| ADR-015 | Pydantic-AI Agents as First-Class Citizens | ✅ Accepted |
| ADR-016 | Prompt Caching Strategy | ✅ Implemented (all 4 phases) |
| ADR-017 | Embedding Cascade for mem0 | ⛔ Superseded by ADR-033 |
| ADR-018 | Promptfoo Eval Framework | ⛔ Superseded by ADR-032 |
| ADR-019 | System-Prompt Consistency for Agents | ✅ Accepted |
| ADR-020 | Embedding Provider Abstraction | ✅ Accepted |
| ADR-021 | Deterministic Analysis Strategy | ✅ Accepted |
| ADR-022 | LLM Wiki — Precomputed Context Layer: core/wiki/ module, TaskIQ-generated WikiSummaries, Prompt versioning, stale/fresh/pending, 9 repository methods, 6 API endpoints, 4 background tasks, 4 event listeners, wiki-optimized token budget. WIKI-001 Feature Spec. | ✅ Implemented (full stack) |
| ADR-023 | Co-Author Change Engine | ✅ Implemented |
| ADR-027 | AI Feature Stabilization Gates | ✅ Completed — freeze lifted; ratcheted post-freeze governance retained |
| ADR-028 | Architecture Exception Register SSOT | ✅ Implemented |
| ADR-029 | VM-First Setup Contract and Optional DevContainer Cleanup | ✅ Implemented |
| ADR-030 | MagicMock-to-Fake Migration Plan for Memory Tests | ✅ Implemented |
| ADR-031 | Local-First OpenTelemetry Observability | ✅ Accepted; implementation migration pending |
| ADR-032 | Pydantic Evals as Evaluation SSOT | ✅ Accepted; implementation migration pending |
| ADR-033 | mem0 v3 OSS Memory Architecture | ✅ Accepted; compatibility verification pending |
| ADR-034 | Conversational History Policy | ✅ Accepted |
| ADR-035 | Agent Output Validation Policy | ✅ Accepted |
| ADR-036 | Durable Execution Boundary | ✅ Accepted; gated before adoption |

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
| System Health Score (DEGRADED) | Medium | Non-blocking metric-floor/baseline artifact. CI remains warning-only for DEGRADED and fails on CRITICAL. Streaming compliance now 0 violations; baseline debt must keep shrinking for ≥0.85. |
| 37 frontend RULE-04 legacy violations | Medium | Ratcheted baseline: no new violations; reductions only unless ADR/user-approved exception. EditorView modularized (764→146 lines). |
| Architecture exception baseline drift | Low | Resolved/revalidated by option B blocker cleanup: exception baseline is current at 13/13 (was 14/14; RULE-02 exception #3 removed). |

---

> Maintained by: Coordinator, updated at session end
