---
id: CONS-001
title: "Consistency Checker"
status: in_progress
area: consistency
mvp: false

ui_tooltip: "Find contradictions in characters, timeline, world facts, and plot."
ui_help_short: |
  Comprehensive consistency analysis across characters, timeline, world facts,
  and plot logic. Identifies contradictions, impossible events, and knowledge
  leaks before readers notice them.
ui_help_long: |
  ## Consistency Checker

  Catch inconsistencies before your readers do.

  **What gets checked:**

  **Character Consistency**
  - Behavior matches established personality
  - Voice remains consistent across dialogue
  - Knowledge appropriate to character
  - Abilities and limitations respected
  - Physical traits maintained

  **Timeline Consistency**
  - Events happen in possible sequence
  - Durations make logical sense
  - Character ages align with events
  - Time jumps are acknowledged
  - Past/future events referenced correctly

  **World Consistency**
  - Location properties maintained
  - System rules followed (magic, tech)
  - Faction relationships consistent
  - Geography and travel times match
  - World facts remain stable

  **Plot Consistency**
  - Cause and effect chains complete
  - Character motivations clear
  - Setup receives payoff
  - Loose ends intentional
  - Parallel plots connect logically

  **How it works:**
  1. Select check type(s) or run all
  2. Choose scope (chapter, selection, entire novel)
  3. AI extracts facts and compares (10-45 seconds)
  4. Issues grouped by severity:
     - **Error**: Impossible contradictions
     - **Warning**: Likely inconsistencies
     - **Info**: Minor discrepancies
  5. For each issue:
     - What was found and where
     - Why it's a problem
     - Suggested fixes
  6. Apply fixes or dismiss as intentional

  **Best practices:**
  - Run after major writing sessions
  - Check both within and across chapters
  - Use warnings to guide revision priorities
  - Update KB when fixing inconsistencies
  - Some inconsistencies are intentional (know your story)

  Available in Analysis panel or via CLI:
  `narrare consistency check --novel <id> --type character`
ui_available_in: [analysis, cli]

service: consistency/checker_service.py
contract: consistency/contracts.py#ConsistencyCheckerProtocol
router: consistency/router.py
prompt: core/prompts/_bundled/consistency/en/check
requires: [INFRA-001, INFRA-002, KB-001, KB-007]
---

# CONS-001 — Consistency Checker

## What it does

Comprehensive consistency analysis across characters, timeline, world facts, and plot logic. Extracts facts from Knowledge Base and chapters, compares for contradictions, and flags issues with severity-rated suggestions.

## Why it exists

Readers notice inconsistencies. Characters change personality between chapters, timelines contradict themselves, world rules shift, and plot holes appear. These errors break immersion and trust. Consistency checking catches problems before publication.

## How it works (User perspective)

1. Open Analysis panel → Consistency
2. Select check type(s):
   - **Character**: Behavior, voice, knowledge, abilities
   - **Timeline**: Event sequencing, durations, ages
   - **World**: Locations, systems, factions
   - **Plot**: Cause/effect, motivations, loose ends
3. Choose scope (current chapter, selected, entire novel)
4. Click "Run Consistency Check"
5. AI extracts and compares facts (10-45 seconds)
6. Issues appear grouped by severity:
   - 🔴 Error: Impossible contradictions
   - 🟡 Warning: Likely inconsistencies
   - 🔵 Info: Minor discrepancies
7. Click any issue for:
   - What was found and location
   - Why it's a problem
   - Suggested fixes
8. Apply fix, mark as intentional, or dismiss

## How it works (Technical)

**Entry point:** `consistency/router.py` → `POST /api/v1/consistency/check`
**Service:** `ConsistencyCheckerService.check()` in `consistency/checker_service.py`
**Contract:** `ConsistencyCheckerProtocol` in `consistency/contracts.py`
**LLM Intent:** `LLMIntent.ANALYZE`

**Consistency issue:**
```python
class ConsistencyIssue:
    type: ConsistencyType  # character, timeline, world, plot
    severity: "error" | "warning" | "info"
    description: str  # What's inconsistent
    locations: list[str]  # Where contradictions appear
    facts: list[Fact]  # Conflicting facts
    suggestion: str  # How to fix
```

**Fact extraction:**
- Rule-based: Pull from structured KB fields
- AI-assisted: Extract from unstructured prose
- Deduplication: Remove duplicate facts
- Confidence scoring: Green (high), yellow (medium), red (low)

**Comparison logic:**
- Direct contradictions: "A is true" vs "A is false"
- Temporal contradictions: Event ordering impossible
- Property contradictions: Character traits conflict
- Knowledge contradictions: Character knows something they shouldn't

## Constraints & Edge Cases

- Requires KB to be populated for best results
- Fact extraction may miss implicit information
- Some contradictions are intentional (unreliable narrators)
- Timeline analysis requires explicit temporal markers
- Character voice analysis requires dialogue samples
- May flag stylistic choices as inconsistencies
- LLM availability required
- False positives possible (human review needed)

## Related Features

- [KB-001](../kb/KB-001-entity-management.md) — Entity definitions
- [KB-007](../kb/KB-007-extraction.md) — Fact extraction
- [CONS-002](CONS-002-rules.md) — Custom consistency rules
- [PLAN-004](../planning/PLAN-004-timeline.md) — Timeline management
- [ANAL-005](../analysis/ANAL-005-coreference.md) — Coreference resolution

## Status & History

- `project-init` — Added to registry as planned feature
