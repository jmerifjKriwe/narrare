---
id: ANAL-010
title: "Literary Analysis Suite"
status: planned
area: analysis
mvp: false

ui_tooltip: "Comprehensive literary analysis: style, themes, comparative, readability."
ui_help_short: |
  Deep literary analysis of your writing. The Suite analyzes style and tone,
  themes and motifs, comparative patterns across chapters, and readability.
  Four analysis types in one comprehensive report.
ui_help_long: |
  ## Literary Analysis Suite

  Comprehensive literary analysis combining four analysis types for deep
  understanding of your craft.

  **1. Comprehensive Literary Analysis**

  **Style & Tone**
  - Narrative voice and perspective
  - Overall tone (dark, hopeful, ironic, etc.)
  - Stylistic devices and techniques
  - Genre adherence

  **Structure & Patterns**
  - Chapter organization
  - Scene construction
  - Pacing and rhythm
  - Literary devices (metaphor, symbolism, etc.)

  **2. Readability Analysis**
  - Flesch Reading Ease score
  - Flesch-Kincaid Grade Level
  - Gunning Fog Index
  - Problematic sentences with AI suggestions

  **3. Thematic Analysis**
  - Major themes and motifs
  - Symbols and imagery
  - Thematic density and distribution
  - Symbol evolution across story

  **4. Comparative Analysis**
  - Writing style across chapters
  - Tone consistency
  - Pacing comparison
  - Voice consistency

  **How it works:**
  1. Select chapters or entire novel
  2. Click "Literary Suite" in Analysis panel
  3. Choose analysis types (all four recommended)
  4. AI generates comprehensive report (1-3 minutes)
  5. Interactive report shows:
     - Executive summary
     - Detailed analysis by type
     - Chapter-by-chapter breakdowns
     - Visualizations and charts
  6. Export report as PDF or Markdown

  **Best practices:**
  - Run after first draft complete
  - Use for revision guidance
  - Compare with genre classics
  - Track changes across revisions

  **Use cases:**
  - Understand your literary strengths and weaknesses
  - Prepare for submission (agent/publisher packets)
  - Guide revision priorities
  - Study your craft systematically

  The Literary Suite is the most comprehensive analysis Narrare offers.
  Combine with Beta Reader Simulation (ANAL-001) for reader perspective.

  Note: Analysis requires LLM with good literary training.
ui_available_in: [analysis]

service: analysis/literary_service.py
contract: analysis/contracts.py#LiteraryProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/literary
requires: [INFRA-001, ANAL-003]
---

# ANAL-010 — Literary Analysis Suite

## What it does

Comprehensive literary analysis combining four analysis types: (1) Style &
Tone analysis, (2) Readability metrics, (3) Thematic analysis, (4) Comparative
analysis across chapters. Generates detailed report with visualizations.

## Why it exists

Writers want to understand their craft — strengths, weaknesses, patterns,
and evolution. Single-purpose analysis tools miss connections. The Literary
Suite provides comprehensive literary understanding in one report.

## How it works (User perspective)

1. Select chapters for analysis (or entire novel)
2. Click "Literary Suite" in Analysis panel
3. Choose analysis types:
   - Style & Tone (recommended)
   - Readability (recommended)
   - Thematic (recommended)
   - Comparative (recommended)
   - Or select "All" for comprehensive report
4. Click "Analyze"
5. Report generates (1-3 minutes depending on length)
6. Interactive report shows:
   - **Executive Summary**: Key findings overview
   - **Style & Tone**: Voice, devices, genre fit
   - **Readability**: Scores with chapter breakdown
   - **Themes**: Major themes, symbols, motifs
   - **Comparative**: Cross-chapter patterns
   - **Visualizations**: Charts and graphs
7. Export as PDF or Markdown

Use for revision guidance, submission preparation, or craft study.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/literary`
**Service:** `LiteraryService.analyze()` in `analysis/literary_service.py`
**Contract:** `LiteraryProtocol` in `analysis/contracts.py`
**LLM Intents:** `LLMIntent.ANALYSE`, `LLMIntent.SENTIMENT`, `LLMIntent.VOICE`

**Analysis types:**
```python
class LiteraryAnalysis:
    style_tone: StyleToneAnalysis
    readability: ReadabilityAnalysis  # From ANAL-003
    themes: ThematicAnalysis
    comparative: ComparativeAnalysis

class StyleToneAnalysis:
    narrative_voice: str  # First, third-limited, omniscient
    tone: str  # Overall tone description
    literary_devices: list[str]  # Metaphor, symbolism, etc.
    genre_adherence: str  # How well fits genre
```

**Thematic analysis:**
- Extract major themes (love, power, redemption, etc.)
- Identify symbols and motifs
- Track theme distribution across chapters
- Analyze symbol evolution and meaning

**Comparative analysis:**
- Style consistency across chapters (see ANAL-009)
- Pacing variation (fast/slow chapters)
- Tone evolution (dark → hopeful, etc.)
- Voice drift detection

## Constraints & Edge Cases

- Minimum 3 chapters required for comparative analysis
- Thematic analysis requires 5000+ words total
- Literary device detection may miss subtle symbols
- Comparative analysis less useful for single chapter
- Report generation is LLM-intensive (slower, costlier)
- Genre assumptions based on frontmatter (may be wrong)
- LLM availability required

## Related Features

- [ANAL-001](ANAL-001-beta-reader.md) — Reader perspective
- [ANAL-003](ANAL-003-readability.md) — Readability component
- [ANAL-007](ANAL-007-voice-author.md) — Voice analysis
- [ANAL-011](ANAL-011-plot-analysis.md) — Plot-focused analysis

## Status & History

- `project-init` — Added to registry as planned feature
