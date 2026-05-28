# Narrare — Current State

> **This document is the live status of the project.**
> Every agent reads this at the start of every session.
> Updated at the end of every session by the responsible agent.
>
> Location: `docs/_shared/CURRENT_STATE.md`

---

## Last Updated

Date: 2026-05-28
Updated by: NarrareDocsSpecialist
Session summary: ANAL-002 Sentiment Analysis and CONS-001 Consistency Checker backlog items fully implemented (spec-complete). Cross-chapter arc trajectory, word count warnings, chart export, hover tooltips, issue actions, KB pre-check, scope selector, fact deduplication all done. 38 new tests (8 warning + 30 rule + 22 rule helper + 6 service). Docs synced.

---

## Project Phase

```
Phase 0: Repository Foundation     ✅ COMPLETE
Phase 1: Core Infrastructure       ✅ COMPLETE
Phase 2: API Foundation            ✅ COMPLETE
Phase 3: Setup Wizard Backend      ✅ COMPLETE
Phase 4: Frontend Foundation       ✅ COMPLETE
Phase 5: Integration & Polish      ⏳ IN PROGRESS
```

---

## What Exists Right Now

### Documentation (complete)

**Shared Foundation (`docs/_shared/`):**
- `CONSTRAINTS.md` — 13 rules, CI-enforced
- `TECH_STACK.md` — canonical technology decisions
- `GLOSSARY.md` — shared vocabulary
- `CURRENT_STATE.md` — this file

**Development (`docs/development/`):**
- `coding-standards.md` — Python 3.14 + TypeScript standards
- `testing-standards.md` — test architecture, coverage targets, fixtures
- `ui-principles.md` — UX principles, component structure, state management
- `deployment-guide.md` — CI/CD, dev environment, release process
- `orchestrator.md` — orchestrator agent definition

**Reference (`docs/reference/`):**
- `project-vision.md` — why, what, for whom
- `directory-structure.md` — canonical file locations

**Architecture (`docs/architecture/`):**
- `decisions/INDEX.md` + ADR-001 through ADR-007
- `questions/INDEX.md` + Q-001 through Q-005

**Features (`docs/features/`):**
- `INDEX.md` — 40+ features catalogued
- `_TEMPLATE.md`
- Individual feature specs (SETUP-001, SETUP-002, WRITE-001) referenced in INDEX but not yet created as separate files

**MVP (`docs/mvp/`):**
- `mvp-plan.md` — 5-phase plan for first running version

### Demo Content (complete)

**German demo ("Im stillen Wald") — `apps/api/narrare/setup/demo_data/de/im-stillen-wald/`:**
- Chapter 1: "Das Flüstern im Wald" (`ch-de-001-fluestern.md`) ✅
- Chapter 2: "Grenze der Welten" (`ch-de-002-grenze-welten.md`) ✅
- KB: Characters — Anna Müller, Johann Bauer, Der Waldgeist ✅
- KB: Locations — Das Försterhaus, Der stille Wald, Das Dorf ✅

**Fantasy demo ("Echoes of the Thornwall") — `apps/api/narrare/setup/demo_data/en/echoes-of-the-thornwall/`:**
- 4 chapters (`ch-en-001` through `ch-en-004`) ✅
- 16 KB entries: 5 characters, 4 locations, 2 factions, 3 systems, 1 object, 1 timeline ✅

**SciFi demo ("Dead Signal") — `apps/api/narrare/setup/demo_data/en/dead-signal/`:**
- 3 chapters (`ch-en-ds-001` through `ch-en-ds-003`) ✅
- 8 KB entries: 3 characters, 2 locations, 1 object, 2 systems ✅

### Code

#### `packages/core/narrare_core/` — Shared Domain Logic (Phase 1)

**LLM Layer (`llm/`):**
- `gateway.py` — Single LLM Gateway (ADR-001), ~290 lines
- `_providers/` — OpenAI, Anthropic, Ollama, ZAI, Others, Registry (6 providers); all accept explicit `api_key`/`base_url`
- `observability.py` — Langfuse integration (LLM tracing, cost tracking)
- `result.py`, `retry.py`, `metrics.py`, `embeddings.py`
- `intents.py` — `LLMIntent` enum (incl. `GENERATE`, `NAME_GENERATE`, `TITLE_GENERATE`), `IntentCategory` enum (incl. `GENERATION`), `INTENT_CATEGORY_MAP`, `ResolvedModelConfig`
- `model_routing.py` — `ModelRoutingResolver` protocol and `ResolvedModel` result type
- `override_schemas.py` — Pydantic schemas for category/intent/token limit overrides

**Prompt System (`prompts/`):**
- `composer.py` — Prompt composition with preference auto-injection and culture injection (`{{culture_guidelines}}`). Agent-PromptComposer integration: all 5 writing agents receive system prompts from PromptComposer (RULE-02 compliance). XML encapsulation wraps user-controlled content to protect against prompt injection.
- `registry.py` — Prompt registry with `resolve_culture()` method (EN fallback)
- `management.py` — `PromptManagementService` — list, get, save, reset, cascade, updates, diff
- `variable_metadata.py` — Variable Registry with descriptions for UI sidebar
- `variable_engine.py` — Variable interpolation
- `context.py` — `PromptContext` with `user_preferences`, `avoidance_patterns`, `style_constraints` fields
- `meta.py`
- `_bundled/generation/` — 3 name generation prompts (en/de/fr) + 9 culture definitions (fantasy/modern/scifi × 3 langs)
- Prompt engineering standards: Chain-of-Thought reasoning, negative examples, scratchpad pattern, structured output format enforced across all new prompts

**Memory Layer (`memory/`):**
- `protocols.py` — `MemoryClientProtocol`, `FeedbackServiceProtocol`, `PreferenceServiceProtocol`
- `models.py` — `FeedbackEvent`, `Preference`, `FeedbackAction` enum
- `mem0_client.py` — `Mem0Client` factory + `NullMemoryClient` graceful degradation (RULE-01 exception)
- `feedback_service.py` — `FeedbackService` — records feedback to PostgreSQL + mem0
- `preference_service.py` — `PreferenceService` — extracts preferences from mem0 for prompt injection

**Shared Utilities (`shared/`):**
- `result.py` — Result type pattern (Ok/Err)
- `crypto.py` — Fernet encryption for API keys (reads `NARRARE_ENCRYPTION_KEY`)
- `pagination.py`, `frontmatter.py`, `file_utils.py`, `errors.py`

**Embedding Layer (`embeddings/`):**
- `store.py` — EmbeddingStoreProtocol, SearchResult, EmbeddingStats
- `hash.py` — compute_content_hash (SHA-256 for dirty detection)
- `scoring.py` — Hybrid search scoring (0.5 similarity + 0.3 usage + 0.2 recency)

**Stub Modules (interfaces only):**
- `context/`, `cache/`, `schemas/`

**Context Layer (`context/`):**
- `proactive_service.py` — ProactiveContextService (3-stage pipeline: name match → embedding search → hybrid scoring)
- `name_matching.py` — match_entity_names() with regex word boundaries
- `suggestion.py` — Suggestion + EntityMetadata dataclasses
- `contracts.py` — ProactiveContextProtocol

**Writing Layer (`writing/`):**
- `models.py` — GenerationMode, GenerationStatus, WritingContext, GenerationRequest, SessionState, SceneState
- `context_models.py` — KBEntity, RecentChapter dataclasses
- `contracts.py` — WritingPipelineProtocol, ContextAssemblerProtocol, DraftProcessorProtocol, SessionManagerProtocol
- `context_assembler.py` — WritingContextAssembler with 5-tier ranking + token budgets + entity connection promotion (first-degree connections of referenced entities promoted from suggested → referenced tier)
- `budget.py` — TokenBudgetManager for tier allocation; `cap_to_budget()` lightweight token enforcement utility for non-tier contexts
- `draft_processor.py` — DraftProcessor with artifact removal + markdown normalization
- `pipeline.py` — WritingPipeline with 4-mode dispatch (full_draft, scene_by_scene, interview_assisted, interactive_session)
- `pipeline_scene.py` — Scene-by-scene mode logic
- `pipeline_interview.py` — Interview-assisted mode logic
- `session_manager.py` — SessionManager with cache-backed persistence (SessionCacheProtocol)
- `prompts/_bundled/writing/` — 14 system prompts (4 modes × 3 languages + rewrite_selection + story_suggest) + 4 tone variants
- `prompts/_bundled/analysis/` — 4 prompts (review, preferences, summarize, remap — en with de/fr translations)
- `prompts/_bundled/planning/` — 1 prompt (outline — en with de/fr translations)

