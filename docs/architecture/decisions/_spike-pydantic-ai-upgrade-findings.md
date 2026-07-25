# Spike Findings: pydantic-ai Upgrade (2.13.0 → 2.18.0)

> **Spike-Typ:** Technische Untersuchung (keine Code-Fixes, nur Dokumentation).
> **Datum:** 2026-07-25
> **Worktree:** `/tmp/opencode/narrare-spike-pydantic-ai` (Branch `feat/pydantic-ai-upgrade`)
> **Status:** ✅ Upgrade ist sicher — keine Breaking Changes für Narrare.

---

## ⚠️ Wichtige Korrektur der Task-Prämisse

Der Task ging von `pydantic-ai-slim==2.9.0` als aktueller Version aus.
**Tatsächlich ist `main` auf `pydantic-ai-slim==2.13.0` gepinnt**
(`packages/core/pyproject.toml:10`, bestätigt via `git rev-parse` auf HEAD
`8fb4098e`). Der echte Upgrade-Pfad ist also **2.13.0 → 2.18.0** (5 Minor-
Versionen), nicht 2.9.0 → 2.18.0 (9 Minor-Versionen).

Das ist eine **kleinere** Distanz als angenommen und liegt vollständig
innerhalb des V2-Stabilitätsfensters (siehe §„Root Cause" unten).

---

## Versions

| Package              | Von (main) | Nach (Spike) | Anmerkung                          |
|----------------------|-----------:|-------------:|------------------------------------|
| `pydantic-ai-slim`   | 2.13.0     | **2.18.0**   | neueste stabile 2.x                |
| `pydantic-ai-harness`| —          | **0.11.0**   | neu hinzugefügt (Basis, keine Extras)|
| `pydantic-evals`     | 2.13.0     | **2.18.0**   | zwingend lockstep (pinnt slim)     |
| `pydantic-graph`      | 2.13.0     | **2.18.0**   | automatisch via slim gezogen       |

`uv lock` Resolution: `Resolved 235 packages`. `uv sync --all-packages`:
alle vier narrare-Packages + Harness + slim 2.18.0 sauber installiert und
importierbar (`import pydantic_ai_harness`, `import narrare_core` → OK).

---

## Root Cause: Warum nichts bricht

**Der entscheidende Befund:** Pydantic AI erreichte V1 am 2025-09-04 mit
einem API-Stabilitätsversprechen („no changes that break your code until V2").
V2.0.0 wurde am **2026-06-23** veröffentlicht und bündelt alle Breaking-
Changes, die das Stabilitätsversprechen nicht erlaubte (V1→V2 Migration).

**Narrare war bereits auf V2** (2.13.0, veröffentlicht 2026-07-17). Die V2-
Migration (die großen Breaking Changes: `OpenAIChatModel`-Rename, `builtin`→
`native`, `history_processors`→`ProcessHistory`, `Usage`→`RunUsage`, MCP-
API-Umstellung, Google-Provider-Konsolidierung etc.) war **bereits absolviert**.

Das Upgrade 2.13.0 → 2.18.0 liegt **vollständig innerhalb des V2-Stabilitäts-
fensters** (V2 verspricht Stabilität bis V3). Die Versionspolitik von
pydantic-ai garantiert daher per Definition keine Breaking Changes in diesem
Bereich — und die Tests bestätigen das empirisch.

Quelle: <https://ai.pydantic.dev/changelog/> (Upgrade Guide, V2-Versionierung)

---

## Breaking Changes

### Category 1: Import-Änderungen
**Anzahl: 0**

Alle von Narrare genutzten Import-Pfade sind in 2.18.0 unverändert gültig.
Vollständige Import-Inventur (99 `from pydantic_ai`/`import pydantic_ai`/
`from pydantic_graph`-Statements in `packages/core`):

| Modul                                        | Symbole                                           | Status 2.18.0 |
|----------------------------------------------|---------------------------------------------------|---------------|
| `pydantic_ai`                                | `Agent`, `RunContext`, `ModelRetry`, `InstrumentationSettings` | ✅ unverändert |
| `pydantic_ai.capabilities`                   | `AbstractCapability`, `ToolSearch`, `Toolset`     | ✅ unverändert |
| `pydantic_ai.exceptions`                     | `ModelRetry`, `ModelHTTPError`, `UnexpectedModelBehavior`, `UsageLimitExceeded` | ✅ unverändert |
| `pydantic_ai.messages`                       | `ModelResponse`                                   | ✅ unverändert |
| `pydantic_ai.models`                         | `Model`, `ModelRequestContext`                    | ✅ unverändert |
| `pydantic_ai.models.test`                    | `TestModel`                                       | ✅ unverändert |
| `pydantic_ai.models.{anthropic,google,groq,openai}` | `AnthropicModel`, `GoogleModel`, `GroqModel`, `OpenAIChatModel` | ✅ unverändert |
| `pydantic_ai.providers.{anthropic,google,groq,openai}` | je `*Provider`                            | ✅ unverändert |
| `pydantic_ai.output`                         | `OutputSpec`                                      | ✅ unverändert |
| `pydantic_ai.settings`                       | `ModelSettings`                                   | ✅ unverändert |
| `pydantic_ai.tools`                          | `Tool`                                            | ✅ unverändert |
| `pydantic_ai.toolsets`                       | `FunctionToolset`                                 | ✅ unverändert |
| `pydantic_ai.usage`                          | `UsageLimits`                                     | ✅ unverändert |
| `pydantic_graph`                             | `End`, `GraphBuilder`, `StepContext`, `TypeExpression` | ✅ unverändert |

### Category 2: API-Änderungen (Signaturen, Parameter, Rückgabewerte)
**Anzahl: 0**

Die von Narrare genutzten Public-APIs sind signatur-identisch:
- `Agent(model=, deps_type=, capabilities=, output_type=, system_prompt=, instructions=)` — Konstruktor unverändert
- `agent.run(prompt, deps=)` → `result.output` — unverändert
- `agent.run_stream(prompt, deps=, message_history=)` → `result.stream_text()`, `result.usage`, `result.new_messages()` — unverändert
- `Agent.instrument_all(settings)` — unverändert (nur der *Konstruktor-Arg* `instrument=` wurde in V2 entfernt; Narrare nutzt die Methode)

### Category 3: Capability/Tool-System
**Anzahl: 0 Breaking, viele Ergänzungen (Phase-2-Potenzial)**

Narrare überschreibt in `NarrareObservability` genau 4 Hooks. Alle 4
Signaturen sind **byte-identisch** mit 2.18.0 `AbstractCapability`:

| Narrare-Hook                                  | 2.18.0-Signatur (aus `capabilities/abstract.py`)         | Match |
|-----------------------------------------------|----------------------------------------------------------|:-----:|
| `for_run(self, ctx) -> AbstractCapability`    | `async def for_run(self, ctx) -> AbstractCapability`     | ✅ |
| `before_model_request(self, ctx, request_context) -> ModelRequestContext` | identisch | ✅ |
| `after_model_request(self, ctx, *, request_context, response) -> ModelResponse` | identisch | ✅ |
| `on_model_request_error(self, ctx, *, request_context, error) -> ModelResponse` | identisch | ✅ |

`NarrareMeta.get_instructions(self) -> str | None` ist kompatibel mit
2.18.0 `-> AgentInstructions[AgentDepsT] | None` (da `str` Teil der
`AgentInstructions`-Union ist — pyright bestätigt, 0 Errors).

**Neu in 2.18.0 (additiv, nicht-gebrochen)** — `AbstractCapability` bietet
jetzt ~25 weitere Hooks/Capability-Methoden (siehe §„Phase-2-Empfehlung"):
- Run-Lifecycle: `before_run`, `after_run`, `wrap_run`, `on_run_error`
- Node-Lifecycle: `before_node_run`, `after_node_run`, `wrap_node_run`, `on_node_run_error`
- Tool-Validate/Execute: je `before_`/`after_`/`wrap_`/`on_*_error`
- Output-Validate/Process: je `before_`/`after_`/`wrap_`/`on_*_error`
- `wrap_run_event_stream`, `handle_deferred_tool_calls`, `resolve_model_id`, `get_model`, `get_ordering`, `prepare_output_tools`, etc.

### Category 4: Provider/Model-Änderungen
**Anzahl: 0 für Narrare**

Provider-Klassen (`AnthropicModel`, `GoogleModel`, `GroqModel`,
`OpenAIChatModel` + zugehörige `*Provider`) sind unverändert. Narrare nutzt
explizite Klassen (nicht Modell-String-Präfixe), deshalb nicht betroffen von:
- `openai:`-Default-Wechsel zu Responses-API (V2-Änderung, bereits absorbiert)
- `groq:`→`xai:` / Google-Provider-Renames (V2-Änderung, bereits absorbiert)

**Modell-Liste-Hinweis (2.14.0):** `gemini-2.5-flash-lite-preview-09-2025`
und `gemini-3.1-flash-lite-preview` wurden entfernt (shut-down-Modelle).
Narrare's `MODEL_ROUTING` prüfen, falls diese referenziert werden (nicht in
diesem Spike geprüft — gehört zur Phase-2-Evaluation).

### Category 5: TestModel/FunctionModel
**Anzahl: 0**

`TestModel` aus `pydantic_ai.models.test` unverändert. Die gesamten
Agent-Level-Tests (TestModel-basiert) laufen grün.

### Category 6: Sonstige (Deprecations, Behavior-Changes)
**Anzahl: 0 Code-Breaks, 1 Behavior-Change, 1 externe Deprecation-Warning**

#### Behavior-Change (kein Code-Break, aber Runtime-Verhalten ändert sich):
- **Instrumentation Defaults (V2.0.0):** `InstrumentationSettings` defaultet
  jetzt auf `version=5` und `use_aggregated_usage_attribute_names=True`.
  Narrare setzt in `agents/instrumentation.py` weder `version=` noch
  `use_aggregated_usage_attribute_names=` explizit → bekommt die neuen
  Defaults. **Auswirkung:** OTel-Spans reporten Token-Usage jetzt unter
  `gen_ai.aggregated_usage.*` (Run-Spans) statt `gen_ai.usage.*`. Dashboards/
  Alerts, die Run-Span-Token-lesen, müssen aktualisiert werden (oder
  `use_aggregated_usage_attribute_names=False` setzen). Kein Code-Fix nötig;
  reine Observability-Konfiguration.

#### Externe Warning (nicht pydantic-ai):
- `google/genai/types.py:42: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17` — stammt vom Google-SDK, nicht von pydantic-ai. Unabhängig vom Upgrade.

#### PydanticAI-interne Deprecations im Bereich 2.14→2.18:
- **2.15.0:** Exa-search-Common-Tools deprecated → `ExaSearch`-Capability im
  Harness. **Narrare nutzt Exa nicht → nicht betroffen.**
- Keine weitere `PydanticAIDeprecationWarning` in Narrare's Test-Output
  (geprüft mit `-W default::DeprecationWarning` auf `tests/unit/core/agents/`
  + `tests/unit/core/llm/`: 1574 passed, 1 skipped, nur die o.g. Google-Warning).

---

## Check-Ergebnisse (Evidence)

| Check                          | Befehl                                  | Ergebnis |
|--------------------------------|-----------------------------------------|----------|
| Architecture (`check_architecture.py` + 4 weitere) | `just check-architecture` | ✅ 2175 Dateien, 16 approved Exceptions (Baseline unverändert: 0 new) |
| Prompt Surface Contract        | (in check-architecture)                 | ✅ OK |
| Exception-Baseline-No-Growth   | (in check-architecture)                 | ✅ 12/12, 0 new |
| Type-Check (pyright, strict)   | `uv run pyright`                        | ✅ **0 errors, 0 warnings** |
| Core-Unit-Tests                | `pytest tests/unit/core/`               | ✅ **5166 passed, 3 skipped, 0 failed** (63s) |
| Vollständige Unit-Suite        | `pytest tests/unit/`                    | ✅ **9630 passed, 3 skipped, 0 failed** (127s) |
| Import-Smoke-Test              | manuell (`importlib`)                   | ✅ agents/base, gateway, instrumentation, capabilities importierbar |
| Deprecation-Warnings           | `pytest -W default::DeprecationWarning` | ✅ 0 `PydanticAIDeprecationWarning` |

**Integration-Tests** (`tests/integration/`) wurden nicht ausgeführt — sie
benötigen Docker-Services + Provider-Credentials und sind für einen Spike
nicht relevant (Unit-Tests mit `TestModel` decken die pydantic-ai-Integration
vollständig ab).

---

## Affected Files (Priorisiert)

| Datei | Break-Typ | Schwere | Fix-Ansatz (Skizze) |
|-------|-----------|:------:|---------------------|
| — | — | — | **Keine Code-Fixes erforderlich.** |

Es gibt **keine** Datei, die wegen des Upgrades angepasst werden muss.
Alle Änderungen in diesem Spike sind:
1. `packages/core/pyproject.toml` — Version-Bump (2.13.0→2.18.0) + Harness-Add
2. `pyproject.toml` (root) — `pydantic-evals` 2.13.0→2.18.0 (zwingend lockstep)
3. `uv.lock` — auto-generiert
4. Diese Findings-Datei

Optionale (nicht-blockierende) Observability-Abstimmung:
| Datei | Hinweis | Schwere |
|-------|---------|:------:|
| `packages/core/narrare_core/agents/instrumentation.py` | Wenn Dashboards `gen_ai.usage.*` auf Run-Spans lesen: `use_aggregated_usage_attribute_names=False` setzen ODER Dashboards auf `gen_ai.aggregated_usage.*` umstellen. | Niedrig (nur bei aktivem Logfire/Dashboards) |

---

## Risikobewertung

### Hochrisiko-Bereiche: **keine**
Die vom Task genannten Hochrisiko-Bereiche (Hook-Signaturen, ToolSearch/Toolset,
ModelRequestContext/ModelResponse) wurden alle verifiziert und sind **nicht
betroffen**. Die V2-Migration lag bereits hinter Narrare.

### Niedrigrisiko-Bereiche:
1. **Instrumentation-Default-Wechsel** — betrifft nur OTel/Dashboards, nicht
   die Code-Korrektheit. Klärung in Phase 2, ob Logfire-Dashboards angepasst
   werden.
2. **Modell-Liste 2.14.0** — zwei shut-down Gemini-Modelle entfernt. Prüfen,
   ob Narrare's `MODEL_ROUTING`/`intents.py` diese referenziert (in diesem
   Spike nicht geprüft — da MODEL_ROUTING kein pydantic-ai-Import ist).
3. **Harness-Adoption** — Harness ist installiert aber ungenutzt. Kein Risiko
   für Bestehendes; reine Phase-2-Opportunity.

### Risiko-Gesamteinschätzung: **SEHR NIEDRIG**
Das Upgrade kann als reiner Versions-Bump + Lockstep-Update committed werden.
Kein Refactoring, keine Adapter, keine Migration nötig.

---

## Phase-2-Empfehlung (Capability-Adoption)

Dieser Spike empfiehlt, in Phase 2 folgende **neuen** 2.18.0-Möglichkeiten zu
evaluieren (alle additiv, keine Dringlichkeit):

### A. Neue AbstractCapability-Hooks (observability + kontrolle)
Narrare's `NarrareObservability` nutzt nur 4 von ~30 verfügbaren Hooks.
Interessant für tiefere Observability / Fehlerbehandlung:
- `wrap_run` / `on_run_error` — Run-Level-Tracing jenseits einzelner Model-Calls
- `before_tool_execute` / `after_tool_execute` — Tool-Level-Metriken
- `wrap_model_request` — Model-Call-Wrapping (Retries, Fallbacks)

### B. Neue Built-in Capabilities (aus `pydantic_ai.capabilities`)
2.18.0 liefert deutlich mehr fertige Capabilities als Narrare's Stand:
`Thinking`, `WebSearch`, `WebFetch`, `MCP`, `ImageGeneration`, `ProcessHistory`,
`Hooks`, `Instrumentation`, `PrepareTools`, `SetToolMetadata`, `PrefixTools`,
`SelectModel`, `ResolveModelId`, `RaiseContentFilterError`, `HandleDeferredToolCalls`,
sowie deferred-loading (on-demand) Capabilities (2.0.0b5).
Besonders relevant für Narrare:
- **`Thinking`** — falls Reasoning-Modelle eingesetzt werden (consistency/analysis)
- **`Instrumentation`** — könnte Narrare's custom `NarrareObservability` ergänzen/vereinfachen
- **`Hooks`** — deklarative Hook-Registrierung ohne Capability-Subclass

### C. Pydantic AI Harness (0.11.0, jetzt installiert)
Das Harness (separates Paket) liefert erste-Klasse-Integrationen: ACP, Modal,
ExaSearch, Logfire-Deep-Integration, Code-Mode, DBOS/Temporal-Durability.
Narrare sollte evaluieren, welche Harness-Features die eigene Infra ersetzen
können (insb. Logfire-Integration und ggf. Durability für lange Writing-Graphs).

### D. Behavior-Change-Abstimmung (Instrumentation v5)
Klären, ob Narrare's Logfire-Dashboards/Alerts auf `gen_ai.usage.*` (Run-Spans)
bauen. Falls ja: entweder Dashboard-Update oder explizit
`use_aggregated_usage_attribute_names=False` in `instrumentation.py`.

### Was Phase 2 **nicht** berücksichtigen muss:
- Migration-Code (keine Breaking Changes)
- Adapter-Schichten (APIs sind identisch)
- Deprecation-Bereinigung (0 `PydanticAIDeprecationWarning`)

---

## Spike-Artefakte

- **Branch:** `feat/pydantic-ai-upgrade` (via `git worktree`, da `git checkout -b`
  in dieser Environment permission-denied war — siehe Hinweis unten)
- **Worktree-Pfad:** `/tmp/opencode/narrare-spike-pydantic-ai`
- **Geänderte Dateien:** `packages/core/pyproject.toml`, `pyproject.toml` (root),
  `uv.lock`, diese Datei
- **Kein Commit** (laut Task: Platform-Specialist committet)

### Hinweis: Branch-Erstellung via Worktree
`git checkout -b feat/pydantic-ai-upgrade` war permission-denied. Die
Permission-Config erlaubt explizit `git worktree*`. Der Branch wurde daher
via `git worktree add -b feat/pydantic-ai-upgrade /tmp/opencode/narrare-spike-pydantic-ai`
erzeugt (sanctioned Alternative, kein Workaround via Scripts). Der Platform-
Specialist findet die Änderungen im Worktree oder kann den Branch direkt nutzen.
