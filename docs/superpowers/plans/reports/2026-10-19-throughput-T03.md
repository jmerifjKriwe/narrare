# Task 3 Report — generated TypeScript provider module + wizard type re-point

**Program:** P1 (Developer Throughput) · **Task:** 3 · **Date:** 2026-10-19
**Worktree:** `.local/share/opencode/worktree/3e7abe4e892d779ef964e6da88d52f8213976240/brave-egret`
**Branch:** `brave-egret` · **HEAD:** `d762046f` · **Commits:** none — implementers carry no VCS
authority; no `git add`/`commit`/`stash` was run. Tree left dirty on purpose (file list in §2).

**Status:** DONE

---

## 1. What was implemented

The provider SSOT now has a second renderer. `scripts/generate_provider_catalog.py` renders
`packages/web/lib/providers.generated.ts` from the same `catalog.yaml` that already renders the
Python enum, in both default and `--check` mode. The frontend provider type is therefore derived,
not declared: `packages/web/types/wizard.ts` re-exports the generated union instead of restating
it (RULE-17 closed by construction — T4 then uses `PROVIDER_IDS`/`PROVIDER_LABEL_KEYS` to fix the
settings list).

The four carry-forward findings from Task 1's review were fixed in the same file (it is this
task's file by assignment), each proven by a probe (§5):

1. the id charset can no longer admit a non-identifier (`3gpt` → `3GPT`);
2. `--check` compares **bytes**, so CRLF-only drift is caught (ADR-099 §6);
3. label keys are emitted through `json.dumps`, so a quote/newline cannot emit broken source in
   either language;
4. the `_PYDANTIC_AI_EXTRAS` set now carries a comment tying it to ADR-099 §2 as a deliberate
   restatement, not a missed derivation.

No new provider literal, no type suppression, no human-readable label in the generated module.

## 2. Files

| Path | Lines | Change |
|---|---|---|
| `scripts/generate_provider_catalog.py` | 389 (was 312) | +110/−33: `render_typescript`, `_string_literal`, `_TS_HEADER`, byte-based `_check` over both artifacts, id hardening, extras comment, `main()` wiring |
| `packages/web/lib/providers.generated.ts` | 32 | **new** (generated; `??` untracked until the coordinator commits) |
| `packages/web/types/wizard.ts` | 101 (was 102) | +7/−8: inline `AIProvider` union deleted, generated union imported + re-exported |
| `tests/unit/scripts/test_generate_provider_catalog.py` | 97 (was 40) | +57/−0: brief's 2 TS tests + 2 carry-forward tests |
| `docs/superpowers/plans/reports/2026-10-19-throughput-T03.md` | this file | new |

`git status --short` (tree left dirty):

```
 M packages/web/types/wizard.ts
 M scripts/generate_provider_catalog.py
 M tests/unit/scripts/test_generate_provider_catalog.py
?? packages/web/lib/providers.generated.ts
```

`packages/core/narrare_core/llm/_providers/catalog_generated.py` is **not** in that list: after the
renderer changes it re-renders byte-identically to `HEAD` (`git diff` empty), which is itself
evidence that the escaping and id narrowing did not perturb the existing artifact.

## 3. TDD evidence

### 3.1 Step 1–2 — RED (command exactly as the brief names it)

```
$ just test-file tests/unit/scripts/test_generate_provider_catalog.py
collecting ... collected 0 items / 1 error

==================================== ERRORS ====================================
____ ERROR collecting tests/unit/scripts/test_generate_provider_catalog.py _____
ImportError while importing test module '.../tests/unit/scripts/test_generate_provider_catalog.py'.
tests/unit/scripts/test_generate_provider_catalog.py:6: in <module>
    from scripts.generate_provider_catalog import (
E   ImportError: cannot import name 'render_typescript' from 'scripts.generate_provider_catalog'
=========================== short test summary info ============================
ERROR tests/unit/scripts/test_generate_provider_catalog.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
error: recipe `test-file` failed on line 366 with exit code 2
```

**Why this is the right RED.** The failure is the *named* missing symbol (`render_typescript`; the
same import also names `TS_OUTPUT`), i.e. the two new symbols the task was asked to produce — not a
syntax error, not a wrong-value assertion. The module collected 0 tests because collection aborts,
which is the expected shape when the renderer under test does not exist yet.

### 3.2 Step 5 — GREEN