**KB v2 Layer (`kb/` + `templates/`):**
- `kb/schemas/` — 8 entity schemas (character, location, faction, object, system, timeline, concept, setting) with nested metadata groups (CharacterMetadata, LocationMetadata, etc.)
- `templates/models.py` — Template, TemplateField, TemplateFieldGroup, TemplateSection, TemplateMeta models
- `templates/parser.py` — parse_template() with v1 flat + v2 grouped frontmatter support
- `templates/defaults/` — 8 language-neutral templates (one per entity type, v3 format with field_groups + sections). Display text comes from i18n exclusively. 24 → 8 files consolidated.
- Character template: 7 groups, 44 fields. Location: 4 groups, 17 fields. Faction: 4 groups, 15 fields. Object: 4 groups, 17 fields. System: 4 groups, 15 fields. Timeline: 2 groups, 10 fields. Concept + Setting: v3 format with domain-specific groups. No language dimension — all display text via i18n.

**Event System (`events/`):**
- Event types, bus protocol (Protocol-based), NullEventBus for testing

**Agent Layer (`agents/`):**
- `base.py` — NarrareAgent base class with `with_meta()` factory for meta-prompt loading
- `summary_agent.py` — ChapterSummaryAgent (NarrareAgent subclass): produces SummaryOutput with summary text, key points, word count, metadata
- `summary_types.py` — SummaryOutput Pydantic output type
- `writing_graph.py` — WritingGraph with 6 steps: plan_outline → write_draft → review_draft → {approved→finalize, needs_revision→revise_draft→write_draft} → generate_summary → end
  - `generate_summary` step runs after `finalize`, calls ChapterSummaryAgent, stores result in `ctx.state.summary`, sets `WritingStatus.SUMMARIZED`
- `test_writing_graph_summary.py` — Unit tests for WritingGraph's generate_summary step
- `kb_assist_agent.py` — KBAssistAgent (4-mode: question, suggest, draft, complete) with KBAssistDeps
- `kb_assist_types.py` — KBAssistOutput (discriminated union output type)
- `extraction_agent.py` — ExtractionAgent for structured KB extraction
- `extraction_types.py` — ExtractionOutput + ExtractionItem

**Planning Layer (`planning/`):**
- `models.py` — ChapterOutlineData, SyncStatus enum (5 levels), StageAssignment dataclass
- `sync.py` — StructuralSyncChecker with 5 status levels (empty, planned, on_track, deviated, completed); rule 3b checks summary presence for stronger COMPLETED signal
- `remap.py` — AIRemapService: analyze_chapter_role(), meets_coverage_threshold(), calculate_confidence(); uses chapter summaries for content-aware stage suggestions
- `adapters/base.py` — StructureAdapter Protocol, StageDef/BeatDef dataclasses, StructureAdapterRegistry
- `adapters/three_act.py` — 3-stage adapter (act-1, act-2, act-3)
- `adapters/five_act.py` — 5-stage adapter
- `adapters/heros_journey.py` — 12-stage adapter (condensed to visual layout)
- `adapters/save_the_cat.py` — 15-beat adapter in 3 acts
- `adapters/seven_point.py` — 7 turning-point adapter

#### `apps/api/narrare/` — FastAPI Backend (Phase 2 & 3)

**App Infrastructure (`_app/`):**
- `main.py`, `config.py`, `database.py`, `dependencies.py`, `lifespan.py`, `middleware.py`
- `lifespan.py` runs `alembic upgrade head` on startup (auto-migration), logs schema version, fails fast if migrations break
- `telemetry.py` — OpenTelemetry setup (traces, metrics, FastAPI instrumentation)
- `events.py` — Redis Pub/Sub event bus implementation
- `event_listener.py` — Event → TaskIQ task routing

**Domain Modules (all contract-first per ADR-003):**
- `auth/` — JWT auth: models, service, router, router_me, repository, contracts, schemas, security, cookie_helpers
  - argon2id password hashing (bcrypt backward compatibility for existing hashes)
  - httpOnly refresh token cookie (`narrare_refresh`) — set on login/register, cleared on logout
- `novels/` — CRUD: models → repository → service → router, contracts, schemas
- `chapters/` — CRUD: models → repository → service → router, contracts, schemas
  - Content versioning: ChapterVersion model, version repository/service/router endpoints
- `volumes/` — Full CRUD + stats + reorder: models → repository → service → router, contracts, schemas; enriched model (subtitle, description, word_count_target, is_default); default volume auto-creation; stats aggregation; deletion protection
- `settings/` — Full AI settings: contracts, provider management, model routing, token limits
  - `contracts.py`, `schemas.py`, `models.py`, `repository.py`, `router.py`
  - `user_providers_repository.py`, `user_ai_settings_repository.py`, `project_ai_settings_repository.py`
  - `user_providers_service.py`, `user_ai_settings_service.py`, `project_ai_settings_service.py`
  - `model_routing_resolver.py`
  - Migration: `0004_ai_settings.py`
- `setup/` — Setup wizard: router, service, contracts, schemas, provider_service, provider_schemas, demo_loader
  - `_validation.py` — Step validation pure functions (extracted from service.py, RULE-04 split)
  - `service.py` now writes to both `user_providers` + `user_ai_settings` AND legacy `project_settings`
  - Z.AI dual endpoint selector (General vs Coding API) in Step 4
  - After setup, AI Settings pages work immediately — no more "No key configured"
  - Demo loader reads `metadata.json` from demo_data dirs (author, logline, pov, tags) — no more hardcoded data
  - `demo_data/*/metadata.json` — demo project metadata for each starter template
- `metrics/` — Health/metrics router
- `memory/` — Memory layer: contracts, schemas, models (feedback_events), repository, service, router
  - POST /memory/feedback — Record AI suggestion feedback
  - GET /memory/preferences — Get preference profile
  - DELETE /memory/preferences — Reset preferences
- `prompts/` — Prompt management: contracts, schemas, service, router
  - GET /prompts — List all prompts with source indicators
  - GET /prompts/{id} — Get prompt content + metadata
  - PUT /prompts/{id} — Save/update prompt override
  - DELETE /prompts/{id} — Reset to default
  - GET /prompts/{id}/updates — Check for bundled updates
  - GET /prompts/{id}/diff — Side-by-side diff comparison
  - GET /prompts/variables — List available variables with descriptions
- `generation/` — Generation features: contracts, schemas, name_service, router
  - POST /generation/names — Generate names with culture/type/count options
  - `name_service.py` — existing names list capped at 500 tokens via `cap_to_budget()`

**Writing Module (`writing/`):**
- `models.py` — GenerationRequest SQLAlchemy model
- `schemas.py` — 11 Pydantic request/response schemas
- `contracts.py` — WritingServiceProtocol, GenerationRepositoryProtocol
- `repository.py` — GenerationRepository (CRUD, status transitions, concurrent prevention)
- `service.py` — WritingService (orchestration of pipeline + repo + feedback)
- `scene_service.py` — Scene-by-scene methods
- `stats_service.py` — Generation analytics
- `ws_handler.py` — WebSocket session handler
- `_ws_cache.py` — WebSocket connection cache for active sessions
- `router.py` — REST + SSE endpoints (generate, stream, status, cancel)
- `router_sessions.py` — WebSocket route (`WS /api/v1/writing/sessions/{chapter_id}`)
- `router_stats.py` — Stats endpoints
- Migration 0008 — generation_requests table + FK to chapter_versions
- `summary_contracts.py` — SummaryServiceProtocol, SummaryResult dataclass
- `summary_service.py` — ChapterSummaryService (wraps ChapterSummaryAgent, persists to DB)
- `summary_router.py` — POST `/api/v1/planning/summary/chapters/{chapter_id}` endpoint
- `summary_deps.py` — FastAPI dependency injection for summary service

**KB Module (`kb/`):**
- Full CRUD: models, repository, service, router, contracts, schemas (following RULE-03 contract-first)
- `kb/_utils.py` — MENTION_RE regex for @Name cross-references (Unicode, multi-word support)
- `kb/service.py` — resolve_references(), autocomplete endpoint
- `kb/repository.py` — get_by_name(), search_by_name_prefix() for cross-reference lookup
- `kb/relationship_repository.py` — relationship CRUD + `get_adjacency_map()` for entity connection adjacency data
- `kb/embedding_hooks.py` — EmbeddingHookManager for content hash + TaskIQ task dispatch on KB changes
- `kb/usage_service.py` — ContextUsageService for accept/dismiss tracking (usage_count, last_referenced_at)
- `kb/models.py` — Added `last_referenced_at`, `usage_count` columns for hybrid search scoring
- 8 entity types: character, location, faction, object, system, timeline, concept, setting
- Migration 0011 — expands CHECK constraints for concept + setting entity types
- `kb/assist_service.py` — KBAssistService (orchestrates KBAgent + PromptComposer + ProactiveContext)
- `kb/assist_contracts.py` — KBAssistProtocol, KBAssistEnhancementResponse, KBAssistQuestionResponse, KBAssistSuggestionResponse
- `kb/session_service.py` — KBSessionService (lifecycle: create, answer, suggest, interview, enhance, complete, abandon)
- `kb/session_store.py` — KBCreationSessionStore (Redis-backed via SessionCacheProtocol, 30min TTL)
- `kb/session_models.py` — KBCreationField (provenance tracking), KBCreationSession
- `kb/session_schemas.py` — CreateSessionRequest, AnswerFieldRequest (RULE-04 split from schemas.py)
- `kb/template_fields.py` — get_template_fields() from KB schema registry
- `kb/router_sessions.py` — 8 REST endpoints for KB creation session lifecycle
- `kb/router_sessions_sse.py` — SSE endpoint for streaming AI responses
- `kb/suggest_service.py` — KBSuggestService (API wrapper for ProactiveContextService)
- `kb/suggest_contracts.py` — KBSuggestProtocol (RULE-04 split)
- `kb/usage_contracts.py` — ContextUsageProtocol (RULE-04 split)
- `kb/extraction_apply_service.py` — ExtractionApplyService for applying endorsed extraction items
- `kb/router_extraction.py` — Extraction routes (extract + apply endpoints)

