# Task 4 Report — fix the settings provider list from the shared derived list (Groq/Z.AI defect)

**Program:** P1 (Developer Throughput) · **Task:** 4 · **Date:** 2026-10-19
**Worktree:** `.local/share/opencode/worktree/3e7abe4e892d779ef964e6da88d52f8213976240/brave-egret`
**Branch:** `brave-egret` · **HEAD:** `162db8b9` · **Commits:** none — implementers carry no VCS
authority; no `git add`/`commit`/`stash` was run. Tree left dirty on purpose (file list in §2).

**Status:** DONE

**Mandatory review:** yes (changes the consumer of a public API shape — the `PROVIDERS` entry type
and `getProviderLabel` signature).

---

## 1. What was implemented

The Studio → Settings → AI provider picker no longer owns a hand-maintained list. Both the settings
form (`ProviderForm.tsx`, which held a 5-entry `PROVIDER_OPTIONS` array) and the wizard
(`WizardStep4.tsx`, which consumed the 7-entry `PROVIDERS`) now render the list derived once from
the generated catalog, and each option's text is an i18n key resolved through a **root**
translator.

The `PROVIDERS` array gained the generated shape
(`{ value: AIProvider; labelKey: string }` derived from `PROVIDER_IDS`/`PROVIDER_LABEL_KEYS`) and
`getProviderLabel` gained the translator parameter, keeping its raw-value fallback for unknown
providers. The dead `providerLabel` export was deleted.

The user-visible defect — Groq and Z.AI were unpickable in Settings → AI — is closed and pinned by
two regression tests plus a locale-resolution guard that a component test structurally cannot
provide.

## 2. Files

| Path | Change |
|---|---|
| `packages/web/lib/providers.ts` | rewritten: `PROVIDERS` derived from `PROVIDER_IDS`/`PROVIDER_LABEL_KEYS`; `getProviderLabel(value, t)`; re-exports `AIProvider`/`PROVIDER_IDS`/`PROVIDER_LABEL_KEYS` |
| `packages/web/lib/providers.test.ts` | +4 tests: key assertions for all 7 ids, preserved unknown/case/empty cases, and the R2 locale-resolution guard (en/de/fr) |
| `packages/web/components/studio/settings/ProviderForm.tsx` | deleted `PROVIDER_OPTIONS` + `providerLabel`; added root `tProviders`; renders `PROVIDERS` / `tProviders(labelKey)` |
| `packages/web/components/studio/wizard/WizardStep4.tsx` | added root `tProviders`; option text is `tProviders(p.labelKey)` instead of `p.label` |
| `packages/web/components/studio/settings/ProviderForm.test.tsx` | +2 regression tests (extended the existing colocated 11-test file; no second file created) |
| `docs/superpowers/plans/reports/2026-10-19-throughput-T04.md` | this file |

`git status --short` (tree left dirty):

```
 M docs/superpowers/plans/2026-10-19-dev-throughput-program.md
 M packages/web/components/studio/settings/ProviderForm.test.tsx
 M packages/web/components/studio/settings/ProviderForm.tsx
 M packages/web/components/studio/wizard/WizardStep4.tsx
 M packages/web/lib/providers.test.ts
 M packages/web/lib/providers.ts
```

The first entry (`docs/superpowers/plans/2026-10-19-dev-throughput-program.md`) is **not mine** — it
is the coordinator's two corrections + two rulings carried in the worktree before this task started
(`git diff` shows only the Task 4 text block). My authored changes are the five `packages/web`
entries.

## 3. TDD evidence

### 3.1 Step 1–2 — RED (the defect's proof)

Command exactly as the brief names it:

```
$ cd packages/web && pnpm test -- ProviderForm
```

Note: the `-- ProviderForm` positional filter was not honoured by this pnpm/vitest combination; the
run executed the whole suite (461 files). The only two failures in it are the two new regression
tests, so the evidence is unaffected. Verbatim output of the failure block:

