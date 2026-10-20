# Quality Gates — Committed SSOT

> **Machine-checked by `scripts/check_gate_drift.py` — keep in sync with the ci.yml
> audit block.**

This document is the canonical prose record of Narrare's quality gates. It mirrors
the gate-audit comment block at the top of `.github/workflows/ci.yml` (the rendered
in-repo SSOT); the drift checker verifies this file is present and fails loudly when
it is missing — an absent SSOT is drift by definition. Gate semantics are governed by
`docs/_shared/CONSTRAINTS.md` §6; the gate-exception registry is
`scripts/gate-exceptions.json` (process authority: ADR-098).

## Gate table

| Gate | Tool / Check                            | CI Status   | Notes                                                          |
|------|------------------------------------------|-------------|----------------------------------------------------------------|
| G1   | pytest unit + integration + e2e          | ✅ Blocking  | Unit/Integration/E2E in separate jobs                          |
| G2   | --cov-fail-under (Coverage)              | ✅ Blocking (≥80%) | Target 80% reached (global 82.51%)                       |
| G3   | check_architecture.py                    | ✅ Blocking  | architecture Job                                               |
| G3e  | check_type_ignores (RULE-23)             | ✅ Blocking  | architecture Job (ratchet — additions fail)                    |
| G3b  | check_exception_baseline.py              | ✅ Blocking  | architecture Job                                               |
| G3d  | check_prompt_surface_contract.py         | ✅ Blocking  | architecture Job (ADR-037 + ADR-049 Phase D)                   |
| --   | generate_provider_catalog.py --check (ADR-099) | ✅ Blocking  | architecture Job                                               |
| --   | check_intent_parity.py (ADR-025/037/038) | ✅ Blocking  | architecture Job                                               |
| G3c  | export_openapi.py --check                | ✅ Blocking  | architecture Job                                               |
| G4   | test_fake_conformance.py                 | ✅ Blocking  | test-unit Job (via pytest)                                     |
| G5   | Cross-layer contract tests               | ✅ Blocking  | test-unit Job (via pytest)                                     |
| G6   | pyright (strict; mypy not required)      | ✅ Blocking  | test-unit pre-block (PR/nightly) + push-only quality Job [1]   |
| G6a  | pyrefly (additive, ADR-097; 3 kinds off + baseline) | ✅ Blocking | quality split as G6 [1]                                |
| G7   | ruff check + ruff format --check         | ✅ Blocking  | quality split as G6 [1]                                        |
| G8   | check_adoption.py                        | ✅ Blocking  | architecture Job                                               |
| G9   | check_prompt_structure.py                | ✅ Blocking  | architecture Job                                               |
| G9   | check_streaming_compliance.py (RULE-20)  | ✅ Blocking  | architecture Job                                               |
| G10  | check_locale_sync.py                     | ✅ Blocking  | architecture Job (was: warning)                                |
| --   | check_doc_drift.py                       | ✅ Blocking  | architecture Job                                               |
| --   | check_registry_drift.py                  | ✅ Blocking  | architecture Job                                               |
| --   | check_quality_metrics.py                 | ⚠️ Warning   | architecture Job (opt-in)                                      |
| --   | check_frontend_file_size.py (RULE-04)    | ✅ Blocking  | frontend Job                                                   |
| --   | check_test_coverage_gaps.py (RULE-10)    | ✅ Blocking  | architecture Job                                               |
| --   | evals smoke (pydantic-evals)             | ✅ Blocking  | architecture Job (secret-free)                                 |
| --   | check_eval_drift.py                      | ✅ Blocking  | architecture Job                                               |
| --   | check_module_coverage.py (RULE-10)       | ✅ Blocking  | test-unit Job (--fail, ratcheted baselines)                    |
| --   | check-testid.ts (data-testid gate)       | ✅ Blocking  | frontend Job                                                   |
| --   | check-vrt-mock-contract.ts (ADR-059)     | ✅ Blocking  | frontend Job (before VRT run)                                  |
| --   | Gitleaks (secret scanning, AUFG-05-09)   | ✅ Blocking  | quality split as G6 [1] (push path: full history)              |
| --   | bandit + pip-audit                       | ✅ Blocking  | quality split as G6 [1]                                        |
| --   | biome check (frontend lint/format)       | ✅ Blocking  | frontend Job                                                   |
| --   | pnpm test (frontend tests)               | ✅ Blocking  | frontend Job                                                   |
| --   | Standalone boot smoke (frontend)         | ✅ Blocking  | frontend Job (post-Build step; PRs + frontend nights, W1-6)    |
| --   | check_test_performance.py                | ⚠️ Warning   | frontend Job (WARNING-only)                                    |
| --   | check_pytest_collection_performance.py   | ⚠️ Warning   | test-unit Job (WARNING-only)                                   |
| --   | check_current_state_facts.py (SSOT)      | ✅ Blocking  | architecture Job                                               |
| --   | check_adr_naming.py (review-04 AUFG-04-10) | ✅ Blocking | architecture Job (ADR-XXX-*.md convention)                     |
| --   | check_pre_commit_gate_tiers.py (ADR-098) | ✅ Blocking  | architecture Job (hook-tier ratchet)                           |
| --   | check_review_policy_consistency.py (ADR-093) | ✅ Blocking  | architecture Job (policy caps + pointers)                      |
| --   | budget-report (quota early-warning)      | 📅 Weekly    | Sundays 03:07 UTC, non-blocking (W1-7, spec §5.7)              |
| MutMut Mutation Score | mutation-testing-monthly.yml | 📅 Monthly | Non-blocking, issue report                                     |

