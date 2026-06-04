# Baseline Strategy

Baselines are committed golden score summaries used for regression comparison.

## How baselines work

1. Run `uv run python -m evals run --suite all --mode smoke` to generate JSON reports.
2. Review report outputs and scores for quality.
3. Run `uv run python scripts/check_eval_drift.py --update-baselines` to store baselines.
4. Future runs compare fresh Pydantic Evals reports against those baselines.

## Versioning

- Baseline filenames follow `<suite>-baseline.json`.
- When suite definitions or evaluators change intentionally, update the baseline.
- Runtime eval baselines should be reviewed manually before replacing smoke baselines.

## Current baselines

_No baselines yet — run the Pydantic Evals smoke command above to generate initial results._
