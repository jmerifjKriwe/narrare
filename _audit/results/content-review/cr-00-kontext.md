# Content Review 00 – Projekt-Kontext (AI-Inhalt)

Audit date: 2026-06-11
Previous audit: 2026-06-02
Scope: prompt/content architecture for CR-01–CR-08 rerun; CR-07 implementation status included only as context.
Method: graph-first inventory (`PromptComposer`, `PromptRegistry`, `PromptContext`, `NarrareMeta`, `NarrareUniversalRules`, mem0/client, KB context, Prompt Management UI) followed by targeted reads for line-level evidence.

## Verbesserungen seit dem vorherigen CR-00

- ✅ **ADR-026 capability baseline is still in place:** every `NarrareAgent` injects `NarrareObservability`, `NarrareUniversalRules`, and `NarrareMeta` at construction (`packages/core/narrare_core/agents/base.py:67-109`).
- ✅ **Production fallback problem from earlier CRs is resolved:** old consistency/extraction fallback entries from the previous CR-00 are no longer present as production inline system prompts. Current graph/grep evidence shows no `You are ...` system-prompt bodies in `apps/api/narrare`; remaining inline fallback logic is scoped to `writing_graph_prompts.py` for `composer is None` bare-bones/test paths (`packages/core/narrare_core/agents/writing_graph_prompts.py:122-181`, `253-361`).
- ✅ **Route governance is explicit:** routeable intents are centralized in `route_table.py`; non-routeable/context-required intents now have rationale (`packages/core/narrare_core/prompts/route_table.py:72-165`).
- ✅ **mem0 preference injection is now wired in API DI:** `_get_preference_service_instance()` checks mem0 availability/provider credentials and injects `PreferenceService` into `PromptComposer` (`apps/api/narrare/_app/dependencies_prompts.py:60-129`). This supersedes the previous “DI returns `None`” finding, though graceful no-op remains when mem0 or credentials are unavailable.
- ✅ **`kb_suggested` adoption improved:** writing templates now consume `{{kb_suggested}}` across writing modes (e.g. `writing/en/new_chapter/system.md:41`, `inline_suggest/system.md:62`, `extend_chapter/system.md:47`).
- ✅ **Project writing profile / context metadata improved:** `WritingContextAssembler` accepts `ProjectWritingProfile`, fills synopsis/style/tone/language fields, and tracks wiki/context metadata (`packages/core/narrare_core/writing/context_assembler.py:209-268`).
- ⚠️ **New/remaining documentation drift:** `PROMPT-002` still describes DB-backed prompt templates, but current code evidence shows the UI/API writes project-level `.narrare/prompts/.../system.md` overrides via `PromptManagementService.save_override()`; no DB prompt model/repository path was found. See §5.

---

## 1. Prompt-Inventar

### System-Prompts (inline im Code)

| Datei | Zeilen | Funktion | Zentralisierbar? |
|---|---:|---|---|
| `packages/core/narrare_core/agents/writing_graph_prompts.py` | 122–181, 253–361 | **Fallback only when `composer is None`**; builds inline user/task prompts for graph steps and loads meta via `MetaPromptLoader` as a degraded system prompt. | Keep only if guaranteed test/bare-bones. If reachable in production, centralize through PromptComposer or fail explicitly. |
| `packages/core/narrare_core/agents/*_agent.py` | constructor `system_prompt` params | Agent constructors accept `system_prompt` from PromptComposer/registry; no authored inline system prompt body found. | Not a content issue; this is the injection point. |
| `apps/api/narrare/*` | n/a | No current production inline system-prompt body found in targeted search. Some services pass short runtime `prompt=f"..."` strings to agents (e.g. character arc/worldbuilding), but these are user/run prompts, not system prompts; review under RULE-02a if they encode feature task instructions. | Monitor in CR-01/CR-03; not listed as system prompt debt here. |

### System-Prompts (als Dateien)

Inventory from `packages/core/narrare_core/prompts/_bundled/**/*.md`.

