---
id: ANAL-008
title: "Character Voice Profiling"
status: stable
area: analysis
mvp: false

ui_tooltip: "Analyze character dialogue to create voice profiles for consistency."
ui_help_short: |
  Ensure each character sounds distinct. Character Voice Profiling analyzes
  dialogue from your chapters to capture how each character speaks — their
  vocabulary, sentence patterns, verbal tics, and emotional register.
ui_help_long: |
  ## Character Voice Profiling

  Give each character a distinct, consistent voice. Character Voice Profiling
  analyzes dialogue from your chapters to capture speech patterns unique to
  each character.

  **What gets analyzed per character:**

  **Speech Patterns**
  - Sentence length and structure preferences
  - Word choice and vocabulary level
  - Favorite phrases and verbal tics
  - Punctuation and formatting habits

  **Personality in Speech**
  - Formal vs casual language
  - Direct vs indirect communication
  - Emotional expressiveness
  - Humor, sarcasm, irony usage

  **Contextual Patterns**
  - How they speak to different characters
  - Speech under stress vs relaxed
  - Professional vs personal voice
  - Lying vs truth-telling markers

  **How it works:**
  1. Select chapters containing character dialogue
  2. Click "Character Voices" in Analysis panel
  3. Choose characters to analyze (or auto-detect)
  4. AI extracts and analyzes dialogue (15-45 seconds)
  5. Voice profile appears for each character:
     - Speech metrics and patterns
     - Example dialogue quotes
     - Comparison to other characters
  6. Save profiles to Knowledge Base
  7. Used by Voice Checker (WRITE-010) for consistency

  **Best practices:**
  - Include at least 10 dialogue passages per character
  - Include dialogue from different contexts
  - Analyze after major dialogue revisions
  - Review profiles before saving to KB

  **Use cases:**
  - Ensure characters sound distinct from each other
  - Maintain voice consistency across long novels
  - Help beta readers identify characters by voice alone
  - Guide AI-generated dialogue for each character

  Character voice profiles are stored in the Knowledge Base and can be edited
  manually. They're used by the Voice Checker and AI dialogue generation.
ui_available_in: [analysis, kb]

service: analysis/character_voice_service.py
contract: analysis/contracts_character_voice.py#CharacterVoiceServiceProtocol
router: analysis/router_character_voice.py
prompt: core/prompts/_bundled/analysis/en/character_voice/system.md
requires: [INFRA-001, INFRA-002, KB-001]
---

# ANAL-008 — Character Voice Profiling

> **Architecture authority:** [ADR-055](../../architecture/decisions/ADR-055-character-voice-contract.md)
> (Character Voice Storage Contract & VOICE Prompt Surface). The technical sections
> below implement that ADR. This spec is `stable` (implemented and validated across
> all layers — Core + Backend + Frontend).

## What it does

Analyzes character dialogue from chapters to extract unique speech patterns.
Creates voice profiles (vocabulary, sentence structure, verbal tics, emotional
register) stored in the Knowledge Base for consistency checking and AI dialogue
generation.

## Why it exists

Characters should sound distinct. Readers should be able to identify who's
speaking without dialogue tags. Character Voice Profiling captures speech
patterns so writers can maintain consistency and AI can generate character-
appropriate dialogue.

## How it works (User perspective)

1. Select chapters containing character dialogue
2. Click "Character Voices" in Analysis panel
3. AI detects speaking characters or you select manually
4. Analysis runs (15-45 seconds depending on dialogue amount)
5. For each character, voice profile shows:
   - **Speech metrics**: Formality, complexity, verbosity (deterministic)
   - **Patterns**: Sentence structure, word choice
   - **Verbal tics**: Repeated phrases, catchphrases
   - **Examples**: Curated quote samples showing their voice
6. Review profiles
7. Save to Knowledge Base (augments the character entry)

Profiles are used by Voice Checker (WRITE-010) to flag inconsistent dialogue.

## How it works (Technical)

