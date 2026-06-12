# Content Review CR-08 – Hardcodierte Werte & Konfigurierbarkeit

Audit date: 2026-06-12
Scope: hardcoded values and configurability for token/context budgets, model routing, provider defaults, streaming/retry values, and RULE-18-relevant dependency factories.
Method: graph-first discovery for `TokenBudgetManager`, `TokenLimitsService`, `ModelRegistry`, `ModelRoutingResolverImpl`, Settings, streaming, and provider configuration; required Narrare context loaded; CR-00 through CR-05 and CR-07 baselines reviewed; targeted reads of narrowed source files; literal search used only after graph narrowing for constants/provider strings.

## Root Cause Summary

Narrare has the right configuration vocabulary: user/project model routing exists, token-limit settings have a multi-layer service, model catalog data can be fetched dynamically, and most provider/model values flow through settings or repositories. The remaining root cause is **configuration/effect drift**: several values are exposed or resolved in one layer but are not consumed at the runtime boundary that users expect them to affect.

**Architectural fit:** The sustainable fix is to strengthen existing cascades (`TokenLimitsService`, `ModelRoutingResolverImpl`, provider catalog/cache, and `PromptComposer`/agent boundaries), not to add local constants per feature. Values with user-facing semantics should resolve through user/project settings; operator/platform values should live in `Settings`; truly safe last-resort values can remain code defaults with freshness/diagnostic labels.

**Alternatives considered:**

1. **Treat current constants as resolved because many are constructor defaults.** Rejected: a default is only acceptable when the value is actually wired from the relevant settings layer into production execution.
2. **Move every numeric value into the Web UI.** Rejected: timeouts, fallback model catalogs, and cost rates are operator/platform concerns, not ordinary user preferences.
3. **Bind exposed settings to runtime consumers and classify remaining defaults by layer.** Chosen: this preserves RULE-18, SET-005, and the settings cascade.

---

## 1. Token- und Kontext-Limits

### 1.1 Gefundene Token-Konstanten

