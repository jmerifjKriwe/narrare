# Narrare Scripts

The `scripts/` directory is Narrare's governance and tooling hub. It contains
~40 check scripts that enforce RULE-XX architecture rules and ADR decisions,
probe scripts for runtime validation, utility scripts for development tasks,
and orchestration runners for CI and pre-commit hooks.

## Quick Start

Run any check script from the project root via `uv run`:

```shell
uv run python scripts/check_adr_naming.py
uv run python scripts/check_architecture.py --json
uv run python scripts/check_doc_drift.py --verbose
```

Most scripts return exit code 0 for pass, 1 for failure, and support a `--json`
flag for machine-readable CI output.

## Script Categories

### Governance and Architecture

Scripts that enforce Narrare's architecture rules (CONSTRAINTS.md), ADR
decisions, and governance policies. These run in pre-commit and CI.

- **check_architecture.py** — Enforces the RULE-XX rules defined in
  CONSTRAINTS.md. The primary architecture gate. Runs in pre-commit and CI.
  Domain logic in `architecture/` package.
- **check_adr_naming.py** — Validates ADR filename convention
  (`ADR-XXX-short-title.md`). Fast check that only runs when the decisions
  directory changes.
- **check_current_state_facts.py** — Enforces ADR-076 volatility policy on
  `docs/_shared/CURRENT_STATE.md`: rejects volatile count claims, requires
  links or commands for authoritative facts.
- **check_registry_drift.py** — Validates `adoption-registry.yaml` against
  actual prompt files using JSON Schema, detecting registered modes without
  prompt files and vice versa (ADR-041 Decision 1).
- **check_gate_drift.py** — Detects drift between documented quality gates and
  CI configuration. Checks gate-exceptions.json against CI YAML and pyproject.toml.
  Uses `gate_drift_checks.py` for check logic.
- **gate_drift_checks.py** — Shared logic module for gate drift detection
  (constants, data structures, check functions).
- **check_gate_expirations.py** — Validates that all active entries in
  `gate-exceptions.json` are within their valid period. Fails on expired
  exceptions.
- **check_exception_baseline.py** — No-growth gate for approved architecture
  exceptions. New exceptions require ADR-approved baseline updates.

### Code Quality

Scripts that enforce code-level quality standards: file size limits, type
safety, prompt structure, and security scanning.

- **check_python_file_size.py** — Enforces RULE-04 hard line-count limits per
  Python module category. Existing violations are ratcheted by baseline.
- **check_frontend_file_size.py** — RULE-04 enforcement for TypeScript/TSX
  files. Mirrors the Python file-size gate for the frontend.
