# Dual-Output Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the permissive output-function twin from all 29 dual-tool agents. Every agent gets `output_type=StrictModel` — one tool, one schema, one contract. Kills both failure modes (FM1: validation failure on missing required fields; FM2: silent empty results passing validation) at the root.

**Architecture:** The `output_type=[self._process_X, XOutput]` pattern creates two function tools with different schemas — models that follow tool schemas precisely (GLM) fill the permissive tool's fields, then fail validation against the strict model. Fix: `output_type=XOutput` only; delete the `_process_*` functions. pydantic-ai streams fine with Model-output (the OutputFunction's streaming rationale was already covered by `ctx.partial_output` returning empty — no real streaming value lost). 13 of 26 benchmark capabilities are affected.

**Analysis basis:** `.superpowers/sdd/2026-08-27-kb-benchmark-package3-runner/architecture-dual-output-analysis.md` (the architecture specialist's audit: 29 classes / 31 sites, Class A item-dict mismatch ×24, Class B all-default silent-empty ×6, plus 1 PydanticAgent bypass).

**Tech Stack:** Python, pydantic-ai Agent output_type, existing agent test infrastructure (TestModel / FunctionModel).

## Global Constraints

- Every agent migration: `output_type=XOutput` (the strict model ONLY), delete the `_process_*` method, remove `output_validator` if it only served the permissive path (keep if it enforces genuine invariants — ADR-035 quality checks).
- Tests: each agent's existing tests must still pass; where tests exercise the output-function path, update to the model-only path. NO new TestModel-only tests for tool choice — the existing tests never exercised it anyway (the audit's finding).
- The `_process_output` methods return `ExtractionOutput()` empty during `ctx.partial_output` — verify no UI/consumer depends on the partial-output path before deleting; if any SSE stream consumes it, document and flag.
- The wiki chapter agent (`wiki/agent_chapter.py:70`) bypasses NarrareAgent (direct PydanticAgent) — include it.
- No behavioral change for models that "worked" with the dual pattern — the strict model was always the intended output; removing the permissive twin just enforces it.
- Per-task caps: ≤3 agents / ≤250 LOC per delegation; batch by domain.
- English; pyright strict; ruff clean; zero type-ignores.

---

### Task 1: Core KB agents (5)
`extraction_agent.py`, `merge_agent.py` (KBMerge), `kb_improve_agent.py`, `kb_assist_agent.py`, `fact_extractor_agent.py`. The extraction agent is THE benchmark build path — highest priority.
Files: packages/core/narrare_core/agents/{extraction,merge,kb_improve,kb_assist,fact_extractor}_agent.py + their tests + `_process_*` method deletions.

### Task 2: Analysis agents (8)
`beta_reader_agent.py` (p1+p2 = two output functions), `dialogue_coach_agent.py`, `coreference_agent.py` (if dual — check), `pov_detection_agent.py`, `readability_agent.py`, `character_voice_agent.py` + checker + drift variants, `author_voice_drift_agent.py`, `character_arc_agent.py`.

### Task 3: Consistency + Planning + Writing agents (8)
`consistency_agent.py`, `series_consistency_agent.py`, `temporal_extraction_agent.py`, `timeline_agent.py`, `worldbuilding_agent.py` (p1+p2), `chapter_summary_agent.py`, `band_summary_agent.py`, `outline_agent.py`.

### Task 4: Remaining agents (8)
`review_agent.py`, `author_voice_agent.py`, `preference_analysis_agent.py`, `wiki agent entity`, `wiki agent chapter` (the PydanticAgent bypass!), `draft_agent.py` (already congruent — verify + document), plus any agents the sweep finds that the analysis missed.

### Task 5: Sweep + guard
- `rg -rn "_process_output\|_process_" packages/core/narrare_core/agents/ | grep -v test | grep -v __pycache__` → must be EMPTY (all permissive twins deleted).
- `rg -rn "output_type=\[" packages/core/narrare_core/agents/ | grep -v test` → must be EMPTY (no more list-of-output-types).
- Guard test: assert no agent file contains `output_type=[` (the dual pattern is banned going forward).
- Full gates: `just check`, `just test-unit`, pyright, ruff, architecture.

### Task 6: CURRENT_STATE + memory
Document the unification, the root cause chain (benchmark → 4 production fixes → architecture audit → systemic unification), and the blast radius.

---

## Plan Self-Review (executed)

- Coverage: 29 agents from the audit → 4 migration tasks + sweep/guard + docs. The wiki chapter bypass included (Task 4).
- Risk: pydantic-ai streaming with Model-output — verify no SSE consumer depends on the permissive partial path before each deletion (per-agent check, documented in the task report).
- No new placeholders: every agent migration follows the same mechanical pattern (delete _process_*, change output_type, update tests).
- The draft agent (congruent pair, no production caller) — verify + document only.
