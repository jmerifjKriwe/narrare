# Narrare — Product Roadmap: MVP → Post-MVP

> **MVP is COMPLETE.** This document now tracks the full product roadmap.
> Phases 0-5 are the MVP (shipped). Phase 6 is the current focus.
> Post-MVP phases are planned with technical details.
>
> This plan is the source of truth for what has been built and what comes next.
> Location: `docs/mvp/mvp-plan.md`
> Maintained by: Architecture Agent

---

## Definition of Done (MVP)

The MVP is complete when a developer can:

1. Clone the repo and run `just dev-setup` on a clean machine
2. Run `just dev` and have the WebUI accessible at `http://localhost:3000`
3. Complete the 5-step Setup Wizard
4. See demo content (if selected) in the editor and dashboard
5. Write text in the editor and have it autosaved
6. Log in with the dev credentials
7. Change settings and have them persist across restarts
8. Run `just test` and have all tests pass
9. Run `just check` and have all constraints pass
10. Generate a full chapter draft with AI (WRITE-002)
11. Manage knowledge base entries with template-driven editor (KB-001)
12. See storyboard visualization with drag-and-drop (PLAN-003/005)
13. Record feedback and see preference profile (LEARN-001)
14. All 2759+ tests pass (2113 backend + 646 frontend)

No stubs. No "TODO: implement this later." No hardcoded bypasses.

---

## What the MVP Includes

### Infrastructure (must be production-quality from day one)

| Component | Why it must be right from the start |
|-----------|-------------------------------------|
| Monorepo structure | Everything else builds on this |
| Database + migrations | Schema changes later are expensive if base is wrong |
| Auth system | Security cannot be retrofitted |
| LLM Gateway (skeleton) | All future AI features go through this |
| Prompt system (skeleton) | Cascade resolver must be right before prompts are added |
| Settings persistence | Used by every feature |
| Dev container | Every developer needs a reproducible environment |
| CI pipeline | Constraints must be enforced before any code accumulates |
| pre-commit hooks | Same reason |
| justfile | Developer experience from day one |
| release-please | Versioning from the first commit |

### Application Features

| Feature | What specifically is built |
|---------|---------------------------|
| Setup Wizard | All 5 steps, fully functional, all 3 languages |
| Demo content | All 3 demo projects loadable |
| Writing Editor | Full editor surface — extensible for all future AI features |
| Dashboard | Basic dashboard showing novel + chapter list |
| User Settings | User preferences, persisted |
| Project Settings | Project configuration, persisted |
| Login | JWT auth, dev user seeded |
| Dev login | `dev@narrare.dev` / `narrare-dev` |

### What is explicitly NOT in MVP

These are real features that will be built — but not now:
- Any AI writing generation (new chapter, extend, rewrite)
- KB entity management
- Analysis features
- Planning features
- Background task processing (Celery)
- Embedding/pgvector operations
- mem0 memory layer
- MCP / A2A adapters

The infrastructure for all of these is designed in from day one.
The services and routes simply don't exist yet — no stubs, no placeholder endpoints.

---

## The Editor: Built for the Future

The editor is the most important MVP component because it must be extensible
without refactoring. Getting it wrong now means rewriting it later.

### What the editor must support at MVP (even without AI features)

**Document model:**
- ProseMirror or equivalent (not a textarea — that cannot be extended)
- Proper node types: paragraph, heading, scene-break, dialogue
- Chapter-scoped documents (not the whole novel in one editor)
- Autosave on change (configurable interval)
- Word count, reading time (live)

**Layout infrastructure:**
- Left sidebar: chapter list (collapsible)
- Main: editor surface
- Right sidebar: context panel (empty at MVP, populated by AI features later)
- Toolbar: formatting + action slots for AI features (empty at MVP)
- Command palette: keyboard-accessible (empty at MVP, populated later)

**Why this level of detail matters:**
If the editor is a `<textarea>`, adding inline AI suggestions later requires
replacing the entire editor. If the layout is a simple column, adding the
context panel later requires restructuring all pages. Build the shell correctly
now.

### Editor extensibility contract

Every AI feature added to the editor will use one of these slots:
- **Toolbar action** — a button that triggers an AI operation
- **Context panel section** — a panel that shows AI-generated content
- **Inline decoration** — highlights or annotations in the text
- **Command palette command** — keyboard-accessible AI operation

These slots are designed into the editor at MVP. The AI features plug into them.
No structural changes needed when AI features arrive.

---

## Implementation Order

The order matters. Each phase unblocks the next.

### Phase 0: Repository Foundation ✅ COMPLETE
*Duration: 1 session*
*No application code. Everything that makes development possible.*

