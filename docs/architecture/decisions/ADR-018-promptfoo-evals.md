# ADR-018 — promptfoo Eval Framework for Prompt Quality

> **Status:** ✅ Accepted
> **Date:** 2026-05-23
> **Deciders:** Platform Specialist
> **Related:** ADR-001 (LLM Gateway), ADR-002 (Prompt System)

---

## Context

Narrare's current test infrastructure covers **code quality** (pytest with
unit/integration/E2E layers) but not **prompt quality**. Unit tests mock LLM
calls via `TestModel`/`FunctionModel` and validate prompt mechanics —
composition, routing, tool-call structure. They cannot detect qualitative
regressions in LLM output.

When a writing prompt is changed, there is no safety net that catches:
- Degraded narrative quality (repetitive phrasing, tone drift)
- Broken guardrails (AI disclaimers leaking into creative output)
- Scoring regression (LLM-rubric scores dropping below threshold)

An audit classified this gap as **"Problematisch, baldiger Handlungsbedarf"**
(⭐⭐ priority). For an LLM-heavy creative writing product, this is a critical
blind spot.

---

## Decision Drivers

- **Qualitative regression detection** — Prompt changes should not silently
  degrade output quality
- **Reproducibility** — Evals must run the same way locally and in CI
- **CI integration** — Automated runs on schedule and on-demand
- **Low overhead** — Must not impact existing pytest infrastructure
- **LLM-native scoring** — Pass/fail is insufficient; need graded rubrics,
  similarity scores, and LLM-as-judge patterns

---

## Options Considered

### Option A — promptfoo (chosen)

Purpose-built prompt evaluation framework with YAML test cases, Web-UI,
regression tracking, custom providers, and built-in assertion types
(`llm-rubric`, `similar`, `contains`, custom JS/Python).

**Pros:**
- Purpose-built for exactly this problem
- Built-in assertion types for LLM output quality
- Web-UI for visual result comparison
- Regression tracking against golden baselines
- Custom provider support (can route through Narrare Gateway later)
- YAML-based test cases — readable, reviewable, diffable
- Active community and well-maintained

**Cons:**
- New Node.js dependency (isolated in `evals/`)
- Separate tool from pytest (different invocation, different reporting)
- Requires real LLM API calls (costs money per run)

### Option B — Custom pytest + LLM-as-judge

Build custom pytest fixtures that call the LLM and use a second LLM call to
score the output.

**Pros:**
- No new tool dependency
- Integrated with existing pytest reporting
- Full Python ecosystem

**Cons:**
- Must build scoring, comparison, regression tracking, and reporting from
  scratch
- No Web-UI for visual comparison
- Custom maintenance burden
- Reinventing what promptfoo already does well

### Option C — No eval framework (status quo)

Accept the risk that prompt changes may cause qualitative regressions
undetected until users notice.

**Pros:**
- Zero implementation effort

**Cons:**
- LLM-heavy product with no prompt quality gate is irresponsible
- Every prompt change is a leap of faith
- Audit flagged this as requiring action

---

## Decision

**We adopt promptfoo as our prompt evaluation framework, with a dedicated
`evals/` directory orthogonal to the pytest test suite.**

Evaluation tests live in `evals/`, not in `tests/`. This separation is
intentional:
- `tests/` = code quality (pytest, mocked LLM, deterministic)
- `evals/` = prompt quality (promptfoo, real LLM calls, graded scoring)

---

## Rationale

promptfoo is purpose-built for this exact problem. Building custom pytest
fixtures would duplicate years of promptfoo development. The Node.js
dependency is isolated — it touches nothing in the Python codebase. The
eval framework operates through the same OpenAI-compatible providers that
Narrare already supports, so there is no architectural mismatch.

The separate-directory approach mirrors how E2E tests are a different tool
(Playwright) from unit tests (pytest). Different problem domain, different
tool, same quality gate philosophy.

---

## Phasing

### Phase 2a — MVP (this ADR)

- promptfoo directly against OpenAI-compatible providers
- 3 baseline test sets: writing-generation, name-generation, summarization
- CLI invocation (`npx promptfoo eval`)
- `workflow_dispatch` CI trigger + nightly schedule
- Baseline strategy documented (golden outputs committed to `evals/baselines/`)

### Phase 2b — Advanced (future)

- Custom promptfoo provider routing through Narrare Gateway
  (validates the full prompt cascade, not just raw prompts)
- Culture-matrix evals (same prompt across cultures/languages)
- Nightly CI job with threshold enforcement (block on regression)
- Integration with Langfuse for eval observability

---

## Consequences

### Positive

- Qualitative regression detection for all prompt changes
- LLM-as-judge scoring with configurable thresholds
- Baseline comparison for reproducibility
- CI integration enables prompt quality gates
- Orthogonal to pytest — no coupling, no interference

### Negative

- New Node.js dependency (promptfoo) — mitigated by isolation in `evals/`
- Eval runs cost real LLM API tokens — mitigated by manual trigger + nightly
  schedule, not per-commit
- Separate reporting from pytest — mitigated by upload-artifact in CI

### Risks

- promptfoo could become unmaintained — mitigated by YAML test cases being
  portable; migration to another tool is straightforward
- LLM API costs could grow — mitigated by `run: 3` default and
  `workflow_dispatch` trigger (not per-commit)

---

## Constraints Affected

None. This decision does not violate any RULE-XX:
- promptfoo lives in `evals/`, outside `core/` and `apps/`
- No Python imports affected
- No change to `core/llm/gateway.py` or `core/prompts/`
- No file size impacts

---

## Compliance

- [x] Does not violate any RULE-XX without an approved exception
- [x] Compatible with four-client model (evals are orthogonal)
- [x] Dependency direction maintained (RULE-07) — evals/ has no imports from
      the Python codebase
- [x] No impact on existing pytest test suite

---

## Review Trigger

- [ ] If promptfoo changes licensing in a way that conflicts with Narrare
- [ ] If eval run costs exceed budget thresholds
- [ ] If a Python-native equivalent emerges that matches promptfoo features
- [ ] If Phase 2b custom provider proves impractical
