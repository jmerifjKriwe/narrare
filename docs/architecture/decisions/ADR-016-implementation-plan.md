# ADR-016 — Implementation Plan: Prompt Caching Strategy

> **Companion to ADR-016.** Phased implementation plan mit Layer-Zuordnung, Definition of Done und Risikobewertung.
>
> Location: `docs/architecture/decisions/ADR-016-implementation-plan.md`

---

## Übersicht

3 Phasen, aufsteigend nach Komplexität. Jede Phase baut auf der vorherigen auf.

```
Phase 0: 🏗️ Agent-Singletons + Cache-Config in ResolvedModelConfig     ~2 Tage
     ↓
Phase 1: 🔧 Provider-native Cache-Settings (Anthropic, Google) + Verification (OpenAI, Z.AI, Groq) ~3 Tage
     ↓
Phase 2: 📊 Observability + Cache-Hit-Tracking                         ~2 Tage
                                                          ─────────────
                                                    Gesamt: ~7 Tage
```

---

## Phase 0 — Agent-Singletons + Cache-Config

**Ziel:** Agents werden einmal erstellt und wiederverwendet. Cache-Config wird Teil von ResolvedModelConfig.

### Tasks

#### 0.1 Agent-Factory Pattern (Core Specialist)

Erstelle einen Agent-Registry/Cache, der Agent-Instanzen pro Model-Konfiguration cached:

```python
# packages/core/narrare_core/agents/registry.py
class AgentRegistry:
    """Cache für Agent-Instanzen — Singleton pro Model-Konfiguration.

    Stellt sicher, dass derselbe Agent (mit demselben Model, denselben
    Tools, demselben System-Prompt) wiederverwendet wird. Ermöglicht
    Provider-side Prompt-Caching.
    """

    _agents: dict[str, NarrareAgent] = {}

    def get_or_create(
        self,
        agent_type: type[NarrareAgent],
        model: Model,
        **kwargs,
    ) -> NarrareAgent:
        """Get cached agent or create new one."""
        key = f"{agent_type.__name__}:{model.model_id}:{hash(frozenset(kwargs.items()))}"
        if key not in self._agents:
            self._agents[key] = agent_type(model=model, **kwargs)
        return self._agents[key]
```

**Layer**: Core
**DoD**: AgentRegistry erstellt und getestet. DraftAgent, KBAgent nutzen Registry.

#### 0.2 Cache-Settings in ResolvedModelConfig (Core Specialist)

```python
@dataclass
class ResolvedModelConfig:
    provider_name: str
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 2000
    streams: bool = False
    cache_prompts: bool = True  # NEU: Prompt-Caching aktivieren
```

**Layer**: Core
**DoD**: `cache_prompts` Feld in ResolvedModelConfig, Provider-Factories nutzen es.

#### 0.3 Pipeline + Graph auf Agent-Registry umstellen (Core Specialist)

WritingPipeline und WritingGraph nutzen `AgentRegistry.get_or_create()` statt `DraftAgent(model=model)` direkt.

**Layer**: Core
**DoD**: Keine direkte `DraftAgent()`-Instantiation mehr in Pipeline/Graph.

---

## Phase 1 — Provider-native Cache-Settings

**Ziel:** Anthropic- und OpenAI-spezifische Cache-Konfiguration in pydantic-ai ModelSettings.

### Tasks

#### 1.1 Anthropic Cache-Settings (Core Specialist)

```python
# In ModelRegistry.get_model() für provider_name == "anthropic":
from pydantic_ai.models.anthropic import AnthropicModelSettings

model_settings = AnthropicModelSettings(
    anthropic_cache_instructions=True,
    anthropic_cache_tool_definitions=True,
)
```

**Layer**: Core
**DoD**: Anthropic-Anfragen nutzen `anthropic_cache_instructions` und `anthropic_cache_tool_definitions`.

#### 1.2 OpenAI Cache-Verifikation (Core Specialist)

OpenAI cached automatisch — verifiziere dass `cache_read_input_tokens` in Usage-Responses erscheint. Wenn ja, ist kein zusätzlicher Code nötig.

**Layer**: Core
**DoD**: Dokumentierte Bestätigung dass OpenAI Prompt-Caching funktioniert.

#### 1.3 Google Gemini Context Caching (Core Specialist)

Prüfe ob pydantic-ai's GoogleProvider Context Caching unterstützt. Wenn ja, konfiguriere es. Wenn nein, dokumentiere als "Phase 2+ nach pydantic-ai v2".

**Layer**: Core
**DoD**: Google Caching entweder konfiguriert oder als "nicht verfügbar" dokumentiert.

