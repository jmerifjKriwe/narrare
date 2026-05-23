---
id: ANAL-008
title: "Character Voice Profiling"
status: planned
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

service: analysis/voice/character_service.py
contract: analysis/contracts.py#CharacterVoiceProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/voice_character
requires: [INFRA-001, KB-001]
---

# ANAL-008 — Character Voice Profiling

## What it does

Analyzes character dialogue from chapters to extract unique speech patterns.
Creates voice profiles (vocabulary, sentence structure, verbal tics) stored in
Knowledge Base for consistency checking and AI dialogue generation.

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
   - **Speech metrics**: Formality, complexity, verbosity
   - **Patterns**: Sentence structure, word choice
   - **Verbal tics**: Repeated phrases, catchphrases
   - **Examples**: Quote samples showing their voice
6. Review profiles
7. Save to Knowledge Base (updates character entries)

Profiles are used by Voice Checker (WRITE-010) to flag inconsistent dialogue.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/voice/character`
**Service:** `CharacterVoiceService.analyze()` in `analysis/voice/character_service.py`
**Contract:** `CharacterVoiceProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.VOICE`

**Voice profile structure:**
```python
class CharacterVoiceProfile:
    character_id: UUID
    formality: float  # 0-1, casual to formal
    vocabulary_level: str  # simple, moderate, complex
    sentence_structure: str  # short, medium, long, varied
    verbal_tics: list[str]
    speech_patterns: dict[str, str]  # pattern → description
    examples: list[str]  # Representative quotes
    emotional_range: str  # restricted, moderate, expressive
```

### Integration with Generation Pipeline

When character voice profiles are generated via this feature, they should be saved
to the character's KB metadata under the `speech` key. The generation pipeline
(`WritingContextAssembler._extract_voice_profiles()`) automatically reads
`KBEntity.metadata["speech"]` and `KBEntity.metadata["personality"]` to populate
the `{{character_voice_profiles}}` variable in all writing prompts.

**Data contract** — `KBEntity.metadata["speech"]` must contain:
```python
{
    "dialect": str | None,
    "vocabulary_quirks": str | None,
    "typical_phrases": list[str] | None,
    "body_language": str | None,
}
```

This matches the `SpeechPatterns` schema in `kb/schemas/character.py` and the
`CharacterMetadata.speech` model. The extraction code handles missing/partial
fields gracefully.

**Analysis process:**
1. **Extract dialogue** attributed to each character
2. **Calculate metrics**:
   - Average words per sentence
   - Vocabulary complexity (syllable count, unique words)
   - Formality indicators (contractions, slang, titles)
   - Repetition patterns (verbal tics)
3. **Select examples** representing each character's voice
4. **Compare to other characters** (distinctiveness score)
5. **Generate profile** saved to KB-001

**Attribution methods:**
- Dialogue tags ("Elena said")
- Scene context (who's present in scene)
- Sequential analysis (speech alternation)
- KB entries (character roles)

## Constraints & Edge Cases

### Critical Implementation Constraint

When saving generated voice profiles to the Knowledge Base, the profile data
MUST be written to the character's KB metadata under the `speech` key in the
exact format specified by the [Generation Pipeline data contract](#integration-with-generation-pipeline).

**Mapping rule:**
```
CharacterVoiceProfile.verbal_tics  →  metadata["speech"]["typical_phrases"]
CharacterVoiceProfile.formality    →  metadata["speech"]["dialect"]  (as descriptor string)
CharacterVoiceProfile.speech_patterns  →  metadata["speech"]["vocabulary_quirks"]  (as JSON string)
CharacterVoiceProfile.examples     →  metadata["speech"]["body_language"]  (as examples context)
```

**Why this matters:** The generation pipeline (`WritingContextAssembler._extract_voice_profiles()`)
reads `KBEntity.metadata["speech"]` and `KBEntity.metadata["personality"]` to inject
`{{character_voice_profiles}}` into all writing prompts. If the profile data is stored
in a different structure or location, the prompt-level voice protection will remain empty —
ANAL-008 analysis results would never reach actual generation.

**Non-compliance:** A future developer implementing ANAL-008 who stores voice profiles
anywhere else (e.g., a separate table, a different metadata key, or a flat field directly
on the character model) will cause the generation pipeline to produce characters without
voice protection. This is a regression.

### Edge Cases

- Minimum 10 dialogue passages per character recommended
- Very sparse dialogue = poor profile quality
- Characters with similar voices may not be distinguished
- Irony, sarcasm, lying not detected (taken literally)
- Dialogue attribution errors affect accuracy
- Re-analysis needed after major dialogue revisions
- LLM availability required

## Related Features

- [WRITE-010](../writing/WRITE-010-voice-checker.md) — Uses profiles for checking
- [KB-001](../kb/KB-001-entity-management.md) — Stores profiles
- [KB-002](../kb/KB-002-kb-session.md) — Create profiles via interview
- [ANAL-007](ANAL-007-voice-author.md) — Author voice analysis

## Status & History

- `project-init` — Added to registry as planned feature
