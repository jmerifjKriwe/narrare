---
id: ANAL-009
title: "Character Voice Drift Detection (Phase 1)"
status: stable
area: analysis
mvp: false

ui_tooltip: "See how each character's voice drifts across your book."
ui_help_short: |
  Has a character's voice drifted across chapters? Character Voice Drift tracks
  how each character's speech evolves — intentional evolution, context-driven
  shifts, or unintended inconsistency — against their stored voice profile.
ui_help_long: |
  ## Character Voice Drift (Phase 1)

  Track how each character's voice changes across your novel. Know whether a
  shift is intentional evolution, scene-driven context, or unintended
  inconsistency — per character, chapter by chapter.

  > **Phase 1 is per-character.** Author-voice drift (the overall narrator's
  > voice) is a planned **Phase 2** feature.

  **What gets compared (per character, per chapter):**

  - Sentence structure shifts (length, variation)
  - Vocabulary level changes (type-token ratio, syllable density)
  - Dialogue rhythm and pacing
  - Contraction rate and punctuation habits
  - Verbal-tic and catchphrase frequency

  Each chapter is matched against the character's stored voice profile
  (from Character Voice Profiling, ANAL-008) and scored as a **match to
  profile** (100 = matches perfectly).

  **How it works:**
  1. Profile your characters first (Character Voice Profiling, ANAL-008)
  2. Click "Voice Drift" in the Analysis panel
  3. The whole novel is analysed (per character, per chapter)
  4. The overview heatmap shows every character × every chapter:
     - Colour band per cell (stable / minor / moderate / major drift)
     - ⚡ jump markers where a metric shifted sharply between chapters
     - Overall match-to-profile % and a classification per character
  5. Click a character row to expand a detail card:
     - Sparkline of the per-chapter trend
     - Jump list (which metric jumped, where)
     - The AI's reasoning: evolution, context, or inconsistency?
     - Per-chapter notes and chapters to review

  **Interpreting the classification:**

  - **Evolution** — gradual shift aligned with the character's arc (often fine)
  - **Context** — scene-driven variation, e.g. action reads faster (usually fine)
  - **Inconsistent** — unexplained drift that may confuse readers (review)

  **Match-to-profile bands:** stable ≥ 90 · minor 70–89 · moderate 50–69 · major < 50.

  **Best practices:**
  - Profile characters first (ANAL-008); drift needs a baseline profile
  - Run after a draft exists across several chapters
  - Context matters — action scenes differ naturally
  - Not all drift is bad — evolution is natural over a long project

  Voice drift isn't always wrong. Many characters evolve intentionally. This
  tool helps you distinguish intentional choices from problematic
  inconsistency, per character.
ui_available_in: [analysis]

service: analysis/voice_drift_service.py
contract: analysis/contracts_voice_drift.py#CharacterVoiceDriftServiceProtocol
router: analysis/router_voice_drift.py
prompt: core/prompts/_bundled/analysis/en/voice_drift/system.md
requires: [INFRA-001, INFRA-002, KB-001, ANAL-008, WRITE-010]
---

# ANAL-009 — Character Voice Drift Detection (Phase 1)

> **Architecture authority:** [ADR-073](../../architecture/decisions/ADR-073-voice-drift-character.md)
> (Character Voice Drift Contract & `voice_drift` Prompt Surface). The technical
> sections below implement that ADR. **Phase 1 is implemented (2026-07-26) across
> all layers and runtime-adopted** (`status: stable`; ADR-073 ✅ Implemented).
> Author-voice drift is **Phase 2** — deferred, own future ADR.

## Phasing (read this first)

ANAL-009 is split into two phases. **This spec covers Phase 1 only.**

| Phase | Scope | Status | Authority |
|-------|-------|--------|-----------|
| **Phase 1 (this spec)** | **Character** Voice Drift — longitudinal drift of one character across chapters, against their stored ANAL-008 profile. Builds on existing ANAL-008 + WRITE-010 infra. | `stable` | ADR-073 |
| Phase 2 (deferred) | **Author** Voice — author-voice storage SSOT decision + author-voice profiling (ANAL-007) + author-voice drift. | not started | separate future ADR |

