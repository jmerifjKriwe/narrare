---
id: ANAL-009
title: "Voice Drift Detection"
status: planned
area: analysis
mvp: false

ui_tooltip: "Detect when your writing voice changes across chapters."
ui_help_short: |
  Has your writing style evolved or drifted? Voice Drift Detection compares
  chapters to identify where your voice has changed — intentional evolution
  or unintentional inconsistency. Track your stylistic journey.
ui_help_long: |
  ## Voice Drift Detection

  Track how your writing voice changes across your novel. Intentional evolution
  or unintentional inconsistency — know the difference.

  **What gets detected:**

  **Stylistic Changes**
  - Sentence structure shifts
  - Vocabulary level changes
  - Dialogue ratio variations
  - Description density changes

  **Pattern Shifts**
  - Metaphor usage frequency
  - Pacing and rhythm changes
  - Action vs introspection balance
  - Show vs tell ratio

  **Possible Causes**
  - Intentional evolution (character POV change, story arc)
  - Unintentional drift (written at different times)
  - Context-dependent (action scenes vs contemplation)
  - Problematic inconsistency (confusing readers)

  **How it works:**
  1. Select chapters or entire novel
  2. Click "Voice Drift" in Analysis panel
  3. Choose baseline chapter (your "target" voice)
  4. AI compares all chapters to baseline (30-60 seconds)
  5. Results show:
     - Similarity score per chapter (0-100%)
     - Specific changes detected
     - Timeline visualization of drift
     - Likely causes for each change
  6. Click any chapter to see:
     - What changed from baseline
     - Whether change is intentional
     - Suggestions for consistency

  **Interpreting scores:**
  - 90-100%: Very consistent with baseline
  - 70-89%: Minor variations (normal)
  - 50-69%: Moderate drift (may need attention)
  - <50%: Major drift (check if intentional)

  **Best practices:**
  - Run after first draft complete
  - Use early chapters as baseline
  - Context matters (action scenes differ naturally)
  - Not all drift is bad — evolution is natural

  **Use cases:**
  - Ensure series consistency across books
  - Catch unintentional voice changes
  - Track stylistic evolution over time
  - Identify chapters that don't fit

  Voice drift isn't always wrong. Many authors evolve intentionally. This tool
  helps you distinguish intentional choices from problematic inconsistency.
ui_available_in: [analysis]

service: analysis/voice/drift_service.py
contract: analysis/contracts.py#VoiceDriftProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/voice_drift
requires: [INFRA-001, ANAL-007]
---

# ANAL-009 — Voice Drift Detection

## What it does

Compares writing style across chapters to detect voice evolution or inconsistency.
Calculates similarity scores against baseline chapter, identifies specific
stylistic changes, and suggests whether drift is intentional or problematic.

## Why it exists

Authors' voices naturally evolve over long projects. But unintentional
inconsistency can confuse readers. Voice drift detection makes stylistic
changes visible, helping authors distinguish evolution from inconsistency.

## How it works (User perspective)

1. Select chapters to compare (or entire novel)
2. Click "Voice Drift" in Analysis panel
3. Choose baseline chapter (often your first or favorite)
4. AI compares all chapters to baseline (30-60 seconds)
5. Visualization shows:
   - **Similarity timeline**: Line graph of scores over chapters
   - **Change breakdown**: What specifically changed per chapter
   - **Cause analysis**: Likely reasons for each change
6. Click any chapter to see details
7. Decide if changes are:
   - Intentional evolution (keep it)
   - Context-dependent (normal variation)
   - Problematic inconsistency (fix it)

Use to ensure series consistency or track your stylistic journey.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/voice/drift`
**Service:** `VoiceDriftService.detect()` in `analysis/voice/drift_service.py`
**Contract:** `VoiceDriftProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.VOICE`

**Comparison process:**
1. **Extract style metrics** from baseline chapter (ANAL-007 profile)
2. **Extract metrics** from each comparison chapter
3. **Calculate similarity** across style dimensions:
   - Sentence structure correlation
   - Vocabulary overlap
   - Dialogue ratio difference
   - Metaphor density similarity
4. **Weighted score** = 0-100% similarity
5. **Identify specific changes** that caused drift
6. **Classify drift type**:
   - **Intentional evolution**: Gradual, story-arc related
   - **Context-dependent**: Scene-type variation (action vs contemplation)
   - **Inconsistency**: Random, unexplained changes

**Drift visualization:**
```python
class VoiceDriftResult:
    chapter_id: UUID
    similarity_score: float  # 0-1
    changes: list[str]  # "longer sentences", "more dialogue", etc.
    drift_type: "evolution" | "context" | "inconsistency"
    confidence: float  # 0-1
```

### Integration with Generation Pipeline

The generation pipeline (`WritingContextAssembler`) already extracts character
voice profiles from KB metadata and injects them into writing prompts as
`{{character_voice_profiles}}`. This serves as a **preventive** measure against
voice drift — characters should already sound consistent when generated.

Voice Drift Detection (this feature) serves as the **corrective** counterpart:
it analyzes generated chapters after the fact to detect remaining drift.
When implementing this feature:
- Use the same `KBEntity.metadata["speech"]` data contract (see ANAL-008)
- The `CharacterVoiceProfile` structure should map to `SpeechPatterns` fields

## Constraints & Edge Cases

- Requires baseline chapter with 1000+ words
- Very short chapters produce noisy comparisons
- Intentional POV changes may be flagged as drift
- Stylistic variety (not drift) may be misclassified
- Similarity scores are relative, not absolute
- Cannot distinguish all intentional from unintentional changes
- LLM availability required

## Related Features

- [ANAL-007](ANAL-007-voice-author.md) — Baseline voice profiling
- [ANAL-010](ANAL-010-literary-suite.md) — Comprehensive comparison
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Maintaining voice in generation

## Status & History

- `project-init` — Added to registry as planned feature