```
⎯⎯⎯⎯⎯⎯⎯ Failed Tests 2 ⎯⎯⎯⎯⎯

 FAIL  components/studio/settings/ProviderForm.test.tsx > ProviderForm > provider select (Groq/Z.AI defect) > offers every catalog provider in canonical order
AssertionError: expected [ 'openai', 'anthropic', …(3) ] to deeply equal [ 'anthropic', 'openai', …(5) ]

- Expected
+ Received

  [
+   "openai",
    "anthropic",
-   "openai",
    "google",
-   "groq",
    "ollama",
    "openrouter",
-   "zai",
  ]

 ❯ components/studio/settings/ProviderForm.test.tsx:293:30
    291|         <ProviderForm mode="add" onSubmit={vi.fn()} onCancel={vi.fn()}…
    292|       );
    293|       expect(optionValues()).toEqual([
       |                              ^
    294|         "anthropic",
    295|         "openai",

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/2]⎯

 FAIL  components/studio/settings/ProviderForm.test.tsx > ProviderForm > provider select (Groq/Z.AI defect) > offers groq and zai specifically (the reported defect)
AssertionError: expected [ 'openai', 'anthropic', …(3) ] to include 'groq'
 ❯ components/studio/settings/ProviderForm.test.tsx:308:30
    306|         <ProviderForm mode="add" onSubmit={vi.fn()} onCancel={vi.fn()}…
    307|       );
    308|       expect(optionValues()).toContain("groq");
       |                              ^
    309|       expect(optionValues()).toContain("zai");
    310|       const labels = Array.from(

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[2/2]⎯

 Test Files  1 failed | 460 passed (461)
      Tests  2 failed | 3926 passed (3928)
```

**The defect, exactly as reported.** The received option set is five values — `openai`, `anthropic`,
`google`, `ollama`, `openrouter` (in that order, the order of the deleted `PROVIDER_OPTIONS`) — and
`groq`/`zai` are absent. Steps 3–5 then made both tests green.

### 3.2 Step 4/6 — GREEN

```
$ cd packages/web && pnpm exec vitest run lib/providers.test.ts components/studio/settings/ProviderForm.test.tsx
 Test Files  2 passed (2)
      Tests  21 passed (21)
```

21 = the 13 `ProviderForm` tests (11 pre-existing + 2 new) and the 8 `providers.test` tests
(4 preserved `getProviderLabel` cases + 4 new locale/coverage cases).

### 3.3 R2 mutation probe — the guard can fail

To satisfy the ruling's sanity check, one label key was temporarily regressed to the
non-namespaced form (`zai: "settings.providers.zai"` in `providers.generated.ts`) and the guard
re-run:

```
$ cd packages/web && pnpm exec vitest run lib/providers.test.ts
 FAIL  lib/providers.test.ts > provider label keys resolve against the real locale trees > resolves every provider label as human-readable text (de)
AssertionError: de:zai must resolve to text: expected '' to be truthy
 ...
 FAIL  lib/providers.test.ts > ... (fr)
❯ expectAllProvidersResolve lib/providers.test.ts:89:73
 Test Files  1 failed (1)
      Tests  4 failed | 4 passed (8)
```

Four failures (the three locale tests + the `getProviderLabel("zai")` key assertion) — the guard
genuinely discriminates. The generated file was restored immediately and re-verified
(`8 passed`, bytes back to `settings-ai.providers.zai`).

## 4. Gate results

### 4.1 `just test-frontend`

```
$ just test-frontend
cd packages/web && pnpm test
 Test Files  461 passed (461)
      Tests  3932 passed (3932)
   Duration  182.11s
```

Baseline before this task was 3926 tests; the delta is exactly the 6 new tests. No pre-existing test
changed colour.

### 4.2 `just typecheck-frontend`

```
$ just typecheck-frontend
cd packages/web && pnpm type-check
$ tsc --noEmit
```

Exit 0, zero `tsc` errors, no type suppressions added.

### 4.3 `just lint-frontend`

