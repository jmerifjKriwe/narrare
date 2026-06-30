# ADR-057 — Voice-Check Checking-Path Contract & `voice_check` Prompt Surface (WRITE-010)

> **Status:** 🔄 Proposed (spec/ADR authored; implementation gated on user review)
> **Date:** 2026-06-30
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-021 (deterministic analysis), ADR-035 (agent output validation),
> ADR-050 Decision 3 (VoiceProfileConsumer — the contract this ADR satisfies on the
> checking path), ADR-054 (Mode-1 PromptComposer mandate), ADR-055 (character-voice
> storage contract + VOICE routeable; **Risk #1 of ADR-055 is closed by this ADR**),
> ADR-056 (runtime-aware adoption gate), CONSTRAINTS.md
> RULE-02/02b/03/04/05/06/07/11/13/22, CR-04 (cross-feature coherence)

> **Scope of this ADR:** contracts + decisions only. It does NOT implement code,
> tests, or the governed template file. Implementation is gated on user review of
> this ADR + the WRITE-010 spec rewrite. The manifest/route-table/model file edits
> land at implementation; this ADR defines the contract they must satisfy.

---

## Context

WRITE-010 (Voice Consistency Checker) is the consumer of ANAL-008 (Character
Voice Profiling, ✅ stable). ANAL-008 writes each character's
`KBEntity.metadata["speech"]["voice_analysis"]`, containing a descriptive
group (`formality`, `vocabulary_level`, …, `voice_examples`) and a metric
group (`voice_metrics: VoiceMetrics` with `avg_sentence_length`,
`sentence_length_std`, `type_token_ratio`, `avg_syllables_per_word`,
`contraction_rate`, `verbal_tic_frequency`, `punctuation_profile`).

WRITE-010 checks chapter dialogue against those stored profiles and reports a
per-character match score + flagged lines. It is **read-only** (it checks; it
does not profile, does not write to KB). It is a **flag+score checker** — it
does NOT produce rewrite suggestions (rewrite reuse of WRITE-004 on flagged
lines is a later, separate concern; YAGNI for v1).

This ADR records five decisions the checker needs: (1) how the checker reads
structured `voice_metrics` (the checking-path model gap), (2) the scoring
strategy, (3) the `voice_check` prompt surface, (4) the module home, and
(5) the flag+score scope boundary.

### Verified state (grounded, not assumed)

| Concern | State | Location |
|---------|-------|----------|
| `VoiceMetrics` / `VoiceAnalysis` / extended `SpeechPatterns` | EXISTS (Layer 0, ADR-055) | `core/kb/schemas/character.py` |
| `DialogueParser` (reusable) | EXISTS (Layer 2, ADR-055) | `core/analysis/dialogue_parser.py` |
| `VoiceMetricsAnalyzer` (reusable) | EXISTS (Layer 2, ADR-021/055) | `core/analysis/voice_metrics.py` |
| `CharacterVoiceAgent` (profiling agent) | EXISTS (Layer 2) | `core/agents/character_voice_agent.py` |
| `LLMIntent.VOICE` routeable | YES (ADR-055 D4); default mode `character_voice`; `allowed_context_modes = {"character_voice"}` | `core/prompts/route_table.py` |
| `VoiceProfileConsumer.assemble_for_checking()` | EXISTS — returns `list[CharacterVoiceProfile]` | `core/profiles/contracts.py` |
| `CharacterVoiceProfile` model | Carries ONLY `character_id, name, speech_summary (flat str), updated_at, is_fresh`. **Does NOT carry `voice_metrics`** | `core/profiles/models.py` |
| `build_character_voice_profile()` builder | Builds the flat model; does NOT surface `voice_metrics` | `core/profiles/_voice_extraction.py` |
| `assemble_for_generation` / `formatted_voice_profiles` | Renders `speech_summary` (which already EXCLUDES metrics, ADR-055) | `core/profiles/models.py` / `assembly.py` |
| ANAL-008 spec claim | ANAL-008 spec §"Integration with the Checking Pipeline" already states the checking path "surfaces structured profiles including `voice_metrics`" — **aspirational until this ADR's model extension lands** | `docs/features/analysis/ANAL-008-voice-character.md` |
| Analysis router URL pattern | `/analysis/{feature}/{chapter_id}` for chapter-scoped (coreference); `/analysis/character-voice/{novel_id}` for novel-scoped profiling | `apps/api/narrare/analysis/router_*.py` |

### Root cause (why this ADR is needed)

**ADR-055 Risk #1 (deliberately deferred, now resolved here).** ADR-055 stated:

> "the current `CharacterVoiceProfile` (`core/profiles/models.py`) carries only
> a flat `speech_summary`; it has no structured `voice_metrics`. … when
> WRITE-010/ANAL-009 are implemented, they must decide how the checker reads
> structured metrics (extend `CharacterVoiceProfile`, or read KB directly)."

Two layers of "why" (architectural-discipline §1):

1. *Why does the checker need a decision at all?* ANAL-008 WRITES
   `voice_metrics` to KB (the data exists), but the checking-path projection
   (`assemble_for_checking()`) returns a `CharacterVoiceProfile` that cannot
   carry metrics. The checker therefore has no contract-sanctioned way to read
   the deterministic metrics it needs to compute a delta.

2. *Why is this an architecture decision rather than an implementation choice?*
   Because there are two ways to read the metrics — (a) through the
   `VoiceProfileConsumer` contract (ADR-050), or (b) by the checker reaching
   into `KBEntity.metadata["speech"]["voice_analysis"]["voice_metrics"]`
   directly. ADR-050 exists precisely to prevent consumers from bypassing the
   provider/SSOT (its P1-C root cause was that `WritingContextAssembler`
   bypassed the SSOT and duplicated freshness policy at the call site). The
   checker bypassing the consumer would repeat the exact anti-pattern ADR-050
   closed. So the *correct* path is to extend the model the consumer already
   returns — which is a cross-feature contract change (the profile flows
   through generation unchanged AND through checking enriched). Per CR-04 /
   RULE-22, a cross-feature contract change needs an ADR, not an inline
   implementation choice.

The second root cause: `LLMIntent.VOICE` currently has only one governed
context_mode (`character_voice`). WRITE-010 needs its own governed prompt
surface (a checker prompt ≠ a profiling prompt), so a new `voice_check`
context_mode must be added to the route. That is a prompt-mechanics change
requiring a Retrofit-Plan (adr-process §D.4).

---

## Decision Drivers

- **RULE-02/02b** — WRITE-010's prompt MUST be PromptComposer Mode 1 (intent +
  `voice_check` context_mode + governed EN template). No inline f-strings,
  no production fallback, no system-prompt-in-user-channel.
