# Narrare — Current State

> This document is the live status of the project.
> Every agent reads this at the start of every session.

---

## Last Updated

Date: 2026-06-24 (ADR-048 Q1/Q3 follow-up amendments documented — Mode 2 Audit results and Budget Resolver decision; ADR-047/048 fully implemented — governance health CI-blocking, writing-adapter delegation to `compose_invocation()`, `KBSuggestedProvider` structured `KBSuggestionResult` return, deprecated `safe_record_evidence()`/`record_invocation_evidence()` removal (Slice F))
Session: ADR-048 follow-up amendments. **ADR-048 Q1 Follow-up (Mode 2 Audit):** the >5 Mode 2 Review Trigger fired (22 declarations total). Audit categorized all into A (11 mislabeled Mode 1 → migrate), B (10 true Mode 2 → keep), C (2 redundant parent wrappers → remove). Post-migration: 10 legitimate Mode 2 remain. Surface finding: `safe_compose_invocation()` is fire-and-forget (returns `None`, discards `ComposedInvocation`, enrichment never reaches the agent). **ADR-048 Q3 Follow-up (Budget Resolver):** Decision = Option D (evidence/quality only, no budget integration now). 3 reasons: non-writing KB contexts <1000 tokens; enrichment is fire-and-forget until Q1 migration completes; enricher/resolver run in the same `prepare()` phase (ordering blocker). Future path = Option B (KB Context Selector) when triggers fire. **Prior:** ADR-047/048 implementation closure — all Phases/Slices implemented (governance health CI-blocking; writing-adapter delegation to `compose_invocation()`; `KBSuggestedProvider` returns structured `KBSuggestionResult`; Slice F deprecated-function removal). Prior session: CR-07 Follow-up v3 lifecycle closure (CR-AUFG-07-14…07-24 resolved, Phases A/B/C complete). Prior (2026-06-20): CR-08 lifecycle resolution — ADR-051 accepted; RULE-18b elevated to CONSTRAINTS.md; CR-08 AUFG set resolved; SET-005 promoted to stable.

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

### Stats (authoritative sources only)

- Knowledge Graph: run `just code-review-graph list-graph-stats` for current node/edge counts
- Backend tests: see `tests/unit/api/` and `tests/integration/`; run `just test` for results
- Frontend tests: see `tests/` (Vitest); run `just test-frontend` for results
- Architecture rules: see `docs/_shared/CONSTRAINTS.md` (§Rules)
- Architecture exceptions: see `docs/_shared/CONSTRAINTS.md` (§7 table)
- ADRs: see `docs/architecture/decisions/INDEX.md`
- Feature specs: see `docs/features/INDEX.md`
- Open questions: see `docs/architecture/questions/INDEX.md`
- AUFG lifecycle: see `docs/architecture/governance/aufg-registry.md`
- Adoption debt: run `just check-adoption` for current status
  - **Runtime adoption status terminology (ADR-045):** "Infrastructure complete" ≠ "Static verified" ≠ "Runtime verified" ≠ "Runtime adopted." Current status: infrastructure complete, static verified, and runtime adopted for all required modes. Runtime adoption means correlated production-path evidence proves the invocation pipeline, prompt-context merge, budget enforcement, model-call marker, and evidence recording for real AI calls. Governed adoption debt remains only for the registered inline fallback baseline; new unapproved gaps fail the gate.
- System health: run `just check-health` for current score

### Core (`packages/core/narrare_core/`)

19 submodules: agents, ai_invocation, analysis, cache, chat, context, embeddings, events, kb, llm, memory, nlp, planning, prompts, schemas, shared, templates, wiki, writing

20 AI agents (pydantic-ai): beta_reader, character_arc, chat (ChatAgent), consistency, draft, extraction, fact_extractor, inline_suggest, kb, kb_assist, kb_improve, merge (KBMergeAgent), outline, pov_detection, preference_analysis, readability, review, summary, timeline, worldbuilding

### Backend (`apps/api/narrare/`)

20 domain modules: analysis, auth, chapters, consistency, embeddings, events, generation, kb, memory, metrics, novels, planning, prompts, settings, setup, tasks, templates, volumes, writing (+ _app infrastructure)

Router files for all CRUD + SSE + WebSocket endpoints in domain modules (KB sessions SSE removed — unused)

