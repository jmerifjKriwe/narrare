# Task 5 Report — Derive the Core provider-set consumers

**Program:** P1 (Developer Throughput) · **Task:** 5 · **Date:** 2026-10-19
**Worktree:** `.local/share/opencode/worktree/3e7abe4e892d779ef964e6da88d52f8213976240/brave-egret`
**Branch:** `brave-egret` · **HEAD:** `ca30ed67` · **Commits:** none — implementers carry no VCS
authority; no `git add`/`commit`/`stash` was run. Tree left dirty on purpose (file list in §2).

**Status:** DONE_WITH_CONCERNS

**Mandatory review:** no.

---

## 1. What was implemented

Two Core modules stopped restating the provider set by hand and now derive it from
`narrare_core.llm._providers.catalog_generated` (the ADR-099 generated SSOT):

- `model_listing.SUPPORTED_CATALOG_PROVIDERS` — name and type unchanged
  (`frozenset[str]`), now `frozenset(PROVIDER_IDS)`. `_dispatch` and all seven
  `_fetch_*` methods are untouched. No consumer change.
- `_model_listing_test_catalog._TEST_CATALOG` — the per-provider test models moved into a
  private `_TEST_MODELS` literal; the public dict is assembled by iterating `PROVIDER_IDS`,
  so a provider without an entry is a `KeyError` at import, not a silently absent key. The
  module imports `catalog_generated` (never `model_listing`), preserving its no-cycle property.

A new consumer-parity test pins all three: the derived set, the test-stub source catalog
(`_TEST_MODELS`, the stale-entry guard), and the `_fetch_<id>` dispatch contract.

## 2. Files

| Path | Change |
|---|---|
| `packages/core/narrare_core/llm/model_listing.py` | +1 import of `PROVIDER_IDS`; literal set replaced by `frozenset(PROVIDER_IDS)` with a 2-line rationale comment. 397 lines (RULE-04 cap 400). |
| `packages/core/narrare_core/llm/_model_listing_test_catalog.py` | +1 import of `PROVIDER_IDS`; `_TEST_MODELS` literal added; `_TEST_CATALOG` assembled from `PROVIDER_IDS`. Shape/type unchanged (`dict[str, list[tuple[str, str, int \| None]]]`). |
| `tests/unit/core/llm/test_provider_catalog_consumers.py` | new, 41 lines: three parity tests (`EXPECTED` literal + `PROVIDER_IDS` cross-check, `_TEST_MODELS` stale-entry guard, `_fetch_<id>` coverage). The second test was corrected in the fix round (§5) — its first version asserted on the derived `_TEST_CATALOG`, which was tautological. |
| `docs/superpowers/plans/reports/2026-10-19-throughput-T05.md` | this report |

`git diff --stat` (authored files):

```
 .../core/narrare_core/llm/_model_listing_test_catalog.py   | 14 ++++++++++++--
 packages/core/narrare_core/llm/model_listing.py            |  7 ++++---
 2 files changed, 16 insertions(+), 5 deletions(-)
```

`git status --short`:

```
 M packages/core/narrare_core/llm/_model_listing_test_catalog.py
 M packages/core/narrare_core/llm/model_listing.py
?? tests/unit/core/llm/test_provider_catalog_consumers.py
```

### 2.1 Two deviations from the brief's literal text (both required by repo gates)

1. **Import order in the test.** The brief's block writes
   `from narrare_core.llm.model_listing import ModelCatalogClient, SUPPORTED_CATALOG_PROVIDERS`.
   `just lint-file` (ruff isort, constants-before-classes) rejects that order. The shipped
   import is `from narrare_core.llm.model_listing import SUPPORTED_CATALOG_PROVIDERS, ModelCatalogClient`.
   Same three tests, no semantic change; deviating was the only way to pass the lint gate.
   (First `just lint-file` run: `Found 1 error. ... help: Organize imports`.)
2. **No docstring on `SUPPORTED_CATALOG_PROVIDERS`.** My first pass attached a 9-line
   docstring; that pushed `model_listing.py` to **403 lines** and `just check-architecture`
   failed with `[RULE-04] File has 403 lines (hard limit: 400). Split required.` The brief only
   specifies the one-line replacement, so the docstring was unnecessary scope. Removed it in
   favour of a 2-line comment; the file is now 397 lines and `check-architecture` is exit 0.
   Rationale detail lives in the new test module's docstring and in ADR-099.