- **RULE-03** — The checking-path model extension + the checker contract MUST
  exist before implementation.
- **RULE-04/06** — Modularise; one responsibility per file (scoring logic ≠
  agent ≠ service ≠ router).
- **RULE-07** — Consumers live in `core/profiles/`; the checker reads metrics
  via the consumer contract, never via direct KB access. No `apps/`→`core`
  cycles; `analysis → profiles → kb.schemas` (read direction only).
- **RULE-11** — Graceful: a character without a stored profile (no
  `voice_analysis`) is skipped with an explicit "no profile" result, not a
  crash or silent drop.
- **RULE-13** — SSE + non-streaming share the service interface (mirrors
  ANAL-005/008).
- **RULE-22 / CR-04** — Extending `CharacterVoiceProfile` is a cross-feature
  contract change (the model flows through generation + checking); the change
  must be coherent end-to-end, not feature-local.
- **ADR-021** — The metric delta MUST use deterministic `VoiceMetrics`
  (stable, comparable). LLM-only metrics are non-deterministic and rejected.
- **ADR-035** — The checker agent's structured output is validated.
- **ADR-050** — The checker MUST consume voice data via
  `VoiceProfileConsumer.assemble_for_checking()`, not via direct KB access.
- **architectural-discipline §1/§4/§7** — Root-cause solution; no KB-bypass
  workaround; "documented ≠ implemented" — the model extension is the
  implementation that makes ADR-055 Risk #1's deferral and the ANAL-008 spec's
  checking-path claim actually true.

---

## Decision 1 — Checking-path model: extend `CharacterVoiceProfile` with `voice_metrics` (closes ADR-055 Risk #1)

### Options Considered

#### Option A — Extend `CharacterVoiceProfile` with `voice_metrics`; consumer surfaces it (CHOSEN)

Add ONE optional field to the existing checking-path value object and have
`assemble_for_checking()` populate it:

```python
# packages/core/narrare_core/profiles/models.py
from dataclasses import dataclass
from narrare_core.kb.schemas.character import VoiceMetrics

@dataclass(frozen=True)
class CharacterVoiceProfile:
    """Voice profile for a single character entity."""
    character_id: str
    name: str
    speech_summary: str                       # unchanged — rendered into generation
    updated_at: str | None = None
    is_fresh: bool = True
    # ADR-057: surfaced on the checking path only. None unless the character's
    # speech.voice_analysis.voice_analysis exists (ANAL-008). NEVER rendered
    # into generation (formatted_voice_profiles does not read it).
    voice_metrics: VoiceMetrics | None = None
```