```
✓ Monorepo structure (apps/, packages/, docs/, tests/, scripts/)
✓ pyproject.toml with Python 3.14, all dependencies pinned
✓ pnpm workspace for frontend
✓ justfile with all commands
✓ .pre-commit-config.yaml (all hooks)
✓ .devcontainer/ (Dockerfile + devcontainer.json + post-create.sh)
✓ docker-compose.dev.yml (postgres pgvector/pgvector:pg17 + redis)
✓ release-please configuration
✓ GitHub Actions: ci.yml, architecture.yml, release-please.yml
✓ scripts/check_architecture.py (full implementation)
✓ pyright configuration (pyrightconfig.json)
✓ ruff configuration (pyproject.toml)
✓ pytest configuration (pyproject.toml)
✓ .env.example
✓ Initial CHANGELOG.md
✓ README.md (setup instructions only)
```

**Definition of done:** `just dev-setup` runs clean. `just check` passes on empty project.

---

### Phase 1: Core Infrastructure ✅ COMPLETE
*Duration: 2-3 sessions*
*The foundation layers. No HTTP yet.*

```
packages/core/narrare_core/
  shared/
    ✓ frontmatter.py (parse_frontmatter, parse_frontmatter_with_content)
    ✓ file_utils.py (safe read/write, path helpers)
    ✓ pagination.py (PaginatedResponse type)
    ✓ result.py (Result[T, E], Ok, Err)

  llm/
    ✓ intents.py (LLMIntent enum — stubs for all intents, routing table)
    ✓ result.py (LLMResult, StreamChunk, LLMError)
    ✓ retry.py (retry configs, exponential backoff)
    ✓ metrics.py (cost tracking hooks — Prometheus counters)
    ✓ _providers/registry.py (provider registry, empty providers)
    ✓ _providers/openai.py (OpenAI + OpenAI-compatible adapter)
    ✓ _providers/anthropic.py (Anthropic adapter)
    ✓ _providers/zai.py (Z.AI OpenAI-compatible adapter)
    ✓ embeddings.py (embed_texts — approved RULE-01 exception)
    ✓ gateway.py (LLMGateway — full implementation)

  prompts/
    ✓ context.py (PromptContext dataclass — all fields)
    ✓ variable_engine.py (substitution, validation)
    ✓ meta.py (meta-prompt loader, cascade, lite variant)
    ✓ registry.py (single cascade resolver — replaces all three old resolvers)
    ✓ composer.py (assembles final prompt from parts)
    ✓ cache.py (fixed-key prompt cache)
    ✓ service.py (CRUD for file-based prompt management)
    ✓ _bundled/ (meta/en/system.md, meta/en/system.lite.md, meta/de/, meta/fr/)

  schemas/
    ✓ auth.py, novels.py, chapters.py (base schemas for MVP)
```

**Tests:** `tests/unit/core/` — full coverage for llm/ and prompts/

**Definition of done:** LLMGateway can make a real call to at least one provider.
Prompt cascade resolves correctly in all test cases.

---

### Phase 2: API Foundation ✅ COMPLETE
*Duration: 2 sessions*
*The HTTP layer. No features yet — just the application shell.*

```
apps/api/narrare/
  _app/
    ✓ main.py (FastAPI factory, all middleware, lifespan)
    ✓ database.py (async engine, get_db session factory)
    ✓ dependencies.py (get_settings, get_gateway, get_composer)
    ✓ middleware.py (CORS, rate limiting, request logging)
    ✓ lifespan.py (startup: auto-migrate DB, seed dev user, log schema version)

  auth/
    ✓ models.py (User SQLAlchemy model)
    ✓ schemas.py (LoginRequest, TokenResponse, UserResponse)
    ✓ contracts.py (AuthServiceProtocol)
    ✓ repository.py (get_user_by_email, create_user)
    ✓ security.py (JWT create/verify, bcrypt hash/verify)
    ✓ service.py (login, register, refresh)
    ✓ router.py (POST /auth/login, /auth/register, /auth/refresh)

  novels/
    ✓ models.py (Novel SQLAlchemy model)
    ✓ schemas.py
    ✓ contracts.py
    ✓ repository.py
    ✓ service.py
    ✓ router.py (CRUD + list)

  chapters/
    ✓ models.py (Chapter model — full schema for future AI fields)
    ✓ schemas.py
    ✓ contracts.py
    ✓ repository.py
    ✓ service.py
    ✓ router.py (CRUD + reorder)

  volumes/
    ✓ [same structure — chapters can belong to volumes]

  settings/
    ✓ models.py (UserSettings, ProjectSettings)
    ✓ schemas.py
    ✓ contracts.py
    ✓ repository.py
    ✓ user_service.py + project_service.py + resolver.py
    ✓ router.py

  metrics/
    ✓ router.py (Prometheus scraping endpoint)

Alembic:
    ✓ Initial migration (all tables)
    ✓ Dev seeder (dev user + demo content scripts)
```

