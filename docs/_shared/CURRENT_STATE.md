# Narrare — Current State

> This document is the live status of the project.
> Every agent reads this at the start of every session.

---

## Last Updated

Date: 2026-06-12 (CR-01 Prompt Governance Remediation Docs Sync)
Session: CR-01 prompt governance remediation documented after verified core/platform implementation. Prompt standards now state template-level explicit wrapping, `variable_registry.USER_CONTENT_VARS` as SSOT, approved wrappers, canonical `{{writing_language}}`, `{{kb_suggested}}` generated-candidate boilerplate, and checker/eval/manual-review enforcement mapping. Previous Review-03 AUFG-03-06/09/10 state remains completed. Adoption debt (109 items) and system health (0.88) unchanged.

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

### Stats (verified 2026-06-11)

- Knowledge Graph: 17,357 nodes, 122,996 edges, risk low
- Backend tests: ~6,240+ across 579 test files (unit + integration)
- Frontend tests: 1,683+ across 201 test files (Vitest + MSW)
- Architecture rules: 23 rules (RULE-01b, RULE-02/02a, RULE-03 through RULE-23)
- Architecture exceptions: 10 in CONSTRAINTS.md §7 table; 12 in ai-gate-baseline.json (incl. 1 RULE-TEST-01 test-mocking entry + 1 inline_fallback + 1 RULE-19)
- ADRs: 42 entries in INDEX.md (ADR-001 through ADR-043, ADR-039 gap — 42 unique entries)
- Feature specs: 86 individual files + INDEX.md (77 registered entries)
- Open questions: 3 active (Q-001, Q-002, Q-011), 9 resolved
- Adoption debt: 109 ratcheted baseline items — 0 new above baseline, 0 resolved (breakdown: 27 not_adopted markers, 63 real runtime-evidence gaps [missing], 18 design-level not_applicable, 1 inline_fallback counter). All 27 modes pass static adoption (probes wired) but 0 of 27 pass full runtime adoption.
- System health: 0.88 HEALTHY (feature_adoption gate at 0.50 — reflects 109 ratcheted baseline items; no new debt above ratchet floor. CI remains warning-only for DEGRADED, fails on CRITICAL.)

### Core (`packages/core/narrare_core/`)

19 submodules: agents, ai_invocation, analysis, cache, chat, context, embeddings, events, kb, llm, memory, nlp, planning, prompts, schemas, shared, templates, wiki, writing

19 AI agents (pydantic-ai): beta_reader, character_arc, chat (ChatAgent), consistency, draft, extraction, inline_suggest, kb, kb_assist, kb_improve, merge (KBMergeAgent), outline, pov_detection, preference_analysis, readability, review, summary, timeline, worldbuilding

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

- `_shared/`: CONSTRAINTS.md (23 rules), TECH_STACK.md, GLOSSARY.md, CURRENT_STATE.md
- `development/`: coding-standards, testing-standards, ui-principles, deployment-guide, orchestrator
- `architecture/decisions/`: ADR-001 through ADR-043 plus implementation plans (INDEX.md, 42 entries — ADR-039 gap)
- `architecture/questions/`: 11 questions in 6 files (3 active, 9 resolved)
- `features/`: 86 feature spec files + INDEX.md (77 registered entries with status tracking)
- `features/INDEX.md` → ADAPTER-001/002: MCP and A2A adapters documented as "Planned, Not Implemented" (post-MVP, Q-001/Q-002 blockers)
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
- `scripts/prompt_governance_checks.py` — Prompt governance checker for approved XML wrappers, deprecated output-language aliases, and generated-candidate boilerplate
- `.github/workflows/` — CI is the blocking architecture/setup gate SSOT; release workflow publishes GHCR image + SBOM; Pydantic Evals are the ADR-032 target for AI quality gates
- Docker Compose: PostgreSQL (pgvector) + Redis + pgBouncer (prod profile)
- OpenTelemetry-only trace standard for API and LLM/agent observability (ADR-031)
- Pydantic Evals as the evaluation SSOT for AI runtime quality (ADR-032; implemented)

### AI Feature Freeze / Post-Freeze Governance

