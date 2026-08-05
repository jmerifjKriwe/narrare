# ADR-074 — Author Voice Storage Contract (ANAL-007 / ANAL-009 Phase 2 enabler)

> **Status:** ✅ Implemented (implemented 2026-07-26 across all layers + runtime-adopted; commit range c4c29867→ceab228c. Originally Accepted 2026-07-26 — user approved by directing the coordinator to proceed to the ANAL-007 spec rewrite.)
> **Date:** 2026-07-26
> **Deciders:** Architecture Specialist; User (approved Option 1 after brainstorming four options)
> **Supersedes:** —
> **Related:**
> ADR-021 (deterministic analysis — pre-names `voice_metrics.py`),
> ADR-040 (`core/profiles/` SSOT),
> ADR-050 (cross-feature context contracts),
> ADR-055 (character-voice storage contract — the structural parallel this ADR mirrors + the descriptive/metric boundary this ADR preserves + Review Trigger #3 this ADR closes),
> ADR-057 (voice-check checking-path contract — metrics never reach generation),
> ADR-069 (AdaptiveSettings as nested JSONB on `ProjectSettings` — THE persistence pattern this ADR mirrors verbatim),
> ADR-073 (Character Voice Drift — **Phase 2 Deferral this ADR unblocks**),
> CONSTRAINTS.md RULE-02/02b/03/04/05/06/07/11/14/22,
> CR-04 (cross-feature coherence)

> **Scope of this ADR:** the author-voice **storage contract only** — where
> author-voice data lives, in what shape, with what descriptive/metric boundary,
> and what migration lands it. The analysis pipeline (the `AuthorVoiceAgent`,
> the deterministic analyzer, the SSE router), the prompt-surface wiring
> (`{{author_voice}}` or repurposing `{{author_style_examples}}`), and the
> ANAL-009 Phase 2 drift consumer are **downstream ANAL-007 / Phase 2 work**,
> flagged here but not designed here. This ADR defines the storage; the
> consumers follow.

---

## Context

### Why this ADR exists

ADR-073 delivered ANAL-009 **Phase 1** (Character Voice Drift) but **explicitly
deferred Phase 2** (Author Voice: storage SSOT + profiling + drift) with a
recorded blocking open question:

> *"where do author-voice metrics live? Candidate homes — User-Settings,
> Project-Settings, or a new `AuthorVoiceProfile` model — are unresolved."*
> — ADR-073 §Phase 2 Deferral

ANAL-007 (Author Voice Profiling) is the prerequisite for Phase 2 and is **also**
blocked on the same question — it cannot write a profile until the profile has a
home. ADR-055 anticipated this and carried it as Review Trigger #3:

> *"When ANAL-007 (Author Voice) is implemented — add the `author_voice`
> context_mode to the VOICE route; resolve author-voice storage (separate ADR —
> out of scope here)."*

**This is that separate ADR.** It closes the storage question that blocks both
ANAL-007 and ANAL-009 Phase 2. The user brainstormed four storage options and
approved Option 1 (novel-scoped `ProjectSettings.author_voice` JSONB, mirroring
AdaptiveSettings). This ADR records that decision with honest rationale, the
grounded facts behind it, and the data contract it implies.

### Verified state (grounded, not assumed — per architectural-discipline §7)

| Concern | State | Location |
|---------|-------|----------|
| `ProjectSettings` model | EXISTS — **structured columns + dedicated JSONB columns** (NOT a single flexible blob). Columns: `autosave_interval`, `default_language`, `ai_provider`, `ai_model`, `category_overrides` (JSONB), `intent_overrides` (JSONB), `token_limit_overrides` (JSONB), `token_limit_profile`, `adaptive_settings` (JSONB, nullable). | `apps/api/narrare/settings/models.py:31-63` |
| `adaptive_settings` JSONB column | EXISTS — a **dedicated nullable JSONB column** added by Alembic migration `0033_adaptive_settings_column` (ADR-069 Decision 2). Read/written by `AdaptiveSettingsRepository`. | `apps/api/narrare/settings/models.py:60`, `apps/api/narrare/adaptive/repository.py` |
| `AdaptiveSettingsRepository` pattern | EXISTS — load/save helper mapping a Core Pydantic type ↔ `ProjectSettings.<col>` JSONB; Pydantic validation on read. THE pattern this ADR mirrors. | `apps/api/narrare/adaptive/repository.py` |
| `VoiceMetrics` (deterministic metric block) | EXISTS — `avg_sentence_length`, `sentence_length_std`, `type_token_ratio`, `avg_syllables_per_word`, `contraction_rate`, `verbal_tic_frequency`, `punctuation_profile`. `ConfigDict(extra="allow")`. **Voice-GENERIC** (pure measurement; docstring says "character" only because ANAL-008 was first consumer). | `packages/core/narrare_core/kb/schemas/character.py:54-70` |
| `VoiceAnalysis` (descriptive + metric) | EXISTS — descriptive (`formality`, `vocabulary_level`, `sentence_profile`, `emotional_range`, `cultural_regional_markers`, `voice_examples`) + nested `voice_metrics: VoiceMetrics \| None`. `ConfigDict(extra="allow")`. **Voice-GENERIC.** | `packages/core/narrare_core/kb/schemas/character.py:73-92` |
| Voice-types import surface | `VoiceMetrics`/`VoiceAnalysis` imported across ~15 modules (Backend analysis services, contracts, schemas, KB writer, agent runners, drift/check helpers, Core analyzer tests). Exported from `kb/schemas/__init__.py`. Frontend has **separate TS mirrors** (unaffected by a Python move). | see `grep VoiceMetrics|VoiceAnalysis` |
| `VoiceMetricsAnalyzer` (deterministic) | EXISTS — reusable Foundation analyzer (ADR-021/055); produces `dict[str, VoiceMetrics]` per speaker. | `packages/core/narrare_core/analysis/voice_metrics.py` |
| `{{author_style_examples}}` prompt variable | **Aspirational only** — appears nowhere except the stale ANAL-007 spec; NOT registered, NOT wired into generation (ADR-055 §Verified state). | `docs/features/analysis/ANAL-007-voice-author.md:141` |
| ANAL-007 spec field list | **STALE** — predates the live `VoiceAnalysis` contract (same root cause as the lossy ANAL-008 mapping ADR-055 rejected). Its `AuthorVoiceProfile` shape (`dialogue_ratio`, `metaphor_density`, `description_density`, `action_introspection_ratio`) is a different, prose-level vocabulary that must be reconciled at ANAL-007 implementation, not trusted as-is. | `docs/features/analysis/ANAL-007-voice-author.md:117-126` |
| `Volume` model | EXISTS — `novel_id ForeignKey("novels.id", ondelete="CASCADE")`. Volume is a **child of Novel**, grouping chapters WITHIN one novel. **NOT a series.** | `apps/api/narrare/volumes/models.py:19` |
| ADR count | ADR-073 is the latest; **next free is ADR-074**. | `docs/architecture/decisions/INDEX.md` |

### Root cause (why a storage decision is needed before profiling)

1. *Why is ANAL-007 blocked?* It needs to **write** an author-voice profile somewhere persistent, and ANAL-009 Phase 2 needs to **read** it for drift. There is currently no home.
2. *Why can't it reuse the character-voice home (`speech.voice_analysis` in KB)?* Author voice is **not a property of a KB character entity** — it is a property of the novel's prose as a whole. Stuffing it into a KB character's `speech` block would be the same kind of semantic corruption ADR-055 rejected (the lossy "map to SpeechPatterns" mapping). The storage home must match the data's actual scope: **the novel**.
3. *Why is this an architecture decision rather than an implementation choice?* Because (a) it adds a `ProjectSettings` column + Alembic migration (RULE-14 — a model change without a migration is a build failure); (b) it determines the data contract every downstream consumer (profiling writer, generation injector, Phase 2 drift checker) reads, so the contract must be fixed before any of them is built (RULE-03); and (c) the descriptive/metric boundary from ADR-055/057 must be **preserved** for author voice too, or the "metrics never reach generation" rule gets a hole punched in it.

### Volume ≠ Series (verified finding — documented definitively)

A genuine ambiguity in the codebase deserves a definitive answer here, because
"where does author voice live" cannot be answered without knowing what a novel's
containment structure actually is.

**Narrare has NO series / Reihe concept today. Each novel is an isolated unit
with its own Knowledge Base.** Evidence:

- **`apps/api/narrare/volumes/models.py:19`** —
  `novel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), ...)`.
  `Volume` is a child of `Novel`. A volume groups chapters **within one novel**.
- **`docs/features/writing/WRITE-011-volume-management.md`** — the spec is
  explicit: *"Organize your novel into volumes"*, *"a hierarchical structure
  **within a single novel**"*, *"Knowledge Base: Shared across all volumes"*
  (they share because they are all in one novel). The spec's mention of
  "trilogies" / "series of arcs" is a **use-case hint** (why a user might create
  volumes), **not** a data-model statement that a Volume spans novels.

`Volume ≠ Series`. A Volume is intra-novel chapter grouping; a Series would be
inter-novel grouping (a `Series` entity with `Novel.series_id`), which **does not
exist**. This distinction is load-bearing for this ADR: it is the factual basis
for scoping author voice at the **novel** level (one profile per novel), not at a
series level (which has no data model to attach to).

### Series / Reihe is the NEXT major platform-level feature (user decision)

The user has decided that **Series / Reihe** is the next major platform-level
feature after Author Voice. It is foundational because it affects nearly every
subsystem:

| Subsystem | Series impact |
|-----------|---------------|
| Data model | New `Series` entity + `Novel.series_id` FK; a novel may belong to a series or stand alone. |
| Knowledge Base | Per-series shared KB vs per-novel KB (or cross-referenced); today each novel's KB is isolated. |
| Dashboard / navigation | Series-level views alongside novel-level views. |
| Generation context | Context assembly may draw on sibling novels in the series. |
| Voice | **Series base voice + per-novel nuances** — exactly the cascade this ADR deliberately does NOT pre-build (see Forward-compatibility). |
| Cross-novel analysis | Consistency, timeline, and drift across novels in a series. |
| Export | Series-level manuscript / series bible export. |

This ADR records that decision so it is **discoverable, not implicit**. It is
documented as *next*, not as *done* — Series/Reihe has no code, no model, no spec
today. The forward-compatibility analysis below explains how this ADR's decision
fits the future Series feature without pre-committing to it.

---

## Decision Drivers

- **RULE-03** — The storage contract + the reused type contract MUST exist before
  the profiling writer or any consumer is built.
- **RULE-04/06** — Modularise; one responsibility per file. The author-voice
  storage type ≠ the analysis agent ≠ the repository ≠ the service.
- **RULE-05/07** — Core owns the Pydantic data contract; Backend owns the
  repository + migration; no `core/`→`apps/` imports; no `apps/`→`core` cycle.
- **RULE-11** — A novel with no profiled chapters / no stored profile degrades
  gracefully (NULL column → "no profile"), never a crash or silent prompt regression.
- **RULE-14** — Adding a `ProjectSettings.author_voice` column REQUIRES an Alembic
  migration in the same task as the model change (a model change without a
  migration is a build failure — this is the bug that motivated RULE-14).
- **RULE-22 / CR-04** — Author voice is shared data (read by generation, by a
  future Phase 2 drift checker, by the dashboard). The producer + consumers must
  be coherent end-to-end, not feature-local.
- **ADR-055/057** — The descriptive/metric boundary ("metrics NEVER reach
  generation") established for character voice MUST be preserved for author voice.
- **ADR-069** — `AdaptiveSettings` on `ProjectSettings` JSONB is THE established
  home for per-novel structured AI-behavior data; this ADR mirrors it for
  consistency (RULE-22 coherence).
- **architectural-discipline §1/§4/§5/§7** — Root-cause solution; no workarounds;
  sustainability check; "documented ≠ implemented" (the migration + repository +
  type must actually land at implementation, the ADR only specifies them).

---

## Options Considered

### Option 1 — `ProjectSettings.author_voice` JSONB nested sub-model, novel-scoped (CHOSEN)

Add ONE nullable JSONB column `author_voice` to `ProjectSettings`, mirroring
`adaptive_settings` (ADR-069 Decision 2) exactly. Store a Core `AuthorVoiceProfile`
Pydantic model serialised as JSON; deserialise + validate on read. A small
`AuthorVoiceRepository` (mirroring `AdaptiveSettingsRepository`) handles the
(de)serialisation. **Novel-scoped**: one profile per novel.

**Pros:**
- **Right-sized for the feature.** ANAL-007 profiles a novel's voice *from its
  chapters*; ANAL-009 Phase 2 detects drift *within a novel*. Both are
  novel-scoped. A novel-level home matches the data's actual scope.
- **Pattern-consistent.** `AdaptiveSettings` is the established home for
  per-novel structured AI-behavior data on `ProjectSettings` JSONB. Mirroring it
  keeps one coherent pattern (RULE-22) instead of introducing a parallel one.
- **Forward-compatible with Series** without being forward-committed (see below).
- **Mirrors a proven, tested pattern** (`AdaptiveSettingsRepository` + migration
  `0033`) — the implementation path is known and low-risk.

**Cons:**
- Requires one Alembic migration (RULE-14) — accepted; this is the standard cost
  of any `ProjectSettings` column and was paid by `adaptive_settings` too.
- JSONB is weakly typed at the DB level — mitigated by Pydantic validation on read
  (same mitigation ADR-069 accepted).

### Option 2 — Dedicated `author_voice_profiles` table with scope discrimination (`scope ∈ {user, novel, [future] series}`)

A purpose-built table that could model an author → series → novel cascade with
fallback resolution (a standalone novel falls back to the author's "base voice").

**Rejected** for two honest reasons:

1. **Over-engineering for speculative levels.** The feature needs **novel-level
   only**. Author-base voice and series voice are YAGNI until they are real
   features — they have no consumer, no UI, no spec. Building a scope-discriminated
   cascade table now is speculative infrastructure for levels that may never ship
   in this shape.

2. **Cascade fallback could be actively harmful.** A standalone novel written in a
   deliberately different voice (the user's explicit domain observation: standalones
   vary, series share voice) would fall back to the author's "base voice" and
   inject the author's *usual* patterns into an experimental book — the opposite of
   what the writer wants. The user's observation that "standalones vary, series
   share voice" actually points **at novel-level as the primary scope**, not at a
   cascade.

> **Note on the "best, not easiest" framing.** The user explicitly asked for the
> BEST solution, not the easiest. This rejection is **not** laziness or
> effort-avoidance — the AI implements either option at the same cost. It is a
> **proportionality / YAGNI** rejection: "best" here means *right-sized to the
> actual feature scope*, not *maximally general*. A cascade table is the
> architecturally correct answer to a *different* question (the Series feature,
> see Forward-compatibility) — not to "where does a single novel's author-voice
> profile live". Building it now would couple the Author Voice feature to a
> Series data model that does not exist yet.

### Option 3 — Promote `ProjectWritingProfile` to a persisted SSOT (resolves the SET-006 deferral)

Make the in-memory `ProjectWritingProfile` (ADR-040) the persisted SSOT and hang
author voice off it.

**Rejected — wrong problem.** SET-006's SSOT promotion is a separate concern with
a high blast radius (every consumer of the in-memory `ProjectWritingProfile`).
Crucially, it does **not** model voice any better than Option 1 — it is still
project-scoped, so it solves the same scope problem with more coupling. ANAL-007
should not absorb SET-006's scope. (This mirrors ADR-069 Decision 2's rejection of
extending `ProjectWritingProfile` for a related reason — RULE-06: stuffing
unrelated concerns into a value object.)

### Option 4 — User-Settings (author voice as a user-level preference)

Store author voice on `UserSettings` — "this user's voice".

**Rejected — semantically too coarse.** It ignores the deliberate per-novel
variation the user emphasised (standalones in different voices, different series
in different voices). It forces all of a user's novels into one voice mould,
which is precisely the failure mode the user flagged. Author voice is a property
of *a novel's prose*, not of *a user's identity*.

---

## Decision

**Option 1.** Author-voice data lives as a nested `author_voice` sub-model inside
`ProjectSettings`, persisted as a **dedicated nullable JSONB column**
(`author_voice`), mirroring the `adaptive_settings` pattern (ADR-069 Decision 2)
exactly. It is **novel-scoped** (one profile per novel, keyed by
`ProjectSettings.novel_id`).

---

## Rationale

`adaptive_settings` (ADR-069) already established that per-novel structured
AI-behavior data lives as a dedicated JSONB column on `ProjectSettings`, with a
small repository handling (de)serialisation and Pydantic validating shape on read.
Author voice is the same kind of data — per-novel, structured, AI-behavior-shaped
— so the architecturally coherent choice is to **mirror that pattern**, not invent
a parallel one. RULE-22 (cross-feature coherence) is satisfied by pattern
consistency: a future maintainer reading `ProjectSettings` sees a uniform
"per-novel structured-AI-data as JSONB" convention (`adaptive_settings`,
`author_voice`, …) instead of a mix of columns + tables.

Novel-scoping is correct because **the Volume ≠ Series finding proves novels are
the largest isolation boundary that exists today.** Author voice is measured from
a novel's chapters and is meaningful per-novel; there is no series entity to attach
a series-level voice to. Option 2's cascade is the right shape *for the Series
feature*, not for this feature — and pre-building it would couple Author Voice to
a data model that does not exist (architectural-discipline §4: no workarounds, no
speculative coupling).

### Sustainability check

1. **Correct in 3 months?** Yes — the profile is per-novel, which matches both
   ANAL-007 (profile a novel) and ANAL-009 Phase 2 (drift within a novel). The
   Series feature adds a *sibling* home (SeriesSettings JSONB), not a replacement.
2. **Hard-to-undo coupling?** None — one nullable column, one Alembic migration
   with a downgrade (mirrors `0033_adaptive_settings_column`). NULL = no profile
   yet → graceful degradation.
3. **Simplest correct solution?** Yes — reuses the proven `adaptive_settings`
   pattern; no new table, no cascade, no scope discrimination. "Simplest correct"
   ≠ "simplest possible" — a flat user-level blob would be simpler but wrong
   (Option 4).
4. **Design intent clear?** Yes — `ProjectSettings.author_voice` is analogous to
   `ProjectSettings.adaptive_settings`; the column name documents the
   responsibility.

### Forward-compatibility with the future Series feature (compatible, not committed)

Option 1 is forward-**compatible** with Series/Reihe without being
forward-**committed** to any particular blend model:

- **Compatible:** when Series lands, a *series-level* voice is an **additive**
  `SeriesSettings.author_voice` JSONB column on a new `Series` entity — a sibling
  home, not a replacement for the novel-level one. The resolution consumer (which
  voice does generation use?) extends naturally: today it reads
  `ProjectSettings.author_voice`; post-Series it MAY also read
  `SeriesSettings.author_voice`. No migration of existing novel-level data is
  required.
- **Not committed:** the **blend / delta resolution model** — "novel voice is a
  nuance on a series base" vs "novel voice overrides series voice" vs "weighted
  blend" — is a **design question for the Series feature**, NOT pre-decided here.
  YAGNI applies: do not pre-build the cascade or the resolution policy. (This is
  exactly why Option 2 is rejected now but recorded as the right shape for Series.)

---

## Data Contract

### Persistence shape

A new nullable JSONB column on `ProjectSettings`, mirroring `adaptive_settings`:

```python
# apps/api/narrare/settings/models.py  (ProjectSettings)
# ADR-074: per-novel author-voice profile (ANAL-007 writes; ANAL-009 Phase 2 +
# generation read). JSONB mirrors the adaptive_settings pattern (ADR-069 D2).
# NULL = no profile yet → consumers degrade gracefully (RULE-11).
author_voice: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
```

A `AuthorVoiceRepository` (in the analysis or settings Backend domain —
implementation decision) mirrors `AdaptiveSettingsRepository`: load/save the
column, map between the JSON payload and the Core `AuthorVoiceProfile` Pydantic
model, validate on read.

### Core data model — `AuthorVoiceProfile`

Author voice is **structurally the same shape as character voice** (ADR-055):
deterministic metrics + LLM qualitative descriptors. The contract therefore
**reuses the voice-generic types** and adds author-specific fields.

#### Type-reuse decision — REUSE (extract `VoiceMetrics` + `VoiceAnalysis` to a voice-generic home)

**Decision: reuse.** `VoiceMetrics` (pure measurement: `avg_sentence_length`,
`type_token_ratio`, `contraction_rate`, …) and `VoiceAnalysis` (voice-generic
descriptive: `formality`, `vocabulary_level`, `sentence_profile`,
`emotional_range`, `cultural_regional_markers`, `voice_examples`) are
**voice-GENERIC**, not character-specific. They live in
`core/kb/schemas/character.py` only as an artifact of ANAL-008 being the first
consumer. Author voice needs the same measurement vocabulary.

**Extraction mechanics (downstream Core work, not this ADR):**
- Extract `VoiceMetrics` + `VoiceAnalysis` to a **voice-generic Core location**
  (natural candidates: a new lightweight `core/voice/` domain, colocation with the
  analyzer under `core/analysis/`, or a neutral schema module — the exact path is
  a Core-implementation decision guided by the principle *voice-generic types do
  not belong in a character-specific file*).
- **Re-export them from `core/kb/schemas/character.py` and `core/kb/schemas/__init__.py`**
  for backward compatibility. Every existing import
  (`from narrare_core.kb.schemas.character import VoiceMetrics, VoiceAnalysis`)
  continues to resolve unchanged → **ANAL-008 / WRITE-010 / ANAL-009 Phase 1 stay
  green with zero edits**. This is the SSOT-correct move (RULE-22): one definition,
  two homes (canonical + backward-compat re-export), no duplication.

**Blast-radius assessment (verified via `grep`):** the types are imported across
~15 modules (Backend analysis services, contracts, schemas, KB writer, agent
runners, drift/check helpers, Core analyzer tests). **All of them import from
`narrare_core.kb.schemas.character` (or the package `__init__`)**, so a re-export
keeps every one working. The frontend has **separate TypeScript mirrors**
(`packages/web/lib/api/character-voice-stream.ts`) that are unaffected by a Python
move. Net: the extraction is a pure move + re-export, low-risk, fully covered by
existing tests.

**Why not duplicate (define a parallel `AuthorVoiceAnalysis`/`AuthorVoiceMetrics`)?**
Duplication would create two sources of truth for the same measurement vocabulary
(avg_sentence_length, type_token_ratio, formality, …), which would drift the
moment one consumer needs a new field — exactly the failure RULE-22 exists to
prevent. The types ARE voice-generic; the extraction is the root-cause-correct
SSOT move.

#### The `AuthorVoiceProfile` model (structural contract)

```python
# packages/core/narrare_core/.../author_voice.py  (Core — exact path is impl. decision)
class AuthorMetrics(BaseModel):
    """Author-specific PROSE-LEVEL metrics — comparison ONLY (ANAL-009 Phase 2
    author drift). NEVER rendered into generation. ``extra="allow"`` lets the
    metric block grow without a migration."""
    model_config = ConfigDict(extra="allow")
    dialogue_ratio: float | None = None                 # 0.0–1.0
    description_density: float | None = None            # 0.0–1.0 sparse..rich
    action_introspection_ratio: float | None = None     # 0.0–1.0 action..introspection
    metaphor_density: float | None = None               # 0.0–1.0

class AuthorVoiceProfile(BaseModel):
    """Machine-derived author-voice profile (ANAL-007 / ADR-074).

    Persisted as ``ProjectSettings.author_voice`` JSONB. Novel-scoped.
    Mirrors the ADR-055 descriptive/metric structure (deterministic metrics +
    LLM qualitative descriptors), REUSING the voice-generic ``VoiceAnalysis`` /
    ``VoiceMetrics`` and ADDING author-specific prose-level metrics.
    """
    model_config = ConfigDict(extra="allow")

    # --- Descriptive group (rendered into generation) ---
    # REUSED voice-generic descriptive block (formality, vocabulary_level,
    # sentence_profile, emotional_range, cultural_regional_markers, voice_examples).
    voice_analysis: VoiceAnalysis | None = None
    # Author-specific curated representative prose passages.
    author_examples: list[str] | None = None

    # --- Metric group (comparison ONLY — NEVER rendered into generation) ---
    # Author-specific prose-level metrics (dialogue_ratio, description_density,
    # action_introspection_ratio, metaphor_density).
    author_metrics: AuthorMetrics | None = None
    # NOTE: voice_analysis.voice_metrics carries the voice-GENERIC metrics
    # (avg_sentence_length, type_token_ratio, ...) — also comparison-only.
```

> **Field-list caveat (honest):** the `AuthorMetrics` field list above reconciles
> the stale ANAL-007 spec's prose-level vocabulary with the live measurement
> contract. The **exact** set of author-specific metrics is a downstream
> ANAL-007 decision informed by the analysis pipeline design (which deterministic
> signals the analyzer computes). The **structural contract is fixed here**: one
> reused descriptive block + author-specific examples + author-specific metrics,
> with `extra="allow"` so the metric block grows without a migration. ADR-055
> took the same approach (fixed the structure, deferred the exact metric tuning).

### Descriptive / metric boundary (preserves ADR-055 / ADR-057)

ADR-055 established, and ADR-057 hardened, that **metrics NEVER reach generation**
— only descriptive fields render into prompts. Author voice **preserves this
boundary**:

| Group | Fields | Reaches generation? |
|-------|--------|---------------------|
| Descriptive (voice-generic) | `voice_analysis.{formality, vocabulary_level, sentence_profile, emotional_range, cultural_regional_markers, voice_examples}` | ✅ YES — rendered into the author-voice prompt variable |
| Descriptive (author-specific) | `author_examples` | ✅ YES — rendered into the author-voice prompt variable |
| Metric (voice-generic) | `voice_analysis.voice_metrics` | ❌ NO — comparison only (ANAL-009 Phase 2 drift) |
| Metric (author-specific) | `author_metrics` | ❌ NO — comparison only (ANAL-009 Phase 2 drift) |

**Constraint introduced (binding on downstream ANAL-007):** the author-voice
**generation consumer** renders the descriptive group (`voice_analysis`
descriptive fields + `author_examples`) into a prompt variable, and **MUST NOT**
render `voice_analysis.voice_metrics` or `author_metrics`. Generation uses
descriptors; drift/checking uses metrics. This is the author-voice analogue of
ADR-055's `get_speech_data()` constraint and ADR-057's checking-path boundary.

---

## Consequences

**Positive:**
- **Unblocks ANAL-007 and ANAL-009 Phase 2.** The storage question that ADR-073's
  Phase 2 Deferral and ADR-055 Review Trigger #3 both flagged is now answered.
- **One coherent per-novel structured-data pattern** on `ProjectSettings` JSONB
  (`adaptive_settings`, `author_voice`, …) — RULE-22 coherence.
- **DRY measurement vocabulary.** Voice-generic types are defined once and shared
  by character voice (KB), author voice (ProjectSettings), and the future series
  voice — no parallel `AuthorVoiceMetrics` to drift.
- **Migration is additive + nullable** → backward compatible (existing novels have
  NULL → "no profile" → graceful degradation).
- **Forward-compatible with Series** (sibling `SeriesSettings.author_voice` later)
  without pre-committing to a blend model.

**Negative / Tradeoffs:**
- One Alembic migration (RULE-14) — accepted, standard cost, mirrors `0033`.
- The voice-generic type extraction touches stable ANAL-008 code paths —
  **mitigated by backward-compat re-exports** (every existing import resolves
  unchanged; existing tests stay green).
- The author-voice **prompt-surface wiring** (`{{author_voice}}` new vs repurposing
  `{{author_style_examples}}`) is NOT resolved here — it is downstream ANAL-007
  work (see Retrofit-Plan §"Out of scope").

**Constraints introduced:**
- The author-voice generation consumer MUST render only the descriptive group,
  never the metric groups (descriptive/metric boundary above).
- ANAL-007 MUST obtain the profile via the repository (not raw column access), so
  Pydantic validation on read is enforced uniformly.
- ANAL-009 Phase 2 (author drift) MUST read `author_metrics` +
  `voice_analysis.voice_metrics` via the same repository contract — never via raw
  `ProjectSettings.author_voice` JSON access (the analogue of ADR-050's "no SSOT
  bypass").

---

## CR-04 Cross-Feature Impact (coherence)

Author voice is **shared data**: written by ANAL-007, read by generation, and (in
Phase 2) read by the author-drift checker. This ADR requires coherence
end-to-end, not feature-local:

- **Producer (ANAL-007 write path) — future.** Writes `ProjectSettings.author_voice`
  (descriptive + metric groups) via `AuthorVoiceRepository`.
- **Consumer (generation read path) — future.** Renders the **descriptive group
  only** into the author-voice prompt variable. The metric groups are excluded
  (boundary above). This is the author-voice analogue of ADR-055's
  `get_speech_data()` extension.
- **Consumer (drift read path) — future (Phase 2).** Reads `author_metrics` +
  `voice_analysis.voice_metrics` via the repository contract for longitudinal
  comparison (reusing the `voice_metric_distances` primitive ADR-057/073
  established), never via raw column access.

This is the CR-04 lesson (architectural-discipline §7): producer + generation
consumer + drift consumer are defined together. Because author voice is a **new**
data source (no existing consumer to break), the cross-feature surface is additive
— but the boundary constraint (descriptive into generation, metrics into
checking) is fixed **here**, before any consumer is built, so the first consumer
cannot accidentally render metrics.

---

## Retrofit-Plan

> **Scope note.** This ADR defines **storage only**. It does NOT itself change
> prompt mechanics (no new `LLMIntent`, no new route, no new template variable is
> introduced *by this ADR*). The storage migration is therefore the Retrofit-Plan
> focus. The **prompt-surface wiring** (which template slots, which route, which
> variable) is downstream ANAL-007 work and will require its own prompt-mechanics
> Retrofit-Plan (per adr-process §D.4) when it lands — flagged in §"Out of scope".

### 1. Inventory of affected paths (storage migration)

- `apps/api/narrare/settings/models.py` — ADD
  `author_voice: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)`
  to `ProjectSettings` (mirrors line 60 `adaptive_settings`).
- `apps/api/alembic/versions/<next>_author_voice_column.py` — NEW Alembic migration:
  add nullable `author_voice` JSONB column to `project_settings` (mirrors
  `0033_adaptive_settings_column` exactly, including a working `downgrade()`).
  The revision id is the next sequential Alembic revision at implementation time
  (not pinned here — other work may land migrations first).
- `apps/api/narrare/{analysis|settings}/author_voice_repository.py` — NEW
  repository mirroring `AdaptiveSettingsRepository`: `load(novel_id)`,
  `save(novel_id, profile)`, mapping JSON ↔ Core `AuthorVoiceProfile`, Pydantic
  validation on read.
- `packages/core/narrare_core/.../author_voice.py` — NEW Core module: the
  `AuthorVoiceProfile` + `AuthorMetrics` Pydantic models (contract above).
- `packages/core/narrare_core/.../voice.py` (or chosen voice-generic home) —
  EXTRACT `VoiceMetrics` + `VoiceAnalysis` here; **re-export** from
  `packages/core/narrare_core/kb/schemas/character.py` and
  `packages/core/narrare_core/kb/schemas/__init__.py` (backward compat).

### 2. Migration steps per path (atomic, independently testable)

1. **Extract voice-generic types** (pure move + re-export): move
   `VoiceMetrics` + `VoiceAnalysis` to the voice-generic home; add re-exports in
   `kb/schemas/character.py` + `__init__.py`. Verify the full existing
   voice test suite (ANAL-008 / WRITE-010 / ANAL-009 Phase 1) stays green with
   **zero** import edits. (This step is independently shippable and could land
   before the rest.)
2. **Add the Core `AuthorVoiceProfile` + `AuthorMetrics` models** (pure schema;
   unit-test round-trip + `None` default).
3. **Add the `ProjectSettings.author_voice` column + Alembic migration**
   (mirror `0033`); schema round-trip regression test
   (`test_project_settings_has_author_voice_column`, mirroring the adaptive test).
4. **Add the `AuthorVoiceRepository`** (mirror `AdaptiveSettingsRepository`;
   unit-test load/save + graceful NULL → "no profile").

### 3. Breaking-change assessment

- **Schema change is additive + nullable** → backward compatible. Existing novels
  have NULL `author_voice` → consumers degrade gracefully ("no profile").
- **Voice-generic type extraction is non-breaking** via re-exports: every existing
  `from narrare_core.kb.schemas.character import VoiceMetrics, VoiceAnalysis`
  continues to resolve. No ANAL-008/WRITE-010/ANAL-009-Phase-1 edit required.
- **No production caller yet** — ANAL-007 (the first writer) is downstream. So no
  caller breaks when the column lands.

**Net: fully backward compatible (additive + re-exports only).**

### 4. Checker (governance) update plan

- `check_architecture.py` — no new rule; RULE-14 (migration with model change) is
  already enforced. Verify the migration lands in the same task as the model
  column (the existing integration-test pattern catches a missing migration).
- No prompt-surface manifest / adoption-registry changes from THIS ADR (storage
  only). Those land with the downstream ANAL-007 prompt-surface work.

### 5. Test update plan

- **Type-extraction regression:** run the existing voice test suites (Core
  `test_voice_metrics.py`, Backend analysis voice tests, ANAL-009 Phase 1 drift
  tests) unchanged — they must stay green, proving the re-exports work.
- **Schema round-trip test:** assert `project_settings.author_voice` column exists
  post-migration (mirror `test_project_settings_has_adaptive_settings_column`).
- **Repository tests:** load/save round-trip; NULL → "no profile" graceful path;
  Pydantic validation rejects malformed JSON on read.
- **`AuthorVoiceProfile` unit tests:** round-trip serialisation; descriptive/metric
  boundary is structural (the two metric groups are distinct fields).

### Out of scope (downstream ANAL-007 / Phase 2 — flagged, not designed here)

- **The `AuthorVoiceAgent`** + deterministic analyzer pipeline (ANAL-007 Core).
- **The author-voice prompt-surface wiring** — deciding between a new
  `{{author_voice}}` variable vs repurposing the unregistered `{{author_style_examples}}`,
  registering it (`_USER_CONTENT_VARS` / `SYSTEM_VARS` per RULE-22 §4/§6), and
  wiring the generation consumer to render the descriptive group. This is a
  **prompt-mechanics change requiring its own Retrofit-Plan** (adr-process §D.4)
  when ANAL-007 lands.
- **The `author_voice` context_mode on `LLMIntent.VOICE`** (the fourth VOICE mode,
  anticipated by ADR-055 D4 + ADR-073) — lands with the ANAL-007 governed template.
- **ANAL-009 Phase 2 author-drift consumer** — reads via the repository contract,
  reuses `voice_metric_distances`; its own ADR/spec when Phase 2 is scheduled.

---

## Risks Surfaced for Coordinator/User Decision (before implementation)

These are NOT blockers for approving this ADR, but should be acknowledged before
ANAL-007 implementation planning:

1. **Voice-generic type extraction touches stable code.** Moving
   `VoiceMetrics`/`VoiceAnalysis` out of `character.py` is a change to files that
   ANAL-008/WRITE-010/ANAL-009-Phase-1 depend on. **Mitigated by backward-compat
   re-exports** (step 1 of the Retrofit-Plan) and the existing test suite as the
   safety net. Low risk, but the extraction must ship as the first atomic step
   with a green existing-test run, not bundled with the new column.

2. **Author-metric field list is provisional.** The `AuthorMetrics` fields
   (`dialogue_ratio`, `description_density`, `action_introspection_ratio`,
   `metaphor_density`) are reconciled from the stale ANAL-007 spec; the exact set
   is a downstream decision informed by what the deterministic analyzer computes.
   `extra="allow"` means the set can grow without a migration. Low risk.

3. **Prompt-surface variable choice is deferred.** Whether author voice injects via
   a new `{{author_voice}}` or the unregistered `{{author_style_examples}}` is an
   ANAL-007 decision. Either way, the descriptive/metric boundary (this ADR) is
   binding. Flagged, not blocking.

4. **Series feature may revisit the resolution model.** When Series/Reihe lands,
   the "which voice does generation use — novel, series, or blend?" question will
   need its own decision. This ADR deliberately does not pre-commit (see
   Forward-compatibility). Low risk — additive sibling home, no migration of
   existing data.

No decision requires a user call before implementation beyond approving this ADR.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02b | ✅ | This ADR introduces NO prompt assembly / no inline f-string / no app-layer loader. The downstream prompt-surface wiring is flagged as separate prompt-mechanics work requiring its own Retrofit-Plan; it is not authorised by this storage ADR. |
| RULE-03 | ✅ | The storage contract (`AuthorVoiceProfile`, `AuthorMetrics`, the repository Protocol) is defined HERE, before the profiling writer or any consumer is built. |
| RULE-04 | ✅ | Modularised: storage type (Core) ≠ repository (Backend) ≠ migration ≠ future agent/service/router. Voice-generic types extracted to their own home rather than bloating `character.py`. |
| RULE-05/06 | ✅ | Core owns the data contract; Backend owns the repository + migration; one responsibility per file; voice-generic types do not live in a character-specific file. |
| RULE-07 | ✅ | `repository → ProjectSettings` (DB); Core data contract has no `apps/` imports; re-exports preserve the existing acyclic `analysis → profiles → kb.schemas` read direction. |
| RULE-11 | ✅ | NULL `author_voice` → graceful "no profile" for consumers (generation renders nothing; drift skips); never a crash or silent prompt regression. |
| RULE-14 | ✅ | The `ProjectSettings.author_voice` column lands with its Alembic migration in the same task (mirrors `0033_adaptive_settings_column`). A model change without a migration is a build failure. |
| RULE-22 / CR-04 | ✅ | Cross-feature coherence: producer (ANAL-007) + generation consumer + drift consumer defined together; the descriptive/metric boundary is fixed before any consumer is built; voice-generic types are SSOT (one definition, re-exported — no duplication). |

---

## Review Trigger

- [ ] When ANAL-007 (Author Voice Profiling) is implemented — verify the profiling
      writer uses `AuthorVoiceRepository`, the generation consumer renders ONLY the
      descriptive group (boundary preserved), and the voice-generic type extraction
      shipped with re-exports keeping ANAL-008/WRITE-010/ANAL-009-Phase-1 green.
      *(Closes ADR-055 Review Trigger #3.)*
- [ ] When ANAL-009 Phase 2 (Author Voice Drift) is implemented — verify it reads
      `author_metrics` + `voice_analysis.voice_metrics` via the repository contract
      (no raw column access — the ADR-050 "no SSOT bypass" analogue) and reuses
      the `voice_metric_distances` primitive. *(Resolves the ADR-073 Phase 2
      Deferral blocking question this ADR answers.)*
- [x] **FULLY CLOSED by ADR-075 + ADR-078 (2026-08-05):** the Series / Reihe
      feature is implemented. **Storage-Teil** closed by ADR-075 (2026-07-29):
      the sibling `SeriesSettings.author_voice` home now exists. **Voice-Teil**
      closed by ADR-078 (2026-08-05, Spec 3 — Series Voice Hierarchy): the voice
      resolution model is decided — **Delta** (series voice as foundation, novel
      voice additive, per-novel `use_series_voice` opt-out); the empty
      `SeriesSettings.author_voice` column is populated; `{{author_voice}}` is
      extended (no new variable) and `AuthorVoiceConsumer` renders the Delta
      composition. ADR-075 confirms this ADR's novel-level home remains the primary
      scope (no forced cascade) — the series voice is an additive sibling, not a
      replacement, exactly as this ADR's Forward-compatibility analysis specified.
      The cascade question is resolved *against* a forced cascade (the
      Cascade-Fallback-Kritik stood; Delta + opt-out is the architecturally honest
      answer). Implementation verification for Spec 3 is tracked in ADR-078's own
      Review Trigger.
- [ ] If the author-metric field list proves insufficient for drift comparison —
      extend `AuthorMetrics` (additive, migration-free via `extra="allow"`).
- [ ] If the voice-generic type extraction causes any import break — fall back to
      defining `AuthorVoiceProfile` with duplicated-but-clearly-marked fields and
      file a follow-up to complete the extraction (last resort; re-exports should
      make this unnecessary).

---

## Cross-References

- **ADR-069** — `AdaptiveSettings` on `ProjectSettings` JSONB (THE persistence
  pattern this ADR mirrors; `AdaptiveSettingsRepository` + migration `0033` are the
  reference implementation).
- **ADR-055** — character-voice storage contract (the structural parallel +
  descriptive/metric boundary this ADR preserves; Review Trigger #3 this ADR
  closes).
- **ADR-057** — voice-check checking-path contract (metrics never reach generation;
  `voice_metric_distances` primitive Phase 2 will reuse).
- **ADR-073** — Character Voice Drift (Phase 2 Deferral blocking question this ADR
  resolves; longitudinal pattern Phase 2 will inherit).
- **ADR-040** — `core/profiles/` SSOT module.
- **ADR-050** — cross-feature context contracts (the "no SSOT bypass" rule the
  Phase 2 drift consumer must honour).
- **ADR-021** — deterministic analysis (pre-names `voice_metrics.py`; measurement
  is deterministic).
- `docs/features/analysis/ANAL-007-voice-author.md` — the (stale) feature spec this
  storage enables; its field list must be reconciled at implementation.
- `docs/features/writing/WRITE-011-volume-management.md` + `apps/api/narrare/volumes/models.py:19`
  — evidence for the Volume ≠ Series finding.