```
$ just lint-frontend
cd packages/web && pnpm lint:check
Checked 1313 files in 1711ms. No fixes applied.
Found 1 warning.
Found 1 info.
```

Exit 0. The single warning is pre-existing and unrelated: an unused `biome-ignore` suppression
comment in `components/studio/extraction/__tests__/ExtractionPanel.test.tsx:29` (not in this task's
file set). The first run of this gate reported four formatter/organizeImports findings in my new
code; they were resolved by letting biome format the five changed files (safe fixes only), after
which the gate is clean.

### 4.4 `grep -rn 'Groq\|Z\.AI' packages/web/components`

```
packages/web/components/studio/settings/ProviderForm.test.tsx:278:  // catalog, not a hand-maintained 5-entry list (Groq/Z.AI were unpickable).
packages/web/components/studio/settings/ProviderForm.test.tsx:280:  describe("provider select (Groq/Z.AI defect)", () => {
```

Neither hit is a provider-label literal. Both are the regression test's own comment and test-suite
name, which the plan's Step 1 text specifies verbatim. No component renders `"Groq"` or `"Z.AI"` as
display text — labels are now `settings-ai.providers.<id>` keys resolved at runtime
(`RULE-16` satisfied: a separate grep for the label strings across the two consumer components
returns nothing).

### 4.5 RULE-04 frontend file size

```
$ uv run --all-packages python scripts/check_frontend_file_size.py
✅ All TS/TSX files are within hard limits
Frontend file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
RESULT: Frontend file-size debt did not grow
```

The extended test file is 317 lines and every changed source file stays well under the limit
(`providers.ts` 16, `providers.test.ts` 121, `ProviderForm.tsx` 128, `WizardStep4.tsx` 168).

## 5. Rulings and corrections — one line each

1. **Correction 1 (no second test file) — SATISFIED.** The regression tests were appended to the
   existing colocated `packages/web/components/studio/settings/ProviderForm.test.tsx` (11 tests),
   keeping its `<ProviderForm mode="add" … t={identity} />` convention; the brief's
   `…/settings/__tests__/ProviderForm.test.tsx` path was not created.
2. **Correction 2 (delete the dead export) — SATISFIED.** `ProviderForm`'s `providerLabel` was
   deleted with the `PROVIDER_OPTIONS` map; `grep -rn providerLabel packages/web` now returns no
   reference (a compile would have caught a hidden importer, and typecheck is clean).
3. **Ruling T4-R1 (root translator) — SATISFIED.** `ProviderForm` adds `const tProviders =
   useTranslations();` (keeping the namespaced `t` prop for its own strings) and `WizardStep4` adds
   `const tProviders = useTranslations();` alongside its existing `useTranslations("studio")`; both
   render `tProviders(labelKey)`, so the fully-qualified key resolves at the root rather than to
   `studio.settings-ai.providers.<id>`. Precedent followed: `analysis/DialogueCoachPanel.tsx:50`.
4. **Ruling T4-R2 (locale-resolution guard) — SATISFIED.** `providers.test.ts` resolves every id's
   real key against the imported `packages/i18n/messages/{en,de,fr}/settings-ai.json` trees through
   a dotted-path lookup that mirrors `lib/i18n/request.ts`'s namespace mapping, asserting a truthy,
   non-key string for all seven ids in all three locales; the failure-mode reasoning (the guard's
   only discriminator for the `settings.providers.<id>` regression is the namespace-prefix check —
   the walked `settings-ai.json` trees resolve `providers.ollama` regardless) is in a comment, and
   §3.3 proves the guard goes red under that mutation.

## 6. Visible label change (as the plan requires flagging)

Settings → AI → Add provider option text changed from the hardcoded English of the deleted map to
the localized i18n values:

| id | before (hardcoded) | after (en i18n) |
|---|---|---|
| anthropic | `Anthropic / Claude` | `Anthropic` |
| openai | `OpenAI` | `OpenAI` |
| google | `Google / Gemini` | `Google AI` |
| ollama | `Ollama (Local)` | `Ollama` |
| openrouter | `OpenRouter` | `OpenRouter` |
| groq | *(absent)* | `Groq` |
| zai | *(absent)* | `Z.AI` |