**Templates Module (`templates/`):**
- Full CRUD: models (KBTemplate SQLAlchemy), repository, service, router, contracts, schemas
- Cascade resolution: user override → project override → bundled default (mirrors Prompt system, language-independent)
- `cascade_resolver.py` — TemplateScope enum (USER, PROJECT, GLOBAL) with priority-based resolution
- Migration 0010 — kb_templates table (idempotent, IF NOT EXISTS pattern)
- Migration 0012 — drops `template_language` column from kb_templates; seed now loads 8 language-neutral templates

**Planning Module (`planning/`):**
- Full storyboard + outline management: models, contracts, schemas, repository, service, router, _helpers
- `models.py` — ChapterOutline SQLAlchemy model (chapter_id FK, stage_assignment, planned_beats JSONB, outline_notes)
- `contracts.py` — OutlineRepositoryProtocol, StoryboardServiceProtocol
- `schemas.py` — Pydantic request/response schemas (BeatSchema, OutlineResponse, StoryboardResponse, SyncStatusResponse, RemapPreviewItem, RemapResponse)
- `repository.py` — OutlineRepository (get_by_chapter_id, create, update, get_all_for_novel)
- `service.py` — StoryboardService (get_storyboard, get_sync_status, get_or_create_outline, update_outline, preview_remap, confirm_remap); injects AIRemapService for AI-powered stage suggestions
- `router.py` — 5 REST endpoints under `/api/v1/planning/`
- `_helpers.py` — compute_sync, find_position, to_outline_response, should_use_ai_remap, ai_suggest_stage (extracted per RULE-04)
- Migration 0013 — chapter_outlines table

**Embedding Store Module (`embeddings/`):**
- models, repository, service, router, dependencies, tasks, contracts, schemas
- `models.py` — Embedding SQLAlchemy model with source_type/source_id, content_hash, embedding vector, HNSW index
- `repository.py` — EmbeddingRepository with upsert, search (cosine similarity + hybrid scoring), stats
- `service.py` — EmbeddingService wrapping store + gateway + TaskIQ dispatch
- `router.py` — REST endpoints for search, stats, reindex
- `tasks.py` — TaskIQ background tasks for embedding generation
- `contracts.py` — EmbeddingServiceProtocol, EmbeddingRepositoryProtocol
- `schemas.py` — Pydantic request/response schemas for search, stats
- `dependencies.py` — FastAPI dependency injection

**Setup (`setup/`):**
- `seed_templates.py` — Version-aware upsert: seeds new templates AND updates existing globals when bundled version is newer

**Database:**
- Alembic migration `0001_initial.py` — initial schema
- Alembic migration `0004_ai_settings.py` — `user_providers`, `user_ai_settings`, project AI override columns
- Alembic migration `0005_project_settings.py` — adds missing `token_limit_profile` column to `project_settings` (forgotten in 0004)
- Alembic migration `0006_feedback_events.py` — creates `feedback_events` table for memory layer
- `env.py` imports all model modules (auth, chapters, novels, settings, volumes, memory) — autogenerate works correctly
- Auto-migration on startup via `lifespan.py` — no manual `alembic upgrade head` needed

#### `packages/i18n/` — Translations (Source of Truth)

- Namespace-based file structure: `messages/{locale}/{namespace}.json` (7 namespaces × 3 locales)
- Locales: en (reference), de, fr
- Frontend loads via `next-intl` from `packages/web/lib/i18n/request.ts`
- `narrare_i18n/` stub: will become Python loader for CLI/MCP/A2A
- Validation: key completeness + placeholder consistency in pre-commit and CI

#### `packages/web/` — Next.js 16 Frontend (Phase 4)

**App Structure (App Router):**
- `app/(auth)/` — Login, Register pages with form validation (react-hook-form + zod)
- Login/Register redirect: `has_providers ? /dashboard : /wizard` (checks `user_providers` table)
- `auth/me` endpoint (in `router_me.py`) returns `has_providers: bool`
- `app/(app)/` — Authenticated pages with shared layout (auth shell + user info)
  - `dashboard/` — Novel list with create/navigate
  - `wizard/` — Setup wizard (5-step, inherits app layout with header/user info)
  - `novel/[id]/editor/` — Full TipTap v3 editor with autosave, chapter sidebar (DnD), context panel
- Route-level `loading.tsx` (skeleton boundaries) and `error.tsx` (error boundaries) at all levels
- `global-error.tsx` as last resort

**Components:**
- `components/editor/` — EditorLayout, EditorSurface (TipTap), EditorToolbar, ChapterSidebar (DnD Kit), ContextPanel, MetadataSidebar, CommandPalette (Cmd+K)
  - `MetadataSidebar.tsx` — Right sidebar with live statistics, session delta, chapter metadata, novel progress (replaces bottom status bar)
  - `extensions/` — 4 custom TipTap extensions: NarrareDocument, SceneBreak, DialogueMark, Autosave
  - `commands.ts` — Command registry for palette (format + editor actions, extensible for AI features)
- `components/editor/EditorLayout.tsx` — Focus mode: ESC handler + floating Minimize2 button (semi-transparent, focus-mode only)
- `components/dashboard/` — DashboardView with NovelCard grid + delete functionality (Trash2 icon, confirm dialog via `novelsApi.delete()`)
- `components/setup/` — 5-step Wizard (WizardShell + WizardStep1-5); steps 2↔3 swapped (starter selection first, then novel details); demo prefill from metadata.json
- `components/settings/` — AI provider management, model routing, token limit profiles, project AI settings
  - `PromptSettings.tsx` — AI Prompts tab with category grouping, source indicators, update badges
  - `PromptEditor.tsx` — Prompt editor with edit mode, variables sidebar
  - `PromptDiff.tsx` — Side-by-side diff comparison
- `components/generation/` — Generation features
  - `NameGenerator.tsx` — Name generator form (type, culture, count, gender selectors)
  - `NameResults.tsx` — Results display with pronunciation, meaning, duplicate badges
- `components/studio/editor/` — Writing generation UI
  - `GenerationPanel.tsx` — Generation trigger + streaming display
  - `GenerationConfig.tsx` — Mode selection + options (4 modes, tone variants)
  - `GenerationDraft.tsx` — Draft zone + controls (accept, reject, save)
  - `SessionPanel.tsx` — Interactive session chat UI
  - `ChatMessage.tsx` — Chat message bubble component
  - Generation commands registered in CommandPalette
- `components/studio/kb/` — Template-driven KB editor
  - `KBEntryDetail.tsx` — Main entry detail, loads template, renders accordion groups or flat fallback
  - `KBEntryHeader.tsx` — Name, type, tags header
  - `KBFieldGroup.tsx` — Accordion group component
  - `KBFlatEditor.tsx` — Fallback flat editor for entries without templates
  - `KBTypeField.tsx` — Renders correct input per field_type (str, int, bool, list, select); uses `kb.fieldDesc.*` i18n keys for placeholder text
  - `KBTagInput.tsx` — Tag/chip input for list fields
  - `KBSectionEditor.tsx` — Guided body section textarea with @mention autocomplete
  - `KBMentionRenderer.tsx` — Renders @mentions as clickable badges
  - `KBCreateForm.tsx` — Entry creation with entity type pre-selection from active category tab
  - `groupMaps.ts` — Icons/colors for 25 field groups and 8 sections across all entity types
  - `kbBodyUtils.ts` — Body ↔ section parsing/assembly
  - `constants.ts` — 8 entity types, TYPE_ICONS, TYPE_LABEL_KEYS
- `components/studio/settings/` — Template management in Settings
  - `KBTemplatesTab.tsx` — Template list with type filter, override/update status
  - `KBTemplateEditor.tsx` — Raw YAML editor with save/reset mutations
