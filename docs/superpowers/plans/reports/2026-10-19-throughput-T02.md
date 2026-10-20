# Task 2 Report — `AIProvider` re-pointed to the generated catalog enum

**Program:** P1 (Developer Throughput) · **Task:** 2 · **Date:** 2026-10-19
**Worktree:** `.local/share/opencode/worktree/3e7abe4e892d779ef964e6da88d52f8213976240/brave-egret`
**Branch:** `brave-egret` · **HEAD:** `00c743ef` · **Commits:** none (ruling 4 — implementers carry
no VCS authority; no `git add`/`commit`/`stash` was run)

**Status:** DONE_WITH_CONCERNS — the acceptance gate caught a real contract drift, whose root
cause lay in T1's generator; fixing it needed 2 files beyond the coordinator's expected 3
(§2.3, §5.1, C1).

---

## 1. What was implemented

`apps/api/narrare/setup/base_schemas.py` no longer declares `AIProvider`. It imports the
generated, class-syntax `StrEnum` from `narrare_core.llm._providers.catalog_generated` as an
explicit re-export (`... import AIProvider as AIProvider`), so `narrare.setup.base_schemas`,
`narrare.setup.schemas` and `narrare.setup` all hand out **the same object** Core generates from
`catalog.yaml`. The API layer can no longer drift from the provider SSOT, because it no longer
holds a second copy of the fact.

Everything else in `base_schemas.py` is untouched: `StoryStructure`, `StoryTone`,
`StarterContent`, and the Step 1–3 schemas. No provider string literal was introduced in
`apps/api` (ruling 3 / RULE-01b; grep-verified, §5.4).

One correction was required **in Core** to make the re-point contract-neutral (§2.3): the
generated enum's class docstring was removed from the generator template and the artifact
regenerated, because pydantic renders a class docstring as the JSON-schema `description` of every
component referencing the enum.

## 2. Files

### 2.1 As expected by the coordinator (3 files)