- `build_character_voice_profile()` (in `_voice_extraction.py`) is extended to
  parse `speech.voice_analysis.voice_metrics` from the raw metadata dict and
  construct a `VoiceMetrics`. It already parses the descriptive group for
  `speech_summary`; this adds the metric block to the same parse.
- `assemble_for_checking()` (ADR-050 contract) returns
  `list[CharacterVoiceProfile]` where each profile now carries `voice_metrics`
  when ANAL-008 has profiled the character. The contract's signature
  (`-> list[CharacterVoiceProfile]`) is **unchanged** — the model gains a
  field, the consumer gains no new method.
- The generation path (`assemble_for_generation` →
  `ProjectWritingProfile.formatted_voice_profiles`) is **unchanged** and
  provably never reads `voice_metrics` (it renders `speech_summary` only).

**Pros:**
- The checker reads metrics **via the ADR-050 consumer contract** — no SSOT
  bypass. This is exactly the coherent end-to-end shape ADR-050 P1-C mandated.
- One model on both projections; the descriptive/metric boundary stays
  structural (generation reads `speech_summary`; checking additionally reads
  `voice_metrics`).
- Additive, optional, `None`-defaulted → backward compatible (existing flows
  that construct `CharacterVoiceProfile` without metrics are unaffected).
- Makes ADR-055 Risk #1's tracked deferral and the ANAL-008 spec's
  checking-path claim *actually true* (architectural-discipline §7).

**Cons:**
- `profiles/models.py` gains a runtime import of
  `narrare_core.kb.schemas.character.VoiceMetrics`. (Verified acyclic:
  `kb/schemas/character.py` imports only `.base` + pydantic — no `profiles`
  import. `profiles → kb.schemas` is a read-direction dependency on shared
  vocabulary, consistent with RULE-07.)
- A frozen dataclass now holds a (mutable) Pydantic `VoiceMetrics`. The
  dataclass-level `frozen=True` guarantees reference identity is stable;
  `VoiceMetrics` is treated as read-only by the checker. (See Risks #1 — a
  follow-up could mark `VoiceMetrics` frozen, but that is an ADR-055
  contract-side change, out of scope here.)

#### Option B — Checker reads `KBEntity.metadata["speech"]["voice_analysis"]["voice_metrics"]` directly

The checker service resolves `KBEntity` for each speaking character and reads
the metrics dict itself, bypassing `VoiceProfileConsumer`.

**Pros:** No model change.

**Cons:** Reintroduces the exact ADR-050 P1-C anti-pattern — a consumer
reaching past the SSOT provider, duplicating freshness policy and metadata
shape knowledge at the call site. It also leaves `assemble_for_checking()`
returning a model that cannot carry the data it is contractually meant to
surface, making the consumer incoherent. Rejected (architectural-discipline §4
— bypassing an existing abstraction is a forbidden workaround).

#### Option C — Separate `VoiceCheckProfile` model parallel to `CharacterVoiceProfile`

Define a new model just for checking that wraps `CharacterVoiceProfile` +
`voice_metrics`.

**Pros:** No change to the existing model.

**Cons:** Two models for the same data, with drift risk — the consumer would
have to project into a second type. Violates one-source-of-truth and adds
mapping surface for no benefit. Rejected.

### Decision

**Option A.** Extend `CharacterVoiceProfile` with
`voice_metrics: VoiceMetrics | None = None`; the consumer surfaces it on the
checking path; generation is unchanged.

### Rationale

ADR-050's `assemble_for_checking()` was designed to "surface structured
profiles for consistency checking" so consumers like WRITE-010 "can apply
their own rule logic." That intent is only realised when the model the
consumer returns actually carries the structured data. Option A is the
smallest change that makes the contract truthful; Options B/C both break the
contract's coherence (B bypasses it; C duplicates it).

### Sustainability check

1. *Correct in 3 months?* Yes — ANAL-009 (drift) will read the same field via
   the same consumer; no second access path.
2. *Hard-to-undo coupling?* None — additive optional field, `None` default,
   no migration, acyclic import.
3. *Simplest correct solution?* Yes — one optional field; the consumer gains
   no new method.
4. *Design intent clear?* Yes — the field name + `None` default + the
   `formatted_voice_profiles` non-reference document the boundary.

