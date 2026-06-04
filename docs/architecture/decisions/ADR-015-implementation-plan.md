# ADR-015 — Implementation Plan: Agents as First-Class Citizens

> **Companion to ADR-015.** Phased migration plan mit Layer-Zuordnung, Definition of Done und Risikobewertung.
>
> Location: `docs/architecture/decisions/ADR-015-implementation-plan.md`

---

## Übersicht

4 Phasen, aufsteigend nach Komplexität. Jede Phase baut auf der vorherigen auf.

```
Phase 0: 🏗️ Fundament (ADR + Gateway als ModelRegistry + Module)     ~3 Tage
     ↓
Phase 1: ✅ Usage Limits + Hooks/Observability (abgeschlossen)
     ↓
Phase 2: ✍️ Output Functions → DraftAgent                              ~7 Tage
     ↓
Phase 3: 🗄️ KB-Tools + ToolSearch → ContextAssembler als Tool         ~10 Tage
     ↓
Phase 4: ✅ 🕸️ Pydantic Graph für Writing-Workflows (abgeschlossen)
                                                              ─────────────
                                                    Gesamt: ~38 Tage
```

---

## Phase 0 — Fundament

**Ziel**: ADR verabschieden, RULE-01b definieren, Gateway umbauen, `core/agents/` Struktur schaffen.

### Tasks

#### 0.1 RULE-01b definieren (Architecture Agent)

`docs/_shared/CONSTRAINTS.md` aktualisieren:

```diff
- RULE-01 · LLM calls go through the Gateway. Always.
+ RULE-01b · Agents are the way to use LLMs. Models come from the Gateway. Always.
```

Detaillierte Regel:
```
Erlaubt in core/agents/:
  from pydantic_ai import Agent
  from pydantic_ai.capabilities import ...
  from pydantic_ai.output import ...

Erlaubt in core/llm/:
  from pydantic_ai.models import Model  # Model-Registry
  from pydantic_ai.providers import ...  # Provider-Adapter

Verboten überall:
  import openai / anthropic (direkter Client)
  httpx.post(...) zu LLM-Endpoints

  Agent(...) instantiiert außerhalb von core/agents/
  agent.run() / agent.run_sync() außerhalb von core/agents/
```

`scripts/check_architecture.py` aktualisieren:
- `import openai` / `import anthropic` → block (wie bisher)
- `from pydantic_ai import Agent` in `core/agents/` → erlaubt
- `from pydantic_ai import Agent` anderswo → block (NEU)
- `Agent(`-Instantiation in `core/agents/` → erlaubt
- `Agent(`-Instantiation anderswo → block (NEU)
- `agent.run(` / `agent.run_sync(` in `core/agents/` → erlaubt
- `agent.run(` / `agent.run_sync(` anderswo → block (NEU)

**Layer**: Platform (Architecture Check)
**DoD**: CI schlägt fehl bei Agent-Instantiation außerhalb von `core/agents/`

#### 0.2 Gateway als ModelRegistry umbauen (Core Specialist)

Aktuell: `Gateway.run(intent, content)` — erzeugt Agent, ruft auf, gibt Ergebnis zurück.

Neu: `Gateway.get_model(config: ResolvedModelConfig) -> Model` — gibt ein konfiguriertes Model-Objekt zurück.

```python
class ModelRegistry:
    """Gateway v2 — liefert konfigurierte Model-Instanzen.

    Übernimmt:
    - Provider-Resolution (welcher Factory für provider_name)
    - Credential-Injection (api_key + base_url aus User-DB)
    - UsageLimits-Vorkonfiguration

    Agents holen sich ihr Model hier, rufen dann selbst run() auf.
    """

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        usage_limits: UsageLimits | None = None,
    ) -> Model:
        """Liefert ein konfiguriertes Model inkl. Credentials."""
        ...

    # Optional: Kurzform für einfache Fälle
    async def run(
        self,
        intent: LLMIntent,
        prompt: str,
        config: ResolvedModelConfig,
        *,
        output_type: type[T] | None = None,
        capabilities: list[AbstractCapability] | None = None,
        deps: Any = None,
        usage_limits: UsageLimits | None = None,
    ) -> AgentRunResult[T]:
        """Erzeugt ephemeren Agent, ruft auf, gibt Ergebnis.

        Bleibt als Komfort-Methode für einfache Fälle (Health Check, etc.)
        """
        ...
```

