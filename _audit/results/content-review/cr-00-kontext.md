# Content Review 00 – Projekt-Kontext (AI-Inhalt)

> **Hinweis:** Diese Datei ist der Ausgangspunkt für alle Content-Reviews (CR-01–CR-08).
> Sie ergänzt `_audit/results/technical-review/review-00-kontext.md` um
> inhaltliche Aspekte.
>
> **Erstellt:** 2026-07-11 (Content Review Audit)
> **Methode:** `code-review-graph` MCP Tools + Read/Glob/Grep Fallback. Alle Einträge
> gegen echten Code verifiziert (nicht aus Annahmen). `prompt-inventory.yaml` als
> Referenz genutzt, aber Diskrepanzen gegen tatsächliche Dateien dokumentiert.

---

## 1. Prompt-Inventar

> Verifiziert via Glob über `packages/core/narrare_core/prompts/_bundled/**/*.md`
> und `ls` der Kategorie-Verzeichnisse. Das `prompt-inventory.yaml` (Stand
> 2026-06-01) wurde als Referenz genutzt, weist jedoch **erhebliche Drift** zur
> Realität auf (siehe Diskrepanz-Hinweise unten).

### System-Prompts (inline im Code)

**Ergebnis: 0 echte inline System-Prompts.** ADR-054 hat die
`INLINE-FEATURE-PROMPT`-Baseline auf 0 gebracht (3 Services → PromptComposer
Mode 1 migriert: `CharacterArcService`, `TimelineExtractionService`,
`KBMergeService`). Der Checker `scripts/architecture/_checkers/_check_inline_feature_prompt.py`
erzwingt dies CI-blockierend.

Die einzigen `system_prompt=`-Vorkommen im Code (via Grep `system_prompt\s*=\s*["']`
gefunden) sind alle leer oder in Docstrings:

| Datei | Zeile | Wert | Bewertung |
|---|---|---|---|
| `agents/kb_agent.py` | 64 | `system_prompt=""` | Leer — Tool-only Agent (kein Prompt-Inhalt) |
| `agents/registry.py` | 60, 64 | `system_prompt="..."` | Docstring-Beispiel, kein Code |
| `prompts/preview.py` | 98 | `system_prompt=""` | Leer — PROMPT-003 Preview (absichtlich provider-frei) |

**Fazit:** Keine inline System-Prompts mit echtem Prompt-Inhalt. ✅ Konsistent mit RULE-02/02b.

### System-Prompts (als Dateien)

**58 `system.md`-Dateien** gesamt in `packages/core/narrare_core/prompts/_bundled/`.

| Kategorie | Sprachen | Modi | Anzahl system.md | Bemerkung |
|---|---|---|---|---|
| `meta` | en, de, fr (deklariert lokalisiert) | `system` | 3 | v3.0.0 — NarrareMeta Capability |
| `universal` | en, de, fr (deklariert lokalisiert) | `system` | 3 | v1.0.0 — NarrareUniversalRules Capability |
| `writing` | en (10 Modi), de (6 Modi), fr (6 Modi) | new_chapter, extend_chapter, rewrite_selection, co_author, scene_by_scene, interactive_session, story_suggest, inline_suggest, interview, chat | 22 | EN-only-Standard (ADR-026 Phase 5); de/fr sind Legacy/Teilbestand |
| `kb` | **en only** | consistency, enhance, extract, improve, interview, merge, suggest, worldbuilding (phase1, phase2) | 9 | EN-only per Standard |
| `analysis` | **en only** | beta_reader, beta_reader_deepdive, consistency, review, preferences, remap, summarize, character_voice, coreference, fact_extraction, pov, readability, voice_check | 13 | EN-only per Standard |
| `planning` | **en only** | outline, timeline, character_arc, temporal_consistency, timeline_extraction | 5 | EN-only per Standard |
| `generation` | **en only** | names | 1 | EN-only per Standard |
| `wiki` | **en only** | chapter_summary, entity_summary | 2 | EN-only per Standard |

**Zusätzlich 18 Nicht-Template-Content-Dateien:**
- `writing/tones/`: 9 Ton-Dateien (balanced, adventurous, quiet, dramatic, humorous, contemplative, suspenseful, romantic, dark)
- `generation/name-styles/`: 9 Namensstil-Dateien (en/de/fr × fantasy/modern/scifi) — Sprach-neutrale Referenz-Dateien, keine Prompt-Templates

