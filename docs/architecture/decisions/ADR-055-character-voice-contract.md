# ADR-055 — Character Voice Storage Contract & VOICE Prompt Surface

> **Status:** ✅ Accepted + Implemented (2026-06-29)
> **Date:** 2026-06-26
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-021 (deterministic analysis), ADR-035 (agent output validation),
> ADR-037/046/049 (prompt-surface manifest + path compliance), ADR-040 (voice SSOT
> module), ADR-050 (voice consumer contract), ADR-054 (Mode-1 PromptComposer mandate),
> CONSTRAINTS.md RULE-02/02b/03/04/05/06/07/08/11/13/22, CR-04 (cross-feature coherence)

> **Implementation note (2026-06-29):** This contract is implemented across all
> layers — Layer 0 (`e12f6539`, `SpeechPatterns` `voice_analysis`), Layer 1
> (`ee0c148f`, VOICE routeable + `character_voice` template), Layer 2 (`96fca8e1`,
> `DialogueParser` + `VoiceMetricsAnalyzer` + `CharacterVoiceAgent` + consumer
> merge), Layer 3 (`74b7c83a`, Backend `CharacterVoiceService` + SSE), Layer 4
> (`ce392ac4`, Frontend panel + hook + i18n). Validated green: `just check` 9/9,
> 8341 backend + 2287 frontend tests, 0 architecture/AI-UX violations. The
> `character_voice` route is **runtime-verified** — probes landed in `ee1cfc50`,
> and ADR-056 made the local commit-gate runtime-evidence-aware, so it witnesses
> the committed markers.

---

## Context

ANAL-008 (Character Voice Profiling) is the next vertical in the Voice lane
(ANAL-007 author → ANAL-008 character → ANAL-009 drift → WRITE-010 checker).
This ADR specifies the **storage data contract** for machine-derived character
voice analysis and the **VOICE prompt-surface route** that ANAL-008 needs. It
also records three supporting design decisions (metrics strategy, dialogue
attribution strategy, foundation placement).

### Verified state (grounded, not assumed)

| Concern | State | Location |
|---------|-------|----------|
| `LLMIntent.VOICE` | EXISTS, categorized ANALYSIS, profile "balanced" | `core/llm/intents.py` |
| VOICE routeable status | **NON-routeable** — "no dedicated bundled PromptComposer template yet" | `core/prompts/route_table.py::NON_ROUTEABLE_INTENTS` |
| Character-voice GENERATION injection | **Live** — reads `KBEntity.metadata["speech"]` → flat string → `{{character_voice_profiles}}` | `core/profiles/_voice_extraction.py::get_speech_data()` → `build_character_voice_profile()` → `ProjectWritingProfile.formatted_voice_profiles` |
| `SpeechPatterns` schema | 4 fields (`typical_phrases`, `dialect`, `vocabulary_quirks`, `body_language`) + `ConfigDict(extra="allow")` — extensible WITHOUT migration | `core/kb/schemas/character.py` |
| `get_speech_data()` | Reads ONLY those 4 fields; extra fields are stored but IGNORED by generation | `core/profiles/_voice_extraction.py` |
| `CharacterMetadata` pattern | Nested sub-models (`appearance`/`personality`/`speech`/`relationships`/`development`) — each a separate `BaseModel` | `core/kb/schemas/character.py` |
| Author-voice storage | **Aspirational only** — `{{author_style_examples}}` appears nowhere except the ANAL-007 spec; `ProjectWritingProfile` is not yet runtime SSOT (SET-006 deferred) | — |
| Established analysis pattern | Deterministic analyzer + `NarrareAgent` structured output + governed EN template + SSE router + panel (ANAL-003/004/005) | `core/analysis/`, `apps/api/narrare/analysis/` |

### Root cause (why this ADR is needed)

The current `docs/features/analysis/ANAL-008-voice-character.md` prescribes a
field-mapping from a hypothetical `CharacterVoiceProfile` to the live
`SpeechPatterns` contract:

```
verbal_tics    → metadata["speech"]["typical_phrases"]
formality      → metadata["speech"]["dialect"]        (as descriptor string)
speech_patterns→ metadata["speech"]["vocabulary_quirks"] (as JSON string)
examples       → metadata["speech"]["body_language"]  (as examples context)
```

**This mapping is semantically wrong and lossy.** (2× Why)

