# Baseline Strategy

Baselines are committed golden outputs used for regression comparison.

## How baselines work

1. Run `npx promptfoo eval` to generate fresh outputs
2. Review the outputs for quality
3. If satisfied, copy the results to `baselines/<test-name>-v<version>.json`
4. Future runs compare against these baselines

## Versioning

- Baselines are versioned (`writing-v1.json`, `names-v1.json`)
- When prompts change intentionally, create a new baseline version
- Keep old baselines for historical comparison

## Current baselines

_No baselines yet — run `npx promptfoo eval` to generate initial results._