#### 1.4 Z.AI / Groq / OpenRouter / Ollama (Core Specialist)

**Z.AI** (glm-*): Automatisches Context-Caching (implizit, keine Konfiguration nötig). Cache-Hits sichtbar via `usage.prompt_tokens_details.cached_tokens`. Cached tokens zu ~50% des Standardpreises abgerechnet. Siehe https://docs.z.ai/guides/capabilities/cache.

**Groq** und **OpenRouter**: OpenAI-kompatibles Caching (automatisch).

**Ollama**: Kein Caching nötig (lokal, Latenz vernachlässigbar).

**Layer**: Core
**DoD**: Dokumentierte Caching-Strategie pro Provider. Z.AI Cache-Hit-Metrik in Observability Tracking berücksichtigt (zusätzlich zu `cache_read_input_tokens` auch `prompt_tokens_details.cached_tokens` prüfen).

---

## Phase 2 — Observability + Cache-Hit-Tracking

**Ziel:** Cache-Hits sind messbar und in Observability sichtbar.

### Tasks

#### 2.1 Cache-Hit-Metriken in NarrareObservability (Core Specialist)

Erweitere `NarrareObservability.after_model_request()` um Cache-Hit-Tracking:

```python
def after_model_request(self, ctx, request_context, response):
    usage = response.usage
    if hasattr(usage, 'cache_read_input_tokens'):
        record_cache_hit(
            model=request_context.model,
            cache_read_tokens=usage.cache_read_input_tokens,
        )
```

**Layer**: Core
**DoD**: Cache-Hits werden in Metriken sichtbar.

#### 2.2 Cache-Hit-Rate in Token-Display (Frontend Specialist)

Zeige Cache-Hit-Rate in der Token-Usage-Sidebar an (Phase 1 Token-Display erweitern).

**Layer**: Frontend
**DoD**: Cache-Hit-Rate sichtbar in UI.

#### 2.3 Cache-Config in Settings-UI (Frontend Specialist)

`cache_prompts` Toggle in User AI Settings.

**Layer**: Frontend
**DoD**: User kann Caching ein-/ausschalten.

---

## Risikobewertung

| Phase | Risiko | Wahrsch. | Impact | Mitigation |
|-------|--------|----------|--------|------------|
| 0 | Agent-Singletons nicht thread-safe | Niedrig | Hoch | Lock-free Dict, keine Mutation nach Erstellung |
| 0 | Memory-Leak durch viele Agent-Instanzen | Niedrig | Mittel | LRU-Cache oder Key-basiertes Cleanup |
| 1 | pydantic-ai unterstützt nicht alle Cache-Features | Mittel | Niedrig | Fallback auf "kein Caching" |
| 1 | Anthropic 4-Block-Limit überschritten | Niedrig | Mittel | Cache nur system+tools, nicht messages |
| 2 | Cache-Hits falsch gemessen | Niedrig | Niedrig | Vergleich mit Provider-Dashboard |

---

## Layer-Zuordnung

| Layer | Phase 0 | Phase 1 | Phase 2 |
|-------|---------|---------|---------|
| **Core** | AgentRegistry, Cache-Settings in ResolvedModelConfig, Pipeline umgestellt | Anthropic/OpenAI/Google Cache-Settings | Observability Cache-Hit-Tracking |
| **Backend** | — | — | — |
| **Frontend** | — | — | Cache-Hit-Rate + Toggle |
| **Platform** | AgentRegistry Tests, Pipeline Tests | Provider-spezifische Tests | Observability Tests |
| **Docs** | ADR-016, Glossary | Provider-Caching-Doku | — |

---

## Abhängigkeiten

- **Voraussetzung:** ADR-015 vollständig implementiert ✅
- **Blockiert von:** Task 7 (KBAgent mit echtem KB-Service) — Cache-Hit-Rate ist irrelevant wenn KB-Tools nicht funktionieren

---

## Wichtige Hinweise für die Implementierung

1. **Keine echten LLM-Calls in Tests** — `TestModel` für Unit-Tests
2. **Provider-Cache-Features sind pydantic-ai-Version-spezifisch** — v1.97.0 prüfen
3. **Agent-Singletons müssen immutable sein nach Erstellung** — keine Mutation von model, tools, system_prompt nach Instanziierung
4. **Memory-Management** — AgentRegistry sollte nicht unendlich wachsen. Überlege ein `max_size` oder TTL-basiertes Cleanup
5. **Kein `--no-verify` bei Commits** — alle Pre-Commit Hooks müssen bestehen
