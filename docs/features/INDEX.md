# Feature Registry — Index

> **The canonical list of all Narrare features.**
> Each feature has its own file in `docs/features/`.
> This index is the overview — load individual feature files only when needed.
>
> Feature files serve double duty:
> - Developer reference (what, how, constraints)
> - UI help text source (tooltip, help panel, onboarding)
>
> Location: `docs/features/INDEX.md`
> Maintained by: Architecture Agent + project owner

---

## Status Legend

| Symbol | Status | Meaning |
|--------|--------|---------|
| ✅ | stable | Fully implemented, tested, documented |
| 🔨 | in-progress | Being implemented in current cycle |
| 📋 | planned | Specified, not yet started |
| 💡 | idea | Not yet specified — needs Architecture session |
| ⛔ | deprecated | Removed or replaced |

---

## Feature Areas

### Core Infrastructure
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [INFRA-001](infra/INFRA-001-llm-gateway.md) | LLM Gateway | ✅ | ✅ |
| [INFRA-002](infra/INFRA-002-prompt-system.md) | Unified Prompt System | ✅ | ✅ |
| [INFRA-003](infra/INFRA-003-context-assembly.md) | Context Assembly Pipeline | ✅ | ✅ |
| [INFRA-004](infra/INFRA-004-embedding-store.md) | Embedding Store | ✅ | ❌ |
| [INFRA-005](infra/INFRA-005-memory-layer.md) | Memory Layer (mem0) | ✅ | ✅ |
| [INFRA-006](infra/INFRA-006-a2a-integration.md) | A2A Integration | 📋 | ❌ |
| [INFRA-007](infra/INFRA-007-background-tasks.md) | Background Tasks | ✅ | ❌ |
| [INFRA-008](infra/INFRA-008-mcp-integration.md) | MCP Integration | 📋 | ❌ |
| [INFRA-009](infra/INFRA-009-proactive-context.md) | Proactive Context Loading | ⛔ | ❌ |
> **Note:** INFRA-009 was merged into [KB-005](kb/KB-005-kb-suggest.md) (Proactive KB Suggestions) and is deprecated as a standalone feature.
| [INFRA-010](infra/INFRA-010-prompting-locally.md) | Prompting Locally | ✅ | ❌ |
| [INFRA-011](infra/INFRA-011-ai-feature-stabilization.md) | AI Feature Stabilization Program | ✅ | ❌ |
| [INFRA-012](infra/INFRA-012-prompt-governance-hardening.md) | Prompt Governance Hardening | ✅ | ❌ |
| [INFRA-013](infra/INFRA-013-ai-invocation-adoption-contract.md) | AI Invocation Adoption Contract | ✅ | ❌ |

> **AI feature freeze lifted:** INFRA-011 gates passed and the ADR-027 freeze-lift
> review completed on 2026-06-03. New AI-feature work may resume under ratcheted
> governance: no new prompt/adoption warning growth, unapproved architecture
> exceptions, frontend file-size violations, REST-only AI streaming paths, or
> workaround implementations.

### Setup & Onboarding
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [SETUP-001](setup/SETUP-001-setup-wizard.md) | Setup Wizard (5-step) | ✅ | ✅ |
| [SETUP-002](setup/SETUP-002-demo-content.md) | Demo Projects | ✅ | ✅ |
| [SETUP-003](setup/SETUP-003-import.md) | Project Import | ✅ | ❌ |

> **SETUP-003 v1 implemented (2026-10-02):** MD+TXT browser-upload import
> shipped per [ADR-091](../architecture/decisions/ADR-091-project-import-v1.md)
> (✅ Implemented; design spec
> `docs/superpowers/specs/2026-10-02-project-import-design.md`) — stateless
> two-phase API (`POST /import/preview` parse-only + `POST /import/commit`
> with deterministic re-parse), guardrails (≤ 100 files, ≤ 5 MB per file,
> ≤ 25 MB total), one shared `ImportPreviewPanel`/`ImportModal` surface for
> the Setup Wizard Step-2 inline section and the novel-workspace sidebar
> modal, `importing` i18n (en/de/fr), and the dormant `import_path` stub
> removed BE+FE in one slice. Next.js proxy amendment:
> `experimental.proxyClientMaxBodySize: "30mb"`, pinned ≥ the API total guard
> by a frontend regression test. DOCX / IO-002 / bulk KB extraction remain
> documented follow-up slices.
| [SETUP-004](setup/SETUP-004-provider-config.md) | AI Provider Configuration | ✅ | ✅ |
| [ONBOARD-001](onboarding-user-guide.md) | Onboarding & AI-Einführung | ✅ | ❌ |

> **CR-07 v3 follow-up:** ONBOARD-001 stays stable for its implemented base scope.
> The conceptual KB + Storyboard + AI “aha moment” is tracked separately as
> CR-AUFG-07-17 in `docs/architecture/governance/cr-07-followup-v3.md`.

