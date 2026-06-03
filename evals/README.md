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

- Node.js ≥ 24 (promptfoo is a Node.js tool)
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
npx promptfoo eval -c evals/testcases/interview.yaml
npx promptfoo eval -c evals/testcases/kb-extract.yaml
npx promptfoo eval -c evals/testcases/kb-improve.yaml
npx promptfoo eval -c evals/testcases/analysis-consistency.yaml
npx promptfoo eval -c evals/testcases/analysis-beta-reader.yaml
npx promptfoo eval -c evals/testcases/writing-story-suggest.yaml
npx promptfoo eval -c evals/testcases/writing-chat.yaml
npx promptfoo eval -c evals/testcases/writing-generation.yaml
npx promptfoo eval -c evals/testcases/writing-extend.yaml
npx promptfoo eval -c evals/testcases/writing-rewrite.yaml
npx promptfoo eval -c evals/testcases/name-generation.yaml
npx promptfoo eval -c evals/testcases/summarization.yaml
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
│   ├── interview.yaml            KB interview question quality
│   ├── kb-extract.yaml           KB entity extraction from chapter text
│   ├── kb-improve.yaml           KB entry improvement analysis
│   ├── analysis-consistency.yaml Cross-chapter contradiction detection
│   ├── analysis-beta-reader.yaml Beta reader structured feedback
│   ├── writing-story-suggest.yaml Story direction suggestions
│   ├── writing-chat.yaml         Chat scope compliance & craft quality
│   ├── writing-generation.yaml   Full draft mode quality
│   ├── writing-extend.yaml       Chapter continuation quality
│   ├── writing-rewrite.yaml      Selection rewrite quality
│   ├── name-generation.yaml      Culture-specific name generation
│   ├── summarization.yaml        Chapter summarization quality
│   └── rewrite.yaml              Basic rewrite quality
├── baselines/                ← Golden outputs for regression comparison
│   └── README.md
└── results/                  ← Output directory (gitignored)
```

## Test case overview

### KB (Knowledge Base) Prompts

| Test case | Production prompt | What it tests |
|-----------|------------------|---------------|
| `interview.yaml` | `kb/en/interview/system.md` | Single focused questions for KB entry building |
| `kb-extract.yaml` | `kb/en/extract/system.md` | Entity/relationship/conflict extraction from chapter text |
| `kb-improve.yaml` | `kb/en/improve/system.md` | Identifying gaps and improvement opportunities in KB entries |

### Analysis Prompts

| Test case | Production prompt | What it tests |
|-----------|------------------|---------------|
| `analysis-consistency.yaml` | `analysis/en/consistency/system.md` | Cross-chapter contradiction and timeline checking |
| `analysis-beta-reader.yaml` | `analysis/en/beta_reader/system.md` | Structured reader-perspective feedback with scoring |

### Writing Prompts

| Test case | Production prompt | What it tests |
|-----------|------------------|---------------|
| `writing-story-suggest.yaml` | `writing/en/story_suggest/system.md` | 3-5 narrative direction suggestions |
| `writing-chat.yaml` | `writing/en/chat/system.md` | Scope compliance (writing scope in, other topics out) |
| `writing-generation.yaml` | (general) | Full narrative draft quality |
| `writing-extend.yaml` | (general) | Seamless chapter continuation |
| `writing-rewrite.yaml` | (general) | Selection rewriting with voice matching |
| `name-generation.yaml` | `generation/en/names/system.md` | Culture-specific name diversity |
| `summarization.yaml` | `analysis/en/summarize/system.md` | Chapter summary conciseness |
| `rewrite.yaml` | (general) | Basic text rewriting quality |

### Relationship to Prompt Engineering Standard

Each inline prompt in the test cases is derived from the corresponding production
prompt in `packages/core/narrare_core/prompts/_bundled/`. The YAML frontmatter
and `{{variable}}` references are preserved to match production behavior.

When bundled prompts are updated, the corresponding eval test cases should be
reviewed and updated to stay in sync. Each test file header contains a comment
with the production prompt path for traceability.

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