> Mirrors the established analysis pattern (ANAL-003/004/005): deterministic
> analyzer + `NarrareAgent` structured output + governed EN template + SSE
> router + panel. Per ADR-021 + ADR-055.

**Entry point:** `analysis/router_character_voice.py` → `POST /api/v1/analysis/character-voice`
**Service:** `CharacterVoiceService.analyze()` in `analysis/character_voice_service.py`
**Contract:** `CharacterVoiceServiceProtocol` in `analysis/contracts_character_voice.py`
**Agent:** `CharacterVoiceAgent` (`core/agents/character_voice_agent.py`, `NarrareAgent` with structured output)
**LLM Intent:** `LLMIntent.VOICE` (context_mode `character_voice`; ADR-055 makes VOICE routeable)
**Prompt:** PromptComposer Mode 1 — `_bundled/analysis/en/character_voice/system.md` (governed EN template; ADR-054)

### Architecture: hybrid metrics (ADR-021, mirrors ANAL-003)

The feature is split into a **deterministic measurement** half and an **LLM
qualitative-understanding** half, exactly like ANAL-003 (Readability):

```python
# Deterministic metrics — for ANAL-009 drift / WRITE-010 comparison (stable, comparable)
class VoiceMetrics:
    avg_sentence_length: float | None
    sentence_length_std: float | None
    type_token_ratio: float | None
    avg_syllables_per_word: float | None
    contraction_rate: float | None
    verbal_tic_frequency: dict[str, float] | None   # n-gram → rate
    punctuation_profile: dict[str, float] | None    # habit → rate

# LLM qualitative judgments (one structured-output call consuming text + metrics)
class CharacterVoiceResult:
    formality: float                       # 0.0 casual – 1.0 formal
    vocabulary_level: str                  # simple | moderate | complex
    sentence_profile: str                  # short | medium | long | varied
    emotional_range: str                   # restricted | moderate | expressive
    cultural_regional_markers: str | None  # intrinsic — persisted
    voice_examples: list[str]              # curated representative quotes
    distinctiveness_notes: str | None      # COMPARISON artifact — display only, not persisted
```

**Agent-output → storage mapping (ADR-055, no data loss):** the service maps the
agent's INTRINSIC qualitative outputs (`formality` … `voice_examples` +
`cultural_regional_markers`) into the `VoiceAnalysis` descriptive group, and the
deterministic `VoiceMetricsAnalyzer` output into `VoiceAnalysis.voice_metrics`.
`distinctiveness_notes` is relative to whichever other characters were analyzed in
the same run (not an intrinsic property) → surfaced in the UI panel as a per-analysis
review aid, recomputed on each run, never persisted on the character profile.

### Architecture: self-contained dialogue attribution (ADR-055 Decision 3)

A deterministic `DialogueParser` splits quotes + tag-attributes ("said Elena",
action beats) with confidence and computes per-utterance metrics. The
`CharacterVoiceAgent` resolves any remaining ambiguous speakers INLINE in the
same single LLM call. ANAL-005 (Coreference) is **not** coupled as a runtime
pre-step (keeps ANAL-008 decoupled, single model call, independently testable;
Coreference = optional future enhancement).

### Pipeline

```
chapters
  → DialogueParser            (utterances + tag attribution + confidence)
                              [Core: core/analysis/dialogue_parser.py]
  → VoiceMetricsAnalyzer      (per-utterance deterministic metrics)
                              [Core: core/analysis/voice_metrics.py  — ADR-021]
  → CharacterVoiceAgent       (resolves ambiguous attribution + qualitative
                               profile + curated examples, consuming text +
                               metrics — ONE LLM call)
                              [Core: core/agents/character_voice_agent.py]
  → deterministic per-character aggregation
  → write structured profile to KBEntity.metadata["speech"]["voice_analysis"]
    + bump updated_at (so existing profiles/_freshness.py is_stale() works)
```

### Data contract (ADR-055 Decision 1 — the corrected, non-lossy contract)

