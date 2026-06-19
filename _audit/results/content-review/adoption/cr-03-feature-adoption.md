# Content Review CR-03 – Feature-Adoption

Audit date: 2026-06-12
Scope: current adoption of mem0, context/token budgets, Knowledge Graph context, prompt enrichment, and machine gates.
Method: graph-first restart, required Narrare context loaded, CR-00/CR-01/CR-02 baselines reviewed, then targeted reads of `ai_invocation`, memory, writing context, token-limit, KG, and adoption-check paths. `just check-adoption` and `uv run python scripts/check_adoption.py --evidence-dir .evidence` were run for gate evidence.

## Status Addendum — 2026-06-19 (ADR-045 complete)

ADR-045 closed the runtime-adoption enforcement layer identified by this audit.
Current adoption status is `PASS 0.97`: all 29 modes are `runtime_verified` and
`adopted`. Runtime evidence is correlated by invocation, enriched dynamic inputs
merge into the prompt context, run-limit enforcement is covered, WebSocket writing was
modularized, and `--evidence-repo` is wired. The debt ratchet resolved 116 items; 1
registered inline-fallback baseline remains as governed adoption debt. Historical
findings below are kept for audit traceability.

## Original Root Cause Summary (2026-06-12)

INFRA-013 has built the right adoption vocabulary: `InvocationPipeline`, enrichers, validators, budget resolver, evidence sinks, registry modes, and `.evidence` files exist. The remaining root cause is **semantic/runtime alignment**, not missing static infrastructure: several runtime proofs show that components exist, but some production paths either do not consume the enriched context, do not wire the pipeline, or do not enforce the resolved output budget at the actual model call.

**Architectural fit:** The sustainable fix is to strengthen the existing boundaries, not add another prompt path. Preference/KG/profile data should flow through `PromptContext`/feature assemblers into `PromptComposer`; validation and budget evidence should be tied to the same invocation that reaches `ModelRegistry`/agent execution; model limits should be enforced in the LLM gateway layer.

**Alternatives considered:**

1. **Trust static registry score because it is now 0.98 PASS.** Rejected: the default checker can still pass while reporting `0 runtime_verified, 0 adopted`.
2. **Add ad-hoc feature-level fallbacks for missing context.** Rejected: this repeats the pre-INFRA-013 problem and bypasses PromptComposer/InvocationPipeline.
3. **Tighten the existing invocation contract and evidence gate.** Chosen: it preserves ADR-026/037 separation and makes adoption claims match production behavior.

---

## 1. mem0 – Adoption-Analyse

### 1.1 Aktuelle Nutzung vs. Sinnvolle Nutzung

| Feature | Aktuelle mem0-Nutzung | Wäre mem0 hier sinnvoll? | Begründung |
|---|---|---|---|
| Writing generation | `PreferenceService` is wired into `PromptComposer` when mem0 + credentials exist; writing prompts include `{{user_preferences}}` and `{{avoidance_patterns}}`. `PreferenceContextEnricherImpl` also exists, but `build_and_validate_prompt()` composes with the original `PromptContext`, not `prepared.context`. | Yes | Cross-session style, pacing, accepted/rejected suggestions, and avoidance memory directly improve prose generation. |
| Extend/rewrite/co-author | Services pass user/project IDs; prompts include preference fields; co-author also records accept feedback. | Yes | These modes are highly preference-sensitive and should learn from edits/rejections. |
| Interactive WebSocket writing | Handler builds a minimal `PromptContext(language="en", mode=..., author_instructions=content)` and uses `PromptComposer` directly; no user/project IDs or invocation pipeline path in the handler. | Yes | Interactive sessions are exactly where adaptive preferences would reduce repeated steering. |
| KB interview/suggest/enhance | KB templates include preferences/avoidance; direct services record invocation evidence through `safe_record_evidence`; preference relevance varies by mode. | Yes, selectively | Interview tone and question style benefit from memory; factual KB extraction should treat preferences as lower priority than source evidence. |
| Analysis/review | Analysis templates include preference/avoidance; evidence wiring exists through `safe_record_evidence`. | Yes, but bounded | Beta-reader/readability output should respect author goals, but must not let preferences hide objective consistency problems. |
| Planning/names | Registry requires preference enrichment; prompts include preference fields. | Yes | Planning and naming conventions are durable author preferences. |

### 1.2 Konkrete mem0-Nutzungsszenarien (priorisiert)

**Szenario 1 – Writing preference learning:** store accepted/rejected/modified AI suggestions with mode, genre, chapter, rating, and modification text; retrieve compact style, pacing, voice, and avoidance summaries before drafting.