**Migration**:
- `LLMGateway` → `ModelRegistry` (neuer Name, neue Verantwortung)
- Alte `LLMGateway`-Klasse bleibt als `_LegacyGateway` für Kompatibilität (Phase 1–2 paralleler Betrieb)
- Alle bestehenden Call-Sites (`gateway.run(...)`) werden auf `registry.get_model()` umgestellt oder nutzen die Komfort-Methode

**Layer**: Core
**DoD**:
- `ModelRegistry` liefert konfigurierte `Model`-Instanzen
- Alle existierenden Tests laufen durch (Kompatibilitäts-Wrapper)
- Credential-Resolution ist unverändert

#### 0.3 core/agents/ Modul-Struktur anlegen (Core Specialist)

```
narrare_core/agents/
├── __init__.py
├── base.py                  ← Base-Agent-Klasse (NarrareAgent)
├── draft.py                 ← DraftAgent (Phase 2)
├── kb_agent.py              ← KBAgent (Phase 3)
├── writing_graph.py         ← WritingGraph (Phase 4)
└── capabilities/
    ├── __init__.py
    ├── narrare_observability.py  ← Hooks-Capability (Phase 1)
    └── ...
```

`NarrareAgent`-Basis:
```python
class NarrareAgent(ABC, Generic[DepsT, OutputT]):
    """Basis-Klasse für alle Narrare-Agents.

    Stellt sicher:
    - Model kommt aus ModelRegistry (nie direkt)
    - Standard-Capabilities werden immer injected (Observability, Limits)
    - Fehler werden einheitlich klassifiziert
    """

    def __init__(
        self,
        model: Model,
        deps_type: type[DepsT],
        output_type: type[OutputT] | None,
        capabilities: list[AbstractCapability] | None = None,
    ):
        self._agent = Agent(
            model=model,
            deps_type=deps_type,
            output_type=output_type,
            capabilities=[
                NarrareObservability(),  # immer
                *(capabilities or []),
            ],
        )

    @abstractmethod
    async def run(self, prompt: str, deps: DepsT) -> OutputT:
        ...
```

**Layer**: Core
**DoD**: `core/agents/` existiert mit Basisklasse, Grundstruktur, Tests

#### 0.4 Bestehende Gateway-Call-Sites prüfen (Backend Specialist)

Alle `gateway.run(...)`-Aufrufe im Codebase identifizieren:
- `apps/api/narrare/writing/service.py`
- `apps/api/narrare/generation/name_service.py`
- `apps/api/narrare/setup/provider_service.py` (Test-Call)
- Tests

Kategorisieren:
- **Simple Calls** (kein spezielles Output-Type, kein Tools) → nutzen `Registry.run()` Komfort-Methode
- **Complex Calls** (Writing-Pipeline) → werden in Phase 2 auf Agent umgestellt

**Layer**: Backend + Core
**DoD**: Liste aller Call-Sites mit Migration-Kategorie erstellt

---

## ✅ Phase 1 — Usage Limits + Hooks (abgeschlossen)

**Ziel**: Token-Sicherheit + bessere Observability — beides noch im alten Gateway-Modell, aber kompatibel mit der neuen Architektur.

### Tasks

#### ✅ 1.1 UsageLimits-Parameter in ModelRegistry (Core Specialist)

```python
class ModelRegistry:
    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        usage_limits: UsageLimits | None = None,
    ) -> Model:
        # UsageLimits vom User-Profil überschreiben falls nicht explizit
        if usage_limits is None and config.token_limit_profile:
            usage_limits = self._profile_to_limits(config.token_limit_profile)
        ...
```