1. *Why is it wrong?* It would store example dialogue quotes inside `body_language`,
   formality inside `dialect`, and a JSON blob inside `vocabulary_quirks` — corrupting
   the human-authored meaning of each KB field and overwriting user data.
2. *Why was it written this way?* The spec predates the live `SpeechPatterns` contract.
   It assumed a separate table that never materialised; `extra="allow"` already lets
   `SpeechPatterns` grow without migration. The correct fix is to **extend the actual
   live contract** rather than work around it with a lossy projection.

The second root cause: `LLMIntent.VOICE` has existed since `project-init` but is
**non-routeable** (no bundled template). Every analysis feature needs a governed
prompt surface (ADR-054 retired inline feature-prompt debt to zero; ANAL-008 must
not reintroduce it). ANAL-008 cannot ship until VOICE becomes routeable with a
governed EN template.

---

## Decision Drivers

- **RULE-02/02b** — ANAL-008's prompt MUST be PromptComposer Mode 1 (intent +
  `context_mode` + governed EN template). No inline f-strings, no production fallback.
- **RULE-03** — The storage + consumer + agent contracts MUST exist before implementation.
- **RULE-04** — Modularise; `SpeechPatterns` must not bloat into one giant flat list.
- **RULE-05/06/07** — Core owns the schema + consumers; no `writing/`→`profiles/` import
  cycles; one responsibility per file.
- **ADR-021** — Voice metrics must be **deterministic** (ANAL-009 drift comparison and
  WRITE-010 checking need stable, comparable numbers; LLM-only metrics are non-deterministic).
- **ADR-040/050** — Voice data flows through `core/profiles/` SSOT and the
  `VoiceProfileConsumer` contract; the storage extension must be consumable by that path.
- **CR-04** — Extending `SpeechPatterns` is a cross-feature contract change affecting
  generation (`{{character_voice_profiles}}`); the change must be coherent end-to-end,
  not feature-local.
- **architectural-discipline §1/§4** — Root-cause solution only; no lossy workarounds.

---

## Decision 1 — Storage: extend `SpeechPatterns` with a nested `voice_analysis` sub-model (Option A)

### Options Considered

#### Option A — Extend `SpeechPatterns` with a nested `voice_analysis` sub-model (CHOSEN)

Add ONE optional nested field `voice_analysis: VoiceAnalysis | None` to
`SpeechPatterns`. Keep the 4 existing human-authored flat fields untouched.
`VoiceAnalysis` groups the machine-derived data into two sub-concerns:

```python
class VoiceMetrics(BaseModel):
    """Deterministic numeric metrics — for ANAL-009 drift / WRITE-010 checking.
    NOT rendered into generation."""
    model_config = ConfigDict(extra="allow")

    avg_sentence_length: float | None = None
    sentence_length_std: float | None = None
    type_token_ratio: float | None = None
    avg_syllables_per_word: float | None = None
    contraction_rate: float | None = None
    verbal_tic_frequency: dict[str, float] | None = None   # n-gram → rate
    punctuation_profile: dict[str, float] | None = None    # habit → rate


class VoiceAnalysis(BaseModel):
    """Machine-derived character voice profile. ANAL-008 writes this;
    the extended consumer renders the descriptive group into generation."""
    model_config = ConfigDict(extra="allow")

    # Descriptive (rendered into {{character_voice_profiles}} by the extended consumer)
    formality: float | None = None              # 0.0 casual – 1.0 formal
    vocabulary_level: str | None = None         # simple | moderate | complex
    sentence_profile: str | None = None         # short | medium | long | varied
    emotional_range: str | None = None          # restricted | moderate | expressive
    cultural_regional_markers: str | None = None  # intrinsic markers that aid generation
    voice_examples: list[str] | None = None     # curated representative quotes

    # Metric (for comparison ONLY — never rendered into generation)
    voice_metrics: VoiceMetrics | None = None
```

> **Persistence scope (no data loss):** the agent's INTRINSIC qualitative outputs
> (formality, vocabulary level, sentence profile, emotional range, cultural/regional
> markers, curated examples) persist into the `VoiceAnalysis` descriptive group and
> render into generation. The agent's COMPARISON output (`distinctiveness_notes`,
> which is relative to whichever other characters were analyzed in the same run) is
> NOT persisted on the character profile — it is not an intrinsic property; it is
> surfaced in the UI panel as a per-analysis review aid and recomputed on each run.
> Metrics come from the deterministic `VoiceMetricsAnalyzer`, never the agent.