### Writing
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [WRITE-001](writing/WRITE-001-editor.md) | Writing Editor | ✅ | ✅ |
| [WRITE-002](writing/WRITE-002-new-chapter.md) | AI: New Chapter Generation | ✅ | ✅ |
| [WRITE-003](writing/WRITE-003-extend.md) | AI: Extend Chapter | ✅ | ❌ |
| [WRITE-004](writing/WRITE-004-rewrite.md) | AI: Rewrite Selection | ✅ | ❌ |
| [WRITE-005](writing/WRITE-005-interactive-session.md) | Interactive Writing Session | ✅ | ✅ |
| [WRITE-006](writing/WRITE-006-co-author.md) | Co-Author Mode | ✅ | ❌ |
| [WRITE-007](writing/WRITE-007-inline-suggestions.md) | Inline AI Suggestions | ✅ | ❌ |
| [WRITE-008](writing/WRITE-008-multi-draft.md) | Multi-Draft Generation | 📋 | ❌ |
| [WRITE-009](writing/WRITE-009-unblock.md) | Writer's Unblock Tools | ✅ | ❌ |
| [WRITE-010](writing/WRITE-010-voice-checker.md) | Voice Consistency Checker | ✅ | ❌ |
| [WRITE-011](writing/WRITE-011-volume-management.md) | Volume Management | ✅ | ✅ |
| [WRITE-012](writing/WRITE-012-chapter-summary.md) | Chapter Summary | ✅ | ❌ |
| [WRITE-013](writing/WRITE-013-workflows.md) | Writing Workflows | 📋 | ❌ |
| [WRITE-014](writing/WRITE-014-context-inspector.md) | Context Inspector | ✅ | ❌ |

### Series
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [SERIES-001](series/SERIES-001-foundation.md) | Series Foundation | ✅ | ❌ |
| [SERIES-002](series/SERIES-002-generation-context.md) | Series Generation Context | ✅ | ❌ |
| [SERIES-003](series/SERIES-003-voice-hierarchy.md) | Series Voice Hierarchy | ✅ | ❌ |
| [SERIES-004](series/SERIES-004-cross-novel-drift.md) | Series Cross-Novel Drift | ✅ | ❌ |