Alembic migrations 0001 through 0030 (0028: invocation_evidence table; 0030: evidence correlation columns from ADR-045 — `invocation_id`, `prepared_context_fingerprint`, `prompt_fingerprint`, `budget_decision_fingerprint`, `model_call_marker`, `streaming`)

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
- `architecture/decisions/`: ADR-001–ADR-051 plus implementation plans (INDEX.md — ADR-039 gap; ADR-046–ADR-051 implemented or accepted as listed there)
- `architecture/questions/`: 11 questions in 6 files (3 active, 9 resolved)
- `features/`: Feature specs with status tracking; see `docs/features/INDEX.md`
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
- **Health note:** System Health reflects ratcheted baseline debt. Runtime adoption gaps from ADR-045 are closed; `just check-adoption` is the authoritative source for current score and counts. The remaining adoption debt class is the governed inline-fallback baseline. DEGRADED is warning-only; CRITICAL blocks.

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
13. ✅ SET-005: Configurable Token Limits — storage/API/UI cascade exists; CR-08 P0-P4 have implementation + enforcement + cross-layer evidence (P0 model-boundary/tier-budget adoption; P1 token profile vocabulary, UI/API/Core parity/FIND-013, model-limit calibration, and suitability warnings/blocks; P2 operator/default governance; P3 governed defaults manifest; P4 status taxonomy + audit-template matrix gate). ADR-051 accepted 2026-06-20; SET-005 promoted to stable (cascade + runtime adoption + UI/API/Core parity + tests verified in the Configuration Adoption Matrix).
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
  44. ✅ **CR-04 Cross-Feature Coherence Remediation**: KB Context Contract with source/evidence/confidence/review_status metadata (CR-AUFG-04-01 + B1 + B3); Variable naming canonical aliases with deprecation of bare `language` (CR-AUFG-04-03 + E2 + B6); ADR Implementation Completeness Gate (Gate 12); Cross-Feature Audit Cadence; FIND-009 (Timeline→Consistency) registered. 39 new tests. Precedence confirmed in RULE-22 §7 (E3: no standalone ADR needed). **Note (2026-06-18, ADR-050):** FIND-009 was split into FIND-009a (resolved by ADR-044 for the Consistency consumer) and FIND-009b (open; closed by ADR-050 P1-B `CrossFeatureRefIndex` for all other consumers).
  45. ✅ **CR-03 / INFRA-013 P4 (ADR-042)**: PersistentEvidenceSink (PostgreSQL hybrid), EvidenceRepository protocol + implementation, PersistentEvidenceSink in Backend, Alembic migration 0028_invocation_evidence, 41 tests (23 unit + 18 integration). FileEvidenceSink unchanged for CI.
   46. ✅ **CR-03 / INFRA-013 P5 — Full Static Adoption Achieved**: All feature modes have adoption infrastructure wired (probes, registry entries, static adoption passes). This completed the infrastructure/static layer; ADR-045 later closed the runtime-adoption layer with correlated evidence and status-bearing gates.