- `components/studio/WorldBuilding.tsx` — 3-column worldbuilding browser (CategorySidebar, EntryList, DetailPanel). Routes entity type selection to KB panels. KB-006a entry point.
- `components/studio/kb/KBCategorySidebar.tsx` — Entity type tabs with live counts (8 types)
- `components/studio/kb/KBEntryList.tsx` — Searchable, filterable entry list with debounced query
- `components/studio/kb/KBDetailPanel.tsx` — Detail/edit/create routing and display in Column 3
- `components/studio/writing/` — Writing pipeline UI
  - `WritingGraphStatus.tsx` — Compact status panel showing current WritingGraph step (highlighted), completed steps (checkmark), and step labels; integrated in EditorView
- `components/studio/planning/` — Storyboard UI
  - `StoryboardPanel.tsx` — Full-width collapsible container above toolbar, DndContext, stage layout
  - `StoryboardCard.tsx` — Draggable chapter card (title, status badge, word count, click-to-navigate)
  - `StoryboardStageColumn.tsx` — Droppable stage column with header
  - `SyncStatusBadge.tsx` — Color-coded status indicator (5 states)
  - `StoryboardScrollArrows.tsx` — Horizontal scroll controls
  - `OutlineEditor.tsx` — Inline beat checklist + notes editor with auto-save
  - `StructureChangeDialog.tsx` — Remap preview modal (before/after table, confirm/cancel)
- `lib/api/planning.ts` — Planning API client (6 methods: getStoryboard, getSyncStatus, getOutline, updateOutline, previewRemap, confirmRemap)
- `lib/hooks/usePlanning.ts` — TanStack Query hooks (useStoryboard, useChapterOutline, useRemap)
- `lib/api/kb.ts` — KBTemplate types + API client (getTemplate, listTemplates, resolveReferences, autocompleteEntries)
- `lib/hooks/useKB.ts` — useKBTemplate, useKBTemplates, useKBResolveReferences, useKBAutocomplete hooks
- `components/ui/` — Button (shadcn/cva-based), Input, Select
- `components/shadcn/` — shadcn/ui generated primitives (future component source)
- `components/shared/` — QueryProvider, ErrorBoundary

**State Management (three-layer):**
- **Server state:** TanStack Query v5 — all API data (novels, chapters, user, settings)
- **UI state:** Zustand — sidebar toggles, focus mode, save status, active chapter ID, editor ref (set by EditorSurface, read by CommandPalette)
- **Local state:** useState for component-ephemeral state

**API Client:**
- `lib/api/client.ts` — Native fetch with token refresh, no axios; `setAccessToken`/`clearAccessToken` sync `narrare_auth` cookie for proxy
- `lib/api/streaming.ts` — SSE streaming client for AI responses (fetch + ReadableStream)
- API clients: `promptsApi` (7 methods for prompt CRUD) + `generationApi` (1 method for name generation)
- `lib/api/generation.ts` — API client for writing generation (SSE streaming + WebSocket client for sessions)

**Styling:**
- Tailwind CSS v4 as sole styling system (styled-jsx removed)
- CSS variables in `globals.css` for all design tokens (light + dark mode)
- shadcn/ui for component primitives (Radix-based, not a runtime dep)

**i18n:**
- next-intl with 3 languages (en, de, fr)
- Translations at `packages/i18n/messages/` (namespace-based structure)
- `validate-i18n.ts`: hardcoded string detection + key completeness + placeholder consistency

**Auth & Security:**
- In-memory access token (not localStorage)
- httpOnly refresh token cookie (`narrare_refresh`) — backend sets on login/register, refresh endpoint reads from cookie; cleared by `POST /api/v1/auth/logout`
- `cookie_helpers.py` — backend helper for setting/clearing refresh cookies (httpOnly, SameSite=Lax)
- `POST /api/v1/auth/logout` — clears `narrare_refresh` cookie; no server-side token invalidation needed (cookie is the sole revocation mechanism)
- `restoreSession()` — frontend function to restore session from httpOnly cookie via silent refresh
- `proxy.ts` — Next.js route-level proxy verifying JWT cookie (`narrare_auth`) via jose for server-side auth protection on `/dashboard`, `/wizard`, `/novel/*`; redirects to `/login` if invalid
- Client syncs `narrare_auth` cookie alongside in-memory token (for proxy consumption)
- `_sessionChecked` guard in authStore — prevents infinite 401 refresh loops by tracking `loadUser()` terminal state; breaks retry cycle after first failed session check
- Auto-redirect to /login on 401

**Testing:**
- Vitest 3.x + Testing Library + MSW
- ~1,200+ tests across 140+ test files: proxy, utils, stores, API client, UI components, wizard steps, generation panel, session panel, KB components
- `npm run test` / `vitest run`

#### `tests/` — Test Suite

**Unit tests (31 files):**
- ~2,850+ tests total (backend), 23 new (WRITE-003 validation + streaming), 7 new (WRITE-004 integration)
- `core/llm/` — gateway, intents, retry, providers_registry, embeddings (5 files)
- `core/prompts/` — registry, composer, variable_engine, meta, variable_engine_hypothesis (5 files)
- `core/shared/` — frontmatter, result, errors, file_utils, result_hypothesis, frontmatter_hypothesis (6 files)
- `core/planning/` — adapters (all 5 types + registry), sync checker, models (117 tests)
- `core/writing/` — budget (incl. cap_to_budget), context_assembler (incl. entity_connections), pipeline, models (6+ files)
- `core/agents/` — review_agent (incl. writing_context), writing_graph (incl. review context enrichment), summary_agent (3+ files)
- `api/setup/` — setup_service, setup_schemas, demo_loader, provider_service, _complete_helpers, test_setup_complete_providers (6 files)
- `api/auth/` — auth_service, security (2 files)
- `api/chapters/` — chapter_service (1 file)
- `api/novels/` — novel_service (1 file)
- `api/volumes/` — volume_service (1 file)
- `api/metrics/` — metrics_router (1 file)
- `api/planning/` — service unit tests, integration tests for 5 endpoints (22 tests)
  - `api/` — test_contracts.py, test_fake_conformance.py (2 files)
  - **LLM testing infrastructure**: `ALLOW_MODEL_REQUESTS=False` global guard, `TestModel`/`FunctionModel` fixtures, `capture_run_messages` fixture for tool call assertions
  - Plus 3 hypothesis property-based tests (in core/shared and core/prompts)

**Integration tests (31 files, 340+ tests):**
- `setup/test_setup_api.py`, `novels/test_novels_api.py`
- `chapters/test_chapters_api.py`, `auth/test_auth_api.py` (24 tests)
- `settings/` — test_settings_api.py, test_ai_providers_api.py, test_ai_settings_api.py, test_project_ai_settings_api.py, test_gateway_integration.py, test_migration.py, test_project_settings_schema.py (50 tests)
- `memory/` — test_memory_api.py, test_memory_analyze_api.py (20 tests)
- `generation/` — test_generation_api.py, test_name_service_budget.py (6+ tests)
- `kb/` — test_kb_api.py, test_kb_schema.py, test_demo_kb_content.py, test_demo_kb_fields.py, test_relationship_repository.py (30+ tests)
- `volumes/test_volumes_api.py`, `health/test_health.py`
- `planning/test_planning_api.py`
- `writing/` — test_writing_api.py, test_full_lifecycle.py, test_scene_lifecycle.py, test_session_lifecycle.py, test_error_scenarios.py, test_generation_schema.py
- `test_seed_dev_user.py` (4 tests)
- `conftest.py` with shared fixtures (registered_user, novel_id, auth helpers, KB dependency override)
- `conftest.py` runs `alembic upgrade head` (not `Base.metadata.create_all()`) to validate migrations
- `conftest.py` provides `NARRARE_ENCRYPTION_KEY` via autouse fixture

**E2E:** Directory exists, no tests yet.

#### Frontend Tests (packages/web/)

**469 tests across:** (base suite + coverage uplift)
- `proxy.test.ts` — 10 tests (JWT verification, route protection, redirects)
- `lib/utils.test.ts` — 32 tests (cn, debounce, formatWordCount, etc.)
- `lib/stores/editorStore.test.ts` — 21 tests
- `lib/api/client.test.ts` — 17 tests (token management + cookie sync)
- `lib/stores/authStore.test.ts` — 15 tests
- `components/ui/` — 19 tests (Button, Input)
- `components/setup/` — WizardStep1-5 + WizardShell tests

#### Infrastructure

- `scripts/` — `check_architecture.py`, `seed_dev_user.py`, `check_commit_message.py`, `local/`
- `.devcontainer/` — full dev container setup
- `.github/workflows/` — CI (`ci.yml`), architecture check (`architecture.yml`), release (`release-please.yml`)
- Docker Compose (`docker-compose.dev.yml`) for PostgreSQL (pgvector) + Redis
- `justfile`, `pyproject.toml`, `uv.lock`

### AI Tooling (opencode + OAC)