**Why the split?** The voice lane was built "backwards" (ANAL-008 + WRITE-010
shipped first and are ✅ stable; ANAL-007 is deferred). Phase 1 unblocks on
existing infrastructure and validates the longitudinal pattern. Phase 2 is
blocked on an unresolved author-voice *storage* question (where do author-voice
metrics live? — User-Settings? Project-Settings? a new model? `ProjectWritingProfile`
is not yet runtime SSOT per SET-006 deferral) that deserves its own cycle. See
ADR-073 § Phase 2 Deferral. **Phase 1 drops the ANAL-007 dependency.**

## What it does

Tracks how a single character's voice drifts across the chapters of a novel,
comparing each chapter's dialogue to that character's stored ANAL-008 voice
profile. Produces a per-(character, chapter) match-to-profile trend, flags
jump points where a metric shifted sharply between adjacent chapters, and
classifies each character's longitudinal drift as evolution, context, or
inconsistency.

**Read-only.** ANAL-009 writes nothing to KB (like WRITE-010; it is analysis,
not profiling). ANAL-008 remains the only writer of `voice_analysis`.

## Why it exists

Characters should sound consistent across a long novel. But voices naturally
evolve, scene context shifts register, and unintentional drift creeps in over
a long project written across many sessions. Per-character drift detection
makes the longitudinal change visible and classifies it, so the author can
distinguish intentional evolution from problematic inconsistency — per
character, not just "the book overall".

## How it works (User perspective)

1. Profile your characters first (Character Voice Profiling, ANAL-008) — drift
   needs a stored profile to compare against.
2. Click "Voice Drift" in the Analysis panel.
3. The whole novel is analysed (per character, per chapter). Characters
   without a stored profile are reported as "no profile"; chapters where a
   character doesn't speak are skipped for that character.
4. The **overview heatmap** shows every character × every chapter:
   - Each cell coloured by drift band (stable / minor / moderate / major) with
     the per-chapter match-to-profile %.
   - ⚡ jump markers between columns where a metric shifted sharply (hover →
     which metric: formality, pacing, sentence length, …).
   - A classification badge + overall match-to-profile % per character row.
5. Click a character row to **expand a detail card**:
   - Sparkline of the per-chapter match trend.
   - Jump list (which metric jumped, where).
   - The AI's reasoning: is this evolution, context, or inconsistency?
   - Per-chapter notes and chapters flagged for review.

> **Approved visualization:** Layout γ (hybrid heatmap overview + expandable
> detail). Reference mockup: `_scratch/anal-009-drift-mockup/anal-009-drift-viz-mockup.html`
> (gitignored — not committed to the repo). It demonstrates all three candidate
> layouts (α/β/γ) with identical mock data; γ was chosen. The score is a
> **match to profile** (100 = matches perfectly) — labelled "match to profile"
> to avoid the inverted meaning of "drift %".

## How it works (Technical)

> Mirrors the established analysis pattern (ANAL-003/008/057): deterministic
> analyzer + `NarrareAgent` structured output + governed EN template + SSE
> router + panel. Per ADR-021 + ADR-073.

**Entry point:** `apps/api/narrare/analysis/router_voice_drift.py` →
`POST /api/v1/analysis/voice-drift/{novel_id}` (novel-scoped; under
`AI_ANALYSIS_LIMITER`)
**Service:** `CharacterVoiceDriftService.analyze()` /
`.analyze_stream()` in `apps/api/narrare/analysis/voice_drift_service.py`
**Contract:** `CharacterVoiceDriftServiceProtocol` in
`apps/api/narrare/analysis/contracts_voice_drift.py`
**Agent:** `CharacterVoiceDriftAgent`
(`packages/core/narrare_core/agents/character_voice_drift_agent.py`,
`NarrareAgent` with structured output — **1 call per character**)
**Scoring (pure Core):** `packages/core/narrare_core/analysis/voice_drift_scoring.py`
**LLM Intent:** `LLMIntent.VOICE` (context_mode `voice_drift`; the **third** VOICE
mode after `character_voice` and `voice_check`; ADR-055 made VOICE routeable,
ADR-057 added the second mode, ADR-073 adds this one)
**Prompt:** PromptComposer Mode 1 —
`packages/core/narrare_core/prompts/_bundled/analysis/en/voice_drift/system.md`
(governed EN template; ADR-054)

