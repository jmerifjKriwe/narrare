# Pre-commit Gate Tiers — Local Hook Staging

> **Scope.** This document records **local hook staging only** — which stage of the
> local Git lifecycle each `.pre-commit-config.yaml` hook runs in, and the scoped
> `just verify-slice` recipe that complements it. The CI gate SSOT remains the
> gate table in the header of `.github/workflows/ci.yml` plus
> `docs/_shared/CONSTRAINTS.md` §6 (process authority: ADR-098). Point at those for
> CI gates; their content is not restated here.

## Why the hooks are tiered

A hook that inspects the whole project regardless of which files changed is a poor
fit for `git commit`: a one-file edit pays the full project cost before the commit
is allowed. Those hooks now run at `git push`, where the cost is paid once per
push instead of once per commit. CI remains the authority for both — a missing
local push is caught there.

The trade-off is deliberate: the commit stage keeps the fast, file-scoped or
cheap checks; the push stage carries the whole-project checks. `just verify` is
unchanged and remains the pre-merge gate.

## Stage census

Derived from `.pre-commit-config.yaml` on 2026-10-20. The **before** column is
the historical snapshot at `d8a844c3` (the tree the T8 tiering change started
from); the **after** column is the current tree at `2771f82b`. Counting method:

- Every hook is counted once per stage it **explicitly** declares in `stages`.
- A hook with **no** `stages` key inherits the top-level `default_stages`. This
  config sets no `default_stages`, so pre-commit's built-in default applies —
  all stages. Such hooks are counted in the **unrestricted** row, not in a single
  stage column.
- The **reach** rows therefore report what actually runs on `git commit` and
  `git push`: explicit stage hooks plus the unrestricted hooks.

| Effective stage | Before (`d8a844c3`) | After (`2771f82b`) |
|---|---:|---:|
| `pre-commit` (explicit) | 22 | 22 |
| `pre-push` (explicit) | 3 | 5 |
| `manual` (explicit) | 1 | 1 |
| `commit-msg` (explicit) | 1 | 1 |
| unrestricted (no `stages` key) | 15 | 14 |
| **hooks defined** | **42** | **43** |
| runs at `git commit` (explicit + unrestricted) | 37 | 36 |
| runs at `git push` (explicit + unrestricted) | 18 | 19 |

The numbers are derived, not copied: the counts above are what the YAML actually
declares. Before the T8 tiering change `openapi-regenerate` had no `stages` key,
so it was unrestricted; it is now explicitly `pre-push`. Since the `d8a844c3`
snapshot the tree has gained exactly one hook: T15 added `intent-parity` at
`pre-commit`, which is why the current tree defines 43 hooks and 22 explicit
commit-stage hooks. T16a changed no stages, so it moved neither column.

## What the T9 ratchet does and does not pin

`scripts/check_pre_commit_gate_tiers.py` pins **tier membership** for the hooks it
names: every id in its `PUSH_ONLY`, `MANUAL_ONLY` and `COMMIT_MSG_ONLY` sets must
declare exactly that stage, and no unnamed hook may declare `pre-push`. It does
**not** pin counts. A new hook added at the commit stage is therefore accepted
silently — the ratchet has no opinion on how many hooks run at commit or push.
The census above is documentation of the current tree; the ratchet is the
mechanism that keeps the named tiers from drifting.

## The two hooks that moved

| Hook | Before | After | Why push-tiered | CI authority |
|---|---|---|---|---|
| `openapi-regenerate` | no `stages` key (all stages, including `pre-commit`) | `pre-push` | Re-exports the entire OpenAPI document regardless of which API files changed | Architecture job runs `scripts/export_openapi.py --check` |
| `typecheck-frontend` | `pre-commit` | `pre-push` | `tsc --noEmit` type-checks the whole `packages/web` project regardless of which file changed | Frontend job runs the project's TypeScript step |

Measured locally on 2026-10-20 with `timeout 600` and `/usr/bin/time`:

- `openapi-regenerate` (`--hook-stage pre-commit --all-files`): **6.39 s**, exit 0.
- `typecheck-frontend` (`--hook-stage pre-commit --all-files`): **1.47 s** with a
  warm `tsconfig.tsbuildinfo`, **4.23 s** after removing it (cold), exit 0.

Both completed well inside the bound on this machine; the justification is
structural (whole-project scope is paid per commit no matter how small the
change), not a claim about a specific wall-clock number. CI stays authoritative.

## The push-stage hooks (after)

`pyright`, `pyright-tests`, `bandit`, `openapi-regenerate`, `typecheck-frontend`.
`just dev-setup` / `just dev-setup-min` already install the `pre-push` hook type,
so a fresh clone gets these checks at push time.

## `just verify-slice` — the scoped slice gate

```sh
just verify-slice packages/core/narrare_core/llm/model_listing.py
just verify-slice packages/web/lib/providers.ts
just verify-slice tests/unit/core/llm/test_gateway.py packages/web/lib/providers.ts
```

Contract:

- Takes one or more paths (variadic `+paths`) and touches **only** those paths.
- Every path is normalised once before routing: a leading `./` is stripped, and
  an absolute path under the repository root is made repo-relative. So
  `packages/web/lib/providers.ts`, `./packages/web/lib/providers.ts` and
  `"$PWD"/packages/web/lib/providers.ts` take the same arm — an arm cannot be
  missed because of how the caller spelled the path. A path that cannot be
  normalised to a repo-relative form (absolute and outside the repository root)
  aborts the recipe with a message and exit 2; it is never handed to a tool that
  cannot parse it.
- Python paths: `just lint-file` (ruff check + format check) → `just
  typecheck-file` (pyright with the path-aware config: root strict for production,
  `tests/pyrightconfig.json` for test files).
- Tests reach pytest **only through `tests/` paths the caller names**: exactly
  those go to `just test-file`, and nothing else does. A source module has no
  pytest target and pytest exits 5 on it, so a **source-only slice runs no tests
  at all** — pass the test file alongside the source file to run both.
- `just test-file` is `pytest <paths> -v`: plain pytest over the named paths, no
  `-m` selection and no service or container boot. A named
  `tests/integration/…` or `tests/e2e/…` path therefore *does* run — pytest
  collects it like any other file — but it runs with nothing provisioned by this
  recipe. Integration and E2E tests execute only when the caller names such a
  path; they are never an implicit consequence of a slice, and a slice that names
  one inherits whatever that test needs from the surrounding environment.
- Paths under `packages/web/`: the Python tools are skipped (ruff and pyright
  cannot parse TypeScript) and scoped Biome runs instead:
  `cd packages/web && npx biome check <paths relative to packages/web>`.
- **Not a substitute for `just verify`.** It is for fast iteration on a slice;
  the pre-merge gate is still `just verify`.

## What did not change

- `just verify` is `check test-all` — unchanged, and still the pre-merge gate.
- `just verify-quick` is `test-unit test-frontend` — unchanged, the fast
  between-slice variant.
- No CI workflow was modified by this change. For CI gates, read the
  `.github/workflows/ci.yml` header table and `docs/_shared/CONSTRAINTS.md` §6
  (ADR-098).
