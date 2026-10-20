# Throughput T16a — ADR-099 fetcher invariant actually implemented

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `30025b52`
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Review finding:** F1 — ADR-099 promised a `--check` invariant that no
  checker implemented.
- **Files authored:**
  - `scripts/generate_provider_catalog.py` (extended, 462 lines)
  - `tests/unit/scripts/test_generate_provider_catalog.py` (extended, 347 lines)
  - `docs/architecture/decisions/ADR-099-provider-catalog-ssot.md` (corrected)
  - this report

## 1. Placement decision

The check lives in `scripts/generate_provider_catalog.py` as
`check_fetchers(specs, repo_root)`, called by `_check` beside `check_parity`.

Why not `scripts/provider_catalog_parity.py`, its semantic home: the module is
576/600 lines under the RULE-04 `script` limit. A class-scoped, loud version
(company: the catalog constant, absent-class branch, per-provider message) is
~26 lines with ruff's 100-column wrapping, which lands at 602 and would fail
`check_python_file_size.py`. Squeezing it to 598–600 would leave zero headroom
and amount to compressing the new family to make room, which the task forbids.
Extracting an existing family would author an additional script module, outside
the task's allowed file set. The generator is the `--check` entry point, has
181 lines of headroom, and already aggregates the gate's exit code, so the check
runs in exactly the same place the ADR names.

## 2. The invariant

For every catalog provider id, `ModelCatalogClient` must define a method named
`_fetch_<listing_strategy>`. Implementation:

1. read `packages/core/narrare_core/llm/model_listing.py` with `ast.parse`
   (never import project code);
2. locate `class ModelCatalogClient`, collect `FunctionDef`/`AsyncFunctionDef`
   names from its body only;
3. an absent class reports one structural violation;
4. each strategy without a method reports
   `zai: listing_strategy 'zai_missing' has no _fetch_zai_missing method`.

Violations are `ParityViolation("fetch.methods", ...)`, so `--check` prints them
in the same `<surface>: <detail>` form and sorts them with the other parity
families.

## 3. Mutation proof (two directions, real CLI)

The entry point takes no catalog path, so the catalog was temporarily edited and
restored from a backup; `git diff --stat` afterwards shows only the authored
files (see §6).

```text
=== CLEAN ===
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
EXIT=0
=== MUTATED (zai -> zai_missing) ===
75:    listing_strategy: zai_missing
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
fetch.methods: zai: listing_strategy 'zai_missing' has no _fetch_zai_missing method
EXIT=1
```

The mutation deliberately changed only `listing_strategy`, which is not
rendered into either artifact: the byte compares stay green and the new surface
alone produces the failure. That is the exact blind spot F1 reported.

## 4. ADR-099 corrections

1. Enforcement table, `_dispatch` + `_fetch_*` row: now names
   `scripts/generate_provider_catalog.py:check_fetchers` as the implementation
   of `ModelCatalogClient._fetch_<listing_strategy>` exists for every id.
2. `pydantic_ai_extra` field row: removed “verified against the imports in
   `_providers/*.py`”. It is now described as a closed literal set restated by
   the generator validator, informational, with an explicit statement that no
   `--check` compares it against those imports. Smaller honest option chosen
   (no new check), because the field does not drive behaviour.
3. One sentence after the enforcement table: `requires_endpoint_selector:
   true → false` is not detectable (it removes a requirement instead of
   breaking one), so that direction is a review obligation, not a gate failure.

## 5. Tests

Added to `tests/unit/scripts/test_generate_provider_catalog.py` (the
catalog-generator test file; the parity file was already 393/400 lines and
adding there would breach the `test` limit):

- `test_pristine_catalog_has_a_fetcher_for_every_listing_strategy` — clean tree
  → no violations;
- `test_listing_strategy_without_a_fetch_method_is_reported` — `zai` changed to
  `zai_missing` → exactly one violation naming provider, strategy and method;
- `test_absent_model_catalog_client_is_reported` — class renamed in a copied
  module → the structural violation, not a silent per-provider pass.

`just test-file tests/unit/scripts/test_generate_provider_catalog.py tests/unit/scripts/test_generate_provider_catalog_parity.py`:

```text
============================== 62 passed in 3.09s ==============================
```

## 6. Gate tails

```text
uv run --all-packages python scripts/generate_provider_catalog.py --check  -> EXIT=0
just check-architecture                                                    -> EXIT=0
uv run --all-packages pyright scripts/generate_provider_catalog.py \
    tests/unit/scripts/test_generate_provider_catalog.py
  -> 0 errors, 0 warnings, 0 informations
ruff check + ruff format --check (3 touched files)                          -> clean
```

Line counts (`wc -l`): `scripts/generate_provider_catalog.py` 462,
`tests/unit/scripts/test_generate_provider_catalog.py` 347,
`scripts/provider_catalog_parity.py` 576 (unchanged).

`git diff --stat` after restoring the catalog:

```text
 docs/architecture/decisions/ADR-099-provider-catalog-ssot.md |  9 +++-
 scripts/generate_provider_catalog.py                         | 57 +++++++++++++++++++---
 tests/unit/scripts/test_generate_provider_catalog.py         | 33 +++++++++++++
 3 files changed, 90 insertions(+), 9 deletions(-)
```

## 7. Residual limitation (disclosed in the ADR)

`requires_endpoint_selector: true → false` cannot be detected by a
presence-based gate: the flag removes a requirement, so the corresponding
`_test_call` branch simply becomes unrequired. A change in that direction is a
review obligation. This is now written in ADR-099 point 7 so a reviewer cannot
mistake the gate for coverage it does not have.

## 8. Concerns

- The new check validates method **names only**, by design: fetcher bodies are
  HTTP shapes the catalog cannot know. A renamed method is caught; a fetcher
  that lists the wrong endpoint is not, and is not claimed to be.
- `_dispatch` itself is still not checked for a branch per provider. The
  enforced fact is the exact ADR promise, `_fetch_<listing_strategy>` existence.
  A new id that reuses an existing strategy (for example `foo` with
  `listing_strategy: zai`) passes this check while `_dispatch` has no `foo`
  branch; that direction remains a review obligation, the same class of blind
  spot as the endpoint-selector flag.
- Placement is a compromise forced by the 600-line limit; moving the checker to
  `provider_catalog_parity.py` should happen when that module is next
  modularized, and this report records the intent.