| Kategorie | Sprachen | Modi / Dateien | Anzahl |
|---|---|---|---:|
| `meta` | en/de/fr | `system.md`, `system.lite.md` | 6 |
| `universal` | en/de/fr | `system.md` | 3 |
| `writing` | en feature prompts + tone snippets | 10 feature modes (`new_chapter`, `extend_chapter`, `rewrite_selection`, `scene_by_scene`, `interview`, `interactive_session`, `inline_suggest`, `story_suggest`, `co_author`, `chat`) + 9 tone snippets | 19 |
| `kb` | en | `interview`, `improve`, `suggest`, `enhance`, `extract`, `consistency`, `merge`, `worldbuilding/phase1`, `worldbuilding/phase2` | 9 |
| `analysis` | en | `review`, `beta_reader`, `beta_reader_deepdive`, `consistency`, `summarize`, `readability`, `pov`, `preferences`, `remap` | 9 |
| `planning` | en | `outline`, `character_arc`, `timeline`, `temporal_extraction`, `temporal_consistency` | 5 |
| `chat` | en | root `chat/en/system.md` | 1 |
| `generation` | en + name-style snippets en/de/fr | `names` + 9 name-style snippets | 10 |
| `wiki` | en | `chapter_summary`, `entity_summary` | 2 |

### Default User-Prompts (Templates)

| Kategorie | Sprachen | Modi | Anzahl |
|---|---|---|---:|
| `kb` | en | `consistency` contains `## First Message` | 1 |
| all others | — | Most runtime user prompts are caller-provided (`user_prompt`) or fall back to `PromptContext.author_instructions` (`PromptComposer.build()`) | 0 file templates |

Evidence: `PromptRegistry._parse_prompt()` extracts `## System Prompt` and optional `## First Message` (`packages/core/narrare_core/prompts/registry.py:248-272`); `PromptComposer.build()` uses caller `user_prompt`, then `resolved.first_message`, then `author_instructions` (`packages/core/narrare_core/prompts/composer.py:152-170`).

---

## 2. Globale Prompt-Identität / Capabilities

**Existiert eine globale Prompt-Identität bzw. garantierte Capability-Basis, die für alle KI-Interaktionen gilt?**
Ja — for all `NarrareAgent` paths. `NarrareAgent.__init__` always attaches `NarrareObservability`, `NarrareUniversalRules`, and `NarrareMeta` (`packages/core/narrare_core/agents/base.py:94-109`). Non-agent or degraded fallback paths must be reviewed separately.

**ADR-026-Status:**

| Inhaltstyp | Erwarteter Mechanismus | Implementiert? | Quelle |
|---|---|---|---|
| Garantierte Universal Rules | `NarrareUniversalRules` Capability | ✅ Yes | Capability loads `_bundled/universal/{lang}/system.md` with EN fallback and graceful degradation (`agents/capabilities/universal_rules.py:47-93`, `96-139`). |
| Meta-Persona / Narrare-Identität | `NarrareMeta` Capability | ✅ Yes | Capability loads `_bundled/meta/{lang}/system.md`, extracts deps variables, and returns instructions (`agents/capabilities/meta.py:43-81`, `84-128`). |
| Anpassbare Feature-Instruktionen | PromptComposer / Cascade | ✅ Yes for routeable intents | `PromptComposer.build()` resolves `LLMIntent` route → `PromptRegistry.resolve()` → substitution (`composer.py:88-150`); route table has explicit non-routeable/context-required rationale (`route_table.py:148-165`). |
| Dynamische Daten (KB, Style, Voice) | PromptContext / Variablen / runtime deps | ✅ Yes, with typed provenance improving | `PromptContext` exposes metadata, KB, preferences, profile fields (`prompts/context.py:87-136`); variable taxonomy classifies user/system/feature dynamic vars (`variable_registry.py:38-148`); writing assembler fills tiered KB/profile/wiki fields (`writing/context_assembler.py:95-268`). |

**Security note:** current implementation relies on templates to XML-wrap user content; `variable_engine.substitute()` substitutes values as-is and states automatic wrapping is no longer used (`variable_engine.py:10-16`, `97-100`). CR-01 must therefore verify template-level XML encapsulation for every `_USER_CONTENT_VARS` use.

---