- opencode CLI installed in dev container
- OpenAgentsControl (OAC) installed with full profile
- Custom Narrare Orchestrator agent (`.opencode/agent/narrare-orchestrator.md`)
- Narrare behavioral rules (`.opencode/context/narrare/` — 5 files: architecture, documentation, implementation, navigation, orchestration)
- Narrare navigation pointing to `docs/` as single source of truth

---

## What Is In Progress

Phase 5 (current):
1. ✅ Writing generation pipeline (WRITE-002) — fully implemented
2. ✅ KB v2 — template-driven structured metadata, cross-references, 8 entity types, template management
3. ✅ Storyboard feature (PLAN-003/005 merged implementation) — core adapters, backend service, frontend UI, i18n
4. ✅ Chapter Summary (WRITE-012) — ChapterSummaryAgent, SummaryService + REST endpoint, WritingGraph summary step, prompt in analysis/en/summarize/
5. ✅ AI-powered storyboard remap — AIRemapService with summary analysis, enhanced sync COMPLETED detection, WritingGraphStatus UI
6. ✅ Feedback & Learning Loop (LEARN-001) — mem0 AsyncMemory wiring, 4-tier embedding cascade, PreferenceAnalysisAgent, modify-tracking, rating UI, preference profile page
7. ✅ KB dedup for name generator — flag existing names, prompt-level dedup
8. ✅ Test coverage uplift — 109 new tests (62 backend + 47 frontend)
9. ✅ Integration test reactivation — 121 previously-skipped tests reactivated across 14 files (auth, settings, memory, generation, KB, seed, gateway). All green.

10. ✅ CR-08 Hardcoded Values — FIND-006/009/010/011 implemented.
        Output-Limits via Token-Profile, Budget-Tier-Override, WS-Timeout in Config,
        mem0 Embedding-Modell via Settings. SET-005 feature doc created.

11. ✅ WRITE-003: Extend Chapter — Complete. Core pipeline + prompts (en/de/fr), Backend API (ExtendService, SSE-direct), Frontend AIAnnotation infrastructure. 23 unit tests (12 validation + 11 streaming). Promptfoo eval baseline (`evals/extend-chapter.yaml`, 356 lines, 9 test cases). Architecture validation clean.

12. ✅ INFRA-004: Embedding Store — Complete. 47 files, 5763 insertions. EmbeddingStoreProtocol, SearchResult, EmbeddingStats in core/. API models/repo/service/router/tasks. KB hooks + usage tracking. RULE-04 test splits applied. Architecture check clean.

13. ✅ KB-005: Proactive Context — `ProactiveContextService` (core) 3-stage pipeline: name matching → embedding search → hybrid scoring. `KBSuggestService` (api) thin wrapper with chapter/entity resolution. `GET /novels/{novel_id}/kb/suggestions/{chapter_id}` endpoint. `match_entity_names()` regex extraction utility. `compute_hybrid_score()` extracted from `rank_candidates()`. 54 new tests (48 core + 6 API). INFRA-009 merged into KB-005.

14. ✅ KB-002: Assisted KB Creation — Complete. Frontend wiring verified (WorldBuilding → KBEntryList → KBAssistedCreationPanel → all sub-views). 3 minor non-blocking gaps noted (2 dead code components, 1 missing i18n key). Backend + Frontend fully operational.

15. ✅ KB-003: AI Improve KB Entry — Complete. `KBImproveService` (analyze + apply) in `kb/improve_service.py`, `KBImproveProtocol` in `kb/improve_contracts.py`, `router_improve.py` with POST /improve + /improve/apply endpoints. `KBImproveAgent` in `core/agents/kb_improve_agent.py`. Frontend: `KBImprovePanel` + "Improve with AI" button in `KBEntryDetail`.

16. ✅ kb-agents-and-prompts — Committed (481e370). KBAssistAgent (4-mode), ExtractionAgent, 4 English prompts, 78 tests.

 17. ✅ WRITE-004: Rewrite Selection — Complete. `RewriteService` in `writing/rewrite_service.py`, SSE-direct endpoint, `AlternativeParser`, `RewriteModeSelector`, `InlineDiff`, `replaceSelectionWithAIContent()`. 7 integration tests (SSE protocol, mode variations, stream errors). Promptfoo eval baseline (`evals/rewrite-selection.yaml`, 279 lines, 7 test cases). Spec frontmatter corrected.

18. ✅ Knowledge Graph Test Gaps — 239 new tests. Core (100), Backend (13 + FakeEmbeddingRepository + 25 Config), Frontend (91). All 15 untested hotspots covered. 4 config properties tested (safety-critical DB routing). Commits: ed21254, b5767e3.

 19. ✅ KB-006a: Worldbuilding View & Navigation — 3-column KB browser implemented. Category sidebar with entity type tabs + live counts, searchable entry list (debounced), detail/edit/create panel in Column 3, assisted creation panel (KB-002 reuse), sidebar navigation. KB-006b (AI gap detection, connection suggestions) remains planned.

 20. ✅ ANAL-001: Beta Reader Simulation — Complete. Two-phase AI chapter analysis (Phase 1: full feedback, Phase 2: deep-dive). BetaReaderAgent in core with 2 prompts. New analysis/ API module (contracts, schemas, errors, service, cache, context assembler, mapper, validation, DI, router). BetaReaderPanel with ScoreRadar (Recharts), FeedbackCard, 4 tabs, editor integration. i18n 3 locales. 57 tests. Recharts v3.8.1 installed for analysis visualization suite.

 21. ✅ Coverage Uplift 2026-05-27 — 1,045+ new tests across 6 waves. All layers now comprehensively tested. Focus areas: backend API services (210 unit tests), frontend components (281 tests), frontend lib/hooks (141 tests), core layer (234 tests), backend integration (85 tests), cross-layer contracts + E2E (~94 tests).

 22. ✅ ANAL-002: Sentiment Analysis — Spec-complete. All backlog items implemented: cross-chapter arc trajectory line graph, word count + arc minimum warnings, chart export (PNG via html-to-image), hover tooltips on emotion chart + arc graph. LLMIntent.SENTIMENT confirmed. 8 warning tests + 30 rule tests. Core NLP module (`core/nlp/`) + analysis module (`core/analysis/`) with LexiconSentimentAnalyzer (deterministic VAD + emotion scoring + arc detection). ADR-021.

 23. ✅ CONS-001: Consistency Checker — Spec-complete. All backlog items implemented: issue actions (dismiss/mark intentional/copy), loading progress with elapsed timer, rule-based KB pre-check (deterministic, confidence=1.0), scope selector (current/selected/all), fact deduplication. LLMIntent.CONSISTENCY confirmed. 22 rule helper tests + 6 service tests. ConsistencyAgent (pydantic-ai) + API endpoints + ConsistencyPanel.

Next focus: Post-MVP features (E2E test patterns, AI-assisted enrichment, analysis panels).

---

## Design Decisions (2026-05-24)

| Decision | Details |
|----------|---------|
| KB-005 ProactiveContextService design | 3-stage pipeline in core (name matching + embedding search + hybrid scoring). EntityMetadata passed from API layer. Name-match boost (+0.2 to similarity). compute_hybrid_score() extracted from rank_candidates() for Suggestion.relevance_score. |
| KB-005 + INFRA-009 merged | Identical 3-stage pipeline and scoring formula. Core: `ProactiveContextService`, API: `KBSuggestService` thin wrapper. |
| INFRA-004: Generic embeddings table | Not KB-only. `embeddings` table with `source_type` (kb_entry, chapter, chapter_summary, note) + `source_id`. HNSW index. Background generation via TaskIQ. Hybrid search (0.5 similarity + 0.3 usage + 0.2 recency). Two-phase model migration. |
| KB-002: Assisted Creation (not chat) | Template-guided creation flow. Spectrum: manual → AI-suggest → interview → auto-generate. Single KBAgent with Union output. REST + SSE. ProactiveContextService for world context. Redis session with 30min TTL. |
| KB-007: Simple review panel | ExtractionAgent (separate from KBAgent). Simple endorse/reject panel. REST endpoint, no SSE needed. Two-stage extraction (rule-based + AI). |
| RULE-20: No half-implementations | Added to CONSTRAINTS.md. Every feature must be complete and correct. No "Phase 1 only" without full infrastructure. |
| Embedding Store: full implementation required | No keyword-search fallback. Build pgvector store from the start. |

---

## What Is Blocked

Nothing blocking Phase 5.

All demo content is complete — sufficient for testing through Phase 5.

---

## Resolved Since Last Update

