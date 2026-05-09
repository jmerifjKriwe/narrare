---
id: ASSIST-001
title: "Plot Consistency Check"
status: planned
area: ai_assist
mvp: false

ui_tooltip: "Analyze plot structure, arcs, pacing, conflicts, and tropes."
ui_help_short: |
  Comprehensive plot analysis that identifies structural patterns, detects
  classical arcs, analyzes pacing, maps conflicts, and recognizes genre
  tropes — helping you understand and refine your story's architecture.
ui_help_long: |
  ## Plot Consistency Check

  Comprehensive analysis of your plot across four dimensions:

  **Arc Detection**
  Compare against classical structures:
  - Hero's Journey
  - Three-Act Structure
  - Five-Act Structure
  - Freytag's Pyramid

  **Pacing Analysis**
  - Tempo measurement across chapters
  - Tension curve visualization
  - Info-dumping detection

  **Conflict Mapping**
  - Internal conflicts (character vs. self)
  - External conflicts (character vs. world)
  - Interpersonal conflicts (character vs. character)
  - Conflict connections and escalation

  **Trope Recognition**
  - Identifies tropes and clichés
  - Recognizes subversions and deconstructions
  - Genre-specific analysis

  **How it works:**
  1. Select chapters or entire novel
  2. Choose analysis dimension(s)
  3. AI scans content (10-30 seconds)
  4. Results appear grouped by dimension:
     - **Arc Detection**: Shows closest classical structure match
     - **Pacing**: Highlights slow/fast sections
     - **Conflicts**: Maps all conflict threads
     - **Tropes**: Lists identified tropes with context
  5. Click any finding for details and suggestions

  **Best practices:**
  - Run arc detection early in writing process
  - Use pacing analysis during revision
  - Map conflicts before major plot changes
  - Combine with storyboard for plan vs actual comparison

  Available in Analysis panel or via CLI:
  `narrare analysis plot --novel <id> --dimension arcs`
ui_available_in: [analysis, cli]

service: analysis/plot_service.py
contract: analysis/contracts.py#PlotCheckProtocol
router: analysis/router_novel.py
prompt: core/prompts/_bundled/analysis/en/plot
requires: [INFRA-001, INFRA-002]
---

# ASSIST-001 — Plot Consistency Check

## What it does

Comprehensive plot structure analysis including arc detection, pacing analysis, conflict mapping, and trope recognition. Compares against classical narrative structures and provides actionable insights for story refinement.

## Why it exists

Plot problems are hard to see while writing. Pacing drags, conflicts lose steam, structural patterns emerge unintentionally. Plot analysis makes these invisible patterns visible, helping writers understand their story's architecture and make informed revision decisions.

## How it works (User perspective)

1. Open Analysis panel
2. Click "Plot Analysis"
3. Select analysis dimension(s):
   - **Arc Detection**: Match against classical structures
   - **Pacing**: Find slow/fast sections
   - **Conflicts**: Map all conflict threads
   - **Tropes**: Identify genre conventions
4. Choose scope (current chapter, selected chapters, entire novel)
5. AI analyzes content (10-30 seconds)
6. Results appear grouped by dimension with:
   - Overall assessment and match scores
   - Chapter-by-chapter breakdowns
   - Specific findings with locations
   - Suggestions for improvement

## How it works (Technical)

**Entry point:** `ai_assist/router.py` → `POST /api/v1/ai_assist/plot-check`
**Service:** `PlotCheckService.analyze()` in `ai_assist/plot_service.py`
**Contract:** `PlotCheckProtocol` in `ai_assist/contracts.py`
**LLM Intent:** `LLMIntent.ANALYZE`

**Analysis types:**
```python
class PlotAnalysisResult:
    dimension: AnalysisDimension  # arc, pacing, conflict, trope
    findings: list[PlotFinding]
    overall_score: float  # 0-1
    suggestions: list[str]
```

**Arc detection:**
- Compares story beat sequence against classical templates
- Scores match quality for each structure type
- Identifies missing or misplaced beats
- Suggests structural adjustments

**Pacing analysis:**
- Measures tempo by events per chapter
- Analyzes sentence length variation
- Detects dialogue vs narration balance
- Flags potential info-dumps

**Conflict mapping:**
- Identifies conflict types through keyword analysis
- Tracks conflict threads across chapters
- Maps character relationships and tensions
- Detects unresolved or dropped conflicts

**Trope recognition:**
- Matches patterns against trope database
- Identifies subversions and deconstructions
- Provides context for each trope usage
- Suggests alternatives for overused tropes

## Constraints & Edge Cases

- Arc detection requires 5+ chapters for accuracy
- Pacing analysis is genre-dependent (romance vs thriller)
- Trope recognition limited to database of known tropes
- May flag intentional subversions as problems
- Context required for conflict type classification
- LLM availability required for analysis
- Results are suggestions, not prescriptions

## Related Features

- [ANAL-011](../analysis/ANAL-011-plot-analysis.md) — Comprehensive plot suite
- [PLAN-003](../planning/PLAN-003-structure.md) — Structure visualization
- [PLAN-005](../planning/PLAN-005-storyboard.md) — Plan vs actual tracking
- [WRITE-001](../writing/WRITE-001-editor.md) — Chapter content source

## Status & History

- `project-init` — Added to registry as planned feature
