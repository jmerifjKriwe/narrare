# Narrare Pydantic Evals

**Node.js ≥ 24**

ADR-032 makes Pydantic Evals the active AI evaluation single source of truth.
This package replaces the former YAML/Node eval stack with Python-native suites
that can exercise Narrare runtime paths.

## Active suites

- `kb_extraction` — evaluates entity/relation extraction quality.
- `rewrite_selection` — evaluates rewrite mode routing and usable output.
- `preference_analysis` — evaluates writing-preference signal extraction.
- `consistency_staged` — evaluates ADR-044 fact extraction, contradiction detection,
  and false-positive guards for staged consistency.

## Run smoke evals without provider secrets

```bash
uv run python -m evals run --suite all --mode smoke
```

Smoke mode is deterministic and CI-safe. It validates the Pydantic Evals runner,
datasets, custom evaluators, report serialization, and drift parser without
external API calls.

## Run runtime evals with a configured model

```bash
export NARRARE_EVAL_PROVIDER=openai
export NARRARE_EVAL_MODEL=gpt-5-mini
export NARRARE_EVAL_API_KEY="$OPENAI_API_KEY"
uv run python -m evals run --suite kb_extraction --mode runtime
```

Runtime mode uses Narrare's Python abstractions (`ModelRegistry`, agents, and
structured outputs) rather than a parallel provider layer. Optional variables:

- `NARRARE_EVAL_PROVIDER` (default: `openai`)
- `NARRARE_EVAL_MODEL` (default: `gpt-5-mini`)
- `NARRARE_EVAL_API_KEY` (falls back to `OPENAI_API_KEY`)
- `NARRARE_EVAL_BASE_URL` (for OpenAI-compatible gateways)

Subjective LLM-as-judge scoring is available explicitly and is disabled in CI:

```bash
uv run python -m evals run --suite rewrite_selection --mode runtime \
  --judge-model openai:gpt-5-mini
```

## Directory structure

```text
evals/
├── __main__.py          # python -m evals
├── runner.py            # CLI runner
├── models.py            # typed case input/output models
├── consistency_models.py # ADR-044 staged consistency models
├── datasets/            # code-first Dataset/Case definitions
├── evaluators/          # custom Evaluator implementations
├── tasks/               # smoke and runtime task entrypoints
├── baselines/           # drift baselines
└── results/             # JSON reports uploaded by CI
```

Reports are written as JSON summaries under `evals/results/` and can be compared
with `python scripts/check_eval_drift.py`.