- **check_type_ignores/** (package) — Manages a ratcheted baseline of
  `# type: ignore` comments. New ignores require explicit addition to the
  baseline. Run via `python -m scripts.check_type_ignores`.
- **check_streaming_compliance.py** — Enforces RULE-20: every backend SSE
  endpoint must have a frontend consumer using `connectSSE()`. Detects REST
  calls used instead of streaming.
- **check_prompt_structure.py** — Validates bundled prompt files for structural
  consistency, variable safety, locale sync, and security (XML wrapping).
  Uses supporting modules: `prompt_checks.py`, `prompt_checks_crossfile.py`,
  `prompt_checks_universal.py`, `prompt_governance_checks.py`,
  `prompt_check_types.py`, `prompt_vars.py`.
- **check_prompt_surface_contract.py** — Enforces ADR-037 and ADR-049 prompt
  surface contracts: manifest coverage, route/template drift, identity chains,
  root-mode prohibition, and orphan template detection.
- **check_kg_consistency.py** — Reads the adoption registry and scans bundled
  prompt files for KG variable usage mismatches. Static CI validation
  (ADR-040 Decision 2).
- **check_module_coverage.py** — Checks per-module test coverage against
  RULE-10 targets and ratcheted baselines from pytest's coverage XML.
- **check_secrets.py** — Gitleaks wrapper for repository secret scanning.
  Local and CI invocation are kept aligned by this single entry point.
- **check_commit_message.py** — Validates commit messages follow the
  Conventional Commits format. Runs in the `commit-msg` pre-commit stage.
- **check_version_consistency.py** — Detects dependency version drift across
  workspace `pyproject.toml` files. Catches Dependabot-induced inconsistency.

### Adoption and Standards

Scripts that measure feature adoption of core infrastructure and validate
prompt quality across locales.

- **check_adoption.py** — Thin entry point that computes per-category and
  overall adoption scores. Domain logic in `adoption/` package (cli.py,
  scorer.py, scorer_models.py, mode2_validation.py, etc.). ADR-025 / ADR-056.
- **prompt_checks_crossfile.py** — Cross-file prompt validation: locale
  coverage, meta-prompt guardrails.
- **prompt_checks_universal.py** — Validates universal rule files exist for
  all supported locales and are not duplicated in templates.
- **prompt_governance_checks.py** — CR-01 governance gates: user-content
  wrapper vocabulary, deprecated variables, generated-suggestion precedence.
- **prompt_quality_de.py** — German locale quality checker for compound
  splitting, Denglisch, and anglicism detection.

### Testing Quality

Scripts that audit and enforce test quality standards.

- **check_test_coverage_gaps.py** — Thin wrapper for the `test_coverage_gaps/`
  package. Discovers modules without tests, maps test coverage gaps, and
  reports findings.
- **check_test_performance.py** — Monitors frontend test execution time
  against a configurable threshold. Supports pre-measured durations (CI mode)
  and live measurement (local mode).
- **check_pytest_collection_performance.py** — Times pytest's collection phase
  and warns if it exceeds a threshold. Catches import-cycle bloat and slow
  conftest files.
- **audit_test_assertions.py** — Entry point for the `test_assertion_audit/`
  package. Scans test files for assertion practices and generates quality
  reports.

### Probes (Runtime Validation)

The `probes/` package exercises Narrare's AI features at runtime and produces
evidence markers consumed by the adoption score gate.

- **run_all_probes.py** — Runs every probe in the package and reports evidence
  status. Used in CI to verify that all adoption registry modes with
  `requires_runtime_evidence: true` produce evidence.
- Individual probes: `analysis_probes.py`, `chat_chat_probe.py`,
  `generation_names_probe.py`, `kb_probes.py`, `planning_outline_probe.py`,
  `preference_enrichment_probe.py`, `validation_budget_probes.py`,
  `writing_probes.py`. Each exercises a specific AI feature mode and writes
  evidence to `.evidence/`.

### CI and Orchestration

Scripts that orchestrate or integrate multiple checks.

- **run_checks.py** — Runs all quality checks sequentially and produces a
  compact, readable summary. Invoked by `just check`.
- **entrypoint.sh** — Container entrypoint that starts both the FastAPI
  backend and Next.js frontend in a single container, with signal propagation
  for graceful shutdown.

### Evaluation Drift

- **check_eval_drift.py** — Thin wrapper for the `eval_drift/` package.
  Detects drift between Pydantic Eval results and the ratcheted baseline.
  Runs in the eval-nightly CI workflow.
- **eval_drift/** (package) — `__main__.py` entry point, `comparison.py` for
  score comparison, `parser.py` for eval result parsing, `reporting.py` for
  output formatting.

### Documentation

Scripts that keep documentation synchronized with the codebase.

- **check_doc_drift.py** — Validates documented version numbers, ADR
  cross-references, spec/RULE-XX alignment, checker terminology, and just-recipe
  references against reality. Domain logic in `doc_drift/` package.
- **doc_drift/** (package) — Check modules for tool version consistency,
  ADR cross-references, spec alignment, terminology drift, lookup-context
  drift, SSOT locale-path parity, and just-recipe doc-drift prevention.
- **check_feature_path_accuracy.py** — Validates that implementation paths in
  feature-file frontmatter (`service:`, `contract:`, `router:`, `prompt:`)
  actually exist on disk. Prevents "documented not equal implemented" drift.
- **check_locale_sync.py** — Detects locale drift between EN/DE/FR prompt
  variants by comparing variables and section headings.

### Utilities

Scripts that support development workflows but do not enforce rules.

- **clean_caches.py** — Cleans all regenerable cache and artifact directories
  (pycache, ruff, pytest, egg-info, pyright, coverage, etc.). Domain logic in
  `clean_cache_lib/` package.
- **seed_dev_user.py** — Seeds the development database with a pre-configured
  dev user (`dev@narrare.dev`). Idempotent.
- **export_openapi.py** — Exports the OpenAPI specification to a static JSON
  file without requiring Docker or a running database. Also provides a CI
  drift detection mode (`--check`).
- **run_mutmut.py** — Wrapper for MutMut 3.x mutation testing with scope
  selection (core, api, all, or custom paths). Handles workspace symlinks
  and pyproject.toml patching.
- **check_system_health.py** — Aggregates individual gate results into a
  weighted health score (0.0-1.0). Pure aggregator over baseline data, does
  not invoke other checks. Uses `health_types.py` and `health_format.py`.
- **check_quality_metrics.py** — Joins Pydantic Eval results, adoption
  reports, audit reports, and invocation evidence into per-mode quality
  metrics. Opt-in via `--quality` flag or `NARRARE_QUALITY_METRICS=1`.
- **check_model_registry.py** — Compares registered model IDs against
  models.dev reference data, warning about unregistered or deprecated models.
- **validate-i18n.ts** — TypeScript i18n validation that checks for missing
  keys, hardcoded strings, and type mismatches in message files.
- **local/toggle_claude.sh** — Local development utility for toggling Claude
  Code configuration.

### AI Interaction Compliance

- **checks/check_ai_interaction_compliance.py** — Enforces ADR-043 / S.16 AI
  Interaction Standards. Verifies 10 machine-checkable rules across TSX
  components and i18n files: SSE/useAIOperation pairing, abort controller
  patterns, i18n error key coverage, signal propagation, and more.
- **checks/ai_operation_inventory.yaml** — Machine-readable compliance surface
  for all frontend AI operations. Validated by the compliance check.
- **checks/_ai_interaction_checks/** — Sub-package with individual check
  implementations and the exclude registry.

## Naming Conventions

- **`check_*.py`** — Standalone entry points intended for CI and pre-commit
  hooks. These are the public API of the scripts directory.
- **Thin wrapper pattern** — When a check grows complex, the `check_*.py`
  file becomes a thin entry point that delegates to a sibling package:
  - `check_adoption.py` imports from `adoption/cli.py`
  - `check_eval_drift.py` delegates to `eval_drift/__main__.py`
  - `check_test_coverage_gaps.py` delegates to `test_coverage_gaps/__main__.py`
  - `audit_test_assertions.py` delegates to `test_assertion_audit/__main__.py`
  - `check_architecture.py` imports from `architecture/checkers.py`
  - `clean_caches.py` uses `clean_cache_lib/`
  - `check_prompt_structure.py` uses `prompt_checks*.py` and `prompt_vars.py`
- **`check_type_ignores/`** — Invoked via `python -m scripts.check_type_ignores`
  (the wrapper `check_type_ignores.py` was removed after naming collisions were
  resolved).
- **`prompt_*.py`** — Support modules for prompt validation; not entry points.
- **`health_*.py`** — Support modules for system health reporting.

## CI Integration

Scripts are wired into two enforcement layers:

### Pre-commit (`.pre-commit-config.yaml`)

All local hooks run via `uv run python scripts/check_*.py`. Key hooks:
- `architecture-constraints` — always runs (check_architecture.py)
- `version-consistency` — on pyproject.toml changes
- `prompt-structure` — always runs
- `adoption-score` — always runs
- `python-file-size` / `frontend-file-size` — always runs
- `feature-path-accuracy` — always runs
- `prompt-surface-contract` — always runs
- `streaming-compliance` — always runs
- `locale-sync` — on prompt file changes
- `adr-naming` — on ADR directory changes
- `openapi-regenerate` — on API/core changes
- `conventional-commits` — commit-msg stage
- `validate-i18n` — on TSX/Python/i18n file changes

### CI (`.github/workflows/ci.yml`)

The architecture job runs the full `check_*` suite sequentially. Every
`check_*.py` entry point in `scripts/` is invoked in CI. Additionally:
- `check_secrets.py` runs in a dedicated security job
- `check_module_coverage.py` runs in the coverage job
- `check_eval_drift.py` runs in the eval-nightly workflow
- `check_frontend_file_size.py` runs in the frontend job
- `check_test_performance.py` runs in the frontend test job
- `check_pytest_collection_performance.py` runs in the backend test job

## Adding a New Script

When adding a new check script, follow this checklist:

1. **RULE compliance** — Ensure the check enforces or supports an existing
   RULE-XX or ADR. Document the reference in the script's docstring.
2. **Test coverage** — Add unit tests in `tests/unit/scripts/`.
3. **CI wiring** — Add the script to `.github/workflows/ci.yml` in the
   appropriate job.
4. **Pre-commit hook** — If the check is fast and relevant before every
   commit, add a local hook in `.pre-commit-config.yaml`.
5. **Documentation** — Add a one-line entry to this README under the
   appropriate category.
6. **Exit codes** — Use 0 for pass, 1 for failure. Support `--json` for CI.
7. **Thin wrapper policy** — If the check exceeds ~300 lines, extract the
   domain logic into a sibling package and keep the entry point thin.