| Item | Resolution |
|------|-----------|
| Q-004 Celery vs arq | → TaskIQ. ADR-007 created. arq in maintenance-only mode. |
| Q-005 GLM/Z.AI/pydantic-ai | → OpenAI-compatible endpoints. Factory function in `core/llm/_providers/zai.py`. |
| Dead links in docs/ | Fixed: CURRENT_STATE.md created, PROJECT_VISION path corrected, Q-005 reference fixed |
| Deployment guide gaps | CI pipeline specs, pre-commit config, justfile catalog, env vars added |
| Coding standards gaps | Result type pattern, service DI pattern added |
| CURRENT_STATE.md drift | Audited and corrected — Phases 1–3 were implemented but not reflected |
| Frontend stack optimized | axios→fetch, styled-jsx→Tailwind v4, shadcn/ui, motion, jose middleware, i18n lint |
| editorStore duplication removed | Server state now exclusively in TanStack Query, Zustand for UI state only |
| Error handling added | Route-level error.tsx + global-error.tsx + ErrorBoundary component |
| Loading states added | Skeleton loading.tsx at all route levels |
| debounce autosave bug fixed | useRef-based debounce pattern replaces broken useCallback |
| Tech Stack Audit | Complete — 16 changes across Core, Backend, Platform, Docs |
| bcrypt → argon2 | ADR-009, security.py rewritten |
| slowapi → fastapi-limiter | ADR-009, async-native Redis rate limiting |
| OpenTelemetry | ADR-010, replaces prometheus-client |
| Langfuse LLM Observability | ADR-010, integrated in gateway via observability.py |
| Content Versioning | ADR-011, chapter_versions table + API endpoints |
| Event-Driven Architecture | ADR-012, core/events + Redis Pub/Sub + TaskIQ |
| infer_provider heuristics | Fixed: explicit model registration + declarative prefix mapping |
| Error Classification | Fixed: layered exceptions (pydantic-ai typed → stdlib → string fallback) |
| Correlation IDs | Enhanced: full UUID + OTel trace context + response headers |
| pgBouncer | Added to Docker Compose (production profile) |
| pydantic-ai v1.93 migration | OpenAIProvider wrapper + output_type rename for API compat |
| Z.AI endpoint selector | Wizard offers General vs Coding API for Z.AI users |
| Provider error pass-through | Real provider errors surfaced to users, not generic messages |
| TYPE_CHECKING ForwardRef fix | All schemas + routers: moved runtime types out of TYPE_CHECKING |
| Dashboard New Novel → Wizard | "New Novel" now launches setup wizard instead of direct creation |
| Q-006 Configurable Model Routing | → Runtime cascade with multi-provider, encrypted API keys, 7 intent categories |
| Setup wizard DB gap | Fixed: `complete()` now writes to `user_providers` + `user_ai_settings` — AI Settings pages work immediately after setup |
| Auto-migration on startup | `lifespan.py` runs `alembic upgrade head` before serving — no manual migration step needed |
| Post-login redirect | `/auth/me` returns `has_providers` flag; login/register redirects to `/wizard` if no providers |
| Alembic env.py | All 5 model modules imported — `alembic revision --autogenerate` detects all schema changes |
| Integration test migrations | Tests use real Alembic migrations (not `create_all()`) — catches migration bugs in CI |
| Setup RULE-04 split | `_validation.py` extracted from `service.py` (325→190 lines) |
| Frontend toggle switches | Fixed dimensions: `w-11 h-6` track, `w-5 h-5` knob in CategoryOverrides + IntentOverrides |
| AI Providers migration warning | Changed to subtle hint, hidden for Ollama, i18n key `migrationWarning` → `addKeyHint` |
| Migration 0004 schema gap | Fixed: migration 0005 adds `token_limit_profile` to `project_settings` — was only added to `user_ai_settings` |
| RULE-14 Migration Discipline | New rule: every model column needs a migration, cross-table check required, regression test mandatory |
| Issue 4: Auth session | httpOnly refresh token cookie (`narrare_refresh`) set on login/register; refresh endpoint reads from cookie; frontend `restoreSession()` via silent refresh |
| Issue 1: Focus mode exit | ESC handler + floating Minimize2 button (semi-transparent, focus-mode only) in EditorLayout |
| Issue 2: Dashboard delete | Trash2 icon on NovelCards (hover-revealed, confirm dialog); `novelsApi.delete()` mutation |
| Issue 3: Wizard flow | Steps 2↔3 swapped (starter selection → novel details); demo metadata.json with author/logline/pov/tags; WizardStep3 prefills store |
| Issue 5: Editor extensions | NarrareDocument, DialogueMark, Autosave extensions + CommandPalette (Cmd+K) + commands.ts registry; EditorSurface refactored for Autosave; editorStore holds editor ref |
| Memory layer implementation | Core memory module: mem0 AsyncMemory with pgvector, FeedbackService, PreferenceService, NullMemoryClient, dual storage architecture, RULE-01 exception |
| Prompt management implementation | PromptManagementService with 7 API endpoints for CRUD, update detection, diff comparison; variable metadata registry; frontend PromptSettings/PromptEditor/PromptDiff |
| Culture injection | {{culture_guidelines}} placeholder, resolve_culture() with EN fallback, 9 culture definitions (fantasy/modern/scifi × en/de/fr) |
| Generation intents | GENERATE, NAME_GENERATE, TITLE_GENERATE in IntentCategory.GENERATION |
| Name generator implementation | API endpoint POST /generation/names, frontend NameGenerator + NameResults components, i18n for 3 locales |
| Migration 0006 | feedback_events table for memory layer dual storage |
| mem0 integration | mem0ai>=1.0 added to core dependencies, psycopg[binary]>=3.0 for pgvector |
| Metadata sidebar (replaces status bar) | EditorView: bottom status bar replaced by collapsible right MetadataSidebar with live stats, session tracking, chapter metadata, and novel progress |
| Volume Management | WRITE-011 fully implemented — backend enrichment, stats, reorder, frontend UI with volume selector and management page |
| Pydantic AI testing tools | `TestModel`/`FunctionModel`/`capture_run_messages` fixtures, `ALLOW_MODEL_REQUESTS=False` guard, FakeLLMGateway in integration tests |
| KB v2: Core schemas | 8 entity schemas with nested metadata groups (CharacterMetadata.appearance, etc.) |
| KB v2: Core templates | 24 bundled templates (8 types × 3 langs) in v2 format with field_groups + sections |
| KB v2: Backend CRUD | kb/ module + templates/ module — full CRUD, cascade resolution, seed version-aware upsert |
| KB v2: Cross-references | @Name pattern with MENTION_RE regex, resolve_references + autocomplete endpoints |
| KB v2: New entity types | concept (ConceptMetadata) + setting (SettingMetadata) — migration 0011 |
| KB v2: Frontend editor | Template-driven accordion editor (8 sub-components, all <200 lines), flat fallback |
| KB v2: Template management | KBTemplatesTab + KBTemplateEditor in Settings, raw YAML with save/reset |
| KB v2: groupMaps | 25 field group icons + 8 section icons across all entity types |
| KB v2: i18n | Group labels, hints, field labels for all types (en/de/fr) |
| FR character YAML fix | Quoted (ex: ...) descriptions to prevent YAML mapping key parsing error |
| Seed version-aware upsert | seed_templates.py now updates existing global entries when bundled version is newer |
| KB template i18n consolidation | 24 language-specific templates → 8 language-neutral. TemplateMeta drops template_language. Field descriptions moved to kb.fieldDesc i18n namespace. Migration 0012. 78 files changed. |
| Storyboard: Core planning adapters | 5 structure adapters (three_act, five_act, heros_journey, save_the_cat, seven_point) + StructureAdapterRegistry in `core/planning/adapters/`. StructuralSyncChecker with 5 status levels in `core/planning/sync.py`. |
| Storyboard: Backend service | StoryboardService (6 methods), OutlineRepository, ChapterOutline model, 5 REST endpoints under `/api/v1/planning/`, migration 0013. 139 backend tests. |
| Storyboard: Frontend UI | 7 components (StoryboardPanel, StoryboardCard, StoryboardStageColumn, SyncStatusBadge, StoryboardScrollArrows, OutlineEditor, StructureChangeDialog), API client, TanStack Query hooks, editor integration, structure change flow, i18n for 3 locales. |
| Storyboard: Feature docs | PLAN-003/004/005 feature files updated to reflect implementation. INDEX.md status updated. |
| Chapter Summary implementation | ChapterSummaryAgent (NarrareAgent subclass), SummaryService + REST endpoint POST /api/v1/planning/summary/chapters/{chapter_id}, WritingGraph generate_summary step (after finalize), prompt analysis/en/summarize/system.md |
| AI-powered storyboard sync | StructuralSyncChecker rule 3b: summary + content → COMPLETED (stronger than word count alone) |
| AI-powered structure remap | AIRemapService: analyze_chapter_role(), meets_coverage_threshold(50%), calculate_confidence(); hybrid approach with position-ratio fallback |
| WritingGraphStatus UI | Compact collapsible panel in EditorView showing pipeline step status (highlighted current, completed checkmarks) |
| LEARN-001 Feedback Loop | Full feedback loop closed. 55 tasks: Embedding cascade (ADR-017, 4-tier fallback for all providers), FeedbackEvent extended with rating + enriched context, mem0 AsyncMemory via MemoryClientCache, PreferenceAnalysisAgent for deep pattern analysis, event-driven processing (FeedbackRecorded/PreferenceAnalysisTriggered → TaskIQ), POST /memory/analyze endpoint, frontend modify-tracking + RatingPrompt + LearningTab preference profile + LearningStatus indicator, 3 migrations |
| CI proxy JWT secret fallback | Proxy.ts now checks `SECRET_KEY` as fallback when `AUTH_JWT_SECRET` is unset — resolves 16 e2e wizard test failures on CI |
| CI tone test fix | `_TONE_IDS` updated from 4→9 tones, count assertion fixed — resolves `test_total_tone_file_count` CI failure |
| Writing conftest extraction | Shared fixtures moved from `test_writing_service.py` to `tests/unit/api/writing/conftest.py` — resolves 3 ERRORs in `test_writing_service_validation.py` |
| Tone count dynamization | `_TONE_IDS` now derived from filesystem glob instead of hardcoded list — future tone additions auto-discovered |
| i18n dead code cleanup | Removed unused `wizard.tone` individual tone-name keys from `studio.json` and `wizard.json` (3 languages × 7 keys = 42 dead keys removed) |
| INFRA-005 Memory Layer | Completed: embedding cascade + PreferenceAnalysisAgent extend the core memory module. Feature spec updated to implemented |
| KB dedup for name generator | _check_duplicates() now queries KB entities, flags duplicates, pre-fills existing_names in prompt context |
| Backend test coverage uplift | 62 new tests: prompts (15), memory (15), settings (20), kb relationships (12) |
| Frontend test coverage uplift | 47 new tests: GenerationPanel (8), SessionPanel (8), KBEntryDetail (7), KBCreateForm (10), OutlineEditor (7), NameGeneratorModal (7) |
| Skipped integration tests | 121 tests reactivated: FK helpers, httpx cookie fix, schema drift fixes, LLM mocking, KB DI workaround, 3 gateway stubs implemented. Latent bug found: kb/dependencies.py missing Depends() |
| Pytest auto-tagging | `pytest_collection_modifyitems` hook in tests/conftest.py auto-assigns unit/integration/e2e markers based on directory path. 21 manual markers removed. `norecursedirs` explicit in pyproject.toml. |
| promptfoo eval framework | ADR-018. evals/ directory with 3 baseline test case sets (writing-generation, name-generation, summarization). CI workflow (nightly + workflow_dispatch). Orthogonal to pytest — evaluates prompt quality, not code. |
| testing-standards.md updated | 3 new sections: Auto-Tagging (RULE-TEST-03), Snapshot Testing Rules (RULE-TEST-04), LLM Prompt Evaluation (ADR-018 reference) |
| Voice Drift Prompt-Ebene (review-03 Quick-Win) | KBEntity.metadata field + character_voice_profiles in WritingContext/PromptContext + 12 prompts updated with voice consistency section. Commit 42241d0. Foundation for ANAL-008, ANAL-009, WRITE-010. |
| Ghost-Text TipTap Assessment (AUFG-03-01) | ProseMirror Decorations API evaluation completed. 4-phase roadmap. Assessment at docs/architecture/assessments/ghost-text-tiptap-assessment.md |
| Feature Docs Voice Integration (Doc Gate) | ANAL-008, ANAL-009, WRITE-010 updated with integration notes for {{character_voice_profiles}} infrastructure |
| CR-01 Prompt Quality Audit | RULE-02 compliance: 5 agents wired to PromptComposer, hardcoded system_prompt strings removed. XML encapsulation for prompt injection defense. Interview + interactive_session prompts enhanced with CoT, negative examples, output format. New bundled prompts: review, preferences, outline, rewrite_selection, story_suggest. User preferences added to generation/name prompts. 10 new de/fr translations. |
| CR-02 System-Prompt Audit | Meta-prompt guardrails added (fiction content, conversation guardrails, avoidance_patterns) to all 4 variants. NarrareAgent.with_meta() factory for meta-prompt loading. ADR-019. 14 new guardrail tests. |
| CR-03 Feature-Adoption Audit | `cap_to_budget()` token utility + token enforcement on name service (500) and interview draft (4000). ReviewDeps extended with `writing_context` for enriched review with KB data. Entity connection promotion in context assembly via `entity_connections` + `get_adjacency_map()`. 5 new test files. |
| CR-04 Preference Wiring | WritingDeps.user_id + _base_context() user_id/project_id in extra + PromptComposer preference_service in dependencies.py. Review prompts (en/de/fr) have "respect preferences" directive. |
| CR-04 Conflict Resolution | Meta-prompt (en/de/fr) has "outline wins over KB state" conflict resolution rule. Commit d1c0d8a. |
| FIND-006 Output-Limits | Router/Deps nutzen resolve_output_limit() statt hardcoded 4000/1000/2000 |
| FIND-009 Budget-Tier-Override | TokenBudgetManager akzeptiert tier_overrides per Constructor |
| FIND-010 WS-Timeout | ws_handler liest settings.ws_idle_timeout_seconds |
| FIND-011 mem0 Config | create_memory_client() mit memory_llm_model / memory_embedding_model aus Settings |
| FIND-005 KB Suggest | Bereits gelöst — kein hardcoded max_entries mehr im KB-Modul |
| CR-08 Config-Expansion | 6 neue Env-Vars: NARRARE_DEFAULT_MAX_TOKENS, WS_IDLE_TIMEOUT, RETRY_*, COST_RATES_JSON |
| CR-08 Feature Doc | SET-005 — Configurable Token Limits erstellt |
| CR-08 Nice-to-have Spec | CR-08-NTH — Cost Estimation, Retry Config, Model Registry |
| KB dependencies bug | Bereits behoben — alle dependencies.py nutzen SessionDep |
| WRITE-003: Core pipeline | GenerationMode.EXTEND, WritingPipeline._extend() (direct LLM call, no WritingGraph), extend-specific context budget (50/15/20/10/5), extend prompts (en/de/fr) |
| WRITE-003: Backend API | ExtendService (separate from DraftService per RULE-04), ExtendRequest schema (text_before, text_after, length, tone, language), POST /extend SSE-direct endpoint, ExtendServiceProtocol contract, integration tests |
| WRITE-003: Frontend AIAnnotation | AIAnnotation Mark (ai-generated) + AIAnnotationTracker Plugin (modify detection, single-pending constraint), AIAnnotationActions floating UI, ContinueButton with length selector, extend command in CommandPalette, AIAnnotationApi standalone functions (insert/append/finalize/accept/reject), Clean Save integration (Autosave removes pending marks) |
| INFRA-004: Core embeddings module | `packages/core/narrare_core/embeddings/` — store.py (EmbeddingStoreProtocol, SearchResult, EmbeddingStats), hash.py (compute_content_hash SHA-256), scoring.py (hybrid search scoring 0.5/0.3/0.2) |
| INFRA-004: API embeddings module | `apps/api/narrare/embeddings/` — models, repository, service, router, dependencies, tasks, contracts, schemas. Full embedding CRUD + search + TaskIQ background generation |
| INFRA-004: KB embedding hooks | `kb/embedding_hooks.py` — EmbeddingHookManager for content hash + task dispatch on KB changes; `kb/usage_service.py` — ContextUsageService for accept/dismiss tracking; `kb/models.py` — added last_referenced_at, usage_count columns |
| KB-002 backend | KBAssistService + KBSessionService + Redis session store + 8 REST endpoints + SSE + template field extraction. 99 tests. Commit 281df89. |
| KB-002 architecturesplits | schemas.py split (session_schemas.py, assist_contracts.py), test split (test_session_service.py, test_session_assist.py), contracts extraction (suggest_contracts.py, usage_contracts.py). RULE-04 compliance. |
| KB-002 type fixes | model_copy() for kwargs, UUID type params in test fakes, PromptComposer for KBAssistService, allow-direct-llm + allow-agent markers. |
| KB-007 Extraction Frontend | ExtractionPanel review UI + ExtractionApplyService (backend apply endpoint) + editor toolbar button + 31 i18n keys + 14 backend tests + frontend component tests |
| KB-002 Spec Update | Feature spec status updated from designed → implemented. Backend + Frontend were already complete. |
| WRITE-003: Extend Chapter — Complete | 23 unit tests (12 validation + 11 streaming). Promptfoo eval baseline `evals/extend-chapter.yaml` (356 lines, 9 test cases). Architecture validation clean. Feature spec → stable. |
| WRITE-004: Rewrite Selection — Complete | 7 integration tests (SSE protocol, mode variations, stream errors). Promptfoo eval baseline `evals/rewrite-selection.yaml` (279 lines, 7 test cases). Spec frontmatter corrected (service → rewrite_service.py, contract → contracts_rewrite.py, router → router_rewrite.py). Feature spec → stable. |
| INFRA-004: Embedding Store — RULE-04 test splits | `test_embedding_migration.py` (349→2 files: coexistence 180, reembed 222). Feature spec → stable. |
| KB-002: Assisted Creation — Verified | Frontend wiring verified: WorldBuilding → KBEntryList → KBAssistedCreationPanel → all sub-views. 3 minor non-blocking gaps found (2 dead code components, 1 missing i18n key). Feature confirmed complete. |
| RULE-04 frontend test splits | `KBAssistedCreationPanel.test.tsx` (588→3: rendering 334, navigation 302, actions 359). `KBInterviewView.test.tsx` (492→2: rendering 270, interactions 286). `useKBSessions.test.tsx` (534→2: lifecycle 296, actions 332). |
| KG Test Gaps — Core | BeatDef (35 tests), classify_error (32 tests, companion file per RULE-04), VariableMeta (33 tests + registry completeness). Commit ed21254. |
| KG Test Gaps — Backend | ExtractionService error + edge case tests (9), FakeEmbeddingRepository + conformance tests (2). Embedding tests refactored to shared fake. Commit ed21254. |
| KG Test Gaps — Frontend | EditorView (13), TipTapEditor (9), KBSectionEditor (16), AiTab (7), VolumeManagement (7), NameGenerator (7), KBTemplateEditor (10), ContinueButton (12), AddRelationshipDialog (10). 91 new frontend tests total. Commit ed21254. |
| KG Test Gaps — Config | 25 tests for Settings.is_test/is_development/is_production/active_database_url. Verifies mode exclusivity and test-mode override safety. Commit ed21254. |
| Test Fixes | Pyright: Settings(**defaults) → model_validate(defaults) in test_config.py. i18n: hardcoded English → i18n keys in ExtractionReview.test.tsx. Commit b5767e3. |
| SET-005: Configurable Token Limits — Phase 1 | Full Phase 1 implementation: `token_limits/` module with contracts/models/schemas/repository/service/router, migration 0021 + 0023 (non-destructive data migration), three-layer resolution cascade (User → Project → Env → Code defaults), writing deps switched to `TokenLimitsService.get_resolved_limits()`, WS handler dynamic limits, dual-write to old columns (deprecated), profile name fix `"long"` → `"long_texts"`, `get_model_limits()` for model-aware limits, frontend profile read/write via `TokenLimitsApi`, i18n EN/DE/FR keys. |
| KB-006a: Worldbuilding View & Navigation | 3-column KB browser implemented (CategorySidebar, EntryList, DetailPanel). Entity type filtering with live counts, debounced search, detail/edit/create routing, assisted creation panel (KB-002 reuse). KB-006b (AI Assistant) remains planned. |
| INFRA-003 feature doc status | INFRA-003-context-assembly.md frontmatter corrected to `status: stable`. History entry added for 2026-05-26. |
| WRITE-011 feature doc status | Feature file frontmatter corrected from `in progress` to `stable`. Status & History entry added for 2026-05-26. Matches INDEX.md. |
| PLAN-003 feature doc status | Feature file frontmatter corrected from `in-progress` to `stable`. Status & History entry added for 2026-05-26. Matches INDEX.md. |
| PLAN-005 feature doc status | Feature file frontmatter corrected from `in-progress` to `stable`. Status & History entry added for 2026-05-26. Matches INDEX.md. |
| SET-005: Configurable Token Limits — Phase 2 cleanup | Removed deprecated `token_limit_profile` / `token_limit_overrides` from API schemas and services. Removed `CustomTokenLimits` component, `TokenLimitOverride` type, and old field references. 3,272 tests passing, architecture validation clean. |
| INFRA-010: Prompting Locally — Cascade Activation | Core cascade activated via workspace root DI wiring — PromptRegistry and MetaPromptLoader now receive project_root=BASE_DIR. ManagementService fallback path fixed (~/.narrare/ → user_config_dir/prompts/). All 5 cascade levels fully operational: DB template → project file → user-global → bundled → bundled EN fallback. Feature doc status: planned → stable. |
| Coverage Uplift 2026-05-27 | 6-wave plan komplett umgesetzt: Backend Unit (16 Dateien, 210 Tests), Backend Integration (7 Dateien, 85 Tests), Frontend Components (31 Dateien, 281 Tests), Frontend Lib/API (17 Dateien, 141 Tests), Core Unit (19 Dateien, 234 Tests), Cross-Layer Contracts (5 Dateien), Router Contracts (4 Dateien), Fake Conformance (1 Datei, 13 Tests), E2E (3 Dateien, 9 Tests). Alle 26 bisher ungetesteten Frontend-Komponenten abgedeckt. Alle 10 ungetesteten Backend-Services abgedeckt. Core Events, Agents, Embeddings vollständig getestet. Coverage weit über 80%. |