| Path | Lines | Change |
|---|---|---|
| `apps/api/narrare/setup/base_schemas.py` | 140 (was 141) | +9/−10: enum body deleted, re-export added, enums-section note |
| `tests/unit/api/setup/test_ai_provider_identity.py` | 33 | new (brief's 3 tests + 1 guard, §5.2) |
| `docs/superpowers/plans/reports/2026-10-19-throughput-T02.md` | this file | new |

### 2.2 Step 5 needed no file change — confirmed

`docs/architecture/decisions/INDEX.md` is **not** in `git status` and was never opened for
writing. It already carries the ADR-099 row (status `🔄`), which landed in `de576f0c` with the ADR
file itself; the checker's file↔row coverage rule forbids splitting them. Evidence in §4.1.

### 2.3 Beyond the expected 3 — the gate-driven fix (2 extra files)

| Path | Lines | Change |
|---|---|---|
| `scripts/generate_provider_catalog.py` | 312 | +4/−2: template renders the enum **without** a class docstring |
| `packages/core/narrare_core/llm/_providers/catalog_generated.py` | 46 | +4/−2: regenerated (docstring out, comment in) |

Why this was unavoidable, and why it is not "accept and regenerate": see §3.3.

```
 apps/api/narrare/setup/base_schemas.py                            | 19 +++++++++----------
 packages/core/narrare_core/llm/_providers/catalog_generated.py    |  6 ++++--
 scripts/generate_provider_catalog.py                              |  6 ++++--
 3 files changed, 17 insertions(+), 14 deletions(-)
```

`git status --short` (working tree, left dirty per ruling 4):

```
 M apps/api/narrare/setup/base_schemas.py
 M packages/core/narrare_core/llm/_providers/catalog_generated.py
 M scripts/generate_provider_catalog.py
?? tests/unit/api/setup/test_ai_provider_identity.py
```

`docs/reference/openapi.json` is **absent** from that list — it was rewritten twice by
`just export-openapi` and ends byte-identical to `HEAD` (§3.4).

## 3. TDD evidence

### 3.1 Steps 1–2 — RED on the re-point (command exactly as the brief names it)

```
$ just test-file tests/unit/api/setup/test_ai_provider_identity.py
tests/unit/api/setup/test_ai_provider_identity.py::test_openapi_component_name_and_values_are_unchanged PASSED [ 33%]
tests/unit/api/setup/test_ai_provider_identity.py::test_base_schemas_reexports_the_generated_enum FAILED [ 66%]
tests/unit/api/setup/test_ai_provider_identity.py::test_setup_schemas_reexports_the_same_object FAILED [100%]

=================================== FAILURES ===================================
________________ test_base_schemas_reexports_the_generated_enum ________________

    def test_base_schemas_reexports_the_generated_enum() -> None:
>       assert FromBaseSchemas is Generated
E       assert FromBaseSchemas is Generated

tests/unit/api/setup/test_ai_provider_identity.py:11: AssertionError
_________________ test_setup_schemas_reexports_the_same_object _________________

    def test_setup_schemas_reexports_the_same_object() -> None:
>       assert FromSchemas is Generated
E       assert FromSchemas is Generated

tests/unit/api/setup/test_ai_provider_identity.py:15: AssertionError
========================= 2 failed, 1 passed in 0.62s ==========================
error: recipe `test-file` failed on line 366 with exit code 1
```

Both failures are the *right* ones: at that moment `base_schemas.py` still declared
`class AIProvider(StrEnum)`, so it was a **different class object** with the same members — the
identity assertion fails, not an import or a value check. (`narrare.setup.schemas` re-exports from
`base_schemas`, so it inherits the same failure; there is no second declaration to fix.)

Test hygiene note: test 3 (`..._name_and_values_are_unchanged`) passed **before** the change too —
it is the contract snapshot, not a discriminator. The tests that actually went RED→GREEN on the
re-point are 1 and 2; test 4 (§5.2) went RED→GREEN on the Core fix (§3.3).

### 3.2 Step 3 — the re-point

```diff
+# Re-export of the generated catalog enum (ADR-099, provider SSOT in Core).
+# The `as AIProvider` form marks it as an explicit re-export so pyright's
+# reportUnusedImport stays quiet while it remains a public name of this module.
+from narrare_core.llm._providers.catalog_generated import AIProvider as AIProvider
+
 # ---------------------------------------------------------------------------
 # Enums — extensible via adding values
+#
+# AIProvider is NOT declared here: it is the generated catalog enum
+# (narrare_core.llm._providers.catalog_generated, ADR-099), imported at the
+# top of this module and re-exported. The provider set has exactly one SSOT.
 # ---------------------------------------------------------------------------
@@
-class AIProvider(StrEnum):
-    ANTHROPIC = "anthropic"
-    ...
-    ZAI = "zai"
```

Deviation from the brief's wording ("keep it adjacent to the other enums"), with evidence: a
module-level import placed in the enums section is rejected by the repo's own lint gate —

```
$ just lint-file apps/api/narrare/setup/base_schemas.py     # import placed where the class was
E402 Module level import not at top of file
  --> apps/api/narrare/setup/base_schemas.py:45:1
I001 [*] Import block is un-sorted or un-formatted
Found 2 errors.
```

So the import sits in the top import block (third-party `pydantic` ⇢ first-party `narrare_core`,
isort-clean) and the enums section carries a note pointing at it. `StrEnum` stays imported: the
three remaining enums use it.

### 3.3 Step 4, first attempt — the acceptance gate FAILED (real drift, not staleness)

```
$ just export-openapi
✅ OpenAPI spec written to .../docs/reference/openapi.json (197 paths, 359 schemas)
EXPORT_EXIT=0

$ git diff --exit-code docs/reference/openapi.json
EXIT_STATUS=1

diff --git a/docs/reference/openapi.json b/docs/reference/openapi.json
@@ -13683,7 +13683,8 @@
           "openrouter",
           "zai"
         ],
-        "title": "AIProvider"
+        "title": "AIProvider",
+        "description": "Provider identifiers; the order matches the catalog."
       },
```

**Why that failure was expected and correct.** The added `description` is verbatim the docstring
of T1's generated `class AIProvider(StrEnum)` (`catalog_generated.py:14`). Pydantic maps an enum
class docstring onto the JSON-schema `description`, so the moment `apps/api` re-exports that
object, `components.schemas.AIProvider` gains a description — the public contract changes on a
commit that was supposed to be a pure re-point. The handwritten enum had no docstring, so `HEAD`'s
artifact has no description. Ruling 5 makes byte-identity the acceptance gate, and it fired.

**Root cause (two "why"s).** Why did the contract change? Because the re-export pulls in an enum
whose docstring pydantic publishes. Why did that enum have a docstring? T1's generator template
emitted one; T1's brief never asked for it (`task-1-brief.md:171-179` says only "the class with one
member per spec"), no T1 test asserts it, and it was invisible while nothing consumed the enum
from a documented API surface. The defect was latent in T1 and **activated** by T2 — exactly the
drift class ADR-099 exists to close.

**Alternatives considered.**

| Option | Verdict |
|---|---|
| Accept the description, regenerate `docs/reference/openapi.json` | Rejected — explicitly forbidden by ruling 5, and a refactor must not change the public contract |
| Strip descriptions in `export_openapi.py` | Rejected — global change to the exporter, affects 359 schemas; a workaround, not a root-cause fix |
| Alias the enum in the API layer (e.g. `AIProvider.__doc__ = None` or a wrapper) | Rejected — breaks the identity that is the *point* of this task (tests 1–2), and pyright/pydantic would still see a class object |
| **Remove the class docstring from the generator template, regenerate** | **Chosen** — root cause, 1 deleted line, artifact stays ruff-clean, information preserved as comments (comments never reach the schema) |

Fix applied to `render_python`: drop the docstring line (and the now-superfluous blank line after
the class header, which `ruff format` would have removed anyway — verified by the first lint run
after the edit), plus a 4-line comment stating *why* the class must stay docstring-free so nobody
re-introduces it.

Independent proof that the fix restores the exact contract, without going through the exporter:

```
old __name__: AIProvider | new __name__: AIProvider
old doc: None | new doc: None
old schema: {'enum': ['anthropic', 'openai', 'google', 'groq', 'ollama', 'openrouter', 'zai'], 'title': 'AIProvider', 'type': 'string'}
new schema: {'enum': [...], 'title': 'AIProvider', 'type': 'string'}
IDENTICAL: True
```

(A scratch probe built a class named `AIProvider` with the old body, no docstring, and compared
`TypeAdapter(...).json_schema()` with the re-exported generated enum — equal. `__name__` is what
drives the title, which is why the generated class name matters and why the identity test pins
it.) A second probe confirmed the rest of the enum semantics are unchanged: member names, values,
order, `str()` and `hash()` equality with the raw strings, `json()`/validation of `"groq"`, and
rejection of `"gemini"`, `"GROQ"`, `""` — all identical.

### 3.4 Step 4, second attempt — the gate is green

```
$ just export-openapi
✅ OpenAPI spec written to .../docs/reference/openapi.json (197 paths, 359 schemas)
EXPORT_EXIT=0

$ git diff --exit-code docs/reference/openapi.json
(no output)
DIFF_EXIT=0
```

The committed component, read back from the file:

```json
      "AIProvider": {
        "type": "string",
        "enum": ["anthropic","openai","google","groq","ollama","openrouter","zai"],
        "title": "AIProvider"
      },
```

Title `AIProvider`, seven values, **no** `description`. Artifact byte-identical to `HEAD`.

### 3.5 GREEN

```
$ just test-file tests/unit/api/setup/test_ai_provider_identity.py tests/unit/scripts/test_generate_provider_catalog.py
tests/unit/api/setup/test_ai_provider_identity.py::test_openapi_component_carries_no_description PASSED [ 87%]
tests/unit/api/setup/test_ai_provider_identity.py::test_setup_schemas_reexports_the_same_object PASSED [100%]

============================== 8 passed in 0.44s ===============================
T1_TEST_EXIT=0
```

`test_generate_provider_catalog.py` (T1's 4 tests, incl. `test_committed_python_artifact_matches_a_fresh_render`
and `test_render_python_is_ruff_format_clean_and_has_no_suppressions`) is green against the amended
template, so the generator still renders ruff-format-clean, suppression-free output that matches
the committed artifact.

RED for the new 4th test (§5.2), reproduced by re-injecting the docstring into the artifact only:

```
$ just test-file tests/unit/api/setup/test_ai_provider_identity.py
>       assert "description" not in TypeAdapter(FromBaseSchemas).json_schema()
E       AssertionError: assert 'description' not in {'description': 'Provider identifiers; the order matches the catalog.', 'enum': [...], 'title': 'AIProvider', 'type': 'string'}
========================= 1 failed, 3 passed in 0.52s ==========================
[restored via] $ uv run --all-packages python scripts/generate_provider_catalog.py
wrote packages/core/narrare_core/llm/_providers/catalog_generated.py
artifact restored byte-identically
$ ... --check
provider catalog check: catalog_generated.py is up to date   (exit 0)
```

## 4. Gates run

| # | Command | Result |
|---|---|---|
| 1 | `just test-file tests/unit/api/setup/test_ai_provider_identity.py` | ✅ 4 passed |
| 2 | `just test-file tests/unit/scripts/test_generate_provider_catalog.py` | ✅ 4 passed |
| 3 | `just test-file tests/unit/api/setup tests/unit/api/settings tests/unit/architecture` | ✅ 644 passed |
| 4 | `git diff --exit-code docs/reference/openapi.json` | ✅ exit **0**, empty (see §3.4) |
| 5 | `uv run --all-packages python scripts/export_openapi.py --check` | ✅ exit 0, "OpenAPI spec up to date (197 paths, 359 schemas)" |
| 6 | `uv run --all-packages python scripts/generate_provider_catalog.py --check` | ✅ exit 0, "is up to date" |
| 7 | `just typecheck` | ⚠️ exit 1, **5 pre-existing** errors in `packages/core/narrare_core/embeddings/rerank.py` (`sentence_transformers` unresolvable ×3 + 2 downstream) — identical to T1's C5 baseline; **none in this task's files** |
| 8 | `just typecheck-file` on all four touched files | ✅ 0 errors, 0 warnings, 0 informations |
| 9 | `just lint-file` on all four touched files | ✅ "All checks passed!" / "4 files already formatted" |
| 10 | `just check` | ⚠️ 10/11 green; **[3/11] Typecheck** is the only failure and is the same pre-existing 5 errors; **[4/11] Typecheck (Tests) 0 errors** |
| 11 | `just test-unit` | ✅ **14073 passed, 3 skipped** in 151.74s |
| 12 | `just check-architecture` | ✅ green (incl. RULE-10: "45 services checked, 0 missing test files, 0 low coverage"; frontend size ratchet 0 new) |
| 13 | `uv run --all-packages python scripts/check_python_file_size.py` | ✅ within hard limits, ratchet did not grow |
| 14 | `uv run --no-sync python scripts/check_doc_drift.py` | ✅ exit 0, "Doc drift check passed (with warnings)", 57 warnings, **no ADR-099 finding** |
| 15 | `uv run --all-packages python -m doc_drift` | ⚠️ not a runnable module in this repo (`No module named doc_drift`); the checker's real entry points are `scripts/check_doc_drift.py` (CI: `ci.yml:577`) and the pre-commit hook `--governance-only` — ran #14 instead |

### 4.1 Step 5 — the ADR-099 index row, verified positively *and* negatively

The brief's shape ("expect **no** `ADR-099 … has no row` finding") is a negative check, which is
weak on its own: it would also pass if the checker silently stopped scanning. So I exercised the
checker's own functions directly (scratch script in `/tmp/opencode`, deleted afterwards; repo
untouched):