**Szenario 2 – Interactive steering memory:** store repeated corrections during WebSocket writing sessions (“shorter paragraphs”, “less exposition”, “ask before adding lore”); retrieve them for the next turn in the same project.

**Szenario 3 – KB interview adaptation:** store whether the author prefers concise concrete questions or deep lore prompts; retrieve only as interaction style, never as factual world data.

**Szenario 4 – Analysis calibration:** store reviewer preferences (e.g. “prefer blunt feedback”, “prioritize pacing over prose polish”) and inject them as reviewer lens while preserving evidence/confidence gates.

**Bewertung mem0-Adoption:** ⭐⭐⭐⭐
**Befunde:** mem0 is now materially wired (adapter, feedback forwarding, preference service, prompt DI), but the invocation-pipeline preference enrichment path is currently more evidential than functional unless enriched `dynamic_inputs` are merged into the `PromptContext` used by `PromptComposer`. WebSocket interactive sessions also miss the richer ID/pipeline preference path.

---

## 2. ContextBudget – Adoption-Analyse

### 2.1 Aktuelle Nutzung

| Feature | ContextBudget genutzt? | Token-Limit bekannt? | Overflow-Handling? |
|---|---|---|---|
| Writing context | Yes: `WritingContextAssembler` uses 5-tier `TokenBudgetManager` with mode-specific allocation. | Default 6000 input-context tokens; tier percentages configurable through token-limit settings/UI. | Yes: Tier 1 truncates only content after fixed outline/frontmatter; Tier 2 falls back full text → summaries → truncation; Tier 3/4 enforce budgets; pinned bypasses. |
| Writing `kb_suggested` | Yes in assembler and templates. | 15% default, 25% first chapter, 10% extend/rewrite. | Yes in assembler; semantic evidence wording still belongs to CR-01/CR-04. |
| Analysis/KB direct-agent evidence | Partial: `safe_record_evidence()` runs pipeline prepare/finalize, but direct-agent content often supplies the real prompt separately. | Output budget evidence can exist; input context limits are feature-specific/manual. | Partial; evidence can prove the contract ran, not necessarily that the true runtime prompt was budgeted. |
| Interactive WebSocket session | Weak: prompt is built directly from author instruction; `WritingPipeline` is constructed without `invocation_pipeline` in `router_sessions.py`. | Config `max_tokens` comes from token-limit service, but gateway enforcement is unclear (see FIND-001). | Minimal; no assembled KB/recent/prefs budget in `_handle_direction()`. |
| Output budgets | Static profiles exist per intent (`quick=500`, `balanced=2000`, `long_texts=8000`, `comprehensive=16000`). | Yes as configuration/profile data. | **No reliable enforcement found at model call**; see FIND-001. |

### 2.2 Problematische Stellen

- `build_and_validate_prompt()` runs `invocation_pipeline.prepare()`, but then calls `composer.build(intent, prompt_ctx)` with the **original** `PromptContext`; `prepared.context.dynamic_inputs` are not merged into prompt variables.
- `KBSuggestedContextEnricher` is wired with `kb_provider=None` in production DI, so the invocation-pipeline KB-suggested path cannot itself supply graph/KB context. Writing still gets `kb_suggested` from `WritingContextAssembler`, which is useful but separate from the enricher evidence.
- `WritingSessionHandler._handle_direction()` bypasses the writing context assembler and invocation adapter for interactive turns; it uses only author instructions and a hard-coded prompt language.
- Output budget profiles are resolved and evidenced, but `ModelRegistry.stream()` does not pass a usage limit to `agent.run_stream()`, and `get_model()` computes `usage_limits` without applying it to the returned model.

### 2.3 Priorisierungs-Strategie

Empfehlung für Kontext-Priorität when not everything fits:

1. Current author instruction and selected/current scene text.
2. Project writing profile/manual project settings.
3. Current outline, timeline position, and immediate chapter context.
4. Curated KB entries and explicit relationships.
5. Character voice profiles for dialogue or character-focused output.
6. Recent chapter summaries/full text.
7. Learned mem0 preferences.
8. Generated/unaccepted KB suggestions (`kb_suggested`) and other low-confidence candidates.

**Bewertung ContextBudget-Adoption:** ⭐⭐⭐
**Befunde:** Input-context budgeting for writing is strong. Cross-feature/direct-agent and interactive paths are weaker, and output-budget enforcement is currently a blocking adoption gap (FIND-001).

---

## 3. Knowledge Graph – Adoption-Analyse

### 3.1 Aktuelle Nutzung