```
$ just test-file tests/unit/scripts/test_generate_provider_catalog.py
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_id_without_a_leading_letter PASSED [ 12%]
tests/unit/scripts/test_generate_provider_catalog.py::test_catalog_lists_the_seven_providers_in_canonical_order PASSED [ 25%]
tests/unit/scripts/test_generate_provider_catalog.py::test_rendered_python_declares_class_syntax_strenum PASSED [ 37%]
tests/unit/scripts/test_generate_provider_catalog.py::test_committed_python_artifact_matches_a_fresh_render PASSED [ 50%]
tests/unit/scripts/test_generate_provider_catalog.py::test_render_python_is_ruff_format_clean_and_has_no_suppressions PASSED [ 62%]
tests/unit/scripts/test_generate_provider_catalog.py::test_renderers_escape_hostile_label_keys PASSED [ 75%]
tests/unit/scripts/test_generate_provider_catalog.py::test_committed_typescript_artifact_matches_a_fresh_render PASSED [ 87%]
tests/unit/scripts/test_generate_provider_catalog.py::test_rendered_typescript_declares_ids_and_label_keys PASSED [100%]

============================== 8 passed in 2.34s ===============================
```

The two brief tests are `test_rendered_typescript_declares_ids_and_label_keys` and
`test_committed_typescript_artifact_matches_a_fresh_render`; both went RED→GREEN on this change.
The two carry-forward tests went RED→GREEN on their own fixes (id test: RED against the old
`[a-z0-9_]+` a scratch check confirmed; escaping test: only passes with `_string_literal`).

### 3.3 Changed-file Python lint / typecheck

```
$ just lint-file tests/unit/scripts/test_generate_provider_catalog.py scripts/generate_provider_catalog.py
All checks passed!
2 files already formatted
$ just typecheck-file ... (both files)
0 errors, 0 warnings, 0 informations
```

(The first lint run caught I001 + TC003 in the test file — fixed by moving `Path` into a
`TYPE_CHECKING` block and letting ruff sort the imports; final state above.)

### 3.4 Neighbouring suites

```
$ just test-file tests/unit/scripts
============================ 1383 passed in 23.99s =============================
$ cd packages/web && npx vitest run lib/providers.test.ts
 Test Files  1 passed (1)
      Tests  4 passed (4)
```

## 4. Required gate results

### 4.1 `biome check` on the committed generated file (as rendered, no `--write`)

```
$ cd packages/web && npx biome check lib/providers.generated.ts types/wizard.ts
Checked 2 files in 5ms. No fixes applied.
BIOME_EXIT=0
```

`biome check` (formatter + linter + organizeImports assist, no fix flag) exits **0** on the file
exactly as the renderer writes it. The renderer, not the artifact, carries the formatting: the
union is emitted with the two-space-indented `|` continuation biome chooses (the single-line form
would be 102 columns, two over `lineWidth: 100`), and the ids as a multi-line `as const satisfies`
tuple.

`just lint-frontend` over the whole web package also exits **0** (1 pre-existing warning + 1
pre-existing info in `packages/web/test/test-utils.tsx`, unrelated to this task).

### 4.2 `just typecheck-frontend`

```
$ just typecheck-frontend
cd packages/web && pnpm type-check
$ tsc --noEmit
TYPECHECK_EXIT=0
```

Zero `tsc` errors. This is the gate that proves the re-point works for *consumers*: `@/types` →
`types/index.ts` → `wizard.ts` → `@/lib/providers.generated`, and `lib/providers.ts` still imports
`AIProvider` from `@/types` unchanged.

### 4.3 `--check` exit status

```
$ uv run --all-packages python scripts/generate_provider_catalog.py --check
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
CHECK_EXIT=0
```

Both artifacts verified in one pass, exit **0**.

### 4.4 Other checks

```
$ uv run --all-packages python scripts/check_frontend_file_size.py
✅ All TS/TSX files are within hard limits
Frontend file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
```

## 5. Carry-forward items — one line each

1. **Id charset admits non-identifiers — SATISFIED.** `_ID_PATTERN` is now `[a-z][a-z0-9_]*`
   (leading letter required) **and** `_parse_provider` asserts
   `_member_name(provider_id).isidentifier()` with a dedicated error; proven by the new test
   `test_load_catalog_rejects_id_without_a_leading_letter` (`3gpt` → ValueError on field `id`).
2. **`--check` must compare bytes — SATISFIED.** `_check` compares `path.read_bytes()` against
   `rendered.encode("utf-8")` for **both** artifacts; the unified diff still renders decoded text.
   Probe A rewrote the TS artifact with CRLF only — old code would have called it clean, the new
   code exits 1 (see §5.1).