## 3. KB-Context-Formate im Überblick

| Format-Name | Erzeugt in | Struktur | Genutzt von |
|---|---|---|---|
| `PromptContext.kb_context_entries` | `packages/core/narrare_core/prompts/context.py:16-32`, `170-178` | Generic Markdown blocks: `### Type: Name\ncontent`; entry carries source/evidence/confidence/review/freshness metadata. | Generic PromptComposer paths that use `{{kb_context_entries}}`. |
| Writing tiered KB blocks | `WritingContextAssembler.assemble()` (`writing/context_assembler.py:164-198`, `230-268`) | Separate fields: `kb_characters`, `kb_locations`, `kb_factions`, `kb_systems`, `kb_timelines`, `kb_relationships`, `kb_suggested`, `kb_pinned`, plus metadata counts. | Writing prompts (`writing/en/*/system.md`) and context inspector metadata. |
| Wiki-compressed entity context | `format_entities_with_wiki()` (`writing/context_wiki.py:22-70`) + Tier 3 processor (`_tier3_processor.py:24-130`) | Prefer fresh wiki summaries (`narrative_summary`, role, attributes), fallback to raw KB content when stale/pending/missing. | Writing Tier 3 referenced/connected KB context. |
| Proactive suggestions | `ProactiveContextService.suggest()` (`context/proactive_service.py:39-143`) | Name matching + embedding search + hybrid scoring; suggestions include entry type/name/relevance/reason. | KB-005 proactive context and writing `{{kb_suggested}}` path. |
| `world_context` | API/core KB services into `PromptContext.extra` | Free-text related entity/world block; validated heuristically by `validate_world_context()` (`prompts/context.py:35-75`). | KB interview/improve/suggest/enhance/merge/worldbuilding prompts. |
| Timeline/planning context | `planning` prompts + writing `timeline_position` | `{{timeline_position}}` appears in writing/consistency prompts; `{{entity_events}}` is used by timeline planning prompt. | Planning/timeline, consistency prompt context; FIND-009 remains open for richer timeline/graph-edge ingestion. |

**Kontext-Tiers:**

| Tier | Name | Immer dabei? | Inhalt |
|---|---|---|---|
| 1 | immediate | Yes | Current chapter content, frontmatter, outline; outline/frontmatter preserved, content truncated if needed (`context_assembler.py:164-171`, `274-292`). |
| 2 | recent | No (empty for first chapter) | Recent chapters, full text if budget allows, otherwise summaries (`context_assembler.py:173-175`, `294-321`). |
| 3 | kb_referenced | Conditional | Referenced + first-degree connected KB entities, split by type; wiki summaries preferred when fresh (`context_assembler.py:177-190`, `_tier3_processor.py:52-64`). |
| 4 | kb_suggested | Conditional | Ranked remaining KB entities by relevance (`context_assembler.py:191-194`, `_classify.py:65-76`). |
| 5 | pinned | Conditional but bypasses limits | User-pinned KB entities always included (`context_assembler.py:196-198`). |

---

## 4. mem0-Nutzung im Überblick

| Feature | mem0-Nutzung | Art der Nutzung |
|---|---|---|
| mem0 adapter | `create_memory_client()` / `create_memory_client_sync()` | Only place mem0 is imported; uses `AsyncMemory.from_config`, pgvector vector store when DB URL provided, embedding cascade, and `NullMemoryClient` fallback (`memory/mem0_client.py:1-15`, `205-318`, `321-375`). |
| Feedback learning | `MemoryFeedbackService` → core `FeedbackService` | Records accepted/rejected/modified AI suggestions with project/mode/genre metadata before forwarding to memory (`apps/api/narrare/memory/service.py:31-117`). |
| Preference retrieval | `MemoryPreferenceService` / core `PreferenceService` | Returns style/content/constraints profile for user/project (`apps/api/narrare/memory/service.py:119-182`). |
| PromptComposer auto-injection | `PromptComposer(preference_service=...)` | If service exists and context has `user_id` + `project_id`, injects `profile.to_prompt_text()` into `user_preferences` (`prompts/composer.py:93-114`). |
| AI Invocation pipeline | `PreferenceContextEnricherImpl` | Parallel/pre-composer enrichment into `dynamic_inputs["user_preferences"]`, no-op with logs when provider/IDs unavailable (`ai_invocation/enrichers/preferences.py:35-115`). |
| Preference analysis | `PreferenceAnalysisAgent` path | Uses PromptComposer route `LLMIntent.EXTRACT` / mode `preferences`, with feedback text as runtime user prompt (`apps/api/narrare/memory/analysis_service.py:203-228`). |