---

## Decision 2 — Scoring: hybrid deterministic-delta + LLM qualitative (mirror ANAL-008 / ADR-021)

### Options Considered

#### Option A — Hybrid: deterministic metric-delta + `CharacterVoiceCheckerAgent` qualitative judgment (CHOSEN)

A new pure Core scoring module computes a **deterministic delta** between the
chapter's per-character current metrics (from `VoiceMetricsAnalyzer`) and the
stored profile's `voice_metrics` (from the consumer), as a normalized distance
per metric (and an aggregate). A new `CharacterVoiceCheckerAgent`
(`NarrareAgent`, structured output, ONE LLM call) consumes the chapter
dialogue + the stored *descriptive* profile + the metric-delta and produces a
qualitative per-character judgment + line-level flags with reasons. The
overall per-character match score (0–100%) is a **deterministic blend** of the
metric-delta sub-score and the agent's qualitative sub-score (the blend lives
in the scoring module — pure, fully testable, no LLM).

This mirrors ANAL-008 / ADR-021's hybrid tier exactly: measurement is
deterministic, understanding is qualitative.

#### Option B — Deterministic-only scoring

Score purely from the metric-delta; no LLM.

**Pros:** Cheapest, fully deterministic.

**Cons:** Metrics cannot judge qualitative consistency (a character may match
all numeric metrics yet read as "off" — register shift, idiom mismatch, tic
absence). The whole point of WRITE-010 is to catch what readers notice.
Rejected.

#### Option C — LLM-only scoring

The agent judges consistency from dialogue + profile text, no metrics.

**Pros:** Captures qualitative.

**Cons:** Discards the deterministic metrics ANAL-008 specifically computed
"for ANAL-009 drift / WRITE-010 checking" (ADR-021/055). Non-deterministic,
unstable scores. Violates ADR-021. Rejected.

### Decision

**Option A.** Deterministic metric-delta + LLM qualitative, blended by a pure
scoring module. Per-character overall score = deterministic blend
(metric-delta sub-score + agent qualitative sub-score). Line-level flags come
from the agent (specific dialogue lines + reasons).

### Rationale

The metrics exist *because* comparison needs stable numbers (ADR-021).
Discarding them (C) or relying on them alone (B) both waste half the signal.
The blend is deterministic so the score is reproducible; the qualitative half
is what makes the flag *useful* to the author.

> **ADR-021 alignment:** ADR-021 pre-names `core/analysis/voice_metrics.py`
> for "Structural voice analysis." The delta + blend reuse that analyzer's
> output and live alongside it in `core/analysis/`. No ADR-021 amendment
> required (same hybrid tier as ANAL-003/008).

---

## Decision 3 — `voice_check` prompt-surface: new context_mode + governed EN template

### Options Considered

#### Option A — New `voice_check` context_mode on the `LLMIntent.VOICE` route (CHOSEN)

- Add `"voice_check"` to `ROUTE_CONFIGS[LLMIntent.VOICE].allowed_context_modes`
  (mirror how `character_voice` was added). Default mode stays
  `character_voice` (ANAL-008); the checker resolves explicitly to
  `voice_check`.
- Create governed EN template
  `core/prompts/_bundled/analysis/en/voice_check/system.md` (9-section
  skeleton, ADR-054 Mode 1). The checker prompt is a *flag+score* prompt
  (different intent from the *profiling* `character_voice` prompt) — it must
  NOT be the profiling template.
- Register VOICE/`voice_check` in the prompt-surface manifest and the
  adoption registry (mirror the `character_voice` entries; declared now,
  runtime evidence lands at implementation per ADR-056).

#### Option B — Reuse the `character_voice` template for checking

**Pros:** No new template.

**Cons:** The profiling prompt instructs the model to *produce a profile*
(formality register, vocabulary level, …); the checking prompt must instruct
it to *flag inconsistencies and score*. Reusing it produces wrong output and
violates RULE-02 (prompt ≠ task). Rejected.

### Decision

**Option A.** A dedicated `voice_check` context_mode + governed EN template.
The VOICE intent now serves two modes — `character_voice` (profile, ANAL-008)
and `voice_check` (check, WRITE-010) — exactly as ANALYSE serves
review/coreference/pov/readability and PLAN serves several planning modes.

### voice_check prompt-surface contract (spec — files edited at implementation)

