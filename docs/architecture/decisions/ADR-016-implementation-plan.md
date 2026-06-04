# ADR-016 — Implementation Plan: Prompt Caching Strategy

> **Companion to ADR-016.** Phased implementation plan mit Layer-Zuordnung,
> Definition of Done und Risikobewertung.
>
> Location: `docs/architecture/decisions/ADR-016-implementation-plan.md`

---

## Übersicht

4 Phasen, aufsteigend nach Komplexität. Jede Phase baut auf der vorherigen auf.

```
Phase 0: 🏗️ AgentRegistry Singleton Cache                      ~2-3 Tage
     ↓
Phase 1: ⚙️ CacheSettings in ResolvedModelConfig + Provider ModelSettings  ~3-4 Tage
     ↓
Phase 2: 📊 Cache-Hit Observability (Prometheus-compatible metrics + OpenTelemetry spans per ADR-031)     ~2-3 Tage
     ↓
Phase 3: 🕸️ WritingGraph Integration (Agent-Reuse über Steps)  ~3-4 Tage
                                                      ─────────────
                                            Gesamt: ~10-14 Tage
```

**Prerequisite**: ADR-015 Phases 0–4 abgeschlossen. `NarrareAgent`, `ModelRegistry`,
`WritingGraph`, alle Agent-Definitionen existieren und sind getestet.

---

## Phase 0 — AgentRegistry Singleton Cache

**Ziel**: `AgentRegistry` als zentraler Cache für Agent-Instanzen. Statt pro Request
einen neuen Agent zu instanziieren, wird ein Singleton pro `(agent_type, model_config_hash)`
gecacht und wiederverwendet.

### Root Cause

Aktuell wird jeder Agent pro Request neu instanziiert (z.B. `DraftAgent(model=model)` in
jedem Graph-Step). Das bedeutet:
- System-Prompts + Tool-Definitionen werden bei jedem Request vollständig gesendet
- Provider können keine Cache-Hits erkennen (neue HTTP-Connection, kein Cache-Key)
- Bei WritingGraph (6 Steps, davon 4 mit LLM-Calls) wird derselbe System-Prompt +
  Tool-Satz 2–4× pro Kapitel gesendet

Die **Ursache** ist nicht "fehlendes Caching" sondern "fehlende Agent-Identität über
Requests hinweg". Agent-Singletons ermöglichen den Providern, System-Prompts und
Tool-Definitionen als identisch zu erkennen und automatisch zu cachen.

### Tasks

#### 0.1 AgentRegistry Contract definieren (Core Specialist)

**Contract-First (RULE-03)**: Protocol in `core/agents/contracts.py` vor Implementation.

```python
# packages/core/narrare_core/agents/contracts.py

@runtime_checkable
class AgentRegistryProtocol(Protocol):
    """Contract for the Agent Registry — singleton cache for Agent instances.

    Provides get_or_create() factory with TTL-based cleanup and max_size limits.
    Thread-safe via asyncio.Lock.

    See ADR-016 Phase 0.
    """

    async def get_or_create(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        *,
        deps_type: type[Any] | None = None,
        output_type: Any | None = None,
        capabilities: list[Any] | None = None,
        system_prompt: str | None = None,
        **agent_kwargs: Any,
    ) -> NarrareAgent[Any, Any]:
        """Get cached agent or create a new one.

        Cache key: (agent_type.__qualname__, id(model), system_prompt or "")

        If an agent with matching key exists and is not expired, return it.
        Otherwise create a new one, cache it, and return it.

        Args:
            agent_type: The NarrareAgent subclass to instantiate.
            model: The Model instance (from ModelRegistry).
            deps_type: Dependencies type for the agent.
            output_type: Output specification.
            capabilities: Additional capabilities.
            system_prompt: System prompt (part of cache key).
            **agent_kwargs: Additional keyword arguments for the agent constructor.

        Returns:
            Cached or freshly created NarrareAgent instance.
        """
        ...

    async def invalidate(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        *,
        system_prompt: str | None = None,
    ) -> bool:
        """Remove a specific agent from the cache.

        Returns True if an agent was removed, False if not found.
        """
        ...

    async def clear(self) -> int:
        """Remove all cached agents. Returns count of removed agents."""
        ...

    @property
    def size(self) -> int:
        """Current number of cached agents."""
        ...
```

**Layer**: Core
**DoD**: Protocol in `contracts.py` definiert, TYPE-CHECKING-Imports korrekt.

#### 0.2 AgentRegistry implementieren (Core Specialist)

Datei: `packages/core/narrare_core/agents/registry.py` (neu)