Character voice profiles are written to the character's KB metadata under the
`speech` key — the SAME single source of truth the generation pipeline already
reads. The existing `SpeechPatterns` schema is extended with ONE nested
`voice_analysis` sub-model. The 4 human-authored fields are untouched
(ANAL-008 AUGMENTS, never overwrites user data).

```python
# core/kb/schemas/character.py  (extends SpeechPatterns — migration-free via extra="allow")

class VoiceMetrics(BaseModel):
    """Deterministic numeric metrics — for ANAL-009/WRITE-010. NOT rendered into generation."""
    model_config = ConfigDict(extra="allow")
    avg_sentence_length: float | None = None
    sentence_length_std: float | None = None
    type_token_ratio: float | None = None
    avg_syllables_per_word: float | None = None
    contraction_rate: float | None = None
    verbal_tic_frequency: dict[str, float] | None = None
    punctuation_profile: dict[str, float] | None = None

class VoiceAnalysis(BaseModel):
    """Machine-derived character voice profile (ANAL-008 writes; consumer renders descriptive)."""
    model_config = ConfigDict(extra="allow")
    # Descriptive group (rendered into {{character_voice_profiles}} by extended consumer)
    formality: float | None = None
    vocabulary_level: str | None = None
    sentence_profile: str | None = None
    emotional_range: str | None = None
    cultural_regional_markers: str | None = None
    voice_examples: list[str] | None = None
    # Metric group (for comparison ONLY — never rendered into generation)
    voice_metrics: VoiceMetrics | None = None

class SpeechPatterns(BaseModel):
    model_config = ConfigDict(extra="allow")
    # Human-authored (unchanged):
    typical_phrases: list[str] | None = None
    dialect: str | None = None
    vocabulary_quirks: str | None = None
    body_language: str | None = None
    # Machine-derived (ADR-055):
    voice_analysis: VoiceAnalysis | None = None
```

### Integration with the Generation Pipeline (CR-04 cross-feature coherence)

The generation pipeline reads `KBEntity.metadata["speech"]` via
`core/profiles/_voice_extraction.py::get_speech_data()`, which builds
`CharacterVoiceProfile.speech_summary`, rendered into `{{character_voice_profiles}}`
by `ProjectWritingProfile.formatted_voice_profiles`.

ADR-055 extends `get_speech_data()` to ALSO render the descriptive group of
`voice_analysis` (formality, vocabulary_level, sentence_profile, emotional_range,
cultural_regional_markers, voice_examples). It MUST NOT render `voice_metrics`
(raw metrics are for comparison, not generation).

This means ANAL-008 results automatically reach every writing prompt — no second
store, no drift. Because the change is producer + consumer + checking-projection
together, it satisfies CR-04 end-to-end coherence (not feature-local).

### Integration with the Checking Pipeline (ADR-050)

WRITE-010 / ANAL-009 consume voice data via `VoiceProfileConsumer.assemble_for_checking()`
(ADR-050), which surfaces structured profiles including `voice_metrics`. ANAL-008's
write path is the producer that satisfies that contract.

### Foundation (reusable Core infrastructure)

Two Foundation analyzers are built now because they are reused by WRITE-010 and
ANAL-009 (justified reuse, not YAGNI). They are infrastructure, not user-facing
features, so they do NOT get a `docs/features/INDEX.md` entry — they are documented here:

| Component | Location | Consumed by |
|-----------|----------|-------------|
| `DialogueParser` | `core/analysis/dialogue_parser.py` | ANAL-008 (now); WRITE-010 (future) |
| `VoiceMetricsAnalyzer` | `core/analysis/voice_metrics.py` (ADR-021) | ANAL-008 (now); ANAL-009 + WRITE-010 (future) |

`DialogueParser`/`VoiceMetricsAnalyzer` may consume `core/nlp/` primitives
(`NLPProvider`, ADR-021) respecting RULE-07 (`analysis → nlp`).

## Constraints & Edge Cases

### Critical Storage Constraint (ADR-055)

