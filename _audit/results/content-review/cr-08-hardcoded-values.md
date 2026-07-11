# Content Review CR-08 – Hardcodierte Werte & Konfigurierbarkeit

> **Review-Datum:** 2026-07-11
> **Reviewer:** Core Specialist (Content Review Audit)
> **Methode:** `code-review-graph` MCP Tools (Graph: 27.434 Knoten, 0 Embeddings →
> Keyword-Suche) + Read/Grep Fallback. Alle Einträge gegen echten Code verifiziert
> (Datei:Zeile), nicht aus Annahmen.
> **Kontext:** `_audit/results/content-review/cr-00-kontext.md`
> **Vorheriger CR-08-Remediation-Stand:** `docs/features/remediation/cr-08-configuration-effect-drift.md`
> (markiert "resolved — P0–P4 complete", ADR-051 → siehe §6 für Diskrepanz)

---

> ⚠️ **Wichtiger Vorab-Befund — CR-AUFG-08-14 Strukturpflicht nicht erfüllbar**
>
> Diese Review kann die **CR-AUFG-08-14 Strukturpflicht** (Matrix-Klassifikation für
> jeden P0/P1 `configuration-effect`-Wert) **nicht** erfüllen, weil das geforderte
> Enforcement-Toolchain-Target **nicht mehr existiert**:
>
> - `docs/architecture/governance/configuration-adoption-matrix.yaml` — **gelöscht**
>   (Commit `f8abb42c`, 815 Zeilen entfernt)
> - `scripts/check_configuration_matrix.py` — **gelöscht** (120 Zeilen; nur noch
>   stale `.pyc` in `scripts/__pycache__/`)
> - `scripts/governance/` (gesamtes Verzeichnis, ~60 Dateien) — **gelöscht**
> - `configuration-adoption-matrix.schema.json`, `matrix-effect-evidence.yaml`,
>   `status_vocabulary.yaml`, `aufg-registry.md` — alle **gelöscht**
>
> Siehe **FIND-014** (§6) für die vollständige Analyse. CONSTRAINTS.md RULE-18b
> referenziert diese Artefakte weiterhin als "CI-validated" (Zeile 601-609) —
> **stale**. P0/P1-Befunde in dieser Review werden mit dem Strukturmarker versehen,
> eine Matrix-Klassifikation ist jedoch erst nach Entscheidung über FIND-014 möglich.

---

## 1. Token- und Kontext-Limits

> Referenz: FIND-005, FIND-006 (vorherige CR-08-Runde), CR-AUFG-08-01/02.
> Token-Konstanten sind seit CR-08 P0/P1 weitgehend in `core/llm/token_profiles.py`
> zentralisiert (Single Source of Truth). Die meisten Werte sind gut kalibriert und
> über das Profile-System konfigurierbar.

### 1.1 Gefundene Token-Konstanten

| Konstante | Wert | Datei:Zeile | Feature-Scope | Konfigurierbar? | Sinnvoll kalibriert? |
|---|---|---|---|---|---|
| `PROFILE_OUTPUT_LIMITS[quick]` | 500 | `core/llm/token_profiles.py:49` | Global (Profile) | Ja (via Profile-Auswahl) | Ja |
| `PROFILE_OUTPUT_LIMITS[balanced]` | 2000 | `core/llm/token_profiles.py:50` | Global (Profile) | Ja | Ja |
| `PROFILE_OUTPUT_LIMITS[long_texts]` | 8000 | `core/llm/token_profiles.py:51` | Global (Profile) | Ja | Ja |
| `PROFILE_OUTPUT_LIMITS[comprehensive]` | 16000 | `core/llm/token_profiles.py:52` | Global (Profile) | Ja | Ja |
| `TOKEN_OUTPUT_ABSOLUTE_MAX` | 131072 | `core/llm/token_profiles.py:25` | Global (Hard Cap) | Nein (Code-Default) | Ja (größte Modell-Ausgabe) |
| `TOKEN_OUTPUT_UX_RECOMMENDED_MAX` | 16000 | `core/llm/token_profiles.py:28` | Global (UX-Slider) | Nein (Code-Default) | Ja (UX-Etikett, nicht API-Max) |
| `TOKEN_PROFILE_MINIMUM_OUTPUT_FLOORS` | 128/512/2048/4096 | `core/llm/token_profiles.py:56-61` | Suitability-Check | Nein (Code-Default) | Ja (Modell-Eignung) |
| `TOKEN_PROFILE_USAGE_LIMITS` (request/total) | 10/16k … 25/256k | `core/llm/token_profiles.py:73-94` | Run-Level | Ja (via Profile) | Ja |
| `SUGGEST_MAX_TOKENS` | 60 | `core/llm/run_limits.py:27` | Inline-Suggest (Feature) | Nein (immutable UX-Cap) | Ja (Low-Latency, ADR-045) |
| `DEFAULT_TOTAL_BUDGET` | 6000 | `core/context/budget.py:59` | Context-Assembly | Ja (Method-Param `total_budget`) | Ja |
| `_BASE_PERCENTAGES` (Tier-Split) | 30/20/25/15/10% | `core/context/budget.py:69-75` | Context-Assembly | Ja (`tier_overrides`-Param + Settings) | Ja |
| `_EXTEND_PERCENTAGES` | 50/15/20/10/5% | `core/context/budget.py:85-91` | Extend-Mode | Ja | Ja |
| `_REWRITE_PERCENTAGES` | 40/15/25/10/10% | `core/context/budget.py:93-99` | Rewrite-Mode | Ja | Ja |
| `ResolvedModelConfig.max_tokens` (Fallback) | 4096 | `core/llm/model_config.py:54` | Global (Fallback) | Ja (Settings-Cascade) | Ja (Fallback, nicht primär) |
| `ResolvedModelConfig.temperature` (Default) | 0.7 | `core/llm/model_config.py:53` | Global | Ja (Settings-Cascade) | Ja |
| `CacheSettings.ttl_seconds` | 300 | `core/llm/model_config.py:29` | Provider-Cache | Nein (Anthropic-Min: 300) | Ja (Provider-Constraint) |
| `CacheSettings.max_cache_points` | 4 | `core/llm/model_config.py:30` | Provider-Cache | Nein (Anthropic-Limit: 4) | Ja (Provider-Constraint) |