| Konstante | Wert | Datei:Zeile | Feature-Scope | Konfigurierbar? | Sinnvoll kalibriert? |
|---|---:|---|---|---|---|
| `TokenBudgetManager.DEFAULT_TOTAL_BUDGET` | 6000 | `packages/core/narrare_core/context/budget.py:59` | Writing input context | Constructor override exists, but production factories instantiate `WritingContextAssembler()` without settings | Partly; UI tier settings do not reach runtime |
| Writing tier percentages | `30/20/25/15/10`, extend `50/15/20/10/5`, rewrite `40/15/25/10/10` | `packages/core/narrare_core/context/budget.py:69-99` | Writing input context | `TokenBudgetManager(tier_overrides=...)` exists, but `WritingContextAssembler.__init__` does not accept/pass overrides | Good defaults; configurable path not wired |
| `AnalysisBudgetManager.DEFAULT_TOTAL_BUDGET` | 6000 | `packages/core/narrare_core/analysis/budget.py:33` | Analysis input context | Constructor only; no settings cascade found | Functional but not user/project calibrated |
| `PROFILE_OUTPUT_LIMITS.quick` | 500 | `packages/core/narrare_core/llm/model_config.py:16-21` | Output profile | Code default/profile | Reasonable for names/suggestions |
| `PROFILE_OUTPUT_LIMITS.balanced` | 2000 | same | Output profile | Code default/profile | Reasonable for chat/moderate structured output |
| `PROFILE_OUTPUT_LIMITS.long_texts` | 8000 | same | Output profile | Code default/profile | Reasonable for common writing/analysis |
| `PROFILE_OUTPUT_LIMITS.comprehensive` | 16000 | same | Output profile | Core-only in several paths; API/frontend profile enums omit it | Needed for consistency; vocabulary drift remains |
| `ResolvedModelConfig.max_tokens` | 4096 | `packages/core/narrare_core/llm/model_config.py:74-77` | Gateway fallback | Operator default via `Settings.default_max_tokens`; not enforced reliably at model boundary | Fallback only; see FIND-001 |
| `ModelRegistry._profile_to_limits()` | request/total token profiles | `packages/core/narrare_core/llm/gateway.py:65-90` | Gateway usage limits | Internal map, not aligned with `PROFILE_OUTPUT_LIMITS`; omits `comprehensive`, includes stale `conservative` | Not an output-token enforcement mechanism |
| `TokenLimitOverrides.output_limit` | 4096 | `apps/api/narrare/settings/token_limits/contracts.py:32` | User/project/operator output setting | Yes in service/API/UI | Not reliably enforced; see FIND-001 |
| `TokenLimitOverrides.tier_percentages` | writing tier defaults | `apps/api/narrare/settings/token_limits/contracts.py:36-44` | User/project context distribution | Exposed in UI/API, but not consumed by `WritingContextAssembler` | ❌ false-control risk; see FIND-012 |
| Consistency chapter cap | 2000 | `apps/api/narrare/settings/token_limits/contracts.py:56`, `settings_model.py:128-132`, `consistency/prompt_builder.py:25-26` | Consistency input context | Operator env + service field; not in response/update schema | Good operator default; user/project exposure incomplete |
| Consistency KB cap | 100 | `apps/api/narrare/settings/token_limits/contracts.py:58`, `settings_model.py:134-138` | Consistency input context | Operator env + service field; not in response/update schema | Good default; user/project exposure incomplete |
| Inline suggest cap | 60 | `apps/api/narrare/writing/deps_suggest.py:36`, `writing/deps_writing.py:73-76` | Low-latency writing suggestions | No; local dependency-factory override | Probably UX-valid, but should be named/configured as low-latency cap |
| Existing names context cap | 500 | `apps/api/narrare/generation/name_service.py:33-35`, `255-264` | Name dedup context | No, code constant | Reasonable; project-size dependent |
| TokenSettings slider max | 16000 | `packages/web/components/studio/editor/TokenSettings.tsx:149-154` | User output setting | UI hard cap; API allows 131072 | Conservative; may hide larger model capacity |

### 1.2 Feature-Output-Limits: Aufgaben-Check

| Funktion | Limit (Tokens) | Max sinnvoller Output | Ausreichend? | Handlungsbedarf |
|---|---:|---|---|---|
| Name generation | `quick=500`; existing names context capped at 500 | Short list + metadata | Usually yes | Keep cap, but consider project config when very large KBs exist |
| Inline suggest | local `max_tokens=60`; `SUGGEST` profile says `quick=500` | 1–3 sentences | Knapp by design | Replace raw `60` with named `inline_suggest_output_limit` or profile sub-cap |
| KB interview / field suggest | `quick=500` | One focused question/field value | Yes | Enforce at model boundary |
| Rewrite alternatives | `long_texts=8000` in authoritative intent defaults; `intent_profiles.py` advisory says `balanced` | Multiple alternatives | Usually yes, but mapping drift | Align profile tables and enforcement |
| Continue / extend | `long_texts=8000` | 500–2500 words | Yes for common cases | Enforce at model boundary; user custom limit honored |
| New chapter / full draft | `long_texts=8000` | 1500–5000 words | Mostly yes | Support custom high output and provider-limit warnings |
| Beta reader | `long_texts=8000` | Detailed report | Yes | Enforce and compare to model limit |
| Consistency check | `comprehensive=16000` | Cross-chapter issue report | Yes in core profile; not user-selectable by profile name | Expose/validate `comprehensive` consistently |

### 1.3 Quartals-Modell-Abgleich

No live network/model catalog calls were made for this audit. Code evidence shows model limits can be fetched from `models.dev` via `get_model_limits()` (`packages/core/narrare_core/llm/cost_rates.py:218-266`) and exposed through `TokenLimitsService.get_model_limits()` (`apps/api/narrare/settings/token_limits/service.py:140-157`). However, no audited runtime path automatically compares the selected output profile/user limit with the selected model's actual output ceiling before invoking the model.