> ⚠️ **Drift: `prompt-inventory.yaml` vs. Realität (Stand 2026-07-11)**
>
> Das Inventory (zuletzt aktualisiert 2026-06-01) ist **signifikant veraltet**.
> Nachfolgende Reviews sollten sich auf Dateisystem-Scans verlassen, nicht auf
> das Inventory-YAML:
>
> 1. **Phantom de/fr-Dateien:** Inventory behauptet de/fr-Varianten für `analysis`,
>    `kb`, `planning`, `wiki` — **keine dieser Verzeichnisse existiert**. Nur
>    `meta`, `universal` und teilweise `writing` haben de/fr.
> 2. **Fehlende Modi im Inventory:** `analysis` hat 13 Modi (Inventory listet 7),
>    `planning` hat 5 (Inventory listet 3). Neuere Modi fehlen: `character_voice`,
>    `coreference`, `fact_extraction`, `pov`, `readability`, `voice_check`
>    (analysis); `temporal_consistency`, `timeline_extraction` (planning).
> 3. **Writing de/fr unvollständig:** Inventory behauptet 10 Modi in de/fr — nur
>    6 existieren (`chat`, `co_author`, `inline_suggest`, `interview`,
>    `new_chapter`, `rewrite_selection`). Fehlend: `extend_chapter`,
>    `interactive_session`, `scene_by_scene`, `story_suggest`.
> 4. **`chat`-Kategorie verschoben:** Inventory hat separate `chat`-Kategorie mit
>    Pfad `chat/en/system.md` — aber `_bundled/chat/` existiert nicht. Chat lebt
>    bei `writing/{lang}/chat/system.md` (ADR-049 Phase C hat CHAT zu
>    `writing/chat` zurückmigriert; separates `_bundled/chat/` wurde gelöscht).
> 5. **`meta/en/system.lite.md`:** Inventory erwähnt eine Lite-Variante — Datei
>    existiert nicht.

### Default User-Prompts (Templates)

Default User-Prompts werden über die `## First Message`-Sektion in den
`system.md`-Dateien definiert. Diese werden vom `PromptComposer` via
`ResolvedPrompt.first_message` extrahiert (`registry.py:261`) und als
`ComposedPrompt.user` zurückgegeben, wenn kein explizites `user_prompt` übergeben
wird (`composer.py:161-168`).

Interaktive Modi mit `First Message`-Sektionen (die eine initiale AI-Nachricht
generieren): `interactive_session`, `interview` (writing + kb),
`scene_by_scene`. Nicht-interaktive Modi (new_chapter, extend_chapter, etc.)
nutzen `author_instructions` als User-Input (`composer.py:170`).

| Kategorie | Modi mit First Message | Sprachen |
|---|---|---|
| writing | interactive_session, interview, scene_by_scene | en |
| kb | interview | en |

---

## 2. Globale Prompt-Identität / Capabilities

**Ja — es existiert eine architektonisch garantierte Prompt-Identität.**

ADR-026 (Capability-Based Prompt Injection Pattern, ✅ Implemented) etabliert
ein dreischichtiges System: garantierte Capabilities (nicht übersteuerbar) +
anpassbare Cascade-Prompts + dynamische Variablen. Jeder `NarrareAgent`
(`agents/base.py:127-132`) injiziert automatisch drei Standard-Capabilities:

```python
capabilities=[
    NarrareObservability(),    # immer
    NarrareUniversalRules(),   # immer — ADR-026 Phase 1
    NarrareMeta(),             # immer — ADR-026 Phase 3
    *(capabilities or []),
]
```