47. ✅ **CR-07 UX Audit Remediation — full §16 closure achieved (CR-07 UX Closure v2)**: ADR-043 `useAIOperation` + `mapSSEError` primitives implemented, CR-AUFG-07-01..06 remediated in Phase 2, and CR-AUFG-07-07..13 now resolved with implementation + enforcement evidence (KB Field Suggest, KB Improve, Timeline Extraction governed adapter, GhostText status indicator, KB Enhance signal propagation, deprecated AI-action aliases, keyboard shortcuts). All 11 platform checks implemented in `scripts/checks/check_ai_interaction_compliance.py`; `just check-ai-ux` reports 0 violations, 3 governed exclusions (all fresh + AUFG-linked); Check 11 validates all 15 resolved AUFG entries carry implementation + enforcement evidence. Lifecycle SSOT: `docs/architecture/governance/aufg-registry.md`; governance contract: `docs/architecture/governance/ai-ux-compliance-v2.md`; machine inventory: `scripts/checks/ai_operation_inventory.yaml`.
48. ✅ **CR-07 UX Audit — Phase 2**: CR-AUFG-07-01 bis CR-AUFG-07-06 abgeschlossen. 8 AI-Files auf useAIOperation migriert (useChat.ts, useBetaReader.ts, useExtraction.ts, useWorldbuilding.ts, NameGenerator.tsx, ConsistencyCheckPanel.tsx). GhostText RULE-04 Split (ghost-text-helpers 389→351, ghost-text-suggestions NEW). coauthor-streaming DEAD CODE DELETED. Migrierte Flows: Chat SSE (CHAT-001), Beta Reader (ANAL-001), Extraction (KB-007), Worldbuilding (KB-006), Name Generator (GEN-001), Consistency Check (CONS-001). Initiale KEYBOARD-001-Shortcut-Abdeckung implementiert; vollständige AI-Output-Shortcut-Konsistenz bleibt CR-AUFG-07-13. 5 Testfiles aktualisiert, 40+14 Tests grün.
49. ✅ **AUFG-03-06 Agent Error Classification**: Core `agents/errors.py` (AgentError, ModelExecutionError, ModelRetryExhaustedError, AgentTimeoutError, AgentCancelledError) + `agents/error_translator.py` (single translation point for `run()`/`run_stream()`) + `agents/base.py` updated to use classified errors. Privacy-safe log attributes, no raw provider exceptions past agent boundary. 31 unit tests in `test_agent_error_classification.py`. Cancel≠error semantics enforced.
50. ✅ **AUFG-03-09 AI-UX-Gate-Governance + ADR-043 Exclude Pflichtfeld-Schema**: `.ai_interaction_exclude` migrated to ADR-043 Note 6 mandatory-field format (file, owner, gate, reason, exit, added, re_evaluated). Checker updated: malformed entries rejected. `just check-ai-ux` reports 0 Violations, 6 Governed Exclusions. Stale review findings (useExtractionPhase/useConnectionLost, NameGenerator.test.tsx) no longer tracked as current violations. Baseline entries carry owner + exit criteria.
51. ✅ **AUFG-03-10 TipTap-AI-UX/i18n Consistency**: GhostText hint localized via Extension-Options (`t("ghostText.hint")` → hintText in en/de/fr). CoAuthor action vocabulary migrated to `studio.aiActions.*` (`acceptAll`, `rejectAll`, `applySelected` in all 3 locales). BetaReaderPanel + useWorldbuildingAnalysis freed from useConnectionLost. Exclude list updated (2 stale entries removed, 2 new governed entries added). §16.8 canonical vocabulary table updated.
52. ✅ **CR-01 Prompt Governance Remediation**: 23 bundled prompt templates remediated; user-content wrapping standardized to approved template-level XML wrappers; bundled output-language variables migrated to `{{writing_language}}`; `{{kb_suggested}}` boilerplate normalized; evidence/confidence/false-positive gates added to relevant prompts; `UNSAFE_USER_VARS` derives from `variable_registry.USER_CONTENT_VARS`; `scripts/prompt_governance_checks.py` added and documented. Validation reported PASS: Ruff, 34 script tests, `check_prompt_structure.py --strict`, `check_architecture.py`.
53. ✅ **ADR-044 / CR-AUFG-01-06 Staged Consistency**: FactExtractorAgent + typed `ExtractedFact`/`TimelineEventEnvelope`, `FACT_EXTRACT` intent/route, enriched `ConsistencyDeps`, backend `ConsistencyOrchestrator`, `timeline_envelope.py`, `checker_context.py`, `stage_schemas.py`, `/consistency/check/stream`, and Pydantic Evals `consistency_staged` smoke/runtime tasks implemented. FIND-009 resolved by integration contract. Validation reported: 57 core tests, 77 backend consistency tests, 9 eval tests; Ruff, Pyright, architecture, prompt checks, and smoke evals passed.
54. ✅ **ADR-045 Runtime Adoption Enforcement**: Completed. Core: invocation correlation (`invocation_id` + fingerprints), prompt-context merge (RULE-22 precedence), run-limit enforcement (`RunLimitResolver`/`ResolvedRunLimits`), mem0 learning event taxonomy, direct-agent helper. Platform: runtime gaps are status-bearing (`PASS`/`GOVERNED_DEBT`/`STATIC_ONLY`/`FAIL`), `--evidence-repo` is threaded, placeholder evidence is rejected. Backend: WebSocket handler modularized, turn service carries user/project/chapter/session IDs, evidence schema migration 0030 adds correlation columns, `comprehensive`+`conservative` profiles are covered. Adoption now reports runtime-verified + adopted for all required modes; governed debt remains only for the registered inline-fallback baseline.
55. ✅ **AUFG-05-12 — Rate-Limiting for AI endpoints**: Shared module at `apps/api/narrare/_app/rate_limits.py` provides reusable AI limiters (`AI_WRITE_LIMITER`, `AI_ANALYSIS_LIMITER`, `AI_LIGHT_LIMITER`, `AI_WS_LIMITER`) plus `SETUP_MODELS_LIMITER` (IP-based). All AI-cost-bearing router files wired via `Depends()`. WebSocket inline check in `router_sessions.py`. Uses in-memory `pyrate_limiter` per AR-05-02.
56. ✅ **AUFG-05-13 — Origin/Referer validation + WebSocket Origin check**: `OriginValidationMiddleware` in `_app/middleware.py` validates Origin/Referer on all POST/PUT/PATCH/DELETE; Bearer-authenticated requests without Origin exempt. `Settings.csrf_trusted_origins` (`NARRARE_CSRF_TRUSTED_ORIGINS`). WebSocket Origin check in `router_sessions.py` (close code 4001). 12 unit tests.
57. ✅ **AUFG-05-14 — OTel Health-Severity Implementation**: `get_observability_status()` extended with `state`/`severity`/`endpoint_configured` keys. `record_otel_setup_outcome()` records setup outcomes thread-safely. `setup_telemetry()` calls it on all 3 paths. `/health` returns `status: obs["severity"]` instead of hardcoded `"ok"`. 13 unit tests. RULE-11 silent-failure gap closed.
  58. ✅ **CR-02 / ADR-046 — Prompt-Path-Compliance Remediation**: 4 prompt-path drift paths fixed (CR-AUFG-02-04 Chat channel injection — system/user channel separation via `system_prompt` kwarg; CR-AUFG-02-05 Worldbuilding Phase2 direct `PromptRegistry.resolve()` replaced with `PromptComposer.build()`; CR-AUFG-02-06 Temporal Consistency `_prompt_loader.py` deleted, replaced with `PromptComposer` route; CR-AUFG-02-07 Writing Graph `composer is None` fallbacks + `_get_fallback_meta()` + `MetaPromptLoader` removed, fail-fast on missing composer). RULE-02b added to CONSTRAINTS.md. Prevention infrastructure: 3 checker modules (`prompt_path.py`, `prompt_channel.py`, extended `prompts.py`), 4 convention test files, adoption metric extension (`prompt_path_compliant` field), ADR Retrofit-Plan requirement in adr-process.md. `prompt_path_compliant` field added to adoption registry. 42 new/updated tests. ADR-046 implemented; derived docs (rules.md, architecture-rules.md, tier1-compact-rules.md, AGENTS.md) synced.
  59. ✅ **CR-04 Remediation (Cross-Feature Coherence) — Phase E governance closure**: FIND-010 (Chat Prompt Surface Drift) and FIND-011 (Timeline Inline-Prompt Bypass) both **Resolved** with implementation + enforcement evidence — not merely documented. Closed by ADR-049 (Prompt-Surface Identity & Path Contract) Phase C implementation + Phase D CI-blocking checkers. FIND-009 split: FIND-009a resolved via ADR-044 (Consistency consumer), FIND-009b closed by ADR-050 P1-A/B (KB Envelope + Lifecycle Observer across all consumers). Core remediation is complete. **Known ratcheted follow-up debt (not concealed):** see "CR-04 Follow-up Debt" below.
  60. ✅ **CR-07 UX Closure v2 (Phase 6)**: CR-AUFG-07-07 through CR-AUFG-07-13 resolved with implementation + enforcement evidence. Frontend: KB Field Suggest/Improve/Enhance signal propagation via `useAIOperation` `execute(signal)`; Timeline Extraction governed cancel adapter; GhostText localized fetching-status indicator; `aiModal.original` → `aiActions.original` migration; consistent `Ctrl/Cmd+Enter` AI-action shortcuts via `lib/ai-action-shortcuts.ts`. Platform: 11 checks in `scripts/checks/check_ai_interaction_compliance.py` (6 new — deprecated-alias, signal-propagation, stale-exclude, lifecycle-sync, operation-inventory, resolution-evidence) + `ai_operation_inventory.yaml` (17 operations, §4 fields). Evidence: `just check-ai-ux` → 0 violations / 3 governed exclusions (fresh + AUFG-linked); Check 11 validates all 15 resolved AUFG entries; 47 platform unit tests across 6 test modules. DoD per `docs/development/finding-lifecycle.md` §5 met (Design + Implementation + Enforcement).
  61. ✅ **CR-07 Follow-up v3 (Phases A + B + C — complete)**: All 11 work items (CR-AUFG-07-14 through CR-AUFG-07-24) resolved with implementation + enforcement evidence per `docs/development/finding-lifecycle.md`. **Phase A** — CR-AUFG-07-14 §16 i18n-fallback hardening (Check 12 prevents `t(...) || "..."` reintroduction); CR-AUFG-07-15 GhostText localized non-blocking error affordance. **Phase B** — CR-AUFG-07-16 PROMPT-003 contract-first implementation (provider-free preview, provider-gated live test, reset, variable metadata/provenance) → PROMPT-003 promoted to `stable`; CR-AUFG-07-17 ONBOARD-001 conceptual tour steps (KB→AI, Storyboard→AI, before/after demo). **Phase C** — CR-AUFG-07-18 shared AI-diff vocabulary (`lib/ai-diff/` + accessible `AIDiffView`); CR-AUFG-07-19 DB-backed append-only prompt history (list/compare/restore/clear, retention); CR-AUFG-07-20 slash-command discovery layer over existing AI operations; CR-AUFG-07-21 SessionPanel server-side stop + WebSocket recovery (ADR-052); CR-AUFG-07-22 regenerate-with-style-variants (governed sub-operation of the rewrite modal); CR-AUFG-07-23 emotional intensity curve (frontend-only deterministic derivation of ANAL-002 arousal); CR-AUFG-07-24 AI feedback rating expansion (Co-Author, KB, Chat via LEARN-001 `/memory/feedback`). Lifecycle SSOT: `docs/architecture/governance/aufg-registry.md`.

