---
id: WRITE-010
title: "Voice Consistency Checker"
status: planned
area: writing
mvp: false

ui_tooltip: "Check if dialogue matches each character's established voice."
ui_help_short: \
  |   Ensure characters sound like themselves. The Voice Checker analyzes
  |   dialogue against character profiles from your Knowledge Base, flagging
  |   inconsistencies and suggesting improvements to match each character's
  |   unique speech patterns.
ui_help_long: |
  ## Voice Consistency Checker

  Characters should sound like themselves — every time they speak. The Voice
  Checker ensures dialogue matches each character's established voice.

  **What it checks:**

  **Voice profile elements:**
  - Formal vs casual language
  - Vocabulary level and complexity
  - Sentence structure preferences
  - Verbal tics and catchphrases
  - Emotional register and expression
  - Cultural/regional markers

  **How it works:**
  1. Open a chapter with dialogue
  2. Click "Check Voice" in toolbar
  3. For each speaking character:
     - AI analyzes their dialogue in the chapter
     - Compares against their KB voice profile
     - Flags inconsistencies and problematic passages
  4. Results show:
     - Overall match score (0-100%)
     - Specific lines that don't match
     - Suggestions for improvement
  5. Click any flagged line to see:
     - Why it doesn't match
     - How to fix it
     - Suggested rewrite

  **Voice profiles:**

  Characters need voice profiles in the Knowledge Base. The more complete the
  profile, the better the checking:
  - Speech examples (what they say)
  - Vocabulary (words they use/avoid)
  - Verbal tics ("You know?", "Like", etc.)
  - Formality level (how they speak)
  - Background influences (education, region, culture)

  **Scores explained:**
  - 90-100%: Excellent match — character sounds consistent
  - 70-89%: Good match — minor inconsistencies
  - 50-69%: Fair match — several problematic lines
  - <50%: Poor match — character doesn't sound like themselves

  **Best practices:**
  - Create detailed voice profiles in KB first
  - Use during revision, not first draft
  - Low scores don't mean bad writing — intentional voice changes are valid
  - Update voice profiles as characters evolve

  The Voice Checker helps consistency, not creativity. If a character
  intentionally speaks differently in a scene (emotional, disguised, etc.),
  that's your call as the author.
ui_available_in: [editor]

service: writing/voice_checker_service.py
contract: writing/contracts.py#VoiceCheckerProtocol
router: writing/router.py
prompt: core/prompts/_bundled/analysis/en/voice
requires: [INFRA-001, KB-001, ANAL-008]
---

# WRITE-010 — Voice Consistency Checker

## What it does

Analyzes chapter dialogue against character voice profiles from Knowledge Base.
Flags inconsistencies, provides match scores, and suggests rewrites to align
dialogue with each character's established speech patterns.

## Why it exists

Readers notice when characters don't sound like themselves. A formal professor
suddenly using slang, a teenager talking like a Victorian — these breaks
pull readers out of the story. Voice checking catches these inconsistencies
before readers do.

## How it works (User perspective)

1. Ensure characters have voice profiles in Knowledge Base
2. Open chapter with dialogue in Editor
3. Click "Check Voice" in toolbar
4. Analysis runs (5-15 seconds)
5. Results panel shows:
   - List of speaking characters
   - Match score percentage for each
   - Color coding: green (good), yellow (fair), red (poor)
6. Click any character to see:
   - Flagged dialogue lines
   - Why each line doesn't match
   - Suggested rewrites
7. Apply suggestions or edit manually

Low scores don't always mean errors — intentional voice changes are valid.
Use your judgment as the author.

## How it works (Technical)

**Entry point:** `writing/router.py` → `POST /api/v1/writing/voice-check/{chapter_id}`
**Service:** `VoiceCheckerService.check()` in `writing/voice_checker_service.py`
**Contract:** `VoiceCheckerProtocol` in `writing/contracts.py`
**LLM Intent:** `LLMIntent.VOICE`

**Voice profile structure** (from KB-001):
```python
class VoiceProfile:
    character_id: UUID
    formality: float  # 0-1, casual to formal
    vocabulary_level: str  # simple, moderate, complex
    sentence_structure: str  # short, medium, long, varied
    verbal_tics: list[str]  # "You know?", etc.
    emotional_range: str  # restricted, moderate, expressive
    cultural_markers: list[str]  # regional, social
    examples: list[str]  # speech samples
```

**Analysis pipeline:**
1. **Extract dialogue** from chapter text
2. **Assign to characters** (by name, context, or attribution)
3. **Compare each line** to character's voice profile:
   - Formality match
   - Vocabulary appropriateness
   - Sentence structure consistency
   - Verbal tic presence/absence
   - Cultural marker alignment
4. **Calculate match score** (weighted average of elements)
5. **Flag outliers** (lines with low individual scores)
6. **Generate suggestions** for flagged lines

**Scoring:**
- Overall score: 0-100% per character
- Line-level scores: individual dialogue passages
- Thresholds: >90% excellent, 70-89% good, 50-69% fair, <50% poor

**Suggestion generation:**
For flagged lines, AI generates rewrite that:
- Preserves meaning/intent
- Aligns with voice profile
- Maintains scene context
- Provides explanation for changes

## Constraints & Edge Cases

- Requires voice profile in KB (create via KB-002 or KB-001)
- Poor profiles = poor checking (garbage in, garbage out)
- Intentional voice changes may be flagged (author discretion)
- Dialogue attribution errors affect accuracy
- Very short dialogue (<10 lines) = unreliable scores
- Sarcasm, irony, lies not detected (taken literally)
- LLM availability required

## Related Features

- [KB-001](../kb/KB-001-entity-management.md) — Voice profiles in KB
- [KB-002](../kb/KB-002-kb-session.md) — Create voice profiles via interview
- [ANAL-008](../analysis/ANAL-008-voice-character.md) — Character voice analysis
- [WRITE-006](WRITE-006-co-author.md) — Rewrite for voice consistency

## Status & History

- `project-init` — Added to registry as planned feature