**Bewertung:** ⭐⭐⭐⭐⭐
Token-Konstanten sind vorbildlich organisiert: zentral in `token_profiles.py`,
über das Profile-System (`quick`/`balanced`/`long_texts`/`comprehensive`/`custom`)
für Nutzer zugänglich, mit harten Caps und Suitability-Floors als Code-Defaults.
Die vorherigen FIND-005/006-Probleme (Output-Limits nicht an Modellgrenze erzwungen,
Tier-Percentages nicht konsumiert) sind **implementiert**: `DefaultRunLimitResolver`
(`run_limits.py:52-93`) erzeugt `UsageLimits` + `model_settings["max_tokens"]` und
`ModelRegistry.run()`/`stream()` (`gateway.py:182-188, 256`) wendet diese an. Override
via `tier_overrides` ist verdrahtet (`apps/api/narrare/writing/deps_pipeline.py`,
Regressionstests `test_deps_tier_overrides.py`).

### 1.2 Feature-Output-Limits: Aufgaben-Check

> Orientierung: ~700 Wörter ≈ 1.000 Tokens.

| Funktion | Limit (Tokens) | Max sinnvoller Output | Ausreichend? | Handlungsbedarf |
|---|---|---|---|---|
| Inline Suggest | 60 (`SUGGEST_MAX_TOKENS`) | ~40 Wörter (1–2 Sätze) | Ja (knapp, intentional) | Keiner — Low-Latency-Ziel <500ms (ADR-045 D3 C) |
| Story Suggest | quick=500 | ~350 Wörter | Ja | Keiner |
| Co-Author (Rewrite) | balanced=2000 | ~1.400 Wörter | Ja | Keiner |
| Continue / Extend | long_texts=8000 | ~5.600 Wörter | Ja (volle Kapitel) | Keiner |
| New Chapter (Write) | long_texts=8000 | ~5.600 Wörter | Ja | Keiner |
| KB-Interview | quick=500 | ~350 Wörter | Ja (eine fokussierte Frage) | Keiner |
| Consistency Check | comprehensive=16000 | ~11.000 Wörter | Ja | Keiner |
| Beta-Reader | long_texts=8000 | ~5.600 Wörter | Ja | Keiner |
| Summarize | quick=500 | ~350 Wörter | Ja (Chapter-Summary) | Keiner |

**Fazit:** Alle Feature-Output-Limits sind für ihre Aufgabe ausreichend. Keine
Limit-bedingte Aufgabenunvollständigkeit erkennbar. `SUGGEST_MAX_TOKENS=60` ist der
engste Wert, aber intentional (Inline-Suggest = niedrigste Latenz).

### 1.3 Quartals-Modell-Abgleich

Modell-Limits stammen aus `models.dev`-Cache (`cost_rates.py`, `models_dev_source.py`).
Das Kalibrierungssystem (`model_calibration.py`) klassifiziert Status:
`known_fresh` / `known_stale` / `unknown_model` / `offline_no_cache` / `invalid_metadata`.
Provider-Caps werden zur Laufzeit angewendet (`run_limits.py:76-81`: cap to provider_max).