- **Status:** Freeze fully lifted after Architecture freeze-lift review (2026-06-03).
- **Resolved blockers:** AUFG-02-01 backend unit failures `7 → 0`; AUFG-02-03 frontend tests stable under 120s (`112.43s`, `115.04s`, `111.95s`); AUFG-03-01 prompt warnings `79 → 35`; AUFG-03-02 KB adoption `0.78 → 0.90 PASS`.
- **Remaining governed debt:** frontend RULE-04 legacy file-size debt fully resolved (`53 → 38 → 37 → 0`). All TS/TSX files within limits.
- **Still blocked by governance:** new prompt/adoption warning growth, new architecture exceptions without ADR/user approval, new frontend file-size violations, REST-only frontend paths for SSE-capable AI backends, and workaround/quick-fix implementations.
- **Streaming compliance:** 0 violations (baseline was 2: unused KB sessions SSE + timeline analysis without frontend consumer; both resolved).
- **Health note:** System Health reflects ratcheted baseline debt (109 adoption items, 12 architecture exceptions). feature_adoption gate at 0.50 due to 63 real runtime-evidence gaps in baseline (not new debt above ratchet). Streaming compliance is 0 violations. DEGRADED is warning-only; CRITICAL blocks.

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
40. ✅ **Chat Migration (CHAT-001, ADR-034)**: `ChatAgent` + `ChatDeps` created with `HistoryPolicy.CONVERSATIONAL` (first adopter of ADR-034). `ProcessHistory` for cross-turn message continuity. Backend `chat_service.py` refactored to use `ChatAgent.run_stream()` instead of `ModelRegistry.stream()`. `StreamEvent` yielded during `NarrareAgent.run_stream()`. Unit tests for chat service (happy path, history, errors).
41. ✅ **CR-03 / INFRA-013 P0 (ADR-038)**: Core `ai_invocation/` module with contracts (`PromptInvocationContext`, `AdoptionPolicy`), enrichers (`PreferenceContextEnricher`), validators (`RuntimeVariableValidator`, `FinalPromptValidator`), budget resolver (`IntentOutputBudgetResolver`), `InvocationPipeline` orchestrator, and WritingPipeline integration via `_invocation_adapter.py`. Backend DI wired. P0.3e (LoggingEvidenceSink) and P1 (User/Project IDs in InvocationContext) also implemented. P1 (mode-specific registry) through P3 remain outstanding.
42. ✅ **CR-03 / INFRA-013 P2 (ADR-040)**: `core/profiles/` module with `ProjectWritingProfile` SSOT (consolidated voice/tone/style/language/genre), `KBConsistencyEnricher` + `VoiceProfileStatus` in `ai_invocation/`, `AuditReport` + KG Consistency Checker in `scripts/adoption/`, `requires_runtime_evidence` flag in adoption registry. 24/27 modes wired with runtime evidence.
43. ✅ **CR-03 / INFRA-013 P3 (ADR-041)**: FileEvidenceSink (`.evidence/invocations.jsonl`), registry drift detection (JSON Schema + `check_registry_drift.py`), doc-drift automation (`doc_drift/` package), quality metrics (`QualityReport` + joiner), CI integration (`--drift` flag, CI jobs). All P3 exit criteria satisfied. INFRA-013 complete through P3.
  44. ✅ **CR-04 Cross-Feature Coherence Remediation**: KB Context Contract with source/evidence/confidence/review_status metadata (CR-AUFG-04-01 + B1 + B3); Variable naming canonical aliases with deprecation of bare `language` (CR-AUFG-04-03 + E2 + B6); ADR Implementation Completeness Gate (Gate 12); Cross-Feature Audit Cadence; FIND-009 (Timeline→Consistency) registered. 39 new tests. Precedence confirmed in RULE-22 §7 (E3: no standalone ADR needed).
  45. ✅ **CR-03 / INFRA-013 P4 (ADR-042)**: PersistentEvidenceSink (PostgreSQL hybrid), EvidenceRepository protocol + implementation, PersistentEvidenceSink in Backend, Alembic migration 0028_invocation_evidence, 41 tests (23 unit + 18 integration). FileEvidenceSink unchanged for CI.
   46. ✅ **CR-03 / INFRA-013 P5 — 27/27 Static Adoption Achieved**: All 27 feature modes have adoption infrastructure wired (probes, registry entries, static adoption passes). Runtime adoption incomplete: 63 runtime-evidence gaps remain (final_validation, preference_enrichment, budget_resolution, evidence_sink missing for various modes). Universal blocker (preference_enrichment) cracked via PreferenceContextEnricherImpl (already existed) + preference enrichment probe + marker file + scorer override. Validation probe (RuntimeVariableValidatorImpl + FinalPromptValidatorImpl) + budget probe (IntentOutputBudgetResolverImpl) + scorer overrides for final_validation, budget_resolution, kb_suggested. Scorer bugfix: not_applicable no longer blocks adoption. 24 new mode probes (writing 9, analysis 7, kb 8) + preference enrichment probe + validation+budget probes. ai-gate-baseline.json ratcheted: 0 new adoption debt above 109-item baseline floor. CI integration: probes run before adoption check.
