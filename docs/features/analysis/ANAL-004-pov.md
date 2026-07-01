---
id: ANAL-004
title: "POV Analysis"
status: stable
area: analysis
mvp: false

ui_tooltip: "Detect POV character, head-hopping, and knowledge leakage."
ui_help_short: |
  Ensure your POV is consistent. POV Analysis identifies which character's
  perspective each scene uses, flags unintentional head-hopping, and catches
  knowledge/emotional leakage — when POV knows things they shouldn't.
ui_help_long: |
  ## POV Analysis

  Maintain narrative consistency by tracking Point-of-View character usage
  and detecting common POV problems.

  **What gets detected:**

  **POV Character Identification**
  - Which character's perspective each scene uses
  - POV distribution across chapter/novel
  - POV character switches (intentional or not)

  **Head-Hopping Detection**
  - Mid-scene POV switches (problematic)
  - Sudden knowledge from other perspectives
  - Emotional responses from non-POV characters

  **Knowledge Leakage**
  - POV knows things they haven't learned
  - Information from scenes POV didn't witness
  - Future knowledge revealed prematurely

  **Emotional Leakage**
  - Non-POV character's feelings described
  - Thoughts attributed to wrong character
  - Reactions POV couldn't observe

  **Physical Impossibility**
  - POV sees/hears things beyond their senses
  - POV in two places at once
  - POV observes themselves objectively

  **Analysis types:**
  - **Single-character POV**: Third person limited
  - **Omniscient POV**: Access to multiple thoughts
  - **First-person POV**: "I" narration
  - **Head-hopping**: Problematic mid-scene switches

  **How it works:**
  1. Select chapters to analyze
  2. Specify POV type (or auto-detect)
  3. Click "POV Analysis" in Analysis panel
  4. Results show:
     - POV character per scene
     - Distribution chart
     - Flagged issues with locations
     - Explanations of each problem
  5. Click any issue for details and fix suggestions

  **Statistics provided:**
  - POV distribution percentages
  - Switch frequency analysis
  - Character POV mapping
  - Problematic scene identification

  **Best practices:**
  - Know your POV type and stick to it
  - Use scene breaks for intentional POV switches
  - Check consistency during revision
  - Fix head-hopping before beta readers

  POV violations pull readers out of the story. This tool helps you catch them
  before your readers do.
ui_available_in: [analysis]

service: analysis/services/pov_service.py
contract: analysis/contracts.py#POVDetector
agent: core/agents/pov_agent.py#POVDetectionAgent
router: analysis/router.py
prompt: ADR-048 Mode 2 (agent-internal — no bundled cascade prompt)
requires: [INFRA-001, INFRA-002, KB-001]
---

# ANAL-004 — POV Analysis

## What it does

Detects POV character per scene, identifies head-hopping (unintentional mid-scene
POV switches), and flags knowledge/emotional leakage. Provides POV
distribution statistics and issue explanations.

## Why it exists

POV inconsistencies break reader immersion. Head-hopping (jumping between
characters' thoughts within a scene) confuses readers about whose perspective
they're experiencing. POV analysis catches these problems early.

## How it works (User perspective)

1. Select chapters to analyze
2. Specify POV type (Single-character, Omniscient, First-person, or Auto-detect)
3. If single-character: specify which character is POV
4. Click "POV Analysis" in Analysis panel
5. Analysis runs (10-30 seconds depending on length)
6. Results show:
   - **POV Map**: Which character's POV each scene uses
   - **Distribution**: Percentage breakdown by character
   - **Issues**: Flagged problems with chapter/line references
7. Click any issue to see:
   - Explanation of the problem
   - Why it violates POV
   - Suggested fix

Use during revision to ensure POV consistency before beta readers.

## How it works (Technical)

**Entry point:** `apps/api/narrare/analysis/router_pov.py` → `POST /api/v1/analysis/pov`
**Service:** `POVService.analyze()` in `apps/api/narrare/analysis/services/pov_service.py`
**Contract:** `POVDetector` in `apps/api/narrare/analysis/contracts_pov.py`
**Architecture per ADR-021:** Hybrid — pronoun/scene detection is deterministic (spaCy), head-hopping detection requires LLM understanding.

**Deterministic analysis** (spaCy-based, no LLM):
- Pronoun analysis: spaCy POS tagging identifies he/she/they/I references
- Scene detection: Splits chapter by section breaks, `***`, or clear shifts
- POV character identification per scene
- POV distribution statistics

**LLM-powered analysis:**
- Head-hopping detection: identifies mid-scene POV switches
- Knowledge leakage detection: POV knows things they shouldn't
- Emotional leakage detection: non-POV character feelings described
- Fix suggestions for each issue

**LLM Intent:** `LLMIntent.ANALYSE` (for head-hopping and leakage detection only)

**Scene detection:**
- Splits chapter into scenes (by section breaks, `***`, or clear shifts)
- Identifies POV character for each scene
- Tracks POV changes between scenes

**Issue detection:**
```python
class POVIssue:
    type: "head_hop" | "knowledge_leak" | "emotional_leak" | "physical_impossibility"
    location: str  # Chapter/line reference
    explanation: str  # What's wrong
    suggestion: str  # How to fix
    severity: "error" | "warning"
```

**Analysis types:**
- **Single-character POV**: All scenes should use one character's perspective
- **Omniscient**: Multiple POVs allowed, but not within scenes
- **First-person**: All "I" references must be same character
- **Head-hopping**: Flag any mid-scene POV switches

**Detection methods:**
- Pronoun analysis (he/she/they/I references) — deterministic, spaCy
- Thought attribution (who thinks what) — LLM
- Knowledge boundaries (what POV could know) — LLM
- Emotional attribution (whose feelings are described) — LLM

## Constraints & Edge Cases

- Requires clear scene structure (ambiguous scenes = errors)
- Omniscient POV may produce false positives
- First-person with unreliable narrator tricky to analyze
- Dialogue attribution can confuse POV detection
- Intentional POV shifts must use scene breaks to avoid flags
- Free indirect discourse may be flagged as head-hopping
- Pronoun/scene detection works without LLM (deterministic). Head-hopping and leakage detection require LLM availability.

## Related Features

- [ANAL-005](ANAL-005-coreference.md) — Character reference resolution
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — POV in chapter frontmatter
- [KB-001](../kb/KB-001-entity-management.md) — Character definitions

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-06-01` — Contracts defined: ``POVDetector`` (LLM-based protocol),
  ``POVServiceProtocol`` (API service protocol).  Types defined:
  ``POVIssueType`` (enum), ``POVIssue``, ``POVScene``, ``POVResult``.
- 2026-06-01 — Full stack implemented (Core: POVDetectionAgent, Backend: POVService + POST /analysis/pov, Frontend: POVPanel). Contracts split for RULE-04. Status: stable.
- `2026-06-22` — ADR-021 applied: documented hybrid architecture (deterministic pronoun detection + LLM head-hopping analysis)