Token-Limit-Profile aus `UserAISettings` / `ProjectAISettings`:
```python
LIMIT_PROFILES = {
    "conservative": UsageLimits(request_limit=10, total_tokens_limit=32000),
    "balanced": UsageLimits(request_limit=25, total_tokens_limit=64000),
    "unlimited": None,  # kein Limit
}
```

**Layer**: Core
**DoD**:
- `ModelRegistry.get_model()` akzeptiert `usage_limits`
- Token-Profile werden korrekt in `UsageLimits` übersetzt
- `UsageLimitExceeded` wird als user-visible error klassifiziert
- Tests: Limits werden angewendet, Limitüberschreitung wird abgefangen

#### ✅ 1.2 NarrareObservability-Hooks-Capability (Core Specialist)

```python
@dataclass
class NarrareObservability(AbstractCapability[Any]):
    """Standard-Observability-Capability für alle Narrare-Agents.

    Ersetzt die manuelle record_success/record_failure im alten Gateway.
    """

    def before_model_request(self, ctx, request_context):
        # Request starten → Metric starten
        start_time = time.monotonic()
        ctx._narrare_start = start_time
        return request_context

    def after_model_request(self, ctx, request_context, response):
        # Tokens + Cost tracken
        elapsed = time.monotonic() - ctx._narrare_start
        record_success(
            model=request_context.model,
            tokens=response.usage,
            duration=elapsed,
        )
        return response

    def on_model_request_error(self, ctx, request_context, error):
        error_type = classify_error(error)
        record_failure(
            model=request_context.model,
            error_type=error_type,
        )
        return error  # propagate
```

Integration:
- `NarrareObservability` wird in `NarrareAgent.__init__()` immer injected
- Ersetzt die Aufrufe in `LLMGateway._run_single()` / `_stream_single()`
- ADR-031 supersedes the earlier Logfire option: Pydantic-AI runtime spans use OpenTelemetry, not Logfire.

**Layer**: Core
**DoD**:
- `NarrareObservability` trackt alle LLM-Calls (Success/Failure/Tokens/Dauer)
- Alte `record_success`/`record_failure` sind durch Hooks ersetzt
- Pydantic-AI OpenTelemetry instrumentation is active through the ADR-031 runtime bootstrap
- Tests: Hooks feuern, Metriken landen im richtigen Backend

#### ✅ 1.3 Token-Usage in UI anzeigen (Frontend Specialist)

Nach jedem Generation-Aufruf die verbrauchten Tokens aus `result.usage` auslesen und in der `MetadataSidebar` anzeigen:
- Tokens dieser Session
- Tokens dieses Kapitels
- Token-Budget (aus Settings)

**Layer**: Frontend
**DoD**: Token-Usage wird nach jeder Generation in der Sidebar angezeigt

---

## ✅ Phase 2 — Output Functions: DraftAgent (abgeschlossen)

**Ziel**: Writing-Pipeline auf echten Agent umstellen. `DraftProcessor` wird Output Function.

### Tasks

#### ✅ 2.1 Output Types definieren (Core Specialist)

Strukturierte Output-Types für den Draft-Prozess:

```python
class DraftOutput(BaseModel):
    """Strukturierter Output eines Draft-Agent-Durchlaufs."""

    text: str
    title: str | None = None
    scene_breaks: list[int] = []  # indices of scene breaks
    word_count: int = 0
    metadata: dict[str, Any] = {}

class DraftConfig(BaseModel):
    """Konfiguration für einen Draft-Durchlauf."""

    mode: Literal["full_draft", "scene_by_scene", "interview_assisted"]
    tone: str | None = None
    max_tokens: int = 8192
```

**Layer**: Core
**DoD**: Pydantic-Modelle definiert und getestet

#### ✅ 2.2 DraftAgent definieren (Core Specialist)