```
ADR files scanned: 98
INDEX rows parsed: 98
ADR-099 file present: True
ADR-099 row present: True
ADR-099 row keys: ['status_emoji', 'title']
ADR-099 row: {'title': 'Provider Catalog SSOT — …', 'status_emoji': '🔄'}
files without a row (expect none): []
probe: rows after deleting the ADR-099 row: 97 -> ADR-099 present: False
probe findings: ['ADR-099 exists as file but has no row in INDEX.md']
```

98/98 file↔row coverage, ADR-099 present with status `🔄`, and the negative probe against an
INDEX copy with the row removed produces exactly the message the brief names — so the absence of
that finding in run #14 is meaningful. **No index edit was needed or made.**

## 5. Self-review findings

1. **Root-cause discipline.** The gate failure was not smoothed over: I did not touch
   `docs/reference/openapi.json` (forbidden by ruling 5, and it would have hidden the drift), and I
   did not add a suppression or exporter special case. The cause — a docstring on a *generated,
   contract-bearing* enum — was removed at its source, with a comment in the template explaining
   why it must stay removed.
2. **One test added beyond the brief's three (test hygiene).** The brief's three tests do not
   discriminate the failure that actually bit this task: tests 1–2 pass with or without a
   docstring, and test 3 checks only name/values. I added
   `test_openapi_component_carries_no_description`, asserting
   `"description" not in TypeAdapter(FromBaseSchemas).json_schema()`. Justification: the invariant
   is currently guarded **only** by the manual `git diff --exit-code` gate, because the pre-commit
   hook `openapi-regenerate` (`:160`) *mutates* `docs/reference/openapi.json` and CI's G3c
   (`ci.yml:562`) only compares the committed artifact against a fresh export — a re-added
   docstring would be silently committed and then pass CI. The added test is 10 lines in my own
   new file; the brief's three functions are byte-for-byte as specified. **Strike it if the
   reviewer prefers not to pin this.**