47. ✅ **CR-07 UX Audit Remediation — Full Implementation**: ADR-043 useAIOperation hook + mapSSEError implementiert. Alle P0/P1 AI-Flows (GenerationPanel, CoAuthorPanel, ContinueButton, TipTapEditor, KB sessions, timeline, KB _components) auf useAIOperation migriert. §16 Compliance: aiActions.* i18n keys (de/en/fr), structured AIErrorResponse, no raw AbortController, no useConnectionLost. Maschinelle Compliance-Checks + CI-Integration. RULE-04: scorer_modes.py (401→365) + compliance script (594→93) modularisiert. ONBOARD-001, PROMPT-003, KEYBOARD-001 Feature-Specs erstellt. Q-012 resolved. Commit 1001125: 84 Dateien, +5.132/-674.
48. ✅ **CR-07 UX Audit — Phase 2**: CR-AUFG-07-01 bis CR-AUFG-07-06 abgeschlossen. 8 AI-Files auf useAIOperation migriert (useChat.ts, useBetaReader.ts, useExtraction.ts, useWorldbuilding.ts, NameGenerator.tsx, ConsistencyCheckPanel.tsx). GhostText RULE-04 Split (ghost-text-helpers 389→351, ghost-text-suggestions NEW). coauthor-streaming DEAD CODE DELETED. Migrierte Flows: Chat SSE (CHAT-001), Beta Reader (ANAL-001), Extraction (KB-007), Worldbuilding (KB-006), Name Generator (GEN-001), Consistency Check (CONS-001). KEYBOARD-001 implementiert (Ctrl+Enter, Escape-Cancel). 5 Testfiles aktualisiert, 40+14 Tests grün.
49. ✅ **AUFG-03-06 Agent Error Classification**: Core `agents/errors.py` (AgentError, ModelExecutionError, ModelRetryExhaustedError, AgentTimeoutError, AgentCancelledError) + `agents/error_translator.py` (single translation point for `run()`/`run_stream()`) + `agents/base.py` updated to use classified errors. Privacy-safe log attributes, no raw provider exceptions past agent boundary. 31 unit tests in `test_agent_error_classification.py`. Cancel≠error semantics enforced.
50. ✅ **AUFG-03-09 AI-UX-Gate-Governance + ADR-043 Exclude Pflichtfeld-Schema**: `.ai_interaction_exclude` migrated to ADR-043 Note 6 mandatory-field format (file, owner, gate, reason, exit, added, re_evaluated). Checker updated: malformed entries rejected. `just check-ai-ux` reports 0 Violations, 6 Governed Exclusions. Stale review findings (useExtractionPhase/useConnectionLost, NameGenerator.test.tsx) no longer tracked as current violations. Baseline entries carry owner + exit criteria.
51. ✅ **AUFG-03-10 TipTap-AI-UX/i18n Consistency**: GhostText hint localized via Extension-Options (`t("ghostText.hint")` → hintText in en/de/fr). CoAuthor action vocabulary migrated to `studio.aiActions.*` (`acceptAll`, `rejectAll`, `applySelected` in all 3 locales). BetaReaderPanel + useWorldbuildingAnalysis freed from useConnectionLost. Exclude list updated (2 stale entries removed, 2 new governed entries added). §16.8 canonical vocabulary table updated.
52. ✅ **CR-01 Prompt Governance Remediation**: 23 bundled prompt templates remediated; user-content wrapping standardized to approved template-level XML wrappers; bundled output-language variables migrated to `{{writing_language}}`; `{{kb_suggested}}` boilerplate normalized; evidence/confidence/false-positive gates added to relevant prompts; `UNSAFE_USER_VARS` derives from `variable_registry.USER_CONTENT_VARS`; `scripts/prompt_governance_checks.py` added and documented. Validation reported PASS: Ruff, 34 script tests, `check_prompt_structure.py --strict`, `check_architecture.py`.

## What's Next