## What's Next

### CR-04 Follow-up Debt (known ratcheted baseline — recorded, not concealed)

The CR-04 core remediation is **implemented + enforced** (FIND-010/011 resolved, checkers CI-blocking). Phase D surfaced these additional items as a ratcheted baseline; they are tracked rather than silently absorbed:

| Item | Nature | Tracking | Why not fixed in CR-04 |
|------|--------|----------|------------------------|
| 3 inline f-string services (`character_arc_service`, `timeline_extraction_service`, `kb/merge_service`) | RULE-02 inline-f-String prompts found after the ratchet baseline was set | Ratcheted baseline in `INLINE-FEATURE-PROMPT` gate | Out of CR-04 scope; the gate prevents *new* growth and they migrate under normal feature work |
| `writing/story_suggest` orphan template | `system.md` (v1.3.0) with no Python consumer; likely a remnant of a redesigned story-suggestions feature | AUFG-04-01 (open) — rewire to WRITE-009 or delete | Cleanup decision, not a coherence gap; checker acknowledges it as documented debt |
| ADR-037 latent AST-parsing bug | Checker's AST parser visited only `ast.Assign`, never `ast.AnnAssign`, so the manifest's annotated table was never actually validated | **Fixed in Phase D** | Root-cause bonus find during checker implementation; now repaired |
| `prompt-standards.md` enumeration gap | Canonical `prompt_type` list omitted `universal` even though `_bundled/universal/` exists and is canonical | **Fixed in Phase E** (2026-06-18) | Docs drift; now corrected to match the enumeration in ADR-049 D5 |