`[1]` Quality split (R3, spec §5.8, tasks W1-3/W1-4): the tool steps live once in the
local composite `.github/actions/quality` — run as test-unit's pre-pytest step-group
on the PR/nightly paths and by the push-only quality Job (code-filtered, spec §5.3)
on direct pushes.

## Cadence & events

The authoritative trigger composition lives in `.github/workflows/ci.yml`
(audit block "Composition notes" + the `on:` block). Pointers:

- **Nightly** — 02:37 UTC, event-driven/incremental via the nightly-gate Job:
  `should_run`/probe/component gating (E2E = backend ∨ frontend); weekly full probe
  on Sundays; idle nights skip all expensive jobs. Budget nights (Sun 03:07) run
  budget-report only.
- **Pull requests** — types `[opened, synchronize, reopened, ready_for_review]`
  (W1-5); draft-≠-true jobs rerun when a draft is marked ready. test-unit (incl. the
  folded quality tools) runs on backend PRs only; E2E is path-gated to `tests/e2e/**`
  (W1-12, spec §5.10).
- **Weekly** — budget-report, Sundays 03:07 UTC (W1-7, spec §5.7), non-blocking.
- **Monthly** — mutation testing (`mutation-testing-monthly.yml`), non-blocking,
  issue report.

## Review & report policy

<!-- review-policy: caps=3/250 report=2/80 -->

Normative text. `AGENTS.md` and `.opencode/agents/NarrareDevCoordinator.md`
reference this section; they do not restate its numbers.

- **Package caps:** ≤3 authored files and ≤250 new production LOC per delegated
  unit. Test files, machine-generated artifacts and single-row documentation edits
  do not count. Sub-slice rather than exceed.
- **Per-task report file — required** when a task changes ≥2 production files, adds
  ≥80 new production LOC, crosses a layer boundary, or changes a governed surface
  (`docs/_shared/CONSTRAINTS.md`, an ADR, `scripts/architecture/*`,
  `.github/workflows/ci.yml`, `justfile`, `.pre-commit-config.yaml`). Otherwise the
  commit message body is the record.
- **Batch review — allowed** when the tasks share a layer and a file cluster and at
  least one of them met the report threshold; the batch report names every covered
  task.
- **Per-task review — mandatory, never batched** when a task adds or renames a
  Protocol/contract, changes a manifest or registry, changes the public shape of an
  API response, or edits a governed surface.

## Exception registry

Accepted drift between this table and CI reality is registered in
`scripts/gate-exceptions.json` (with expiry discipline enforced by
`scripts/check_gate_expirations.py`). The registry's process authority is ADR-098.
The presence of this file itself is **not exception-eligible**: if
`docs/development/quality-gates.md` goes missing, `check_gate_drift.py` fails
unregistered (`ssot-present` critical).