| Modell / Quelle | Max Output (aktuell) | Im Code bekannt? | Ungenutztes Potenzial / Risiko |
|---|---:|---|---|
| `models.dev` cache | Provider/model-specific `limit.output` | Yes through `get_model_limits()` | Not applied to runtime output-limit validation |
| User-selected provider/model | Depends on provider | Provider/model stored in DB settings | Suitability hint exists, but routing still uses user/project model without capability enforcement |
| UI token slider | 16,000 max | Yes in frontend | API allows 131,072; larger-model capacity is inaccessible from this control |
| Unknown/offline provider | Unknown | Graceful `None` | Should warn/label unknown rather than imply calibrated limits |

**Bewertung Token- und Kontext-Limits:** ⭐⭐
**Befunde:** Input and output budget infrastructure exists, but two high-impact runtime gaps remain: output limits are not reliably enforced (FIND-001), and context tier settings exposed in the UI are not wired into the writing context assembler (FIND-012).

---

## 2. Modell-Konfiguration

### 2.1 Hardcodierte Modell-Referenzen

| Fundstelle | Modell-String | Zweck | Sollte konfigurierbar sein? |
|---|---|---|---|
| `apps/api/narrare/_app/settings_model.py:81-83` | `claude-sonnet-4-5-20251020`, `claude-haiku-3-5-20241022`, `text-embedding-3-small` | Operator defaults | Already env-configurable via `Settings`; acceptable code fallback |
| `apps/api/narrare/_app/settings_model.py:88-89` | `gpt-4o-mini`, `text-embedding-3-small` | mem0 defaults | Already operator-configurable; API DI passes them to mem0 |
| `packages/core/narrare_core/memory/mem0_client.py:28-40` | provider default memory models | Last-resort mem0 defaults | Acceptable only as fallback; API override exists |
| `apps/api/narrare/setup/provider_service.py:21-67` | fallback model catalog for 7 providers | Setup model list when provider API unavailable | Should be catalog/cache/settings backed or visibly stale; high change likelihood |
| `packages/core/narrare_core/llm/_providers/registry.py:67-80` | provider inference prefixes | dev/debug provider inference | Acceptable as fallback utility; runtime resolver uses explicit provider |
| `packages/core/narrare_core/llm/cost_rates.py:28-38` | default provider rates | cost-estimate fallback when models.dev unavailable | Operator override exists via `Settings.cost_rates_json`, but core fallback is static |
| `apps/api/narrare/setup/provider_service.py:77`, `110`; setup schemas | `http://localhost:11434` | Ollama default URL | Should default from settings/provider base_url; currently repeated |
| `apps/api/narrare/_app/dependencies_services.py:141-174` | `category="writing"`, max_tokens `4096`, provider inferred from default model | system/background default config | Operator defaults used, but category is a two-branch string and bypasses user/project resolver by design |

### 2.2 Default-Modelle pro Feature

Most user-facing features correctly resolve through `ModelRoutingResolverImpl`: project intent → project category → user intent → user category → user default → configuration error (`apps/api/narrare/settings/model_routing_resolver.py:62-165`). This is strong RULE-18 compliance. Feature-level model suitability is advisory: `get_intent_profile(intent).capability_tier` is stored on `ResolvedModel.recommended_tier`, but it does not constrain or select a model (`model_routing_resolver.py:93-99`, `149-159`, `220-233`).