**Tests:** `tests/integration/` — all router endpoints, auth flow

**Definition of done:** `just dev-api` starts. Auth works. CRUD works. Migrations run automatically on startup. `just db-migrate` also works for manual control.

---

### Phase 3: Setup Wizard Backend ✅ COMPLETE
*Duration: 1-2 sessions*

```
apps/api/narrare/setup/
  ✓ contracts.py
  ✓ schemas.py (SetupWizardState, all 5 step request/response types)
  ✓ service.py:
      - validate_step_1() (project name, language, autosave)
      - validate_step_2() (novel metadata)
      - validate_step_3() (starter content selection)
      - load_demo_content() (Fantasy / SciFi / German)
      - validate_step_4() (provider + API key validation — real test call)
      - complete_setup() (creates novel, chapters, settings, writes to user_providers + user_ai_settings, returns redirect)
  ✓ _validation.py (step validation pure functions — RULE-04 split)
  ✓ provider_service.py (fetch available models per provider — real API call)
  ✓ router.py

Demo content:
  ✓ scripts/demo_data/fantasy/ (Echoes of the Thornwall — 4 chapters, 5 KB stubs)
  ✓ scripts/demo_data/scifi/ (Dead Signal — 3 chapters, 3 KB stubs)
  ✓ scripts/demo_data/german/ (Im stillen Wald — 2 chapters, 3 KB stubs)
```

**Tests:** `tests/integration/setup/` — all 5 wizard steps, all 3 demo projects, provider validation

---

### Phase 4: Frontend Foundation ✅ COMPLETE
*Duration: 2-3 sessions*
*The shell. Correct from day one. Built for extension.*

```
packages/web/
  ✓ Next.js 16 App Router setup
  ✓ Tailwind CSS + design tokens (CSS variables in globals.css)
  ✓ i18n setup (next-intl, en/de/fr)
  ✓ Zustand stores: auth, editor, ui
  ✓ TanStack Query setup
  ✓ API client (typed, all endpoints)

  app/
    ✓ (auth)/login/page.tsx
    ✓ (auth)/register/page.tsx
    ✓ (setup)/wizard/page.tsx (5-step wizard, fully functional)
    ✓ (app)/dashboard/page.tsx (novel list + chapter list)
    ✓ (app)/novel/[id]/editor/page.tsx (editor page — full shell)

  components/
    setup/
      ✓ WizardLayout.tsx
      ✓ Step1Location.tsx
      ✓ Step2Novel.tsx
      ✓ Step3StarterContent.tsx
      ✓ Step4AIProvider.tsx (with live model loading)
      ✓ Step5Confirm.tsx
    editor/
      ✓ EditorLayout.tsx (sidebar + main + right panel slots)
      ✓ ChapterSidebar.tsx
      ✓ EditorSurface.tsx (ProseMirror — full node types, autosave)
      ✓ EditorToolbar.tsx (formatting + AI action slots, empty)
      ✓ ContextPanel.tsx (right panel shell, empty)
      ✓ CommandPalette.tsx (shell, empty)
      ✓ WordCount.tsx
    shared/
      ✓ Button, Input, Select, Modal, Toast (design system components)
      ✓ LanguageSwitch.tsx
      ✓ ThemeToggle.tsx (light/dark)
```

**Definition of done:** Complete Setup Wizard flow works. Editor opens and autosaves.
All UI text is i18n strings (no hardcoded English). Light + dark mode works.

---

### Phase 5: Integration, AI & Polish ✅ COMPLETE
*Duration: 15+ sessions*
*The full feature stack: writing, KB, planning, learning.*