| Modell-Familie | Max Output (bekannt) | Im Code bekannt? | Ungenutztes Potenzial |
|---|---|---|---|
| Anthropic Claude (Sonnet/Opus) | 64.000 (via models.dev) | Ja (Cache, `known_fresh`) | Comprehensive=16k → ~48k ungenutzt (UX-Slider-Limit, intentional) |
| OpenAI GPT-4o/4.1 | 16.384 / 32.768 | Ja (Cache) | long_texts=8k → ~8-24k ungenutzt (UX-gesteuert, intentional) |
| Ollama (lokal) | Modellabhängig | `unknown_model` (kein models.dev) | Suitability=ADVISORY, keine Cap-Info |
| Google Gemini | 8.192 (variiert) | Ja (Cache) | Profile respektieren dies via Cap |
| Z.AI (GLM) | Modellabhängig | `unknown_model` | Suitability=ADVISORY |

**Neue Modelle seit letztem Review:** _Keine neuen Modelle im `models.dev`-Cache
identifiziert (Cache-Review nicht im Scope dieses Content-Reviews; Quartals-Check
empfohlen über `models.dev`-Source)._

**Bewertung:** ⭐⭐⭐⭐
`TOKEN_OUTPUT_ABSOLUTE_MAX=131072` deckt die größte bekannte Modell-Ausgabe ab.
UX-Empfehlung 16k ist bewusst konservativ (Slider-Range), Custom-Mode erlaubt bis
131.072. Das Kalibrierungssystem warnt bei `known_stale`/`unknown`/`offline`. Kein
ungenutztes Potenzial, das nicht bewusst UX-gesteuert eingeschränkt wäre.

**Befunde:** Keine neuen P0/P1-Befunde in §1. Token-Limits sind der am besten
governed Bereich des Codes.

---

## 2. Modell-Konfiguration

> RULE-18 wird durch `check_architecture.py` + Router-Contract-Tests erzwungen.
> Keine hardcodierten Modell-Namen in Routern oder Dependency-Factories gefunden.

### 2.1 Hardcodierte Modell-Referenzen

| Fundstelle | Modell-String | Zweck | Sollte konfigurierbar sein? |
|---|---|---|---|
| `core/memory/mem0_client.py:28-40` | `claude-haiku-4-20250414`, `gpt-4.1-nano`, `llama3.2:3b`, `glm-4-flash` | mem0-Extraktions-LLM pro Provider (ADR-064) | Bereits (via Settings-Mem0-Config; Scope-Boundary-Annotiert) |
| `core/llm/_providers/registry.py` | `infer_provider()` Heuristik (`claude-` → anthropic, `gpt-` → openai) | Provider-Inferenz für dev/debug | Nein (Governed Default — Runtime nutzt expliziten Provider) |
| `apps/api/narrare/setup/constants.py:14` | `OLLAMA_DEFAULT_URL = "http://localhost:11434"` | Setup-Default für lokales Ollama | Bereits (CR-AUFG-08-06, zentralisiert) |
| `apps/api/alembic/versions/0004_ai_settings.py` | Provider/Modell-Seed (Migration) | DB-Initialisierung | Ja (Migration, einmalig) |

**Keine** hardcodierten Modell-Namen in Produktions-Routern, Dependency-Factories
oder Services gefunden (RULE-18 ✅). Die `infer_provider()`-Heuristik ist nur
dev/debug (Governed Default mit Annotation). mem0-Modelle sind per ADR-064
Scope-Boundary explizit als Third-Party-Bibliotheks-Konfiguration klassifiziert.

### 2.2 Default-Modelle pro Feature

Default-Modelle werden **nicht** pro Feature hardcodiert. Sie werden über die
`ModelRoutingResolver`-Kaskade aufgelöst (`core/llm/model_routing.py:8`):
`project_intent → project_category → user_intent → user_category → user_default → error`.
Die `INTENT_PROFILES` (`intent_profiles.py:71-126`) sind **rein advisory** — sie
empfehlen Capability-Tier + Output-Profile, wählen aber **kein** Modell aus.