| Feature | KG genutzt? | Zweck | Sinnvoll erweitert? |
|---|---|---|---|
| Writing context | Yes/partial | Relationship repository data is formatted into `kb_relationships`; `entity_connections` promotes connected entities into Tier 3; `kb_suggested` fills Tier 4. | Yes: keep current path, but make evidence distinguish assembler-supplied KG context from invocation-enricher context. |
| KB graph UI | Yes | `GraphService` builds nodes/edges, stats, connected components, shortest path for visualization. | Yes: currently more UI/navigation than prompt intelligence. |
| Consistency checks | Partial | `analysis/en/consistency` can consume relationship text; `KBConsistencyEnricher` protocol/model exists. | Yes: use graph traversal/edge provenance to detect relationship and timeline contradictions, not only text summaries. |
| KB worldbuilding/merge | Partial | Worldbuilding templates use relationships/candidate pairs; merge service has invocation evidence. | Yes: pair selection and conflict scoring should use graph metrics/path evidence. |
| Planning/timeline | Partial | Planning prompts can consume relationships and entity events; CR-02 found temporal consistency still bypasses PromptComposer. | Yes: timeline graph/event traversal is high-value for chronology and cause/effect coherence. |

### 3.2 Untergenutzte KG-Potenziale

- The KG is useful in the UI and as formatted relationship text, but there is no single graph-aware prompt-context provider that can answer “which connected entities matter for this scene and why?”
- `KBConsistencyEnricher` is a solid contract, but production `get_invocation_pipeline()` does not wire a consistency checker; it only wires preferences and a no-provider `KBSuggestedContextEnricher`.
- `GraphService.get_shortest_path()` exists for UI exploration, but no evidence shows shortest paths, connected components, or relationship degrees feeding consistency/planning prompts.
- The writing assembler promotes connected entities but loses graph provenance in the final prompt; the model sees relationship lines, not an explanation of why each related entity was included.

**Bewertung KG-Adoption:** ⭐⭐⭐
**Befunde:** The project has a useful relationship graph and prompt variables consume parts of it, but KG remains underused as a reasoning substrate for consistency, planning, and candidate ranking.

---

## 4. Prompt-Anreicherung – Vollständigkeits-Check

| Funktion | Bekommt aktuell | Fehlt | Überflüssig |
|---|---|---|---|
| KB-Interview | Template structure, existing answers, world context, preferences/avoidance, output schema. | Runtime evidence should prove the same prompt that reaches the agent, not only placeholder evidence; output language variable consistency remains CR-01. | None obvious. |
| Writing-Continue / Extend | Current text with marker, outline, KB characters/locations, recent chapters, voice profiles, relationships, `kb_suggested`, preferences/avoidance. | Enriched invocation context is not merged into composer input; output budget not enforced at gateway; interactive WebSocket continue path is thinner. | Potentially too much low-priority KG if `kb_suggested` lacks precedence labels. |
| Consistency Check | Chapter/Kb text, check types, relationships in some paths, preferences/avoidance. | Graph traversal evidence, timeline/edge provenance, staged fact extraction for long projects. | Preferences should be bounded so they do not suppress objective contradictions. |
| Suggest | Nearby text, preferences/avoidance, optional KB suggestions, short output constraints. | For low-latency inline suggest: compact relationship/voice signals only when available; runtime budget evidence should show deliberate `kb_suggested` rejection. | Full KG context would be too heavy for ghost text. |
| Rewrite | Selection/before/after, mode instructions, KB/relationship/voice context, preferences/avoidance. | Same enriched-context merge and output-budget enforcement gaps; stronger graph provenance for voice/relationship rewrites. | None obvious. |
| Free/project chat | Dedicated chat prompt and preferences; CR-02 found system prompt is concatenated into user channel. | Correct feature-prompt injection channel, project-context enrichment, output budget enforcement. | User-channel system prompt text is misplaced rather than useful. |

**Bewertung Prompt-Anreicherung:** ⭐⭐⭐⭐
**Befunde:** Main writing prompts are rich and materially improved. Completeness is now limited by runtime/evidence alignment: enriched context must reach the prompt actually sent to the model.

---

## 5. Feature-Adoption-Gates & Machine Checks

**Machine gate evidence:**

- `just check-adoption` ran `uv run python scripts/check_adoption.py` and returned `Feature Adoption Score: 0.98 (PASS)`, but reported `0 runtime_verified, 0 adopted` for every mode category. This means the default local gate still passes on static score even when runtime adoption is absent from the invocation.
- `uv run python scripts/check_adoption.py --evidence-dir .evidence` returned the same `0.98 PASS` and `27/27 adopted` via `.evidence/preference_enrichment.json`, `.evidence/final_validation.json`, `.evidence/budget_resolution.json`, and `.evidence/invocations.jsonl`.
- `.evidence/invocations.jsonl` contains many `static_verified` placeholder records with `final_prompt_validated=false`, `preference_status=not_applicable`, and `output_budget_profile=null`; the JSON evidence files are what make the modes adopted.