**Core Infrastructure:**
  ✓ LLM Gateway with 7 providers + ModelRegistry
  ✓ Prompt system with cascade resolution + variable interpolation
  ✓ Writing pipeline (4 modes: full_draft, scene_by_scene, interview, interactive)
  ✓ Context assembly with 5-tier ranking + token budgets
  ✓ Embedding cascade (4-tier: OpenAI → local → disabled) — ADR-017
  ✓ PreferenceAnalysisAgent for deep pattern extraction
  ✓ ChapterSummaryAgent (NarrareAgent pattern)
  ✓ WritingGraph (6-step pydantic-graph: plan → write → review → finalize → summary)
  ✓ 5 structure adapters (3-act, 5-act, hero's journey, save the cat, 7-point)
  ✓ AIRemapService with summary-based stage suggestions
  ✓ Event-driven architecture (Redis Pub/Sub + TaskIQ stubs)

**Backend Modules (all contract-first, per RULE-03):**
  ✓ auth/ — JWT + httpOnly refresh cookies + argon2id
  ✓ novels/ — CRUD + word counts
  ✓ chapters/ — CRUD + content versioning + versions API
  ✓ volumes/ — CRUD + stats + reorder + default auto-creation
  ✓ settings/ — User/Project AI settings + provider management + model routing + token limits
  ✓ setup/ — 5-step wizard + provider validation + demo loader + Z.AI dual endpoint
  ✓ writing/ — Generation pipeline + SSE streaming + WebSocket sessions + stats
  ✓ memory/ — Feedback recording + preference profile + analysis trigger + mem0 integration
  ✓ prompts/ — 7-endpoint CRUD + update detection + diff comparison + variable metadata
  ✓ generation/ — Name generation + KB dedup
  ✓ kb/ — Full CRUD + 8 entity types + cross-references + autocomplete + relationships
  ✓ templates/ — Cascade resolution (user → project → bundled) + version-aware upsert
  ✓ planning/ — Storyboard + outlines + sync status + AI remap + chapter summary endpoint

**Frontend:**
  ✓ TipTap v3 editor with 4 custom extensions (NarrareDocument, SceneBreak, DialogueMark, Autosave)
  ✓ EditorLayout with sidebar + main + right panel slots
  ✓ MetadataSidebar with live stats + session delta + chapter metadata
  ✓ CommandPalette (Cmd+K) with extensible command registry
  ✓ GenerationPanel + GenerationConfig + GenerationDraft + SessionPanel + ChatMessage
  ✓ RatingPrompt + LearningStatus + LearningTab + PreferenceProfile
  ✓ Full KB editor: template-driven accordion, flat fallback, @mention autocomplete, tag input
  ✓ StoryboardPanel with DnD + 7 sub-components + structure change dialog
  ✓ WritingGraphStatus (pipeline step visualization)
  ✓ NameGenerator + NameResults with duplicate badges
  ✓ PromptSettings + PromptEditor + PromptDiff in Settings
  ✓ ToneLibrarySection with 9 bundled tones + custom CRUD
  ✓ Settings: AI providers, model routing, token limits, project AI settings
  ✓ Dashboard + delete + wizard (5 steps with demo prefill)
  ✓ Focus mode (ESC + floating minimize button)

**Demo Content:**
  ✓ "Echoes of the Thornwall" (EN, Fantasy) — 4 chapters, 15 KB entries
  ✓ "Dead Signal" (EN, SciFi) — 3 chapters, 7 KB entries
  ✓ "Im stillen Wald" (DE, Fantasy) — 2 chapters, 5 KB entries

**Infrastructure:**
  ✓ 19 Alembic migrations (auto-run on startup)
  ✓ OpenTelemetry-only observability standard accepted (ADR-031; implementation migration pending)
  ✓ Redis Pub/Sub event bus + TaskIQ integration stubs
  ✓ pgBouncer for production
  ✓ 17 ADRs documented
  ✓ Pre-commit: architecture, ruff, pyright, bandit, biome, i18n, TypeScript

**Testing:**
  ✓ 2113 backend tests (unit + integration)
  ✓ 646 frontend tests (Vitest + Testing Library + MSW)
  ✓ Property-based tests (hypothesis) for core utilities
  ✓ Architecture validation via check_architecture.py (526 files, 0 new violations)

**Metadata Consistency (cross-cutting):**
  ✓ 9 bundled tones (contemplative, dark, adventurous, romantic + existing 5)
  ✓ writing_language freetext field (separate from prompt language)
  ✓ name_style freetext field (renamed from culture, with fallback)
  ✓ explanation_language field
  ✓ Custom Tone CRUD (4 endpoints)

---

### Phase 6: Writing Intelligence ⏳ IN PROGRESS
*Duration estimate: 4-6 sessions*
*Extending the writing experience: continue, rewrite, refine.*

#### WRITE-003: Extend Chapter (AI: Continue)

**Ziel:** Cursor platzieren → "Weiter" → Text wird fortgesetzt.

**User Story:** Writer schreibt einen Absatz, kommt nicht weiter. Klickt "Continue". AI analysiert die letzten 500-1000 Tokens, versteht die Szene, und schreibt nahtlos weiter.

**Architektur:**
- **Endpoint:** `POST /api/v1/writing/chapters/{id}/extend`
- **Service:** `DraftService.extend()` in `writing/draft_service.py`
- **Contract:** Erweiterung von `DraftServiceProtocol` in `writing/contracts.py`
- **LLM Intent:** `LLMIntent.EXTEND` (bereits definiert in `intents.py`)
- **Composer Mapping:** `EXTEND → "writing"/"extend_chapter"` (bereits konfiguriert)
- **Streaming:** SSE (wiederverwendung des bestehenden Streaming-Infrastruktur)

**Core-Änderungen:**
- Prompt-Templates: `_bundled/writing/{en,de,fr}/extend_chapter/system.md`
  - Pre-Text Verbatim inkludieren: "Here's what came before: ..."
  - Cursor-Position markieren: `[CONTINUE FROM HERE]`
  - Längensteuerung: Short (100-200w), Medium (300-500w), Long (500-1000w)
  - Stilanalyse aus Pre-Text: Satzstruktur, Dialog-Anteil, Erzählperspektive
- `WritingContext` erweitern: `pre_text: str`, `post_text: str`, `extend_length: str`
- `WritingPipeline` erweitern: neue Dispatch-Logik für extend-Modus

**Backend-Änderungen:**
- Neuer Router `writing/router_extend.py` (RULE-04: eigener Router)
- Schema: `ExtendRequest(chapter_id, cursor_position, length)`, `ExtendResponse`
- Service ruft Kontext-Assembler auf (Pre-Text ab Cursor-Position)
- SSE Streaming wie bei FULL_DRAFT

**Frontend-Änderungen:**
- Cursor-Position aus TipTap extrahieren (`editor.state.selection`)
- "Continue" Button im Toolbar oder浮动
- Inline-Fortsetzung: Text wird direkt am Cursor eingefügt
- Längen-Wähler: Short/Medium/Long als kompakte Inline-Option
- Accept/Reject/Continue-More Controls
- RatingPrompt-Integration (wiederverwendung)

**Constraints:**
- Min. 100 Wörter bestehender Text für gute Qualität
- Max. 1000 Wörter pro Fortsetzung
- TipTap Transaction für Cursor-Position nötig

**Dependencies:** Prompt Templates (neu), bestehende Streaming-Infrastruktur (✅)

#### WRITE-004: Rewrite Selection (AI: Rewrite)

**Ziel:** Text auswählen → Modus wählen → 1-3 Alternativen erhalten → ersetzen.

**User Story:** Writer markiert einen Absatz, der "flach" wirkt. Klickt "Rewrite" → wählt "More Dramatic" → bekommt 3 Varianten → wählt die beste → ersetzt den Originaltext.

**Architektur:**
- **Endpoint:** `POST /api/v1/writing/rewrite`
- **Service:** `DraftService.rewrite()` in `writing/draft_service.py`
- **LLM Intent:** `LLMIntent.REWRITE` (bereits definiert)
- **Composer Mapping:** `REWRITE → "writing"/"rewrite_selection"` (bereits konfiguriert)
- **Kein Streaming** — Response kommt als Array von Alternativen

**Core-Änderungen:**
- `RewriteMode` Enum: `tone | style | voice | fix | custom`
- Prompt-Templates: `_bundled/writing/{en,de,fr}/rewrite_selection/system.md`
  - Modus-spezifische Strategien:
    - Tone: Emotionale Sprache, Pacing, Wortwahl anpassen
    - Style: Satzstruktur, Beschreibungsdichte, Aktiv/Passiv
    - Voice: Charakter-Sprachmuster aus KB (speech_patterns field)
    - Fix: Show-don't-tell, Redundanzen entfernen, schwache Verben stärken
    - Custom: Freitext-Instruktionen
- `RewriteRequest(selection_text, chapter_id, mode, options, character_id?, count)`
- `RewriteResponse(alternatives: list[RewriteAlternative])`
- `RewriteAlternative(text, label, focus_description)`

**Backend-Änderungen:**
- Schema: `RewriteRequest`, `RewriteResponse`, `RewriteAlternative`, `RewriteMode`
- Router `writing/router_rewrite.py`
- Service: Multi-Response Parsing (1-3 Alternativen aus LLM-Output)
- Kontext: Selection + 200 Tokens Umgebung + Chapter-Frontmatter + Charakterprofil (für voice)

**Frontend-Änderungen (Design-Highlight):**
- **Text-Selection Detection:** TipTap Selection → Position + Text extrahieren
- **Rewrite-Mode-Selektor:** Inline-Panel mit 5 Modi (Tone/Style/Voice/Fix/Custom)
  - Voice-Modus: Charakter-Dropdown aus KB
  - Custom-Modus: Freitext-Input
  - Count-Wähler: 1-3 Alternativen
- **Alternatives-Vergleichs-UI** (zentrales Design-Element):
  - Karten-Layout: Original + 1-3 Alternativen als Tabs oder nebeneinander
  - Inline-Diff-Hervorhebung: Änderungen farblich markiert (hinzugefügt/entfernt)
  - One-Click Replace: Klick ersetzt die Auswahl direkt im Editor
  - Insert-as-New: Fügt Alternative als neue Passage ein
  - Sanfte Animationen für das Erscheinen/Verschwinden der Karten
  - Ästhetik: Editorial/Refined — nicht vom Schreiben ablenken
- **Kontextmenü:** Rechtsklick auf Selection → "Rewrite" Option
- **Toolbar-Integration:** "Rewrite" Button aktiv wenn Text ausgewählt

**Constraints:**
- Selection min. 50 Wörter, max. 2000 Wörter
- Voice-Modus braucht Charakter im KB
- Show-don't-tell kann Details erfinden die nicht im Original stehen
- Custom-Instruktionen braucht LLM-Interpretation

**Dependencies:** Prompt Templates (neu), Rewrite-Schemas (neu), KB für Voice-Modus (✅)

#### Phase 6 Shared Tasks

- E2E Smoke Tests für beide Features
- i18n für alle neuen UI-Strings (en/de/fr)
- Prompt-Templates in 3 Sprachen
- Unit + Integration Tests für Backend
- Component Tests für Frontend
- Feature Specs aktualisieren (WRITE-003, WRITE-004 → status: stable)
- ADR falls nötig (Rewrite als eigene Service-Schicht)

---

## Post-MVP Roadmap

> **Status:** Geplant. Technische Kerndetails definiert. OpenSpec Proposals bei Start der jeweiligen Phase.
>
> **Architekturelle Voraussetzungen:** Alle Post-MVP-Features bauen auf der bestehenden Infrastruktur auf:
> - RULE-12 (Service Layer als einzige öffentliche API) — MCP/A2A/CLI sind Clients
> - Protocol-basierte DI — Services ohne Code-Änderungen für neue Clients nutzbar
> - Event-Driven Architecture (ADR-012) — TaskIQ für Hintergrundverarbeitung bereit
> - Embedding Cascade (ADR-017) — Skaliert für zukünftige Embedding-Anwendungen
> - Lernschleife (LEARN-001) — Fundament für alle Adaptions-Features

---

### Post-MVP Phase 1: "Writing Intelligence"

*Schwerpunkt: Die Schreiberfahrung intelligenter machen. Writer's Block überwinden. Stimme erhalten.*

| Feature | ID | Kernpunkte |
|---------|-----|-----------|
| **Co-Author Mode** | WRITE-006 | Dialog-basiertes Schreiben mit AI. Nicht "Schreib mir ein Kapitel" sondern "Lass uns gemeinsam diese Szene entwickeln." Nutzt Interactive Session Infrastructure. AI fragt nach, macht Vorschläge, widerspricht. |
| **Inline AI Suggestions** | WRITE-007 | Autocomplete-ähnlich: AI schlägt den nächsten Satz vor während man tippt. TipTap Decoration API. Debounced (1s Pause → Vorschlag). Ghost-text Darstellung. Tab zum Akzeptieren. Braucht niedrige Latenz LLM-Calls. |
| **Entity Extraction** | KB-007 | Automatische Entität-Erkennung aus Chapter-Text. AI liest Chapter → schlägt neue KB-Einträge vor (Charaktere, Orte, Gegenstände). Event-getriggert nach Chapter-Save. Nutzt bestehende ChapterSummaryAgent-Infrastruktur. |
| **Style Adaptation** | LEARN-002 | Baut auf LEARN-001 auf: Preferences werden nicht nur gespeichert sondern aktiv in Prompts injiziert. "Du schreibst kurze Sätze, wenig Adjektive, viel Dialog" → AI passt Output an. `PromptContext.style_constraints` bereits vorbereitet. |

**Technische Kerne:**
- WRITE-007 braucht TipTap `DecorationSet` Extension + SSE-Streaming mit `<200ms` Time-to-First-Token
- KB-007 braucht neuen `EntityExtractionAgent` (NarrareAgent-Pattern) + Event: `ChapterSaved → ExtractEntities`
- LEARN-002 erweitert `PromptComposer` um dynamische Stil-Constraints aus PreferenceProfile

**Dependencies:** Phase 6 (WRITE-003/004) sollte zuerst abgeschlossen sein — WRITE-007 erweitert die Continue-Funktionalität.

---

### Post-MVP Phase 2: "Analysis & Feedback"

*Schwerpunkt: Dem Writer zeigen was funktioniert und was nicht. Objektives Feedback.*

| Feature | ID | Kernpunkte |
|---------|-----|-----------|
| **Beta Reader Simulation** | ANAL-001 | AI liest als Beta-Reader: "Pacing dragging in chapter 3", "Character motivation unclear", "Great tension in the chase scene". Structured Output mit `BetaReaderReport` (Gesamtbewertung, Kapitel-Feedback, konkrete Vorschläge). |
| **POV Analysis** | ANAL-004 | Erkennt Head-Hopping, inkonsistente Perspektive, Filter-Wörter. Pro-Absatz-Analyse. Visuelle Markierung im Editor (TipTap Decoration). |
| **Author Voice Profiling** | ANAL-007 | Extrahiert Stimm-profil aus bestehendem Text: Satzlängen-Verteilung, Vokabular-Diversität, Dialog/Narration-Ratio, Häufigkeitswörter. Speichert als `VoiceProfile` in User-Settings. |
| **Character Voice Profiling** | ANAL-008 | Gleiches wie ANAL-007 aber per Charakter. Analysiert alle Dialoge eines Charakters → extrahiert Sprachmuster. Speichert in KB-Entity (CharacterMetadata.speech_patterns). |
| **Voice Consistency** | WRITE-010 | Nutzt ANAL-007 + ANAL-008 Profile um Voice-Drift zu erkennen. "This dialogue doesn't sound like Elena — she uses short sentences, not philosophical monologues." Inline-Warnungen im Editor. |

**Technische Kerne:**
- Alle ANAL-Features nutzen NarrareAgent-Pattern mit Structured Output
- `BetaReaderAgent` (neu): Input = Kapitel-Text + KB-Kontext, Output = `BetaReaderReport`
- `VoiceProfiler`: Statistische Analyse + LLM-basierte Muster-Erkennung
- TipTap Decorations für Inline-Markierung (POV-Verletzung, Voice-Drift)
- ANAL-007/008 Output speichern in User-Settings bzw. KB-Entity

**Dependencies:** Keine harten Abhängigkeiten. Kann parallel zu Phase 1 laufen.

---

### Post-MVP Phase 3: "Collaboration & Publishing"

*Schwerpunkt: Manuscript exportieren. Projekte importieren. Mit AI chatten.*

| Feature | ID | Kernpunkte |
|---------|-----|-----------|
| **Manuscript Export** | IO-001 | Export als PDF, ePub, DOCX, Markdown. Jinja2-Templates für Formatierung. Chapter-Order aus Volume-Struktur. KB-Anhang als Anhang. Titelseite aus Novel-Metadaten. |
| **Project Import** | IO-002 | DOCX/Markdown/TXT Import → AI analysiert Struktur → schlägt Chapters, Volumes, KB-Einträge vor. Nutzt EntityExtractionAgent. Interaktiver Bestätigungs-Flow. |
| **Story Chat** | ASSIST-003 | Chat-Interface für Fragen zum eigenen Projekt. "Which chapters mention the forest?", "Summarize Elena's arc", "Find continuity errors". RAG über KB + Chapter-Summaries. |

**Technische Kerne:**
- IO-001: `python-docx` für DOCX, `weasyprint` für PDF, `ebooklib` für ePub
- IO-002: `python-docx` / `markdown` Parser → `ImportAnalysisAgent` → Struktur-Vorschlag → User-Bestätigung → Batch-Create
- ASSIST-003: Neuer Chat-Endpoint, RAG mit pgvector-Ähnlichkeitssuche über KB + Summaries, Context-Window-Management

**Dependencies:** IO-002 braucht KB-007 (Entity Extraction) für beste Ergebnisse.

---

### Post-MVP Phase 4: "Platform & Integrations"

*Schwerpunkt: Narrare als Platform. MCP. A2A. Analytics.*

| Feature | ID | Kernpunkte |
|---------|-----|-----------|
| **MCP Server** | Q-001 | Geplanter Model-Context-Protocol-Adapter. Externe AI-Clients sollen Narrare-Services als Tools aufrufen können; Auth-Strategie bleibt offen. |
| **A2A Protocol** | Q-002 | Geplanter Agent-to-Agent-Adapter. Andere Agents sollen Schreib-Aufgaben an Narrare delegieren können; Streaming-Anforderung bleibt offen. |
| **Embedding Abstraction** | Q-003 | Einheitliches Embedding-Interface in `core/llm/embeddings.py`. Aktuell: OpenAI + sentence-transformers ad-hoc. Ziel: Provider-Interface wie LLM-Gateway. |
| **Writing Statistics** | STATS-001 | Zeitreihen-Analyse: Wörter/Tag, aktive Schreibzeiten, Kapitel-Fortschritt. Dashboard mit Charts. Persistenz in neuer `writing_sessions`-Tabelle. |
| **Cost Tracking** | STATS-002 | Pro-Request Token-Tracking (bereits teilweise via Langfuse). UI-Dashboard mit Kosten pro Tag/Woche/Monat. Budget-Warnungen. |

**Technische Kerne:**
- MCP: Geplanter `apps/mcp/` Adapter, der bestehende Service-Protokolle aufruft. Q-001 entscheidet die Auth-Strategie vor Implementierung.
- A2A: Geplanter `apps/a2a/` Adapter. RULE-12 stellt sicher: nur Service-Calls, keine neue Logik. Q-002 entscheidet Streaming vor Implementierung.
- Q-003: `EmbeddingProvider` Protocol + `EmbeddingRegistry`. Cascade wird zur Registry-Methode.
- STATS-001: `writing_sessions` Tabelle (start_time, end_time, words_written, chapter_id). Cron-Job aggregiert täglich.
- STATS-002: Langfuse-Daten → `ai_costs` Tabelle → Analytics-Endpoint → Frontend-Dashboard.

**Dependencies:** Keine harten Abhängigkeiten. Kann parallel zu allen anderen Phasen laufen.

---

### Architektur-Entscheidungen für Post-MVP

| Entscheidung | Status | Begründung |
|-------------|--------|-----------|
| Neue Agents folgen NarrareAgent-Pattern | ✅ Festgelegt | BetaReaderAgent, VoiceProfiler, EntityExtractionAgent — alle als NarrareAgent-Subklassen |
| MCP/A2A als Service-Clients | ✅ Festgelegt | RULE-12: Nur Service-Calls, keine neue Logik in Adaptern |
| IO-Export via Templates | ✅ Festgelegt | Jinja2-Templates für Formatierung, leicht anpassbar |
| Inline-Suggestions via TipTap Decorations | ✅ Festgelegt | Keine Content-Mutation, nur visuelle Overlays |
| RAG für Chat via pgvector | ✅ Festgelegt | Bestehende pgvector-Infrastruktur, keine neue DB |

### Offene Architektur-Fragen (Post-MVP)

| ID | Frage | Empfehlung | Blockiert |
|----|-------|-----------|-----------|
| Q-001 | MCP Auth-Strategie | Offen — Adapter-Spec vor Implementierung erforderlich | apps/mcp/ |
| Q-002 | A2A Streaming | Offen — Adapter-Spec vor Implementierung erforderlich | apps/a2a/ |
| Q-003 | Embedding-Abstraktion | Provider-Interface wie LLM-Gateway | core/llm/embeddings.py |
| Q-NEW | Inline-Suggestion Latenz | Prefix-Caching + kompakte Prompt-Templates? Mini-Modell? | WRITE-007 |
| Q-NEW | Multi-Agent Chat Memory | Kontext-Window für Chat: wie viele KB-Einträge? Reranking? | ASSIST-003 |

---

## Architecture Decisions Pre-Made for MVP

These decisions are made now so the MVP doesn't need to revisit them:

### Editor: ProseMirror via TipTap
TipTap wraps ProseMirror with a React-friendly API. Extensible via custom extensions.
The AI feature slots (toolbar, context panel, inline decorations) are TipTap extensions.

### Frontend State
- Server state: TanStack Query v5
- Client state: Zustand v5
- Forms: React Hook Form v7

### i18n
next-intl. Messages in `packages/web/messages/{locale}.json`.
All user-facing strings use `useTranslations()`. Zero hardcoded English in components.

### Auth
JWT (access + refresh token). Access token in memory (not localStorage).
Refresh token in httpOnly cookie. Standard, secure, extensible.

### Autosave
Debounced on editor content change. Configurable interval via project settings.
Optimistic update in UI, confirmed by server response.

---

## What "No Stubs" Actually Means

For every API endpoint in the MVP:
- Has a real service implementation (not `return {"todo": "implement"}`)
- Has input validation (Pydantic models, real errors)
- Has auth checking where required
- Has at least one integration test

For every UI component:
- Has real data (not hardcoded mock data except for Storybook)
- Has loading state
- Has error state
- Has i18n strings (not hardcoded English)

For the editor specifically:
- Autosave actually saves to the database
- Word count is actually computed from content
- Chapter switching actually loads the correct chapter content

---

## pyproject.toml Key Configuration

```toml
[project]
requires-python = ">=3.14"

[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
reportMissingImports = true
reportMissingTypeStubs = false  # Some stubs not yet available for 3.14

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "TCH"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.coverage.run]
source = ["apps", "packages"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.narrare.architecture]
llm_allowed_modules = ["core/llm/gateway.py", "core/llm/embeddings.py"]
prompt_allowed_modules = ["core/prompts/"]
forbidden_llm_imports = ["openai", "anthropic", "pydantic_ai"]
forbidden_llm_urls = ["api.openai.com", "api.anthropic.com"]
file_size_limits = {router = 150, service = 300, repository = 250, default = 400}
```

---

## Open Questions Blocking MVP

See `docs/architecture/questions/Q-005-resolved.md`

The Z.AI/GLM provider adapter must be confirmed working before Phase 1 is complete.
All other providers (OpenAI, Anthropic) are unblocked and can proceed in parallel.

---

> Last updated: 2026-05-22 — Phase 5 COMPLETE. Phase 6 (WRITE-003/004) IN PROGRESS. Post-MVP roadmap added.
> Owner: Architecture Agent + Dev Coordinator
> This plan changes only via Architecture session + ADR entry
