---
id: ANAL-007
title: "Author Voice Profiling"
status: planned
area: analysis
mvp: false

ui_tooltip: "Analyze your narrative voice and create an author-voice profile for AI generation."
ui_help_short: |
  Narrare can learn your unique writing voice — the narrator's sentence patterns,
  vocabulary, dialogue-to-prose ratio, and descriptive habits. Author Voice
  Profiling analyzes your existing chapters and creates a per-novel profile that
  helps AI write in your style.
ui_help_long: |
  ## Author Voice Profiling

  Teach Narrare to write like you. Author Voice Profiling analyzes your existing
  chapters to capture the narrative voice that runs through your prose — distinct
  from how individual characters speak.

  **What gets analyzed (the narrator's prose):**

  **Sentence Structure**
  - Length distribution (short, medium, long, varied)
  - Rhythm and flow patterns
  - Punctuation habits (em-dash, ellipsis, exclamation)

  **Vocabulary & Register**
  - Word choice and complexity level
  - Diversity and repetition (type-token ratio)
  - Formality register (casual ↔ formal)

  **Prose Composition (author-specific)**
  - Dialogue-to-narration ratio
  - Description density (sparse ↔ rich)
  - Action-vs-introspection balance
  - Figurative-language density (provisional proxy)

  **How it works:**
  1. Select 3+ chapters for analysis (more = better profile)
  2. Click "Analyze Voice" in the Analysis panel
  3. AI analyzes your narrative prose (30–60 seconds)
  4. Author-voice profile appears with:
     - Qualitative descriptors (formality, vocabulary level, sentence profile, …)
     - Curated representative prose passages
     - Prose-composition metrics (for future drift comparison)
  5. Save profile to this novel's project settings
  6. Future AI generation uses your author voice automatically

  **How AI uses your voice:**
  Generation reads the descriptive part of your profile (register, vocabulary
  level, sentence profile, emotional range, cultural markers, and your curated
  example passages) and shapes new prose to match. The numeric metrics are used
  ONLY for future drift comparison — they never reach generation.

  **Best practices:**
  - Analyze after 3+ chapters (10,000+ words) for accuracy
  - Include chapters from different story phases
  - Re-analyze after major style changes (the old profile is overwritten)
  - Review the profile before saving

  Your author-voice profile is stored locally with this novel and never shared.
  Delete it anytime to return to the default AI style.

  Note: This is the AUTHOR half of voice profiling. Character Voice Profiling
  (ANAL-008) captures how individual characters speak; this captures how YOU
  narrate.
ui_available_in: [analysis, settings]

service: analysis/author_voice_service.py
contract: analysis/contracts_author_voice.py#AuthorVoiceServiceProtocol
router: analysis/router_author_voice.py
prompt: core/prompts/_bundled/analysis/en/author_voice/system.md
# INFRA-001 (LLM Gateway — the AuthorVoiceAgent) + INFRA-002 (Prompt System —
# the governed Mode-1 author_voice template). Author voice does NOT depend on
# INFRA-004 (Embedding Store — no embeddings are involved) nor KB-001 (it writes
# ProjectSettings.author_voice, not a KB entity). The generation-consumer wiring
# touches INFRA-003 (Context Assembly) but that is the consumer side, not a hard
# dependency of the profiling feature itself.
requires: [INFRA-001, INFRA-002]
---

# ANAL-007 — Author Voice Profiling

> **Architecture authority:** [ADR-074](../../architecture/decisions/ADR-074-author-voice-storage.md)
> (Author Voice Storage Contract). The storage contract is **Accepted**; this
> spec defines the feature built on top of it — the analysis pipeline, the
> prompt-surface wiring, the generation consumer, and the SSE endpoint. The
> technical sections below implement ADR-074 + mirror the established
> character-voice pattern ([ADR-055](../../architecture/decisions/ADR-055-character-voice-contract.md),
> [ANAL-008](ANAL-008-voice-character.md)). This spec is `planned` (not yet
> implemented across layers).

## Scope

### In Scope

- The author-voice **profiling pipeline**: extract chapter prose → compute
  deterministic metrics (reused `VoiceMetrics` + new `AuthorMetrics`) →
  `AuthorVoiceAgent` (one LLM call) → descriptive profile.
- The **storage wiring** per ADR-074: `AuthorVoiceRepository` ↔
  `ProjectSettings.author_voice` JSONB + Alembic migration (RULE-14).
- The **prompt surface**: a fourth `author_voice` context_mode on
  `LLMIntent.VOICE` + governed EN template + the `{{author_voice}}` generation
  variable + `AuthorVoiceConsumer` rendering the descriptive group.
- The **Backend service + SSE endpoint** (novel-scoped, under
  `AI_ANALYSIS_LIMITER`).
- The **Frontend panel + hook + i18n** (mirrors `CharacterVoicePanel`).

### Out of Scope

- **Phase 2B — Author Voice Drift** (ANAL-009 Phase 2): the longitudinal
  per-chapter drift detector that reads `author_metrics` +
  `voice_analysis.voice_metrics` via the repository. It reuses the
  `voice_metric_distances` delta primitive (ADR-057/073) applied to
  author-voice metrics. Its own ADR/spec when scheduled; **cross-referenced
  here** so this spec's `AuthorMetrics` is designed to be delta-comparable.
- **Series / Reihe voice**: a series-level voice home
  (`SeriesSettings.author_voice`) is forward-compatible (ADR-074
  Forward-compatibility) but not built — no `Series` entity exists today.
- **Historical versioning of the profile**: re-analysis overwrites the stored
  profile (YAGNI for v1; Phase 2B drift re-computes per-chapter on the fly,
  like Phase 1 — it does not need historical profiles).

## What it does

Analyzes a novel's chapter prose to extract the author's narrative voice — the
narrator's register, vocabulary level, sentence profile, emotional range,
cultural/regional markers, plus prose-composition signals (dialogue ratio,
description density, action/introspection balance, figurative-language density).
The resulting per-novel profile is stored on `ProjectSettings.author_voice`
(ADR-074) and consumed by generation to shape new prose in the author's style.

## Why it exists

Default AI prose sounds generic. A writer's voice is the product of thousands
of choices in sentence structure, vocabulary, rhythm, and the balance between
dialogue, description, action, and introspection. Author Voice Profiling
captures these patterns so AI generation (WRITE-002, WRITE-003, …) can narrate
in the author's style rather than a neutral default.

*Why?* Because per-character voice (ANAL-008) only covers how individuals
**speak**; it says nothing about how the **narrator** writes the prose between
the dialogue. *Why?* Because readers experience a novel's voice as a whole —
the narrator's sentences are the substrate every scene is built on. Author
voice is the missing complement to character voice: together they cover *how
the book sounds*.

## Root Cause / Motivation

This feature was **deferred** by ADR-073 (Character Voice Drift Phase 2
Deferral) on a single blocking question — *where do author-voice metrics
live?* ADR-074 resolved that question (novel-scoped
`ProjectSettings.author_voice` JSONB, mirroring `adaptive_settings`). With
storage decided, ANAL-007 is unblocked. This spec is the **Phase 2A** deliverable
of the voice lane; ANAL-009 Phase 2 (author drift) builds directly on it.

The voice-lane build order is recorded: `007 author → 008 character → 009 drift
→ WRITE-010 checker` was built as `008 → WRITE-010 → 009-Phase1 (character)`
with `007 + 009-Phase2 (author)` deferred until storage was decided (ADR-073).
This is a recorded adaptation, not a planning failure.

## How it works (User perspective)

1. Select 3+ chapters for analysis (more chapters = better profile)
2. Click "Analyze Voice" in the Analysis panel
3. AI analyzes the narrative prose (30–60 seconds)
4. Author-voice profile appears showing:
   - **Descriptors**: formality, vocabulary level, sentence profile, emotional
     range, cultural/regional markers (qualitative, from the LLM)
   - **Examples**: curated representative prose passages
   - **Composition metrics**: dialogue ratio, description density,
     action/introspection balance, figurative-language density (deterministic;
     for future drift comparison)
5. Review and adjust if needed
6. Save profile to this novel's project settings

Once saved, AI generation automatically reads the descriptive part of the
profile and shapes new prose to match. Delete the profile anytime to return to
the default AI style.

## How it works (Technical)

> Mirrors the established analysis pattern (ANAL-003/004/008): deterministic
> analyzer + `NarrareAgent` structured output + governed EN template + SSE
> router + panel. Per ADR-021 + ADR-074. **Differs from character voice in
> WHAT it measures** (full chapter prose, not per-utterance dialogue) — see
> "Prose-level measurement" below.

**Entry point:** `apps/api/narrare/analysis/router_author_voice.py` → `POST /api/v1/analysis/author-voice/{novel_id}`
**Service:** `AuthorVoiceService.analyze()` in `apps/api/narrare/analysis/author_voice_service.py`
**Contract:** `AuthorVoiceServiceProtocol` in `apps/api/narrare/analysis/contracts_author_voice.py`
**Agent:** `AuthorVoiceAgent` (`packages/core/narrare_core/agents/author_voice_agent.py`, `NarrareAgent` with structured output)
**LLM Intent:** `LLMIntent.VOICE` (context_mode `author_voice`; the fourth VOICE mode after `character_voice` / `voice_check` / `voice_drift`)
**Prompt:** PromptComposer Mode 1 — `packages/core/narrare_core/prompts/_bundled/analysis/en/author_voice/system.md` (governed EN template; ADR-054)
**Storage:** `ProjectSettings.author_voice` JSONB via `AuthorVoiceRepository` (ADR-074)

### Architecture: hybrid metrics (ADR-021, mirrors ANAL-008)

The feature is split into a **deterministic measurement** half and an **LLM
qualitative-understanding** half, exactly like ANAL-008. The descriptive/metric
boundary (ADR-055/057) is preserved: **metrics NEVER reach generation**.

```python
# Deterministic metrics — REUSED voice-generic block (ADR-074 type-reuse)
# Computed by VoiceMetricsAnalyzer.analyze_text() on the AUTHOR's full prose.
# For ANAL-009 Phase 2 author drift comparison ONLY — never rendered.
class VoiceMetrics:                       # reused verbatim (ADR-074)
    avg_sentence_length: float | None
    sentence_length_std: float | None
    type_token_ratio: float | None
    avg_syllables_per_word: float | None
    contraction_rate: float | None
    verbal_tic_frequency: dict[str, float] | None
    punctuation_profile: dict[str, float] | None

# Deterministic author-specific PROSE-LEVEL metrics (NEW — ADR-074)
# For ANAL-009 Phase 2 author drift comparison ONLY — never rendered.
class AuthorMetrics:
    dialogue_ratio: float | None              # 0.0–1.0  (quoted words / total words)
    description_density: float | None         # 0.0–1.0  (modifier density proxy)
    action_introspection_ratio: float | None  # 0.0–1.0  (action..introspection proxy)
    metaphor_density: float | None            # 0.0–1.0  (simile/figurative-cue proxy — PROVISIONAL)

# LLM qualitative descriptors (one structured-output call consuming prose + metrics).
# Descriptive group → rendered into {{author_voice}} by AuthorVoiceConsumer.
class AuthorVoiceOutput:
    formality: float                       # 0.0 casual – 1.0 formal
    vocabulary_level: str                  # simple | moderate | complex
    sentence_profile: str                  # short | medium | long | varied
    emotional_range: str                   # restricted | moderate | expressive
    cultural_regional_markers: str | None  # intrinsic — persisted
    author_examples: list[str]             # curated representative prose passages
```

> **Boundary invariant (binding, ADR-074):** the `AuthorVoiceAgent` produces
> ONLY descriptive fields. It NEVER produces `VoiceMetrics` or `AuthorMetrics`
> — those are computed deterministically by the analyzers. This keeps the
> ADR-021 determinism guarantee intact (metrics are stable across runs for
> Phase 2B drift comparability) and preserves the descriptive/metric boundary.

### Architecture: prose-level measurement (the author-voice difference)

Character voice (ANAL-008) measures **per-utterance dialogue** attributed to a
single speaker via `DialogueParser` → `VoiceMetricsAnalyzer.analyze()` (groups
`AttributedUtterance`s by speaker). Author voice measures **the narrator's full
chapter prose** — narration + dialogue together, as a single voice. The
measurement vocabulary is the same (the types are voice-generic, ADR-074
type-reuse); the **input shape differs**.

**Foundation reuse — `VoiceMetricsAnalyzer.analyze_text()` (NEW public entry point):**

`VoiceMetricsAnalyzer` already computes every `VoiceMetrics` field in
`_compute_metrics(texts, verbal_tic_candidates)`, which takes a plain
`list[str]` — the speaker-grouping in the public `analyze()` is the only layer
that is dialogue-specific. Author voice adds a second public entry point that
reuses `_compute_metrics` on full chapter prose directly, bypassing the
speaker grouping:

```python
# packages/core/narrare_core/analysis/voice_metrics.py (EXTEND — reuse, do not duplicate)
class VoiceMetricsAnalyzer:
    def analyze_text(self, chapter_texts: list[str]) -> VoiceMetrics:
        """Prose-level VoiceMetrics for author-voice profiling (ANAL-007 / ADR-074).

        Runs the SAME _compute_metrics pipeline as analyze(), but over the
        author's full chapter prose (narrator + dialogue together) rather than
        per-speaker attributed utterances. Deterministic (ADR-021). The
        author's narrative voice is one voice, so the result is a single
        VoiceMetrics block, not a per-speaker dict.
        """
        return self._compute_metrics(chapter_texts, verbal_tic_candidates=None)
```

> **Documented difference (binding):** `analyze()` is for character voice
> (per-utterance, grouped by speaker); `analyze_text()` is for author voice
> (prose-level, single voice). Both call the same `_compute_metrics` — zero
> measurement-logic duplication. `verbal_tic_frequency` is `None` for author
> voice (verbal tics are a per-character concept, not a narrator concept).

**Foundation NEW — `AuthorMetricsAnalyzer`:**

The author-specific prose-level metrics (`dialogue_ratio`,
`description_density`, `action_introspection_ratio`, `metaphor_density`) have
no character-voice analogue, so a new deterministic analyzer computes them. It
is **pure** and **deterministic** (ADR-021), may consume `core/nlp/` primitives
(spaCy POS) respecting RULE-07 (`analysis → nlp`).

| Field | Computation | Determinism / Provisionality |
|-------|-------------|------------------------------|
| `dialogue_ratio` | Quoted-dialogue word count / total word count, via `DialogueParser` quote-span extraction. | Deterministic, stable. |
| `description_density` | Modifier density proxy — (adjective + adverb token count) / total token count, via `core/nlp` POS. | Deterministic; provisional proxy (the "right" definition of descriptive density is subjective — eval-tunable via ADR-032). |
| `action_introspection_ratio` | Verb/action density vs internal-thought-marker density proxy (thought tags, first-person reflection cues). 0.0 action-heavy → 1.0 introspection-heavy. | Deterministic; provisional proxy. |
| `metaphor_density` | **Simile/figurative-cue proxy** — density of simile markers ("like a", "as a", "as if") + a curated figurative-cue lexicon. | **Deterministic; deliberately crude; the hardest metric.** See decision below. |

> **Key design decision — `metaphor_density` handling (Q1 resolution):**
> True metaphor detection requires semantic understanding and is not reliably
> deterministic. Two options were considered:
>
> - **(A) LLM-assist** — have the `AuthorVoiceAgent` return a qualitative
>   `metaphor_density` estimate stored in `AuthorMetrics`. **REJECTED** — it
>   would violate two invariants at once: (a) the descriptive/metric boundary
>   (the agent must produce ONLY descriptive fields, per the boundary invariant
>   above) and (b) ADR-021 determinism (a drift-comparable metric must be
>   stable across runs; an LLM estimate is not). Phase 2B drift needs stable
>   metrics.
> - **(B) Deterministic simile/figurative-cue proxy** — count simile-cue
>   patterns ("like a", "as a", "as if", "as though") + a small curated
>   figurative-cue lexicon, normalized by word count. **CHOSEN.** It is crude
>   (it catches similes, not all metaphors) but deterministic, stable, and
>   cheap — which is exactly what a drift-comparable metric must be. The field
>   is **nullable** and the metric set is **provisional** (`extra="allow"`): if
>   ADR-032 evals show the proxy is too noisy to be useful for drift, it can be
>   dropped to `None` (migration-free) or replaced without touching the rest of
>   the profile.
>
> The qualitative sense of the author's figurative language is captured in the
> **descriptive** group (the agent may comment on imagery in
> `cultural_regional_markers` / `author_examples`); the **metric** is a stable
> deterministic proxy. This is the clean separation ADR-021 + the boundary
> require.

### Pipeline

```
chapters (selected, 3+)
  → extract prose               (full chapter text: narrator + dialogue together)
                                [Backend: chapter_repo]
  → VoiceMetricsAnalyzer.analyze_text(chapter_prose)
                                → VoiceMetrics (deterministic, REUSED)
                                [Core: core/analysis/voice_metrics.py — ADR-021]
  → AuthorMetricsAnalyzer.analyze(chapter_prose)
                                → AuthorMetrics (deterministic, NEW)
                                [Core: core/analysis/author_metrics.py]
  → resolve governed author_voice system prompt via PromptComposer Mode 1
                                (LLMIntent.VOICE + context_mode="author_voice")
                                [Backend: analysis/author_voice_prompt.py — RULE-02b]
  → AuthorVoiceAgent(model, system_prompt=resolved).run(
        prompt=prose_excerpt + metrics_summary, deps=...)
                                → AuthorVoiceOutput (ONE LLM call — descriptive fields only)
                                [Core: core/agents/author_voice_agent.py]
  → assemble AuthorVoiceProfile
        (voice_analysis descriptive ← agent output
         + voice_analysis.voice_metrics ← VoiceMetricsAnalyzer
         + author_metrics ← AuthorMetricsAnalyzer
         + author_examples ← agent output
         + updated_at + is_fresh)
  → AuthorVoiceRepository.save(novel_id, profile)
        + bump ProjectSettings.updated_at (so freshness signals work)
                                [Backend: analysis/author_voice_repository.py — ADR-074]
```

### Data contract (ADR-074 — the storage shape this spec consumes)

Author voice is **structurally the same shape as character voice** (deterministic
metrics + LLM qualitative descriptors). The contract therefore **reuses the
voice-generic types** and adds author-specific fields, exactly as ADR-074
specifies.

```python
# packages/core/narrare_core/.../author_voice.py  (Core — exact path is an
# implementation decision; ADR-074 Retrofit-Plan §1 lists candidates. The
# voice-generic VoiceAnalysis/VoiceMetrics are EXTRACTED to a voice-generic
# home + re-exported from kb/schemas/character.py for backward compat.)

class AuthorMetrics(BaseModel):
    """Author-specific PROSE-LEVEL metrics — comparison ONLY (ANAL-009 Phase 2
    author drift). NEVER rendered into generation. ``extra="allow"`` lets the
    metric block grow without a migration. Provisional set (see metaphor_density
    decision above)."""
    model_config = ConfigDict(extra="allow")
    dialogue_ratio: float | None = None                 # 0.0–1.0
    description_density: float | None = None            # 0.0–1.0 sparse..rich
    action_introspection_ratio: float | None = None     # 0.0–1.0 action..introspection
    metaphor_density: float | None = None               # 0.0–1.0 (simile-cue proxy — PROVISIONAL)

class AuthorVoiceProfile(BaseModel):
    """Machine-derived author-voice profile (ANAL-007 / ADR-074).

    Persisted as ``ProjectSettings.author_voice`` JSONB. Novel-scoped.
    Mirrors the ADR-055 descriptive/metric structure (deterministic metrics +
    LLM qualitative descriptors), REUSING the voice-generic ``VoiceAnalysis`` /
    ``VoiceMetrics`` and ADDING author-specific prose-level metrics.
    """
    model_config = ConfigDict(extra="allow")

    # --- Descriptive group (rendered into {{author_voice}} by AuthorVoiceConsumer) ---
    # REUSED voice-generic descriptive block (formality, vocabulary_level,
    # sentence_profile, emotional_range, cultural_regional_markers, voice_examples).
    voice_analysis: VoiceAnalysis | None = None
    # Author-specific curated representative prose passages (the agent's
    # author_examples → stored on voice_analysis.voice_examples OR here; the
    # merge step decides — the consumer renders whichever is populated).
    author_examples: list[str] | None = None

    # --- Freshness (mirrors character-voice: profiles/_freshness.py is_stale) ---
    updated_at: str | None = None
    is_fresh: bool = True

    # --- Metric group (comparison ONLY — NEVER rendered into generation) ---
    # Author-specific prose-level metrics (dialogue_ratio, description_density,
    # action_introspection_ratio, metaphor_density).
    author_metrics: AuthorMetrics | None = None
    # NOTE: voice_analysis.voice_metrics carries the voice-GENERIC metrics
    # (avg_sentence_length, type_token_ratio, ...) — also comparison-only.
```

> **Type-reuse (ADR-074 binding):** `AuthorVoiceProfile` composes the reused
> `VoiceAnalysis` (which carries both the descriptive group and the nested
> voice-generic `VoiceMetrics`). There is NO parallel `AuthorVoiceMetrics` /
> `AuthorVoiceAnalysis` — that would duplicate the measurement vocabulary and
> drift (RULE-22). The extraction of `VoiceMetrics`/`VoiceAnalysis` to a
> voice-generic Core home + backward-compat re-exports is ADR-074 Retrofit-Plan
> step 1; it ships as the first atomic step so ANAL-008/WRITE-010/ANAL-009-Phase-1
> stay green with zero import edits.

> **Delta-comparability for Phase 2B (design intent, binding):** every
> `AuthorMetrics` field is `float | None` in `[0.0, 1.0]`, so the
> `voice_metric_distances` delta primitive (ADR-057/073) generalizes trivially
> to author metrics in Phase 2B. Phase 2B will add an
> `author_metric_distances` helper (or extend the existing primitive) — both
> metric blocks are designed to be delta-comparable from the start.

### Storage wiring (ADR-074 — `AuthorVoiceRepository`)

A new Backend repository mirrors `AdaptiveSettingsRepository` (ADR-069 D2) —
the proven pattern for a per-novel structured JSONB column on `ProjectSettings`.

```python
# apps/api/narrare/analysis/author_voice_repository.py  (NEW — mirrors adaptive/repository.py)
class AuthorVoiceRepository:
    """Load/save/clear ProjectSettings.author_voice JSONB (ADR-074).

    Maps between the JSONB column and the Core AuthorVoiceProfile Pydantic
    model. Pydantic validation on read (malformed JSON → None, RULE-11)."""
    async def load(self, novel_id: UUID) -> AuthorVoiceProfile | None: ...
    async def save(self, novel_id: UUID, profile: AuthorVoiceProfile) -> None: ...
    async def clear(self, novel_id: UUID) -> None: ...   # "delete to return to default"
```

**Module home decision:** `apps/api/narrare/analysis/` (the analysis domain
owns the write path; the generation consumer reads via the same repository).
ADR-074 named `apps/api/narrare/{analysis|settings}/author_voice_repository.py`
as the candidate set; `analysis/` is chosen because the producer is an analysis
service and the type is Core-owned (RULE-06: the repository lives with its
writer, not in a generic `settings/` bag).

**Migration (RULE-14 — binding, same task as the column):**

```python
# apps/api/alembic/versions/<next>_author_voice_column.py  (NEW — mirrors 0033_adaptive_settings_column)
def upgrade() -> None:
    op.add_column("project_settings", sa.Column("author_voice", sa.JSONB(), nullable=True))
def downgrade() -> None:
    op.drop_column("project_settings", "author_voice")
```

Plus a schema round-trip regression test
(`test_project_settings_has_author_voice_column`, mirroring the adaptive test).
A model change without this migration is a build failure (RULE-14).

**Freshness:** `save()` writes `AuthorVoiceProfile.updated_at` and relies on
`ProjectSettings.updated_at` (`onupdate=func.now()`) bumping on the row update,
mirroring how character-voice bumps `KBEntity.updated_at` so
`profiles/_freshness.py::is_stale()` works. The generation consumer surfaces a
stale-marker rather than silently dropping the profile (RULE-11).

### Prompt surface (Q3 resolution — the deferred ADR-074 wiring)

ADR-074 deferred the prompt-surface wiring to ANAL-007. This spec resolves it.
Per adr-process §D.4, the prompt-mechanics change has its own Retrofit-Plan
below.

**1. Fourth `context_mode` on `LLMIntent.VOICE`:**

Add `author_voice` to `PromptRouteConfig.allowed_context_modes` for VOICE
(currently `{"character_voice", "voice_check", "voice_drift"}`). The governed
EN template is `core/prompts/_bundled/analysis/en/author_voice/system.md`
(Mode 1, ADR-054). It is a PROFILER (builds a descriptive + metric author-voice
profile), distinct from the character_voice profiler, the voice_check checker,
and the voice_drift classifier.

**2. Generation consumer — `AuthorVoiceConsumer` (parallel to `VoiceProfileConsumer`):**

```python
# packages/core/narrare_core/profiles/contracts.py  (EXTEND — parallel to VoiceProfileConsumer)
@runtime_checkable
class AuthorVoiceConsumer(Protocol):
    """Consumer-side contract for author-voice data (ADR-074 / ANAL-007).

    Reads ProjectSettings.author_voice via AuthorVoiceRepository and renders
    the DESCRIPTIVE group into the {{author_voice}} prompt variable. MUST NOT
    render voice_analysis.voice_metrics or author_metrics (descriptive/metric
    boundary — ADR-055/057/074). Bound at Backend DI composition time."""
    async def get_profile(self, project_id: UUID) -> AuthorVoiceProfile | None: ...
    def render_for_generation(self, profile: AuthorVoiceProfile | None) -> str:
        """Render descriptive group → {{author_voice}} text. Empty string when
        no profile (graceful degradation, RULE-11). NEVER reads metrics."""
```

`WritingContextAssembler.assemble()` populates a new `WritingContext.author_voice`
field from `author_voice_consumer.render_for_generation(...)`, exactly parallel
to how it populates `character_voice_profiles` from
`voice_profile_consumer.assemble_for_generation(...)` today
(`writing/context_assembler.py:234-239`).

**3. Prompt variable decision (Q3 key decision) — introduce `{{author_voice}}`:**

> **Decision: introduce a NEW `{{author_voice}}` variable.** Do NOT repurpose
> the unregistered `{{author_style_examples}}`.
>
> - **(A) Introduce `{{author_voice}}`** — **CHOSEN.** The consumer renders
>   the FULL descriptive profile (formality, vocabulary_level, sentence_profile,
>   emotional_range, cultural_regional_markers, author_examples). The semantics
>   are "the author's narrative voice", which parallels
>   `{{character_voice_profiles}}` (per-character) cleanly. Naming is honest:
>   the variable carries the descriptive profile, not just examples.
> - **(B) Repurpose `{{author_style_examples}}`** — **REJECTED.** The name
>   implies EXAMPLES-ONLY, but the consumer renders the full descriptive
>   profile. It would mislead maintainers and create semantic debt. It was
>   never registered or wired (ADR-055/074 confirmed it is aspirational-only,
>   appearing nowhere except the stale ANAL-007 spec); repurposing an
>   unregistered aspirational name adds no value.

**Variable registration (RULE-22 §4/§6 — binding):**

- Register `author_voice` in **`SYSTEM_VARS`** in `prompts/variable_registry.py`
  (it is system-attributed descriptive text rendered from a machine-derived
  stored profile — directly analogous to `character_voice_profiles`, which is
  already in `SYSTEM_VARS`). It is **NOT** `_USER_CONTENT_VARS` — the rendered
  text is curated by the consumer from the author's prose, not user-authored
  prompt content, so no XML-wrapping is required (RULE-22 §6 does not apply).
- Add `author_voice` to the `optional_variables` of the **generation/writing
  intents** that should see author voice — mirroring where
  `character_voice_profiles` appears today (WRITE, EXTEND, REWRITE, COAUTHOR,
  CHAT, OUTLINE, INLINE_SUGGEST, STORY_SUGGEST per
  `prompt-surface-manifest.yaml`). Generation degrades gracefully to empty
  when no profile is saved (RULE-11).
- Update `scripts/architecture/prompt-surface-manifest.yaml` (add the
  `author_voice` context_mode under VOICE + add `author_voice` to the writing
  intents' `optional_variables`) and `scripts/architecture/adoption-registry.yaml`
  (register `analysis/author_voice: true` + the runtime marker, mirroring
  `analysis/voice_drift`).

> **Cross-feature flag (binding):** the generation-consumer wiring
> (`AuthorVoiceConsumer` + `WritingContext.author_voice` + writing-template
> adoption of `{{author_voice}}`) is a **cross-feature change** — it touches
> the writing pipeline, not just the analysis domain. It is **in scope for
> this spec** (CR-04: producer + generation consumer defined together), but
> the implementation cycle must sequence it after the Core types + repository
> land and must update every adopted writing template's `optional_variables`
> so the variable engine does not raise (RULE-11). See Definition of Done.

### Integration with the Generation Pipeline (CR-04 cross-feature coherence)

Generation reads `ProjectSettings.author_voice` via `AuthorVoiceConsumer`
(NEVER raw column access — the ADR-050 "no SSOT bypass" analogue), renders the
**descriptive group only** into `{{author_voice}}`, and the writing templates
shape new prose to match. The metric groups (`voice_analysis.voice_metrics` +
`author_metrics`) are excluded at the consumer boundary — this is the
author-voice analogue of ADR-055's `get_speech_data()` constraint and
ADR-057's checking-path boundary.

Because the producer (ANAL-007 write path), the generation consumer, and the
(future) drift consumer are defined together here, the cross-feature surface is
coherent end-to-end — the first generation consumer cannot accidentally render
metrics because the boundary is fixed at the `AuthorVoiceConsumer` contract.

### Integration with the Checking Pipeline (Phase 2B — ANAL-009 Phase 2)

Phase 2B (Author Voice Drift) will read `author_metrics` +
`voice_analysis.voice_metrics` via `AuthorVoiceRepository` (no raw column
access) and reuse the `voice_metric_distances` delta primitive (ADR-057/073)
applied to author-voice metrics. Both metric blocks are designed
delta-comparable (all `float | None` in `[0,1]`). Phase 2B re-computes
per-chapter metrics on the fly (like Phase 1) — it does **not** need
historical profiles, which is why v1 stores a single current profile (re-analysis
overwrites; no versioning — YAGNI).

### Foundation (reusable Core infrastructure)

| Component | Location | Status | Consumed by |
|-----------|----------|--------|-------------|
| `VoiceMetricsAnalyzer.analyze_text()` | `packages/core/narrare_core/analysis/voice_metrics.py` (ADR-021) | **EXTEND** (new prose-level entry point reusing `_compute_metrics`) | ANAL-007 (now); ANAL-009 Phase 2 (future) |
| `AuthorMetricsAnalyzer` | `packages/core/narrare_core/analysis/author_metrics.py` (NEW) | **NEW** (deterministic prose-level metrics) | ANAL-007 (now); ANAL-009 Phase 2 (future) |
| `DialogueParser` | `packages/core/narrare_core/analysis/dialogue_parser.py` | REUSE (quote-span extraction for `dialogue_ratio`) | ANAL-007 (now); ANAL-008, WRITE-010, ANAL-009 (existing) |
| `VoiceAnalysis` / `VoiceMetrics` (voice-generic) | extracted to a voice-generic Core home + re-exported from `kb/schemas/character.py` (ADR-074) | **EXTRACT + re-export** (backward-compat) | ANAL-007, ANAL-008, WRITE-010, ANAL-009 (all) |

These are infrastructure, not user-facing features — they do NOT get a
`docs/features/INDEX.md` entry; they are documented here (mirroring ANAL-008's
Foundation table).

## Phasing (Q6)

This spec is **Phase 2A — Author Voice Profiling** of the voice lane. It
complements the CHARACTER half (ANAL-008, built) and unblocks **Phase 2B —
Author Voice Drift** (ANAL-009 Phase 2).

| Phase | Feature | Status | Builds on |
|-------|---------|--------|-----------|
| Phase 1 | ANAL-009 Phase 1 — Character Voice Drift | ✅ built (ADR-073) | `voice_metric_distances` delta primitive |
| **Phase 2A** | **ANAL-007 — Author Voice Profiling (THIS SPEC)** | **planned** | ADR-074 storage; ANAL-008 hybrid pattern |
| Phase 2B | ANAL-009 Phase 2 — Author Voice Drift | deferred | THIS spec's `AuthorMetrics` + `voice_metric_distances`; its own ADR/spec |

> Phase 2B will reuse the Phase 1 `voice_drift_scoring` delta primitive
> (`trend_against_profile`, `detect_adjacent_jumps`) applied to author-voice
> metrics — which is why `AuthorMetrics` is designed delta-comparable here.

## Constraints & Edge Cases

### Minimum sample size

- Minimum **3 chapters** recommended for meaningful analysis.
- Minimum **10,000 words** total recommended.
- Below these thresholds the profile is low-confidence; the panel surfaces a
  soft warning (does not block — the user may proceed).

### Determinism (ADR-021)

`VoiceMetrics` + `AuthorMetrics` are deterministic (stable across runs and
minor edits). Only the qualitative descriptors (formality register, emotional
range, cultural markers, example curation) come from the LLM. This makes the
metrics suitable for Phase 2B drift comparison.

### Re-analysis overwrites (no versioning in v1)

Re-analysis overwrites the stored profile. There is no historical versioning in
v1 — YAGNI (Phase 2B drift re-computes per-chapter on the fly, like Phase 1; it
does not need historical profiles). The panel warns before overwrite.

### Descriptive/metric boundary (ADR-055/057/074 — binding)

- The `AuthorVoiceAgent` produces ONLY descriptive fields.
- The `AuthorVoiceConsumer` renders ONLY the descriptive group into
  `{{author_voice}}`.
- `voice_analysis.voice_metrics` and `author_metrics` NEVER reach generation
  (comparison-only for Phase 2B drift).
- This boundary is enforced structurally (distinct fields) and at the consumer
  contract (`render_for_generation` does not read metrics).

### RULE-11 graceful degradation

- No profiled chapters / NULL column → "no profile" (generation renders empty
  `{{author_voice}}`; drift skips). Never a crash or silent prompt regression.
- Malformed JSONB on read → `AuthorVoiceRepository.load()` returns `None`
  (Pydantic validation, RULE-11).
- LLM availability required for the qualitative profile; the deterministic
  metrics are computed regardless.

### Privacy

The profile is stored locally with the novel (`ProjectSettings.author_voice`);
it is project-scoped, never shared.

## Module Boundaries

| Layer | File Path | Responsibility |
|-------|-----------|----------------|
| Core | `packages/core/narrare_core/.../author_voice.py` | `AuthorVoiceProfile` + `AuthorMetrics` Pydantic models (ADR-074 data contract) |
| Core | `packages/core/narrare_core/agents/author_voice_agent.py` | `AuthorVoiceAgent` (NarrareAgent, structured output, ONE LLM call) |
| Core | `packages/core/narrare_core/agents/author_voice_types.py` | `AuthorVoiceOutput` + `AuthorVoiceDeps` |
| Core | `packages/core/narrare_core/analysis/voice_metrics.py` | **EXTEND** `VoiceMetricsAnalyzer.analyze_text()` (prose-level reuse) |
| Core | `packages/core/narrare_core/analysis/author_metrics.py` | **NEW** `AuthorMetricsAnalyzer` (deterministic prose-level metrics) |
| Core | `packages/core/narrare_core/profiles/contracts.py` | **EXTEND** `AuthorVoiceConsumer` Protocol |
| Core | `packages/core/narrare_core/profiles/_author_voice_render.py` | **NEW** descriptive-group renderer (parallel to `_voice_extraction._add_voice_analysis_parts`) |
| Core | `packages/core/narrare_core/prompts/_bundled/analysis/en/author_voice/system.md` | **NEW** governed EN template (Mode 1, ADR-054) |
| Core | `packages/core/narrare_core/prompts/route_table.py` | **EXTEND** add `author_voice` to VOICE `allowed_context_modes` |
| Core | `packages/core/narrare_core/prompts/variable_registry.py` | **EXTEND** register `author_voice` in `SYSTEM_VARS` |
| Core | `packages/core/narrare_core/writing/context_assembler.py` | **EXTEND** populate `WritingContext.author_voice` via `AuthorVoiceConsumer` |
| Backend | `apps/api/narrare/settings/models.py` | **EXTEND** `ProjectSettings.author_voice` JSONB column (ADR-074) |
| Backend | `apps/api/alembic/versions/<next>_author_voice_column.py` | **NEW** Alembic migration (RULE-14) |
| Backend | `apps/api/narrare/analysis/author_voice_repository.py` | **NEW** load/save/clear JSONB ↔ `AuthorVoiceProfile` (mirrors `adaptive/repository.py`) |
| Backend | `apps/api/narrare/analysis/author_voice_service.py` | **NEW** orchestration service (mirrors `character_voice_service.py`) |
| Backend | `apps/api/narrare/analysis/contracts_author_voice.py` | **NEW** `AuthorVoiceServiceProtocol` (RULE-03) |
| Backend | `apps/api/narrare/analysis/schemas_author_voice.py` | **NEW** SSE event + request/response models |
| Backend | `apps/api/narrare/analysis/author_voice_prompt.py` | **NEW** Mode-1 prompt resolution helper (mirrors `voice_drift_prompt.py`) |
| Backend | `apps/api/narrare/analysis/author_voice_agent_runner.py` | **NEW** agent runner helper (RULE-04 split) |
| Backend | `apps/api/narrare/analysis/router_author_voice.py` | **NEW** SSE endpoint (mirrors `router_character_voice.py`) |
| Backend | `apps/api/narrare/analysis/dependencies_author_voice.py` | **NEW** DI wiring (mirrors `dependencies_voice_drift.py`) |
| Frontend | `packages/web/components/analysis/author-voice-panel.tsx` | **NEW** panel (mirrors `CharacterVoicePanel`) |
| Frontend | `packages/web/hooks/use-author-voice.ts` | **NEW** `useAuthorVoice` hook (`useAIOperation`, ADR-043) |
| Frontend | `packages/web/lib/api/author-voice-stream.ts` | **NEW** SSE client (typed) |
| Frontend | `packages/i18n/messages/{en,de,fr}/analysis.json` | **EXTEND** i18n strings (RULE-16 parity) |
| Governance | `scripts/architecture/prompt-surface-manifest.yaml` | **EXTEND** `author_voice` context_mode + `author_voice` optional var on writing intents |
| Governance | `scripts/architecture/adoption-registry.yaml` | **EXTEND** `analysis/author_voice: true` + runtime marker |

## Contracts (Protocol Signatures)

`apps/api/narrare/analysis/contracts_author_voice.py` (RULE-03 — defined before
implementation):

```python
@runtime_checkable
class AuthorVoiceServiceProtocol(Protocol):
    """Author-voice profiling service (ANAL-007 / ADR-074).

    Orchestrates the hybrid pipeline (deterministic metrics + LLM qualitative
    profile) over a novel's selected chapters, persists the resulting
    AuthorVoiceProfile to ProjectSettings.author_voice, and streams SSE events."""
    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[AuthorVoiceStreamEvent]: ...

    async def get_profile(self, novel_id: UUID, user_id: UUID) -> AuthorVoiceProfile | None: ...

    async def clear_profile(self, novel_id: UUID, user_id: UUID) -> None: ...
```

## RULE-XX Compliance Matrix

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | The `AuthorVoiceAgent` is a `NarrareAgent` (subclass); models come from `ModelRegistry`. No direct `import openai` / no `pydantic_ai.Agent` outside `core/agents/`. |
| RULE-02/02a/02b | ✅ | The `author_voice` prompt is governed Mode 1 (`LLMIntent.VOICE` + `context_mode="author_voice"` + `_bundled/analysis/en/author_voice/system.md`). Resolution is exclusively in `core/prompts/` (PromptComposer); the service passes runtime prose + metrics as the agent run prompt (user channel, category-3). No inline f-strings, no app-layer loader, no system prompt in the user channel. |
| RULE-03 | ✅ | `AuthorVoiceServiceProtocol` (Backend) + `AuthorVoiceConsumer` (Core profiles) Protocols defined in this spec before implementation. `AuthorVoiceProfile` + `AuthorMetrics` contract fixed (ADR-074). |
| RULE-04 | ✅ | Service splits: `author_voice_service.py` + `author_voice_prompt.py` + `author_voice_agent_runner.py` + `author_voice_repository.py` (mirrors the character-voice / voice-drift split). Hard limits enforced by the same pattern. |
| RULE-05/06 | ✅ | Core owns the data contract (`AuthorVoiceProfile`, `AuthorMetrics`, `AuthorVoiceConsumer`); Backend owns the repository + migration + service. One responsibility per file. Voice-generic types extracted to a voice-generic home (not a character-specific file). |
| RULE-07 | ✅ | Dependency direction: `router → service → repository → ProjectSettings` (DB). Core data contract has no `apps/` imports. The extraction re-export preserves the existing acyclic `analysis → nlp`, `analysis → voice-types` read direction. |
| RULE-08 | ✅ | `AuthorMetricsAnalyzer` consumes `core/nlp/` primitives (spaCy POS) for `description_density`; `DialogueParser` for `dialogue_ratio`. No raw spaCy outside `core/nlp/`. |
| RULE-09 | ✅ | Full type annotations on `AuthorVoiceServiceProtocol`, `AuthorVoiceConsumer`, `AuthorVoiceProfile`, `AuthorMetrics`, `AuthorVoiceOutput`. No `Any` in public signatures. |
| RULE-10 | ✅ | Unit tests for `AuthorMetricsAnalyzer` + `AuthorVoiceAgent` (TestModel) + `AuthorVoiceRepository` (NULL→None, round-trip); integration tests for the SSE endpoint. Thresholds: core 90%, api 80%. |
| RULE-11 | ✅ | NULL column → "no profile" (generation renders empty `{{author_voice}}`; drift skips); malformed JSONB → `None`; no chapters → empty result, no LLM call (saves cost). Never a crash or silent prompt regression. |
| RULE-13 | ✅ | `AuthorVoiceService.analyze()` is an `AsyncIterator` (SSE stream) mirroring `CharacterVoiceService.analyze()`; the agent is a `NarrareAgent` (`run()` non-streaming structured output). The two-method contract is honoured at the layer where it applies. |
| RULE-14 | ✅ | The `ProjectSettings.author_voice` column lands with its Alembic migration (`<next>_author_voice_column.py`, mirrors `0033_adaptive_settings_column`) in the same task as the model change. A model change without a migration is a build failure. |
| RULE-16 | ✅ | UI i18n strings added with en/de/fr parity (`packages/i18n/messages/{en,de,fr}/analysis.json`). The bundled author-voice system prompt is EN-only; output language is controlled via `{{writing_language}}`. |
| RULE-17 | ✅ | Contract tests: a Backend fake `AuthorVoiceService` implementing `AuthorVoiceServiceProtocol`; a Core fake `AuthorVoiceConsumer` implementing the Protocol. No Mock-with-`# type: ignore[arg-type]`. |
| RULE-22 / CR-04 | ✅ | Cross-feature coherence: producer (ANAL-007 write) + generation consumer (`AuthorVoiceConsumer`) + future drift consumer defined together. The descriptive/metric boundary is fixed at the consumer contract before any consumer is built. `{{author_voice}}` registered in `SYSTEM_VARS`; manifest + adoption-registry updated. Voice-generic types are SSOT (one definition, re-exported). |

## Definition of Done

> This spec is `planned`. The following is the implementation-cycle DoD (per
> layer), sequenced for the next cycle after user approval.

### Core Layer
- [ ] Voice-generic `VoiceMetrics`/`VoiceAnalysis` extracted to a voice-generic home + re-exported from `kb/schemas/character.py` + `kb/schemas/__init__.py` (ADR-074 Retrofit-Plan step 1). Existing ANAL-008/WRITE-010/ANAL-009-Phase-1 tests stay green with zero import edits.
- [ ] `AuthorVoiceProfile` + `AuthorMetrics` Pydantic models (ADR-074 data contract).
- [ ] `VoiceMetricsAnalyzer.analyze_text()` prose-level entry point (reuses `_compute_metrics`).
- [ ] `AuthorMetricsAnalyzer` (deterministic prose-level metrics; `metaphor_density` = simile-cue proxy, provisional).
- [ ] `AuthorVoiceAgent` + `AuthorVoiceOutput` + `AuthorVoiceDeps` (NarrareAgent, structured output, ONE LLM call).
- [ ] `AuthorVoiceConsumer` Protocol + descriptive-group renderer.
- [ ] Governed EN template `_bundled/analysis/en/author_voice/system.md` (Mode 1).
- [ ] `route_table.py` + `variable_registry.py` (`author_voice` in VOICE modes + `SYSTEM_VARS`).
- [ ] `WritingContext.author_voice` field + assembler wiring.
- [ ] Unit tests: 3+ per public method; core coverage ≥ 90%.

### Backend Layer
- [ ] `ProjectSettings.author_voice` JSONB column + Alembic migration `<next>_author_voice_column.py` (RULE-14, same task) + schema round-trip test.
- [ ] `AuthorVoiceRepository` (load/save/clear; Pydantic validation on read; NULL→None).
- [ ] `AuthorVoiceService` + `author_voice_prompt.py` + `author_voice_agent_runner.py` (Mode-1 PromptComposer).
- [ ] `AuthorVoiceServiceProtocol` (contracts) + SSE schemas.
- [ ] `router_author_voice.py` SSE endpoint under `AI_ANALYSIS_LIMITER`.
- [ ] Integration tests for the SSE endpoint; contract test with a fake service.
- [ ] api coverage ≥ 80%.

### Frontend Layer
- [ ] `AuthorVoicePanel` (chapter multi-select, Analyze trigger, profile display, save/clear).
- [ ] `useAuthorVoice` hook (`useAIOperation`, ADR-043); AI Operation Inventory registration.
- [ ] Typed SSE client `author-voice-stream.ts`.
- [ ] i18n en/de/fr parity.
- [ ] UI tests for key interactions.

### Cross-Cutting / Governance
- [ ] `prompt-surface-manifest.yaml` updated (`author_voice` context_mode + `author_voice` optional var on writing intents).
- [ ] `adoption-registry.yaml` updated (`analysis/author_voice: true` + runtime marker).
- [ ] Writing templates adopted for `{{author_voice}}` (mirror `character_voice_profiles` coverage).
- [ ] `check_architecture.py` / prompt-governance checks green (RULE-14 + RULE-22 §4 variable registration).
- [ ] Runtime adoption probes (mirroring `voice_drift`) witnessing the committed markers.
- [ ] ADR-074 Review Trigger #1 satisfied (profiling writer uses repository; generation consumer renders descriptive-only; voice-generic extraction shipped with re-exports).

## Related Features

- [ADR-074](../../architecture/decisions/ADR-074-author-voice-storage.md) — Storage contract authority (Accepted).
- [ADR-055](../../architecture/decisions/ADR-055-character-voice-contract.md) — Character-voice storage + descriptive/metric boundary this spec preserves.
- [ADR-057](../../architecture/decisions/ADR-057-voice-check-checking-path-contract.md) — Checking-path boundary + `voice_metric_distances` delta primitive Phase 2B will reuse.
- [ADR-073](../../architecture/decisions/ADR-073-voice-drift-character.md) — Phase 2 Deferral this spec (+ ADR-074) resolves.
- [ANAL-008](ANAL-008-voice-character.md) — Character Voice Profiling (the sibling; structural pattern mirrored here).
- [ANAL-009](ANAL-009-voice-drift.md) — Voice Drift. **Phase 1 (Character)** built (ADR-073); **Phase 2 (Author)** builds on this spec.
- [WRITE-002](../writing/WRITE-002-new-chapter.md), [WRITE-003](../writing/WRITE-003-extend-chapter.md) — Generation consumers of the `{{author_voice}}` variable.
- [LEARN-002](../learning/LEARN-002-style-adaptation.md) — Adaptivity Dashboard (visibility + steering; author voice is a peer adaptive signal).

## Status & History

- `project-init` — Added to registry as planned feature (with the stale
  `{{author_style_examples}}` variable + a prose-level metric vocabulary that
  predated the live `VoiceAnalysis` contract).
- `2026-07-26` — **Spec rewritten against ADR-074 (Accepted).** Dropped the
  stale assumptions (no more "store in database" vagueness, no more unregistered
  `{{author_style_examples}}`). Concrete `ProjectSettings.author_voice` JSONB
  storage (ADR-074 Option 1) + `AuthorVoiceRepository` (mirrors
  `AdaptiveSettingsRepository`). Hybrid metrics (ADR-021) mirroring ANAL-008,
  with the prose-level measurement difference documented
  (`VoiceMetricsAnalyzer.analyze_text()` reuses `_compute_metrics`; new
  `AuthorMetricsAnalyzer` for prose-level metrics). Key design decisions:
  `metaphor_density` = deterministic simile-cue proxy (preserves ADR-021 +
  the descriptive/metric boundary; agent produces descriptive-only); new
  `{{author_voice}}` variable (NOT repurposing `author_style_examples`);
  `AuthorVoiceConsumer` parallels `VoiceProfileConsumer`. Phasing documented
  (Phase 2A; Phase 2B drift builds on it). Status remains `planned`
  (implementation is the next cycle, pending user approval of this spec).
