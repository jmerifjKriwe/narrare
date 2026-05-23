# Narrare Prompt Evaluation

> **See [ADR-018](../docs/architecture/decisions/ADR-018-promptfoo-evals.md)
> for architectural context and rationale.**

## What is this?

This directory contains **prompt quality evaluations** — tests that validate the
quality of LLM outputs, not the correctness of code. These are orthogonal to
the pytest suite:

| Test type | Tool | What it validates | LLM calls |
|-----------|------|-------------------|-----------|
| Unit tests | pytest | Code logic, mechanics | Mocked |
| Integration tests | pytest | DB, Redis, service wiring | Mocked |
| E2E tests | pytest + Playwright | Full stack | Mocked |
| **Prompt evals** | **promptfoo** | **Output quality, tone, guardrails** | **Real** |

## Prerequisites

- Node.js ≥ 20 (promptfoo is a Node.js tool)
- An `OPENAI_API_KEY` environment variable (or other configured provider)

Install promptfoo:

```bash
npm install -g promptfoo
# or use npx without global install:
npx promptfoo eval
```

## Running evaluations

```bash
# Run all test cases
npx promptfoo eval

# Run a specific test case
npx promptfoo eval -c evals/testcases/writing-generation.yaml
npx promptfoo eval -c evals/testcases/name-generation.yaml
npx promptfoo eval -c evals/testcases/summarization.yaml
npx promptfoo eval -c evals/testcases/interview.yaml
npx promptfoo eval -c evals/testcases/rewrite.yaml

# Open the Web-UI to view results visually
npx promptfoo view
```

## Directory structure

```
evals/
├── README.md                 ← This file
├── promptfooconfig.yaml      ← Global config (providers, defaults)
├── testcases/                ← YAML test case definitions
│   ├── writing-generation.yaml
│   ├── name-generation.yaml
│   ├── summarization.yaml
│   ├── interview.yaml
│   └── rewrite.yaml
├── baselines/                ← Golden outputs for regression comparison
│   └── README.md
└── results/                  ← Output directory (gitignored)
```

## Baseline strategy

Baselines are committed golden outputs used for regression comparison.

1. Run `npx promptfoo eval` to generate fresh outputs
2. Review the outputs for quality
3. If satisfied, copy results to `baselines/<test-name>-v<version>.json`
4. Future runs compare against these baselines

See `baselines/README.md` for details.

## CI integration

Evaluations run in GitHub Actions:

- **On-demand:** `workflow_dispatch` with optional test filter
- **Nightly:** 3 AM UTC on the main branch

Results are uploaded as artifacts (30-day retention).

## Architecture relationship

```
Quality Gates:
  pytest (code quality)  ← tests/
  check_architecture.py  ← scripts/
  promptfoo (prompt quality) ← evals/     ← YOU ARE HERE
```

All three are independent quality gates. None depends on the others.

## When to add new test cases

- When a new prompt intent is added to `core/prompts/`
- When an existing prompt is significantly reworked
- When a new agent is added that generates user-facing text
