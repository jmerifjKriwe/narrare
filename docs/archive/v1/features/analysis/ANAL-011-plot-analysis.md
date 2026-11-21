---
id: ANAL-011
title: "Plot Analysis Suite"
status: planned
area: analysis
mvp: false

ui_tooltip: "Arc detection, pacing, conflict mapping, and trope recognition."
ui_help_short: |
  Understand your story's structure. Plot Analysis detects story arcs,
  analyzes pacing, maps conflicts, and recognizes tropes. Four dimensions of
  plot analysis to strengthen your narrative architecture.
ui_help_long: |
  ## Plot Analysis Suite

  Comprehensive plot structure analysis in four dimensions.

  **1. Arc Detection**

  Compare your story against classical structures:
  - **Hero's Journey**: Call to adventure, trials, return
  - **Three-Act Structure**: Setup, confrontation, resolution
  - **Five-Act Structure**: Exposition, rising action, climax, falling action, resolution
  - **Freytag's Pyramid**: Introduction, inciting incident, rising action, climax, falling action, catastrophe/denouement

  **2. Pacing Analysis**

  **Tempo measurement**
  - Fast vs slow chapters
  - Action vs introspection balance
  - Scene length variation

  **Tension curve**
  - Rising/falling tension
  - Climax identification
  - Resolution satisfaction

  **Info-dumping detection**
  - Excessive exposition flagged
  - Telling vs showing balance
  - Worldbuilding integration

  **3. Conflict Mapping**

  **Internal conflicts**
  - Character vs self
  - Emotional struggles
  - Moral dilemmas

  **External conflicts**
  - Character vs character
  - Character vs society
  - Character vs nature

  **Interpersonal conflicts**
  - Relationship struggles
  - Alliance shifts
  - Betrayals and reconciliations

  **4. Trope Recognition**

  **Tropes and clichés**
  - Identifies genre tropes used
  - Recognizes subversions
  - Flags overused patterns
  - Genre-specific analysis

  **How it works:**
  1. Select chapters or entire novel
  2. Click "Plot Analysis" in Analysis panel
  3. Choose dimensions (all four recommended)
  4. AI analyzes (30-90 seconds)
  5. Interactive results:
     - Arc match: Which structure fits, with confidence
     - Pacing chart: Tempo and tension across chapters
     - Conflict map: Types and relationships
     - Tropes list: Used, subverted, or avoided
  6. Export analysis as report

  **Best practices:**
  - Run arc detection early in writing process
  - Use pacing analysis for revision
  - Map conflicts before major plot changes
  - Know your genre's tropes before analyzing

  **Use cases:**
  - Validate story structure
  - Fix pacing problems
  - Ensure conflict variety
  - Avoid or embrace tropes intentionally

  Plot analysis reveals your story's architecture. Strengthen weak foundations,
  reinforce what works, and make intentional choices about structure.

  Note: Arc detection requires 5+ chapters for accuracy.
ui_available_in: [analysis]

service: analysis/plot_service.py
contract: analysis/contracts.py#PlotProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/plot
requires: [INFRA-001, KB-001]
---

# ANAL-011 — Plot Analysis Suite

## What it does

Four-dimensional plot analysis: (1) Arc Detection against classical structures,
(2) Pacing Analysis with tempo and tension curves, (3) Conflict Mapping of
internal/external/interpersonal struggles, (4) Trope Recognition with
subversion detection.

## Why it exists

Plot structure underpins reader satisfaction. Weak arcs, pacing problems, or
confusing conflicts frustrate readers. Plot analysis makes narrative
architecture visible, helping writers strengthen structural foundations.

## How it works (User perspective)

1. Select chapters (or entire novel)
2. Click "Plot Analysis" in Analysis panel
3. Choose dimensions:
   - **Arc Detection**: Which classical structure fits?
   - **Pacing**: Tempo and tension analysis
   - **Conflict Map**: What's at stake?
   - **Tropes**: Genre patterns used
4. Click "Analyze" (30-90 seconds)
5. Results appear per dimension with visualizations:
   - **Arc**: Structure diagram, match percentage
   - **Pacing**: Line graph of tempo/tension
   - **Conflict**: Network diagram of conflicts
   - **Tropes**: List with subversion flags
6. Click any element for details
7. Export analysis as PDF

Use during planning to validate structure, or revision to fix problems.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/plot`
**Service:** `PlotService.analyze()` in `analysis/plot_service.py`
**Contract:** `PlotProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.ANALYSE`

**Arc detection:**
- Extracts plot events from chapters (summarization)
- Compares event sequence to classical templates
- Returns best-fit structure with confidence score
- Identifies arc deviations (missing beats, extra scenes)

**Pacing analysis:**
```python
class PacingAnalysis:
    tempo_scores: list[float]  # Per chapter
    tension_curve: list[float]  # Rising/falling tension
    climax_chapter: int | None  # Peak tension
    info_dumps: list[int]  # Chapters with excessive exposition
```

**Conflict mapping:**
- Extracts conflicts from text (character goals, obstacles)
- Classifies by type (internal, external, interpersonal)
- Maps conflict relationships (A vs B, A vs self, etc.)
- Tracks resolution status

**Trope recognition:**
- Matches patterns against genre trope database
- Classifies as used, subverted, or avoided
- Flags overused or problematic tropes
- Context-aware (what's subverted vs played straight)

## Constraints & Edge Cases

- Arc detection requires 5+ chapters
- Pacing analysis less useful for single chapter
- Conflict extraction may miss subtext
- Trope database may not cover all genres
- Subversive tropes may be misclassified
- Experimental structures won't match classical arcs
- LLM availability required

## Related Features

- [ANAL-002](ANAL-002-sentiment.md) — Emotional arc analysis
- [PLAN-001](../planning/PLAN-001-scene-planning.md) — Scene-level planning
- [PLAN-003](../planning/PLAN-003-structure.md) — Structure visualization
- [ASSIST-001](../ai_assist/ASSIST-001-plot-check.md) — Plot suggestions

## Status & History

- `project-init` — Added to registry as planned feature