## 3. Evidence

> **Note (fix round, §5):** the §3.1–§3.2 and §3.5 evidence below predates the fix round.
> §3.2's mutation RED was captured on the *pre-derivation* tree and is superseded — see §5.2
> for the re-recorded RED against the shipped code. The test names in §3.1/§3.5 also predate
> the §5.1 rename.

### 3.1 Step 2 — new test run before the derivation (GREEN)

The tree was consistent before the change (`SUPPORTED_CATALOG_PROVIDERS` already equalled
`EXPECTED`, `_TEST_CATALOG` already had 7 keys, all 7 `_fetch_*` existed), so Step 2 was GREEN
rather than RED — the brief anticipated this ("the meaningful RED is produced in Step 2b").

```
tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_test_catalog_entry PASSED [ 33%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_model_fetcher PASSED [ 66%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_supported_catalog_providers_is_derived PASSED [100%]

============================== 3 passed in 2.29s ===============================
```

### 3.2 Step 2b — mutation (RED), verbatim

> **SUPERSEDED by §5.2 — do not read as current evidence.** This RED was captured on the
> **pre-derivation** tree, where `_TEST_CATALOG` still held the entries as a literal and
> deleting `"groq"` produced an `AssertionError`. Under the shipped derivation the same
> deletion is an import-time `KeyError`, and the assertion this run caught
> (`set(_TEST_CATALOG) == EXPECTED`) has since been deleted as tautological (§5.1). The
> current RED for both mutation directions is re-recorded verbatim in §5.2. Kept here only
> as the original record.

Temporarily deleted the `"groq"` entry from `_TEST_CATALOG`, then re-ran:

```
tests/unit/core/llm/test_provider_catalog_consumers.py::test_supported_catalog_providers_is_derived PASSED [ 33%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_model_fetcher PASSED [ 66%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_test_catalog_entry FAILED [100%]

=================================== FAILURES ===================================
_________________ test_every_provider_has_a_test_catalog_entry _________________

    def test_every_provider_has_a_test_catalog_entry() -> None:
>       assert set(_TEST_CATALOG) == EXPECTED
E       AssertionError: assert {'anthropic',...outer', 'zai'} == {'anthropic',...nrouter', ...}
E         Extra items in the right set:
E         'groq'
E         Full diff:
E           {
E               'anthropic',...
E         ...Full output truncated (7 lines hidden), use '-vv' to show

tests/unit/core/llm/test_provider_catalog_consumers.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_test_catalog_entry
========================= 1 failed, 2 passed in 2.37s ==========================
error: recipe `test-file` failed on line 366 with exit code 1
```

The failure names `groq` (`Extra items in the right set: 'groq'`).

**Restore proof** — restored from a byte copy, then:

```
$ git diff --stat
(no output)

$ git diff -- packages/core/narrare_core/llm/_model_listing_test_catalog.py
(no output)
```

No diff against HEAD for that file ⇒ the mutation left no residue. (The `_TEST_MODELS`/
`PROVIDER_IDS` change in §2 came afterwards.)

### 3.3 Import-chain probes (hard gate) — all pass

Run in fresh interpreters after the derivation was in place:

```
$ uv run --all-packages python -c "import narrare_core.llm.model_listing as m; print('ok model_listing', sorted(m.SUPPORTED_CATALOG_PROVIDERS))"
ok model_listing ['anthropic', 'google', 'groq', 'ollama', 'openai', 'openrouter', 'zai']

$ uv run --all-packages python -c "import narrare_core.llm; import narrare_core.llm.model_listing; print('ok package-first')"
ok package-first

$ uv run --all-packages python -c "import narrare_core.llm._providers.catalog_generated; import narrare_core.llm.model_listing; print('ok catalog-first')"
ok catalog-first
```

No cycle, no `partially initialized module`. The coordinator's pre-read of the chain is
confirmed empirically.

### 3.4 Import-chain consequence (honest statement)

