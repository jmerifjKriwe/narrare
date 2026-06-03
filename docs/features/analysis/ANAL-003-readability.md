---
id: ANAL-003
title: "Readability Analysis"
status: stable
area: analysis
mvp: false

ui_tooltip: "Analyze text complexity and get AI-powered simplification suggestions."
ui_help_short: |
  Check if your prose is too complex or too simple for your target audience.
  Combines industry-standard metrics (Flesch, Kincaid) with AI suggestions
  that improve clarity while preserving your voice.
ui_help_long: |
  ## Readability Analysis

  Ensure your prose matches your genre and audience. Readability Analysis
  combines mathematical metrics with AI feedback to help you write clearly
  without sacrificing style.

  **Metrics calculated:**

  **Flesch Reading Ease** (0-100)
  - Higher = easier to read
  - 90-100: Very easy (5th grade)
  - 60-70: Standard (8th-9th grade)
  - 0-30: Very difficult (academic)

  **Flesch-Kincaid Grade Level** (0-18)
  - School grade level needed to understand
  - 6-8: Young Adult
  - 8-10: Commercial fiction
  - 12-16: Literary fiction

  **Gunning Fog Index** (0-20)
  - Years of education required
  - Accounts for complex words
  - Higher = more complex

  **AI-powered features:**

  **Problematic sentence identification**
  - Flags specific sentences that are difficult
  - Explains why (length, complexity, ambiguity)
  - Shows word/syllable counts

  **Rewrite suggestions**
  - Provides 2-3 alternatives per difficult sentence
  - Preserves meaning and voice
  - Shows improvement in metrics

  **Genre benchmarks:**
  - Middle Grade: 80-90 Flesch, Grade 4-6
  - Young Adult: 70-85, Grade 6-8
  - Commercial Fiction: 60-75, Grade 7-9
  - Literary Fiction: 50-70, Grade 8-12

  **How it works:**
  1. Select passage or chapter
  2. Click "Readability" in Analysis panel
  3. Metrics appear instantly (formula-based)
  4. AI analysis completes in 5-15 seconds
  5. See:
     - Overall scores
     - Genre comparison
     - Problematic sentences highlighted
     - Rewrite suggestions
  6. Apply suggestions or edit manually

  **Best practices:**
  - Use during revision, not first draft
  - Balance variety and consistency
  - Simplify without dumbing down
  - Target appropriate complexity for your genre

  Good readability doesn't mean simple writing. It means clear, appropriate
  complexity for your audience.
ui_available_in: [editor, analysis]

service: analysis/readability_service.py
contract: analysis/contracts.py#ReadabilityAnalyzer
agent: core/analysis/readability_agent.py#ReadabilityAgent
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/readability
requires: [INFRA-001, INFRA-002]
---

# ANAL-003 — Readability Analysis

## What it does

Combines formula-based readability metrics (Flesch Reading Ease, Flesch-Kincaid
Grade Level, Gunning Fog Index) with AI-powered sentence analysis and rewrite
suggestions. Identifies problematic sentences and provides improvements that
preserve voice.

## Why it exists

Writers may unintentionally write prose that's too complex or too simple for
their target audience. Mathematical metrics identify overall complexity but
don't explain specific problems or offer solutions. AI analysis fills this gap
with actionable suggestions.

## How it works (User perspective)

1. Select passage or chapter to analyze
2. Click "Readability" in Analysis panel
3. Results appear in two parts:
   - **Metrics** (instant): Flesch, Kincaid, Fog scores
   - **AI Analysis** (5-15s): Problematic sentences + suggestions
4. Compare scores to genre benchmarks
5. Click any highlighted sentence to see:
   - Why it's difficult
   - Word/syllable breakdown
   - 2-3 rewrite suggestions
6. Apply suggestion or edit manually
7. Re-run analysis to verify improvements

Use during revision to ensure your prose matches your genre and audience.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/readability`
**Service:** `ReadabilityService.analyze()` in `analysis/readability_service.py`
**Contract:** `ReadabilityProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.ANALYSE` (for sentence-level analysis)

**Formula-based metrics** (instant):
```python
class ReadabilityMetrics:
    flesch_reading_ease: float  # 0-100
    flesch_kincaid_grade: float  # 0-18
    gunning_fog: float  # 0-20
    avg_sentence_length: float
    avg_syllables_per_word: float
    complex_word_ratio: float
```

**AI sentence analysis:**
```python
class SentenceAnalysis:
    sentence: str
    position: int  # in chapter
    issues: list[str]  # "too long", "complex vocabulary", etc.
    readability_score: float  # 0-1, lower = harder
    suggestions: list[str]  # 2-3 rewrite alternatives
```

**Genre benchmarks:**
- Middle Grade: Flesch 80-90, Grade 4-6
- Young Adult: Flesch 70-85, Grade 6-8
- Commercial: Flesch 60-75, Grade 7-9
- Literary: Flesch 50-70, Grade 8-12

**Suggestion generation:**
- Simplifies vocabulary
- Breaks long sentences
- Removes unnecessary complexity
- Preserves core meaning and voice

## Constraints & Edge Cases

- Metrics less accurate for < 100 words
- Formula-based metrics ignore context
- Poetry/stylized prose may score poorly intentionally
- Suggestions may change tone or voice
- Genre benchmarks are generalizations, not rules
- AI suggestions require LLM availability
- Very long sentences (>50 words) always flagged

## Related Features

- [ANAL-010](ANAL-010-literary-suite.md) — Comprehensive literary analysis
- [WRITE-004](../writing/WRITE-004-rewrite.md) — Apply readability fixes
- [ANAL-001](ANAL-001-beta-reader.md) — Reader perspective

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-27` — Follow-up identified: integrate deterministic readability metrics into Beta Reader (ANAL-001) as a "Computed metrics" section. See ADR-021 hybrid feature pattern.
- `2026-06-01` — Contracts defined: ``ReadabilityAnalyzer`` (deterministic protocol),
  ``ReadabilityAgentProtocol`` (LLM-based protocol), ``ReadabilityServiceProtocol``
  (API service protocol).  Types defined: ``ReadabilityMetrics``,
  ``SentenceAnalysis``, ``ReadabilityResult``.
- 2026-06-01 — Full stack implemented (Core: FormulaReadabilityAnalyzer + ReadabilityAgent, Backend: ReadabilityService + POST /analysis/readability, Frontend: ReadabilityPanel). Contracts split for RULE-04. Status: stable.