| Feature | Default-Modell | Aufgaben-Komplexität | Modell passt? | Bessere Alternative? |
|---|---|---|---|---|
| Suggest (Inline) | Nutzer-Cascade (Profile: `quick`/`fast`) | Niedrig | _Modellabhängig_ — Advisory: `capability_unknown` wenn Tier nicht deklariert | Suitability-Warnung vorhanden |
| Continue / Extend | Nutzer-Cascade (Profile: `long_texts`/`creative`) | Hoch | _Modellabhängig_ | Suitability-Warnung vorhanden |
| Rewrite / Co-Author | Nutzer-Cascade (Profile: `balanced`/`creative`) | Mittel | _Modellabhängig_ | Suitability-Warnung vorhanden |
| KB-Interview | Nutzer-Cascade (Profile: `quick`/`balanced`) | Mittel | _Modellabhängig_ | Suitability-Warnung vorhanden |
| Consistency Check | System-Default (`SystemModelCategory.ANALYSIS`) | Hoch | _Modellabhängig_ | Suitability-Warnung vorhanden |
| Freier Assistent (Chat) | Nutzer-Cascade (Profile: `balanced`/`balanced`) | Variabel | _Modellabhängig_ | Suitability-Warnung vorhanden |

> Hinweis: "Modell passt?" ist hier nicht mit Ja/Nein bewertbar, weil das konkrete
> Modell vom Nutzer kommt. Die `evaluate_model_suitability()`-Funktion
> (`model_suitability.py:67-124`) liefert Advisory/Warning/Hard-Block pro Aufruf.
> Hard-Block nur bei unmöglichen/unsicheren Calls (Provider-Cap unter Minimum-Floor,
> Context-Window zu klein).

**Bewertung:** ⭐⭐⭐⭐⭐
Modell-Konfiguration ist vorbildlich über die Routing-Kaskade gelöst. Keine
pro-Feature-Hardcodierung. Suitability-Evaluation mit dreistufiger Severity
(advisory/warning/hard_block) ist implementiert und testgedeckt
(`test_model_suitability.py`).

**Befunde:** Keine neuen Befunde in §2.

---

## 3. Weitere Magic Numbers & Strings

### 3.1 Gefundene Kandidaten

> **Eskalationsregel:** Hardcodierter Wert mit Änderungsrisiko "Hoch" +
> "Konfigurierbar machen: Ja" → FIND.

| Konstante/Wert | Datei:Zeile | Beschreibung | Änderungsrisiko | Konfigurierbar machen? | FIND |
|---|---|---|---|---|---|
| `SUGGEST_MAX_TOKENS = 60` | `core/llm/run_limits.py:27` | Inline-Suggest Output-Cap | Mittel | Nein (immutable UX-Cap, dokumentiert) | — (CR-AUFG-08-04) |
| `temperature=0.3` (Suggest) | `apps/api/narrare/writing/deps_writing.py:77`, `deps_suggest.py:37` | Hardcodierte Temperatur für Inline-Suggest | Niedrig | Nein (Low-Latency-Design) | — |
| `DEFAULT_TOTAL_BUDGET = 6000` | `core/context/budget.py:59` | Context-Assembly Gesamt-Budget | Mittel | Bereits (Method-Param, Settings) | — |
| `n = 2000` (Co-Author selection) | `apps/api/narrare/writing/coauthor_service.py:54` | Max-Wörter für Co-Author-Selection | Niedrig | Bereits (`default_max_selection_words` Setting) | — |
| `max_chapter_tokens = 2000` (Fallback) | `apps/api/narrare/consistency/checker_context.py:117` | Consistency-Chapter-Budget Fallback | Mittel | Bereits (`NARRARE_CONSISTENCY_MAX_CHAPTER_TOKENS`) | — |
| `max_kb_entries = 100` (Fallback) | `apps/api/narrare/consistency/checker_context.py:118` | Consistency-KB-Limit Fallback | Mittel | Bereits (`NARRARE_CONSISTENCY_MAX_KB_ENTRIES`) | — |
| `DEFAULT_KB_SUGGEST_MAX_RESULTS = 20` | `apps/api/narrare/kb/suggest_service.py:57`, `router_suggestions.py:25` | KB-Suggest Ergebnis-Limit | Mittel | Bereits (Query-Param `max_results`, 1-100) | — (FIND-005 originär) |
| `max_results = 20` (Proactive) | `core/context/proactive_service.py:67` | Proactive Context Vorschläge | Mittel | Bereits (Method-Param, 1-100) | — |
| `threshold = 0.7` (Embedding) | `core/embeddings/store.py:107` | Embedding-Similarity-Threshold | Mittel | Bereits (Method-Param; CR-AUFG-08-13) | — (CR-AUFG-08-13) |
| `limit = 20` (Embedding) | `core/embeddings/store.py:108` | Embedding-Search-Limit | Mittel | Bereits (Method-Param; CR-AUFG-08-13) | — (CR-AUFG-08-13) |
| `DEFAULT_EMBEDDING_MODEL` | `apps/api/narrare/embeddings/service.py:52` | Embedding-Modell (env `DEFAULT_EMBEDDING_MODEL`, Fallback `text-embedding-3-small`) | Hoch | Bereits (Env-Var) | — |
| `CATALOG_TIMEOUT = 10.0` | `core/llm/model_listing.py:66` | Provider-Katalog-Request-Timeout | Mittel | Bereits (Method-Param; CR-AUFG-08-12) | — (CR-AUFG-08-12) |
| `OPENROUTER_MAX_MODELS = 30` | `core/llm/model_listing.py:77` | OpenRouter-Modell-Cap | Niedrig | Bereits (Method-Param) | — (CR-AUFG-08-12) |
| `CACHE_TTL = 86400` (24h) | `core/llm/models_dev_source.py:23` | models.dev Cache-TTL | Niedrig | Bereits (Method-Param) | — (CR-AUFG-08-12) |
| `FETCH_TIMEOUT = 10.0` | `core/llm/models_dev_source.py:30` | models.dev Fetch-Timeout | Niedrig | Bereits (Method-Param) | — |
| `TRANSPORT_MAX_RETRIES_DEFAULT = 2` | `core/llm/_transport_retry.py:49` | Provider-SDK Transport-Retry | Mittel | Bereits (Env `NARRARE_LLM_TRANSPORT_MAX_RETRIES`; ADR-060) | — (ADR-060) |
| `prompt_history_retention_limit = 100` | `apps/api/narrare/_app/settings_model.py:162` | Prompt-History-Limit | Niedrig | Bereits (Env `NARRARE_PROMPT_HISTORY_RETENTION_LIMIT`) | — |
| **`Rate(3, 1min)` (Write)** | `apps/api/narrare/_app/rate_limits.py:54` | AI-Write Rate-Limiter | **Hoch** | **Ja (Operator-Config)** | **FIND-015** |
| `Rate(5, 1min)` (Analysis) | `apps/api/narrare/_app/rate_limits.py:60` | AI-Analysis Rate-Limiter | Hoch | Ja (Operator-Config) | FIND-015 |
| `Rate(10, 1min)` (Light) | `apps/api/narrare/_app/rate_limits.py:67` | AI-Light Rate-Limiter | Hoch | Ja (Operator-Config) | FIND-015 |
| `Rate(3, 1min)` (WS) | `apps/api/narrare/_app/rate_limits.py:92` | WebSocket Rate-Limiter | Hoch | Ja (Operator-Config) | FIND-015 |
| `Rate(5, 1min)` (Live-Test) | `apps/api/narrare/_app/rate_limits.py:82` | Prompt-Live-Test Rate-Limiter | Mittel | Ja (Operator-Config) | FIND-015 |