```python
class DraftDeps:
    """Dependencies für den DraftAgent."""
    context_assembler: ContextAssemblerProtocol
    preference_service: PreferenceServiceProtocol
    kb_service: KBAgent  # Phase 3 — in Phase 2 noch manuell

class DraftAgent(NarrareAgent[DraftDeps, DraftOutput]):
    """Agent für Kapitel-Generierung.

    Nutzt:
    - Output Function für Post-Processing (ersetzt DraftProcessor)
    - Tool für KB-Kontext-Abfrage
    - Capabilities: Thinking (optional), NarrareObservability
    """

    def __init__(self, model: Model):
        super().__init__(
            model=model,
            deps_type=DraftDeps,
            output_type=[self._process_draft_output, str],
            # str als Fallback: wenn Modell keinen strukturierten Output liefert
        )

    @agent.output_function
    async def _process_draft_output(
        self,
        ctx: RunContext[DraftDeps],
        text: str,
        title: str | None = None,
    ) -> DraftOutput:
        """Output Function — Post-Processing + Validierung.

        Führt die Logik des bisherigen DraftProcessor aus:
        - Artifact-Removal
        - Markdown-Normalisierung
        - Word-Count-Berechnung
        """
        if ctx.partial_output:
            return DraftOutput(text=text)

        # Vollständige Verarbeitung nur beim finalen Output
        cleaned = remove_artifacts(text)
        normalized = normalize_markdown(cleaned)

        return DraftOutput(
            text=normalized,
            title=title,
            word_count=count_words(normalized),
        )

    @agent.tool
    async def get_kb_context(
        self,
        ctx: RunContext[DraftDeps],
        entity_names: list[str],
    ) -> str:
        """Tool: Hole KB-Kontext für die genannten Entitäten.

        Wird vom Modell gerufen, wenn es Details zu Charakteren,
        Orten oder anderen KB-Entitäten benötigt.
        """
        return await ctx.deps.context_assembler.get_kb_context(entity_names)

    @agent.output_validator
    async def validate_draft(
        self,
        ctx: RunContext[DraftDeps],
        output: DraftOutput | str,
    ) -> DraftOutput | str:
        """Output-Validator: Qualitäts-Checks.

        Nur auf finalem Output ausführen (nicht auf Partial-Streams).
        """
        if ctx.partial_output or isinstance(output, str):
            return output

        if output.word_count < 50:
            raise ModelRetry(
                "Der Draft ist zu kurz (< 50 Wörter). "
                "Bitte schreibe einen vollständigen Kapitel-Entwurf."
            )

        return output
```

**Integration mit ModelRegistry**:
```python
# In writing/service.py:
model = await registry.get_model(config, usage_limits=usage_limits)
agent = DraftAgent(model)
result = await agent.run(prompt, deps=DraftDeps(...))
```

**Layer**: Core
**DoD**:
- `DraftAgent` generiert Kapitel mit strukturiertem Output
- Output Function führt dieselbe Logik wie bisheriger `DraftProcessor` aus
- `ModelRetry` aus Validator führt zu erneuten LLM-Calls
- Streaming funktioniert (Partial→Final-Unterscheidung via `ctx.partial_output`)

#### ✅ 2.3 Alte Pipeline als Kompatibilitätsschicht (Core Specialist)

Die alte `WritingPipeline` wird zum **Wrapper**:
```python
# pipeline.py — Legacy-Wrapper
class WritingPipeline:
    def __init__(self, registry: ModelRegistry):
        self._registry = registry

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        # Feature-Flag: old_pipeline = False (default)
        if self._use_draft_agent(request):
            agent = DraftAgent(await self._registry.get_model(request.config))
            result = await agent.run(request.prompt, deps=...)
            return self._to_generation_result(result)
        else:
            # Legacy-Pfad (Phase 2/3 parallel)
            return await self._legacy_generate(request)
```

**Layer**: Core
**DoD**: Feature-Flag schaltet zwischen altem und neuem Pipeline-Pfad um

#### ✅ 2.4 Tests für DraftAgent (Platform Specialist)

- Unit-Tests mit `TestModel` + `FunctionModel` (keine echten LLM-Calls)
- Output Function wird korrekt aufgerufen
- Tool `get_kb_context` wird korrekt aufgerufen
- Validator lehnt zu kurze Drafts ab → `ModelRetry`
- Streaming: `ctx.partial_output`-Verhalten korrekt
- Vergleich alt/neu: gleicher Output bei gleichem Input (mit FunctionModel)