**Alignment assessment:**

| Expectation | Covered by machine gate? | Gap |
|---|---|---|
| Registry exists and modes are declared | ✅ | Strong. |
| Static prompt variables exist | ✅ | Strong. |
| Runtime evidence can be loaded | ✅ with `--evidence-dir .evidence` | Default `just check-adoption` does not load it. |
| Runtime adoption is required for PASS | ❌ | Default run can pass with 0 adopted. |
| Evidence proves real production prompt path | ⚠️ | Some evidence is component-level/placeholder and can diverge from the prompt/model path. |
| Token budgets are enforced before model calls | ❌ | FIND-001. |

**Bewertung Adoption-Gates:** ⭐⭐⭐
**Befunde:** The registry/scorer/evidence infrastructure is valuable, but the default gate semantics still allow a static PASS without runtime adoption. Evidence needs to bind to real invocation paths and output-limit enforcement.

---

## 6. Token-Limits – Kalibrierung & Aktualität

### 6.1 Output-Limits: Passen sie zur Aufgabe?

> **Eskalation:** Because the resolved output profiles are not reliably enforced at `ModelRegistry.run()` / `ModelRegistry.stream()`, this section creates **FIND-001**.

| Funktion | Typische Output-Länge (Wörter) | Benötigte Tokens (ca.) | Definiertes Limit | Ausreichend? | FIND? |
|---|---:|---:|---|---|---|
| Inline suggest / names | 10–200 | 30–300 | `quick=500` | In profile yes; enforcement gap | FIND-001 |
| KB interview question | 50–300 | 100–500 | `quick=500` | Usually yes; enforcement gap | FIND-001 |
| Rewrite alternatives | 300–1500+ | 450–2500+ | `long_texts=8000` for `REWRITE` | Yes for common cases; enforcement gap | FIND-001 |
| Continue/extend | 400–2500 | 600–4000 | `long_texts=8000` for `EXTEND` | Yes for common cases; enforcement gap | FIND-001 |
| New chapter/full draft | 1500–5000 | 2200–7500 | `long_texts=8000` for `WRITE` | Mostly yes; edge cases need custom; enforcement gap | FIND-001 |
| Beta read / long analysis | 1000–4000 | 1500–6000 | `long_texts=8000` | Yes for normal outputs; enforcement gap | FIND-001 |
| Cross-chapter consistency | 2000–9000 | 3000–14000 | `comprehensive=16000` | Yes in profile; frontend/API profile selector cannot choose `comprehensive`; enforcement gap | FIND-001 |

### 6.2 Sind die Limits feature-spezifisch oder global?

They are feature-/intent-specific at the profile mapping layer: every routeable intent has a default profile (`quick`, `balanced`, `long_texts`, `comprehensive`). User/project token-limit settings also support an `output_limit` value and context tier percentages. However, the gateway path does not reliably translate profile/output-limit decisions into enforced model call settings, so the current strength is configurability metadata rather than runtime enforcement.

### 6.3 Modell-Vergleich: Wie viel Potenzial liegt brach?

| Modell | Max Output | Aktuell genutzt | Ungenutzt |
|---|---:|---:|---:|
| models.dev-known provider/model | Looked up by `get_model_limits(provider, model_id)` when cache/network available | Not automatically compared to selected profile in the audited runtime path | Potentially large; no automatic calibration against model output ceiling. |
| Unknown/offline model cache | Unknown | Profile defaults 500/2000/8000/16000 or user `output_limit` metadata | Unknown; graceful degradation returns no model limits. |
| UI slider | 16,000 max in `TokenSettings` | User can set output_limit 500–16,000 | Larger-model output windows above 16k cannot be selected in UI despite API schema allowing up to 131,072. |

### 6.4 Konfigurierbarkeit

- **User WebUI:** yes for output limit slider/profile in the editor and context tier percentages in AI settings.
- **Self-host/operator:** yes through settings defaults and token-limit service cascade.
- **Project-level overrides:** yes through token-limit service/project repository path.
- **Gap:** frontend/API profile enum allows `quick|balanced|long_texts|custom`, but core has `comprehensive=16000`; consistency defaults can use it internally, but users cannot select that named profile directly.
- **Gap:** configured/resolved limits must be enforced in the actual agent/model call before this can count as full token-limit adoption.