`SpeechPatterns` gains exactly one field:

```python
class SpeechPatterns(BaseModel):
    model_config = ConfigDict(extra="allow")
    # Human-authored (unchanged):
    typical_phrases: list[str] | None = None
    dialect: str | None = None
    vocabulary_quirks: str | None = None
    body_language: str | None = None
    # Machine-derived (ANAL-008 / ADR-055):
    voice_analysis: VoiceAnalysis | None = None
```

**Migration-free**: `extra="allow"` is inherited everywhere; the new field is
optional with a `None` default, so existing rows deserialize unchanged.

**Pros:**
- Single source of truth — one `speech` block per character; no second `metadata["voice_profile"]` to drift.
- Clean human/machine separation (the 4 human fields stay flat; all machine data nests).
- Mirrors the established `CharacterMetadata` sub-model pattern exactly.
- Migration-free via `extra="allow"` + optional default.
- Descriptive-vs-metric boundary is structural (two sub-models), not a comment convention.

**Cons:**
- `get_speech_data()` consumer must be extended to read the descriptive group.
- Slightly deeper nesting (3 levels for metrics).

#### Option B — Flat fields on `SpeechPatterns` + separate `metadata["voice_profile"]`

Add the 5 descriptive fields + metrics flat to `SpeechPatterns`, AND/OR store a
separate `metadata["voice_profile"]` blob.

**Pros:** No nesting.

**Cons:** Two voice sources → drift (violates one-responsibility); mixes 4 human + 6
machine fields at one level (poor separation); a separate `voice_profile` key
duplicates the `speech` source-of-truth. Rejected.

#### Option C — The lossy mapping from the current ANAL-008 spec

Semantically corrupts KB fields (quotes in `body_language`, formality in `dialect`).
Violates no-quick-fix / root-cause. Rejected.

### Decision

**Option A.** Extend `SpeechPatterns` with a nested `voice_analysis: VoiceAnalysis | None`.
Descriptive data renders into generation; metric data does not.

### Rationale

`CharacterMetadata` already groups every concern as a nested sub-model
(`AppearanceFields`, `PersonalityFields`, `SpeechPatterns`, …). A nested
`VoiceAnalysis` is the same pattern applied to the machine-derived half of speech
data. It keeps the human-authored 4 fields semantically pure (ANAL-008 AUGMENTS,
never overwrites user data), and the descriptive/metric split makes the generation
boundary structural: the consumer reads descriptive fields and provably never the
metric block.

### Sustainability check

1. *Correct in 3 months?* Yes — WRITE-010 and ANAL-009 read `voice_metrics`;
   generation reads descriptive fields; both share one source.
2. *Hard-to-undo coupling?* None — additive optional field, no migration.
3. *Simplest correct solution?* Yes — one optional nested field, no second store.
4. *Design intent clear?* Yes — sub-model names (`VoiceAnalysis`, `VoiceMetrics`)
   are self-documenting.

---

## Decision 2 — Metrics: hybrid deterministic + LLM (ADR-021, mirrors ANAL-003)

### Options Considered

#### Option A — Hybrid: deterministic `VoiceMetricsAnalyzer` (Core) + `CharacterVoiceAgent` (NarrareAgent) (CHOSEN)

A shared deterministic `VoiceMetricsAnalyzer` computes per-utterance hard metrics
(sentence-length distribution, type-token ratio, avg syllables/word, contraction
rate, verbal-tic n-gram frequency, punctuation habits). `CharacterVoiceAgent`
consumes text + metrics in ONE LLM call and produces qualitative judgments
(formality register, emotional expressiveness, cultural/regional markers, speech-
pattern descriptions, distinctiveness vs other characters, curated example
selection). This is exactly the ANAL-003 formula+agent split.

#### Option B — LLM-only metrics

Non-deterministic; unsuitable for ANAL-009 drift comparison and WRITE-010 checking
(both need stable, comparable numbers). Violates ADR-021. Rejected.

#### Option C — Deterministic-heavy (formulas only)

Misses qualitative aspects formulas cannot capture (emotional register, cultural
markers, distinctiveness judgments). Rejected.

### Decision

**Option A.** Deterministic metrics for measurement + LLM for qualitative
understanding. Mirrors ANAL-003 and ADR-021's hybrid tier.