**Layer**: Platform
**DoD**: 20+ Tests für DraftAgent, Abdeckung >90%

---

## ✅ Phase 3 — KB-Tools + ToolSearch (abgeschlossen)

**Ziel**: ContextAssembler wird zu einem Toolset. KB-Entity-Zugriff wird dem Modell als Tool angeboten — mit deferred loading via ToolSearch.

### Tasks

#### ✅ 3.1 KBAgent definieren (Core Specialist)

```python
class KBDeps:
    repository: KBCacheProtocol

class KBAgent(NarrareAgent[KBDeps, None]):
    """Agent, der KB-Tools für andere Agents bereitstellt.

    Wird nicht selbst ausgeführt, sondern stellt nur Tools zur Verfügung,
    die von anderen Agents (z.B. DraftAgent) genutzt werden.
    """

    def __init__(self, model: Model):
        super().__init__(model=model, deps_type=KBDeps, output_type=None)

    @agent.tool(defer_loading=True)
    async def search_kb(
        self,
        ctx: RunContext[KBDeps],
        query: str,
        entity_type: str | None = None,
    ) -> list[dict]:
        """Suche in der Wissensdatenbank.

        Args:
            query: Suchbegriff
            entity_type: Optional filter (character, location, ...)
        """
        ...

    @agent.tool(defer_loading=True)
    async def get_entity(
        self,
        ctx: RunContext[KBDeps],
        name: str,
    ) -> dict | None:
        """Hole eine KB-Entität mit vollem Namen.

        Args:
            name: Vollständiger Name der Entität (z.B. "Anna Müller")
        """
        ...

    @agent.tool(defer_loading=True)
    async def get_related_entities(
        self,
        ctx: RunContext[KBDeps],
        entity_name: str,
        relation_type: str | None = None,
    ) -> list[dict]:
        """Finde verwandte Entitäten.

        Args:
            entity_name: Name der Ausgangs-Entität
            relation_type: Optional filter ("appears_in", "knows", ...)
        """
        ...
```

**Layer**: Core
**DoD**: ✅ 3 KB-Tools definiert mit `defer_loading=True` (search_kb, get_entity, get_related_entities)

#### ✅ 3.2 ToolSearch-Capability konfigurieren (Core Specialist)

```python
# In NarrareAgent.__init__():
capabilities.append(
    ToolSearch(strategy="bm25")  # Lokaler Fallback
    # Anthropic/OpenAI nutzen nativ server-executed search
)
```

Provider-Adaptivität:
- **Anthropic + OpenAI**: Native ToolSearch (Server executed)
- **Google, Groq, Ollama**: Lokale BM25-Fallback-Strategie
- `ToolSearch` erkennt automatisch, welche Strategie für das aktuelle Model passt

**Layer**: Core
**DoD**: ✅ ToolSearch-Capability integriert (implementiert mit `strategy="keywords"`)

#### ✅ 3.3 DraftAgent + KBAgent integrieren (Core Specialist)

```python
class DraftAgent(NarrareAgent[DraftDeps, DraftOutput]):
    def __init__(self, model: Model):
        super().__init__(
            model=model,
            deps_type=DraftDeps,
            output_type=[self._process_draft_output, str],
            capabilities=[
                # KBAgent-Tools in DraftAgent einbinden
                Toolset(kb_agent.get_toolset()),
                # KB-Tools sind deferred — das Modell sieht nur
                # die Namen + kurze Beschreibung, nicht die volle Schema
                ToolSearch(strategy="keywords"),
            ],
        )
```

Alternativ: KB-Tools per Capability:
```python
# Noch sauberer: KBAgent als Capability bündeln
capabilities=[
    KBTools(repository=...),  # bündelt 3 KB-Tools
    ToolSearch(),
]
```

**Layer**: Core
**DoD**: ✅ DraftAgent kann KB-Tools nutzen (optionaler `kb_agent`-Parameter), ToolSearch lädt Tools nur bei Bedarf