### Architecture: hybrid longitudinal (ADR-021, mirrors ANAL-008/WRITE-010)

The feature splits into a **deterministic measurement** half and an **LLM
qualitative-classification** half:

```python
# Deterministic (pure Core, voice_drift_scoring.py) — reuses voice_check_scoring primitives
# Per (character, chapter):
#   DialogueParser → per-utterance attribution + metrics
#   VoiceMetricsAnalyzer → per-chapter VoiceMetrics
#   voice_metric_distances(profile.voice_metrics, chapter_metrics) → per-metric [0,1] delta
#   metric_delta_subscore(...) → per-chapter match [0,100] (100 = identical to profile)
#   band_for_score(...) → green/yellow/fair/red band
# Trend = the per-chapter match series; Jumps = adjacent-chapter delta via the same primitive

# LLM qualitative (1 call per character) — classifies the longitudinal trend
class CharacterVoiceDriftResult(BaseModel):
    drift_type: Literal["evolution", "context", "inconsistency"]
    confidence: float                              # 0.0–1.0
    longitudinal_reasons: list[str]                # why this classification
    per_chapter_notes: dict[str, str]              # chapter_id → note (sparse)
    suggested_attention: list[str]                 # chapter_ids to review
```

Measurement is **deterministic** (ADR-021): the per-chapter metrics, the trend,
the jumps, and the band are all pure Core. The agent only **interprets** the
trend qualitatively (the `evolution` vs `context` vs `inconsistency`
classification). This is exactly the hybrid tier ANAL-003/008/057 use.

### Comparison model (ADR-073 Decision 2)

Two complementary deterministic signals, both reusing `voice_metric_distances`:

- **(i) Profile-trend** — each chapter's metrics vs the stored profile's
  `voice_metrics` → per-chapter match sub-score → trend (the heatmap row / sparkline).
- **(iii) Adjacent-jump detection** — delta between consecutive chapters'
  metrics → jump points labelled with which metric shifted (localises *where*
  drift started).

A third candidate — chapter-vs-baseline-chapter (signal ii) — is **deferred** as
a future UI "reference toggle" (it is a reference-swap on signal (i), not a new
signal; no architecture impact to add later).

### Data contract (ADR-055-consistent — the stale "map to SpeechPatterns" note is removed)

> **Correction:** the earlier draft of this spec said *"The `CharacterVoiceProfile`
> structure should map to `SpeechPatterns` fields"* and used the same lossy
> mapping ANAL-008 originally carried. ADR-055 superseded that with the nested
> `voice_analysis` contract. ANAL-009 consumes the deterministic `voice_metrics`
> (NOT LLM metrics) via the `VoiceProfileConsumer` contract. This is recorded in
> ADR-055 Risk #2 and closed by ADR-073.

ANAL-009 reads voice data **via** `VoiceProfileConsumer.assemble_for_checking()`
(ADR-050), which returns `list[CharacterVoiceProfile]` where each profile carries
`voice_metrics` when ANAL-008 has profiled the character (ADR-057 closed the
checking-path model gap). **No SSOT bypass** — ANAL-009 never reaches into
`KBEntity.metadata["speech"]["voice_analysis"]["voice_metrics"]` directly (the
exact anti-pattern ADR-050 closed). The consumer is the single read path for
structured metrics; ANAL-009 is just another caller of the existing contract.

### Pipeline

```
novel → VoiceProfileConsumer.assemble_for_checking() → list[CharacterVoiceProfile]
                                                           (carries voice_metrics when profiled)
  for each profiled character:
    for each chapter (in order):
      DialogueParser        (per-character utterances in this chapter)
      VoiceMetricsAnalyzer  (per-chapter VoiceMetrics for this character)
      if character speaks in this chapter:
        trend_against_profile(profile.voice_metrics, chapter_metrics)   [signal i]
      else:
        skip this chapter for this character   (RULE-11: no artificial zeros)
    adjacent_jumps(per-chapter metrics)                                  [signal iii]
    deterministic band (band_for_score) + overall match
    → CharacterVoiceDriftAgent.run (ONE call — sees whole trend + jumps + descriptive profile)
    → CharacterVoiceDriftResult (drift_type, confidence, reasons, per_chapter_notes, attention)
    → SSE yield per character
  characters without a stored profile → graceful "no profile" result       (RULE-11)
```