**mem0-Konfiguration:**

- Default memory extraction models are intentionally small/cheap (`memory/mem0_client.py:28-41`).
- Extraction prompt is language-specific for en/de/fr (`memory/mem0_client.py:43-88`).
- Embedding cascade: OpenAI → provider-native future hook → local sentence-transformers → disabled/null (`memory/mem0_client.py:10-15`, `124-202`).
- API prompt DI now attempts real singleton wiring and degrades to no preference service if mem0 package or credentials are missing (`apps/api/narrare/_app/dependencies_prompts.py:60-129`).

---

## 5. WebUI-Prompt-Anpassbarkeit

**System vorhanden:**
Ja, but current implementation appears **file/project-override based**, not truly DB-backed despite PROMPT-002 documentation.

**Architektur:**
- **Frontend:** Settings → Prompts UI via `PromptsTab` and `PromptEditor`; lists prompts, filters categories, edits content, resets, shows diff/update states (`packages/web/components/studio/settings/PromptsTab.tsx:36-170`, `PromptEditor.tsx:25-194`).
- **API:** `/prompts` router lists, retrieves, saves, resets, cascades, diffs prompt overrides (`apps/api/narrare/prompts/router.py:39-115`).
- **Service:** API wrapper delegates to core; core `PromptManagementService` scans bundled prompts and writes overrides (`apps/api/narrare/prompts/service.py:28-99`, `packages/core/narrare_core/prompts/management.py:56-178`).
- **CLI:** No current evidence of a prompt-management CLI in this audit scope.
- **MCP:** Planned adapter only; no prompt-management adapter yet (features index marks MCP as idea and blocked by Q-001).
- **A2A:** Planned adapter only; no prompt-management adapter yet (features index marks A2A as idea and blocked by Q-002).

**Kaskaden-System (CSS-artig):**
1. **DB template:** documented and accepted as `db_content` by `PromptRegistry.resolve()` (`registry.py:80-113`), but no current production caller/model/repository was found that persists prompt templates in DB.
2. **Project:** `{project_root}/.narrare/prompts/{category}/{language}/{mode}/system.md` (`registry.py:157-163`). Current Settings UI save path writes here (`management.py:153-178`, `250-269`).
3. **User-global:** `~/.config/narrare/prompts/{category}/{language}/{mode}/system.md` (`registry.py:164-168`).
4. **Bundled:** `_bundled/{category}/{language}/{mode}/system.md` (`registry.py:170-175`).
5. **Fallback:** bundled English for non-EN feature prompts (`registry.py:176-181`).

**Anpassbare Prompts:** Feature-specific templates resolved by PromptComposer/Cascade (`writing`, `kb`, `analysis`, `planning`, `chat`, `generation`, `wiki`). Project/user-global file overrides work architecturally. UI currently exposes project-level prompt edits.

**Nicht anpassbare Prompts (obwohl zentralisierbar):** `NarrareMeta` and `NarrareUniversalRules` are guaranteed Capabilities by ADR-026 and intentionally not user-customizable through the feature prompt cascade (`CONSTRAINTS.md:106-119`; `agents/base.py:97-101`).

**Locale-Strategie:**
- Feature-Templates: EN-only bundled feature prompts are intentional under current ADR-026/prompt-content policy; output language is controlled via variables, especially `{{writing_language}}`.
- Meta/Universal Rules: en/de/fr variants exist and are loaded by capabilities with EN fallback.
- Ausgabe-Sprache: `PromptContext.as_variables()` defaults `writing_language` to `language` if unset (`prompts/context.py:164-167`). Existing templates still mix deprecated `{{language}}` and canonical `{{writing_language}}`; `VARIABLE_ALIASES` documents `language → writing_language` as deprecated for new templates (`variable_registry.py:7-10`, `161-165`).