| Feature | Default-Modell | Aufgaben-Komplexität | Modell passt? | Handlungsbedarf |
|---|---|---|---|---|
| Suggest | user/project cascade | Low | Depends on user's model | Fast/cheap recommendation exists; raw 60-token cap should be named/configurable |
| Continue / Extend | user/project cascade | Medium/high creative | Depends | Keep user control; surface creative-tier recommendation |
| Full draft | user/project cascade | High creative | Depends | Warn if selected model is below recommended tier/output capacity |
| KB interview | user/project cascade | Medium structured | Depends | Balanced-tier recommendation is sufficient |
| Consistency check | user/project cascade | High reasoning | Depends | Reasoning-tier recommendation should become visible/actionable |
| Free assistant | user/project cascade | Variable | Depends | Balanced default is acceptable |
| Background wiki generation | system default config | Medium summarization | Operator-dependent | Route through a named system/default resolver rather than string category branch |

**Bewertung Modell-Konfiguration:** ⭐⭐⭐⭐
**Befunde:** The main runtime path is configurable and RULE-18-aligned. Remaining risks are stale fallback catalogs/default URLs and advisory-only model suitability; no new formal FIND is needed unless fallback catalogs become a production source of truth.

---

## 3. Weitere Magic Numbers & Strings

### 3.1 Gefundene Kandidaten

| Konstante/Wert | Datei:Zeile | Beschreibung | Änderungsrisiko | Konfigurierbar machen? | FIND |
|---|---|---|---|---|---|
| `tier_percentages` exposed in UI/API but not consumed | `ContextBudget.tsx:69-157`, `useAiTabData.ts:103-109`, `deps_pipeline.py:40-47` | User can adjust context budget distribution, but production writing assembler uses default `WritingContextAssembler()` | Hoch | ✅ Wire into assembler/settings cascade | FIND-012 |
| Output profiles not enforced | `gateway.py:119-126`, `178-194`, `249-262` | Resolved limits/evidence do not reliably cap actual model calls | Hoch | ✅ Gateway/agent boundary | FIND-001 |
| `comprehensive` profile missing from API/frontend profile enums | `model_config.py:16-21`, `schemas.py:42-46`, `types/settings.ts:57`, `aiTabConstants.ts:3-8` | Core can select comprehensive; user/API cannot select it by profile | Mittel/Hoch | ✅ Vocabulary unification | FIND-001 related |
| Inline suggest `max_tokens=60` | `writing/deps_suggest.py:36`, `writing/deps_writing.py:73-76` | Local feature cap bypasses token profile/settings vocabulary | Mittel | ✅ Named low-latency cap | — |
| Provider fallback model catalog | `setup/provider_service.py:21-67` | Static model release list for setup fallback | Mittel/Hoch | Operator/catalog-backed; label stale | — |
| Ollama URL default repeated | `setup/provider_service.py:77`, `110`; `setup/provider_schemas.py` | Local provider URL default | Mittel | Settings/provider base_url | — |
| OpenRouter catalog cap `30` | `llm/model_listing.py:85-92`, `322-329` | UI usability cap for huge catalog | Mittel | Constructor parameter exists | — |
| Model catalog timeout `10.0` | `llm/model_listing.py:85-92` | Provider catalog request timeout | Mittel | Constructor parameter exists | — |
| models.dev cache TTL `86400` | `llm/cost_rates.py:74-90` | Cost/model-limit cache freshness | Mittel | Function parameter only; no operator setting | — |
| Wiki retry delays `[30, 120, 300]` | `apps/api/narrare/wiki/tasks.py:22-23`, `106-147` | Background summary retry backoff | Mittel | Parameter exists; future TaskIQ config should own | — |
| Embedding threshold `0.7`, limit `20` | `apps/api/narrare/embeddings/service.py:105-155` | Vector search defaults | Mittel | Already method parameters; callers can override | — |
| Name dedup page size `1000` + token cap `500` | `generation/name_service.py:235-264` | Existing name dedup context | Mittel | Project/operator setting if large KBs suffer | — |

### 3.2 Timeouts & Retry-Logik