### Module homes (ADR-073 Retrofit-Plan)

**Core (`packages/core/narrare_core/`):**
- `analysis/voice_drift_scoring.py` (NEW): `chapter_metric_trend()`,
  `trend_against_profile()` (reuses `voice_metric_distances` +
  `metric_delta_subscore`), `adjacent_jumps()` (reuses `voice_metric_distances`
  on consecutive chapters), `classify_severity()` (deterministic banding via
  `band_for_score`).
- `agents/character_voice_drift_agent.py` + `character_voice_drift_types.py`
  (NEW): `CharacterVoiceDriftAgent` + `CharacterVoiceDriftResult`.
- **Reused unchanged:** `DialogueParser`, `VoiceMetricsAnalyzer`,
  `VoiceProfileConsumer.assemble_for_checking()` (ADR-050),
  `voice_check_scoring.voice_metric_distances` / `metric_delta_subscore` /
  `band_for_score` (ADR-057 — no duplication).

**Prompt surface:**
- `prompts/route_table.py`: add `"voice_drift"` to
  `ROUTE_CONFIGS[LLMIntent.VOICE].allowed_context_modes` (third mode; default
  stays `character_voice`).
- `prompts/_bundled/analysis/en/voice_drift/system.md` (NEW, governed Mode 1).
- `scripts/architecture/prompt-surface-manifest.yaml` +
  `adoption-registry.yaml`: register VOICE/`voice_drift` (mirror the
  `voice_check` entries; runtime evidence lands at implementation per ADR-056).

**Backend (`apps/api/narrare/analysis/`):** `contracts_voice_drift.py`,
`schemas_voice_drift.py`, `voice_drift_service.py` (Mode-1 PromptComposer),
`router_voice_drift.py` (SSE `POST /analysis/voice-drift/{novel_id}`),
`dependencies_voice_drift.py`.

**Frontend (`packages/web/`):** `VoiceDriftPanel` + sub-components (overview
heatmap + expandable detail per Layout γ) + `useCharacterVoiceDrift`
(`useAIOperation`, ADR-043 — no manual AbortController) + SSE client +
i18n (en/de/fr). Wired into the editor analysis panels beside
`CharacterVoicePanel` / `VoiceCheckPanel`.

### Integration with the Checking Pipeline (ADR-050 / ADR-057)

ANAL-009 is a **new longitudinal consumer** of the `VoiceProfileConsumer`
contract. It reads exactly what WRITE-010 reads (`voice_metrics` via
`assemble_for_checking()`), at novel scope instead of chapter scope. Producer
(ANAL-008) and generation/checking consumers are unchanged — ANAL-009 is "one
more caller of the existing contract" (CR-04 coherence). See ADR-073 § CR-04.

## Constraints & Edge Cases

### Read-only (ADR-073 Decision 5)

ANAL-009 writes nothing to KB. It is analysis, like WRITE-010. ANAL-008 is the
only writer of `voice_analysis`. No caching in v1 (deterministic computation is
fast; caching is YAGNI until a measured performance problem — revisit via
content-hash-keyed per-chapter metric cache if needed).

### Determinism (ADR-021)

Per-chapter metrics are deterministic (stable across runs and minor edits). Only
the longitudinal classification (`drift_type`, reasons, notes) comes from the
LLM. This makes the trend + jumps suitable for reliable longitudinal comparison.

### Cardinality

1 agent call per character per run (N characters = N LLM calls). Accepted
(ADR-073 Decision 5) — the agent sees the whole trend in one call, so no
per-chapter fan-out.

### Edge Cases

- Character without a stored ANAL-008 profile → graceful "no profile" result
  (RULE-11).
- Character silent in a chapter → that chapter is skipped for that character
  (no artificial zeros in the trend).
- Project with no profiled characters → empty result, not an error.
- Very short dialogue in a chapter → noisy per-chapter metrics (surfaced via
  lower confidence, not hidden).