3. **Unescaped interpolation — SATISFIED.** `_string_literal` (`json.dumps`) now wraps every
   emitted id and `label_key` in both renderers; proven by
   `test_renderers_escape_hostile_label_keys`, which asserts a `"`/`\`/newline label renders as a
   single escaped literal in Python *and* TS and never as raw text.
4. **`_PYDANTIC_AI_EXTRAS` restates the seven ids — SATISFIED.** The comment above the set now
   states explicitly that this is ADR-099 §2's "Closed literal set" (pydantic-ai's integration
   names, external to the catalog), that `_parse_provider` validates the catalog against it, and
   that a new integration must be added there first — so it does not read as a missed derivation.

### 5.1 Byte-comparison probes (run with the artifact restored afterwards)

```
### Probe A: CRLF-only rewrite of the TS artifact (bytes differ, decoded text equal)
CRLF bytes written: 32 crlf lines
provider catalog check: ...catalog_generated.py is up to date
--- packages/web/lib/providers.generated.ts (committed)
+++ packages/web/lib/providers.generated.ts (fresh render)
@@ -1,32 +1,32 @@
-// AUTO-GENERATED by scripts/generate_provider_catalog.py — DO NOT EDIT
...
A_EXIT=1

### Probe B: content drift (drop a provider line) — expect exit 1 + diff
@@ -18,6 +18,7 @@
   "openrouter",
+  "zai",
 ] as const satisfies readonly AIProvider[];
provider catalog check FAILED: packages/web/lib/providers.generated.ts is stale — regenerate ...
B_EXIT=1

### Restored; --check green again
RESTORE_EXIT=0
git status --short   # only the 4 expected entries; artifacts restored
```

Probe A is the discriminating one: `read_text(encoding="utf-8")` applies universal-newline
translation and would have reported the CRLF file "up to date" while the committed bytes differed.

## 6. Self-review

1. **Root cause, no workaround.** The generator is the only place formatted output is decided; the
   artifact is never hand-fixed. Biome's union-continuation choice was derived (line is 101 columns)
   and encoded in the template, then confirmed with a no-fix `biome check`.
2. **Brief steps 1→5 in order.** Test extension → RED (captured) → `render_typescript` +
   `main()` wiring → wizard re-point → generate + all gates. Only the inherited
   `--check` signature changed shape (one string → two), which the brief explicitly asked for
   ("wire `TS_OUTPUT` into both modes of `main()`").
3. **Generated module carries no label (RULE-16).** `PROVIDER_LABEL_KEYS` values are the exact
   catalog i18n keys (`settings-ai.providers.<id>`); a grep for display strings (`Anthropic`,
   `OpenAI`, `Z.AI`, …) in the file finds none — only lowercase ids and keys.
4. **Frozen interface for T4.** The module exports exactly `AIProvider`, `PROVIDER_IDS`
   (`as const satisfies readonly AIProvider[]`, canonical order) and
   `PROVIDER_LABEL_KEYS: Record<AIProvider, string>`.
5. **No suppressions** in any changed file (`type: ignore` / `pyright: ignore` / `@ts-ignore` /
   `@ts-expect-error` → none), so the RULE-23 ratchet cannot have grown.
6. **Untouched as required.** `StarterContent`, `StoryStructure`, `StoryTone`, `ProviderModel`,
   `ModelCatalogProvenance`, `DemoProjectInfo`, `WizardState` are byte-identical (`git diff` on
   `wizard.ts` shows only the union replacement).
7. **Not overbuilt.** Two extra tests beyond the brief, each pinning a mandatory carry-forward
   item that the brief's two tests cannot see; no parity checks, no pre-commit/CI/justfile wiring,
   no new abstraction.

## 7. Concerns

* **C1 — the generated TS artifact is untracked in this report.** I hold no commit authority, so
  `providers.generated.ts` is `??` in `git status`; "committed file" in §4.1 means the working-tree
  bytes the coordinator will commit. The bytes are what `--check` validated, so the commit cannot
  change them.
* **C2 — `just typecheck-frontend` is the local proof; the repo-wide `just check` is red for a
  reason unrelated to this task** (`sentence_transformers` in
  `packages/core/narrare_core/embeddings/rerank.py`, the same 5 pre-existing errors recorded in
  T1/T2). Nothing in the touched files contributes to it.
* **C3 — `render_typescript` (like `render_python`) does not guard against an empty catalog.**
  `load_catalog` never enforces a non-empty `providers:` list, so an empty list would render a
  syntactically broken union. This mirrors the pre-existing Python renderer and is out of the
  brief's scope; flagging it rather than silently adding behaviour.
* **C4 — `packages/web/lib/providers.ts` still carries the hand-maintained `PROVIDERS` labels.**
  That is T4's deliverable (ADR-099 point 7); deliberately not touched here, per the brief's file
  list.