Importing `narrare_core.llm.model_listing` now executes the parent package
`narrare_core.llm._providers.__init__`, which eagerly imports `anthropic, ollama, openai,
others, zai` and runs their `register()` side effects. Observed directly:

```
$ uv run --all-packages python -c "
import sys, narrare_core.llm.model_listing as m
print('providers package loaded:', 'narrare_core.llm._providers' in sys.modules)
from narrare_core.llm._providers.registry import available
print('registered providers:', available())"
providers package loaded: True
registered providers: ['anthropic', 'google', 'groq', 'ollama', 'openai', 'openrouter', 'zai']
```

Is this ordering *new anywhere in the app's startup*? **No.** In Python, importing a submodule
imports its parent package first, so `gateway.py`'s existing line 28
(`from narrare_core.llm._providers.registry import get as get_provider`) already executed
`_providers/__init__` and registered every provider before this task. Reproduced in a fresh
interpreter with only the gateway-style import:

```
$ uv run --all-packages python -c "
from narrare_core.llm._providers.registry import get as get_provider
import sys
print('after gateway-style registry import -> _providers package loaded:', 'narrare_core.llm._providers' in sys.modules)"
after gateway-style registry import -> _providers package loaded: True
```

So what is genuinely new is narrower: **`model_listing` itself** (and anything that imports only
it) now drags in the vendor SDK modules and the registration side effects. The app's startup
ordering is unchanged.

Registration is idempotent: `registry.register` (registry.py:84-86) is a plain
`_REGISTRY[name] = factory` assignment, and provider submodules execute at most once per process
(`sys.modules` caching). Re-running the import chain yields the same 7-entry registry, observed
above.

**Candidate observation for the end-of-program review:** `model_listing` is a read-only catalog
module; that it now transitively imports SDK-adapter modules is a coupling worth a look
(a future `catalog_generated` import path that does not trigger `_providers/__init__` would
remove it). It does not block this task and was not worked around (no lazy/inline import, no
`importlib`) — the plan placed the artifact under `_providers/` and this task had no mandate to
move it.

### 3.5 Gate 1 — new consumer test (GREEN)

```
tests/unit/core/llm/test_provider_catalog_consumers.py::test_supported_catalog_providers_is_derived PASSED [ 33%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_test_catalog_entry PASSED [ 66%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_model_fetcher PASSED [100%]
============================== 3 passed in 2.25s ===============================
```

### 3.6 Gate 2 — whole `tests/unit/core/llm/` (GREEN)

```
======================== 756 passed, 1 skipped in 8.45s ========================
```

This includes `test_model_listing.py::TestSupportedProviders::test_all_providers_present`,
which keeps its independent literal expectation (`expected == SUPPORTED_CATALOG_PROVIDERS`) — it
is untouched and still passes.

Extra (not in the required gates): `tests/unit/operators/test_cr08_p2_operator_defaults.py`
and `tests/unit/api/setup/test_model_fetchers.py` (the only consumers outside `core/llm/`) —
`18 passed in 0.83s`.

### 3.7 Gate 3 — catalog regeneration check (exit 0)

```
$ uv run --all-packages python scripts/generate_provider_catalog.py --check
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
exit=0
```

### 3.8 Gate 4 — `just typecheck` (EXPECTED RED, pre-existing, not mine)

```
$ just typecheck
uv run --all-packages pyright
.../packages/core/narrare_core/embeddings/rerank.py
  .../embeddings/rerank.py:102:16 - error: Import "sentence_transformers" could not be resolved (reportMissingImports)
  .../embeddings/rerank.py:148:18 - error: Import "sentence_transformers" could not be resolved (reportMissingImports)
  .../embeddings/rerank.py:148:47 - error: Type of "MultiVectorEncoder" is unknown (reportUnknownVariableType)
  .../embeddings/rerank.py:191:10 - error: Import "sentence_transformers" could not be resolved (reportMissingImports)
  .../embeddings/rerank.py:191:39 - error: Type of "MultiVectorEncoder" is unknown (reportUnknownVariableType)
5 errors, 0 warnings, 0 informations
error: recipe `typecheck` failed on line 485 with exit code 1
```