#### ✅ 3.4 Tests (Platform Specialist)

- KB-Tools mit `FunctionModel` testen
- ToolSearch-Verhalten: TestModel zeigt welche Tools geladen wurden
- Integration: DraftAgent + KB-Tools + ToolSearch
- Vergleich Token-Verbrauch mit/ohne ToolSearch

**Layer**: Platform
**DoD**: ✅ 31 Tests für KB-Tools + ToolSearch (14 KBAgent + 14 KB-Formatters + 3 Integration)

> **Implementation Notes:**
> - KBAgent verwendet `FunctionToolset` (statt nativer pydantic-ai Agent-Tools) mit `defer_loading=True` für alle 3 KB-Tools
> - KB-Format-Logik in eigenem Modul (`kb_formatters.py`) wegen RULE-04 (File-Size-Limit)
> - ToolSearch-Strategie: `"keywords"` (nicht `"bm25"` wie initial geplant — lokaler Keyword-Match)
> - KB-Service ist via `KBDeps.kb_service` injizierbar, aber optional — Tools liefern Fallback-Messages wenn kein Service konfiguriert
> - DraftAgent nimmt `kb_agent: KBAgent | None` als optionalen Parameter (abwärtskompatibel)

---

## ✅ Phase 4 — Pydantic Graph für Writing-Workflows (abgeschlossen)

**Ziel**: Linearer Writing-Flow (Outline → Draft → Review → Revise → Final) als Graph mit State-Persistence.

### Tasks

#### ✅ 4.1 Graph-Zustand definieren (Core Specialist)

- `WritingState` dataclass mit `chapter_id`, `novel_id`, `outline`, `draft`, `revision`, `final`, `status`, `attempts`
- `WritingStatus` enum: `PLANNED`, `OUTLINED`, `DRAFTED`, `IN_REVIEW`, `NEEDS_REVISION`, `APPROVED`, `REVISED`, `COMPLETED`
- `WritingDeps` dataclass für Dependency Injection
- `Decision` typed dict: `Approved` | `NeedsRevision`
- Defined in `core/agents/writing_graph_types.py` (separate module per RULE-04)

**Layer**: Core
**DoD**: ✅ WritingState + WritingStatus + WritingDeps + Decision defined and tested (8 type tests)

#### ✅ 4.2 Graph-Steps definieren (Core Specialist)

5 Graph Nodes via `GraphBuilder` API (pydantic-graph 1.97+):
- `PlanOutline` — outline generation
- `WriteDraft` — draft generation
- `ReviewDraft` — review with decision branching (Approved / NeedsRevision)
- `ReviseDraft` — revision with loop back to WriteDraft (max 3 attempts)
- `Finalize` — finalize approved draft

Decision-Branching:
- `ReviewDraft` returns `Decision` → `Approved` → `Finalize`
- `ReviewDraft` returns `Decision` → `NeedsRevision` → `ReviseDraft`
- `ReviseDraft` → `WriteDraft` loop (max 3 attempts, then force-finalize)

Defined in `core/agents/writing_graph.py` using `GraphBuilder` (NOT deprecated Graph API).

**Layer**: Core
**DoD**: ✅ 5 nodes defined, decision branching works, max-attempts guard tested

#### ✅ 4.3 Graph-Instanz erstellen (Core Specialist)

- `create_writing_graph()` factory using `GraphBuilder`
- Returns `Graph[WritingState, WritingDeps]`
- Mermaid export via `graph.render(title='Writing Graph', direction='LR')`
- Diagramm saved to `docs/architecture/workflows/writing-graph.mermaid`

**Layer**: Core
**DoD**: ✅ Writing-Workflow als Graph modelliert, Mermaid-Diagramm generiert

#### ✅ 4.4 State-Persistence (Backend Specialist)

Deferred to post-MVP. Current implementation uses in-memory state via `WritingState` dataclass.
PostgreSQL-based persistence will be added when graph runs need to survive server restarts.

**Layer**: Backend
**DoD**: ✅ State management works in-memory; persistence deferred

#### ✅ 4.5 Graph-Visualisierung (Docs Specialist)