| Artifact | Path / key | Change |
|----------|-----------|--------|
| Route config | `core/prompts/route_table.py` `ROUTE_CONFIGS[LLMIntent.VOICE]` | `allowed_context_modes = {"character_voice", "voice_check"}` |
| Mode map | `core/prompts/route_table.py` `INTENT_TO_MODE[LLMIntent.VOICE]` | unchanged (`"character_voice"` remains the *default* mode); checker resolves `voice_check` explicitly |
| Composer | `core/prompts/composer.py` (if it mirrors the route table) | verify VOICE/`voice_check` resolves; route_table is SSOT |
| Governed template | `core/prompts/_bundled/analysis/en/voice_check/system.md` | NEW (9-section skeleton, Mode 1) |
| Manifest | `scripts/architecture/prompt-surface-manifest.yaml` | add `voice_check` under the VOICE intent's `context_modes` (mirror `character_voice`); `required_variables: []`, same `optional_variables` as `character_voice`, `fallback_policy: fail_loudly_if_bundled_missing` |
| Adoption registry | `scripts/architecture/adoption-registry.yaml` | add `analysis/voice_check: true` (governed adoption debt until runtime evidence lands) + `features.analysis.modes.voice_check: {requires_runtime_evidence: true}` |

The checker's run prompt (user channel) carries the chapter dialogue + stored
descriptive profile + metric-delta as category-3 runtime data (RULE-02a),
exactly as `character_voice` carries attributed dialogue + metrics. No
required template variables (`required_variables: []`); KB world-context
variables are optional (a project may legitimately have none — RULE-11
graceful degradation).

---

## Decision 4 — Module home: `analysis/` (not `writing/`)

WRITE-010's implementation lives in `analysis/`, mirroring the ANAL-008
sibling and the ANAL-003/004/005 analysis pattern.

**Rationale:**
- WRITE-010 is **read-only**: it reads chapter dialogue + reads stored profiles
  + produces a flag/score report. It mutates nothing. The `writing/` area is
  for generation/transform operations (WRITE-001..009 all generate or transform
  chapter text). A non-mutating check is analysis, not writing.
- It **reuses the analysis Foundation** (`DialogueParser`,
  `VoiceMetricsAnalyzer`) and is checking-like (deterministic delta + LLM
  qualitative judgment) — the same shape as the analysis features. Placing it
  in `analysis/` keeps all voice-analysis siblings cohesive (character_voice +
  voice_check + future voice_drift) in one module (RULE-06 cohesion).
- Dependencies stay one-directional: `analysis → profiles (consumer) →
  kb.schemas`; no `writing/` coupling, no cycles (RULE-07).

**Feature identity preserved:** the feature keeps its ID `WRITE-010` and its
"Writing" placement in `docs/features/INDEX.md` (user-facing taxonomy: it is a
revision-time aid the author runs from the editor). The INDEX grouping is a
user-facing category, not a module constraint; the developer-reference
frontmatter paths (`service`, `contract`, `router`, `prompt`) point to
`analysis/`, and that is documented in the spec's Technical section. No
renumbering → no broken cross-references (ANAL-008, ANAL-009, WRITE-006 all
link to WRITE-010).

---

## Decision 5 — Scope boundary: flag+score only, NO rewrite suggestions (YAGNI)

WRITE-010 v1 flags inconsistent lines + scores each character. It does NOT
generate suggested rewrites.

**Rationale:**
- Rewrite generation is a separate capability with its own contract (WRITE-004
  Rewrite Selection). Coupling it into the checker would bloat the checker
  (two concerns in one agent: judge + rewrite) and duplicate WRITE-004's
  logic. RULE-06 (one responsibility per file/agent).
- The author workflow is: run the checker → see flagged lines + reasons →
  optionally select a flagged line and run WRITE-004 (existing, stable) to
  rewrite it. That composes two clean features instead of fusing them.
- YAGNI: there is no approved requirement for inline rewrite suggestions from
  the checker. If/when that becomes a requirement, it is a separate spec
  (rewrite-on-flagged-line) reusing WRITE-004.

This is a scope decision, recorded so the checker agent's output type carries
`flagged_lines` + `reasons` + `score` — never `suggested_rewrite`.

---

## Consequences

**Positive:**
- ADR-055 Risk #1 is **closed** — the checking path now carries structured
  metrics through the ADR-050 consumer contract (no SSOT bypass).
- The checker is decoupled from KB internals — it depends only on the consumer
  contract + the analysis Foundation.
- `LLMIntent.VOICE` gains its second governed mode (`voice_check`), reusing
  the route ADR-055 made routeable. ANAL-009 (drift) will add a third.
