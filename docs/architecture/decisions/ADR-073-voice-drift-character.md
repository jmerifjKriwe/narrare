# ADR-073 — Character Voice Drift Contract & `voice_drift` Prompt Surface (ANAL-009 Phase 1)

> **Status:** 🔄 Proposed (spec/ADR authored; awaiting user approval before implementation)
> **Date:** 2026-07-25
> **Deciders:** Architecture Specialist; User (approved the five decisions in brainstorming)
> **Supersedes:** —
> **Related:** ADR-021 (deterministic analysis), ADR-035 (agent output validation),
> ADR-050 (cross-feature context contracts — `VoiceProfileConsumer`, no SSOT bypass),
> ADR-054 (Mode-1 PromptComposer mandate), ADR-055 (character-voice storage contract +
> VOICE routeable; **Risk #2 closed by this ADR**), ADR-056 (runtime-aware adoption gate),
> ADR-057 (voice-check checking-path contract + reusable delta primitive; **Risk #3
> satisfied by this ADR**), ADR-065 (RULE-13 two-method run/stream), ADR-043
> (`useAIOperation`), CONSTRAINTS.md RULE-02/02a/02b/03/04/05/06/07/11/13/17/22, CR-04

> **Scope of this ADR:** contracts + five decisions only. This document records the
> longitudinal character-voice-drift contract the ANAL-009 Phase 1 implementation must
> satisfy; the code, tests, governed template, manifest/registry entries, and runtime
> evidence live in the modules named in the Retrofit-Plan and Cross-References, not in
> this ADR. **Phase 2 (Author Voice: storage SSOT + profiling + drift) is explicitly
> deferred** to a separate future ADR + cycle (see Decision 1 + Phase 2 Deferral).

---

## Context

ANAL-009 (Voice Drift Detection) is the longitudinal member of the Voice lane. The
lane's intended order was `ANAL-007 author → ANAL-008 character → ANAL-009 drift →
WRITE-010 checker`. It was **built backwards**: ANAL-008 (character profiling) and
WRITE-010 (voice check) shipped first and are ✅ stable; ANAL-007 (author voice) is
deferred pending an unresolved author-voice *storage* decision (where do author-voice
metrics live? — see Phase 2 Deferral); ANAL-009's original spec described *author*
drift and declared `requires: [ANAL-007]`, so as-specced it was blocked on a deferred
feature. This is a **recorded adaptation** to the deferred author-voice-storage
decision, not a planning failure — it is documented here so the lane's non-linear
build order is discoverable rather than implicit.

This ADR unblocks the lane by reconceptualising ANAL-009 **Phase 1** as **Character
Voice Drift**: longitudinal drift of a single character's voice across chapters,
computed against that character's stored ANAL-008 profile. It builds entirely on
infrastructure that already exists (ANAL-008 write path + WRITE-010's deterministic
delta primitive). Author-voice drift becomes **Phase 2** — a separate cycle with its
own future ADR.

### Voice-lane build order (recorded)

| Lane position | Intended | Built | State |
|---------------|----------|-------|-------|
| Profiling — author | ANAL-007 | — | ⏸ Deferred (Phase 2 of ANAL-009 lane; own ADR) |
| Profiling — character | ANAL-008 | ANAL-008 | ✅ Stable |
| Drift | ANAL-009 | ANAL-009 Phase 1 (character) | 🔄 This ADR |
| Checker | WRITE-010 | WRITE-010 | ✅ Stable |

Built order: `ANAL-008 → WRITE-010 → ANAL-009-Phase1 (character)` with
`ANAL-007 + ANAL-009-Phase2 (author)` deferred. The deferral is driven by the
author-voice-storage open question (Phase 2 Deferral), not by feature priority.

### Verified state (grounded, not assumed — per architectural-discipline §7)

| Concern | State | Location |
|---------|-------|----------|
| `VoiceAnalysis` / `VoiceMetrics` / extended `SpeechPatterns` | EXISTS (Layer 0, ADR-055) | `core/kb/schemas/character.py` |
| `DialogueParser` (reusable) | EXISTS (Layer 2, ADR-055) | `core/analysis/dialogue_parser.py` |
| `VoiceMetricsAnalyzer` (reusable) | EXISTS (Layer 2, ADR-021/055) | `core/analysis/voice_metrics.py` |
| `CharacterVoiceAgent` (profiling agent, ANAL-008 writer) | EXISTS (Layer 2) | `core/agents/character_voice_agent.py` |
| `voice_metric_distances(stored, current)` delta primitive | EXISTS — module-level, documented "so ANAL-009 (voice drift) can reuse them (ADR-057 Review Trigger #2)" | `core/analysis/voice_check_scoring.py` |
| `metric_delta_subscore(stored, current)` aggregate [0,100] | EXISTS (same module) | `core/analysis/voice_check_scoring.py` |
| `band_for_score(score)` → green/yellow/fair/red (>=90/70-89/50-69/<50) | EXISTS (same module) | `core/analysis/voice_check_scoring.py` |
| `CharacterVoiceProfile.voice_metrics` (checking-path projection) | EXISTS (Layer 0, ADR-057 closed ADR-055 Risk #1) | `core/profiles/models.py` |
| `VoiceProfileConsumer.assemble_for_checking()` → `list[CharacterVoiceProfile]` (carries `voice_metrics`) | EXISTS (ADR-050/057) | `core/profiles/contracts.py` |
| `LLMIntent.VOICE` routeable | YES (ADR-055 D4); `allowed_context_modes = {"character_voice", "voice_check"}`; default mode `character_voice` | `core/prompts/route_table.py` |
| `voice_check` governed EN template | EXISTS (ADR-057 D3) | `core/prompts/_bundled/analysis/en/voice_check/system.md` |
| `voice_drift` context_mode / template / manifest / registry | **DOES NOT EXIST** — this ADR introduces it (third VOICE mode) | — |
| Analysis router scope convention | novel-scoped: `POST /analysis/character-voice/{novel_id}`; chapter-scoped: `POST /analysis/voice-check/{chapter_id}` | `apps/api/narrare/analysis/router_*.py` |
| Approved visualization mockup | EXISTS (gitignored, NOT committed) — Layout γ (hybrid heatmap + drill-in) chosen | `_scratch/anal-009-drift-mockup/anal-009-drift-viz-mockup.html` |

### Root cause (why this ADR is needed)

Two layers of "why" (architectural-discipline §1):

1. *Why is a decision needed at all?* The stale ANAL-009 spec describes author-voice
   drift and depends on ANAL-007 (deferred). Building it as-specced would block on an
   unresolved author-voice-storage decision. Meanwhile the **complete** character-voice
   infrastructure exists: ANAL-008 writes `speech.voice_analysis` (descriptive +
   `voice_metrics`) to KB; WRITE-010 checks the current chapter against stored
   profiles; `voice_check_scoring.voice_metric_distances()` exposes a reusable
   deterministic delta primitive (ADR-057 Risk #3 anticipated ANAL-009 would reuse it).
   Character drift is therefore unblocked and is the natural longitudinal extension of
   the built half of the lane.

2. *Why is this an architecture decision rather than an implementation choice?* Because
   (a) it adds a new prompt-surface route (`voice_drift` context_mode + governed
   template) — a prompt-mechanics change requiring a Retrofit-Plan (adr-process §D.4);
   (b) it introduces a NEW longitudinal consumer of the `VoiceProfileConsumer` contract
   (CR-04 / RULE-22 cross-feature coherence: producer + generation-consumer +
   checking-consumer + NEW longitudinal-consumer must be defined together, not feature-
   locally); and (c) the comparison model (which signals to compute) and the LLM role
   (a trend-classifier, not a per-chapter snapshot judge) are contract decisions that
   determine the agent's output type and the SSE event shape — not implementation
   details that can be left to the implementation specialist.

The third root cause: ADR-055 Risk #2 and the ADR-055/057 Review Triggers carry open
ANAL-009 items. This ADR closes them (ANAL-009 consumes `voice_metrics` via the
consumer contract and reuses the delta primitive — no stale "map to SpeechPatterns"
assumption, no duplication).

---

## Decision Drivers

- **RULE-02/02a/02b** — The drift prompt MUST be PromptComposer Mode 1 (intent +
  `voice_drift` context_mode + governed EN template). No inline f-strings, no
  production fallback, no system-prompt-in-user-channel, no app-layer loader.
- **RULE-03** — The drift contracts (service Protocol, agent Protocol, the
  trend/jump scoring API) MUST exist before implementation.
- **RULE-04/06** — Modularise; one responsibility per file (trend scoring ≠ jump
  detection ≠ agent ≠ service ≠ router ≠ prompt-builder).
- **RULE-07** — Consumers live in `core/profiles/`; the drift service reads metrics via
  the `VoiceProfileConsumer` contract, never via direct KB access. No `apps/`→`core`
  cycles; `analysis → profiles → kb.schemas` (read direction only).
- **RULE-11** — Graceful: a character without a stored profile → "no profile" result; a
  character silent in a chapter → that chapter is skipped (no artificial zeros); a
  project with no profiled characters → empty result, not an error.
- **RULE-13** — SSE + non-streaming share the service interface (mirrors ANAL-005/008
  and the ADR-057 WRITE-010 checker; ADR-065 two-method run/stream).
- **RULE-17** — Backend SSE event field names must match frontend TypeScript types.
- **RULE-22 / CR-04** — Adding a longitudinal consumer is a cross-feature contract
  read; the change must be coherent end-to-end (the producer + existing consumers are
  unchanged; the NEW consumer reads via the same contract).
- **ADR-021** — Per-chapter voice metrics MUST be deterministic; the LLM only
  interprets the longitudinal trend qualitatively (same hybrid tier as ANAL-003/008).
- **ADR-035** — The drift agent's structured output is validated.
- **ADR-050** — The drift service MUST consume voice data via
  `VoiceProfileConsumer.assemble_for_checking()`, not via direct KB access (the exact
  anti-pattern ADR-050 closed).
- **ADR-055/057** — Reuse the routeable VOICE intent, the `voice_metrics` storage, and
  the deterministic delta primitive; preserve "metrics never reach generation".
- **architectural-discipline §1/§4/§7** — Root-cause solution; no KB-bypass
  workaround; "documented ≠ implemented" — this ADR defines the contract; runtime
  evidence lands at implementation per ADR-056.

---

## Decision 1 — Scope & sequencing: ANAL-009 covers BOTH author + character drift (Option C), delivered PHASED (γ)

### Options Considered

#### Option α — Lane-faithful sequential: build ANAL-007 (author) → ANAL-009 author-drift → then character-drift

Follow the lane's intended order strictly. Build author-voice profiling + author-voice
drift first (requires resolving author-voice storage), then character drift.

**Pros:** Lane-faithful; one storage model decided up front.

**Cons:** **Blocked** on the unresolved author-voice-storage decision (Phase 2
Deferral). Longest path to first user value — the whole drift capability waits on an
architecture question that deserves its own cycle. Rejected.

#### Option β — Fused single feature: one ANAL-009 that mixes author + character drift in one pass

Build a single drift feature that compares both author voice and each character's voice
in the same run, resolving author storage inline.

**Pros:** One feature, one run.

**Cons:** Mixes two distinct storage models (author metrics have an unresolved storage
home; character metrics live in `speech.voice_analysis`) in one service/agent — violates
RULE-06 (one responsibility per file) and makes validation harder (two projection
paths through one consumer). Forces the author-storage decision into this ADR rather
than giving it its own cycle. Rejected.

#### Option γ — Phased: Phase 1 = Character Drift (this ADR, unblocked); Phase 2 = Author Voice (separate future ADR + cycle) (CHOSEN)

Split ANAL-009 into two phases. **Phase 1** (this spec + this ADR) delivers Character
Voice Drift on existing infrastructure (ANAL-008 + WRITE-010 scoring). **Phase 2**
(separate future ADR + cycle) delivers Author Voice: the storage SSOT decision +
author-voice profiling + author-voice drift. Phase 2 is explicitly deferred with its
blocking open question recorded (Phase 2 Deferral).

**Pros:**
- **Unblocked incremental value** — character drift ships now on existing infra.
- **De-risking** — validates the longitudinal pattern (per-chapter trend + jump
  detection + trend-classifying agent) before tackling author storage, so the Phase 2
  ADR inherits a proven longitudinal architecture.
- **Each spec stays focused** (RULE-06) — Phase 1 is purely character-scoped; Phase 2
  is purely author-scoped.
- **Each phase is a complete, working, tested subsystem** (RULE-20 incremental path is
  acceptable; each increment is complete, not a skeleton).

**Cons:**
- Two cycles instead of one — accepted (the AI implements; there is no human-effort
  argument, and the author-storage decision genuinely needs its own design pass).

### Decision

**Option γ.** ANAL-009 Phase 1 = Character Voice Drift (this ADR). Phase 2 = Author
Voice (deferred, own ADR). **Phase 1 drops the ANAL-007 dependency** — it requires
ANAL-008 (profile writer, ✅) and reuses WRITE-010's `voice_check_scoring` delta
primitive (✅).

### Sustainability check

1. *Correct in 3 months?* Yes — Phase 1 builds on stable ANAL-008/WRITE-010 infra and
   a reusable Core primitive; Phase 2 will add an author consumer of the same
   longitudinal pattern without disturbing Phase 1.
2. *Hard-to-undo coupling?* None — Phase 1 is a new read-only consumer; it adds no
   storage, no schema change, no migration. The author-storage decision is deferred,
   so no premature coupling is introduced.
3. *Simplest correct solution?* Yes — it ships the unblocked half now and defers the
   genuinely-open question rather than rushing it.
4. *Design intent clear?* Yes — the Phasing section + this ADR make the split
   discoverable; the recorded lane-build-order table explains the non-linear history.

---

## Decision 2 — Comparison model: (i) profile-trend + (iii) adjacent-chapter jump detection

### Options Considered

The drift feature must answer two complementary diagnostic questions: *"is this
character's voice drifting?"* and *"where did it start?"* Three candidate signals were
considered; two are adopted.

#### Signal (i) — Per-chapter match against the stored profile (profile-trend) (CHOSEN)

For each (character, chapter): extract the chapter's per-character metrics (reuse
`DialogueParser` + `VoiceMetricsAnalyzer`) and compute the delta vs the stored
ANAL-008 profile's `voice_metrics` via the existing
`voice_check_scoring.voice_metric_distances()` primitive → per-metric [0,1] distances
→ aggregate per-chapter match sub-score (`metric_delta_subscore`, [0,100],
100=identical) → banded (`band_for_score`). The per-chapter match scores form the
**trend** (the always-visible sparkline / heatmap row).

#### Signal (ii) — Chapter-vs-baseline-chapter (a user-chosen "target" chapter)

Let the user pick a baseline chapter and compare every chapter to *it* (rather than to
the stored profile). This is the model the stale spec described ("choose baseline
chapter").

**Pros:** Familiar from diff tools; user controls the reference.

**Cons:** This is **calibration of the reference, not a new signal** — it is signal (i)
with the reference swapped from "stored profile" to "chapter N's metrics". It can be
added later as a **UI toggle** (reference = profile | specific chapter) without any new
scoring primitive or architecture change. Building it now would add UI + state for a
non-essential variant. **Deferred** as a follow-up toggle (no architecture impact).

#### Signal (iii) — Delta between consecutive chapters (jump detection) (CHOSEN)

Compute the delta between *adjacent* chapters' metrics (the same `voice_metric_distances`
primitive applied to chapter N vs chapter N+1) → flag **jump points** where a specific
metric shifted sharply between two consecutive chapters, labelled with *which* metric
jumped (e.g. "Ch3→Ch4 · formality"). This localises *where* drift started.

#### Alternative combos considered

- **(i) alone** — answers "is there drift?" but cannot localise *where* it began (no
  jump markers). The user sees a declining trend with no chapter-level anchors.
- **(iii) alone** — good at jumps but misses slow, continuous evolution (a character
  whose formality drifts gradually with no single jump would read as "no jumps").
- **(i)+(ii)** — redundant signal (ii ⊂ i as a reference swap); not a real addition.
- **(ii)+(iii)** — loses the profile-trend (the actually-valuable "is this character
  drifting from their established voice?" signal).

### Decision

**Signals (i) + (iii).** Profile-trend (i) answers "is there drift?"; adjacent-jump
detection (iii) answers "where did it start?". Both reuse the same deterministic
`voice_metric_distances` primitive — no second scoring engine.

Signal (ii) is **deferred** as a future UI "reference toggle" (profile | baseline
chapter) that requires no new primitive — recorded in the Review Trigger.

### Rationale

(i) and (iii) answer *complementary* diagnostic questions from the same deterministic
foundation. (ii) is a reference-swap on (i), not a new signal, so deferring it costs
nothing architecturally. (iii) is a *second primitive* (adjacent-chapter delta) that
would be expensive to retrofit later, so it is included now.

### Sustainability check

1. *Correct in 3 months?* Yes — both signals are deterministic and reuse a stable
   primitive; the trend + jump data model is independent of the visualization.
2. *Hard-to-undo coupling?* None — the scoring module is pure Core logic with no I/O.
3. *Simplest correct solution?* Yes — one primitive (`voice_metric_distances`) serves
   both the profile-trend and the adjacent-jump computation.
4. *Design intent clear?* Yes — `chapter_metric_trend` / `trend_against_profile` /
   `adjacent_jumps` are self-documenting function names; the (ii) deferral is recorded.

---

## Decision 3 — LLM role: (c) new `CharacterVoiceDriftAgent` + new `voice_drift` context_mode + governed EN template

### Options Considered

#### Option (a) — No LLM / metrics-only

Compute the trend + jumps deterministically and render them; no agent.

**Pros:** Cheapest, fully deterministic.

**Cons:** Breaks the ADR-021 hybrid pattern (measurement deterministic, understanding
qualitative). A bare trend + jump list forces the user to *guess* whether a decline is
intentional evolution (a character arc), context-dependent variation (action scenes
read faster), or genuine inconsistency — and **that classification is the actually-
valuable output** of a drift feature (the mockup's agent-reasoning quote is the whole
point of drilling in). Rejected.

#### Option (b) — Reuse `CharacterVoiceCheckerAgent` N× per chapter

Run the existing WRITE-010 checker once per chapter (it judges a snapshot against the
profile), then aggregate.

**Pros:** Reuses an existing agent.

**Cons:** **N× LLM cost** (one call per chapter per character). The checker judges
*snapshots*, not *trends* — it would flag each chapter independently with no
longitudinal view, then you'd still need a separate aggregation/classification step.
Fundamentally the wrong abstraction: the checker answers "is *this chapter*
consistent?" while drift needs "how has this character *evolved across* the book?".
Rejected (also violates RULE-06 — would fuse two concerns into one agent).

#### Option (c) — New `CharacterVoiceDriftAgent` that classifies the precomputed trend (CHOSEN)

One LLM call **per character** (not per chapter). The agent consumes:
- the precomputed per-chapter match sub-scores (signal i) + the deterministic band,
- the jump points with their metric labels (signal iii),
- the stored *descriptive* profile (formality, vocabulary level, etc.),
- chapter metadata (titles, positions),

…and classifies the **longitudinal** drift in a single structured output:

```python
class CharacterVoiceDriftResult(BaseModel):  # packages/core/narrare_core/agents/character_voice_drift_types.py
    drift_type: Literal["evolution", "context", "inconsistency"]
    confidence: float                              # 0.0–1.0
    longitudinal_reasons: list[str]                # why this classification
    per_chapter_notes: dict[str, str]              # chapter_id → note (sparse)
    suggested_attention: list[str]                 # chapter_ids to review
```

Measurement stays **deterministic** (ADR-021): the per-chapter metrics, the trend, the
jumps, and the band are all computed in pure Core (`voice_drift_scoring.py`). The agent
only **interprets** the trend qualitatively. This is exactly the hybrid tier (mirrors
ANAL-003/008).

**New prompt surface:** add `"voice_drift"` as the **third** mode on
`LLMIntent.VOICE` (after `character_voice`, `voice_check`). ADR-055 Decision 4
explicitly anticipated this ("`voice_drift` (ANAL-009, deferred)"). Create governed EN
template `core/prompts/_bundled/analysis/en/voice_drift/system.md` (Mode 1, 9-section
skeleton). Register in `prompt-surface-manifest.yaml` + `adoption-registry.yaml`;
runtime evidence per ADR-056 lands at implementation.

The `voice_drift` prompt is **deliberately different** from `voice_check` (snapshot
flag+score) and `character_voice` (profiling): three modes, three intents, one
`LLMIntent.VOICE` — exactly as PLAN serves outline/timeline/character_arc.

**Pros:**
- ADR-021 compliant (deterministic measurement + qualitative interpretation).
- **Efficient** — 1 LLM call per character (the agent sees the whole trend at once).
- The classification (`evolution` vs `context` vs `inconsistency`) is the valuable
  output the user actually needs.
- Reuses the routeable VOICE intent + its variable surface (additive context_mode).

**Cons:**
- One new agent + governed template + manifest/registry entries (standard analysis-
  vertical surface, mirrors ANAL-008/WRITE-010).
- N characters = N LLM calls per run (e.g. 5 characters = 5 calls) — accepted; the
  agent sees the whole trend in one call, so per-chapter fan-out is avoided.

### Decision

**Option (c).** A dedicated `CharacterVoiceDriftAgent` (1 call/character) classifies
the precomputed longitudinal trend. Measurement is deterministic; the agent only
interprets. New `voice_drift` context_mode + governed EN template (third VOICE mode).

### Rationale

The hybrid tier is the established analysis pattern (ANAL-003/008/057). Metrics alone
(option a) discard the qualitative half that makes drift *actionable*; the checker
(option b) is the wrong unit of work (snapshot, not trend) at N× the cost. A single
trend-classifying call per character (option c) is both ADR-021-compliant and the
cheapest correct shape.

### Sustainability check

1. *Correct in 3 months?* Yes — the agent's input is the deterministic trend (stable);
   if the classification logic evolves, only the prompt + output type change, not the
   scoring.
2. *Hard-to-undo coupling?* None — additive prompt surface (third mode); no existing
   mode is changed; default mode stays `character_voice`.
3. *Simplest correct solution?* Yes — one call/character reuses the whole trend; no
   per-chapter fan-out, no aggregation step.
4. *Design intent clear?* Yes — `voice_drift` ≠ `voice_check` ≠ `character_voice` is
   documented at the route + in this ADR; the agent's output type names its role
   (`drift_type`, `longitudinal_reasons`).

---

## Decision 4 — Visualization: Layout γ (hybrid — heatmap overview + expandable detail)

### Options Considered

An approved mockup (`_scratch/anal-009-drift-mockup/anal-009-drift-viz-mockup.html`,
gitignored — **not** committed to the repo) demonstrates all three layouts with
identical mock data. γ was chosen in brainstorming.

#### Layout α — Heatmap grid only (characters × chapters)

A scrollable grid: rows = characters, columns = chapters, cells coloured by drift band
(green/yellow/fair/red = stable/minor/moderate/major) with the per-chapter match %, a
⚡ jump marker between columns where a metric jumped (hover → which metric), a
classification badge, and an overall match % per row.

**Pros:** Whole cast at a glance; compact; scales to many characters.

**Cons:** No per-chapter "why" — the user sees the pattern but cannot read the agent's
reasoning without a second view.

#### Layout β — Per-character detail cards only

One rich card per character: sparkline of the per-chapter trend, jump list with labels,
the agent's reasoning quote, a "view per-chapter notes" expander.

**Pros:** Deep context per character; the agent reasoning is always visible.

**Cons:** No cross-character glance — scrolling through N cards to compare the cast;
the overview is implicit.

#### Layout γ — Hybrid: always-visible heatmap overview + expandable per-row detail (CHOSEN)

The heatmap (α) is the always-visible overview. Clicking/expanding a row reveals a
β-style detail card inline (sparkline trend + jump list + agent reasoning quote +
per-chapter notes). Other rows collapse/dim while one is expanded.

**Pros:** Scalable overview (α) + drill-in depth (β) — the standard analysis-panel
pattern (matches how the existing analysis panels compose overview + detail).

**Cons:** More moving parts (expand state + a second sub-view to build and keep in
sync) — accepted; this is ordinary React state, not architectural complexity.

### Decision

**Layout γ.** Heatmap overview + expandable detail per row.

### Terminology (from the approved mockup — use consistently in spec + UI)

The score is a **match score** (100 = matches the stored profile perfectly). The
mockup labels it **"match to profile"** to avoid the inverted-meaning confusion of
"drift %" (where higher would mean worse). The spec and UI MUST use **"match to
profile"** / **"match score"** consistently. The agent's `drift_type` classification
(`evolution`/`context`/`inconsistency`) carries the qualitative "is this drift a
problem" judgement — the score is neutral.

**Band ↔ colour ↔ label mapping** (deterministic, reuses `band_for_score`):

| Match score | Band (`band_for_score`) | Heatmap label | Symbol |
|-------------|------------------------|---------------|--------|
| ≥ 90 | green | stable | ● |
| 70–89 | yellow | minor | ▲ |
| 50–69 | fair | moderate | ◆ |
| < 50 | red | major | ◇ |

**Row classification badge** (the mockup's composite label): the badge is a
**display label derived from the band + the agent's `drift_type` + confidence**,
demonstrated concretely in the approved mockup (e.g. a flat green-band trend with
no jumps → "Stable"; a yellow-band trend → "Mild variation"; a deeper decline
surfacing the agent's qualitative call → "Evolution" / "Context" / "Inconsistent").
The **exact badge-composition rule is a frontend concern guided by the approved
mockup** — it is NOT fixed by this ADR. What IS fixed by this ADR is the data
contract the badge is derived from: **(overall match score, deterministic band,
`drift_type ∈ {evolution, context, inconsistency}`, `confidence`)**. The frontend
composes the label; the backend emits the contract.

### Sustainability check

1. *Correct in 3 months?* Yes — γ composes two standard views; either can evolve
   independently. The data contract is visualization-agnostic.
2. *Hard-to-undo coupling?* None — the visualization reads the SSE result; it adds no
   backend contract.
3. *Simplest correct solution?* Yes — γ is the minimal layout that delivers both
   "at-a-glance" and "drill-in why" without a separate page.
4. *Design intent clear?* Yes — the approved mockup is the authoritative visual
   reference; the band/label table is in this ADR.

---

## Decision 5 — Persistence & scope: read-only, no caching, novel-scoped SSE, 1 agent call per character

### Options Considered

#### Persistence

- **(A) Read-only — ANAL-009 writes nothing to KB (CHOSEN).** Like WRITE-010, drift is
  *analysis*, not profiling. ANAL-008 remains the only writer of `voice_analysis`.
- (B) Cache the per-run drift result on the novel/character. Rejected — see Caching.

#### Caching

- **(A) No metric caching in v1 (CHOSEN).** The per-chapter metric extraction +
  delta + band are deterministic and fast; caching is YAGNI until a measured
  performance problem (architectural-discipline §1: do not optimize without
  measurement). Caching would also introduce a staleness surface (the cache must
  invalidate when a chapter is edited or a profile is re-profiled) for no current gain.
- (B) Cache per-chapter metrics keyed by chapter content hash. Deferred — revisit only
  if a measured run is too slow.

#### Endpoint scope

- **(A) Novel-scoped `POST /analysis/voice-drift/{novel_id}` (CHOSEN).** Drift is
  inherently longitudinal (across all chapters); it mirrors `character-voice`
  novel-scoping, NOT `voice_check` chapter-scoping (the checker judges one chapter).
- (B) Chapter-scoped. Rejected — a single chapter has no "drift"; the feature is
  meaningless below the novel scope.

#### LLM call cardinality

- **(A) 1 agent call per character (CHOSEN).** The agent sees the whole trend in one
  call (Decision 3). N characters = N calls per run (e.g. 5 characters = 5 LLM calls).
  Accepted — the alternative (one call for all characters) would force the agent to
  emit a variable-length list and dilute per-character reasoning.
- (B) 1 call for the whole novel. Rejected — couples all characters into one prompt
  and produces weaker per-character reasoning.

#### Graceful degradation (RULE-11)

- A character **without** a stored ANAL-008 profile → graceful **"no profile"** result
  for that character (not an error; the character is listed as un-analysable).
- A character who **does not speak** in a given chapter → that chapter is **skipped**
  for that character (no artificial zeros in the trend; the trend is defined over the
  chapters where the character speaks).
- A project with **no profiled characters** → empty result, not an error.

### Decision

Read-only; no caching in v1; novel-scoped SSE endpoint under `AI_ANALYSIS_LIMITER`; 1
agent call per character; graceful degradation per RULE-11.

### Sustainability check

1. *Correct in 3 months?* Yes — read-only means no staleness/invalidation surface to
   maintain; caching can be added later behind the same service interface if measured.
2. *Hard-to-undo coupling?* None — adds no storage, no schema, no migration.
3. *Simplest correct solution?* Yes — the minimal correct surface (read + classify);
   caching and chapter-scoping are explicitly not the simplest *correct* solution.
4. *Design intent clear?* Yes — "read-only analysis, like WRITE-010" is a one-sentence
   summary; the cardinality + graceful-degradation rules are in this ADR.

---

## Consequences

**Positive:**
- ADR-055 Risk #2 is **closed** — the stale "map to SpeechPatterns" assumption is
  removed; ANAL-009 consumes `voice_metrics` via the `VoiceProfileConsumer` contract.
- ADR-057 Risk #3 is **satisfied** — ANAL-009 reuses the `voice_metric_distances`
  delta primitive (no duplication), exactly as ADR-057's Review Trigger anticipated.
- `LLMIntent.VOICE` gains its **third** governed mode (`voice_drift`), reusing the
  route ADR-055 made routeable. (Phase 2 will add the fourth, `author_voice`.)
- The longitudinal pattern (trend + jumps + trend-classifying agent) is validated on
  the unblocked character half, de-risking the Phase 2 author-voice ADR.
- Generation is provably unaffected — ANAL-009 is read-only and never touches
  `formatted_voice_profiles` or `voice_metrics` on the generation projection.

**Negative / Tradeoffs:**
- One new governed prompt artifact set (`voice_drift` template + manifest/registry
  entries) — additive prompt surface, runtime evidence tracked per ADR-056.
- N characters = N LLM calls per run — accepted (Decision 5); the agent sees the whole
  trend in one call, so no per-chapter fan-out.
- A new analysis-vertical surface (scoring + agent + service + SSE router + panel +
  hook + i18n) — standard, mirrors ANAL-008/WRITE-010.
- The author-voice half of the lane remains deferred (Phase 2) — recorded, not hidden.

**Constraints introduced:**
- ANAL-009 MUST obtain profiles via `VoiceProfileConsumer.assemble_for_checking()` —
  never via direct `KBEntity.metadata` access (ADR-050).
- ANAL-009 MUST write nothing to KB (read-only — Decision 5).
- `formatted_voice_profiles` MUST NOT read anything ANAL-009 produces (generation is
  unaffected — trivially true since ANAL-009 writes nothing).
- A character with no stored `voice_analysis` MUST yield a graceful "no profile" result
  (RULE-11).
- A character silent in a chapter MUST be skipped for that chapter (no artificial zeros).

---

## CR-04 Cross-Feature Impact (coherence)

ANAL-009 adds a NEW **longitudinal consumer** of the voice-profile data. This ADR
requires coherence end-to-end, not feature-local:

- **Producer (ANAL-008 write path):** unchanged. ANAL-008 already writes
  `speech.voice_analysis.voice_metrics` (ADR-055). ANAL-009 adds no write.
- **Consumer (generation read path):** unchanged. `assemble_for_generation` →
  `formatted_voice_profiles` renders `speech_summary` and never reads `voice_metrics`.
  ANAL-009 is read-only and touches neither.
- **Consumer (checking read path):** unchanged. WRITE-010 reads `voice_metrics` via the
  consumer (ADR-057). ANAL-009 is a *separate* consumer of the same contract, not a
  modification of WRITE-010.
- **Consumer (longitudinal read path) — NEW.** ANAL-009 reads `voice_metrics` via the
  same `VoiceProfileConsumer.assemble_for_checking()` contract WRITE-010 uses. **No
  SSOT bypass** — the consumer is the single read path for structured metrics; ANAL-009
  does not reach into `KBEntity.metadata` directly (the exact anti-pattern ADR-050
  closed). The consumer's signature is unchanged; ANAL-009 is just another caller.

This is the CR-04 lesson applied (architectural-discipline §7): the producer +
generation-consumer + checking-consumer + the NEW longitudinal-consumer are defined
together. Because ANAL-009 is a pure read-only consumer of an existing contract, the
cross-feature surface is "one more caller of `assemble_for_checking`" — no contract
change, no migration, no coherence gap.

---

## Retrofit-Plan (mandatory — new prompt-surface route, per adr-process.md §D.4)

This ADR adds a new `voice_drift` context_mode + governed template on the routeable
`LLMIntent.VOICE`. That is a prompt-mechanics change. Retrofit-Plan:

### 1. Inventory of affected paths

**Prompt surface:**
- `packages/core/narrare_core/prompts/route_table.py` — add `"voice_drift"` to
  `ROUTE_CONFIGS[LLMIntent.VOICE].allowed_context_modes` (becomes
  `{"character_voice", "voice_check", "voice_drift"}`). Default mode stays
  `character_voice`. `optional_variables` unchanged (the KB world-context + preference
  variables already declared for `character_voice`/`voice_check` cover `voice_drift`;
  the per-chapter trend + jumps + stored descriptive profile are runtime user-channel
  data, not template variables — mirrors the checker).
- `packages/core/narrare_core/prompts/route_table.py` comments — update the VOICE
  block comment to note `voice_drift` is now the third governed mode (Phase 1 of
  ANAL-009) and `author_voice` remains deferred.
- `core/prompts/composer.py` — verify VOICE/`voice_drift` resolves via the route_table
  (route_table is SSOT; composer mirrors it). No new entry needed if the composer
  derives from `ROUTE_CONFIGS`; verify, do not duplicate.
- `packages/core/narrare_core/prompts/_bundled/analysis/en/voice_drift/system.md` —
  NEW governed EN template (9-section skeleton, Mode 1, ADR-054).

**Drift Core (scoring + agent):**
- `packages/core/narrare_core/analysis/voice_drift_scoring.py` — NEW: pure deterministic
  trend + jump computation. `chapter_metric_trend()`,
  `trend_against_profile()` (reuses `voice_check_scoring.voice_metric_distances` +
  `metric_delta_subscore`), `adjacent_jumps()` (reuses `voice_metric_distances` on
  consecutive chapters), `classify_severity()` (deterministic banding via
  `band_for_score`). No I/O, no LLM, fully unit-testable.
- `packages/core/narrare_core/agents/character_voice_drift_agent.py` +
  `character_voice_drift_types.py` — NEW: `CharacterVoiceDriftAgent` (`NarrareAgent`,
  structured output, 1 call/character) consuming the precomputed trend + jumps +
  stored descriptive profile; emits `CharacterVoiceDriftResult` (`drift_type`,
  `confidence`, `longitudinal_reasons`, `per_chapter_notes`, `suggested_attention`).

**Reused unchanged:** `DialogueParser`, `VoiceMetricsAnalyzer`,
`VoiceProfileConsumer.assemble_for_checking()` (ADR-050),
`voice_check_scoring.voice_metric_distances` / `metric_delta_subscore` /
`band_for_score`.

**Governance / manifest:**
- `scripts/architecture/prompt-surface-manifest.yaml` — add a `voice_drift` entry under
  the VOICE intent's `context_modes` (mirror the `voice_check` entry: same
  `optional_variables`, `required_variables: []`, `fallback_policy:
  fail_loudly_if_bundled_missing`).
- `scripts/architecture/adoption-registry.yaml` — add `analysis/voice_drift: true`
  (governed adoption debt until runtime evidence lands) +
  `features.analysis.modes.voice_drift: {requires_runtime_evidence: true}`.

**Backend:**
- `apps/api/narrare/analysis/contracts_voice_drift.py` —
  `CharacterVoiceDriftServiceProtocol` (RULE-03).
- `apps/api/narrare/analysis/schemas_voice_drift.py` — request/response/SSE event
  types (RULE-17: field names must match frontend TS types).
- `apps/api/narrare/analysis/voice_drift_service.py` — Mode-1 PromptComposer service
  (binds `VoiceProfileConsumer`; iterates profiled characters; per chapter:
  `DialogueParser` + `VoiceMetricsAnalyzer` → `trend_against_profile` (i) +
  `adjacent_jumps` (iii) + band → `CharacterVoiceDriftAgent.run`; SSE yield per
  character). RULE-04 split helpers as needed (mirror WRITE-010's `_prompt` /
  `_agent_runner` / `_results` / `_runtime_content` split if the service approaches
  its limit).
- `apps/api/narrare/analysis/dependencies_voice_drift.py` — DI (RULE-19 `SessionDep`).
- `apps/api/narrare/analysis/router_voice_drift.py` — SSE
  `POST /analysis/voice-drift/{novel_id}` (novel-scoped) under `AI_ANALYSIS_LIMITER`;
  register in `apps/api/narrare/_app/main.py`.

**Frontend:**
- `packages/web/.../VoiceDriftPanel` + sub-components (overview heatmap + expandable
  detail per Layout γ) + `useCharacterVoiceDrift` (`useAIOperation`, ADR-043 — no
  manual AbortController) + SSE client (`connectSSE`) + i18n (en/de/fr, RULE-16).
  Wired into the editor analysis panels beside `CharacterVoicePanel` /
  `VoiceCheckPanel`. Field names match backend schemas (RULE-17).

### 2. Migration steps per path (atomic, independently testable)

1. Add the `voice_drift` route entry + governed EN template + manifest/registry
   declarations (pure governance; the ORPHAN-TEMPLATE + manifest gates then recognise
   it). No production caller yet.
2. Build the scoring module (pure unit tests: per-chapter trend, profile-delta,
   adjacent jumps, deterministic banding; silent-chapter skip; "no profile" path).
3. Build the drift agent (TestModel structured-output tests; ADR-035 validation).
4. Build the Backend service (Mode-1 PromptComposer; Fake consumer; graceful "no
   profile" + silent-chapter paths) + SSE router + schemas/contracts/dependencies.
5. Build the Frontend panel + hook + SSE client + i18n.
6. Land ADR-056 runtime-evidence probes (agent + service) to move `voice_drift` off
   governed adoption debt.

### 3. Breaking-change assessment

- `voice_drift` is a NEW context_mode + template → **additive** prompt surface. No
  existing caller routes VOICE to `voice_drift` yet, so no break. Default mode stays
  `character_voice`.
- No schema change, no model extension, no migration (ANAL-009 is read-only and reuses
  the existing `voice_metrics` storage + consumer).
- `assemble_for_checking()` signature is unchanged — ANAL-009 is just another caller.
- Generation projection is untouched → `{{character_voice_profiles}}` content is
  byte-identical.

**Net: fully backward compatible (additive only).**

### 4. Checker (governance) update plan

- `_check_prompt_orphan.py` — the new `voice_drift` template is reachable (VOICE
  routeable, `voice_drift` in `allowed_context_modes`), so NO orphan exemption is
  needed. Verify the ORPHAN-TEMPLATE gate passes without one.
- `prompt-surface-manifest` checker (ADR-037) — VOICE/`voice_drift` must be declared;
  the manifest INTENT-COMPLETENESS gate now recognises the third VOICE mode.
- Prompt-Path-Compliance test (ADR-046 §D.1) — assert VOICE/`voice_drift` resolves
  through PromptComposer Mode 1 to
  `_bundled/analysis/en/voice_drift/system.md` (no inline fallback, no app-layer
  loader, no system-prompt-in-user-channel — RULE-02b).
- ADR-056 commit gate — `voice_drift` runtime evidence (agent + service probes) is
  required to move it off governed adoption debt. Declared now; runtime evidence lands
  at implementation.

### 5. Test update plan

- Scoring module unit tests (per-chapter trend; profile-delta reuses
  `voice_metric_distances`; adjacent jumps with metric labels; deterministic banding;
  silent-chapter skip; "no profile" path returns no trend).
- Agent TestModel structured-output tests (ADR-035; `drift_type` ∈ the three literals;
  `confidence` range; sparse `per_chapter_notes`).
- Backend integration + SSE tests (Fake consumer; graceful "no profile" result for
  un-profiled characters; silent-chapter skip; per-character SSE yield; field-name
  parity with frontend types per RULE-17).
- Frontend Vitest (panel, hook, SSE client, i18n parity en/de/fr per RULE-16;
  Layout γ overview + expand states).
- Prompt-Path-Compliance test for VOICE/`voice_drift` (ADR-046 §D.1).

---

## Phase 2 Deferral (Author Voice — separate future ADR + cycle)

**Phase 2** of the ANAL-009 lane is **Author Voice**: (a) the author-voice *storage*
SSOT decision, (b) author-voice profiling (ANAL-007), (c) author-voice drift. It is
**explicitly deferred** to a separate cycle with its own future ADR. This ADR does
**not** attempt to resolve it.

**Open question that blocks Phase 2:** *where do author-voice metrics live?* Candidate
homes — User-Settings, Project-Settings, or a new `AuthorVoiceProfile` model — are
unresolved. `ProjectWritingProfile` is **not** yet runtime SSOT (SET-006 deferral), so
it cannot be assumed. Resolving this is an architecture decision deserving its own
design pass (storage SSOT + consumer contract + generation/checking/longitudinal
projections), not a rushed add-on to a character-drift ADR.

**When Phase 2 lands**, it will: add a fourth VOICE mode (`author_voice`, already
anticipated by ADR-055 D4 + the route-table comment), reuse the longitudinal pattern
this ADR validates (trend + jumps + trend-classifying agent), and reuse the
`voice_metric_distances` primitive on the author-side metrics once they have a home.

---

## Risks Surfaced for Coordinator/User Decision (before implementation)

These are NOT blockers for approving this ADR, but should be acknowledged before
implementation planning:

1. **N LLM calls per run (cardinality).** N profiled characters = N agent calls per
   run (e.g. 5 characters = 5 calls). Accepted (Decision 5) — the agent sees the whole
   trend in one call, so there is no per-chapter fan-out. If cost becomes a concern,
   the agent could later batch, but that dilutes per-character reasoning. Low risk.

2. **Metric-delta normalization reuse.** ANAL-009 reuses `voice_metric_distances` and
   the green/yellow/fair/red banding (`band_for_score`) from `voice_check_scoring.py`.
   The per-metric normalization weights are ADR-057's tuning parameters (eval-tunable
   via ADR-032). Drift inherits the same normalization; if drift-specific calibration
   is needed later, it is an eval change, not an architecture change. Low risk.

3. **Long-novel compute cost (no caching).** A novel with many chapters × many
   characters runs `DialogueParser` + `VoiceMetricsAnalyzer` per (character, chapter).
   v1 does not cache (Decision 5 — do not optimize without measurement). If a measured
   run is too slow, cache per-chapter metrics keyed by content hash (invalidates on
   edit/re-profile) — a future change behind the same service interface. Flagged, not
   blocking.

4. **Classification label semantics (frontend derivation).** The row badge is a
   composite (band-derivable "Stable" vs the agent's `drift_type`). The exact
   derivation is a frontend concern guided by the approved mockup; the data contract is
   fixed by this ADR. Low risk.

No decision requires a user call before implementation beyond approving this ADR + the
spec rewrite.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02a/02b | ✅ | `voice_drift` prompt = PromptComposer Mode 1 (intent + `voice_drift` context_mode + governed EN template); no inline f-string, no production fallback, no app-layer loader, no system-prompt-in-user-channel. |
| RULE-03 | ✅ | Contracts (`CharacterVoiceDriftServiceProtocol`, `CharacterVoiceDriftAgent` Protocol, `CharacterVoiceDriftResult` output type, the trend/jump scoring API) defined before implementation. |
| RULE-04 | ✅ | Modularised: trend/jump scoring in `voice_drift_scoring.py`; agent in `character_voice_drift_agent.py` + `_types.py`; Backend split into `contracts_voice_drift.py` / `schemas_voice_drift.py` / `voice_drift_service.py` / `router_voice_drift.py` / `dependencies_voice_drift.py` (+ RULE-04 split helpers if the service approaches its limit, mirroring WRITE-010). |
| RULE-05/06 | ✅ | Core owns scoring + agent; Backend owns service/router; one responsibility per file. Drift reads via the consumer contract, not KB directly. |
| RULE-07 | ✅ | `analysis → profiles (consumer) → kb.schemas` read-direction only; no `apps/`→`core` cycle; reuses the acyclic `profiles → kb.schemas` import ADR-057 verified. |
| RULE-11 | ✅ | Character without `voice_analysis` → graceful "no profile" result; character silent in a chapter → skipped (no artificial zeros); no profiled characters → empty result, not an error. |
| RULE-13 | ✅ | SSE + non-streaming share the service interface (mirrors ANAL-005/008/057; ADR-065 two-method run/stream). |
| RULE-17 | ✅ | Backend SSE event field names match frontend TypeScript types (test asserted). |
| RULE-22 / CR-04 | ✅ | Cross-feature coherence: producer (ANAL-008, unchanged) + generation consumer (unchanged) + checking consumer (unchanged) + NEW longitudinal consumer (reads via the same `VoiceProfileConsumer` contract — no SSOT bypass) defined together. |
| ADR-021 | ✅ | Per-chapter metrics deterministic (reuse `VoiceMetricsAnalyzer` + `voice_metric_distances`); LLM only classifies the trend qualitatively (same hybrid tier as ANAL-003/008/057). |
| ADR-035 | ✅ | Drift agent structured output validated. |
| ADR-050 | ✅ | Drift service consumes via `VoiceProfileConsumer.assemble_for_checking()` — no SSOT bypass (the longitudinal consumer is just another caller of the existing contract). |
| ADR-054 | ✅ | Mode-1 PromptComposer mandate honoured (governed EN template, no inline debt reintroduced). |
| ADR-055 | ✅ | Closes Risk #2 (ANAL-009 spec rewritten to consume `voice_metrics` via the consumer; stale "map to SpeechPatterns" assumption removed); reuses the routeable VOICE intent; preserves "metrics never reach generation". |
| ADR-056 | ✅ | `voice_drift` runtime evidence (agent + service probes) declared now; lands at implementation to move off governed adoption debt. |
| ADR-057 | ✅ | Satisfies Risk #3 + Review Trigger (ANAL-009 reuses `voice_metric_distances` — no duplication); reuses `band_for_score` / `metric_delta_subscore`. |

---

## Review Trigger

- [x] When this ADR is approved + the spec is rewritten — ADR-055 Risk #2 (stale
      "map to SpeechPatterns" assumption) is resolved; ADR-057 Risk #3 (delta-primitive
      reuse) is satisfied. (Closed by this ADR's authoring.)
- [ ] When this ADR is implemented — verify the drift service reads `voice_metrics` via
      `VoiceProfileConsumer.assemble_for_checking()` (not KB directly); verify
      `formatted_voice_profiles` is unaffected; verify the agent is called once per
      character; verify silent chapters are skipped.
- [ ] When Phase 2 (Author Voice) is scoped — open a separate ADR resolving the
      author-voice storage SSOT (User-Settings vs Project-Settings vs a new
      `AuthorVoiceProfile` model; `ProjectWritingProfile` is not yet runtime SSOT per
      SET-006 deferral); add the `author_voice` context_mode as the fourth VOICE mode;
      reuse the longitudinal pattern validated here.
- [ ] If long-novel compute cost is measured as too slow — add per-chapter metric
      caching keyed by content hash (invalidates on edit/re-profile) behind the same
      service interface (Decision 5 deferred this).
- [ ] If a "baseline chapter" reference toggle becomes a requirement — add it as a UI
      toggle on signal (i) (Decision 2 deferred signal (ii)); no new scoring primitive.
- [ ] If metric-delta banding proves mis-calibrated for drift specifically — recalibrate
      via ADR-032 Pydantic Evals (the banding is pure-logic, eval-tunable).

---

## Cross-References

- ADR-021 — deterministic analysis (pre-names `core/analysis/voice_metrics.py`).
- ADR-035 — agent output validation.
- ADR-043 — `useAIOperation` (frontend hook primitive).
- ADR-050 Decision 3 — `VoiceProfileConsumer` contract (the read path this ADR's
  longitudinal consumer reuses — no SSOT bypass).
- ADR-054 — Mode-1 PromptComposer mandate.
- ADR-055 — character-voice storage contract + VOICE routeable (Risk #2 closed here;
  route + storage + Foundation reused; `voice_drift` is the third mode ADR-055 D4
  anticipated).
- ADR-056 — runtime-aware adoption gate (`voice_drift` runtime evidence).
- ADR-057 — voice-check checking-path contract + reusable delta primitive (Risk #3 +
  Review Trigger satisfied here; `voice_metric_distances` / `metric_delta_subscore` /
  `band_for_score` reused).
- ADR-065 — RULE-13 two-method run/stream.
- ANAL-009 spec — feature-level implementation contract (rewritten against this ADR).
- ANAL-008 spec — sibling producer (✅ stable).
- Approved visualization mockup — `_scratch/anal-009-drift-mockup/anal-009-drift-viz-mockup.html`
  (gitignored; Layout γ reference).