3. **Completeness against the brief.** Steps 1→5 executed in order with the named commands, no
   step skipped. Step 3's required re-export form is exactly
   `from narrare_core.llm._providers.catalog_generated import AIProvider as AIProvider`
   (explicit re-export; pyright `reportUnusedImport` confirmed quiet in gate #8/#10).
   `StoryStructure`, `StoryTone`, `StarterContent` and Steps 1–3 verified untouched by diff.
   Both import paths required by the brief work (`narrare.setup.base_schemas` **and**
   `narrare.setup.schemas`, tests 1–2); the component keeps title `AIProvider` + seven values
   (test 3, §3.4).
4. **No new provider literal in `apps/api` (ruling 3).**
   `rg -n "anthropic|openai|google|groq|ollama|openrouter|zai" apps/api/narrare/setup/base_schemas.py`
   → **no match at all**: after the re-point the file contains zero provider strings, not merely no
   *new* ones.
5. **No suppressions.** grep for `type: ignore` / `pyright: ignore` / `noqa` across all four files
   → none, so the RULE-23 ratchet cannot have grown (consistent with gate #10's clean
   security/typecheck-tests steps).
6. **Not overbuilt.** No TS renderer, no parity checks, no pre-commit/CI/justfile wiring, no new
   abstraction. The only Core-side edit is the docstring removal the gate proved necessary; the
   `ServiceLocator`/DI, router and schema layers are untouched (a plain import change, no service
   behaviour).
7. **Import chain not re-investigated (ruling 2).** No startup/import failure was observed in any
   of the 15 gate runs; `narrare_core.llm._providers` was already on `apps/api`'s import graph via
   `gateway.py`/`provider_service.py`.

## 6. Concerns

* **C1 — the delivery is 4 effective files, not the expected 3, and 2 of them are T1's.** The
  acceptance gate cannot pass without the Core-side docstring removal (§3.3). The coordinator
  should confirm this is the intended resolution rather than, e.g., routing the generator change
  into a T1 fix-up commit or revisiting the "byte-identical" ruling. If the description is judged
  an *improvement*, the alternative is to accept the contract change and regenerate
  `docs/reference/openapi.json` — but that contradicts ruling 5 and my test 4, and it would make
  T2 a contract-changing refactor.
* **C2 — the OpenAPI drift guard is one-directional.** The pre-commit hook regenerates the
  artifact; CI only checks "artifact matches a fresh export". Neither compares the *contract*
  before vs. after, so a schema-shape change can be committed and CI stays green. My test 4
  covers only the `AIProvider` component. A repo-wide guard (export before/after, diff the
  schemas) would close the class of defect, but that is a program-level decision, not T2 scope.
* **C3 — `just typecheck` / `just check` remain red for the pre-existing reason** documented in
  T1's report: `packages/core/narrare_core/embeddings/rerank.py` cannot resolve
  `sentence_transformers` in this worktree venv (5 errors, same lines). Unrelated to this task;
  every touched file typechecks at 0 errors. `just verify` was therefore not run end-to-end
  (its `check` half is #10, already characterised; its `test-all` half needs Docker services and a
  Node toolchain the brief does not name). I ran the decisive unit half instead: #11 (`just
  test-unit`, 14073 passed).
* **C4 — the added comment lives inside a generated file.** `catalog_generated.py` is now 46 lines
  and carries a 4-line "do not add a docstring" comment. It is rendered by the generator, so it
  cannot be hand-edited away unnoticed, but a reader may mistake it for hand-written guidance
  inside an AUTO-GENERATED block.
* **C5 — no regression test in Core for the template rule.** The comment explains the constraint,
  but nothing in `tests/unit/scripts/` fails if the docstring is re-added to the template
  (T1's `test_rendered_python_declares_class_syntax_strenum` does not look at docstrings). My
  test 4 catches it per-component on the API side. A one-line assertion in the generator test
  would be the tighter place; that file belongs to T1, so I left it alone and flag it here.
* **C6 — the unit-suite test count does not reconcile with T1's figure.** HEAD is unchanged
  (`00c743ef`) and `git status` shows only this task's files, yet `just test-unit` reports
  **14073 passed, 3 skipped** where T1's report recorded **14061 passed, 3 skipped**. My change
  adds 4 test functions (tests 1–4), so 14065 would be expected; ~8 are unaccounted for. The full
  unit tree collects **14077** tests via
  `just test-file tests/unit --collect-only -q` (xdist's run reports one fewer), and nothing
  fails. Most likely T1's figure came from a differently-scoped or earlier run (e.g. before T1's
  own `tests/unit/scripts` file existed); worth a glance from the coordinator, but not a
  regression signal from this task.