| Wert | Aktuell | Sinnvoll? | Konfigurierbar? |
|---|---|---|---|
| API/model catalog timeout | `ModelCatalogClient(catalog_timeout=10.0)` | Yes | Constructor parameter; not surfaced as operator setting |
| models.dev timeout | `_fetch_models(timeout=10.0)` | Yes | Function parameter; not surfaced as operator setting |
| WebSocket idle timeout | `Settings.ws_idle_timeout_seconds=1800` → `TokenLimitsService` → `WritingSessionHandler` | Yes | Operator/user/project via token limits |
| Frontend SSE connect timeout | `DEFAULT_CONNECT_TIMEOUT_MS=30_000` with option override | Yes | Caller option; not global user setting |
| AI operation connection-loss timeout | `DEFAULT_CONNECTION_LOSS_TIMEOUT=15_000`; auto retries `0` | Yes | Hook options |
| WritingSessionSocket reconnect | default `5` attempts, `1000ms` base | Reasonable | Constructor options |
| Retry max/base delay | `Settings.retry_max_attempts=3`, `retry_base_delay=1.0` | Reasonable | TokenLimitsService/API/UI |
| Wiki background retry | `[30.0, 120.0, 300.0]` | Reasonable for background | Function parameter; should become TaskIQ/operator config when broker is wired |

### 3.3 Feature-Flags & Kill-Switches

| Feature | Aktuell aktiv? | Flag vorhanden? | Konfigurierbar? |
|---|---|---|---|
| mem0 memory | Conditional | Credentials/package availability; `NullMemoryClient` fallback | Operator/provider config |
| mem0 embeddings | Conditional | embedding provider `auto/openai/local/disabled` | Factory parameter/settings path |
| Prompt caching | Default enabled | `CacheSettings.enabled` | Resolved model config |
| E2E LLM suppression | Conditional | `NARRARE_E2E_TEST` | Test operator env |
| Streaming/UI cancel behavior | Mostly active | `useAIOperation` options | Component/hook config, not user settings |
| Inline fallback prompt paths | Still present in known bypasses | Exception/register-level only | No runtime kill switch; tracked by CR-02/CR-04 findings |

**Bewertung Magic Numbers & Strings:** ⭐⭐⭐
**Befunde:** Most raw values are defaults with some configurability, but the high-risk category is settings that appear configurable while runtime still uses constants/defaults.

---

## 4. Konfigurierbarkeits-Matrix

| Wert | Aktuell | Sollte konfigurierbar sein für | Priorität |
|---|---|---|---|
| Output-token limit per intent/profile | User/project/operator data exists; model-call enforcement open | Nutzer (simple profile), Projekt, Operator raw cap | 🔴 Hoch |
| Context tier percentages | UI/API writes `tier_percentages`; writing assembler ignores runtime settings | Nutzer/Projekt for writing workflow | 🔴 Hoch |
| Default model per feature/category | User/project model routing cascade | Nutzer/Projekt | 🟢 Already |
| Model suitability hints | Advisory only | UI/project admin | 🟡 Mittel |
| Provider model catalog/fallback list | Dynamic fetch + static fallback | Operator/catalog data; not normal user | 🟡 Mittel |
| Consistency `max_chapter_tokens` / `max_kb_entries` | Operator env/service field; not API response/update schema | Operator primarily; project for very large novels | 🟡 Mittel |
| Inline suggest max output | Raw `60` in factories | Project/user low-latency preset or code default constant | 🟡 Mittel |
| API/catalog/model-limit timeouts | Constructor/function/settings mix | Operator | 🟡 Mittel |
| WebSocket idle timeout/retry | Settings cascade + UI | Nutzer/Projekt/Operator | 🟢 Already |
| Cost rates | `models.dev` cache + provider fallback + env JSON | Operator | 🟢 Mostly |
| Embedding search threshold/limit | Method parameters, default service values | Feature/API callers; maybe user later | 🟡 Mittel |

---

## 5. Empfehlung: Konfigurationsschichten

