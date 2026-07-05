# ADR-063 — Deterministic CI Virtualenv Contract — `uv sync` once, `--no-sync` always

> **Status:** ✅ Accepted
> **Date:** 2026-07-05
> **Deciders:** Architecture Agent
> **Supersedes:** N/A

---

## Context

Narrare uses `uv` for Python package management with a workspace of three members
(`apps/api`, `packages/core`, `packages/i18n`) plus optional packages. CI runs a
full validation suite: architecture checks, lint, types, tests, coverage, and OpenAPI
export — each step invoking `uv run <command>`.

During CI debugging sessions in July 2026, three related build-system bugs were
identified that caused repeated CI failures with `No module named 'narrare'` at the
"Check OpenAPI spec drift" step:

1. **Root misconfiguration:** The root `pyproject.toml` was incorrectly set up as a
   buildable package (copy-pasted hatchling config with `[build-system]` and
   `packages = ["narrare"]`) when it should be a virtual workspace container.
   This caused a name collision with `apps/api/narrare/` on fresh checkouts.

2. **Hatchling editable-install bug:** Even for packages without a root build
   collision, hatchling's editable-install auto-detection silently fails for complex
   packages (hatchling issue #860), producing empty wheels without `.pth` files.
   This left workspace members unimportable.

3. **`uv run` reconciliation:** `uv run` without `--no-sync` triggers venv
   reconciliation, which evicts workspace members not declared as root dependencies.
   This caused subsequent `import narrare` failures even when the initial venv was
   correctly built.

---

## Decision Drivers

- CI must produce deterministic, reproducible venvs — every run must start from the
  same resolution state with no variation between steps.
- `uv run` must not re-reconcile the venv between check steps, as reconciliation can
  evict workspace members not declared as root dependencies.
- Each workspace member must be independently importable from within the venv, not
  merely available via the root package.
- No `sys.path` hacks or environment workarounds — only standard `uv` and hatchling
  configuration.
- The convention must be simple enough to replicate in every CI step without tribal
  knowledge or per-developer incantation.

---

## Options Considered

### Option A — `uv sync --all-packages` at job start, `--no-sync` for all steps (Selected)

Sync once with all packages at job initialization, then pin every subsequent
`uv run` invocation to `--no-sync` to freeze the venv for the job's lifetime.
The root workspace is declared `[tool.uv] package = false`. Each workspace member
explicitly sets `dev-mode-dirs = ["."]` in its hatchling build config.

**Pros:**
- Deterministic — the venv is built once and frozen for the entire job
- No reconciliation surprises between steps
- `--no-sync` is a single, simple flag to remember
- Works with pre-commit hooks and local development (the flag is harmless locally)

**Cons:**
- Every CI step must remember `--no-sync` (mitigated by documented convention)
- Every new workspace member must add `dev-mode-dirs = ["."]` (build-config burden)

### Option B — Export `PYTHONPATH` to include workspace members

Manually extend `PYTHONPATH` in CI to include each workspace member's source
directory, bypassing the venv entirely for member resolution.

**Pros:**
- No venv reconciliation issues to worry about
- No build-config changes needed

**Cons:**
- Environment-dependent — different shells and CI runners may interpret
  `PYTHONPATH` differently
- Masks real import issues that would surface in production
- Not reproducible across developer machines without the same environment variables
- Circumvents `uv`'s package resolution guarantees
- **Rejected:** violates the deterministic, self-documenting requirement

### Option C — `uv run --no-sync` without `--all-packages` sync

Use `--no-sync` on all steps but sync only the root dependencies without
`--all-packages`.

**Pros:**
- Simpler command at sync time
- Same `--no-sync` convention for check steps

**Cons:**
- Partial sync misses optional workspace members — they may never enter the venv
- Silent failures: `uv run` succeeds but imports fail at runtime
- Does not guarantee all workspace members are available
- **Rejected:** tradeoffs are not worth the marginal simplification

---

## Decision

**We choose Option A:** `uv sync --all-packages` at job start → `uv run --no-sync` for
all subsequent check steps. The root workspace is `[tool.uv] package = false`. Each
workspace member declares `dev-mode-dirs = ["."]` in its `[tool.hatch.build.targets.wheel]`
section.

---

## Rationale

`uv`'s `--no-sync` flag tells `uv run` to skip venv reconciliation entirely.
Combined with `uv sync --all-packages` at job start, the venv is built once from a
complete resolution of all workspace members and then frozen for the job's lifetime.
No step can inadvertently evict a workspace member or introduce resolution drift.

Setting `[tool.uv] package = false` at the workspace root prevents `uv` from treating
the root `pyproject.toml` as a package — which it isn't — and avoids the name
collision with `apps/api/narrare/` that originally caused the `No module named 'narrare'`
failure.

Adding `dev-mode-dirs = ["."]` to each member's hatchling config works around
hatchling issue #860 (editable-install auto-detection producing empty wheels).
Without this setting, hatchling's editable install produces a wheel with no `.pth`
file, leaving the package silently unimportable. The explicit configuration tells
hatchling exactly where to find the package source.

This combination — root virtual package, explicit dev-mode-dirs, all-packages sync,
and frozen venv — is the minimum configuration that makes CI venv behavior
deterministic across all steps.

---

## Consequences

**Positive:**
- Deterministic venv state across all CI steps — no reconciliation surprises
- Easy to understand: sync once, freeze with `--no-sync`
- Works for both CI and local development (`--no-sync` is harmless locally)
- Resolves the long-standing flakiness of OpenAPI spec drift checks

**Negative / Tradeoffs:**
- Must remember `--no-sync` on every `uv run` in CI (mitigated by documented
  convention and canonical CI workflow example)
- Existing CI workflows and pre-commit hooks had to be updated in one batch

**Constraints introduced:**
- Root `pyproject.toml` must remain `[tool.uv] package = false` — it must never be
  made a buildable package again
- Every new workspace member must add `dev-mode-dirs = ["."]` to its hatchling build
  config as part of initial scaffolding

---

## Implementation Notes

**CI pattern** (`.github/workflows/ci.yml`):

```yaml
- name: Sync venv
  run: uv sync --all-packages --frozen

- name: Check
  run: uv run --no-sync <command>
```

**Pre-commit hooks** (`.pre-commit-config.yaml`):

```yaml
- id: openapi-regenerate
  entry: uv run --no-sync python scripts/export_openapi.py
```

**Local development:** `--no-sync` is not strictly required locally because `uv`
auto-reconciles the local venv, but using it doesn't cause issues and keeps the
pattern consistent.

**Files affected by this decision:**
- `pyproject.toml` (root) — `[tool.uv] package = false`, removed `[build-system]`
- `apps/api/pyproject.toml` — added `dev-mode-dirs = ["."]`
- `packages/core/pyproject.toml` — added `dev-mode-dirs = ["."]`
- `packages/i18n/pyproject.toml` — added `dev-mode-dirs = ["."]`
- `.github/workflows/ci.yml` — all `uv run` steps use `--no-sync`
- `.pre-commit-config.yaml` — openapi-regenerate hook uses `--no-sync`
- `scripts/export_openapi.py` — docstring updated to canonical pattern
- `justfile` — export-openapi recipe uses canonical pattern

**ADR Implementation Completeness Gate (Gate 12):** Before marking this ADR as
"✅ Implemented", verify all items in the Gate 12 checklist at
`.opencode/context/narrare-dev/processes/quality-gates.md`. An ADR is not
implemented until it is fully wired, tested, consumed, and documented.

---

## Review Trigger

- When `uv` changes its `--no-sync` behavior or workspace resolution (check on
  major version bumps)
- When hatchling fixes dev-mode-dirs auto-detection (check if `dev-mode-dirs = ["."]`
  can be removed from workspace member configs)
