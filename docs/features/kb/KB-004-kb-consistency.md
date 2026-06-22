---
id: KB-004
title: "AI: KB Consistency Check"
status: stable
area: kb
mvp: false

ui_tooltip: "Find contradictions and inconsistencies in your Knowledge Base."
ui_help_short: |
  Run a consistency check on your Knowledge Base to find contradictions,
  conflicting information, and inconsistencies between related entities.
  The AI flags problems and suggests resolutions.
ui_help_long: |
  ## KB Consistency Check

  As your story grows, inconsistencies creep in. A character's eye color changes
  between entries. A location is described differently. Timeline events don't
  align. The KB Consistency Check finds these problems before your readers do.

  **What the check analyzes:**

  **Internal consistency**
  - Conflicting facts within a single entry
  - Contradictory statements
  - Impossible combinations (e.g., died twice)

  **Cross-entity consistency**
  - Character relationships that conflict (A is B's friend, B hates A)
  - Timeline misalignments
  - Location distances that don't make sense
  - Faction memberships that conflict

  **Logical consistency**
  - Ages that don't match birth years
  - Events that couldn't happen in stated timeframe
  - Parent/child relationships with impossible ages

  **How it works:**
  1. Open Knowledge Base → click "Check Consistency"
  2. AI scans all entries and relationships
  3. Issues flagged by severity:
     - **Error**: Impossible contradictions
     - **Warning**: Likely inconsistencies
     - **Info**: Minor discrepancies
  4. For each issue, see:
     - What's conflicting
     - Which entries are involved
     - Suggested resolution
  5. Fix issues manually or apply suggestions

  **Best practice:** Run after major revisions or before publishing.
ui_available_in: [kb]

service: kb/consistency_service.py
contract: kb/consistency_contracts.py#KBConsistencyProtocol
router: kb/router.py
prompt: core/prompts/_bundled/kb/en/consistency
requires: [KB-001, KB-007]
---

# KB-004 — AI: KB Consistency Check

## What it does

Automated consistency analysis of Knowledge Base entries. Detects contradictions,
conflicting relationships, timeline misalignments, and logical impossibilities.
Provides severity ratings and resolution suggestions.

## Why it exists

KBs grow organically. Details get added, changed, or forgotten. What was true
in chapter 1 might be contradicted in chapter 20. Manual review is tedious and
error-prone. Automated checking catches problems human eyes miss.

## How it works (User perspective)

1. Open Knowledge Base panel
2. Click "Check Consistency" button
3. Progress indicator shows analysis (may take 30s-2min for large KBs)
4. Results appear grouped by severity:
   - 🔴 Errors: Impossible contradictions
   - 🟡 Warnings: Likely inconsistencies
   - 🔵 Info: Minor discrepancies
5. Click any issue to see details and resolution options
6. Apply fixes or edit entries manually

Run anytime after making significant changes to your KB.

## How it works (Technical)

**Entry point:** `kb/router.py` → `POST /api/v1/kb/consistency-check`
**Service:** `KBAnalyzerService.check_consistency()` in `kb/analyzer_service.py`
**Contract:** `KBAnalyzerProtocol` in `kb/contracts.py`
**LLM Intent:** `LLMIntent.CONSISTENCY`

**Analysis pipeline:**
1. **Extract facts** from all KB entries (via KB-007)
2. **Compare related facts** for contradictions
3. **Validate logical constraints** (ages, dates, relationships)
4. **Check relationship consistency** (A→B implies B←A)
5. **Flag issues** with severity scores
6. **Generate resolutions** for each issue

**Issue types detected:**
- **Direct contradiction**: "X is true" and "X is false"
- **Relationship asymmetry**: A lists B as friend, B lists A as enemy
- **Timeline impossibility**: Event B before Event A, but B requires A
- **Age mismatch**: Character age inconsistent with birth year
- **Location conflict**: Same place with incompatible descriptions

**Issue format:**
```python
class ConsistencyIssue:
    severity: "error" | "warning" | "info"
    type: str  # contradiction, timeline, relationship, etc.
    description: str
    entities: list[UUID]  # affected KB entries
    conflicting_facts: list[str]
    suggested_resolution: str
```

## Constraints & Edge Cases

- Analysis requires LLM — slower than pure rule-based checks
- May flag intentional ambiguities as errors
- Relationship checking limited to direct connections (1 hop)
- Timeline checking requires dates/ages to be specified
- Large KBs (500+ entries) may take several minutes
- False positives possible — human review recommended

## Related Features

- [KB-001](KB-001-entity-management.md) — Entries being checked
- [KB-007](KB-007-extraction.md) — Fact extraction prerequisite
- [CONS-001](../consistency/CONS-001-checker.md) — Chapter-level consistency
- [PLAN-004](../planning/PLAN-004-timeline.md) — Timeline consistency

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-06-10` — Fully implemented and promoted to stable. KB consistency check with internal/cross-entity/logical analysis, severity ratings, resolution suggestions. KBAnalyzerService, KBAnalyzerProtocol contract, consistency prompt, `/api/v1/kb/consistency-check` endpoint.