```python
@dataclass
class _CacheEntry:
    """Internal cache entry with TTL tracking."""
    agent: NarrareAgent[Any, Any]
    created_at: float  # time.monotonic()
    last_accessed: float  # time.monotonic()


class AgentRegistry:
    """Singleton cache for NarrareAgent instances.

    Cache key: (agent_type.__qualname__, id(model), system_prompt or "")
    - id(model) is safe because Model instances from ModelRegistry are
      unique per (provider_name, model_id, credentials) combination.

    Memory management:
    - max_size: Maximum cached agents (default 50). LRU eviction when exceeded.
    - ttl_seconds: Time-to-live for idle agents (default 300 = 5min).
      Expired entries are cleaned up on next get_or_create() or explicit cleanup.

    Thread safety:
    - asyncio.Lock for all mutations (dict writes, cleanup).
    - Reads are lock-free (dict is thread-safe for reads in CPython).

    Immutability guarantee:
    - Agents returned from get_or_create() MUST NOT be mutated after creation.
      No changes to model, tools, system_prompt, or capabilities.
      This is enforced by convention + documented in agent docstrings.
    """

    def __init__(
        self,
        *,
        max_size: int = 50,
        ttl_seconds: float = 300.0,
    ) -> None:
        self._cache: dict[tuple[str, int, str], _CacheEntry] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

    def _cache_key(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        system_prompt: str | None,
    ) -> tuple[str, int, str]:
        return (agent_type.__qualname__, id(model), system_prompt or "")

    async def get_or_create(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        *,
        deps_type: type[Any] | None = None,
        output_type: Any | None = None,
        capabilities: list[Any] | None = None,
        system_prompt: str | None = None,
        **agent_kwargs: Any,
    ) -> NarrareAgent[Any, Any]:
        key = self._cache_key(agent_type, model, system_prompt)
        now = time.monotonic()

        # Fast path: check cache without lock
        entry = self._cache.get(key)
        if entry is not None and (now - entry.last_accessed) < self._ttl_seconds:
            entry.last_accessed = now
            return entry.agent

        # Slow path: create or recreate under lock
        async with self._lock:
            # Double-check after acquiring lock
            entry = self._cache.get(key)
            if entry is not None and (now - entry.last_accessed) < self._ttl_seconds:
                entry.last_accessed = now
                return entry.agent

            # Cleanup if at capacity
            await self._cleanup_locked()

            # Create new agent
            kwargs: dict[str, Any] = {"model": model}
            if deps_type is not None:
                kwargs["deps_type"] = deps_type
            if output_type is not None:
                kwargs["output_type"] = output_type
            if capabilities is not None:
                kwargs["capabilities"] = capabilities
            if system_prompt is not None:
                kwargs["system_prompt"] = system_prompt
            kwargs.update(agent_kwargs)

            agent = agent_type(**kwargs)
            self._cache[key] = _CacheEntry(
                agent=agent,
                created_at=now,
                last_accessed=now,
            )
            return agent

    async def _cleanup_locked(self) -> None:
        """Remove expired + LRU entries. Must be called under self._lock."""
        now = time.monotonic()

        # Remove expired entries
        expired_keys = [
            k for k, v in self._cache.items()
            if (now - v.last_accessed) >= self._ttl_seconds
        ]
        for k in expired_keys:
            del self._cache[k]

        # If still at capacity, remove oldest (LRU)
        while len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].last_accessed)
            del self._cache[oldest_key]

    async def invalidate(
        self,
        agent_type: type[NarrareAgent[Any, Any]],
        model: Model,
        *,
        system_prompt: str | None = None,
    ) -> bool:
        key = self._cache_key(agent_type, model, system_prompt)
        async with self._lock:
            return self._cache.pop(key, None) is not None

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    @property
    def size(self) -> int:
        return len(self._cache)
```

**Design-Entscheidungen**:

| Entscheidung | Begründung |
|-------------|-----------|
| Cache-Key: `(qualname, id(model), system_prompt)` | `id(model)` ist sicher weil Model-Instanzen pro `(provider, model_id, credentials)` einzigartig sind. `system_prompt` ist Teil des Keys weil verschiedene Prompts verschiedene Agent-Instanzen erfordern. |
| `max_size=50` | Conservativ: bei 10 Agent-Typen × 5 Model-Konfigurationen = 50 Einträge. Übersteigbar falls nötig. |
| `ttl_seconds=300` (5min) | Entspricht Anthropic's Cache-TTL (5min minimal). Agent wird nach 5min Inaktivität verworfen. |
| LRU Eviction | Vorhersagbares Verhalten: am längsten nicht verwendete Agents werden zuerst verworfen. |
| `asyncio.Lock` | Nur für Mutationen (write-path). Read-path ist lock-free. |
| Immutability via Convention | Keine Runtime-Enforcement (zu invasiv). Starker Documentation-Contract + Architectural-Review. |

