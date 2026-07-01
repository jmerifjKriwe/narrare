---
id: LEARN-002
title: "Style Adaptation"
status: planned
area: learning
mvp: false

ui_tooltip: "AI learns your writing voice and generates text in your style."
ui_help_short: |
  AI analyzes your existing chapters to learn your unique writing voice,
  then generates text that matches your style — sentence patterns,
  vocabulary, dialogue ratios, and narrative rhythm.
ui_help_long: |
  ## Style Adaptation

  Generate text that sounds like you wrote it.

  **Voice Analysis Phase**
  - Sentence length distribution
  - Vocabulary profile and diversity
  - Dialogue-to-narration ratio
  - Metaphor density and usage patterns
  - Narrative rhythm and paragraph structure
  - Common phrases and stylistic tics

  **Style Profile**
  - Persisted per-project
  - Updated as you write
  - Comparable across projects
  - Exportable for backup

  **Generation Phase**
  - Loads your Style Profile
  - Uses few-shot prompting with your examples
  - Generates text matching your patterns
  - Streams results in real-time
  - Confidence scores for style match

  **How it works:**
  1. Write 3+ chapters (minimum for analysis)
  2. Click "Analyze Style" in Settings → Style
  3. AI analyzes your writing (30-60 seconds)
  4. Style profile created showing:
     - Sentence length distribution
     - Vocabulary diversity
     - Dialogue percentage
     - Common patterns
  5. Enable "Use my style" for generation
  6. Future AI suggestions match your voice
  7. Re-analyze after major style changes

  **Best practices:**
  - Analyze after 3+ chapters for accuracy
  - Re-analyze after major style changes
  - Use specific, grounded prompts for best results
  - Review generated text for quality, not just style
  - Style match is one factor among many

  Available in Settings panel or via CLI:
  `narrare style analyze --novel <id>`
  `narrare style generate --novel <id> --prompt "The door creaked open..."`
ui_available_in: [settings, cli]

service: learning/style_service.py
contract: learning/contracts.py#StyleServiceProtocol
router: learning/router.py
prompt: core/prompts/_bundled/learning/en/style
requires: [INFRA-001, INFRA-002, WRITE-001]
---

# LEARN-002 — Style Adaptation

## What it does

AI-powered style profiling that analyzes a writer's unique voice from existing chapters and uses that profile to generate matching text. Captures sentence patterns, vocabulary, dialogue ratios, and narrative rhythm for personalized AI assistance.

## Why it exists

Generic AI text sounds generic. Writers have unique voices developed over years — specific sentence lengths, vocabulary choices, dialogue patterns. Style adaptation enables AI to generate text that sounds like it came from the same author, maintaining voice consistency across AI-assisted passages.

## How it works (User perspective)

1. Write at least 3 chapters (minimum for meaningful analysis)
2. Open Settings → Style Adaptation
3. Click "Analyze My Style"
4. AI analyzes your writing (30-60 seconds)
5. View your Style Profile:
   - Sentence length distribution chart
   - Vocabulary diversity score
   - Dialogue vs narration percentage
   - Common phrases and patterns
   - Stylistic tics and preferences
6. Enable "Use my style for generation"
7. Future AI suggestions incorporate your voice
8. Re-analyze after major style evolution

## How it works (Technical)

**Entry point:** `apps/api/narrare/learning/router.py` → `POST /api/v1/learning/style/analyze`
**Service:** `StyleService.analyze()` and `generate_with_style()` in `apps/api/narrare/learning/style_service.py`
**Contract:** `StyleServiceProtocol` in `apps/api/narrare/learning/contracts.py`
**LLM Intent:** `LLMIntent.ANALYZE` (for analysis), `LLMIntent.GENERATE` (for generation)

**Style profile:**
```python
class StyleProfile:
    project_id: UUID
    analyzed_at: datetime
    chapters_analyzed: int
    word_count: int

    # Sentence patterns
    sentence_length_mean: float
    sentence_length_std: float
    sentence_length_distribution: list[float]

    # Vocabulary
    vocabulary_diversity: float  # Unique words / total words
    common_words: list[tuple[str, int]]  # Word, frequency
    vocabulary_level: str  # simple, moderate, complex

    # Dialogue
    dialogue_ratio: float  # Dialogue words / total words
    dialogue_tag_patterns: list[str]

    # Rhythm
    paragraph_length_mean: float
    paragraph_length_distribution: list[float]

    # Examples
    example_sentences: list[str]  # For few-shot prompting
```

**Analysis pipeline:**
1. Extract text from analyzed chapters
2. Tokenize and parse sentences
3. Calculate statistical measures
4. Identify common patterns (n-grams)
5. Extract representative examples
6. Store profile for generation

**Generation with style:**
1. Load project's Style Profile
2. Select representative examples
3. Add style instructions to prompt
4. Use few-shot examples for pattern matching
5. Generate with style constraints
6. Score output for style match (0-1)

## Constraints & Edge Cases

- Requires minimum 3 chapters for meaningful analysis
- Style analysis is descriptive, not prescriptive
- May amplify bad habits if writer has them
- Style evolution requires re-analysis
- Style match score is approximate
- Examples in prompt increase token usage
- Cannot capture intangible qualities like "voice"
- Generated text may match style but lack substance

## Related Features

- [WRITE-001](../writing/WRITE-001-editor.md) — Chapter content source
- [ANAL-007](../analysis/ANAL-007-voice-author.md) — Author voice analysis
- [ANAL-010](../analysis/ANAL-010-literary-suite.md) — Literary analysis
- [LEARN-001](LEARN-001-feedback-loop.md) — Feedback-based learning
- [WRITE-006](../writing/WRITE-006-co-author.md) — Co-author mode

## Status & History

- `project-init` — Added to registry as planned feature