---

## Decisions Made (full log in ADR files)

| ADR | Decision | Status |
|-----|---------|--------|
| ADR-001 | Single LLM Gateway | ✅ Implemented in `core/llm/gateway.py` |
| ADR-002 | Unified Prompt System | ✅ Implemented in `core/prompts/` |
| ADR-003 | Protocol-First Development | ✅ Applied across all API modules |
| ADR-004 | Hard File Size Limits | ✅ Enforced via `check_architecture.py` |
| ADR-005 | Directory Structure & Module Ownership | ✅ Applied |
| ADR-006 | Technology Stack | ✅ Applied |
| ADR-007 | TaskIQ for Background Tasks | ✅ Decided, integration pending |
| ADR-009 | Security Stack Modernization (argon2 + fastapi-limiter) | ✅ Implemented |
| ADR-010 | Observability Strategy (OpenTelemetry + Langfuse) | ✅ Implemented |
| ADR-011 | Content Versioning for Chapters | ✅ Implemented |
| ADR-012 | Event-Driven Architecture (Redis Pub/Sub) | ✅ Implemented |
| ADR-013 | Internationalization Architecture | ✅ Implemented |
| ADR-014 | RULE-14: Model-Migration Consistency | ✅ Enforced |
| ADR-015 | Pydantic-AI Agents as First-Class Citizens | 🔄 Proposed |
| ADR-016 | Prompt Caching Strategy | 🔄 Proposed |
| ADR-017 | Embedding Cascade for mem0 | ✅ Implemented in `core/memory/embedding_cascade.py` |
| ADR-018 | Promptfoo Eval Framework for Prompt Quality | ✅ | evals/, CI |
| ADR-019 | System-Prompt Consistency for pydantic-ai Agents | ✅ Accepted | `core/agents/`, `core/prompts/`, RULE-02 |

