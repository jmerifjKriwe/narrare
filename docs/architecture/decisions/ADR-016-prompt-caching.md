# ADR-016 — Prompt Caching Strategy

> **Status:** ✅ Accepted
> **Date:** 2026-05-20
> **Deciders:** Architecture Agent, Narrare Dev Coordinator
> **Supersedes:** —
> **Related:** ADR-015 (Agents as First-Class Citizens), ADR-031 (observability portions supersede Langfuse references)

---

## Context

Narrare unterstützt 7 LLM-Provider mit unterschiedlichen Caching-Mechanismen. Nach Abschluss von ADR-015 (Agents as First-Class Citizens) werden Agents pro Request neu instanziiert — was Prompt-Caching verhindert. System-Prompts und Tool-Definitionen werden bei jedem Request vollständig gesendet. Bei typischen Writing-Workflows (PlanOutline → WriteDraft → ReviewDraft → ReviseDraft) wird derselbe System-Prompt + Tool-Satz 2–4× pro Kapitel übertragen.

### Provider-Landschaft (7 Provider)

| Provider | Caching-Mechanismus | API-Control |
|----------|-------------------|-------------|
| **Anthropic** (claude-*) | `anthropic_cache`, `anthropic_cache_instructions`, `anthropic_cache_tool_definitions`, `anthropic_cache_messages`, `CachePoint` | max 4 cache_control blocks, TTL 5min/1h |
| **OpenAI** (gpt-*) | Automatisches server-side Prompt Caching | `cache_read_input_tokens` in Usage, kein expliziter API-Control nötig |
| **Google** (gemini-*) | Native Gemini Context Caching | `cached_contents` API — explizite Cache-Creation mit TTL |
| **Groq** (OpenAI-kompatibel) | Automatisches Caching auf Server-Seite (wie OpenAI) | `cache_read_input_tokens` in Usage |
| **OpenRouter** (Proxy) | Forwarded Provider-Caching | Hängt vom Ziel-Provider ab |
| **Ollama** (lokal) | Kein Prompt-Caching | Lokal, Latenz ist vernachlässigbar |
| **Z.AI** (glm-*) | Automatisches Context-Caching (implizit) | `usage.prompt_tokens_details.cached_tokens`, kein expliziter API-Control nötig, ~50% Kostenersparnis bei Cache-Hits |

### Aktuelle Probleme

1. **Agent wird pro Request neu instanziiert** → kein Agent-Level Caching
2. **Keine Cache-Konfiguration** in `ResolvedModelConfig` oder Provider-Factories
3. **Keine Cache-Hit/Miss-Tracking** in Observability
4. **System-Prompts sind statisch** (gut für Caching!) aber Tools werden nicht gecacht
5. **Writing-Graph**: Derselbe System-Prompt + Tool-Satz wird 2–4× pro Kapitel gesendet

### Token-Kosten-Schätzung (bei Anthropic, typischer Writing-Request)

| Komponente | Tokens |
|-----------|--------|
| System-Prompt | ~800 |
| Tool-Definitionen (DraftAgent + KBAgent Tools) | ~1.200 |
| Pro Kapitel (4 Graph-Steps) | 4 × 2.000 = **8.000** Input-Tokens für System+Tools |
| **Mit Caching** | 1 × 2.000 + 3 × Cache-Read (~10% des Preises) = **~2.600** äquivalente Input-Tokens |

---

## Decision Drivers

- **Kosten** — Bei 7 Providern mit unterschiedlichen Preisstrukturen ist Prompt-Caching der größte Kostenhebel
- **Latency** — Cache-Hits reduzieren Time-to-First-Token signifikant
- **Multi-Provider-Komplexität** — Jeder Provider hat andere Caching-Mechanismen
- **ADR-015 Dependency** — Agent-Singletons sind Voraussetzung für effektives Caching
- **MVP-Timing** — MVP hat keine produktiven User, aber die Architektur muss stimmen

---

## Options Considered

### Option A — Provider-native Caching (pro Provider konfigurieren)

Nutze die nativen Caching-Mechanismen jedes Providers: Anthropic `anthropic_cache=True` in ModelSettings, OpenAI/Z.AI/Groq automatisch (Agent muss persistent sein), Google explicit `cached_contents` API, OpenRouter forwarded, Ollama ignorieren.

**Pros:**
- Maximale Kontrolle, volle Provider-Features
- Jeder Provider wird optimal ausgenutzt

**Cons:**
- Hohe Komplexität (7 verschiedene APIs)
- Wartungsaufwand bei Provider-Änderungen
- Testbarkeit schwer (Provider-spezifische Mocks nötig)

### Option B — Agent-Singletons + pydantic-ai ModelSettings (gewählt)

Mache Agents zu Singletons (einmal instanziiert, wiederverwendet). Nutze pydantic-ai's `ModelSettings`-Abstraktion für provider-übergreifende Cache-Konfiguration. Füge `CacheSettings` zu `ResolvedModelConfig` hinzu.

**Pros:**
- Ein Konfigurations-Punkt für alle Provider
- pydantic-ai abstrahiert Provider-Unterschiede bereits
- Agent-Singletons lösen das Kernproblem (Identität über Requests)

