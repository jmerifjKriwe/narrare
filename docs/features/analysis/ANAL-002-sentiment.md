---
id: ANAL-002
title: "Sentiment Analysis"
status: in_progress
area: analysis
mvp: false

ui_tooltip: "Track emotional arcs and tone across your story."
ui_help_short: |
  Visualize the emotional journey of your story. Sentiment Analysis tracks
  positive/negative tone, excitement/calm, and dominant/submissive dynamics
  across chapters — helping you see if your emotional arc lands as intended.
ui_help_long: |
  ## Sentiment Analysis

  Track and visualize the emotional landscape of your story chapter by chapter.

  **What gets measured:**

  **VAD Dimensions:**
  - **Valence**: Positive to negative emotional tone (0-1)
  - **Arousal**: Calm to excited state (0-1)
  - **Dominance**: Submissive to dominant stance (0-1)

  **Basic Emotions:**
  Eight emotions with intensity scores:
  - Joy, sadness, anger, fear
  - Surprise, anticipation, trust, disgust

  **Arc Detection:**
  Compare your story's emotional arc against classical patterns:
  - Rags to riches (rise)
  - Tragedy (fall)
  - Man in a hole (fall-rise)
  - Icarus (rise-fall)
  - Cinderella (rise-fall-rise)
  - Oedipus (fall-rise-fall)

  **How it works:**
  1. Select chapters or entire novel
  2. Click "Sentiment Analysis" in Analysis panel
  3. AI analyzes emotional content (5-10 seconds per chapter)
  4. Visualizations appear:
     - Line graph: Emotional arc across chapters
     - Bar chart: Emotion distribution per chapter
     - Arc match: Which classical pattern fits
  5. Hover over any point for details
  6. Click chapter to see specific emotions

  **Use cases:**
  - Verify emotional arc matches intent
  - Identify jarring emotional shifts
  - Ensure climax has highest arousal
  - Check tone consistency within arcs

  **Best practices:**
  - Run after first draft complete
  - Compare segments within chapters
  - Use for revision, not writing
  - Trust your instincts over AI labels

  Sentiment Analysis shows patterns, not prescriptions. Your story doesn't need
  to match classical arcs — but knowing where it diverges helps you make
  intentional choices.
ui_available_in: [analysis]

service: analysis/sentiment_service.py
contract: analysis/contracts.py#SentimentProtocol
router: analysis/router.py
prompt: core/prompts/_bundled/analysis/en/sentiment
requires: [INFRA-001]
---

# ANAL-002 — Sentiment Analysis

## What it does

Analyzes emotional content across chapters using VAD model (Valence, Arousal,
Dominance) and basic emotion classification. Detects classical story arc
patterns and provides visualizations of emotional trajectory.

## Why it exists

Writers intend emotional journeys but may not achieve them. Readers feel
disconnected if the emotional arc doesn't land. Sentiment analysis makes the
emotional trajectory visible, helping writers verify and adjust their story's
emotional impact.

## How it works (User perspective)

1. Select chapters to analyze (or entire novel)
2. Click "Sentiment Analysis" in Analysis panel
3. Choose visualization:
   - **Emotional Arc**: Line graph across chapters
   - **Emotion Distribution**: Bar chart per chapter
   - **Arc Pattern**: Which classical structure fits
4. Analysis runs (5-10 seconds per chapter)
5. Interactive visualizations appear:
   - Hover over points for emotion details
   - Click chapters to see breakdown
   - Compare selected chapters
6. Export charts as images

Use to verify your emotional intent matches reader experience, identify jarring
shifts, or ensure the climax has maximum impact.

## How it works (Technical)

**Entry point:** `analysis/router.py` → `POST /api/v1/analysis/sentiment`
**Service:** `SentimentService.analyze()` in `analysis/sentiment_service.py`
**Contract:** `SentimentProtocol` in `analysis/contracts.py`
**LLM Intent:** `LLMIntent.SENTIMENT`

**Analysis per chapter:**
```python
class SentimentResult:
    chapter_id: UUID
    vad: VADScore  # valence, arousal, dominance (0-1 each)
    emotions: dict[str, float]  # joy, sadness, anger, etc.
    dominant_emotion: str
    intensity: float  # 0-1
```

**Arc detection:**
- Compares chapter-by-chapter VAD trajectory
- Matches against classical arc templates
- Returns best-fit pattern with confidence score
- Identifies arc deviations (unexpected shifts)

**Visualization data:**
```python
class SentimentVisualization:
    arc_line: list[tuple[int, VADScore]]  # (chapter, VAD)
    emotion_bars: dict[int, dict[str, float]]  # chapter → emotions
    arc_pattern: str  # "rags_to_riches", etc.
    confidence: float  # 0-1
```

**Classical arc templates:**
- Rags to riches: Rising valence throughout
- Tragedy: Falling valence throughout
- Man in hole: Fall then rise
- Icarus: Rise then fall
- Cinderella: Rise-fall-rise
- Oedipus: Fall-rise-fall

## Constraints & Edge Cases

- Minimum 500 words per chapter for reliable analysis
- Very short chapters may produce noisy data
- Irony, sarcasm, subtext may be misclassified
- Cultural/emotional context affects interpretation
- Arc detection requires 3+ chapters
- Confidence scores indicate fit, not quality
- LLM availability required

## Related Features

- [ANAL-010](ANAL-010-literary-suite.md) — Thematic analysis
- [ANAL-011](ANAL-011-plot-analysis.md) — Plot arc analysis
- [PLAN-003](../planning/PLAN-003-structure.md) — Structure planning

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-28` — Moved to `in_progress`. Core NLP module (`core/nlp/`) and analysis module (`core/analysis/`) implemented. LexiconSentimentAnalyzer with deterministic VAD + emotion scoring + narrative arc detection. API and frontend implemented (tests pending).
- `2026-05-28` — All spec requirements implemented. Cross-chapter arc trajectory line graph added. Word count + arc minimum warnings added to service. Chart export (PNG download) via html-to-image. Hover tooltips on emotion chart + arc graph. LLMIntent.SENTIMENT confirmed in intents.py. 8 warning tests + 30 rule tests added.