Mermaid-Diagramm generated via `graph.render(title='Writing Graph', direction='LR')`.
Saved to `docs/architecture/workflows/writing-graph.mermaid`.

**Layer**: Docs
**DoD**: ✅ Mermaid-Diagramm liegt in `docs/architecture/workflows/writing-graph.mermaid`

#### ✅ 4.6 Feature-Flag + paralleler Betrieb (Platform Specialist)

- Feature-Flag `use_writing_graph` in `WritingPipeline` constructor
- Default: `False` (old pipeline path)
- New pipeline path in `core/writing/pipeline_graph.py` (separate module per RULE-04)
- Pipeline integration: `_generate_via_graph()` method with graph-based generation

**Layer**: Platform
**DoD**: ✅ Feature-Flag schaltet zwischen Graph und alter Pipeline um

#### ✅ 4.7 Tests (Platform Specialist)

- 8 type tests: WritingState, WritingStatus, WritingDeps, Decision types
- 11 graph tests: node execution, decision branching, max-attempts guard, loop detection, full pipeline
- 4 pipeline integration tests: feature-flag switching, graph/pipeline fallback
- Total: 23 tests, 0 architecture violations

**Layer**: Platform
**DoD**: ✅ 23 tests (8 Types + 11 Graph + 4 Pipeline), all passing

---

## Task 0.4 — Call-Site-Inventar (nachträglich erstellt)

> Erstellt am 2026-05-20. Vollständiger Scan aller `gateway.run()`, `gateway.stream()`, `registry.get_model()`, `registry.run()` und direkten `Agent()`-Aufrufe (exkl. Tests und `__pycache__`).

### gateway.run() / gateway.stream() Aufrufe (Legacy-Pfad)

| Datei | Zeile | Intent | Migration-Kategorie |
|-------|-------|--------|---------------------|
| `apps/api/narrare/generation/name_service.py` | 82 | Name-Generierung (WRITE intent) | Simple → `Registry.run()` Komfort-Methode |
| `apps/api/narrare/writing/ws_handler.py` | 212 | Writing WebSocket-Streaming | Complex → DraftAgent (Phase 2 erledigt) |
| `apps/api/narrare/writing/_interview_draft.py` | 152 | Interview-Draft-Streaming | Complex → Pipeline nutzt DraftAgent intern |
| `packages/core/narrare_core/writing/pipeline.py` | 238 | Pipeline-Streaming (Legacy-Pfad) | Complex → Feature-Flag steuert Alt/Neu |
| `packages/core/narrare_core/writing/pipeline_scene.py` | 64 | Scene-Pipeline-Streaming (private access) | Complex → Pipeline nutzt DraftAgent intern |
| `packages/core/narrare_core/writing/pipeline_interview.py` | 60 | Interview-Pipeline run (private access) | Complex → Pipeline nutzt DraftAgent intern |
| `packages/core/narrare_core/llm/model_routing.py` | 66 | Model-Routing / Fallback-Test | Simple → `Registry.run()` Komfort-Methode |

### registry.get_model() Aufrufe (Neuer Pfad)

| Datei | Zeile | Agent | Status |
|-------|-------|-------|--------|
| `packages/core/narrare_core/agents/draft_agent.py` | 7 | DraftAgent | ✅ Migriert |
| `packages/core/narrare_core/agents/base.py` | 9 | NarrareAgent (Base) | ✅ Migriert |
| `packages/core/narrare_core/agents/base.py` | 37 | NarrareAgent (Base) | ✅ Migriert |
| `packages/core/narrare_core/agents/writing_graph.py` | 50 | WritingGraph | ✅ Migriert |
| `packages/core/narrare_core/writing/pipeline.py` | 302 | Pipeline → DraftAgent | ✅ Migriert (Feature-Flag-Pfad) |

### Direkte Agent()-Instanziierung