**Do not** treat any of these as "CR-04 complete" claims without re-reading this table. "Implemented" means the core coherence contract is in code + checkers; these items are the *explicitly disclosed* remainder.

---

### CR-07 Follow-up Debt (resolved 2026-06-19 — CR-07 UX Closure v2)

ADR-043 primitives are implemented, CR-AUFG-07-01..06 were remediated in Phase 2, and CR-AUFG-07-07..13 are now **resolved** with implementation + enforcement evidence — not from audit prose, checker-green, or ADR existence alone. Each registry entry carries Design + Implementation + Enforcement exit evidence per `docs/development/finding-lifecycle.md` §5. The table below records the original finding nature and the evidence that closed it:

| Item | Nature | Tracking | Required closure evidence |
|------|--------|----------|---------------------------|
| CR-AUFG-07-07 | KB Field Suggest lacks governed lifecycle/cancel/error handling | AUFG registry + AI UX Compliance v2 | Frontend implementation + tests + Platform cancel/signal/inventory gate |
| CR-AUFG-07-08 | KB Improve lacks governed lifecycle/cancel handling | AUFG registry + AI UX Compliance v2 | Frontend implementation + tests + Platform inventory gate |
| CR-AUFG-07-09 | Timeline Extraction manual callback SSE lifecycle/exclude needs migration or governed adapter | AUFG registry + AI UX Compliance v2 | Frontend migration/adapter + stale-exclude/signal enforcement |
| CR-AUFG-07-10 | GhostText has no visible loading/status during suggestion fetch | AUFG registry + AI UX Compliance v2 | Frontend status UI + tests + governed non-React inventory |
| CR-AUFG-07-11 | KB Enhance cancel may be UI-only unless signal propagation is proved | AUFG registry + AI UX Compliance v2 | Signal propagation implementation + regression gate |
| CR-AUFG-07-12 | Deprecated AI-action aliases need removal or exact-key usage gate | AUFG registry + AI UX Compliance v2 | Frontend key migration plus Platform checker; broader namespaces not blanket-banned |
| CR-AUFG-07-13 | AI output action keyboard shortcuts are inconsistent | AUFG registry + AI UX Compliance v2 | Frontend shortcuts + tests + Docs update |

