---
id: ANAL-007
title: "Author Voice Profiling"
status: planned
area: analysis
mvp: false

ui_tooltip: "Analyze your writing style and create a voice profile for AI generation."
ui_help_short: |
  Narrare can learn your unique writing voice — sentence patterns, vocabulary,
  dialogue ratio, metaphor usage. Author Voice Profiling analyzes your existing
  chapters and creates a profile that helps AI write in your style.
ui_help_long: |
  ## Author Voice Profiling

  Teach Narrare to write like you. Voice Profiling analyzes your existing
  chapters to capture your unique writing style.

  **What gets analyzed:**

  **Sentence Structure**
  - Length distribution (short, medium, long)
  - Complexity (simple, compound, complex)
  - Rhythm and flow patterns
  - Paragraph structure

  **Vocabulary**
  - Word choice preferences
  - Complexity level
  - Diversity and repetition
  - Favorite words and phrases

  **Dialogue vs Narration**
  - Ratio of dialogue to prose
  - Dialogue tag patterns
  - Interior monologue frequency

  **Stylistic Elements**
  - Metaphor density and types
  - Sensory detail preferences
  - Description density (sparse vs rich)
  - Action vs introspection balance

  **How it works:**
  1. Select 3+ chapters for analysis (more = better profile)
  2. Click "Analyze Voice" in Analysis panel
  3. AI analyzes your writing (30-60 seconds)
  4. Voice profile appears with:
     - Style metrics and scores
     - Example passages for each element
     - Comparison to genre averages
  5. Save profile to your project
  6. Future AI generation uses your voice automatically

  **Best practices:**
  - Analyze after 3+ chapters for accuracy
  - Include chapters from different story phases
  - Re-analyze after major style changes
  - Review profile before saving

  **How AI uses your voice:**
  - Matches sentence structure in generation
  - Mimics your vocabulary choices
  - Replicates your dialogue patterns
  - Uses your metaphors and stylistic habits

  Your voice profile is stored locally and never shared. Delete anytime to
  return to default AI style.

  Note: Voice matching requires LLM with sufficient context window.
ui_available_in: [analysis, settings]

service: analysis/voice/author_service.py
contract: analysis/contracts.py#AuthorVoiceProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/voice_author
requires: [INFRA-001]
---

# ANAL-007 — Author Voice Profiling

## What it does

Analyzes existing chapters to extract author's unique writing style. Creates a
voice profile (sentence patterns, vocabulary, dialogue ratio, metaphors) that
informs AI generation to match author's voice.

## Why it exists

Default AI prose sounds generic. Writers have unique voices — the product
of thousands of choices in sentence structure, word choice, and rhythm. Voice
profiling captures these patterns so AI can write in the author's style.

## How it works (User perspective)

1. Select 3+ chapters for analysis (more chapters = better profile)
2. Click "Analyze Voice" in Analysis panel
3. AI analyzes writing (30-60 seconds)
4. Voice profile appears showing:
   - **Metrics**: Sentence length, vocabulary, dialogue ratio, etc.
   - **Examples**: Passages that exemplify your style
   - **Comparison**: How you differ from genre averages
5. Review and adjust if needed
6. Save profile to project

Once saved, AI generation (WRITE-002, WRITE-003, etc.) automatically uses
your voice profile.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/voice/author`
**Service:** `AuthorVoiceService.analyze()` in `analysis/voice/author_service.py`
**Contract:** `AuthorVoiceProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.VOICE`

**Voice profile structure:**
```python
class AuthorVoiceProfile:
    sentence_structure: SentenceMetrics
    vocabulary: VocabularyMetrics
    dialogue_ratio: float  # 0-1
    metaphor_density: float  # 0-1
    description_density: float  # 0-1
    action_introspection_ratio: float  # 0-1
    examples: dict[str, list[str]]  # Style element → example passages
```

**Analysis process:**
1. **Extract text** from selected chapters
2. **Calculate metrics**:
   - Sentence length distribution (mean, std, histogram)
   - Vocabulary complexity (type-token ratio, syllable count)
   - Dialogue percentage (quoted words / total words)
   - Metaphor frequency (pattern matching)
3. **Select examples** for each style element
4. **Compare to genre baselines**
5. **Generate profile** stored in database

**Usage in generation:**
- Profile loaded by context assembly (INFRA-003)
- Injected into prompts as `{{author_style_examples}}`
- Used by LLM to mimic patterns

## Constraints & Edge Cases

- Minimum 3 chapters required for meaningful analysis
- Minimum 10,000 words total recommended
- Profile quality depends on text diversity
- Voice matching requires LLM with sufficient context
- Very unique styles may not match perfectly
- Re-analysis needed after major style evolution
- Profile stored locally only (privacy)

## Related Features

- [ANAL-009](ANAL-009-voice-drift.md) — Detect voice changes
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Uses voice profile
- [LEARN-002](../learning/LEARN-002-style-adaptation.md) — Style learning

## Status & History

- `project-init` — Added to registry as planned feature