Diese Capabilities **können nicht** durch Template-Overrides oder Cascade-Konfiguration
übergangen werden (`universal_rules.py:1-4`: "These rules CANNOT be overridden by
templates or cascade — they are always present.").

**ADR-026-Status:**

| Inhaltstyp | Erwarteter Mechanismus | Implementiert? | Quelle |
|---|---|---|---|
| Garantierte Universal Rules | `NarrareUniversalRules` Capability | ✅ Ja | `agents/capabilities/universal_rules.py` (L97) → `_bundled/universal/{en,de,fr}/system.md` (v1.0.0). Lädt synchron in `__post_init__`, Language-Resolution via `for_run(ctx)` mit EN-Fallback. Inhalt: Fiction-Richtlinien, Outline > KB Konfliktlösung, Author-Instructions > Preferences, Injection-Defense (XML-getaggter Content = Data-only). |
| Meta-Persona / Narrare-Identität | `NarrareMeta` Capability | ✅ Ja | `agents/capabilities/meta.py` (L85) → `_bundled/meta/{en,de,fr}/system.md` (v3.0.0). Identity ("You are Narrare"), Role Flexibility, Conversation Guardrails, Variablen-Substitution (`author_name`, `genre`, `project_title`, `tone`, `story_structure`, `writing_language`, `avoidance_patterns`). |
| Anpassbare Feature-Instruktionen | PromptComposer / Cascade | ✅ Ja | `prompts/composer.py` (L43) + `prompts/registry.py` (L37) — 5-Level-Cascade (DB → Project → User-global → Bundled → EN-Fallback). Route-Auflösung via `prompts/routes.py` (`resolve_prompt_route`). |
| Dynamische Daten (KB, Style, Voice) | PromptContext / Variablen | ✅ Ja | `prompts/context.py` (PromptContext), `prompts/variable_engine.py` (`prepare_variables_for_template`, `substitute`), `prompts/variable_registry.py` (`USER_CONTENT_VARS`, `SYSTEM_VARS`, `VARIABLE_ALIASES`), ADR-037 Prompt Surface Contract Manifest. KB-Context über `KBContextEnvelope`-Protocol (ADR-050). |

**Zusätzliche Capabilities:**
- `NarrareObservability` (`agents/capabilities/observability.py`) — Metriken &
  Logging (immer injiziert)
- `PromptDeps` / `PromptContextDeps` Protocols (`agents/capabilities/contracts.py`)
  — MINIMUM-Interface für Deps-Typen (`language`-Property + optionale
  `writing_language`/`genre`)

---

## 3. KB-Context-Formate im Überblick

KB-Context wird an mehreren Stellen formatiert. Das `KBContextEnvelope`-Protocol
(`context/_kb_envelope.py`, ADR-050 P1-A) ist der verbindliche Render-Contract:
jeder Render-Pfad MUSS Provenienz (source, evidence, confidence, review_status)
erhalten oder explizit mit `OmissionReason` weglassen — stillschweigender Verlust
ist eine RULE-22-Verletzung.

| Format-Name | Erzeugt in | Struktur | Genutzt von |
|---|---|---|---|
| Standard-Entity-Format | `writing/_helpers.py:format_entities()` | `### Type: Name\nContent` (zeilenweise) | Tier-3 Referenced, Tier-4 Suggested, Tier-5 Pinned |
| Wiki-komprimiert | `writing/context_wiki.py:format_entities_with_wiki()` / `writing/_tier3_processor.py:apply_tier3()` | `### Type: Name\nNarrativeSummary` (Wiki-compressed statt voller Entry) | Tier-3 bei verfügbaren WikiSummaries (ADR-022) |
| Proactive Suggestion | `context/proactive_service.py:ProactiveContextService._build_candidates()` | Hybrid-Scoring (semantisch + strukturell) → formatierte Entity-Liste | KB-005 Proactive Context |
| PromptContext-KB | `prompts/context.py:PromptContext._format_kb_entries()` | KB-Entries als formatierter String für Prompt-Variable | KB-/Writing-Services via PromptComposer |
| Voice Profiles | `writing/_voice_profiles.py:extract_voice_profiles()` | Character-Sprachmuster formatiert als `character_voice_profiles`-Variable | Writing-Features mit Dialog (ADR-055) |
| Timeline Event Envelope | `analysis/timeline_envelope.py` | Strukturierte `TimelineEventEnvelope`-Typen (ADR-044) | Consistency-Pipeline (FIND-009a) |
| KBContextEnvelope (Protocol) | `context/_kb_envelope.py` | `RenderedKBContext(text, preserved_fields, omitted_fields, entry_count, render_path)` | Vertrag für ALLE Render-Pfade; Implementationen in obigen Modulen |

**Kontext-Tiers (Writing Context Assembler — `writing/context_assembler.py`,
`context/budget.py:TokenBudgetManager`):**

| Tier | Name | Immer dabei? | Inhalt | Budget-Anteil |
|---|---|---|---|---|
| 1 | Immediate | Ja (Kapitel-Content ist Kern-Input) | Aktuelles Kapitel: Content, Frontmatter, Chapter-Outline | 30% (Default) |
| 2 | Recent | Ja (wenn vorhanden) | Letzte N Kapitel als komprimierter Kontext | 20% (0% bei erstem Kapitel) |
| 3 | KB Referenced | Ja (wenn referenzierte Entities existieren) | Referenzierte + verbundene KB-Entities, getrennt nach Typ (characters, locations, factions, systems, timelines); Wiki-komprimiert wenn verfügbar | 25% |
| 4 | KB Suggested | Nein (optional) | Proactive/semantisch vorgeschlagene KB-Entities (unedorsed Kandidaten) | 15% |
| 5 | Pinned | Ja (Bypass — immer inkludiert, auch wenn Budget erschöpft) | Vom Autor angepinnte KB-Entities | 10% (wird bei Overflow nicht gekürzt) |

> **Overflow-Verhalten:** Nicht verbrauchtes Budget fließt in den nächsten Tier
> (`context_assembler.py:190-229`). Tier 5 (Pinned) ist ein Budget-Bypass —
> immer inkludiert, auch wenn vorherige Tiers das Budget überschreiten.

---

## 4. mem0-Nutzung im Überblick

mem0 (`mem0ai` v2.0.11, ADR-033) ist der Memory-Layer für Preference-Learning
und Feedback-Speicherung. Implementiert als OSS `AsyncMemory` mit pgvector
Backend. Konfiniert auf `core/memory/` (RULE-08).

| Feature | mem0-Nutzung | Art der Nutzung |
|---|---|---|
| **Feedback Collection** (LEARN-001) | `memory/feedback_service.py:FeedbackService` | `mem0.add()` — Übersetzt `FeedbackEvent` in natürlichsprachlichen Text, forwardet best-effort an mem0 für semantische Preference-Extraction. DB-Persist immer, mem0-Forward bei Fehlern nur Warning (graceful degradation). |
| **Preference Derivation** (LEARN-001) | `memory/preference_service.py:PreferenceService` | `mem0.search()` — Intent-spezifische Queries extrahieren Preference-Dimensionen (Satzlänge, Ton, Wortschatz, Perspektive, Pacing, Dialog-Stil, Beschreibungsdichte, Genre-Konventionen). Aggregiert zu `PreferenceProfile`. Leeres Profile bei mem0-Ausfall. |
| **Preference Injection** (in Prompts) | `prompts/composer.py:PromptComposer.build()` (L93-113) | Wenn `preference_service` konfiguriert und Context leer: ruft `PreferenceService.get_preferences(user_id, project_id)` auf, injiziert als `user_preferences`-Variable in den Prompt. Best-effort mit Warning bei Fehlern. |

**mem0-Konfiguration (`memory/mem0_client.py`):**

- **Client-Factory:** `create_memory_client()` (async) / `create_memory_client_sync()`
  (sync für DI-Init) — einziges Modul, das `from mem0 import AsyncMemory` ausführt
- **NullMemoryClient** (`memory/_null_client.py`): No-op-Fallback bei
  mem0-Verfügbarkeit (gleiche API-Signatur wie `AsyncMemory` 2.0.x)
- **Memory-Modelle** (`_PROVIDER_DEFAULT_MODELS`, ADR-064): Klein/günstig pro Provider:
  - anthropic: `claude-haiku-4-20250414`
  - openai: `gpt-4.1-nano`
  - ollama: `llama3.2:3b`
  - zai: `glm-4-flash`
  - Fallback: `gpt-4.1-nano`
- **Embedding-Cascade** (`memory/embedding_cascade.py:EmbeddingCascadeResolver`):
  - Tier 1: OpenAI `text-embedding-3-small` (wenn OpenAI-Key vorhanden)
  - Tier 2: Provider-native Embeddings (future hook — nicht implementiert)
  - Tier 3: Lokal `sentence-transformers` `all-MiniLM-L6-v2` via HuggingFace-Provider
  - Tier 4: Disabled → `NullMemoryClient` (kein Memory)
- **Vector Store:** pgvector (`vector_store.provider = "pgvector"`, `db_url`)
- **Custom Extraction Prompts:** Sprachspezifisch (`_WRITING_PREFERENCE_PROMPTS`)
  in en/de/fr — sagen mem0's Extraktions-LLM, worauf zu fokussieren ist
  (Satzlängen, Ton, Wortschatz, etc.)
- **Memory Client Cache:** `memory/memory_client_cache.py` — LRU-Cache für
  `AsyncMemory`-Instanzen pro User
- **ADR-064 Scope-Boundary:** mem0-Konfigurationsstrings tragen
  `# narrare: allow-prompt-path reason="mem0 config string, not Narrare prompt path"`
  Annotationen — sie sind KEINE Narrare-Prompts im Sinne von RULE-02b, sondern
  Third-Party-Bibliotheks-Konfiguration.

**Graceful Degradation:** Mem0 ist vollständig optional. Bei fehlendem Package,
fehlenden Embeddings, oder Erstellungs-Fehlern läuft das System ohne Memory
weiter (`NullMemoryClient`).

---

## 5. WebUI-Prompt-Anpassbarkeit

**System vorhanden: Ja — PROMPT-003 (Prompt Customization UX), ✅ Implemented, Status `stable` (2026-06-22).**

PROMPT-003 bietet Provider-freie Preview, Provider-gated Live-Test,
Reset-to-Default, Variablen-Metadaten/Provenance und Diagnostik.

**Architektur:**
- **Frontend:** Settings-Seite mit Prompt-Editing-UI. Prompt-Historie
  (DB-gestützt, append-only: list/compare/restore/clear via CR-AUFG-07-19).
  Slash-Command Discovery-Layer (CR-AUFG-07-20).
- **API:** `apps/api/narrare/prompts/router_prompt_ux.py` — Endpoints:
  - `POST /prompts/{prompt_id}/preview` — Provider-freie Vorschau
  - `POST /prompts/{prompt_id}/live-test` (SSE) — Provider-gated Live-Test
  - `POST /prompts/{prompt_id}/reset` — Reset auf Bundled-Default
  - `GET /prompts/{prompt_id}/variables` — Variablen-Metadaten
- **Service:** `apps/api/narrare/prompts/preview_service.py`
  (`PromptPreviewApiService` — API-Layer-Adapter für Core-Preview),
  `live_test_service.py` (`PromptLiveTestApiService` — SSE-Streaming mit echtem
  Provider via `PromptLiveTestAgent`)
- **Core:** `prompts/preview.py:PromptPreviewService` — Provider-freie
  Prompt-Auflösung via `PromptComposer` + `PromptRegistry`. Liefert
  `PromptPreview` mit resolved-system, resolved-user, Variablen-Metadaten und
  Diagnostics. Ruft **niemals** einen LLM auf, instantiiert keinen Agent,
  importiert keine Provider-SDKs.
- **CLI:** Nicht implementiert (keine dedizierte Narrare-CLI; PROMPT-003 ist
  WebUI-exklusiv)
- **MCP:** Nicht implementiert (ADAPTER-001 geplant, blockiert durch Q-001)
- **A2A:** Nicht implementiert (ADAPTER-002 geplant, blockiert durch Q-002)

**Kaskaden-System (CSS-artig, 5-Level — `prompts/registry.py:7-12, 144-183`):**

1. **DB-Template** (höchste Priorität): User-saved Override via
   `UserPromptTemplateService` — wird von Service-Layer als `db_content` an
   `PromptComposer.build()` übergeben. `source="db"`.
2. **Project-Level**: `{project_root}/.narrare/prompts/{category}/{language}/{mode}/system.md`
   (inkl. Genre-spezifisch: `system_{genre}.md`). `source="project"` /
   `"project_genre"`.
3. **User-Global**: `~/.config/narrare/prompts/{category}/{language}/{mode}/system.md`
   (inkl. Genre-spezifisch). `source="user"` / `"user_genre"`.
4. **Bundled Default**: `narrare_core/prompts/_bundled/{category}/{language}/{mode}/system.md`
   (inkl. Genre-spezifisch). `source="bundled"` / `"bundled_genre"`.
5. **Bundled EN-Fallback** (nur wenn language ≠ "en"):
   `_bundled/{category}/en/{mode}/system.md`. `source="bundled_en"` /
   `"bundled_en_genre"`.

Jede Stufe kann durch ein Genre-spezifisches `system_{genre}.md` überschrieben
werden (wird VOR dem generischen `system.md` in derselben Stufe geprüft).

**Anpassbare Prompts:** Alle Feature-Prompts der Kategorien `writing`, `kb`,
`analysis`, `planning`, `generation`, `wiki` sind über die Cascade anpassbar
(DB → Project → User-global → Bundled → EN-Fallback). Jede Ebene kann den
Template-Inhalt überschreiben, Variablen-Substitution erfolgt immer durch den
Composer.

**Nicht anpassbare Prompts (architektonisch garantiert):**
- **`NarrareUniversalRules`** — garantiert für jeden Agent, lädt aus
  `_bundled/universal/`, kann NICHT via Cascade übergangen werden
  (`universal_rules.py:1-4`)
- **`NarrareMeta`** — garantiert für jeden Agent, lädt aus `_bundled/meta/`,
  auto-injiziert, nicht via Cascade überschreibbar
- **`NarrareObservability`** — Metriken/Logging, kein Prompt-Inhalt

> **Hinweis:** Die Capability-Dateien (`_bundled/meta/`, `_bundled/universal/`)
> können nicht via PROMPT-003 WebUI angepasst werden — sie sind Teil der
> Core-Architektur, nicht der Cascade.

**Locale-Strategie:**
- **Feature-Templates:** EN-only per ADR-026 Phase 5 / RULE-22 §5
  (`prompt-standards.md` §5: "Bundled feature system prompts are EN-only by
  default"). Ausgabe-Sprache wird über `{{writing_language}}`-Variable gesteuert,
  nicht durch Template-Duplikation. **Ausnahme-Legacy:** `writing/de/` und
  `writing/fr/` haben jeweils 6 Modi (chat, co_author, inline_suggest, interview,
  new_chapter, rewrite_selection) als ältere lokalisierte Templates. Diese sind
  nicht mit dem EN-only-Standard konsistent und sollten migriert oder entfernt
  werden (CR-Potenzial).
- **Meta/Universal Rules:** Mehrsprachig (en/de/fr) als deklarierte lokalisierte
  Familie — alle 3 Locales vorhanden, Versions-Parität erforderlich
  (`prompt-standards.md` §5: "all declared locale variants at the same version
  number"). meta: v3.0.0 in allen Locales ✓; universal: v1.0.0 in allen Locales ✓.
  Register: DE = Du, FR = tu (per `prompt-content-standards.md` §8 — Q-013 gelöst).
- **Ausgabe-Sprache:** Über `{{writing_language}}` (kanonisch) gesteuert —
  wird vom `PromptContext.writing_language` gesetzt, kann von UI-Sprache
  abweichen (z.B. language='en' UI aber writing_language='de' für deutschen
  Roman). `{{language}}` ist deprecated und nicht in bundled system prompts
  erlaubt (`variable_registry.VARIABLE_ALIASES`).

---

## 6. Bekannte inhaltliche Probleme (Vorbelastung)

> Quelle: `docs/_shared/CURRENT_STATE.md` (Known Risks, Follow-up Debt),
> `docs/architecture/questions/INDEX.md`, manuelle Code-Verifikation.
> Nur real existierende Einträge — nichts erfunden.

| ID / Thema | Problem | Status | Content-Relevanz |
|---|---|---|---|
| **prompt-inventory.yaml Drift** | Inventory (2026-06-01) weicht massiv von Realität ab: Phantom de/fr-Dateien für analysis/kb/planning/wiki; fehlende Modi (character_voice, coreference, voice_check, etc.); verschobene chat-Kategorie; unvollständige writing de/fr. | Offen (Dokumentations-Dienst) | Hoch — nachfolgende CRs könnten auf falsche Daten vertrauen. **Aktion:** Inventory regenerieren oder als deprecated markieren. |
| **Writing de/fr Legacy-Templates** | 6 writing-Modi existieren in de/fr (chat, co_author, inline_suggest, interview, new_chapter, rewrite_selection), obwohl ADR-026 Phase 5 EN-only für Feature-Prompts vorschreibt. Weder vollständig (4 Modi fehlen) noch konsistent mit Standard. | Offen (Legacy-Dienst) | Mittel — Content-Drift-Risiko zwischen EN und de/fr. CR-01/02 sollten Parität/Qualität prüfen oder Migration empfehlen. |
| **Graph-MCP-Verfügbarkeit** | `code-review-graph` MCP zeitweise nicht verfügbar; semantische Suche nach Capability-Klassen ("NarrareUniversalRules", "NarrareMeta") liefert 0 Treffer trotz existierender Implementierung. Entry-Points unter nativen Queries nicht auffindbar. | Known Risk (CURRENT_STATE) | Mittel — Reviews müssen auf Read/Glob/Grep zurückfallen, verlieren strukturellen Kontext. |
| **ADR-Status-Diskrepanz** | `decisions/INDEX.md` markiert ADR-047, ADR-061, ADR-062 mit ⛔ (Superseded), während teils andere Status genannt werden. | Offen (SSOT-Inkonsistenz) | Niedrig für Content — mittel für Architecture. |
| **Strategische Deferrals** | SET-006 (Project Writing Profile) bewusst außer Scope — würde globale Schreibprofil-Variable einführen, die in Meta/Capability injiziert werden könnte. CONS-003/KB-011/WRITE-013 (Multi-Step-Workflows) deferred. | Deferred (dokumentiert) | Niedrig für aktuelle CR — relevant wenn SET-006 angegangen wird. |
| **ADR-039 Lücke** | INDEX springt ADR-038 → ADR-040 (kein ADR-039 vorhanden) | Offen (Dokumentations-Lücke) | Niedrig |
| **Worldbuilding Phase 2 Prompt** | `prompt-content-standards.md` (L224) bewertet als ⭐⭐⭐ "Weak": fehlt formales Output-Schema, Do-NOT-Sektion, CoT, Confidence-Thresholds. | Bekannt (Content-Standards) | Hoch für CR-03 (KB-Content) — sollte remediiert werden. |
| **Q-001 / Q-002** | MCP-Auth-Strategie / A2A-Streaming blockieren ADAPTER-001/002. WebUI ist derzeit einziger Client für PROMPT-003. | 🟡 Open | Niedrig für Content — PROMPT-003 bleibt WebUI-exklusiv bis Adapter gebaut. |
| **Q-011** | Distributions-Strategie für nicht-technische Nutzer unklar. | 🟡 Open | Niedrig für Content |

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

## Anhang — Verifizierte Datei-Pfade (für nachfolgende CRs)

| Element | Pfad |
|---|---|
| Capability-Verträge | `packages/core/narrare_core/agents/capabilities/contracts.py` |
| NarrareUniversalRules | `packages/core/narrare_core/agents/capabilities/universal_rules.py` |
| NarrareMeta | `packages/core/narrare_core/agents/capabilities/meta.py` |
| NarrareObservability | `packages/core/narrare_core/agents/capabilities/observability.py` |
| Agent-Basis (Capability-Injection) | `packages/core/narrare_core/agents/base.py` |
| PromptComposer | `packages/core/narrare_core/prompts/composer.py` |
| PromptRegistry (Cascade) | `packages/core/narrare_core/prompts/registry.py` |
| PromptContext | `packages/core/narrare_core/prompts/context.py` |
| Variable Engine | `packages/core/narrare_core/prompts/variable_engine.py` |
| Variable Registry | `packages/core/narrare_core/prompts/variable_registry.py` |
| Prompt Preview (PROMPT-003) | `packages/core/narrare_core/prompts/preview.py` |
| Route Resolution | `packages/core/narrare_core/prompts/routes.py` |
| KBContextEnvelope-Protocol | `packages/core/narrare_core/context/_kb_envelope.py` |
| TokenBudgetManager (Tiers) | `packages/core/narrare_core/context/budget.py` |
| Writing Context Assembler | `packages/core/narrare_core/writing/context_assembler.py` |
| Tier-3 Processor | `packages/core/narrare_core/writing/_tier3_processor.py` |
| mem0 Client Factory | `packages/core/narrare_core/memory/mem0_client.py` |
| NullMemoryClient | `packages/core/narrare_core/memory/_null_client.py` |
| FeedbackService | `packages/core/narrare_core/memory/feedback_service.py` |
| PreferenceService | `packages/core/narrare_core/memory/preference_service.py` |
| Bundled Prompts Root | `packages/core/narrare_core/prompts/_bundled/` |
| Prompt Content Standards | `docs/development/prompt-content-standards.md` |
| Prompt Standards | `docs/development/prompt-standards.md` |
| INLINE-FEATURE-PROMPT Checker | `scripts/architecture/_checkers/_check_inline_feature_prompt.py` |