> **SERIES-004 stable (2026-08-08):** Series Cross-Novel Drift (Spec 4 of the
> Series program) — **all five slices shipped** and merged to `main` via PR #145
> (squash `c007b559`). Implemented against
> [ADR-079](../architecture/decisions/ADR-079-series-cross-novel-drift.md)
> (✅ Implemented). Two cross-novel drift modes: (a) **canon-contradiction** via
> new `SeriesConsistencyAgent` (novel chapter prose vs series **Canon KB**;
> `CanonConflict` list with severity; mirrors the `BandSummaryAgent` 1-call
> pattern + ADR-035 validator; governed Mode-1 `analysis/en/series_consistency`
> template) and (b) **series-scope voice drift** reusing the existing
> `AuthorVoiceDriftAgent` pipeline (no new drift agent) with
> `SeriesSettings.author_voice` (Spec 3) as the **trend baseline** (one signal,
> not a fixed template — closes ADR-078's Spec-4 Review-Trigger item).
> **Read-scope = current-band-vs-series** (not full-series batch scan — YAGNI);
> **integrated in Bände-Tab** (no separate tab — `SeriesDriftPanel` →
> `SeriesConflictList` + `SeriesDriftSummary`); **stateless v1** (no persistence
> — results repository + retrieval endpoint deferred); new
> `SeriesVoiceDriftService` (pipeline reused, not duplicated — keeps the
> novel-level `AuthorVoiceDriftService` byte-identical, RULE-06); standalone
> regression-tested; JSON endpoints (not SSE). Frontend (Task 4) + i18n (Task 5:
> the `series.drift.*` namespace, en/de/fr — consolidating consistency +
> voice-drift under one namespace, not the originally-predicted split) landed in
> commit `ede62081` before the #145 squash-merge. **The Series program Spec 1–4
> is complete and formally closed; Spec 5 (Export) was retired 2026-08-14 as YAGNI
> (PO decision — see `../superpowers/specs/2026-08-14-post-export-followups-design.md` §2).**

> **SERIES-003 implemented (2026-08-05):** Series Voice Hierarchy (Spec 3 of the
> Series program) implemented across Core → Backend → Frontend against
> [ADR-078](../architecture/decisions/ADR-078-series-voice-hierarchy.md)
> (✅ Implemented) — **Delta** resolution model (series voice as foundation, novel
> voice additive, per-novel opt-out; chosen over Override/Blend/Cascade). Pure-Core
> `render_author_voice_delta()` composes the existing descriptive-only renderer;
> `{{author_voice}}` is **extended** (no new prompt variable/route/manifest entry).
> `SeriesVoiceService` **reuses the existing `AuthorVoiceAgent`** (no new agent,
> RULE-01b). `ProjectSettings.use_series_voice: bool` (default True) + Alembic
> `0039` (RULE-14). Frontend Voice tab activated + opt-out card +
> `useSeriesVoice` hooks + `series.voice.*` / `novel.settings.useSeriesVoice.*`
> i18n (en/de/fr). **Closes ADR-074 Review Trigger Voice-Teil — FULLY CLOSED**
> (storage by ADR-075, voice model by ADR-078) + ADR-075 Spec-3 item. Status →
> `stable`. Coordinator commit pending.

> **SERIES-002 implemented (2026-08-02):** Series Generation Context (Spec 2 of
> the Series program) implemented across all layers against
> [ADR-077](../architecture/decisions/ADR-077-series-generation-context.md)
> (✅ Implemented) — per-band `BandSummary` (1:1 to Novel) with auto-generated
> `full`/`short` summary + user `override`; pure-Core `SeriesHistoryTier`
> (recency-window: last `context_window_size` bands full, older short;
> "sacrifice older first" token budget); `SeriesHistoryProvider` Backend→Core
> bridge + KB-Redirect (merged Canon+Overlay via Spec 1's
> `find_merged_for_novel`); `{{series_history}}` governed SYSTEM_VAR threaded
> through `WritingPipeline`; Triple-Trigger generation (manual / auto
> series→completed / lazy). Frontend `BandSummaryCard` + `BandOverrideEditor`
> + `useBandSummary` hooks + `series.bandSummary.*` i18n (en/de/fr). Alembic
> `0038` (RULE-14). Closes ADR-075's Spec 2 Review Trigger. **Open work:** the
> context-window *slider* (UI to tune `context_window_size`) — the setting
> works at default 3; the settings API exposure + slider remain. *(Planned as
> ADR-076; renumbered to 077 — ADR-076 was claimed by the CURRENT_STATE
> volatility policy.)* Status → `stable`.

> **SERIES-001 implemented (2026-07-29):** Foundation + KB Evolution (Spec 1 of
> the Series program) implemented across all layers against
> [ADR-075](../architecture/decisions/ADR-075-series-foundation.md) (✅
> Implemented) — hybrid KB Series-Canon+Novel-Overlay (Option C), Schema 2A+STI,
> N2 Series-Workspace, Single-Series, Policy iii scope defaults + Policy α
> adaptive join. Alembic `0037` (RULE-14). Closes the Series-storage portion of
> ADR-074's Review Trigger (Voice-Teil open for Spec 3). Commit range
> `46a5c425`→`37f0cc17`. Status → `stable`.
> **PR #145 review fixes (2026-08-02):** C1 IDOR ownership enforcement,
> C2 `kb_entries.series_id` FK SET NULL + Canon-fate, C3 `JoinReasonCode`,
> D4 demote-409 Canon-integrity guard, I-A1/I-A2 Protocol splits + typed
> `NovelRow` — backend `c6d24472` + frontend `9ed37bc0`; documented in
> ADR-075 §A–F (Post-Implementation Amendment). Status remains `stable`.

### Chat
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [CHAT-001](chat/CHAT-001-free-form-chat.md) | Free-Form Chat | ✅ | ❌ |

### Notes
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [NOTES-001](notes/NOTES-001-scratchpad.md) | Scratchpad | ✅ | ❌ |

### Knowledge Base
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [KB-001](kb/KB-001-entity-management.md) | KB Entity CRUD | ✅ | ✅ |
| [KB-002](kb/KB-002-kb-session.md) | Assisted KB Creation (AI-guided creation) | ✅ | ❌ |
| [KB-003](kb/KB-003-kb-improve.md) | AI: Improve KB Entry | ✅ | ❌ |
| [KB-004](kb/KB-004-kb-consistency.md) | AI: KB Consistency Check | ✅ | ❌ |
| [KB-005](kb/KB-005-kb-suggest.md) | Proactive KB Suggestions | ✅ | ✅ |
| [KB-006](kb/KB-006-worldbuilding.md) | Worldbuilding Assistant | ✅ | ❌ |
| [KB-007](kb/KB-007-extraction.md) | Entity Extraction from Chapters | ✅ | ❌ |
| [KB-008](kb/KB-008-knowledge-graph.md) | Knowledge Graph | ✅ | ❌ |
| [KB-009](kb/KB-009-kb-merge.md) | KB Entity Merge / Deduplication | ✅ | ❌ |
| [KB-010](kb/KB-010-editor-graph.md) | Editor-Integrated Knowledge Graph | 💡 | ❌ |
| [WIKI-001](kb/WIKI-001-llm-wiki.md) | LLM Wiki — Precomputed Context Layer | ✅ | ❌ |

### Analysis
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [ANAL-001](analysis/ANAL-001-beta-reader.md) | Beta Reader Simulation | ✅ | ❌ |
| [ANAL-002](analysis/ANAL-002-sentiment.md) | Sentiment Analysis | ✅ | ❌ |
| [ANAL-003](analysis/ANAL-003-readability.md) | Readability Analysis | ✅ | ❌ |
| [ANAL-004](analysis/ANAL-004-pov.md) | POV Analysis | ✅ | ❌ |
| [ANAL-005](analysis/ANAL-005-coreference.md) | Coreference Analysis | ✅ | ❌ |
| [ANAL-006](analysis/ANAL-006-sensitivity.md) | Sensitivity Review | 📋 | ❌ |
| [ANAL-007](analysis/ANAL-007-voice-author.md) | Author Voice Profiling | ✅ | ❌ |
| [ANAL-008](analysis/ANAL-008-voice-character.md) | Character Voice Profiling | ✅ | ❌ |
| [ANAL-009](analysis/ANAL-009-voice-drift.md) | Voice Drift Detection | ✅ | ❌ |
| [ANAL-010](analysis/ANAL-010-literary-suite.md) | Literary Analysis Suite | 📋 | ❌ |
| [ANAL-011](analysis/ANAL-011-plot-analysis.md) | Plot Analysis | 📋 | ❌ |

> **ANAL-008 (Character Voice Profiling):** Implemented (2026-06-29) across all
> layers against [ADR-055](../architecture/decisions/ADR-055-character-voice-contract.md)
> — the character-voice storage contract (nested `voice_analysis` extension to the
> live `SpeechPatterns` schema, hybrid metrics per ADR-021, self-contained dialogue
> attribution) and the VOICE prompt-surface route (makes `LLMIntent.VOICE`
> routeable). Status → `stable` (validated: `just check` 9/9, 8341 backend + 2287
> frontend tests green). `character_voice` runtime adoption is **runtime-verified**
> (probes landed in `ee1cfc50`; local commit-gate runtime-evidence-aware via ADR-056).
> The earlier lossy
> field-mapping (quotes in `body_language` etc.) was removed.

> **WRITE-010 (Voice Consistency Checker):** Implemented + runtime-verified
> (2026-06-30) across all layers against
> [ADR-057](../architecture/decisions/ADR-057-voice-check-checking-path-contract.md)
> (✅ Implemented) — the voice-check checking-path contract (extends
> `CharacterVoiceProfile` with `voice_metrics`, surfaced via
> `VoiceProfileConsumer.assemble_for_checking` — no KB bypass; closes ADR-055
> Risk #1), hybrid deterministic-delta + LLM scoring (ADR-021), new `voice_check`
> context_mode on the routeable `LLMIntent.VOICE`, module home `analysis/`,
> flag+score scope (no rewrites). All layers (Core 0/1/2a/2b + Backend 3a/3b/3c +
> Frontend 4) implemented and validated; `voice_check` is static ✅, runtime ✅,
> and adopted ✅ (adoption_debt 5 → 1 — true debt only). Status → `stable`.

> **ANAL-009 (Voice Drift Detection — Phase 1: Character Voice Drift):** Implemented
> + runtime-adopted (2026-07-26) across all layers against
> [ADR-073](../architecture/decisions/ADR-073-voice-drift-character.md)
> (✅ Implemented) — the character-voice-drift longitudinal contract. Phase 1 is the
> **third** governed mode on the routeable `LLMIntent.VOICE` (`voice_drift`
> context_mode + governed EN template, Mode 1 ADR-054). Comparison model =
> profile-trend signal (i) + adjacent-chapter jump detection (iii), both reusing
> `voice_check_scoring.voice_metric_distances` (no duplication — satisfies ADR-057
> Risk #3; closes ADR-055 Risk #2). New `CharacterVoiceDriftAgent` (1 call per
> character, trend-classifier) + `voice_drift_scoring` (pure Core, deterministic
> banding). Novel-scoped SSE `POST /analysis/voice-drift/{novel_id}` (read-only —
> writes nothing to KB; consumes `VoiceProfileConsumer.assemble_for_checking`, no
> SSOT bypass). Frontend `VoiceDriftPanel` (Layout γ: heatmap overview +
> expandable per-row detail) + `useCharacterVoiceDrift` hook + i18n (en/de/fr).
> Commit range `a7aa3286` → `e899faae` (Core → Backend → Frontend → Platform).
> `voice_drift` is static ✅ / runtime ✅ / adopted ✅ (PASS); adoption_debt 5 → 1.
> `just check` 9/9, 9759 unit + 3002 frontend tests, pyright 0. Status → `stable`.
> **Phase 2 (Author Voice: storage SSOT + profiling + drift) remains deferred** to
> a separate future ADR — not claimed done.

### Planning
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [PLAN-001](planning/PLAN-001-scene-planning.md) | Scene Planning | 📋 | ❌ |
| [PLAN-002](planning/PLAN-002-gap-analysis.md) | Narrative Gap Analysis | 📋 | ❌ |
| [PLAN-003](planning/PLAN-003-structure.md) | Story Structure Visualization | ✅ | ✅ |
| [PLAN-004](planning/PLAN-004-timeline.md) | Timeline Management | ✅ | ❌ |
| [PLAN-005](planning/PLAN-005-storyboard.md) | Storyboard View | ✅ | ✅ |
| [PLAN-006](planning/PLAN-006-character-arc.md) | Character Arc Analysis | ✅ | ❌ |

> **Note:** PLAN-003 (Structure) and PLAN-005 (Storyboard) were implemented together as a merged feature. PLAN-003's structure adapters power PLAN-005's stage layout. PLAN-004 Timeline Management is fully implemented through Phase 4 (AI timeline analysis, extraction, consistency checks, frontend visualization). PLAN-006 Character Arc Analysis is fully implemented (backend service + frontend `CharacterArcPanel` UI).
>
> **Supplement:** `planning/PLAN-004-architecture.md` is an architecture supplement for PLAN-004 (Timeline Management), not a separate feature entry. It documents the internal architecture of the timeline feature.

### AI Assist (Standalone Operations)
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [ASSIST-001](ai_assist/ASSIST-001-plot-check.md) | Plot Consistency Check | 📋 | ❌ |
| [ASSIST-002](ai_assist/ASSIST-002-title-suggest.md) | Title Suggestions | 📋 | ❌ |
| ~~ASSIST-003~~ | ~~Story Chat Assistant~~ | ⛔ | ❌ |
| [ASSIST-004](ai_assist/ASSIST-004-dialogue-coach.md) | Dialogue Coach | ✅ | ❌ |

> **ASSIST-004 implemented (2026-07-24):** All layers landed against
> [ADR-069](../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md)
> — Core agent + types + governed template, Backend `DialogueCoachService`
> (run/stream) + SSE router, Frontend `DialogueCoachPanel` + editor wiring,
> and the RULE-18b voice_fidelity weight-effect eval suite (Pydantic Evals).
> Commit range `ace72dc7` → `a9a740b8` (28 commits). Status → `stable`.

> **Note:** ASSIST-003 (Story Chat Assistant) has been superseded by [CHAT-001](chat/CHAT-001-free-form-chat.md) with a scoped, architecturally grounded design. See the new spec for details.

### Generation
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [GEN-001](generation/GEN-001-name-generator.md) | Character/Place Name Generator | ✅ | ✅ |
| [GEN-002](generation/GEN-002-research.md) | Research Assistant | 📋 | ❌ |

### Consistency
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [CONS-001](consistency/CONS-001-checker.md) | Consistency Checker | ✅ | ❌ |
| [CONS-002](consistency/CONS-002-rules.md) | Custom Consistency Rules | 📋 | ❌ |

### Learning & Adaptation
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [LEARN-001](learning/LEARN-001-feedback-loop.md) | Feedback & Learning Loop | ✅ | ✅ |
| [LEARN-002](learning/LEARN-002-style-adaptation.md) | Adaptivity Dashboard | ✅ | ❌ |

> **LEARN-002 implemented (2026-07-24):** All layers landed against
> [ADR-069](../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md)
> — Backend (4 REST endpoints: context/toggle/weights/snapshots +
> `AdaptiveContextService`), Frontend (`AdaptiveDashboard` + 4 weight sliders +
> source list + snapshot history + 3-state `AdaptiveStatusIndicator`),
> evidence project-scoping
> ([ADR-070](../architecture/decisions/ADR-070-evidence-project-scoping.md):
> `novel_id` column + migration `0035`), and i18n (3 namespaces × 3 locales = 9
> files). Commit range `ace72dc7` → `a9a740b8` (28 commits). Status → `stable`.

### Prompt Customization
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [PROMPT-001](prompts/PROMPT-001-file-overrides.md) | File-based Prompt Overrides | ✅ | ✅ |
| [PROMPT-002](prompts/PROMPT-002-db-templates.md) | User DB Prompt Templates | ✅ | ✅ |
| [PROMPT-003](prompt-customization-ux.md) | Prompt Customization UX | ✅ | ❌ |

> **CR-07 v3 Phase B (complete):** PROMPT-003 was implemented (CR-AUFG-07-16) and
> promoted to `stable` (2026-06-22): provider-free preview, variable
> provenance/metadata, reset-to-default, provider-gated SSE live test. See
> `docs/architecture/governance/cr-07-followup-v3.md`.

### Import / Export
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [IO-001](io/IO-001-export.md) | Manuscript Export | ✅ | ❌ |
| [IO-002](io/IO-002-import.md) | Project Import & Analysis | 📋 | ❌ |
| [IO-003](io/IO-003-sync.md) | External Sync | 📋 | ❌ |

### Internationalization & UI Copy
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [I-Copy-001](i18n/I-Copy-001-formality-register.md) | User-Selectable UI Formality (du / Sie) | ✅ | ❌ |

> **I-Copy-001 (2026-08-08):** Spec created (Overlay-Merge architecture). User-selectable formality
> register for UI copy — familiar (*duzen*/*tutoyer*) vs. neutral (*Siezen*/*vouvoiement*), `de`/`fr`
> only; `en` unchanged. Resolved one layer before next-intl in the message loader
> (`lib/i18n/request.ts`): a sparse `formality/{locale}.json` overlay is deep-merged over the base
> messages when `NEXT_FORMALITY=formal`. Zero call-site migration; zero component changes;
> `next-intl` untouched. Setting name is `formality` (NOT `tone` — collides with `StoryTone`).
> RULE-02 boundary verified (UI-copy-only; cannot reach `core/prompts/`). Cookie-only persistence
> (no backend/migration for v1). Source: Q-015 (✅). The one real cost is editorial
> (~150–300 formal DE/FR variants to author/review). Spec 2026-08-08, shipped 2026-08-09 (`17ad629d` +
`da5c73d2`): 159/159 DE/FR tone-sensitive variants (FR = forward-correct no-op — base
already vouvoiement); switcher beside the auth-screen language switcher; loader behavior
tests 2026-08-18 (B closure). Status → `implemented`.

### Settings & Configuration
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [SET-001](settings/SET-001-user-settings.md) | User Settings | ✅ | ✅ |
| [SET-002](settings/SET-002-project-settings.md) | Project Settings | ✅ | ✅ |
| [SET-003](settings/SET-003-model-config.md) | Per-task Model Configuration | ✅ | ✅ |
| [SET-004](settings/SET-004-shortcuts.md) | Keyboard Shortcuts | 📋 | ❌ |
| [SET-005](settings/SET-005-configurable-token-limits.md) | Configurable Token Limits | ✅ | ❌ |
| [KEYBOARD-001](keyboard-consistency.md) | Tastatur-Konsistenz | ✅ | ❌ |

### Analytics & Cost
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [STATS-001](analytics/STATS-001-writing-stats.md) | Writing Statistics | 📋 | ❌ |
| [STATS-002](analytics/STATS-002-cost-tracking.md) | AI Cost Tracking | 📋 | ❌ |

### Adapter / Integration
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| ADAPTER-001 | MCP (Model Context Protocol) Adapter | 💡 | ❌ |
| ADAPTER-002 | A2A (Agent-to-Agent) Adapter | 💡 | ❌ |

> **Adapter status:** MCP and A2A are planned roadmap adapters, not yet implemented.
> The Service Layer is designed for multi-adapter capability under RULE-12/13 (service
> layer is the only public API; streaming/non-streaming share one interface).
> Implementation requires resolution of Q-001 (MCP auth strategy) and Q-002 (A2A
> streaming requirement) before adapter-specific specs can be written.
>
> **Contract-Test Gates (required before first adapter implementation):**
> 1. Service contracts must be adapter-neutral (see CONSTRAINTS.md RULE-12).
> 2. Streaming/non-streaming signatures must work identically (see CONSTRAINTS.md RULE-13).
> 3. Adapter specs must define contract tests for Service Layer calls, auth/identity
>    mapping, protocol error mapping, streaming/non-streaming parity, and the invariant
>    that adapter files contain no business logic.
> 4. No `apps/mcp/` or `apps/a2a/` skeleton is created only to satisfy a review item;
>    implementation starts only after Q-001/Q-002 are resolved or explicitly scoped in
>    an approved adapter spec.

---

### Supplementary Documentation

The following directories contain supplementary docs that are NOT standalone features:

| Location | Type |
|----------|------|
| `docs/features/remediation/` | CR-item remediation specifications (linked from governance docs) |
| `docs/features/ai-ux/` | CR-07 UX follow-up specifications (CR-AUFG-07-18 through CR-AUFG-07-24) |
| `docs/features/planning/PLAN-004-architecture.md` | Architecture supplement for PLAN-004 (Timeline) |

These are not listed as features in the registry above but are tracked here for discoverability.

---

## Feature File Schema

Every feature file follows this structure:

```markdown
# [ID] — [Feature Name]

[Frontmatter — see schema below]

## What it does
[1-3 sentences. Precise. No jargon. This becomes the UI help text.]

## Why it exists
[The user problem this solves. Connects to PROJECT_VISION.md.]

## How it works (User perspective)
[Step-by-step from the user's point of view. No implementation details.]

## How it works (Technical)
[Implementation details. Which services, contracts, agent, prompt.]

## Constraints & Edge Cases
[What it cannot do. What happens when things fail.]

## Related Features
[IDs of features that interact with this one.]

## Status & History
[When added, any significant changes.]
```

### Frontmatter Schema

```yaml
---
id: WRITE-002
title: "AI: New Chapter Generation"
status: planned          # planned | in-progress | stable | deprecated
area: writing            # writing | kb | analysis | planning | setup | etc.
mvp: false               # included in first running version?

# UI text — consumed by frontend help system
ui_tooltip: "Generate a complete new chapter draft using your KB and story context."
ui_help_short: |
  Ask the AI to write a complete new chapter. Narrare automatically
  loads your relevant characters, locations, and story context — you
  just describe what should happen.
ui_help_long: |
  [Full help text for the help panel — can be multiple paragraphs,
   can reference other features. Markdown supported.]
ui_available_in: [editor, chapter-list]  # where the help icon appears

# Developer reference
service: writing/draft_service.py
contract: writing/contracts.py#DraftServiceProtocol
router: writing/router_drafts.py
prompt: core/prompts/_bundled/writing/en/new_chapter/system.md
requires: [INFRA-001, INFRA-002, INFRA-003, KB-001]
---
```

---

## Adding a New Feature

1. Assign the next ID in the appropriate area
2. Copy `_TEMPLATE.md` from this directory
3. Fill in all frontmatter fields
4. Write all sections — especially `ui_help_short` (required for UI)
5. Add to this index
6. If MVP=true: add to `MVP_PLAN.md` implementation list
7. Bring to Architecture Agent for review before implementation starts

---

> Last updated: 2026-10-02 — SETUP-003 (Project Import) v1 → `stable` (implemented per ADR-091 ✅ Implemented: MD+TXT browser multipart upload, stateless preview/commit with deterministic re-parse, `import_path` stub removal BE+FE, wizard Step-2 inline + sidebar modal entries, Next.js `proxyClientMaxBodySize` "30mb" amendment; DOCX / IO-002 / bulk KB extraction documented follow-ups). Prior 2026-08-23 — NOTES-001 (Scratchpad) → `stable` (new `notes` feature area registered). Novel-independent notes with type (idea/concept/question/other), free-form tags, Markdown content, and an optional single link to one novel *or* one series (`ON DELETE SET NULL` — the note outlives its link; Alembic `0041_notes`: scope CHECK, GIN index on `tags TEXT[]`). Backend `/api/v1/notes` CRUD + `GET /notes/tags` + `POST /notes/search` — semantic via embeddings `source_type="note"` through the ADR-080 in-process pipeline, RULE-11 lexical ILIKE fallback with honest `mode` badge; delete cleans embeddings. Chat: `ChatRequest.note_id` attaches a note as runtime context (`format_note_context_block`, RULE-02-safe) + project-less conversations (`chat_conversations.project_id` nullable, Alembic `0042`). Frontend `/scratchpad` workspace (list rail + filter bar with tag autocomplete + scope filter + editor with Markdown preview/links + `NotesChatDrawer`), sidebar entry, global QuickCapture Ctrl/⌘+Shift+U (single provider mount), `notes.*` i18n en/de/fr. Prior 2026-08-17 — IO-001 gains **DOCX** (C3 of the post-export-followups program: fourth export format — pandoc `--reference-doc` manuscript format [Times 12 pt, 1.5 spacing, first-line indent, centred chapter headings], golden `document.xml` test; plan 2026-08-17-c3-docx-export.md; ADR-081 review-trigger item closed, no new ADR). Prior 2026-08-15 — SERIES-005 (Series Export) retired as YAGNI (PO decision 2026-08-14; Series program formally complete with Specs 1–4; docs-consistency pass C0 of the post-export-followups program). Prior 2026-08-14 — IO-001 (Manuscript Export Pipeline) → `stable` (4-stage non-LLM pipeline: Narrare Normalizer + pandoc + Typst/narrare-roman PDF + EPUB3 + Markdown; Golden-Pages 26 passed, EPUBCheck passed; PR #163; ADR-081 ✅ Implemented; deferred: DOCX, drop cap 5g, isbn/description). Prior 2026-08-08 — SERIES-004 (Series Cross-Novel Drift) → `stable` (Spec 4 of the Series program; all five slices shipped and merged to `main` via PR #145 (squash `c007b559`); Frontend Task 4 + i18n Task 5 (`series.drift.*` namespace, en/de/fr) landed in `ede62081`; canon-contradiction via `SeriesConsistencyAgent` + series-scope voice drift reusing `AuthorVoiceDriftAgent` with `SeriesSettings.author_voice` as trend baseline; current-band-vs-series read-scope; integrated in Bände-Tab; stateless v1; closes ADR-078 Spec-4 Review-Trigger item; Series program Spec 1–4 complete, Spec 5 Export downstream). Prior 2026-08-05 — SERIES-003 (Series Voice Hierarchy) → `stable` (implemented all layers against [ADR-078](../architecture/decisions/ADR-078-series-voice-hierarchy.md); Delta resolution model — series voice foundation, novel voice additive, per-novel `use_series_voice` opt-out; pure-Core `render_author_voice_delta` extends `{{author_voice}}` (no new variable); `SeriesVoiceService` reuses existing `AuthorVoiceAgent` (no new agent); Alembic `0039`; Frontend Voice tab + opt-out card + `useSeriesVoice` hooks + `series.voice.*` i18n (en/de/fr); **closes ADR-074 Review Trigger Voice-Teil — FULLY CLOSED** (storage by ADR-075, voice model by ADR-078) + ADR-075 Spec-3 item). Prior 2026-08-02 — SERIES-002 (Series Generation Context) → `stable` (implemented all layers against [ADR-077](../architecture/decisions/ADR-077-series-generation-context.md); per-band `BandSummary` + pure-Core `SeriesHistoryTier` recency-window + `SeriesHistoryProvider` Backend→Core bridge + KB-Redirect (merged Canon+Overlay via Spec 1's `find_merged_for_novel`) + `{{series_history}}` SYSTEM_VAR + Triple-Trigger generation (manual / auto series→completed / lazy); Alembic `0038`; Frontend `BandSummaryCard` + `BandOverrideEditor` + `useBandSummary` hooks + `series.bandSummary.*` i18n (en/de/fr); closes ADR-075 Spec 2 Review Trigger. **Open work:** the context-window *slider* — the setting works at default 3; settings-API exposure + slider remain. Renumbering: planned as ADR-076, landed as ADR-077 — ADR-076 was claimed by the CURRENT_STATE volatility policy). Same-day — SERIES-001 docs reconciliation for PR #145 review fixes (C1–C4 + D4 + contract splits; stale `contracts.py` path references corrected in ADR-075 + SERIES-001; ADR-075 Post-Implementation Amendment §A–F verified accurate against implementation; status remains `stable`). Prior 2026-07-29 — SERIES-001 (Series Foundation) → `stable` (implemented all layers against [ADR-075](../architecture/decisions/ADR-075-series-foundation.md); hybrid KB Canon+Overlay + Schema 2A+STI + Series-Workspace; Alembic `0037`; closes ADR-074 Review Trigger Series-storage-Teil; commits `46a5c425`→`37f0cc17`). Prior 2026-07-26 — ANAL-009 Phase 1 (Character Voice Drift) → `stable` (implemented all layers against [ADR-073](../architecture/decisions/ADR-073-voice-drift-character.md); Core scoring + agent + `voice_drift` governed template (third VOICE mode), Backend `VoiceDriftService` + SSE `POST /analysis/voice-drift/{novel_id}`, Frontend `VoiceDriftPanel` (Layout γ) + hook + i18n, Platform probes + runtime markers; commits `a7aa3286`→`e899faae`; `voice_drift` static/runtime/adopted ✅, adoption_debt 5 → 1; Phase 2 author-voice deferred). Earlier 2026-07-24 — ASSIST-004 (Dialogue Coach) → `stable` (implemented all layers against [ADR-069](../architecture/decisions/ADR-069-adaptive-context-dialogue-coach.md); Core agent + governed template, Backend `DialogueCoachService` run/stream + SSE router, Frontend `DialogueCoachPanel` + editor wiring, RULE-18b weight-effect eval suite via Pydantic Evals; commits `ace72dc7`→`a9a740b8`, 28 commits). LEARN-002 (Adaptivity Dashboard) → `stable` (implemented all layers; 4 REST endpoints + `AdaptiveContextService`, `AdaptiveDashboard` + 4 weight sliders + `AdaptiveStatusIndicator`, evidence project-scoping [ADR-070](../architecture/decisions/ADR-070-evidence-project-scoping.md) with `novel_id` + migration `0035`, i18n 3×3=9 files). Earlier 2026-07-19 — LEARN-002 recalibrated from "Style Adaptation" (statistical pipeline) to "Adaptivity Dashboard"; ASSIST-004 detailed with implementation paths; pilot consumer of the new `AdaptiveContext` Core contract. Earlier 2026-06-30 — WRITE-010 (Voice Consistency Checker) → `stable` (ADR-057 ✅ Implemented; implemented across all layers + runtime-verified; `voice_check` static/runtime/adopted, adoption_debt 5 → 1 — true debt). Earlier 2026-06-30 — WRITE-010 spec authored against ADR-057 (checking-path contract + `voice_check` prompt surface; closes ADR-055 Risk #1), promoted to `stable` after all layers + runtime evidence landed. 2026-06-29 — ANAL-008 (Character Voice Profiling) → `stable` (implemented all layers; ADR-055 implemented); INFRA-007 (Background Tasks) and INFRA-012 (Prompt Governance Hardening) promoted to `stable`; WRITE-009 (Writer's Unblock Tools) → `stable`; ANAL-005 (Coreference Analysis) → `stable`; PROMPT-003 INDEX status corrected to `stable` (spec was already stable since 2026-06-22); PLAN-006 note updated (now has a frontend UI). CR-07 Follow-up v3 governance links (PROMPT-003/CR-AUFG-07-16, ONBOARD-001/CR-AUFG-07-17) retained. SET-005 remains `stable` (ADR-051). ADAPTER-001/002 remain planned, not implemented; Q-001/Q-002 stay adapter-spec blockers.
> Features are specified before they are implemented — never after