**Bewertung der Kandidaten:** Die meisten Magic Numbers sind bereits korrekt
klassifiziert und konfigurierbar (CR-AUFG-08-01 bis 08-13). Die Rate-Limiter
(siehe FIND-015) sind die einzige verbleibende Gruppe mit hohem Änderungsrisiko und
fehlender Konfigurierbarkeit.

### 3.2 Timeouts & Retry-Logik

| Wert | Aktuell | Sinnvoll? | Konfigurierbar? |
|---|---|---|---|
| API-Request-Timeout | Nicht explizit gesetzt (Provider-SDK-Default) | Ja (SDK-Defaults sind konservativ) | Nein (Provider-SDK-Verantwortung) |
| Retry-Anzahl (Transport) | `TRANSPORT_MAX_RETRIES_DEFAULT = 2` (`_transport_retry.py:49`) | Ja (SDK-Parität, ADR-060) | Ja (Env `NARRARE_LLM_TRANSPORT_MAX_RETRIES`) |
| Retry-Backoff | Provider-SDK-Default (komponiert mit Narrare-Retry) | Ja (ADR-060 Option B) | Nein (bewusst nicht nutzerseitig — Double-Retry-Footgun) |
| Streaming-Timeout (Frontend) | `connect_timeout_ms=30000`, `connection_loss_timeout_ms=15000` (`useAIOperation.ts`) | Ja (Local-First, UX-Schutz) | Ja (Hook-Optionen; CR-AUFG-08-13) |
| Catalog-Timeout | `CATALOG_TIMEOUT = 10.0` (`model_listing.py:66`) | Ja | Ja (Method-Param) |

### 3.3 Feature-Flags & Kill-Switches

| Feature | Aktuell aktiv? | Flag vorhanden? | Konfigurierbar? |
|---|---|---|---|
| OTEL-Tracing | Nein (Default `false` dev) | Ja (`OTEL_TRACES_ENABLED`, `_app/telemetry.py:8`) | Ja (Env-Var) |
| mem0 Memory | Bedingt (graceful degradation) | Ja (Embedding-Cascade Tier 4 → NullMemoryClient) | Ja (Provider-Config) |
| Wiki-Summaries | Ja (wenn verfügbar) | Ja (`wiki_optimized`-Param, `budget.py:198`) | Ja (Method-Param) |
| Proactive Context | Ja | Ja (Feature-Scope, KB-005) | Ja (Service-Config) |
| Systematischer Kill-Switch | — | **Nein** | — |