1. ✅ **AI Feature Freeze lifted** — new AI feature work may resume under ratcheted governance.
2. ✅ **Backend-Unit-Failures behoben (AUFG-02-01)** — 7 Failures → 0.
3. ✅ **Prompt-Warnungen reduziert (AUFG-03-01)** — 79 → 35; no-growth ratchet aktiv.
4. ✅ **KB-Adoption über 0.85 (AUFG-03-02)** — 0.78 → 0.90 PASS.
5. ✅ **Frontend-Tests beschleunigt (AUFG-02-03)** — Vitest stabil <120s.
6. ✅ **Streaming Compliance (Review-01 Phase 1)** — 2 violations → 0. KB sessions SSE removed; timeline analysis fixed.
7. ✅ **Frontend-Hubs modularisiert (AUFG-01-02)** — All frontend RULE-04 violations resolved (`53 → 38 → 37 → 0`). EditorView modularized (764→146 lines). File-size check reports 0 current, 0 baseline, 0 new.
8. ✅ **E2E test patterns** — Playwright-based E2E tests established (16 test files, 3.3k lines). Auth proxy pattern, wizard robustness, editor persistence, warmup fixture, `NARRARE_E2E_TEST=1` mode. Documented in testing-standards.md.
9. ⏳ **ANAL-005: Coreference Analysis** — may resume after Architecture/Implementation planning under post-freeze governance.
10. ✅ **CR-03 / INFRA-013 P0–P5** — Core ai_invocation module implemented through P5. P0 (pipeline + contracts), P1 (User/Project IDs), P2 (profiles + KG consistency), P3 (FileEvidenceSink + drift detection + quality metrics), P4 (PersistentEvidenceSink + PostgreSQL), P5 (27/27 modes static adoption — probes wired, 63 runtime-evidence gaps ratcheted as baseline). INFRA-013 complete.
11. ✅ **CR-07 UX Audit — Full Implementation** — ADR-043 implementiert, alle P0/P1 flows migriert, §16 compliance durchgesetzt, maschinelle Checks + CI.
12. ✅ **ONBOARD-001: Onboarding & AI-Einführung** — Demo-Discovery im Dashboard, KI-Tour (1–2 Min.), kontextuelle Tooltips. Post-MVP. Implementiert: GET /setup/demos, DemoProjectCards, useSeenTooltips, Tour-Replay.
13. ⏳ **PROMPT-003: Prompt Customization UX** — Variablen-Erklärung, Preview/Test-Modus, Reset-to-Default. Post-MVP (nicht vor Phase 6).
14. ✅ **KEYBOARD-001: Tastatur-Konsistenz** — Ctrl+Enter für alle AI-Aktionen, Escape für Cancel, Tab für GhostText-Accept. Post-MVP. Implementiert: ChatPanel (Ctrl+Enter send, Escape cancel/close), CoAuthorPanel (Escape close), ConsistencyCheckPanel (Escape close). 14 neue Test-Assertions. i18n Keys für sendHint + Shortcuts in allen 3 Locales.
15. ✅ **CR-07 UX Audit — Phase 2 (Implementation)** — CR-AUFG-07-01 bis CR-AUFG-07-06: 8 Files auf useAIOperation migriert (useChat.ts, useBetaReader.ts, useExtraction.ts, useWorldbuilding.ts, NameGenerator.tsx, ConsistencyCheckPanel.tsx). GhostText RULE-04 Split (ghost-text-helpers 389→351, ghost-text-suggestions NEW). coauthor-streaming gelöscht (dead code). 5 Testfiles aktualisiert, 40 Tests grün. 0 manuelle AbortController in AI-Komponenten.

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
| ADR-024 | Free-Form Chat for Writing Craft | ✅ Implemented — ChatAgent + ChatDeps + HistoryPolicy.CONVERSATIONAL |
| ADR-025 | Feature Adoption Infrastructure | ✅ Implemented — 27/27 modes static adoption (probes wired); 63 runtime-evidence gaps ratcheted; INFRA-013 complete |
| ADR-026 | Capability-Based Prompt Injection Pattern | ✅ Implemented |
| ADR-027 | AI Feature Stabilization Gates | ✅ Completed — freeze lifted; ratcheted post-freeze governance retained |
| ADR-028 | Architecture Exception Register SSOT | ✅ Implemented |
| ADR-029 | VM-First Setup Contract and Optional DevContainer Cleanup | ✅ Implemented |
| ADR-030 | MagicMock-to-Fake Migration Plan for Memory Tests | ✅ Implemented |
| ADR-031 | Local-First OpenTelemetry Observability | ✅ Phase 1 implemented — Langfuse removed; Pydantic-AI OTel instrumentation active |
| ADR-032 | Pydantic Evals as Evaluation SSOT | ✅ Implemented |
| ADR-033 | mem0 v3 OSS Memory Architecture | ✅ Implemented (mem0 2.0.x) |
| ADR-034 | Conversational History Policy | ✅ Implemented |
| ADR-035 | Agent Output Validation Policy | ✅ Implemented (all 17 structured-output agents) |
| ADR-036 | Durable Execution Boundary | ✅ Accepted; gated before adoption |
| ADR-037 | Prompt Surface Contract Manifest | ✅ Accepted — CR-01 prompt surface contract for manifest-routeable intents (INFRA-012) |
| ADR-038 | AI Invocation Adoption Contract | ✅ Implemented (P0–P5) — CR-03 runtime evidence contract complete through P5; core ai_invocation module with InvocationPipeline, enrichers, validators, budget resolver, LoggingEvidenceSink; User/Project IDs in InvocationContext; core/profiles/ (ProjectWritingProfile SSOT); KBConsistencyEnricher; AuditReport; FileEvidenceSink; PersistentEvidenceSink (PostgreSQL hybrid); registry drift detection; doc-drift automation; quality metrics; CI integration; 27/27 modes static adoption (probes wired), 63 runtime-evidence gaps ratcheted as baseline — INFRA-013 complete |
| ADR-040 | KG Consistency / Voice Profile SSOT / Audit Lifecycle | ✅ Accepted — P2 architecture for ProjectWritingProfile SSOT, KG consistency evidence, audit lifecycle reporting, mode runtime proof expansion (24/27 modes) |
| ADR-041 | Typed Manifests / Doc-Drift Automation / Quality Metrics / Persistent Evidence | ✅ Accepted — P3 architecture for registry drift detection (JSON Schema + check_registry_drift.py), doc-drift automation (doc_drift/ package), quality metrics (QualityReport + joiner), and file-based evidence persistence (FileEvidenceSink with .evidence/invocations.jsonl) |
| ADR-042 | PostgreSQL Evidence Upgrade | ✅ Implemented (P4) — hybrid FileEvidenceSink (CI) + PersistentEvidenceSink (production) |
| ADR-043 | `useAIOperation` Primitives | ✅ Implemented — shared streaming client, cancel/error/loading primitives, canonical `studio.aiActions.*` labels, §16 compliance checks, P0/P1 flows migrated (Commit 1001125) |

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
| Q-009 | Chat conversations: project-scoped vs user-scoped | ✅ → Project-scoped (Option A) |
| Q-010 | Chat prompt i18n: EN-only v1 vs full i18n | ✅ → English-only v1 (Option A) |
| Q-011 | Distribution strategy for non-technical users | 🟡 Open |
| Q-012 | Prompt-Variablen-Erklärung und Reset-to-Default in der WebUI | ✅ Resolved — adressiert durch PROMPT-003 (Post-MVP), UX-Lücke dokumentiert in Feature-Spec |

Full details: `docs/architecture/questions/INDEX.md`

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Python 3.14 missing type stubs | Low | Documented in pyproject.toml |
| TipTap v3 API changes | Medium | Pin exact version |
| Editor h-full in flex container | Low | Follow DashboardView pattern |
| System Health Score | Medium | Current: 0.88 HEALTHY. feature_adoption gate at 0.50 (109 ratcheted baseline items: 27 not_adopted markers + 63 real runtime-evidence gaps + 18 design-level N/A + 1 counter). No growth above ratchet floor. CI remains warning-only for DEGRADED and fails on CRITICAL. |
| Frontend RULE-04 regressions | Low | All 37 legacy violations resolved (53→0). `check_frontend_file_size.py` enforces limits in CI. New violations blocked by ratchet. |
| Architecture exception baseline drift | Low | Resolved/revalidated by option B blocker cleanup: CONSTRAINTS.md §7 table has 10 entries; ai-gate-baseline.json has 12 (incl. 1 RULE-TEST-01 + 1 inline_fallback + 1 RULE-19). RULE-02 exception #3 removed. |

---

> Maintained by: Coordinator, updated at session end
> Last content update: 2026-06-12 (CR-01 Prompt Governance Remediation Docs Sync)