- Intentional POV/arc shifts may read as drift — the agent's `drift_type`
  classification (evolution/context) is meant to distinguish these from
  inconsistency.
- LLM availability required (metrics + trend + jumps are deterministic; the
  classification is not).

## Related Features

- [ANAL-008](ANAL-008-voice-character.md) — Writes the profiles + `voice_metrics`
  this feature compares against (✅ stable).
- [WRITE-010](../writing/WRITE-010-voice-checker.md) — Sibling checking consumer;
  ANAL-009 reuses its `voice_check_scoring` delta primitive (✅ stable).
- [ANAL-007](ANAL-007-voice-author.md) — Author voice analysis (**Phase 2**;
  deferred; separate storage decision, out of Phase 1 scope).
- [ANAL-010](ANAL-010-literary-suite.md) — Comprehensive comparison.
- [ADR-073](../../architecture/decisions/ADR-073-voice-drift-character.md) —
  Phase 1 architecture authority.
- [ADR-055](../../architecture/decisions/ADR-055-character-voice-contract.md) —
  Storage contract (Risk #2 closed by ADR-073).
- [ADR-057](../../architecture/decisions/ADR-057-voice-check-checking-path-contract.md)
  — Delta-primitive provider (Risk #3 satisfied by ADR-073).

## Status & History

- `project-init` — Added to registry as planned feature (originally author-voice
  drift; `requires: [ANAL-007]`).
- `2026-07-25` — **Reconceptualised as Phase 1 (Character Voice Drift).** The
  voice lane was built "backwards" (ANAL-008 + WRITE-010 shipped first; ANAL-007
  deferred), so the spec is split: Phase 1 (this spec) delivers character drift
  on existing infra; Phase 2 (author voice) is deferred to its own ADR. Stale
  "map to SpeechPatterns" assumption removed (ADR-055 Risk #2 closed by
  ADR-073); ANAL-007 dependency dropped for Phase 1. New `voice_drift`
  context_mode (third VOICE mode) + governed EN template specified (ADR-073).
  Comparison model fixed as profile-trend (i) + adjacent-jump detection (iii),
  both reusing `voice_metric_distances` (ADR-057 Risk #3 satisfied).
  Visualization fixed as Layout γ (approved mockup in `_scratch/`, gitignored).
  Status remains `planned` (implementation pending user approval of ADR-073).
- `2026-07-26` — **Phase 1 implemented across all layers and runtime-adopted.**
  Status → `stable`. All four task layers landed against [ADR-073](../../architecture/decisions/ADR-073-voice-drift-character.md)
  (✅ Implemented): **Core** (`a7aa3286`) — `voice_drift_scoring` (profile-trend
  signal i + adjacent-jump signal iii, both reusing `voice_metric_distances` — no
  duplication) + `CharacterVoiceDriftAgent` + `character_voice_drift_types` + the
  `voice_drift` governed EN template (third VOICE mode, Mode 1 ADR-054) + route +
  manifest/registry entries (108 drift tests); **Backend** (`26e1023b`) —
  `VoiceDriftService` (Mode-1 PromptComposer, binds `VoiceProfileConsumer`) + SSE
  `POST /analysis/voice-drift/{novel_id}` + contracts/schemas/dependencies
  (21 unit + 4 integration tests); **Frontend** (`8ea28176`) — `VoiceDriftPanel`
  (Layout γ: heatmap overview + expandable per-row detail) + `useCharacterVoiceDrift`
  hook + SSE client + i18n (en/de/fr) (45 new / 3002 total); **Platform** (`e899faae`)
  — `voice_drift` probes + runtime-evidence markers; `just check` 9/9, 9759 unit +
  3002 frontend tests, pyright 0. `voice_drift` is static ✅ / runtime ✅ / adopted ✅
  (PASS); adoption_debt 5 → 1 (true debt only). The drift service reads
  `voice_metrics` via `VoiceProfileConsumer.assemble_for_checking()` (no SSOT
  bypass — verified); read-only; 1 agent call per character; silent chapters
  skipped (RULE-11). **Phase 2 (Author Voice) remains deferred** to a separate
  future ADR — not claimed done.