> **Beobachtung:** Es gibt **kein zentrales Feature-Flag-System** (kein
> `/features`-Endpoint, kein Flag-Store). Features werden via Settings/Env/Method-Params
> gesteuert. Für ein lokales Single-User-Produkt ist das adäquat; ein globaler
> Kill-Switch wäre nur bei Managed-Hosting relevant (Q-011 Distributions-Strategie
> offen). Kein FIND — architektonisch bewusst verzichtet.

**Bewertung (§3 gesamt):** ⭐⭐⭐⭐
Die Magic-Number-Landschaft ist größtenteils durch CR-08-Remediation (P0-P3)
bereinigt. Verbleibend: FIND-015 (Rate-Limiter hart codiert). Timeouts/Retry sind
korrekt als `operator_default` (ADR-060) klassifiziert mit Env-Override.

---

## 4. Konfigurierbarkeits-Matrix

> ⚠️ Die originale `configuration-adoption-matrix.yaml` existiert nicht mehr
> (siehe FIND-014). Diese Tabelle ist eine **Review-interne Neuerfassung** des
> Soll-Zustands. Eine formelle Matrix-Klassifikation erfordert FIND-014-Entscheidung.

| Wert | Aktuell | Sollte konfigurierbar sein für | Priorität |
|---|---|---|---|
| Output-Token-Limit pro Profile | Profile-System (`quick`…`comprehensive`) | Nutzer (einfach) + Operator (Rohwert) | 🟢 Erfüllt |
| `TOKEN_OUTPUT_ABSOLUTE_MAX=131072` | Code-Default | Entwickler (Code) | 🟢 Erfüllt (Hard-Cap) |
| Default-Modell pro Feature | Routing-Kaskade | Nutzer | 🟢 Erfüllt |
| max_entries KB-Suggest | Query-Param (20, 1-100) | Nutzer / Auto | 🟢 Erfüllt |
| API-Timeout | Provider-SDK-Default | Operator (indirekt) | 🟡 Akzeptabel |
| Transport-Retry | Env `NARRARE_LLM_TRANSPORT_MAX_RETRIES` | Operator | 🟢 Erfüllt |
| Consistency-Caps (`max_chapter`/`max_kb`) | Env `NARRARE_CONSISTENCY_*` | Operator | 🟢 Erfüllt |
| Context-Budget (6000) | Method-Param + Settings | Operator / Power-User | 🟢 Erfüllt |
| Tier-Percentages | Settings + Method-Param | Operator / Power-User | 🟢 Erfüllt |
| Embedding-Threshold (0.7) | Method-Param | Entwickler (Code-Default) | 🟢 Erfüllt |
| **Rate-Limiter (Write/Analysis/Light/WS)** | **Hardcodiert (`Rate(N, 1min)`)** | **Operator** | **🔴 Hoch (FIND-015)** |
| mem0-Extraktions-Modelle | Settings-Mem0-Config (pro Provider) | Operator | 🟢 Erfüllt (ADR-064) |
| `temperature=0.3` (Suggest) | Hardcodiert | Entwickler (UX-Constraint) | 🟡 Akzeptabel (Low-Latency-Design) |

---

## 5. Empfehlung: Konfigurationsschichten

Nicht alles muss in die WebUI — aber alles sollte *irgendwo* ohne Code-Änderung
anpassbar sein. Empfohlene Schichten (bestehend + Lücken):

| Schicht | Zielgruppe | Ort | Beispiele | Status |
|---|---|---|---|---|
| **Nutzer-UI** | Endnutzer | WebUI Einstellungen (AI-Tab) | Output-Profil (quick/balanced/long/comprehensive/custom), Custom-Limit bis 131k, Default-Modell | ✅ Vorhanden (PROMPT-003 + AI-Settings) |
| **Projekt-Config** | Power-User | `{project}/.narrare/` + DB (Project-AI-Settings) | Projekt-spezifische Modelle, Intent-Overrides, Genre-Prompts | ✅ Vorhanden (Routing-Kaskade) |
| **Operator-Config** | Self-Hoster | `Settings` / Env-Vars | `NARRARE_CONSISTENCY_*`, `NARRARE_LLM_TRANSPORT_MAX_RETRIES`, `NARRARE_PROMPT_HISTORY_*`, `DEFAULT_EMBEDDING_MODEL`, `OTEL_TRACES_ENABLED` | 🟡 **Lücke: Rate-Limiter** (FIND-015) |
| **Code-Defaults** | Entwickler | `token_profiles.py`, `budget.py`, `model_config.py` | Hard-Caps, Tier-Percentages, Suitability-Floors, Cache-Settings | ✅ Vorhanden |