| Schicht | Zielgruppe | Ort | Beispiele |
|---|---|---|---|
| **Nutzer-UI** | Endnutzer | Settings / editor controls | Output profile, output length slider, default model/category overrides, context tier distribution once runtime-wired |
| **Projekt-Config** | Power users/project maintainers | Project AI/token settings | Per-project model/category overrides, context budgets, consistency depth/caps for very large novels |
| **Operator-Config** | Self-hosters/admins | `Settings` / env / deployment config | Raw token defaults, provider/catalog timeouts, Ollama URL, cost-rate override, fallback catalog source, mem0 defaults |
| **Code-Defaults** | Developers | Core defaults with tests | Safe fallback profiles, conservative cache/cost fallbacks, last-resort provider inference, test-only defaults |

---

## Gesamtbewertung Konfigurierbarkeit

**Bewertung:** ⭐⭐⭐
**Zusammenfassung:** Narrare is no longer dominated by hardcoded provider/model values: user/project model routing, operator settings, and token-limit services are materially in place. The weak point is runtime binding. Output limits, context tier percentages, and some profile names are configured or exposed in one layer but not honored consistently by the execution layer. That makes some controls misleading until the existing cascades are wired through to `WritingContextAssembler`, `ModelRegistry`/agents, and profile validation.

---

## Aufgaben

<!-- Nummerierung: CR-AUFG-08-XX -->

- **CR-AUFG-08-01:** Enforce resolved output limits at the actual LLM boundary. `ModelRegistry.run()` and `ModelRegistry.stream()` must apply `ResolvedModelConfig.resolve_output_limit()` / invocation budget decisions through the correct pydantic-ai `ModelSettings` or provider-specific max-output parameter. Cross-reference: `CR-AUFG-03-06`, `CR-AUFG-03-07`, FIND-001.
- **CR-AUFG-08-02:** Wire `TokenLimitOverrides.tier_percentages` into production writing context assembly. `WritingContextAssembler` should accept tier overrides, API factories should pass resolved user/project limits, and tests should prove changing the UI setting changes the emitted tier budgets. Cross-reference: FIND-012.
- **CR-AUFG-08-03:** Unify token profile vocabulary across core, gateway, API schemas, validators, and frontend. Decide whether `custom` is a user profile or raw `output_limit` mode; expose `comprehensive` where consistency uses it; remove or document stale `conservative` in `ModelRegistry._profile_to_limits()`.
- **CR-AUFG-08-04:** Replace inline suggest raw `max_tokens=60` with a named low-latency output cap resolved from the token-limit/profile system, or document it as an immutable UX cap with regression tests.
- **CR-AUFG-08-05:** Decide the configuration layer for consistency caps (`max_chapter_tokens`, `max_kb_entries`, `max_selection_words`): expose them in token-limit API/UI/project settings if user/project-tunable, or document them as operator-only and remove UI implications.
- **CR-AUFG-08-06:** Move setup fallback model catalogs and repeated Ollama defaults behind a catalog/settings abstraction. Fallback lists should have freshness/source labels so users know when they are stale.
- **CR-AUFG-08-07:** Add model-limit calibration at settings/runtime boundaries: compare selected output limit/profile against `models.dev` `ModelLimits.output` when available, warn on unknown/too-low/too-high limits, and avoid implying calibration when offline.
- **CR-AUFG-08-08:** Review system/background model config (`build_system_default_config`) and route it through a named system-model settings resolver rather than a two-value category string branch, especially for wiki/background tasks.

## FINDs

- **Open existing:** `_audit/results/content-review/findings/FIND-001-output-limits-not-enforced.md` — output token profiles/settings exist but are not reliably enforced at model calls.
- **New:** `_audit/results/content-review/findings/FIND-012-context-tier-settings-not-applied.md` — context tier percentages are exposed through settings UI/API but production writing context assembly uses default tier allocations.

## Next Prompt Recommendation

Proceed with **CR-06 – Summary / Abschlussbericht** next. CR-06 should consolidate CR-00 through CR-05, CR-07, and this CR-08, with FIND-001, FIND-009, FIND-010, FIND-011, and FIND-012 as active formal findings.