> **ADR-021 alignment note:** ADR-021's feature table lists "ANAL-007/008/009 Voice"
> under "Deterministic (spaCy structural + embeddings)". ANAL-008 uses the **hybrid**
> tier (deterministic metrics + LLM qualitative) — the same tier ANAL-003 (Readability)
> and ANAL-004 (POV) use. This is consistent with ADR-021's tiering *principle*
> (measurement deterministic, understanding qualitative) and its pre-named
> `core/analysis/voice_metrics.py` module; the LLM agent handles only the
> qualitative half, never the measurement half. No ADR-021 amendment is required.

---

## Decision 3 — Attribution: self-contained hybrid (NO Coreference coupling)

### Options Considered

#### Option A — Deterministic `DialogueParser` + inline ambiguous-speaker resolution in `CharacterVoiceAgent` (CHOSEN)

A deterministic `DialogueParser` splits quotes + tag-attributes ("said Elena",
action beats) with confidence and computes per-utterance metrics. The
`CharacterVoiceAgent` resolves any remaining ambiguous speakers INLINE in the same
single LLM call that produces the qualitative profile. ANAL-005 (Coreference) is
NOT coupled as a runtime pre-step.

#### Option B — Couple ANAL-005 Coreference as a runtime pre-step

Doubles LLM cost/latency and creates a cross-feature runtime dependency. Rejected —
keeps ANAL-008 independently testable and single-model-call.

#### Option C — Parser-only (no LLM attribution)

Poor coverage of untagged/pronoun dialogue common in literary prose. Rejected.

### Decision

**Option A.** Self-contained hybrid. Coreference becomes an optional future
enhancement, not a dependency.

### Rationale

ANAL-008's job is per-character voice profiling, not pronoun resolution. Coupling
Coreference would import ANAL-005's cost and failure modes into a feature that can
resolve its own (narrower) attribution ambiguity inline. This keeps ANAL-008
decoupled, independently testable, and a single model call.

---

## Decision 4 — VOICE prompt-surface: new `character_voice` route (CHOSEN)

### Options Considered

#### Option A — Promote `LLMIntent.VOICE` from non-routeable to routeable, with a dedicated `character_voice` context_mode + governed EN template (CHOSEN)

- Remove `LLMIntent.VOICE` from `route_table.NON_ROUTEABLE_INTENTS`.
- Add `LLMIntent.VOICE: "analysis"` to `INTENT_TO_CATEGORY` and
  `LLMIntent.VOICE: "character_voice"` to `INTENT_TO_MODE`.
- Add `ROUTE_CONFIGS[LLMIntent.VOICE] = PromptRouteConfig("analysis", "character_voice", allowed_context_modes={"character_voice"})`.
- Create governed EN template `core/prompts/_bundled/analysis/en/character_voice/system.md`.
- Register VOICE/`character_voice` in the prompt-surface manifest and adoption registry.

This resolves the "no template yet" gap the route table explicitly carries.

#### Option B — Fold character voice into `LLMIntent.ANALYSE` + a `character_voice` context_mode (like ANAL-003/004/005)

Minimal route-table change. But it orphans the dedicated `LLMIntent.VOICE` (which has
a specific docstring scope) forever and loses semantic clarity. Rejected — VOICE is a
distinct, category-worthy concern.

### Decision

**Option A.** The `VOICE` intent serves all three voice features via distinct
context_modes — `character_voice` (ANAL-008), `author_voice` (ANAL-007, deferred),
`voice_drift` (ANAL-009, deferred). This mirrors how `PLAN` serves
outline/timeline/character_arc/timeline_extraction. ANAL-008 ships the first
(`character_voice`) mode and makes the intent routeable.

### Rationale