**Empfehlung für FIND-015:** Rate-Limiter (`Rate(3, 1min)` etc.) als
`operator_default` in `Settings` mit Env-Var-Override (`NARRARE_RATE_LIMIT_*`)
klassifizieren — analog zu `NARRARE_LLM_TRANSPORT_MAX_RETRIES`. Self-Hoster mit
anderen Hardware-Ressourcen oder Managed-Hosting-Profile brauchen anpassbare Limits.

---

## 6. ⚠️ Kopf-Befund: CR-AUFG-08-14 Enforcement-Toolchain entfernt

> Dieser Abschnitt dokumentiert den **materialsten Befund** dieses Reviews: Das
> Enforcement-Toolchain, das CR-AUFG-08-14 und RULE-18b implementieren sollte,
> wurde am 2026-07-08 **bewusst gelöscht** — aber CONSTRAINTS.md referenziert es
> weiterhin als "CI-validated".

### 6.1 Befund

- [P1] [category: configuration-effect] FIND-014 / CR-AUFG-08-15: **RULE-18b-Enforcement-Toolchain entfernt, CONSTRAINTS.md stale**

  Die gesamte P0-P5-Governance-Toolchain wurde im Commit `f8abb42c` ("chore: remove
  P0-P5 governance toolchain (ADR-047/051/061/062)") bewusst gelöscht:
  - `docs/architecture/governance/configuration-adoption-matrix.yaml` (815 Zeilen)
  - `scripts/check_configuration_matrix.py` (120 Zeilen)
  - `scripts/governance/` (gesamtes Verzeichnis, ~60 Dateien)
  - `configuration-adoption-matrix.schema.json`, `matrix-effect-evidence.yaml`,
    `status_vocabulary.yaml`, `aufg-registry.md` (2.346 Zeilen)
  - ADR-047/051/061/062 alle auf "⏸ Superseded" gesetzt.

  **Das Problem:** `CONSTRAINTS.md` RULE-18b (Zeile 601-609) referenziert diese
  Artefakte weiterhin als live-erzwungen:
  > "The configuration adoption matrix is CI-validated. It fails when…"
  > "The review-finding coverage gate fails when a structured material P0/P1
  > `[category: configuration-effect]` review finding is not referenced by a matrix entry"

  Diese Aussagen sind **falsch** — weder die Matrix noch der Checker noch der
  Review-Gate existieren. Dies ist eine RULE-18b-Verletzung Typ 3 ("No regression
  evidence of effect") auf Meta-Ebene: die Enforcement-Behauptung selbst hat keinen
  Runtime-Effekt mehr.

  **Zusätzlich stale:**
  - ADR-051-Body (Zeile 209-252) behauptet weiterhin "Accepted: 2026-06-20" mit
    "Implementation and Enforcement Evidence", die ins Leere laufen (Matrix=815
    Zeilen referenziert → gelöscht; Checker=CI-blocking → gelöscht). Der Header
    (Zeile 3) sagt korrekt "⏸ Superseded", aber der Body wurde nicht bereinigt.
  - `cr-08-configuration-effect-drift.md` (Remediation-Spec) behauptet "resolved —
    P0–P4 implementation/enforcement complete" und listet gelöschte Evidence-Dateien.
  - `cr-08-p3-governed-defaults-manifest.md` verweist auf nicht-existierende
    Matrix-Einträge ("§6 Matrix Status").

### 6.2 Warum P1 (nicht P0)

Kein Produktions-Ausfall oder Datenverlust — die Runtime-Werte (Token-Limits,
Modelle, Caps) funktionieren weiterhin korrekt. Aber das **Präventions-Gate** für
zukünftige Konfigurations-Drift-Befunde fehlt: Neue hardcodierte Werte können
unentdeckt als False Controls eindringen, weil keine CI-Blockade mehr existiert.
Dies schwächt RULE-18b auf eine reine Dokumentations-Aussage ohne maschinelle
Erzwingung.

### 6.3 Entscheidung erforderlich

Entweder:
- **(A)** RULE-18b-Enforcement-Abschnitt in CONSTRAINTS.md (Zeile 599-613)
  aktualisieren: Matrix als "removed/superseded" markieren, Stale-Referenzen aus
  ADR-051-Body, Remediation-Spec und P3-Manifest bereinigen. CR-AUFG-08-14
  Strukturpflicht aus Review-Templates entfernen. → Akzeptiert die Enforcement-Lücke.
- **(B)** Configuration Adoption Matrix + Checker wiederherstellen (oder
  leichtgewichtigen Nachfolger bauen), RULE-18b bleibt voll erzwungen.

> Dies ist eine Architektur-Entscheidung, nicht im Scope dieses Content-Reviews.
> **Gemeldet als FIND-014 / CR-AUFG-08-15 für Architecture + Platform.**

---

## Gesamtbewertung Konfigurierbarkeit

**Bewertung:** ⭐⭐⭐⭐

**Zusammenfassung:** Die Token-, Modell- und Limit-Konfigurierbarkeit ist auf
Werte-Ebene **vorbildlich** umgesetzt — CR-08 P0-P3 hat echte Runtime-Effekt-Adoption
erreicht (Output-Limits an Modellgrenze erzwungen, Tier-Percentages konsumiert,
Profile-Vokabular vereinheitlicht, Suitability-Evaluation implementiert). Fast alle
Magic Numbers sind korrekt als `adopted`, `operator_default` oder `governed_default`
klassifiziert und besitzen Config-Pfade (Env-Vars, Method-Params, Settings-Cascade).

**Zwei Abzüge (1 Stern):**
1. **FIND-014 (P1):** Das Enforcement-Toolchain (Matrix + Checker + Review-Gate)
   wurde gelöscht, aber CONSTRAINTS.md RULE-18b behauptet weiterhin CI-Validierung.
   Dies ist ein False Control auf Meta-Ebene und untergräbt die Nachhaltigkeit der
   sonst guten Arbeit. Zukünftige Drift-Befunde haben keine CI-Blockade mehr.
2. **FIND-015 (P2):** Rate-Limiter sind hart codiert (`Rate(N, 1min)`), nicht
   operator-konfigurierbar — die einzige verbleibende Magic-Number-Gruppe mit
   hohem Änderungsrisiko ohne Config-Pfad.

Beide sind behebbar ohne die starke Werte-Ebene anzutasten.

---

## Aufgaben

<!-- Nummerierung: CR-AUFG-08-15, CR-AUFG-08-16 … (08-01 bis 08-14 aus vorheriger Runde) -->

- [P1] [category: configuration-effect] FIND-014 / CR-AUFG-08-15: **RULE-18b-Enforcement-Toolchain entfernt, CONSTRAINTS.md stale** —
  Die Configuration Adoption Matrix, `check_configuration_matrix.py`, `scripts/governance/`
  und zugehörige Tests wurden in Commit `f8abb42c` bewusst gelöscht (ADR-047/051/061/062
  → Superseded). CONSTRAINTS.md RULE-18b (Zeile 601-609) referenziert Matrix + Review-Gate
  weiterhin als "CI-validated" — stale. ADR-051-Body und `cr-08-configuration-effect-drift.md`
  behaupten "resolved with enforcement evidence" für gelöschte Dateien. CR-AUFG-08-14
  Strukturpflicht in Review-Templates ist nicht erfüllbar. **Matrix-Klassifikation für
  diesen Wert: nicht möglich (Matrix existiert nicht) — formelle FIND-014-Entscheidung
  (Option A: stale-Referenzen bereinigen; Option B: Toolchain wiederherstellen) ist
  Voraussetzung für künftige Matrix-Klassifikationen.** Owner: Architecture + Platform.

- [P2] FIND-015 / CR-AUFG-08-16: **Rate-Limiter hart codiert, nicht operator-konfigurierbar** —
  `AI_WRITE_LIMITER = Rate(3, 1min)`, `AI_ANALYSIS_LIMITER = Rate(5, 1min)`,
  `AI_LIGHT_LIMITER = Rate(10, 1min)`, `AI_WS_LIMITER = Rate(3, 1min)`,
  `AI_PROMPT_LIVE_TEST_LIMITER = Rate(5, 1min)` in
  `apps/api/narrare/_app/rate_limits.py:54-92` sind hardcodiert ohne Env/Settings-Override.
  Self-Hoster mit anderer Hardware oder Managed-Hosting-Profile können Limits nicht
  anpassen. Empfehlung: als `operator_default` mit Env-Vars (`NARRARE_RATE_LIMIT_WRITE`
  etc.) klassifizieren, analog zu `NARRARE_LLM_TRANSPORT_MAX_RETRIES` (ADR-060).
  Änderungsrisiko: Hoch (Managed-Hosting / Multi-User). Owner: Backend + Platform.
  > Hinweis: Kein `configuration-effect`-Marker, da die Rate-Limiter nie als
  > konfigurierbar dokumentiert waren (keine False-Control-Lüge). Reiner
  > Konfigurierbarkeits-FIND.

---

*End of CR-08 Content Review. Alle Einträge gegen echten Code verifiziert
(Datum: 2026-07-11, Commit-Stand: HEAD).*