Cause: the `embeddings` extra (`sentence_transformers`, which pulls torch) is not installed in
this worktree. All 5 errors are in a file this task did not touch. Torch was **not** installed,
`rerank.py` was **not** touched, no suppression was added. "typecheck green" would be false.

**File-scoped type evidence for the changed files:**

```
$ uv run --all-packages pyright packages/core/narrare_core/llm/model_listing.py packages/core/narrare_core/llm/_model_listing_test_catalog.py
0 errors, 0 warnings, 0 informations

$ uv run --all-packages pyright --project tests/pyrightconfig.json tests/unit/core/llm/test_provider_catalog_consumers.py
0 errors, 0 warnings, 0 informations
```

(The test file is checked with `tests/pyrightconfig.json` — the repo's rule set for tests: root
`[tool.pyright].include` deliberately excludes `tests/`, and `.pre-commit-config.yaml` runs the
`pyright-tests` hook against that project. The root strict config would otherwise flag the
brief-mandated `_TEST_CATALOG` import as `reportPrivateUsage`; that rule is not part of the
repo's test-typecheck contract.)

### 3.9 Supplementary gates

```
$ just lint-file <3 files>
All checks passed!
3 files already formatted

$ just check-architecture        # exit 0
✅ Architecture constraints OK (3359 files checked, 13 approved exception(s))

$ just check-python-size
✅ All Python files are within hard limits
Python file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
```

## 4. Concerns

1. **Typecheck is red for an unrelated, pre-existing reason** (§3.8). Not fixable in this
   worktree without installing the `embeddings` extra (torch), which is explicitly out of scope.
2. **ADR-099 wording vs. implementation.** ADR-099 §(line ~260) describes the `_TEST_CATALOG`
   keys as "derived at import from `AIProvider`"; the implementation derives them from
   `PROVIDER_IDS` (the coordinator's directed single-ordering source). Both are generated from
   the same `catalog.yaml`, the resulting key set is identical, and the parity test pins
   equality — no functional gap, but the ADR text is one noun off. Flagging for the Docs pass;
   not changed here (no mandate, and it is an ADR).
3. **New transitive coupling of `model_listing` on `_providers/__init__`** (§3.4). Behaviourally
   safe and already implied by the app's gateway import, but a candidate for the end-of-program
   review.
4. **`_TEST_MODELS` is module-private but not underscore-`__all__`-exported** — consistent with
   the module's existing style (`__all__ = ["_test_catalog"]`); noted only so a reviewer does not
   read it as an oversight.

---

## 5. Fix round — review findings

**Date:** 2026-10-19 · **Branch:** `brave-egret` · **HEAD at fix time:** `a6c58b8b`
(the reviewed commit). **Files touched:** the test module and this report only. The two
production modules are unchanged — the derivation is approved and was not re-opened.

The independent task review raised one Important finding and one evidence finding. Both are
about the same thing: the guard and its proof were not real.

### 5.1 Finding 1 (Important) — the parity test was tautological

`test_every_provider_has_a_test_catalog_entry` asserted `set(_TEST_CATALOG) == EXPECTED`.
Under the shipped derivation `_TEST_CATALOG` is built as
`{provider: _TEST_MODELS[provider] for provider in PROVIDER_IDS}`, so its keys **are**
`PROVIDER_IDS` by construction and a provider missing from `_TEST_MODELS` makes the module
unimportable. The assertion therefore never inspected `_TEST_MODELS` — the dict that actually
holds the per-provider entries, and the only place a **stale** entry (a provider no longer in
`PROVIDER_IDS`) can linger: the comprehension silently drops such a key and nothing caught it.
It was a restatement of the same file's first assertion, and a vacuous assertion inside a guard
is worse than a missing one because it reads as coverage.

**What changed in `tests/unit/core/llm/test_provider_catalog_consumers.py`:**

- The test no longer imports `_TEST_CATALOG`; it imports `_TEST_MODELS` and asserts
  `set(_TEST_MODELS) == EXPECTED`.
- The tautological `set(_TEST_CATALOG) == EXPECTED` assertion was **deleted**, not kept beside
  the new one.
- The test was renamed to `test_test_models_exactly_matches_generated_provider_set`, so its
  name states what it now pins. The other two tests are unchanged.
- A four-line comment names *why* `_TEST_MODELS` is the surface: a stale key is dropped by the
  comprehension, a missing key is an import-time `KeyError`, so this assertion is the
  stale-entry guard.
- The module docstring's second bullet now names `_TEST_MODELS` instead of `_TEST_CATALOG`.

**Why `_TEST_MODELS` is the right surface.** It is the single place a human edits when adding or
retiring a provider: `PROVIDER_IDS` is generated (ADR-099) and pinned by the first test, and
`_TEST_CATALOG` is a pure function of the other two. Pinning the *source* dict therefore closes
both directions with the smallest surface — missing key ⇒ `KeyError` at import (unchanged,
still guaranteed by the comprehension), stale key ⇒ this assertion. Pinning the derived view
pins nothing the comprehension does not already force.

**Deviation from the fix brief's wording (reported, not silent):** the brief said to import
`_TEST_MODELS` "alongside `_TEST_CATALOG`". Because the tautological assertion had to go,
`_TEST_CATALOG` had no remaining use in the module, and an unused import fails `just lint-file`
(ruff `F401` is selected and has no `tests/**` ignore — `pyproject.toml:155-176`). The import was
therefore replaced, not extended. Verified by the lint gate in §5.4.

### 5.2 Finding 2 (evidence) — the recorded mutation RED did not match the shipped code

The §3.2 RED was captured on the pre-derivation tree, where deleting the `"groq"` entry produced
an `AssertionError`. Under the shipped code the same mutation is an import-time collection error,
so the artifact did not show RED against the code that ships. Both directions of the *new* guard
were re-recorded verbatim below, post-derivation, on HEAD `a6c58b8b`.

**Direction A — missing entry (the `KeyError` guarantee).** Deleted the `"groq"` key from
`_TEST_MODELS`, then ran
`just test-file tests/unit/core/llm/test_provider_catalog_consumers.py`:

```
collecting ... collected 0 items / 1 error

==================================== ERRORS ====================================
___ ERROR collecting tests/unit/core/llm/test_provider_catalog_consumers.py ____
tests/unit/core/llm/test_provider_catalog_consumers.py:18: in <module>
    from narrare_core.llm._model_listing_test_catalog import _TEST_MODELS
packages/core/narrare_core/llm/__init__.py:19: in <module>
    from narrare_core.llm.model_listing import (
packages/core/narrare_core/llm/model_listing.py:20: in <module>
    from narrare_core.llm._model_listing_test_catalog import _test_catalog
packages/core/narrare_core/llm/_model_listing_test_catalog.py:63: in <module>
    provider: _TEST_MODELS[provider] for provider in PROVIDER_IDS
              ^^^^^^^^^^^^^^^^^^^^^^
E   KeyError: 'groq'
=========================== short test summary info ============================
ERROR tests/unit/core/llm/test_provider_catalog_consumers.py - KeyError: 'groq'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 1.81s ===============================
error: recipe `test-file` failed on line 366 with exit code 2
```

This RED belongs to **Direction A (missing entry)**. It is a collection/import error naming
`groq` — not the assertion. Restored from a byte copy before Direction B (proof in §5.3).

**Direction B — stale entry (the new guard firing).** Added a bogus
`"some-retired-provider"` entry to `_TEST_MODELS`, then ran the same command:

```
collecting ... collected 3 items

tests/unit/core/llm/test_provider_catalog_consumers.py::test_supported_catalog_providers_is_derived PASSED [ 33%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_model_fetcher PASSED [ 66%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_test_models_exactly_matches_generated_provider_set FAILED [100%]

=================================== FAILURES ===================================
___________ test_test_models_exactly_matches_generated_provider_set ____________

    def test_test_models_exactly_matches_generated_provider_set() -> None:
        # ``_TEST_MODELS`` is the surface this guard must inspect, not the derived
        # ``_TEST_CATALOG``: the comprehension there silently drops a *stale* key (a
        # provider no longer in ``PROVIDER_IDS``), while a *missing* key raises
        # ``KeyError`` at import. So this assertion is the stale-entry guard;
        # ``set(_TEST_CATALOG) == EXPECTED`` would only restate that comprehension.
>       assert set(_TEST_MODELS) == EXPECTED
E       AssertionError: assert {'anthropic',...nrouter', ...} == {'anthropic',...nrouter', ...}
E
E         Extra items in the left set:
E         'some-retired-provider'
E
E         Full diff:
E           {
E               'anthropic',...
E
E         ...Full output truncated (8 lines hidden), use '-vv' to show

tests/unit/core/llm/test_provider_catalog_consumers.py:36: AssertionError
=========================== short test summary info ============================
FAILED tests/unit/core/llm/test_provider_catalog_consumers.py::test_test_models_exactly_matches_generated_provider_set
========================= 1 failed, 2 passed in 2.45s ==========================
error: recipe `test-file` failed on line 366 with exit code 1
```

This RED belongs to **Direction B (stale entry)**: the module imports fine (the comprehension
drops the stale key), and the *new* assertion fails naming `some-retired-provider`. This is the
guard that did not exist before the fix — under the old test it would have been green.

**Whitespace note (applies to both transcripts above):** the blank `E` continuation lines in
these transcripts had their trailing whitespace trimmed by the repo's `trailing-whitespace`
pre-commit hook, and nothing else on those lines changed, so the blocks above are not
byte-for-byte padded output. Raw hook output:

```
$ pre-commit run trailing-whitespace --files docs/superpowers/plans/reports/2026-10-19-throughput-T05.md
trim trailing whitespace.................................................Passed
```

### 5.3 Restore proof (after the final restore)

Restored `_model_listing_test_catalog.py` from the byte copy taken before Direction A:

```
$ md5sum packages/core/narrare_core/llm/_model_listing_test_catalog.py
392d0366dafed23751a2484ebde38960  packages/core/narrare_core/llm/_model_listing_test_catalog.py

$ git diff --stat packages/core/narrare_core/llm/_model_listing_test_catalog.py
(no output)
```

The md5 equals the pre-mutation checksum and the `git diff --stat` against HEAD `a6c58b8b` is
empty ⇒ neither mutation left residue. The production modules carry no fix-round change.

### 5.4 Gates after the change

**Gate 1 — `just test-file tests/unit/core/llm/test_provider_catalog_consumers.py` (GREEN):**

```
tests/unit/core/llm/test_provider_catalog_consumers.py::test_supported_catalog_providers_is_derived PASSED [ 33%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_every_provider_has_a_model_fetcher PASSED [ 66%]
tests/unit/core/llm/test_provider_catalog_consumers.py::test_test_models_exactly_matches_generated_provider_set PASSED [100%]

============================== 3 passed in 2.27s ===============================
```

**Gate 2 — `just test-file tests/unit/core/llm/` (GREEN):**

```
======================== 756 passed, 1 skipped in 8.49s ========================
```

**Gate 3 — `uv run --all-packages python scripts/generate_provider_catalog.py --check` (exit 0):**

```
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
generate exit=0
```

**Gate 4 — lint and file-scoped typecheck:**

```
$ just lint-file tests/unit/core/llm/test_provider_catalog_consumers.py
All checks passed!
1 file already formatted

$ uv run --all-packages pyright --project tests/pyrightconfig.json \
    tests/unit/core/llm/test_provider_catalog_consumers.py
0 errors, 0 warnings, 0 informations
```

`just typecheck` (whole repo) is still pre-existing-RED for the absent `sentence_transformers`
extra (`rerank.py`, untouched — §3.8); it was not re-run as a fix-round gate and was not
touched. The file-scoped run above is the unchanged-file evidence for the changed test.

### 5.5 Standings after the fix round

- Finding 1 (tautological guard): resolved — the guard now inspects `_TEST_MODELS`, the deleted
  assertion is gone, the test is renamed, and the comment states the surface rationale.
- Finding 2 (evidence mismatch): resolved — §3.2 is marked SUPERSEDED and both mutation
  directions are re-recorded verbatim against the shipped code in §5.2, with an empty-diff
  restore proof in §5.3.
- The §4 concerns below the fix-round section still stand (§4.1 pre-existing typecheck RED,
  §4.2 ADR-099 wording, §4.3 transitive coupling, §4.4 private-name note).