- Scoring is deterministic + reproducible (the blend is pure Core logic).
- Generation is provably unaffected (`formatted_voice_profiles` never reads
  `voice_metrics`).

**Negative / Tradeoffs:**
- One new field on a shared model (additive, optional, acyclic) — minor.
- A frozen dataclass holds a mutable `VoiceMetrics` (see Risks #1) — accepted;
  treated read-only by the checker.
- Two new governed prompt artifacts (the `voice_check` template + manifest/
  registry entries) — additive prompt surface, runtime evidence tracked per
  ADR-056.
- The checker adds a NEW agent + scoring module + service + SSE router +
  panel + hook + i18n — standard analysis-vertical surface (mirrors ANAL-008).

**Constraints introduced:**
- `formatted_voice_profiles` MUST NOT read `voice_metrics` (generation never
  sees raw metrics — ADR-055 constraint preserved).
- The checker MUST obtain profiles via `VoiceProfileConsumer.assemble_for_checking()`
  — never via direct `KBEntity.metadata` access (ADR-050).
- A character with no stored `voice_analysis` MUST yield a graceful "no
  profile" result (RULE-11), not an error.

---

## CR-04 Cross-Feature Impact (coherence)

Extending `CharacterVoiceProfile` is a **cross-feature contract change**: the
model flows through generation AND checking. This ADR requires coherence
end-to-end, not feature-local:

- **Producer (ANAL-008 write path):** unchanged. ANAL-008 already writes
  `speech.voice_analysis.voice_metrics` (ADR-055). WRITE-010 adds no write.
- **Consumer (generation read path):** unchanged. `assemble_for_generation`
  → `formatted_voice_profiles` renders `speech_summary` and never reads
  `voice_metrics`. Verified: the extended field is never referenced by the
  generation projection.
- **Consumer (checking read path):** enriched. `assemble_for_checking()`
  returns profiles that now carry `voice_metrics` when ANAL-008 profiled the
  character. WRITE-010 reads metrics via this contract.

This is the CR-04 lesson applied (architectural-discipline §7): the spec
defines producer + generation-consumer + checking-consumer projections
together. The earlier ANAL-008 spec's claim that the checking path "surfaces
structured profiles including `voice_metrics`" was aspirational; this ADR's
model extension is the implementation that makes it true.

---

## Retrofit-Plan (mandatory — model + prompt-mechanics change, adr-process §D.4)

### 1. Inventory of affected paths

**Model / consumer (Core):**
- `core/profiles/models.py` — add `voice_metrics: VoiceMetrics | None = None`
  to `CharacterVoiceProfile`.
- `core/profiles/_voice_extraction.py::build_character_voice_profile()` —
  parse `speech.voice_analysis.voice_metrics` → construct `VoiceMetrics`.
- `core/profiles/assembly.py` (and the Backend provider impl behind
  `assemble_for_checking`) — surface `voice_metrics` on the returned profiles.
  (`assemble_for_checking` signature unchanged.)

**Checker (Core):**
- `core/analysis/voice_check_scoring.py` — NEW: deterministic delta + blend
  (pure functions, fully unit-testable).
- `core/agents/character_voice_checker_agent.py` +
  `character_voice_checker_types.py` — NEW: `CharacterVoiceCheckerAgent`
  (`NarrareAgent`, structured output, ONE LLM call).

**Prompt surface:**
- `core/prompts/route_table.py` — add `"voice_check"` to VOICE
  `allowed_context_modes`.
- `core/prompts/_bundled/analysis/en/voice_check/system.md` — NEW governed
  EN template (9-section, Mode 1).
- `scripts/architecture/prompt-surface-manifest.yaml` — add VOICE/`voice_check`.
- `scripts/architecture/adoption-registry.yaml` — add `analysis/voice_check`
  + `features.analysis.modes.voice_check`.

**Backend:**
- `apps/api/narrare/analysis/contracts_voice_check.py` —
  `CharacterVoiceCheckerServiceProtocol`.
- `apps/api/narrare/analysis/schemas_voice_check.py` — request/response/event.
- `apps/api/narrare/analysis/voice_check_service.py` — Mode-1 PromptComposer
  service (binds `VoiceProfileConsumer`, reuses Foundation + scoring + agent).
- `apps/api/narrare/analysis/dependencies_voice_check.py` — DI.
- `apps/api/narrare/analysis/router_voice_check.py` — SSE
  `POST /analysis/voice-check/{chapter_id}` (chapter-scoped, mirrors
  coreference) under `AI_ANALYSIS_LIMITER`.

**Frontend:**
- `CharacterVoiceCheckerPanel` + `useCharacterVoiceCheck`
  (`useAIOperation` — no manual AbortController, ADR-043) + SSE client + i18n
  (en/de/fr). Wired into the editor analysis panels next to
  `CharacterVoicePanel`.

### 2. Migration steps per path (atomic, independently testable)

1. Add `voice_metrics` to `CharacterVoiceProfile` + extend the builder (pure;
   unit-test: field populated when `voice_analysis.voice_metrics` present,
   `None` otherwise; existing flows unaffected).
2. Extend the checking-path provider to surface `voice_metrics` (unit-test the
   consumer returns enriched profiles; generation projection unchanged).
3. Add the `voice_check` route entry + governed template + manifest/registry.
4. Build the scoring module (pure unit tests: delta normalization, blend
   weights, thresholds green/yellow/red).
5. Build the checker agent (TestModel structured-output tests; ADR-035
   validation).
6. Build the Backend service (Mode-1 PromptComposer; Fake consumer) + SSE
   router + schemas/contracts/dependencies.
7. Build the Frontend panel + hook + SSE client + i18n.

### 3. Breaking-change assessment

- Model change is additive + optional (`None` default) → backward compatible.
  Existing `CharacterVoiceProfile(...)` call sites that omit `voice_metrics`
  behave identically.
- Generation projection is untouched → `{{character_voice_profiles}}` content
  is byte-identical for every character (verified: `formatted_voice_profiles`
  does not read the new field).
- `assemble_for_checking()` signature is unchanged (same return type, richer
  instances) → no caller breaks.
- `voice_check` is a NEW context_mode + template → additive prompt surface;
  no existing caller routes VOICE to `voice_check` yet, so no break.

### 4. Checker (governance) update plan

- `_check_prompt_orphan.py` — the new `voice_check` template is reachable
  (VOICE routeable, `voice_check` in `allowed_context_modes`), so NO orphan
  exemption is needed. Verify the ORPHAN-TEMPLATE gate passes without one.
- `prompt-surface-manifest` checker (ADR-037) — VOICE/`voice_check` must be
  declared; the manifest INTENT-COMPLETENESS gate now recognises it.
- Prompt-Path-Compliance test (ADR-046 §D.1): assert VOICE/`voice_check`
  resolves through PromptComposer Mode 1 to
  `_bundled/analysis/en/voice_check/system.md` (no inline fallback).
- ADR-056 commit gate: `voice_check` runtime evidence (agent + service probes)
  is required to move it off governed adoption debt. Declared now; runtime
  evidence lands at implementation.

### 5. Test update plan

- Model round-trip + `None`-default tests; builder tests (metric surfaced /
  absent graceful); generation-projection regression test (assert
  `formatted_voice_profiles` output unchanged with and without
  `voice_metrics`).
- Scoring module unit tests (delta, blend, thresholds).
- Agent TestModel structured-output tests (ADR-035).
- Backend integration + SSE tests (Fake consumer; graceful "no profile"
  result for characters without `voice_analysis`).
- Frontend Vitest (panel, hook, SSE client, i18n).

---

## Risks Surfaced for Coordinator/User Decision (before implementation)

These are NOT blockers for approving this ADR, but should be acknowledged
before implementation planning:

1. **Frozen dataclass ↔ mutable `VoiceMetrics`.** `CharacterVoiceProfile` is
   `frozen=True`; `VoiceMetrics` is a (mutable) Pydantic model. The dataclass
   freeze guarantees reference identity is stable; the checker treats
   `VoiceMetrics` as read-only, so this is safe in practice. If we later want
   full immutability, mark `VoiceMetrics` `frozen=True` — but that is an
   ADR-055 contract-side change (affects ANAL-008's write path) and is out of
   scope here. Low risk; no action needed before WRITE-010.

2. **Metric-delta normalization weights.** The blend weights (metric-delta
   sub-score vs. agent qualitative sub-score) and the per-metric normalization
   are tuning parameters. The spec defines the contract (deterministic blend in
   a pure module, thresholds green/yellow/red); the exact weights are
   calibrated at implementation / eval time (ADR-032 Pydantic Evals). Not a
   decision blocker.

3. **Checker-vs-ANAL-009 overlap.** WRITE-010 (per-chapter consistency check
   against a stored profile) and ANAL-009 (voice drift over time) both read
   `voice_metrics`. They are distinct (check = current-chapter-vs-profile;
   drift = profile-vs-profile-over-time) but share the Foundation + the
   scoring-delta primitive. The scoring module should expose the delta as a
   reusable primitive so ANAL-009 reuses it rather than duplicating. Flagged
   for the ANAL-009 spec update (ADR-055 Review Trigger already covers it).

4. **Dialogue attribution reuse.** WRITE-010 reuses `DialogueParser`
   (deterministic) for per-character utterance extraction in the checked
   chapter. As with ANAL-008, the checker agent resolves residual ambiguous
   speakers inline (no ANAL-005 Coreference coupling) — same ADR-055 Decision 3
   rationale. No new coupling introduced.

No decision requires a user call before implementation beyond approving this
ADR + the spec rewrite.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02b | ✅ | `voice_check` prompt = PromptComposer Mode 1 (intent + `voice_check` context_mode + governed EN template); no inline f-string, no production fallback, no system-prompt in user channel. |
| RULE-03 | ✅ | Contracts (`CharacterVoiceCheckerServiceProtocol`, `CharacterVoiceCheckerAgent` Protocol, the `CharacterVoiceProfile.voice_metrics` extension) defined before implementation. |
| RULE-04 | ✅ | Modularised: scoring in `voice_check_scoring.py`; agent in `character_voice_checker_agent.py` + `_types.py`; Backend split into `contracts_voice_check.py` / `schemas_voice_check.py` / `voice_check_service.py` / `router_voice_check.py` / `dependencies_voice_check.py`. |
| RULE-05/06 | ✅ | Core owns model extension + scoring + agent; Backend owns service/router; one responsibility per file. The checker reads via the consumer contract, not KB directly. |
| RULE-07 | ✅ | `analysis → profiles (consumer) → kb.schemas` read-direction only; no `apps/`→`core` cycle; `profiles → kb.schemas` import verified acyclic. |
| RULE-11 | ✅ | Character without `voice_analysis` → graceful "no profile" result; stale profile surfaced with reduced confidence (ADR-050 freshness contract); missing KB context renders empty, not crash. |
| RULE-13 | ✅ | SSE + non-streaming share the service interface (mirrors ANAL-005/008). |
| RULE-22 | ✅ | Cross-feature coherence: producer (ANAL-008, unchanged) + generation consumer (unchanged) + checking consumer (enriched via this ADR) defined together (CR-04). |
| ADR-021 | ✅ | Metric-delta uses deterministic `VoiceMetrics`; LLM handles only qualitative judgment (same hybrid tier as ANAL-003/008). |
| ADR-035 | ✅ | Checker agent structured output validated. |
| ADR-050 | ✅ | Checker consumes via `VoiceProfileConsumer.assemble_for_checking()` — no SSOT bypass. |
| ADR-055 | ✅ | Closes Risk #1 (checking-path model gap); reuses the routeable VOICE intent + Foundation; preserves the "metrics never reach generation" constraint. |

---

## Review Trigger

- [ ] When this ADR is implemented — verify the checker reads `voice_metrics`
      via `VoiceProfileConsumer.assemble_for_checking()` (not KB directly),
      and that `formatted_voice_profiles` does not read the new field.
- [ ] When ANAL-009 (Voice Drift) is implemented — verify it reuses the
      scoring module's delta primitive (no duplication) and reads
      `voice_metrics` via the same consumer contract; update ANAL-009's stale
      "map to SpeechPatterns" assumption to ADR-055's nested contract.
- [ ] If rewrite-on-flagged-line becomes a requirement — write a separate
      spec reusing WRITE-004 (Decision 5 rejected fusing it into the checker).
- [ ] If `VoiceMetrics` immutability is required — a follow-up ADR marking it
      `frozen=True` (ADR-055 contract-side change).
- [ ] If metric-delta blend weights prove unstable — recalibrate via
      ADR-032 Pydantic Evals (the weights are pure-logic, eval-tunable).

---

## Cross-References

- ADR-021 — deterministic analysis (pre-names `core/analysis/voice_metrics.py`).
- ADR-035 — agent output validation.
- ADR-050 Decision 3 — `VoiceProfileConsumer` contract (the checking-path
  contract this ADR satisfies / enriches).
- ADR-054 — Mode-1 PromptComposer mandate.
- ADR-055 — character-voice storage contract + VOICE routeable (Risk #1 closed
  here; route + Foundation reused).
- ADR-056 — runtime-aware adoption gate (`voice_check` runtime evidence).
- WRITE-010 spec — feature-level implementation contract (rewritten against
  this ADR).