**Layer**: Core
**DoD**:
- `AgentRegistry` implementiert mit `get_or_create()`, `invalidate()`, `clear()`
- TTL-basiertes Cleanup funktioniert
- LRU-Eviction bei `max_size`-Überschreitung
- Thread-safe via `asyncio.Lock`
- Unit-Tests: Cache-Hit, Cache-Miss, TTL-Expiry, LRU-Eviction, Concurrent Access

#### 0.3 AgentRegistry in DI-Integration (Backend Specialist)

Integration in die FastAPI Dependency Injection:

```python
# apps/api/narrare/_app/dependencies.py

from narrare_core.agents.registry import AgentRegistry

# Singleton — eine Instanz pro Process
_agent_registry: AgentRegistry | None = None

def get_agent_registry() -> AgentRegistry:
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry(
            max_size=50,
            ttl_seconds=300.0,
        )
    return _agent_registry

AgentRegistryDep = Annotated[AgentRegistry, Depends(get_agent_registry)]
```

**Layer**: Backend
**DoD**: `AgentRegistryDep` als FastAPI-Dependency verfügbar, Singleton-Lebenszyklus getestet

#### 0.4 Tests für AgentRegistry (Platform Specialist)

- Unit-Tests mit `TestModel` (keine echten LLM-Calls)
- Cache-Hit: Gleicher Key → gleiche Instanz
- Cache-Miss: Verschiedener Key → neue Instanz
- TTL-Expiry: Agent nach TTL wird neu erstellt
- LRU-Eviction: Älteste Agents werden bei `max_size` verworfen
- Concurrent Access: Mehrere Coroutinen gleichzeitig → keine Race-Conditions
- `invalidate()` und `clear()` funktionieren korrekt

**Layer**: Platform
**DoD**: 15+ Tests, Coverage >90% für `registry.py`

---

## Phase 1 — CacheSettings in ResolvedModelConfig + Provider ModelSettings

**Ziel**: Provider-spezifische Cache-Konfiguration in `ResolvedModelConfig` aufnehmen
und in `ModelRegistry.get_model()` an die Provider-Factory weiterreichen.

### Root Cause

Selbst mit Agent-Singletons (Phase 0) müssen Provider explizit über Cache-Präferenzen
informiert werden:
- **Anthropic**: `cache_control=True` in `AnthropicModelSettings` aktiviert
  `cache_control`-Blöcke. Ohne diese Einstellung cacht Anthropic nicht aktiv.
- **Google**: Explicit `cached_contents` API benötigt Cache-Creation.
- **OpenAI / Z.AI / Groq**: Caching funktioniert automatisch bei identischen
  System-Prompts — keine Konfiguration nötig.
- **Ollama**: Kein Caching, Ignorieren.

Die pydantic-ai `ModelSettings`-Abstraktion ist der korrekte Ort: sie ist
Provider-übergreifend und wird bereits von pydantic-ai in Agent-Requests
berücksichtigt.

### Tasks

#### 1.1 CacheSettings definieren (Core Specialist)

Erweiterung von `ResolvedModelConfig` in `core/llm/intents.py`:

```python
@dataclass(frozen=True, slots=True)
class CacheSettings:
    """Prompt caching configuration for a resolved model.

    Provider-specific behavior:
    - Anthropic: Enables cache_control blocks on system prompt + tools.
    - OpenAI / Z.AI / Groq: Ignored (automatic server-side caching).
    - Google: Triggers explicit cached_contents creation.
    - Ollama: Ignored (no caching support).
    - OpenRouter: Forwarded to underlying provider.
    """

    enabled: bool = True
    """Whether prompt caching is enabled for this model configuration."""

    ttl_seconds: int = 300
    """Cache TTL in seconds. Anthropic minimum: 300 (5min)."""

    max_cache_points: int = 4
    """Maximum cache_control blocks per request (Anthropic limit: 4)."""


@dataclass(frozen=True, slots=True)
class ResolvedModelConfig:
    """Fully resolved model configuration ready for the gateway."""
    # ... existing fields ...
    provider_name: str
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 4096
    streams: bool = False
    token_limit_profile: str | None = None
    cache: CacheSettings | None = None  # NEU
```

**Provider-spezifische ModelSettings-Factories**:

```python
# packages/core/narrare_core/llm/_providers/cache_settings.py

def build_model_settings(
    provider_name: str,
    cache: CacheSettings | None,
) -> dict[str, Any]:
    """Build provider-specific ModelSettings kwargs for prompt caching.

    Returns a dict of kwargs to pass to Agent.run(model_settings=...).

    Provider mapping:
    - anthropic: AnthropicModelSettings(cache_control=True)
    - openai / groq / zai: {} (automatic, no config needed)
    - google: {"cached_content": True} (when pydantic-ai supports it)
    - ollama: {} (no caching)
    - openrouter: depends on underlying provider (forwarded)
    """
    if cache is None or not cache.enabled:
        return {}

    match provider_name:
        case "anthropic":
            # pydantic-ai AnthropicModelSettings
            return {"cache_control": True}
        case "google":
            # Google Context Caching — requires pydantic-ai support
            # Fallback: no config until pydantic-ai supports it
            return {}
        case "openai" | "groq" | "zai" | "openrouter":
            # Automatic server-side caching — no config needed
            return {}
        case "ollama":
            # No caching support
            return {}
        case _:
            return {}
```

**Layer**: Core
**DoD**:
- `CacheSettings` als frozen dataclass in `intents.py`
- `ResolvedModelConfig.cache`-Feld hinzugefügt
- `build_model_settings()` implementiert mit Provider-spezifischer Logik
- Unit-Tests für alle 7 Provider

#### 1.2 CacheSettings in ModelRegistry integrieren (Core Specialist)

Anpassung an `ModelRegistry.get_model()` und Konvenient-Methoden:

```python
class ModelRegistry:
    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> Model:
        # ... existing logic ...

    def get_cache_settings(
        self,
        config: ResolvedModelConfig,
    ) -> dict[str, Any]:
        """Build provider-specific ModelSettings for prompt caching.

        Returned as kwargs dict for Agent.run(model_settings=...).
        """
        from narrare_core.llm._providers.cache_settings import build_model_settings
        return build_model_settings(config.provider_name, config.cache)
```

**Anthropic Cache-Control Integration**:

Für Anthropic werden `cache_control`-Marker benötigt. pydantic-ai's
`AnthropicModelSettings(cache_control=True)` setzt automatisch
`cache_control` auf System-Prompt + Tool-Definitionen.

Anthropic Limit: **max 4 `cache_control`-Blöcke**. Unsere Strategie:
- Cache Block 1: System-Prompt (~800 tokens)
- Cache Block 2: Tool-Definitionen (~1.200 tokens)
- Cache Blocks 3–4: Reserviert für zukünftige Nutzung (z.B. langer KB-Kontext)

**Layer**: Core
**DoD**:
- `get_cache_settings()` auf ModelRegistry verfügbar
- Anthropic `cache_control=True` wird korrekt gesetzt
- OpenAI / Z.AI / Groq: Keine Settings (automatisch)
- Ollama: Keine Settings (kein Caching)
- Tests mit `TestModel` für alle Provider

#### 1.3 AgentRegistry + CacheSettings kombinieren (Core Specialist)

Die `AgentRegistry.get_or_create()` Methode muss CacheSettings an den Agent
weiterreichen. Entweder via `model_settings` in `run()` oder via Agent-Constructor.

Design-Entscheidung: **CacheSettings via `model_settings` in `agent.run()`**, nicht
im Constructor. Grund: `model_settings` sind per-Request, nicht per-Agent. Der Agent
bleibt immutable — nur der Run-Aufruf bekommt die Settings.

```python
# Usage in WritingGraph:
agent = await agent_registry.get_or_create(
    DraftAgent,
    model=model,
    deps_type=DraftDeps,
    system_prompt=system_prompt,
)
cache_kwargs = registry.get_cache_settings(deps.model_config)
result = await agent.run(prompt=user_prompt, deps=deps, **cache_kwargs)
```

**Layer**: Core
**DoD**: CacheSettings fließen korrekt von `ResolvedModelConfig` über `ModelRegistry`
zu `agent.run()`.

#### 1.4 Tests für CacheSettings (Platform Specialist)

- `CacheSettings`-Defaults korrekt
- `build_model_settings()` liefert richtige Werte für jeden Provider
- Integration: `ModelRegistry.get_cache_settings()` → `agent.run()`
- Anthropic: `cache_control=True` wird gesetzt
- OpenAI: Leeres Dict (automatisch)
- Ollama: Leeres Dict (kein Caching)

**Layer**: Platform
**DoD**: 10+ Tests, Coverage >90% für `cache_settings.py`

---

## Phase 2 — Cache-Hit Observability

**Ziel**: Cache-Hit/Miss-Tracking in Prometheus + Langfuse. Ermöglicht Messung der
effektiven Cache-Rate und Kostenersparnis.

### Root Cause

Ohne Observability können wir nicht messen, ob Prompt Caching tatsächlich funktioniert.
Anthropic und OpenAI liefern Cache-Statistiken in ihren Usage-Responses:
- Anthropic: `cache_read_input_tokens`, `cache_creation_input_tokens`
- OpenAI: `cache_read_input_tokens` in `usage.prompt_tokens_details`
- Z.AI: `usage.prompt_tokens_details.cached_tokens`