These were not marked `resolved` from audit prose, checker green, or ADR existence alone. Per `docs/development/finding-lifecycle.md`, closure required implementation + enforcement evidence — that evidence now exists on disk for every item, and `just check-ai-ux` (0 violations) plus Check 11 (all 15 resolved AUFG entries have evidence) are the regression gates. Re-open if any enforced check is removed or a governed exception regresses.

---

1. ✅ **AI Feature Freeze lifted** — new AI feature work may resume under ratcheted governance.
2. ✅ **Backend-Unit-Failures behoben (AUFG-02-01)** — 7 Failures → 0.
3. ✅ **Prompt-Warnungen reduziert (AUFG-03-01)** — 79 → 35; no-growth ratchet aktiv.
4. ✅ **KB-Adoption über 0.85 (AUFG-03-02)** — 0.78 → 0.90 PASS.
5. ✅ **Frontend-Tests beschleunigt (AUFG-02-03)** — Vitest stabil <120s.
6. ✅ **Streaming Compliance (Review-01 Phase 1)** — 2 violations → 0. KB sessions SSE removed; timeline analysis fixed.
7. ✅ **Frontend-Hubs modularisiert (AUFG-01-02)** — All frontend RULE-04 violations resolved (`53 → 38 → 37 → 0`). EditorView modularized (764→146 lines). File-size check reports 0 current, 0 baseline, 0 new.
8. ✅ **E2E test patterns** — Playwright-based E2E tests established (16 test files, 3.3k lines). Auth proxy pattern, wizard robustness, editor persistence, warmup fixture, `NARRARE_E2E_TEST=1` mode. Documented in testing-standards.md.
9. ⏳ **ANAL-005: Coreference Analysis** — may resume after Architecture/Implementation planning under post-freeze governance.
10. ✅ **CR-03 / INFRA-013 + ADR-045** — Core ai_invocation module implemented through P5 and ADR-045 runtime enforcement completed. Infrastructure complete, static verified, and runtime adopted are now separately tracked. Current adoption is PASS with all required modes runtime-verified + adopted; governed debt remains only for the registered inline-fallback baseline.
11. ✅ **CR-07 UX Audit — closed (CR-07 UX Closure v2 + Follow-up v3)** — CR-AUFG-07-07 through CR-AUFG-07-13 (Closure v2) and CR-AUFG-07-14 through CR-AUFG-07-24 (Follow-up v3: Phases A, B, C) all resolved with implementation + enforcement evidence; `just check-ai-ux` reports 0 violations and Check 11 validates all resolved AUFG entries.
12. ✅ **ONBOARD-001: Onboarding & AI-Einführung** — Demo-Discovery im Dashboard, KI-Tour (1–2 Min.), kontextuelle Tooltips. Post-MVP. Implementiert: GET /setup/demos, DemoProjectCards, useSeenTooltips, Tour-Replay.
13. ✅ **PROMPT-003: Prompt Customization UX** — Implementiert (CR-AUFG-07-16, Follow-up v3 Phase B). Provider-free Preview, provider-gated Live-Test, Reset-to-Default, Variablen-Metadaten/Provenance, Diagnostik. Promoted to `stable` (2026-06-22).
14. ✅ **KEYBOARD-001: Tastatur-Konsistenz** — Shortcut-Abdeckung implementiert (ChatPanel Ctrl+Enter send, Escape cancel/close; CoAuthorPanel Escape close; ConsistencyCheckPanel Escape close; GhostText Tab accept) plus konsistente Ctrl/Cmd+Enter Accept/Apply für AI-Output-Aktionen via `lib/ai-action-shortcuts.ts` (CR-AUFG-07-13 resolved).
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
| ADR-025 | Feature Adoption Infrastructure | ✅ Implemented — adoption registry/probes/checkers exist; runtime adoption is enforced by ADR-045 status semantics. Current adoption is PASS with all required modes runtime-verified + adopted; governed debt remains only for the registered inline-fallback baseline. |
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
| ADR-038 | AI Invocation Adoption Contract | ✅ Implemented (P0–P5 + ADR-045 enforcement) — core ai_invocation module with InvocationPipeline, enrichers, validators, budget resolver, evidence sinks, profile/KG consistency, drift/doc/quality tooling, persistent evidence, and CI integration. ADR-045 adds correlated evidence semantics and runtime-adoption PASS requirements. Current adoption is PASS with all required modes runtime-verified + adopted. |
| ADR-040 | KG Consistency / Voice Profile SSOT / Audit Lifecycle | ✅ Accepted — P2 architecture for ProjectWritingProfile SSOT, KG consistency evidence, audit lifecycle reporting, mode runtime proof expansion (24/27 modes) |
| ADR-041 | Typed Manifests / Doc-Drift Automation / Quality Metrics / Persistent Evidence | ✅ Accepted — P3 architecture for registry drift detection (JSON Schema + check_registry_drift.py), doc-drift automation (doc_drift/ package), quality metrics (QualityReport + joiner), and file-based evidence persistence (FileEvidenceSink with .evidence/invocations.jsonl) |
| ADR-042 | PostgreSQL Evidence Upgrade | ✅ Implemented (P4) — hybrid FileEvidenceSink (CI) + PersistentEvidenceSink (production) |
| ADR-043 | `useAIOperation` Primitives | ✅ Implemented — hook/error/loading/cancel primitives exist and full §16 adoption is achieved: CR-AUFG-07-01..13 resolved with implementation + enforcement evidence; `just check-ai-ux` reports 0 violations; Check 11 validates all 15 resolved AUFG entries. |
| ADR-044 | Staged Multi-Agent Consistency Pipeline | ✅ Implemented — FactExtractorAgent → ConsistencyAgent, enriched TimelineEventEnvelope integration, SSE stage endpoint, and `consistency_staged` Pydantic Evals |
| ADR-045 | Runtime Adoption Enforcement and Invocation Evidence Correlation | ✅ Implemented — runtime gaps are status-bearing (`PASS`/`GOVERNED_DEBT`/`STATIC_ONLY`/`FAIL`); correlated evidence (`invocation_id` + fingerprints + model-call marker); prompt-context merge with RULE-22 precedence; run-limit enforcement; WebSocket turn modularization; mem0 learning event taxonomy. Current adoption is PASS with all required modes runtime-verified + adopted; governed debt remains only for the registered inline-fallback baseline. |
| ADR-046 | Prompt-Path-Compliance: Resolution-Path Retrofit & Prevention | ✅ Implemented — 4 drift paths fixed; RULE-02b codified; prevention infrastructure (3 checker modules, 4 convention tests, adoption metric) built; `_prompt_loader.py` deleted; `MetaPromptLoader` deprecated; `composer is None` fallbacks removed; chat channel injection fixed |
| ADR-047 | Governance Drift Automation for Review Findings and AUFG Lifecycle | ✅ Implemented (2026-06-24) — All Phases 1–4 implemented. Phases 1–2 (AUFG registry seeded, review-finding coverage checker). Phase 3 (SSOT/gate drift aggregation via `scripts/governance/ssot_aggregation.py`). Phase 4 (CI-blocking via `scripts/check_governance_health.py` in the CI workflow, `just check-governance`). Governance Health Check is now CI-blocking with a `GOVERNED_DEBT` baseline. |
| ADR-048 | Non-Writing Invocation Adapter (Domain-Agnostic Pipeline Composition) | ✅ Implemented (2026-06-24) — All Slices A–F implemented (core adapter, deprecation, both invocation modes migrated, writing adapter Bug 2 fix, Slice F deprecated-function removal). Open Questions Q1/Q2/Q3 resolved **and implemented**: Q1=(b) Mode 2 is exception not default; Q2=(b) full delegation — writing adapter delegates to `compose_invocation()` (spec in ADR-048 §Architecture Spec Q2); Q3=structured return — `KBSuggestedProvider` returns `KBSuggestionResult` structured data (Protocol-breaking change completed across Core + Backend; contract in ADR-048 §Amendment Q3). **Q1 Follow-up (Mode 2 Audit):** >5 trigger fired (22 declarations); audit categorized A=11 migrate→Mode 1, B=10 keep (true Mode 2), C=2 remove (redundant parent wrappers); 10 legitimate remain. `safe_compose_invocation()` fire-and-forget documented. **Q3 Follow-up (Budget Resolver):** Option D chosen (evidence/quality only; no budget integration now; future path = Option B KB Context Selector on triggers). |
| ADR-049 | Prompt-Surface Identity & Path Contract Retrofit (FIND-010 + FIND-011) | ✅ Implemented — Phase C (CHAT routing restored to ADR-024 `writing/chat`; `_bundled/chat/` deleted; `_bundled/planning/en/timeline/system.md` created; `timeline_analysis_service.py` migrated to PromptComposer Mode 1; premature ADR-048 Mode 2 declaration removed) + Phase D checkers (PROMPT-IDENTITY/ROOT-MODE/PATH-DERIVABILITY/FRONTMATTER-MATCH/CONTEXT-MODES/ORPHAN-TEMPLATE/INLINE-FEATURE-PROMPT) CI-blocking. FIND-010 + FIND-011 resolved. ADR-037 latent AST bug (only `ast.Assign` visited, never `ast.AnnAssign`) found and fixed. |
| ADR-050 | Cross-Feature Context Contracts (KB Envelope, Ref Lifecycle, kb_pinned Governance) | ✅ Accepted + Core contracts implemented — `KBContextEnvelope`/`RenderedKBContext`, `KBEntityLifecycleObserver`/`CrossFeatureRefIndex`/per-consumer Protocols in `core/context/`, `VoiceProfileConsumer` in `core/profiles/`, `kb_pinned`/`kb_timelines`/`kb_systems` registered. Backend wiring (Renderer→RenderedKBContext + KB-Lifecycle-Observer) implemented. FIND-009 split: FIND-009a resolved via ADR-044 (Consistency consumer); FIND-009b closed by ADR-050 P1-A/B. |
| ADR-051 | Configuration Effect Adoption Contract | ✅ Accepted — in effect (2026-06-20). RULE-18b (Configuration Effect Integrity) elevated to CONSTRAINTS.md. CR-08 AUFG set resolved (P0–P4 implementation + enforcement + cross-layer evidence); SET-005 promoted to stable. The contract governs `docs/features/remediation/cr-08-configuration-effect-drift.md` and FIND-013. |

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
| System Health Score | Medium | Run `just check-health` for current score. feature_adoption gate reflects ratcheted baseline debt (no new above ratchet floor). CI remains warning-only for DEGRADED and fails on CRITICAL. CI coverage gate target documented in `gate-exceptions.json`. |
| Frontend RULE-04 regressions | Low | All 37 legacy violations resolved (53→0). `check_frontend_file_size.py` enforces limits in CI. New violations blocked by ratchet. |
| Architecture exception baseline drift | Low | Resolved/revalidated by option B blocker cleanup. The remaining adoption baseline class is the registered inline fallback. RULE-19 sync remains enforced by `--check-sync`. |
| Code Knowledge Graph MCP intermittently unavailable | Medium | Agents fall back to Read/Glob/Grep, losing structural context (callers, dependents, test coverage). Fallback protocol documented in `code-graph-first.md`. Session startup check via `list_graph_stats_tool` recommended. Reported in Reviews 01–04. |

---

> Maintained by: Coordinator, updated at session end
> Last content update: 2026-06-24 (ADR-048 Q1/Q3 follow-up amendments documented — Mode 2 Audit results and Budget Resolver Option D decision; `safe_compose_invocation()` fire-and-forget finding recorded)