| Datei | Zeile | Status |
|-------|-------|--------|
| `apps/api/narrare/setup/provider_service.py` | 223 | ⚠️ Allowlisted — Setup-Phase Validation (ADR-015 Ausnahme, mit `# narrare: allow-agent` Comment) |
| `packages/core/narrare_core/writing/pipeline.py` | 308 | ✅ `DraftAgent()` — NarrareAgent-Subklasse, korrekte Nutzung |
| `packages/core/narrare_core/llm/gateway.py` | 126 | ⚠️ Legacy-Gateway — intern erlaubt (wird mit Task 5 entfernt) |
| `packages/core/narrare_core/llm/_legacy.py` | 95 | ⚠️ `_LegacyGateway` — intern erlaubt (wird mit Task 5 entfernt) |

### Kategorisierung

- **Simple Calls** (kein Output-Type, kein Tools) → nutzen `Registry.run()` Komfort-Methode
  - `name_service.py` (Name-Generierung)
  - `model_routing.py` (Model-Routing/Fallback)
- **Complex Calls** (Writing-Pipeline) → auf Agent umgestellt ✅
  - `pipeline.py`, `pipeline_scene.py`, `pipeline_interview.py` nutzen intern DraftAgent oder Legacy-Pfad (Feature-Flag-gesteuert)
  - `ws_handler.py`, `_interview_draft.py` rufen Pipeline auf, die ihrerseits DraftAgent nutzt
- **Not migrated** → dokumentieren warum nicht
  - `provider_service.py:223` — Setup-Phase Validation: kein Agent sinnvoll, explizit allowlisted
  - `gateway.py:126`, `_legacy.py:95` — Legacy-Gateway erzeugt intern Agent für Kompatibilität; wird mit Legacy-Entfernung (Task 5) obsolet

---

## Risikobewertung

| Phase | Risiko | Wahrsch. | Impact | Mitigation |
|-------|--------|----------|--------|------------|
| 0 | CI-Tooling schlägt fehl nach RULE-Änderung | Mittel | Niedrig | Vor Merge testen |
| 1 | UsageLimits blockieren legitime Calls | Niedrig | Niedrig | Good Defaults, Logging |
| 2 | DraftAgent produziert anderen Output als alte Pipeline | Mittel | Hoch | Paralleler Betrieb, automatischer Vergleich in Tests |
| 3 | ToolSearch funktioniert nicht mit allen Providern | Mittel | Mittel | Fallback auf BM25 |
| 4 | Graph-Persistence zu langsam | Niedrig | Mittel | Redis-Option bereithalten |

---

## Abhängigkeiten zwischen Phasen

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
  ↑             ↑             ↑             ↑             ↑
  ADR          RULE-01b      DraftAgent    KB-Tools      Graph
  Gateway      Hook-Cap      OutputFunc    ToolSearch    Persistence
  Module-Struktur             Legacy-Wrapper
```

Phasen 1–2 können **teilweise parallel** laufen (Gateway-Umbau beeinträchtigt Hooks nicht).

---

## Layer-Zuordnung (Gesamt)

| Layer | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|-------|---------|---------|---------|---------|---------|
| **Core** | Gateway→Registry, Module Struktur | ✅ UsageLimits, Hooks, Observability | ✅ DraftAgent, Output Types, Output Func | ✅ KB-Tools, KBAgent, ToolSearch, KB-Formatters | ✅ Graph-Steps, Graph-State, Decision-Branching, GraphBuilder |
| **Backend** | Call-Sites prüfen | ✅ | ✅ Service-Integration (Feature-Flag) | Repository-Integration | ✅ Pipeline Integration (use_writing_graph flag) |
| **Frontend** | — | ✅ Token-Usage in Sidebar | — | — | — |
| **Platform** | CI-Checks aktualisieren | — | ✅ DraftAgent-Tests (20 Tests, >90%) | ✅ KB-Tool-Tests (31 Tests: Agent + Formatters + Integration) | ✅ Graph-Tests (23 Tests: 8 Types + 11 Graph + 4 Pipeline) |
| **Docs** | ADR + Plan | — | (dieser PR) | ✅ ADR-015, Glossary, CHANGELOG (dieser PR) | ✅ Mermaid-Diagramm, ADR-015 Plan Update |