> Note: `providers.ollamaLocal` (`"Ollama (local)"` in all three locale files) is now unreferenced —
> `grep -rn ollamaLocal` returns only the three message definitions and no code reference; its
> consumer was the deleted `lib/providers.ts` entry. It is left in place for the i18n cleanup pass.

Also, and this is the actual fix: the order becomes the canonical catalog order and two entries
appear that could not previously be chosen. German/French now follow their own catalogs
(`packages/i18n/messages/{de,fr}/settings-ai.json`) instead of English. The wizard's English labels
were already these values for every provider except one: its previous hardcoded label for `ollama`
was `Ollama (local)` (from the deleted `lib/providers.ts` list) and it now renders `Ollama`; for the
other six providers the wizard's only change is that their labels are now locale-aware. This is the
intended RULE-16 change and the only user-visible text change in the task.

## 7. Concerns

* **C1 — `pnpm test -- ProviderForm` does not filter with this pnpm/vitest pair.** The command the
  brief names runs the whole 461-file suite (~3 min) instead of the one file; harmless for evidence
  but slow for iteration. I used `pnpm exec vitest run <path>` for targeted runs. Not a code defect;
  flagged in case the plan's other tasks rely on that invocation.
* **C2 — `getProviderLabel` now has no production consumer** (only its own test exercises it). It
  was already unused outside the test before this task; the plan explicitly keeps it and its
  fallback behaviour, so it was preserved rather than deleted. If a future task decides unused
  exports should go, `PROVIDER_IDS`/`PROVIDER_LABEL_KEYS` re-exports in `providers.ts` are in the
  same position.
* **C3 — the label lookup is `PROVIDERS.find(...)` per call.** O(n) over seven entries, called once
  per option render — not a performance concern at this size; noted only so a reviewer does not
  have to re-derive it.
* **C4 — the R2 guard reaches outside `packages/web` (into `packages/i18n`).** That directory is a
  separate workspace package; the repo already has this pattern in several test files
  (`lib/test-utils.tsx`, `lib/__tests__/token-profile-i18n.test.ts`, `components/series/__tests__/…`),
  so it is not novel, but it means `providers.test.ts` fails if a locale file is renamed — which is
  the intended coupling for a labels-locale invariant.

---

## 8. Fix round — review findings (accuracy only, no behaviour change)

Two accuracy findings from the independent task review. No source, catalog or generated file was
touched; the two files below are the whole change. The coordinator's ruling T4-R3 stands: the uniform
`settings-ai.providers.<id>` mapping is intended, and `providers.generated.ts:29` /
`catalog.yaml:49` were not re-pointed.

### 8.1 Finding 1 — the §6 table was wrong on the `ollama` row

**What was wrong.** §6's `ollama` row read `Ollama (Local)` → `` `Ollama (local)` ``. That is false.
`PROVIDER_LABEL_KEYS.ollama` (`packages/web/lib/providers.generated.ts:29`) is
`settings-ai.providers.ollama`, and `providers.ollama` is the string `"Ollama"` in all three locale
files (`packages/i18n/messages/{en,de,fr}/settings-ai.json`), so the rendered value is `Ollama`. The
string `Ollama (local)` lives in the *separate* entry `providers.ollamaLocal`, which no code
references. The report copied the stale wording from the commit message, which carries the same
error.

**Every row re-checked.** "Previous" values were read from the two lists the diff deletes —
`PROVIDER_OPTIONS` in `packages/web/components/studio/settings/ProviderForm.tsx` (5 entries) for the
Settings table, and the `PROVIDERS` array in the deleted `packages/web/lib/providers.ts` (7 entries)
for the wizard. "After" values were read from `PROVIDER_LABEL_KEYS` plus the three locale files.