Diese Werte müssen extrahiert, getrackt und in Dashboards sichtbar gemacht werden.

### Tasks

#### 2.1 Cache-Metrisken in Prometheus (Core Specialist)

Erweiterung von `core/llm/metrics.py`:

```python
# Neue Prometheus-Metriken

llm_cache_read_tokens_total = Counter(
    "narrare_llm_cache_read_tokens_total",
    "Total tokens served from cache (cache hits)",
    ["intent", "model", "provider"],
)

llm_cache_creation_tokens_total = Counter(
    "narrare_llm_cache_creation_tokens_total",
    "Total tokens written to cache (cache writes)",
    ["intent", "model", "provider"],
)

llm_cache_hit_total = Counter(
    "narrare_llm_cache_hit_total",
    "Total LLM requests that had cache hits",
    ["intent", "model", "provider"],
)

llm_cache_miss_total = Counter(
    "narrare_llm_cache_miss_total",
    "Total LLM requests with no cache hits",
    ["intent", "model", "provider"],
)
```

Neue Recording-Funktion:

```python
def record_cache_usage(
    *,
    intent: str,
    model: str,
    provider: str,
    cache_read_tokens: int,
    cache_creation_tokens: int,
) -> None:
    """Record cache hit/miss statistics from an LLM call."""
    if cache_read_tokens > 0:
        llm_cache_hit_total.labels(
            intent=intent, model=model, provider=provider,
        ).inc()
        llm_cache_read_tokens_total.labels(
            intent=intent, model=model, provider=provider,
        ).inc(cache_read_tokens)

    if cache_creation_tokens > 0:
        llm_cache_creation_tokens_total.labels(
            intent=intent, model=model, provider=provider,
        ).inc(cache_creation_tokens)

    if cache_read_tokens == 0 and cache_creation_tokens == 0:
        llm_cache_miss_total.labels(
            intent=intent, model=model, provider=provider,
        ).inc()
```

**Layer**: Core
**DoD**: Prometheus-Metriken definiert, Recording-Funktion implementiert.

#### 2.2 Cache-Statistiken aus Usage extrahieren (Core Specialist)

Erweiterung von `TokenUsage` und `NarrareObservability`:

```python
# core/llm/result.py — TokenUsage erweitern
@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    provider: str = ""
    model: str = ""
    # NEU: Cache-Statistiken
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
```

```python
# agents/capabilities/observability.py — Cache-Tracking in Hooks
class NarrareObservability(AbstractCapability):
    async def after_model_request(self, ctx, *, request_context, response):
        # ... existing token tracking ...

        # Cache-Statistiken extrahieren
        cache_read = getattr(ctx.usage, "cache_read_input_tokens", 0) or 0
        cache_creation = getattr(ctx.usage, "cache_creation_input_tokens", 0) or 0

        token_usage = TokenUsage(
            prompt_tokens=ctx.usage.input_tokens or 0,
            completion_tokens=ctx.usage.output_tokens or 0,
            total_tokens=ctx.usage.total_tokens or 0,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )

        # Cache-Metriken aufzeichnen
        if cache_read > 0 or cache_creation > 0:
            record_cache_usage(
                intent=self._intent or "unknown",
                model=self._model_id or "unknown",
                provider=self._provider_name or "unknown",
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
            )

        record_success(...)
        return response
```

**Hinweis**: pydantic-ai's `RunUsage` hat `details: dict[str, int]` für Provider-spezifische
Metriken. Cache-Statistiken sind dort zu finden (z.B. `details["cache_read_input_tokens"]`).
Die genaue Struktur muss mit der verwendeten pydantic-ai-Version abgeglichen werden.

**Layer**: Core
**DoD**:
- `TokenUsage` hat `cache_read_tokens` und `cache_creation_tokens` Felder
- `NarrareObservability` extrahiert Cache-Statistiken aus Usage
- Cache-Metriken werden bei jedem LLM-Call aufgezeichnet

#### 2.3 Cache-Statistiken in Langfuse (Core Specialist)

Erweiterung von `core/llm/observability.py`:

```python
class LLMObservability:
    def finish_trace(self, trace_context, result_text, usage, duration_ms):
        # ... existing logic ...
        generation.end(
            output=result_text[:2000],
            usage={
                "input": usage.prompt_tokens,
                "output": usage.completion_tokens,
                "total": usage.total_tokens,
                # NEU: Cache-Statistiken
                "cache_read": usage.cache_read_tokens,
                "cache_creation": usage.cache_creation_tokens,
            },
            metadata={
                "duration_ms": duration_ms,
                "cache_savings_pct": (
                    round(usage.cache_read_tokens / max(usage.prompt_tokens, 1) * 100, 1)
                    if usage.cache_read_tokens > 0 else 0
                ),
            },
        )
```