**PROMPT-002 documentation drift:**
- Docs say DB templates are highest-priority, per-user, and saved in the database (`docs/features/prompts/PROMPT-002-db-templates.md:56-115`, `127-149`).
- Code evidence found no DB prompt model/repository; the API `PUT /prompts/{id}` delegates to `PromptManagementService.save_override()`, which writes a file under `.narrare/prompts/.../system.md` (`router.py:97-105`, `management.py:153-178`, `250-269`).
- Risk: users/reviewers may believe prompt overrides are per-user DB records while implementation is project-file scoped.

---

## 6. Bekannte inhaltliche Probleme (Vorbelastung)

| Befund / Thema | Status 2026-06-11 | Aktueller Hinweis |
|---|---|---|
| FIND-001 missing PromptComposer targets | ✅ Resolved | Route table governs routeable/context-required/non-routeable intents (`route_table.py:72-165`). |
| FIND-002 production inline prompt fallbacks | ✅ Mostly resolved | Previous consistency/extraction fallbacks no longer evidenced; `writing_graph_prompts.py` still has composer-None fallback and should remain non-production/test-scoped. |
| FIND-003 mem0 preference injection not wired | ✅ Resolved | DI now creates `PreferenceService` when mem0 + credentials are available (`dependencies_prompts.py:60-129`). |
| FIND-004 output token profiles under-calibrated | ✅ Resolved per finding/current state | `FIND-004` marks all 28 intents mapped; CR-08 records SET-005/per-intent profile completion. |
| FIND-005 variable registry coverage incomplete | ✅ Resolved | `variable_registry.py` has user/system/feature-dynamic taxonomy and aliases (`variable_registry.py:38-148`). |
| FIND-007 project writing profile inconsistent | ✅ Resolved | `WritingContextAssembler` consumes `ProjectWritingProfile` and maps profile fields (`context_assembler.py:209-268`). |
| FIND-008 cross-feature precedence under-specified | ✅ Resolved | Prompt standards now define precedence: author instruction → project profile → scene/timeline → curated KB → mem0 → generated suggestions (`docs/development/prompt-standards.md:460-479`). |
| FIND-009 timeline/graph edges not consumed by consistency checker | 🟡 Open | Timeline position exists, but richer timeline/graph edge ingestion remains a documented gap (`_audit/results/content-review/findings/FIND-009-timeline-consistency-gap.md`). |
| Prompt customization UX | 🟡 Planned/partial | Editing/reset/diff exists; PROMPT-003 preview/test/variable explanation UX remains planned (`docs/features/prompt-customization-ux.md:44-149`). |
| PROMPT-002 DB-template claim | 🔴 Newly confirmed drift | Feature docs describe DB-backed templates, but current code writes project-level file overrides. Needs doc correction or actual DB implementation. |

---

## 7. Bewertungs-Skala (gilt für alle CR-Dateien)

| Note | Bedeutung |
|---|---|
| ⭐⭐⭐⭐⭐ | Vorbildlich, inhaltlich durchdacht und effektiv |
| ⭐⭐⭐⭐ | Gut, kleinere inhaltliche Lücken |
| ⭐⭐⭐ | Funktional, aber inhaltlich optimierungswürdig |
| ⭐⭐ | Inkonsistent oder inhaltlich problematisch |
| ⭐ | Kritisch – fehlt, widerspricht sich oder schadet der Nutzererfahrung |

---

## CR-00 Handoff für CR-01

Root cause focus for the next prompt review: most earlier architectural causes were fixed (capabilities, routeability, variable taxonomy, mem0 DI). The main remaining content-review risks are now **template-level quality and doc/runtime drift**, especially XML wrapping because substitution is template-based, PROMPT-002 DB-vs-file mismatch, and the open timeline/graph context gap.

Recommended next review prompt: **CR-01 – Default-Prompts Qualitätsaudit**, using this updated inventory and treating old CR-01 findings as partially stale unless current evidence confirms them.