**Bewertung Token-Limits:** ⭐⭐
**Befunde:** Calibration data is much better than the previous stale CR-03, but runtime enforcement is not proven and appears absent in `ModelRegistry.stream()`/`run()` convenience paths. See FIND-001.

---

## Original Gesamtbewertung Feature-Adoption (2026-06-12)

**Bewertung:** ⭐⭐⭐
**Vorherige Bewertung:** ⭐⭐⭐ | **Trend:** ↗️ Besser in Infrastruktur, ➡️ Gleich im Risiko
**Zusammenfassung:** Narrare now has most of the infrastructure CR-03 asked for: mem0 wiring, PromptComposer routes, mode registry, InvocationPipeline, validators, budget resolver, evidence files, and graph-aware context fields. The content value is real in normal writing prompts. The remaining adoption risk is that machine evidence can overstate production reality: enriched context is not always the context sent to `PromptComposer`, some paths bypass the pipeline, KG is mostly text/UI rather than reasoning substrate, and output limits are configured but not reliably enforced at model calls.

---

## Aufgaben

Previously stale CR-03 tasks from the old result are superseded; do not reopen resolved mem0 DI or per-intent profile-mapping tasks unless new evidence contradicts this report.

- **CR-AUFG-03-01:** Make runtime adoption evidence mandatory in the default/CI adoption gate: `check_adoption.py` should fail or warn when `requires_runtime_evidence: true` modes have `0 adopted`, and `just check-adoption`/CI should load the intended evidence source or clearly label the run as static-only.
- **CR-AUFG-03-02:** Ensure `InvocationPipeline.prepare()` enrichment affects the actual prompt composition path, or document each manual-injection exception. In writing, merge `prepared.context.dynamic_inputs` into the `PromptContext` before `composer.build()` or prove an equivalent path.
- **CR-AUFG-03-03:** Align `kb_suggested` runtime evidence with actual production context: either wire a real `KBSuggestedProvider` into `KBSuggestedContextEnricher` or classify writing-assembler-supplied `kb_suggested` as the adopted path with its own evidence.
- **CR-AUFG-03-04:** Wire interactive WebSocket writing sessions into the same invocation/prompt enrichment contract as other writing modes, including user/project IDs, preferences, budget evidence, and final validation.
- **CR-AUFG-03-05:** Promote KG from UI/relationship text to reasoning context for consistency/planning: wire a real `KBConsistencyCheck`/graph traversal provider and include graph provenance in high-impact prompts.
- **CR-AUFG-03-06:** Fix token-limit enforcement at the LLM gateway/agent boundary so resolved intent/user/project output limits are applied to `agent.run()` / `agent.run_stream()` or provider model settings.
- **CR-AUFG-03-07:** Reconcile token profile configurability: expose/validate `comprehensive` consistently where cross-chapter consistency needs it, and document how UI `output_limit` maps to model/provider maximums.

### ADR-045 closure status (2026-06-19)

| Task | Status | Evidence |
|------|--------|----------|
| CR-AUFG-03-01 | ✅ Resolved | Runtime gaps are status-bearing; adoption reports `PASS 0.97` only with 29/29 modes runtime-verified + adopted. |
| CR-AUFG-03-02 | ✅ Resolved | Prepared dynamic inputs merge into `PromptContext` before prompt composition. |
| CR-AUFG-03-03 | ✅ Resolved | Runtime evidence records canonical adoption paths; no placeholder evidence satisfies runtime adoption. |
| CR-AUFG-03-04 | ✅ Resolved | WebSocket handler modularized; turn service carries user/project/chapter/session IDs and evidence. |
| CR-AUFG-03-05 | ✅ Resolved for ADR-045 adoption gate | Runtime adoption evidence is complete; deeper KG reasoning enhancements remain future feature work, not an adoption blocker. |
| CR-AUFG-03-06 | ✅ Resolved | `ResolvedRunLimits` / `DefaultRunLimitResolver` coverage proves run/stream usage-limit enforcement. |
| CR-AUFG-03-07 | ✅ Resolved | `comprehensive`/runtime profile handling is covered in run-limit enforcement and adoption evidence. |

## FINDs

- **FIND-001:** `_audit/results/content-review/findings/FIND-001-output-limits-not-enforced.md` — resolved by ADR-045 run-limit enforcement (`ResolvedRunLimits`, `DefaultRunLimitResolver`, ModelRegistry run/stream tests).

## Next Prompt Recommendation

Proceed with **CR-04 – Cross-Feature Coherence / Context Precedence** next. Use this CR-03 to focus CR-04 on conflicts between current author instruction, project profile, curated KB, KG-derived relationships, mem0 preferences, and generated `kb_suggested` candidates.