`LLMIntent.VOICE` exists with a specific scope ("author's voice, narrative distance,
stylistic patterns, and character dialogue distinctiveness"). Making it routeable
once, with multi-mode support, is cleaner than folding voice into the generic
ANALYSE intent or leaving VOICE non-routeable. Each future voice feature adds a
context_mode + template, not a new intent.

---

## Decision 5 — Foundation placement: documented in the ANAL-008 spec, NOT a registry entry

`DialogueParser` and `VoiceMetricsAnalyzer` are reusable Core analysis
infrastructure (consumed by ANAL-008 now; WRITE-010 and ANAL-009 later). They are
**not** user-facing features, so they do NOT get a `docs/features/INDEX.md` entry
(INDEX.md is for user-facing features). They live as a **Foundation section in the
ANAL-008 spec** that documents: what is reusable, who consumes it, why it is built
now (justified reuse, not YAGNI), and where it lives.

**Module homes (per ADR-021):**
- `core/analysis/voice_metrics.py` — `VoiceMetricsAnalyzer` (pre-named by ADR-021).
- `core/analysis/dialogue_parser.py` — `DialogueParser` (orchestrates extraction +
  attribution + per-utterance metric computation; may consume `core/nlp/` primitives
  per ADR-021 `nlp/dialogue.py`, respecting RULE-07 `analysis → nlp`).
- `core/agents/character_voice_agent.py` + `character_voice_types.py` — `CharacterVoiceAgent`.

---

## Consequences

**Positive:**
- One source of truth for character voice (`speech.voice_analysis`); no drift.
- Machine-derived metrics are deterministic and comparable (ADR-021) — ready for
  ANAL-009 drift and WRITE-010 checking without rework.
- `LLMIntent.VOICE` becomes routeable — closes a long-standing "no template yet" gap
  and unblocks the whole voice lane.
- Generation automatically benefits from richer voice data (the extended consumer
  renders the descriptive group into `{{character_voice_profiles}}`).
- Human-authored KB fields stay pure; ANAL-008 augments, never overwrites.

**Negative / Tradeoffs:**
- `get_speech_data()` consumer must be extended (descriptive fields rendered; metric
  block excluded) — a contract change to a generation-path consumer.
- Three new types (`VoiceAnalysis`, `VoiceMetrics`, and the agent output type) plus
  two Foundation analyzers add test surface.
- VOICE leaves `NON_ROUTEABLE_INTENTS` — the manifest/route-table/registry must be
  updated together (see Retrofit-Plan).

**Constraints introduced:**
- The extended `get_speech_data()` MUST render `voice_analysis` descriptive fields
  and MUST NOT render `voice_metrics` (generation never sees raw metrics).
- ANAL-008 MUST set `updated_at` on the KB entity so the existing
  `profiles/_freshness.py::is_stale()` freshness signal keeps working.
- No `writing/`→`profiles/` import cycle (RULE-07); consumers live in `core/profiles/`.

---

## CR-04 Cross-Feature Impact (generation coherence)

Extending `SpeechPatterns` is a **cross-feature contract change**: the generation
pipeline reads `metadata["speech"]`. This ADR requires the change to be coherent
end-to-end, not feature-local:

- **Producer (ANAL-008 write path):** writes `speech.voice_analysis` (descriptive +
  metric) and bumps `updated_at`.
- **Consumer (generation read path):** `get_speech_data()` extended to render the
  descriptive group into `CharacterVoiceProfile.speech_summary`, which
  `ProjectWritingProfile.formatted_voice_profiles` already renders into
  `{{character_voice_profiles}}`. The metric block is excluded.
- **Consumer (ADR-050 checking path):** WRITE-010/ANAL-009 will consume voice
  data via `VoiceProfileConsumer.assemble_for_checking()`. NOTE: the current
  `CharacterVoiceProfile` model carries only a flat `speech_summary` — it does
  NOT yet carry structured `voice_metrics`. Surfacing metrics on the checking
  path (whether by extending `CharacterVoiceProfile` or by having the checker
  read `speech.voice_analysis.voice_metrics` directly) is a WRITE-010/ANAL-009
  decision, NOT an ANAL-008 concern. ANAL-008's only obligation here is to WRITE
  the metrics to KB so the data exists for the future checker. (See Risks below.)

This is exactly the CR-04 lesson (architectural-discipline §7): "documented ≠
implemented"; the spec defines producer + consumer + checking projection together.
Feature-local green is insufficient.

---

## Retrofit-Plan (mandatory — prompt-mechanics change, per adr-process.md §D.4)

This ADR introduces a new route (`LLMIntent.VOICE` routeable) and a new
`context_mode`, which are prompt-mechanics changes. Retrofit-Plan:

### 1. Inventory of affected paths
- `core/prompts/route_table.py` — `NON_ROUTEABLE_INTENTS` (remove VOICE);
  `INTENT_TO_CATEGORY` / `INTENT_TO_MODE` (add VOICE); `ROUTE_CONFIGS` (add VOICE).
- `core/prompts/composer.py` — `_INTENT_TO_CATEGORY` / `_INTENT_TO_MODE` (add VOICE)
  if the composer maintains its own copy (verify; the route_table is the SSOT).
- `core/prompts/_bundled/analysis/en/character_voice/system.md` — new governed EN
  template (9-section skeleton, ADR-054 Mode 1).
- `scripts/architecture/prompt-surface-manifest.yaml` — add VOICE/`character_voice`.
- `scripts/architecture/adoption-registry.yaml` — add VOICE/`character_voice` mode
  with `requires_runtime_evidence: true` (ADR-040 Decision 4).
- `core/profiles/_voice_extraction.py` — extend `get_speech_data()` to render the
  descriptive group (NOT `voice_metrics`).
- `core/kb/schemas/character.py` — add `VoiceAnalysis`, `VoiceMetrics`, and the
  `voice_analysis` field to `SpeechPatterns`.

### 2. Migration steps per path (atomic, independently testable)
1. Add `VoiceMetrics` + `VoiceAnalysis` to `character.py` (pure schema; unit-test
   round-trip + `None` default for existing rows).
2. Extend `get_speech_data()` (unit-test: descriptive rendered, metrics excluded).
3. Add the VOICE route (route_table + composer) and remove from NON_ROUTEABLE.
4. Create the governed EN template.
5. Register in manifest + adoption registry.
6. Build Foundation analyzers + agent (Core).
7. Build Backend service/SSE router (Mode 1 PromptComposer).
8. Build Frontend panel + hook + SSE client + i18n.

### 3. Breaking-change assessment
- Schema change is additive + optional → backward compatible (no migration).
- VOICE leaving NON_ROUTEABLE is a one-way promotion; no production code currently
  routes VOICE (it is non-routeable), so no caller breaks.
- The `get_speech_data()` change adds rendered content to `{{character_voice_profiles}}`
  for characters that HAVE `voice_analysis`; characters without it render identically
  to today (no regression for existing user-authored-only characters).

### 4. Checker update plan
- `_check_prompt_orphan.py` — the new `character_voice` template must be reachable
  (VOICE routeable), so NO orphan exemption is needed (unlike the old `story_suggest`
  case). Verify the ORPHAN-TEMPLATE gate passes without an exemption.
- `prompt-surface-manifest` checker (ADR-037) — VOICE/`character_voice` must be
  declared; the manifest INTENT-COMPLETENESS gate now expects a VOICE template.
- No ratchet baseline change expected (this adds a routeable surface, not debt).

### 5. Test update plan
- New Prompt-Path-Compliance test (ADR-046 §D.1): assert VOICE resolves through
  PromptComposer Mode 1 to `_bundled/analysis/en/character_voice/system.md`
  (no inline fallback).
- Schema round-trip tests; consumer tests (descriptive rendered / metrics excluded);
  Foundation analyzer unit tests; agent TestModel tests; Backend integration + SSE;
  Frontend Vitest.

---

## Risks Surfaced for Coordinator/User Decision (before implementation planning)

These are NOT blockers for approving this ADR (they are downstream or
cross-feature), but the coordinator/user should be aware before planning
implementation:

1. **Checking-path model gap (WRITE-010 / ANAL-009 scope).** The current
   `CharacterVoiceProfile` (`core/profiles/models.py`) carries only a flat
   `speech_summary`; it has no structured `voice_metrics`. ANAL-008 WRITES metrics
   to `speech.voice_analysis.voice_metrics` (this ADR's contract), so the data
   exists. But when WRITE-010/ANAL-009 are implemented, they must decide how the
   checker reads structured metrics (extend `CharacterVoiceProfile`, or read KB
   directly). That is a separate downstream decision — out of scope here, tracked in
   the Review Trigger. No action needed before ANAL-008 implementation.

2. ~~**ANAL-009 spec carries the same stale "map to SpeechPatterns" assumption.**~~
   **✅ RESOLVED (2026-07-25, ADR-073).** ANAL-009 has been reconceptualised as
   **Phase 1 — Character Voice Drift** (ADR-073). Its rewritten spec consumes
   deterministic `voice_metrics` via the `VoiceProfileConsumer` contract (not LLM
   metrics, not the lossy "map to SpeechPatterns" mapping). The stale assumption is
   removed. See the ANAL-009 spec §"Data contract" and ADR-073 § CR-04.

3. **VOICE intent categorization/profile consistency.** `LLMIntent.VOICE` is
   "categorized ANALYSIS, profile balanced" per the composer. When VOICE becomes
   routeable, the Core specialist must confirm the category/mode/profile entries in
   `composer.py` and `route_table.py` agree (the route_table currently has NO VOICE
   entry at all — only the NON_ROUTEABLE stub). Low risk; mechanical verification
   at implementation.

4. **`DialogueParser` module home (`analysis/` vs `nlp/`).** ADR-021 pre-named
   `nlp/dialogue.py` ("Dialogue extraction from prose") and `analysis/voice_metrics.py`
   ("Structural voice analysis"). This ADR places `DialogueParser` in
   `core/analysis/dialogue_parser.py` (it orchestrates extraction + attribution +
   per-utterance metric computation — analysis computation, not raw NLP) and
   `VoiceMetricsAnalyzer` in `core/analysis/voice_metrics.py` (per ADR-021). If raw
   dialogue-extraction primitives are needed, they go in `core/nlp/dialogue.py` per
   ADR-021 and `DialogueParser` consumes them (RULE-07 `analysis → nlp`). The Core
   specialist resolves the exact split at implementation; both homes are ADR-021-consistent.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02b | ✅ | VOICE prompt = PromptComposer Mode 1 (intent + `character_voice` context_mode + governed EN template); no inline f-string, no production fallback. |
| RULE-03 | ✅ | Contracts (`VoiceAnalysis`, `VoiceMetrics`, `CharacterVoiceAgent` Protocol, `CharacterVoiceService` Protocol) defined before implementation. |
| RULE-04 | ✅ | Schema split into `VoiceAnalysis`/`VoiceMetrics`; Foundation split into `dialogue_parser.py`/`voice_metrics.py`; Backend split into `contracts_character_voice.py`/`schemas_character_voice.py`/`router_character_voice.py`. |
| RULE-05/06 | ✅ | Core owns schema + consumers + analyzers; Backend owns service/router; one responsibility per file. |
| RULE-07 | ✅ | Consumers in `core/profiles/`; no `writing/`→`profiles/` cycle; `analysis → nlp` only. |
| RULE-08 | ✅ | `DialogueParser`/`VoiceMetricsAnalyzer` may consume `NLPProvider` (ADR-021); no raw spaCy outside `core/nlp/`. |
| RULE-11 | ✅ | `updated_at` bump keeps freshness signal; missing `voice_analysis` degrades gracefully. |
| RULE-13 | ✅ | SSE + non-streaming share the service interface (mirrors ANAL-005). |
| RULE-22 | ✅ | Cross-feature coherence: producer + generation consumer + checking consumer defined together (CR-04). |

---

## Review Trigger

- [ ] When WRITE-010 (Voice Consistency Checker) is implemented — verify it reads
      `speech.voice_analysis.voice_metrics` and uses `VoiceProfileConsumer.assemble_for_checking`.
- [x] When ANAL-009 (Voice Drift) is implemented — verify it consumes the deterministic
      `voice_metrics` (not LLM metrics) for comparison, and update ANAL-009's stale
      "map to SpeechPatterns" assumption to this contract.
      **✅ DONE (2026-07-25, ADR-073):** ANAL-009 Phase 1 spec rewritten to consume
      `voice_metrics` via `VoiceProfileConsumer.assemble_for_checking()`; stale
      assumption removed (Risk #2 closed). Implementation pending user approval of
      ADR-073.
- [ ] When ANAL-007 (Author Voice) is implemented — add the `author_voice` context_mode
      to the VOICE route; resolve author-voice storage (separate ADR — out of scope here).
- [ ] If `VoiceMetrics` fields prove insufficient for drift comparison — extend the
      metric block (additive, migration-free).
- [ ] If dialogue attribution quality is insufficient — evaluate coupling ANAL-005
      Coreference as an optional pre-step (Decision 3 rejected this for v1).

---

## Cross-References

- ADR-021 — deterministic analysis (pre-names `core/analysis/voice_metrics.py`).
- ADR-040 — `core/profiles/` SSOT module + voice extraction relocation.
- ADR-050 — `VoiceProfileConsumer` contract (checking projection this ADR satisfies).
- ADR-054 — Mode-1 PromptComposer mandate (ANAL-008 must not reintroduce inline debt).
- ANAL-008 spec — feature-level implementation contract.