**Layer**: Core
**DoD**: Langfuse zeigt Cache-Statistiken in Generation-Traces.

#### 2.4 Tests für Cache-Observability (Platform Specialist)

- `record_cache_usage()` schreibt korrekte Prometheus-Metriken
- `TokenUsage` mit Cache-Feldern serialisierbar
- `NarrareObservability` extrahiert Cache-Statistiken aus Mock-Usage
- Langfuse-Trace enthält Cache-Metadaten
- Integration: Agent-Run → Observability → Prometheus + Langfuse

**Layer**: Platform
**DoD**: 10+ Tests, Cache-Observability vollständig getestet.

---

## Phase 3 — WritingGraph Integration (Agent-Reuse über Steps)

**Ziel**: WritingGraph nutzt AgentRegistry für Agent-Reuse über Steps hinweg.
Dasselbe DraftAgent-Instanz wird für `write_draft` und `revise_draft` wiederverwendet.

### Root Cause

Nach Phase 0–2 haben wir die Infrastruktur (AgentRegistry, CacheSettings, Observability).
Jetzt muss sie in der WritingGraph tatsächlich genutzt werden. Aktuell instanziiert jeder
Graph-Step seinen Agent frisch:

```python
# writing_graph.py — aktueller Code
agent = DraftAgent(model=model, system_prompt=system_prompt)  # JEDER Step: neue Instanz
```

Nach dieser Phase:

```python
# writing_graph.py — neuer Code
agent = await deps.agent_registry.get_or_create(
    DraftAgent,
    model=model,
    deps_type=DraftDeps,
    system_prompt=system_prompt,
)
```

### Tasks

#### 3.1 WritingDeps um AgentRegistry erweitern (Core Specialist)

```python
# writing_graph_types.py
@dataclass
class WritingDeps:
    registry: Any  # ModelRegistry
    composer: Any = None
    context_assembler: Any = None
    model_config: Any = None
    agent_registry: Any = None  # NEU: AgentRegistry
    # ... rest ...
```

**Layer**: Core
**DoD**: `WritingDeps.agent_registry`-Feld vorhanden, abwärtskompatibel (`None`-Default).

#### 3.2 Graph-Steps auf AgentRegistry umstellen (Core Specialist)

Alle Graph-Steps in `writing_graph.py` umstellen:

```python
# Vorher (jeder Step):
model = await get_model(ctx.deps)
agent = DraftAgent(model=model, system_prompt=system_prompt)

# Nachher (mit AgentRegistry):
model = await get_model(ctx.deps)
if ctx.deps.agent_registry is not None:
    agent = await ctx.deps.agent_registry.get_or_create(
        DraftAgent,
        model=model,
        deps_type=DraftDeps,
        system_prompt=system_prompt or None,
        word_target=ctx.deps.word_target,
    )
else:
    agent = DraftAgent(model=model, system_prompt=system_prompt)
```

**Betroffene Steps**:
- `plan_outline`: `OutlineAgent` → via Registry
- `write_draft`: `DraftAgent` → via Registry (wird auch in `revise_draft` wiederverwendet)
- `review_draft`: `ReviewAgent` → via Registry
- `revise_draft`: `DraftAgent` → via Registry (Cache-Hit: dieselbe Instanz wie `write_draft`)
- `generate_summary`: `ChapterSummaryAgent` → via Registry

**Cache-Settings durchreichen**:

```python
# Cache-Settings für agent.run()
cache_kwargs = ctx.deps.registry.get_cache_settings(ctx.deps.model_config)
result = await agent.run(prompt=user_prompt, deps=deps, **cache_kwargs)
```

**Abwärtskompatibilität**: Wenn `agent_registry is None` → Fallback auf direkte
Instanziierung (altes Verhalten). Ermöglicht schrittweise Migration.

**Layer**: Core
**DoD**:
- Alle 5 Graph-Steps nutzen `AgentRegistry` (wenn verfügbar)
- Fallback auf direkte Instanziierung (wenn `agent_registry is None`)
- `DraftAgent` wird zwischen `write_draft` und `revise_draft` wiederverwendet
- Cache-Settings fließen in jeden `agent.run()`-Aufruf

#### 3.3 Backend-Integration: AgentRegistryDep in Services (Backend Specialist)

Die Backend-Services, die `WritingDeps` konstruieren, müssen `AgentRegistry` injizieren:

```python
# apps/api/narrare/writing/service.py (oder pipeline_graph.py)
from narrare._app.dependencies import AgentRegistryDep

async def _build_writing_deps(
    self,
    registry: ModelRegistry,
    agent_registry: AgentRegistry,
    # ...
) -> WritingDeps:
    return WritingDeps(
        registry=registry,
        agent_registry=agent_registry,  # NEU
        model_config=config,
        # ...
    )
```

**Layer**: Backend
**DoD**: `WritingDeps` wird mit `AgentRegistry`-Instanz konstruiert. Tests zeigen Cache-Hits.

#### 3.4 End-to-End Tests (Platform Specialist)

- WritingGraph mit AgentRegistry: `DraftAgent` wird nur einmal instanziiert für
  `write_draft` + `revise_draft`
- Cache-Hit-Szenario: 2. `DraftAgent.run()` zeigt Cache-Statistiken
- Fallback: WritingGraph ohne AgentRegistry funktioniert wie bisher
- TokenUsage enthält Cache-Statistiken nach Graph-Run
- Integration: ModelRegistry → AgentRegistry → WritingGraph → Observability

**Layer**: Platform
**DoD**: 12+ Tests, End-to-End Szenarien abgedeckt.

---

## Risikobewertung

| Phase | Risiko | Wahrsch. | Impact | Mitigation |
|-------|--------|----------|--------|------------|
| 0 | Agent-Mutation nach Caching verursacht inkonsistentes Verhalten | Niedrig | Hoch | Immutability-Contract + Architectural Review. Agent-Klassen dokumentieren "frozen after init". |
| 0 | Memory-Leak durch zu viele gecachte Agents | Niedrig | Mittel | `max_size=50` Hard-Limit + TTL-Cleanup + Prometheus-Alert auf `size`-Metrik. |
| 1 | pydantic-ai `AnthropicModelSettings` API ändert sich | Mittel | Mittel | `build_model_settings()` isoliert Provider-Logik. Bei Breaking Change: nur eine Datei ändern. |
| 1 | Anthropic `cache_control` wird nicht korrekt gesetzt | Niedrig | Mittel | Integration-Test mit echtem Anthropic-Call (optional, manuell). |
| 2 | Cache-Statistiken in pydantic-ai `RunUsage` nicht verfügbar | Mittel | Niedrig | Fallback: `details`-Dict prüfen. Wenn nicht verfügbar: Metriken zeigen 0. |
| 3 | WritingGraph bricht bei `agent_registry=None` | Niedrig | Hoch | Fallback-Pfad ist derselbe Code wie vor Phase 3. Integration-Tests decken beide Pfade ab. |
| 3 | Agent-Reuse über Steps kollidiert mit verschiedenem `system_prompt` | Niedrig | Hoch | `system_prompt` ist Teil des Cache-Keys. Verschiedene Prompts → verschiedene Instanzen. |

---

## Abhängigkeiten zwischen Phasen

```
Phase 0 ──────→ Phase 1 ──────→ Phase 3
  ↑                ↑                ↑
  AgentRegistry    CacheSettings    WritingGraph
  Contract+Impl    Provider-Logic   Integration
                   ↓
               Phase 2 (parallel zu Phase 3 möglich)
                  ↑
               Observability
               Metrics+Langfuse
```

Phase 0 und 1 sind **strikt sequenziell**: AgentRegistry muss existieren bevor
CacheSettings genutzt werden können.

Phase 2 und 3 können **teilweise parallel** laufen: Observability ist unabhängig
von der WritingGraph-Integration. Phase 3 setzt Phase 1 voraus.

---

## Anthropic Cache-Control Limits

Anthropic erlaubt max. **4 `cache_control`-Blöcke** pro Request. Unsere Strategie:

| Block | Inhalt | Tokens (ca.) | Priorität |
|-------|--------|-------------|-----------|
| 1 | System-Prompt | ~800 | Hoch — ändert sich nie pro Session |
| 2 | Tool-Definitionen | ~1.200 | Hoch — ändert sich nie pro Agent-Typ |
| 3 | Reserviert | — | Zukunft: langer KB-Kontext |
| 4 | Reserviert | — | Zukunft: Conversation-History |

**Strategie**: Nur System-Prompt + Tools cachen. Messages werden nie gecacht
(sie ändern sich bei jedem Request).

---

## Provider-Verhalten

| Provider | Caching | API-Control | Token-Savings | Konfiguration |
|----------|---------|-------------|---------------|---------------|
| **Anthropic** | Explicit `cache_control` | `AnthropicModelSettings(cache_control=True)` | ~67% Input-Tokens | Phase 1 |
| **OpenAI** | Automatic server-side | Keine nötig | Automatisch bei identischem System-Prompt | Keine |
| **Z.AI** | Automatic context | Keine nötig | ~50% bei Cache-Hits | Keine |
| **Groq** | Automatic server-side | Keine nötig | Automatisch | Keine |
| **Google** | Explicit `cached_contents` | `cached_contents` API | Provider-abhängig | Phase 1 (vorbereitet) |
| **OpenRouter** | Forwarded | Hängt von Ziel-Provider ab | Hängt von Ziel-Provider ab | Keine |
| **Ollama** | Kein Caching | — | — | Keine |

