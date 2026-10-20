# Throughput T16c — stale pre-T8 hook-tiering claims corrected

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `ac6e2ba1`
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Review finding:** T16 — two documents still described the pre-T8 hook
  tiering; no gate compares prose against `.pre-commit-config.yaml`.
- **Files authored:**
  - `docs/development/deployment-guide.md` (corrected)
  - `docs/architecture/decisions/ADR-097-pyrefly-precommit-typecheck.md`
    (status note + one current-state sentence corrected)
  - this report

## 1. Derived stage census (source of every stage claim)

A throwaway script parsed `.pre-commit-config.yaml` with `yaml.safe_load` and
printed each hook's explicit `stages` list. A missing key is pre-commit's
built-in default, all stages (the config sets no `default_stages`).

```text
architecture-constraints         pre-commit       always_run=True
version-consistency              <all>            always_run=False
prompt-structure                 pre-commit       always_run=True
frontmatter-schema               pre-commit       always_run=True
adoption-score                   manual           always_run=True
ai-interaction-compliance        pre-commit       always_run=True
exception-baseline               pre-commit       always_run=True
type-ignore-discipline           pre-commit       always_run=False
python-file-size                 pre-commit       always_run=True
frontend-file-size               pre-commit       always_run=True
feature-path-accuracy            pre-commit       always_run=True
prompt-surface-contract          pre-commit       always_run=True
provider-catalog-check           pre-commit       always_run=True
intent-parity                    pre-commit       always_run=True
streaming-compliance             pre-commit       always_run=True
locale-sync                      pre-commit       always_run=False
mutation-inert-assets            pre-commit       always_run=False
openapi-regenerate               pre-push         always_run=False
adr-naming                       <all>            always_run=False
ssot-consistency                 pre-commit       always_run=True
doc-drift                        <all>            always_run=False
stub-variables                   pre-commit       always_run=False
ruff-lint                        <all>            always_run=False
ruff-format                      <all>            always_run=False
pyright                          pre-push         always_run=False
pyright-tests                    pre-push         always_run=False
pyright-tests-staged             pre-commit       always_run=False
pyrefly                          pre-commit       always_run=False
bandit                           pre-push         always_run=False
secrets-gitleaks                 pre-commit       always_run=True
biome-frontend                   <all>            always_run=False
check-testid                     pre-commit       always_run=False
check-vrt-mock-contract          pre-commit       always_run=False
validate-i18n                    <all>            always_run=False
typecheck-frontend               pre-push         always_run=True
trailing-whitespace              <all>            always_run=False
end-of-file-fixer                <all>            always_run=False
check-yaml                       <all>            always_run=False
check-toml                       <all>            always_run=False
check-json                       <all>            always_run=False
check-merge-conflict             <all>            always_run=False
check-added-large-files          <all>            always_run=False
conventional-commits             commit-msg       always_run=False
```

Aggregated by stage: `pre-commit` = 22 explicit hooks; `pre-push` = 5
(`openapi-regenerate`, `pyright`, `pyright-tests`, `bandit`,
`typecheck-frontend`); `manual` = 1 (`adoption-score`); `commit-msg` = 1;
unrestricted (no `stages` key) = 14. These match the Tier-2 census in
`docs/development/pre-commit-gate-tiers.md`.

## 2. `deployment-guide.md`

The old table had three factually wrong rows and subsumed two others:

| Old row | Claim | Reality |
|---|---|---|
| Architecture/setup | pre-commit | `adoption-score` is `manual`; `openapi-regenerate` is `pre-push` |
| Python quality | pre-commit | `pyright`, `pyright-tests`, `bandit` are `pre-push` |
| Frontend quality | pre-commit | `typecheck-frontend` is `pre-push` |

Rewritten as 16 stage-accurate rows, splitting categories that now span stages
(Python types → staged at `pre-commit`, full project at `pre-push`; frontend
types → `pre-push`; OpenAPI and adoption pulled into their own rows). Hooks with
no `stages` key are labelled "all stages" with a sentence explaining the
pre-commit default. The canonical-source sentence already existed; it now also
points at `docs/development/pre-commit-gate-tiers.md` (no duplicate pointer).

The German paragraph at the old lines 277–282 was translated to English with
every fact preserved: `always_run: true` applies to `ssot-consistency` and
`secrets-gitleaks`; the former reads `CURRENT_STATE.md` repo-wide (ADR-076);
the latter scans staged file contents only (no history); the full-history audit
is the CI security job (AUFG-05-09).

The fast-path paragraph was corrected: the commit stage runs architecture,
prompt, governance, Ruff, Biome, i18n, and staged type checks; pyright, bandit,
the OpenAPI export, and the frontend TypeScript check run at `pre-push`. The
`SKIP` example previously listed `pyright` (now push-only) and `adoption-score`
(manual, so never runs on commit); it now lists four broad commit-stage
governance hooks. The advice itself (fast path, CI authoritative, run `just
check` before push) is unchanged.

## 3. `ADR-097-pyrefly-precommit-typecheck.md`

- Added `## Status note (2026-10-20)`: T8 moved `typecheck-frontend` and
  `openapi-regenerate` to `pre-push`; `pyrefly` remains at `pre-commit`; the
  decision and its budget argument stand.
- Corrected one current-state sentence in Implementation Notes:
  "whole-project tsc runs at pre-commit" → it ran there at the time of the
  decision, with T8's move noted and cross-referenced to the status note.
- Left the 2026-08-13 D1 history, the decision, Option A/B/C analysis, and all
  measurements untouched.

## 4. Gates

```text
uv run --all-packages python scripts/check_doc_drift.py --governance-only
  -> exit 0 (57 pre-existing feature-doc warnings, unrelated to this change)

grep -nP '[äöüß]|\bDie\b|\bDer\b|\bDas\b' docs/development/deployment-guide.md
  -> matches remain only in the VRT section (lines 408, 409, 414),
     outside the touched hook region

grep -c 'typecheck-frontend' docs/development/deployment-guide.md \
                            docs/architecture/decisions/ADR-097-*.md
  -> 2 and 2; every occurrence states the correct stage
     (guide: `pre-push` row; its `just typecheck-frontend` recipe row makes no
     stage claim; ADR: status note + corrected precedent sentence)

pre-commit validate-config .pre-commit-config.yaml -> valid (exit 0)
```

## 5. Concerns

- `deployment-guide.md` still contains German prose in the VRT section
  (lines 408, 409, 414). It is outside the task's touched region and was not
  translated; it remains documentation debt under the project-language rule.
- The doc-drift run reports 57 pre-existing feature-doc path warnings. They are
  non-blocking and unrelated to this change.
- No gate compares the hook prose to the YAML; the new table is derived and
  accurate today, but a future stage move must update it manually.

## Commit

Committed as `0402cb14` — `docs(dev): describe the hook tiers as they are`.

Status correction: the "not committed" line above describes the report at the time
it was written; this section records the commit that landed it.
