---
id: CR-AUFG-07-23
title: "Emotional Intensity Curve"
status: planned
area: ai-ux
mvp: false
ui_tooltip: "See how emotional intensity rises and falls across the story."
ui_help_short: |
  The Emotional Intensity Curve visualizes existing sentiment-analysis intensity
  and arousal data so writers can inspect pacing without inventing new analytics.
ui_help_long: |
  This feature starts from ANAL-002 data. It does not claim to know reader emotion
  beyond the existing sentiment contract; it visualizes grounded intensity scores
  and warnings already produced by the analysis layer.
ui_available_in: [analysis]
service: apps/api/narrare/analysis/services/sentiment_service.py#ChapterSentimentService
contract: apps/api/narrare/analysis/contracts.py#SentimentService
router: apps/api/narrare/analysis/router.py
prompt: ~
requires: [ANAL-002]
---

# CR-AUFG-07-23 — Emotional Intensity Curve

## Problem / Root cause

**Symptom:** Sentiment Analysis exposes VAD and emotion results, but writers lack a focused intensity visualization for revision pacing.

**Warum 1?** ANAL-002 was designed around sentiment arcs and emotion distribution, not a dedicated “how intense does this feel over time?” review surface.

**Warum 2?** CR-07 Phase C listed the curve as an enhancement, but did not decide whether it should be deterministic, LLM-based, or hybrid.

**Root cause:** The product need is visualization and interpretation of already-grounded emotional intensity, not a new speculative analysis pipeline.

## User-facing behavior and acceptance criteria

- The curve uses existing ANAL-002 `intensity` and/or `arousal` scores as its data source.
- Writers can view chapter-level intensity across selected chapters.
- The chart explains what the score means and what it does not mean.
- Empty/insufficient data shows actionable guidance: run Sentiment Analysis or select enough text/chapters.
- The UI never claims reader certainty; it uses “estimated intensity” language.
- Clicking a point links back to the corresponding chapter/sentiment details when available.

## Architecture fit and layer ownership

| Layer | Ownership |
|-------|-----------|
| Core | No new LLM; uses existing sentiment result model unless a small typed view model is needed. |
| Backend | May expose a read/aggregation endpoint over existing sentiment data if current API cannot serve the chart cleanly. |
| Frontend | Owns chart component, explanatory copy, empty states, and accessibility. |
| Platform | Adds contract/component tests; ensures no ungrounded LLM path is introduced. |
| Docs | Updates ANAL-002 help after implementation. |

## API/contract implications

- Preferred first increment: derive the curve from the existing sentiment response produced by `ChapterSentimentService` through the `SentimentService` contract.
- If backend aggregation is required, explicitly extend `apps/api/narrare/analysis/contracts.py#SentimentService` before implementation with a typed method returning `SentimentIntensityCurveResponse` with points `{chapter_id, chapter_title, order, intensity, arousal, confidence?, warnings}` and matching frontend types.
- No new `LLMIntent` or prompt in the first increment.

## Data model/migration implications

None for the first increment. If sentiment results are not persisted today, the curve is session/result derived rather than stored.

## i18n requirements

- DE/EN/FR keys under `studio.analysis.emotionalIntensity.*` for title, axis labels, score explanation, empty states, insufficient data, warnings, and export labels.

## AI-UX lifecycle requirements

- If it only visualizes existing data, lifecycle is non-AI rendering: loading/error for data fetch only.
- If it triggers Sentiment Analysis, it must use the existing `analysis.sentiment` operation lifecycle with cancel/retry/connection-loss semantics.
- Partial output is not applicable unless sentiment streaming exists later.

## Tests/enforcement gates required

- Unit tests for intensity point derivation from ANAL-002 results.
- Component tests for empty/insufficient/warning states and chart accessibility.
- Contract tests if a backend aggregation schema is added.
- Architecture check/review evidence that no new LLM prompt or unregistered analysis intent was introduced.

## Alternatives considered

1. **New LLM emotional-curve analysis.** Rejected for first increment: unnecessary, costlier, and risks ungrounded analytics.
2. **Manual writer-entered intensity markers only.** Rejected: useful later, but it does not satisfy the requested AI-analysis enhancement.
3. **Existing ANAL-002-derived deterministic curve (chosen).** Best fit: grounded, testable, and no new prompt/model path.

## Explicit out-of-scope

- Segment-level scene curve unless existing data supports it.
- Predicting actual reader emotion with certainty.
- Prescriptive “fix your pacing” rewrites.

## Dependencies/order constraints

- Depends on ANAL-002 stable sentiment data.
- Can be implemented late in Phase C because it does not unblock other AUFGs.