When saving generated voice profiles, the data MUST be written to
`KBEntity.metadata["speech"]["voice_analysis"]` in the exact structure above.
The 4 human-authored fields (`typical_phrases`, `dialect`,
`vocabulary_quirks`, `body_language`) MUST NOT be overwritten by ANAL-008.

**Why this matters:** the generation pipeline reads `metadata["speech"]` via
`get_speech_data()`. Storing voice data anywhere else (a separate table, a
different metadata key) breaks the single source of truth and leaves generation
without voice protection — a regression.

> **Non-lossy contract:** unlike the earlier draft of this spec, ANAL-008 does
> NOT remap its outputs onto the human-authored fields (that mapping was
> semantically wrong — example quotes in `body_language`, formality in `dialect`).
> See ADR-055 Decision 1 for the root cause and the corrected contract.

### Determinism (ADR-021)

`VoiceMetrics` are deterministic (stable across runs and minor edits). Only the
qualitative fields (formality register, emotional range, cultural markers,
distinctiveness, example curation) come from the LLM. This makes the metrics
suitable for ANAL-009 drift comparison and WRITE-010 consistency checking.

### Edge Cases

- Minimum 10 dialogue passages per character recommended
- Very sparse dialogue = poor profile quality
- Characters with similar voices may not be distinguished
- Irony, sarcasm, lying taken literally by metrics (the agent may surface these)
- Dialogue attribution errors affect accuracy (the agent resolves ambiguity inline)
- Re-analysis needed after major dialogue revisions
- LLM availability required (metrics are deterministic; qualitative profile is not)

## Related Features

- [WRITE-010](../writing/WRITE-010-voice-checker.md) — Uses profiles + metrics for checking
- [ANAL-009](ANAL-009-voice-drift.md) — Consumes `voice_metrics` for drift comparison (its spec's stale "map to SpeechPatterns" note is superseded by ADR-055)
- [ANAL-007](ANAL-007-voice-author.md) — Author voice analysis (deferred; separate storage decision, out of scope here)
- [KB-001](../kb/KB-001-entity-management.md) — Stores profiles (`speech.voice_analysis`)
- [ADR-055](../../architecture/decisions/ADR-055-character-voice-contract.md) — Storage + prompt-surface contract authority

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-06-26` — Spec authored against ADR-055 (storage contract + VOICE prompt
  surface). Removed the earlier lossy field-mapping (semantically wrong; stored
  quotes in `body_language` etc.) in favour of the nested `voice_analysis`
  extension to the live `SpeechPatterns` contract. Hybrid metrics (ADR-021),
  self-contained attribution (no Coreference coupling), and Foundation
  (`DialogueParser` / `VoiceMetricsAnalyzer`) specified. Status remains `planned`
  (implementation pending user approval of ADR-055).
- `2026-06-29` — **Implemented (all layers: Core Foundation + agent, Backend
  service+SSE, Frontend panel+hook+i18n).** Hybrid metrics (ADR-021),
  self-contained dialogue attribution, nested `voice_analysis` contract
  (ADR-055), VOICE promoted to routeable. Validated: `just check` 9/9, 8341
  backend + 2287 frontend tests green, 0 architecture/AI-UX violations.
  `character_voice` runtime adoption is **runtime-verified** (probes landed in
  `ee1cfc50`; the local commit-gate is runtime-evidence-aware via ADR-056, so it
  witnesses the committed markers).
  Commits: `e12f6539` (Layer 0 — `SpeechPatterns` `voice_analysis`),
  `ee0c148f` (Layer 1 — VOICE routeable + `character_voice` template),
  `96fca8e1` (Layer 2 — `DialogueParser` + `VoiceMetricsAnalyzer` +
  `CharacterVoiceAgent` + consumer merge),
  `74b7c83a` (Layer 3 — Backend `CharacterVoiceService` + SSE),
  `ce392ac4` (Layer 4 — Frontend panel + hook + i18n).
  Status → `stable`.