---

## Layer-Zuordnung (Gesamt)

| Layer | Phase 0 | Phase 1 | Phase 2 | Phase 3 |
|-------|---------|---------|---------|---------|
| **Core** | `agents/contracts.py` (Protocol), `agents/registry.py` (AgentRegistry), `agents/__init__.py` (Export) | `llm/intents.py` (CacheSettings), `llm/_providers/cache_settings.py` (Provider-Logic), `llm/gateway.py` (get_cache_settings) | `llm/metrics.py` (Cache-Metriken), `llm/result.py` (TokenUsage Cache-Felder), `agents/capabilities/observability.py` (Cache-Hooks), `llm/observability.py` (Langfuse Cache) | `agents/writing_graph.py` (Registry-Nutzung), `agents/writing_graph_types.py` (WritingDeps), `agents/writing_graph_prompts.py` (Cache-Settings durchreichen) |
| **Backend** | `_app/dependencies.py` (AgentRegistryDep) | — | — | `writing/service.py` oder `writing/pipeline_graph.py` (WritingDeps mit AgentRegistry) |
| **Platform** | 15+ Tests für AgentRegistry | 10+ Tests für CacheSettings | 10+ Tests für Cache-Observability | 12+ Tests für WritingGraph Integration |

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | Agent-Instanziierung bleibt in `core/agents/`. AgentRegistry lebt in `core/agents/registry.py`. ModelRegistry bleibt in `core/llm/`. |
| RULE-02 | ✅ | Prompts werden weiterhin via PromptComposer gebaut. AgentRegistry cached fertige Agents, baut keine Prompts. |
| RULE-03 | ✅ | `AgentRegistryProtocol` in `contracts.py` vor Implementation. |
| RULE-04 | ✅ | `registry.py` (< 200 Zeilen), `cache_settings.py` (< 150 Zeilen). Modularisierung eingehalten. |
| RULE-05 | ✅ | AgentRegistry ist ein eigenes Modul in `core/agents/`. Keine `_internal`-Cross-Imports. |
| RULE-06 | ✅ | `registry.py` = Agent Cache, `cache_settings.py` = Provider-Cache-Logic, `metrics.py` = Metriken. Eine Verantwortung pro Datei. |
| RULE-07 | ✅ | Dependency: `writing_graph` → `AgentRegistry` → `NarrareAgent` + `Model`. Keine Rückwärts-Imports. |
| RULE-08 | ✅ | Provider-spezifische Settings sind in `cache_settings.py` abstrahiert. Kein direkter Provider-Import außerhalb von `_providers/`. |
| RULE-09 | ✅ | Alle öffentlichen Methoden typannotiert. Kein `Any` in Cache-Key-Logik (ausgenommen DI-Integration). |
| RULE-10 | ✅ | 47+ Tests geplant (15 + 10 + 10 + 12). Coverage-Thresholds: Core 90%. |
| RULE-11 | ✅ | Fehler im Cache-Path werden geloggt und fallen auf Neu-Erstellung zurück (graceful degradation). |
| RULE-12 | ✅ | Service Layer bleibt einzige öffentliche API. AgentRegistry ist ein Implementation-Detail von Core. |
| RULE-13 | ✅ | Streaming/Non-Streaming teilen Interface. Cache funktioniert für beide Modi. |

---

## Sustainability Check

1. **In 3 Monaten noch korrekt?** Ja. Agent-Singletons sind ein etabliertes Pattern.
   pydantic-ai's ModelSettings-API ist stabil. TTL-basiertes Cleanup verhindert veraltete Agents.

2. **Erzeugt sie Kopplung, die sich schwer lösen lässt?** Nein. AgentRegistry ist ein
   optionales Feature (Fallback auf direkte Instanziierung). WritingDeps.agent_registry
   ist `None`-default. Kein Breaking Change bei Entfernung.

3. **Einfachste *korrekte* Lösung?** Ja. Agent-Singletons sind die einzige Lösung,
   die Prompt-Caching ermöglicht, ohne den LLM-Call-Path zu verändern. Alternative
   (Redis-Cache) wäre komplexer und weniger effektiv.

4. **Versteht der nächste Entwickler das Design-Intent?** Ja. Der Code ist explizit:
   "get_or_create" statt "new". Cache-Key-Zusammensetzung ist dokumentiert.
   TTL und max_size sind konfigurierbar und begründet.
