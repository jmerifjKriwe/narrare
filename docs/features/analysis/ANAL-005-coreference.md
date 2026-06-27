---
id: ANAL-005
title: "Coreference Analysis"
status: stable
area: analysis
mvp: false

ui_tooltip: "Resolve pronoun references and track character mentions."
ui_help_short: |
  Coreference Analysis resolves who "he", "she", or "they" refers to in each
  sentence. Tracks which characters appear where, and flags ambiguous
  references that might confuse readers.
ui_help_long: |
  ## Coreference Analysis

  Ensure readers know who "he", "she", or "they" refers to. Ambiguous
  pronoun references confuse readers and break immersion.

  **What gets analyzed:**

  **Pronoun Resolution**
  - Maps each pronoun to its referent (which character)
  - Tracks pronoun chains across sentences
  - Identifies the antecedent for each reference

  **Ambiguity Detection**
  - Flags pronouns with multiple possible referents
  - Highlights sentences where "he" could be either character
  - Shows which character is most likely meant

  **Character Mention Tracking**
  - Maps which characters appear in each scene
  - Tracks character presence (on-screen vs mentioned)
  - Identifies scenes where POV character isn't present

  **Reference Clarity**
  - Scores overall pronoun clarity (0-100%)
  - Flags problematic passages
  - Suggests rephrasing for ambiguous references

  **How it works:**
  1. Select chapter or passage
  2. Click "Coreference" in Analysis panel
  3. Analysis runs (5-15 seconds)
  4. Results show:
     - Character mention map (who appears where)
     - Ambiguous references highlighted in text
     - Pronoun resolution for each sentence
     - Clarity score for passage
  5. Click any ambiguous reference to see:
     - Possible referents
     - Most likely antecedent
     - Suggested rewrites

  **Best practices:**
  - Use during revision, not writing
  - Fix ambiguities before beta readers
  - Repeat character names instead of pronouns when confused
  - Ensure POV character is clear in each sentence

  **Common issues caught:**
  - "He walked toward him" (who is who?)
  - Multiple male characters, only "he" used
  - Character introduced without name, then referenced
  - POV character unclear in pronoun chains

  Clear references keep readers grounded in your scene.
ui_available_in: [analysis]

service: analysis/coreference_service.py
contract: analysis/contracts.py#CoreferenceProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/coreference
requires: [INFRA-001, KB-001]
---

# ANAL-005 — Coreference Analysis

## What it does

Resolves pronoun references to specific characters, tracks character mentions
across scenes, and flags ambiguous pronoun usage. Provides character mention
maps and clarity scoring for passages.

## Why it exists

Ambiguous pronouns frustrate readers. "He walked toward him" — which he is
which? When multiple characters of the same gender are present, unclear
references break immersion. Coreference analysis catches these issues.

## How it works (User perspective)

1. Select chapter or passage to analyze
2. Click "Coreference" in Analysis panel
3. Analysis runs (5-15 seconds)
4. Interactive view shows:
   - Your text with ambiguous references highlighted
   - Character mention map (who appears where)
   - Pronoun resolution for each sentence
5. Click any highlight to see:
   - Possible characters "he/she/they" could refer to
   - Most likely antecedent
   - Suggested rewrites
6. Apply suggestions or edit manually

Use during revision to ensure readers always know who is being referred to.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/coreference`
**Service:** `CoreferenceService.analyze()` in `analysis/coreference_service.py`
**Contract:** `CoreferenceProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.ANALYSE`

**Coreference resolution:**
```python
class CoreferenceResult:
    pronoun: str  # "he", "she", "they", etc.
    position: int  # Character position in text
    referent: str  # Character name
    confidence: float  # 0-1
    is_ambiguous: bool
```

**Ambiguity detection:**
- Counts same-gender characters present in scene
- Flags pronouns with multiple possible antecedents
- Scores ambiguity by distance and salience
- Low confidence = likely ambiguous

**Character mention tracking:**
```python
class CharacterMention:
    character_id: UUID
    character_name: str
    mentions: list[int]  # Positions in text
    scenes_present: list[int]  # Scene indices
    is_pov: bool
```

**Clarity scoring:**
- Percentage of unambiguous pronouns
- Penalizes multiple same-gender characters
- Rewards explicit name usage
- Flags passages below 70% clarity

## Constraints & Edge Cases

- Requires character names to be defined (in KB or text)
- Struggles with intentional ambiguity (sometimes valid)
- First-person "I" not analyzed (trivial)
- Group references ("they all") may be misclassified
- Very long sentences increase ambiguity
- Cultural naming conventions affect accuracy
- LLM availability required

## Related Features

- [ANAL-004](ANAL-004-pov.md) — POV analysis
- [KB-001](../kb/KB-001-entity-management.md) — Character definitions
- [WRITE-006](../writing/WRITE-006-co-author.md) — Apply fixes

## Status & History

- `project-init` — Added to registry as planned feature
- 2026-06-26 — Implemented (status → `stable`): `CoreferenceAgent` (Core,
  `NarrareAgent` with structured output; ANALYSE intent gains the `coreference`
  context_mode; bundled `analysis/en/coreference` template). Backend:
  `CoreferenceService` (Mode 1 PromptComposer), `contracts_coreference.py`,
  `schemas_coreference.py`, SSE `router_coreference.py`
  (`POST /analysis/coreference/{chapter_id}`), `dependencies_coreference.py`.
  Frontend: `CoreferencePanel` + `CoreferenceTrigger` + `useCoreference` hook +
  SSE client (`coreference-stream.ts`), wired into the editor analysis panels;
  i18n (en/de/fr). Tests: 31 Core + 12 Backend + 22 Frontend (verified — no
  skips/TODOs). Implementation, tests, OpenAPI docs, and i18n complete. LLM
  result-accuracy may be iteratively tuned in future releases.