---

## Open Questions (summary)

| ID | Question | Status | Blocks |
|----|---------|--------|--------|
| Q-001 | MCP auth strategy | 🟡 Open | apps/mcp/ (post-MVP) |
| Q-002 | A2A streaming requirement | 🟡 Open | apps/a2a/ (post-MVP) |
| Q-003 | Embedding provider abstraction | 🟡 Open | core/llm/embeddings.py (post-MVP) |
| Q-004 | Celery vs arq | ✅ Resolved → TaskIQ | — |
| Q-005 | GLM/Z.AI compatibility | ✅ Resolved → OpenAI-compatible | — |
| Q-006 | Configurable Model Routing | ✅ Resolved → Runtime cascade | — |

---

## Known Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Python 3.14 missing type stubs for some deps | Low | Low | Tried `reportMissingTypeStubs = true` — 261 false positives from inline-typed first-party code. Documented with TODO in pyproject.toml |
| TipTap v3 extension API changes | Low | Medium | Pin exact version in package.json |
| Feature spec files not yet individualized | Low | Low | INDEX.md has catalogue, can be expanded per-feature as needed |
| Frontend Button tests use semantic token assertions (not class names) — may break if shadcn tokens change | Low | Low | Update test assertions when tokens change |
| Editor uses h-full inside flex container — new pages must handle their own scroll | Low | Low | Follow DashboardView pattern: h-full overflow-y-auto wrapper |

---

## Next Session Should Start With

**Phase 5 (current):**
1. Post-MVP features development
2. KB-006b: AI gap detection & connection suggestions
3. Analysis panel integration in ContextPanel
4. Editor: Ghost-Text feature (TipTap Decoration API)
5. Embedding provider abstraction (Q-003)

**Post-MVP (future):**
1. Connect writing features to the editor (SSE streaming sessions)
2. AI-assisted KB entry enrichment (LLM fills template fields from body text)
3. Add analysis panels to the ContextPanel
4. Embedding provider abstraction (Q-003)

Infrastructure now includes: OpenTelemetry tracing, Langfuse LLM observability, event-driven
architecture (Redis Pub/Sub → TaskIQ), content versioning, argon2id auth, async rate limiting,
memory layer (mem0 + pgvector), prompt management (override CRUD + diff), culture-aware generation,
promptfoo eval framework (prompt quality regression testing), auto-tagged pytest infrastructure.

---

> Maintained by: Architecture Agent, updated by Orchestrator at session end