| id | before — `ProviderForm.tsx` `PROVIDER_OPTIONS` | after — `PROVIDER_LABEL_KEYS` + locale value | verdict |
|---|---|---|---|
| anthropic | `Anthropic / Claude` | `settings-ai.providers.anthropic` → `Anthropic` | already correct |
| openai | `OpenAI` | `settings-ai.providers.openai` → `OpenAI` | already correct |
| google | `Google / Gemini` | `settings-ai.providers.google` → `Google AI` | already correct |
| ollama | `Ollama (Local)` | `settings-ai.providers.ollama` → `Ollama` | **corrected** (was reported as `Ollama (local)`) |
| openrouter | `OpenRouter` | `settings-ai.providers.openrouter` → `OpenRouter` | already correct |
| groq | *(absent — not in `PROVIDER_OPTIONS`)* | `settings-ai.providers.groq` → `Groq` | already correct |
| zai | *(absent — not in `PROVIDER_OPTIONS`)* | `settings-ai.providers.zai` → `Z.AI` | already correct |

**One row corrected**, and it is the `ollama` row: its *previous* value (`Ollama (Local)`) was right,
its *after* value was wrong. No other row's previous or after value needed changing.

**Wizard sentence corrected.** The paragraph below the table claimed the wizard's English labels
"were already these values". That holds for six of seven providers but not for `ollama`: the wizard
previously rendered `p.label` from the deleted `lib/providers.ts` list, whose `ollama` entry was
`Ollama (local)`, and it now renders `Ollama`. The paragraph now states that single exception while
keeping its overall claim (the two unpickable providers now appear, the labels become locale-aware,
this is the intended RULE-16 change).

**`ollamaLocal` note added.** `providers.ollamaLocal` is now unreferenced:

```
$ grep -rn "ollamaLocal" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next
./packages/i18n/messages/{en,de,fr}/settings-ai.json:7:    "ollamaLocal": "Ollama (local)",
```

Only the three message definitions remain (the two other hits are prior-review/ADR prose, not code);
no `.ts`/`.tsx`/`.py` consumer survives — its only consumer was the deleted `lib/providers.ts`
entry. It is deliberately left in place for the i18n cleanup pass, and §6 carries that one-line note.

§5's ruling T4-R2 summary repeated the same mistaken reasoning and was corrected there too.

### 8.2 Finding 2 — the guard comment overstated its mechanism

`packages/web/lib/providers.test.ts:49-57` argued the `settings.providers.<id>` regression "would
fail anyway" because `settings.json`'s `providers` is the string `"Providers"`. That describes the
production next-intl lookup, not this test: `resolveProviderKey` only ever indexes the
`settings-ai.json` trees imported at `:2-4`, where `providers.ollama` *does* resolve. A key
`settings.providers.<id>` with the prefix check removed would walk those trees to a truthy, non-key
string and the assertions would **pass** — so the prefix check at `:69` is the guard's only
discriminator, and a maintainer trusting the old comment could delete it and silently lose the
protection.

Reworded to say exactly that (the tree walk alone would resolve a `settings-ai.*`-prefixed key
regardless of the regression; it is the prefix assertion that catches it), with the production
`settings.json` detail kept only as an explicit aside. **No assertion changed.**

### 8.3 Gates re-run after the edits

Re-running the suite is expected here: the edited comment lives in the same file as the assertions.

```
$ cd packages/web && pnpm test -- providers.test
 Test Files  461 passed (461)
      Tests  3932 passed (3932)
   Duration  183.96s
```

Same totals as §4.1 (the positional filter is still not honoured — concern C1 — so this is the full
frontend suite; the 8 `providers.test` tests are included and green). Then:

```
$ just typecheck-frontend   → exit 0, no tsc output
$ just lint-frontend        → exit 0, Checked 1313 files, Found 1 warning, Found 1 info
```

The single lint warning is the same pre-existing unrelated one recorded in §4.3
(`ExtractionPanel.test.tsx:29`). No behaviour change: the two edited files are the report and one
comment in `providers.test.ts`.