**Cons:**
- Weniger fine-grained Control als Option A
- pydantic-ai muss die Provider unterstützen
- Agent-Singletons erfordern Thread-Safety-Überlegungen

### Option C — Redis-Response-Cache (pyai-caching)

Zwischengespeicherte Responses in Redis — komplett provider-unabhängig.

**Pros:**
- Provider-agnostic, funktioniert mit allen Providern
- Keine Änderung an Agent-Architektur nötig

**Cons:**
- Veraltet bei Prompt-Änderungen
- Semantic-Caching ist komplex
- Benötigt Redis-Infrastruktur
- Response-Caching spart weniger als Prompt-Caching (responses sind unterschiedlich, system+tools sind gleich)

---

## Decision

**We choose Option B — Agent-Singletons + pydantic-ai ModelSettings.**

Agent-Singletons sind die wichtigste einzelne Maßnahme: sie ermöglichen Pydantic-ai (und den Providern) System-Prompts und Tool-Definitionen als identisch über Requests hinweg zu erkennen. Provider-native Caching (Anthropic cache_control, OpenAI automatic) greift dann automatisch.

---

## Rationale

ADR-015 hat die Agent-Struktur geschaffen, aber Agents werden noch pro Request instanziiert. Das ist der erste Hebel. Dann kommen provider-spezifische ModelSettings via pydantic-ai. Die pydantic-ai Bibliothek abstrahiert bereits Anthropic (`AnthropicModelSettings`), OpenAI, etc. — wir müssen diese Settings nur konfigurieren.

Option C (Redis-Cache) ist als Ergänzung denkbar, aber nicht als Erstmaßnahme. Die Token-Ersparnis durch Prompt-Caching ist wesentlich größer als durch Response-Caching (system+tools sind bei jedem Request gleich, responses sind unterschiedlich).

Option A bietet maximale Kontrolle, aber Narrare nutzt pydantic-ai als Abstraktionsschicht — Provider-native Caching-Aufrufe würden diese Schicht umgehen. Die bessere Strategie ist, pydantic-ai's eigene ModelSettings zu nutzen, die Provider-Unterschiede bereits abstrahieren.

---

## Consequences

**Positive:**
- Signifikante Kostenreduktion bei Anthropic, OpenAI und Z.AI (größte Kostentreiber)
- Schnellere Time-to-First-Token bei Cache-Hits
- Messbar via `cache_read_input_tokens` in Usage-Stats
- Architektur ist vorbereitet für produktive User

**Negative / Tradeoffs:**
- Agent-Singletons erfordern Thread-Safety / Async-Safety
- Provider-spezifische Settings müssen gewartet werden
- Komplexität in `ModelRegistry.get_model()` steigt

**Constraints introduced:**
- Agent-Instanziierung muss vom Consumer (Pipeline/Graph) zur Registry verschoben werden
- `ResolvedModelConfig` bekommt Cache-Settings
- Agent-Instanzen müssen immutable sein nach Erstellung (keine Mutation von model, tools, system_prompt)

---

## Implementation Plan

Siehe [ADR-016-implementation-plan.md](ADR-016-implementation-plan.md).

Zusammenfassung:
- **Phase 0** (~2-3 Tage): `AgentRegistry` Singleton Cache in `core/agents/registry.py`
- **Phase 1** (~3-4 Tage): `CacheSettings` in `ResolvedModelConfig` + provider-spezifische ModelSettings
- **Phase 2** (~2-3 Tage): Cache-Hit Observability (Prometheus-compatible metrics + OpenTelemetry spans per ADR-031)
- **Phase 3** (~3-4 Tage): WritingGraph Integration (Agent-Reuse über Steps)

---

## Technical Notes

- **Keine echten LLM-Calls in Tests** — `TestModel` für Unit-Tests
- **Provider-Cache-Features sind pydantic-ai-Version-spezifisch** — v1.97.0+ prüfen
- **Agent-Singletons müssen immutable sein nach Erstellung** — keine Mutation von model, tools, system_prompt nach Instanziierung
- **Memory-Management** — `AgentRegistry` hat `max_size=50` + TTL-basiertes Cleanup (5min)
- **Anthropic** hat ein Limit von **4 `cache_control` blocks** — cache nur system+tools, nicht messages

---

## Review Trigger

- [ ] Nach pydantic-ai v2 Release: Kompatibilität mit neuen Caching-Features prüfen. pydantic-ai könnte native Agent-Caching oder erweiterte ModelSettings anbieten, die `build_model_settings()` vereinfachen.
- [ ] Wenn produktive User eintreffen: Cache-Hit-Rate via `narrare_llm_cache_hit_total` / `narrare_llm_cache_miss_total` messen. Ziel: >80% Cache-Hit-Rate bei WritingGraph-Workflows. Wenn Ziel nicht erreicht: Cache-Key-Strategie oder TTL anpassen.
- [ ] Nach AgentRegistry-Implementation: Memory-Usage via `AgentRegistry.size`-Property überwachen. Bei dauerhaft >30 Einträgen: max_size oder TTL anpassen.
- [ ] Wenn Google Context Caching in pydantic-ai integriert wird: `build_model_settings()` für Google-Provider aktivieren (aktuell No-Op).
