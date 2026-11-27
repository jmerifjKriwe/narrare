# Localization Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers do not commit; the coordinator commits only after an independent review is green, and names the implementer's and the reviewer's models at every dispatch from the developer's local assignment.

**Goal:** Make a fourth language a data change, show every failure in the reader's language, download only the catalog a reader reads, and give manuscript text in a Han script its language's own face.

**Architecture:** An ordered registry is the one list of languages; the generator derives every view from it and refuses a registry entry without a catalog and the reverse. Failures carry a typed code from the kernel to an exhaustive catalog mapping and are translated when a face renders, never when it catches. Non-source catalogs are lazy modules the generator emits and the shell loads once, on demand, through a small store. Manuscript prose carries its `lang`, and `:lang()` rules pick the font stacks.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, Alembic, PostgreSQL, pytest; Node 22, pnpm 11.5.2, Vite 8, React 19, TypeScript 7, Vitest 5, Playwright; `intl-messageformat` 12.1.4 and the existing generated catalogs.

**Spec:** `docs/superpowers/specs/2026-11-25-i18n-architecture-hardening-design.md` — it amends rule 5 of `docs/_shared/CONSTRAINTS.md` and records its governance statements in §7.

## Global Constraints

- Python `>=3.14`; CI runs Node 22, pnpm `11.5.2` and just `1.58.0`. Code was revalidated at `main` `12186926e`; every task addresses code by symbol, never by line number.
- Rule 5 of `docs/_shared/CONSTRAINTS.md` as Task 2 amends it: English in code, tests and developer documentation; user-visible text in every catalog; the languages and their display order come from `i18n/registry/locales.json`, never from a list in code; every catalog is sorted, carries the same keys and writes every plural category its language has except a lone `many`; a missing key is a build error.
- No new check script, hook, gate or mandatory document. Design §7 carries the three governance statements for the registry, the typed code union and the plural-rule test. Task evidence goes into the SDD task report under `.superpowers/sdd/` (git-ignored), never into `docs/`.
- Lane A: branch `feat/i18n-hardening`, one pull request, one commit per task, a whole-branch review at the end. A task is a commit slice, never a pull request. UI and frontend tasks are implemented and reviewed by subagents.
- Nothing is committed before the review is green. The coordinator commits with `git commit --trailer "Assisted-by: OpenCode (<model>)"`. Conventional commits; `fix` and `perf` carry a real `User-visible:` line; work no user can observe uses a hidden type (`chore`, `refactor`, `test`) and states its effect. `--no-verify` and force push are forbidden.
- Three gate tiers, kept apart:
  - **Inner loop** — the files a step names: `just test-file <path>`, `CI=true pnpm --dir web exec vitest run <files>`, `just test-e2e-file <path> -k <word>`.
  - **Task gate** — before the reviewer, with its output read: `just check` (lint and types only); `CI=true just test-frontend` for any task that touches `web/` or `app/capabilities/*/web/`; `just test` for Tasks 5 and 6 and `just test-file <touched test files>` for the other backend tasks; `CI=true just check-generated` for any task that touches a generated view or its source (it needs the network); the E2E suites the task names, as `just test-e2e <capability>`.
  - **Branch gate** — once, before the whole-branch review: `CI=true just verify all`.
  A pull request that touches a shared surface (`web/`, `i18n/`, `app/api/`, `app/kernel/`, the conftests, `justfile` or either lockfile) owes all six E2E suites (`scripts/affected.py`, `SHARED`). A push to `main` sets `mode="--none"` and owes none.
- The only permitted fake is the LLM provider at its boundary (rule 2). No test intercepts an API answer.
- Tests read a language's real catalog through `web/lib/test/catalogs.ts` once it exists (Task 10); none compares rendered text with the store's fallback.
- A test that mocks a module of that bed — `./catalog` or `./generated/catalogs` — starts with `vi.resetModules()`, imports what it tests dynamically, and calls `preloadCatalogs()` when it needs the preloaded store: the setup file has already evaluated those modules.
- No right-to-left work, no new language, no translation of novel content, demo novels, help or AI prompts, no palette, no server-side `<html lang>`, no registry membership for `novels.language`, no extension of the formality overlay.
- `CI=true` for `just test-frontend` and `just check-generated` in the shared checkout; `just check` and `just typecheck` run without it. Pre-commit runs on the staged files only.

## Review Focus

1. **A language switch while a failure is on screen** — the failure re-renders in the new language; no stored string freezes it (Task 8).
2. **A catalog chunk that cannot be fetched** — the first paint falls back to the source language, a switch stays where it was, nothing hangs (Task 11).
3. **A tag the registry does not carry verbatim** — `de-AT`, `zh-Hans-CN`, `tlh` — resolves or falls back without throwing; only the Settings API refuses (Task 4).
4. **A plural message that skips a category its language requires** — refused with language, key and category, while French stays valid without `many` (Task 2).
5. **A manuscript in a Han language under a German interface** — the prose carries its `lang` and reads its own stacks (Task 12).

---

## File Structure

- `i18n/registry/locales.json` — the ordered list of languages; the one place a language is registered.
- `scripts/generate_capabilities.py` — reads the registry, checks parity, writes `localeOrder`, `errorCodes.ts`, `endonyms`, `catalogLoaders` and one lazy module per language.
- `app/generated/locales.py`, `web/lib/generated/catalogs.ts`, `web/lib/generated/catalogs/<identifier>.ts`, `web/lib/generated/errorCodes.ts` — generated views; never edited by hand.
- `i18n/en.json`, `i18n/de.json`, `i18n/fr.json` — twenty `numberWords.*` keys and seventeen `errors.*` keys each.
- `web/lib/numberWords.ts` — reads the words from the catalog of the active language.
- `web/lib/locale.ts`, `web/lib/format.ts` — `matchLocale`, `resolveLocale`, the format tag, `hydrateLocale`, `activateLocale`.
- `web/lib/language.tsx`, `app/capabilities/settings/web/SettingsPage.tsx`, `app/capabilities/writing/web/BookSettings.tsx` — the three surfaces map over `localeOrder`; endonyms from the generated table.
- `app/kernel/contracts/user.py`, `app/kernel/contracts/novel.py`, `app/capabilities/settings/schemas.py`, `app/capabilities/writing/metadata.py`, `app/kernel/interchange/format.py`, one Alembic revision — language columns and validation at 64 characters.
- `app/kernel/errors.py` — `ErrorCode`, `coded`, `coded_detail`.
- `web/lib/api/errors.ts` — `ApiError`, `codeOf`, `statusOf`, `isNetworkFailure`, `failureKey`, `CODE_KEY`, `useLocalizedError`.
- `web/lib/query.ts`, `web/lib/updates.ts` — every request failure throws `ApiError`; domain exceptions keep their own types.
- `web/routes/__root.tsx`, writing error faces and their callers, `NewBookDialog.tsx`, `providersSection.tsx`, `refusal.tsx` — translate at render; the update-check faces keep their localized copy and gain regression pins.
- `web/lib/catalog.ts` — the catalog store.
- `web/lib/i18n.ts` — `t()` reads the store.
- `web/lib/test/catalogs.ts`, `web/lib/test/setup.ts` — the test bed: real catalogs eagerly, the store preloaded.
- `web/globals.css`, `app/capabilities/writing/web/SceneEditor.tsx`, `EditorColumn.tsx`, `ZenMode.tsx` — `lang` on the prose and `:lang()` stacks.
- `docs/_shared/CONSTRAINTS.md`, `REVIEW.md`, `CONTRIBUTING.md` — rule 5 and its echoes.

---

## Task 0: Design and plan into the repository

**Precondition:** satisfied — the owner approved the design and this plan on 2026-11-26.

**Files:**
- Move: `~/.opencode/plan/2026-11-25-i18n-architecture-hardening-design.md` → `docs/superpowers/specs/2026-11-25-i18n-architecture-hardening-design.md`
- Move: `~/.opencode/plan/2026-11-25-i18n-architecture-hardening.md` → `docs/superpowers/plans/2026-11-25-i18n-architecture-hardening.md`
- Modify: `docs/superpowers/specs/2026-11-09-server-injected-i18n-design.md` (its `**Status:**` line)
- Modify: `docs/superpowers/plans/2026-11-09-server-injected-i18n-plan.md` (a note above everything else)
- Modify: `docs/superpowers/follow-ups.md` (one row)
- Create outside the repository: the wave's follow-up index issue
- Create, git-ignored: `.superpowers/sdd/i18n-hardening/baseline-assets.txt`

- [ ] **Step 1: Branch and workspace**

Fetch `narrare/main` and create `feat/i18n-hardening` from the current `main` through the `using-git-worktrees` skill. Begin not on a stale local `main`.

Expected: `git status --short` prints nothing; `git log -1 --format=%h` names the fetched tip.

- [ ] **Step 2: Record the bundle baseline**

On the fresh `feat/i18n-hardening` branch at `main`'s tip, run `just build`, then `mkdir -p .superpowers/sdd/i18n-hardening && ls -l web/dist/assets > .superpowers/sdd/i18n-hardening/baseline-assets.txt`.

Expected: the file lists the eager chunks; `git status --short` still prints nothing (`web/dist` and `.superpowers/` are ignored).

- [ ] **Step 3: Move both documents**

Move, never copy: one state, not two.

- [ ] **Step 4: Mark the superseded pair**

In the 2026-11-09 design, replace `**Status:** Proposed` with:
`**Status:** Superseded 2026-11-26 — never built; replaced by \`docs/superpowers/specs/2026-11-25-i18n-architecture-hardening-design.md\`, which loads catalogs as lazy modules instead of injecting them into the shell.`
As the first line of the 2026-11-09 plan, insert:
`> **Superseded 2026-11-26 (whole plan):** never started. See \`docs/superpowers/plans/2026-11-25-i18n-architecture-hardening.md\`.`

- [ ] **Step 5: Open the wave's follow-up index issue and add its row**

The coordinator runs:

```bash
gh issue create --label follow-up-index \
  --title "Localization hardening (2026-11-25) — index of follow-ups" \
  --body "The localization hardening wave's index of follow-up findings. One pull request (branch \`feat/i18n-hardening\`). Spec and plan per the follow-ups row. Open children: none at opening."
```

Expected: the issue's URL. The implementer then appends one row to the table in `docs/superpowers/follow-ups.md`, in the format of the rows above it: the first cell names the wave and its date, what it covers, the spec and plan paths and "One PR. Opened with Task 0"; the second cell names the issue number as open with no children at opening.

- [ ] **Step 6: Review and commit**

A reviewer checks that the plan contradicts no standing rule, that the superseded pair says so, and that the row names the issue number. Then:

```bash
git add docs/superpowers/specs/2026-11-25-i18n-architecture-hardening-design.md \
  docs/superpowers/plans/2026-11-25-i18n-architecture-hardening.md \
  docs/superpowers/specs/2026-11-09-server-injected-i18n-design.md \
  docs/superpowers/plans/2026-11-09-server-injected-i18n-plan.md docs/superpowers/follow-ups.md
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "chore(docs): record the localization hardening design and plan"
```

- [ ] **Step 7: Push and open the pull request**

Title, a plain sentence and not a commit subject: "Languages come from a registry, failures speak the reader's language, catalogs load on demand". Body per `.github/PULL_REQUEST_TEMPLATE.md`; under Boundaries, tick the last box with "the registry is approved: design §7".

---

## Task 1: The ordered registry

**Files:**
- Create: `i18n/registry/locales.json`
- Modify: `scripts/generate_capabilities.py` (module docstring, `locales`, new `registry_locales`, `typescript_catalogs`, the comment above `SOURCE_LOCALE`)
- Regenerate: `app/generated/locales.py`, `web/lib/generated/catalogs.ts`
- Test: `app/api/test_catalog_merge.py`, `app/api/test_capability_views.py`, `scripts/tests/test_generate_help.py`
- Modify: `CONTRIBUTING.md` (the i18n section)

**Interfaces:**
- Registry file: `{ "locales": ["de", "en", "fr"] }` — the set of languages in display order; the source language must be a member.
- Produces Python: `registry_locales(root: Path) -> tuple[str, ...]` — the registry order; refuses a malformed file or code, a duplicate, a registry without the source locale, a registry entry without `i18n/<code>.json` and a central catalog the registry does not list, each by name. `locales(root: Path) -> tuple[str, ...]` — unchanged shape: the source language first, the rest in registry order.
- Produces generator: `typescript_catalogs(root: Path, known: tuple[str, ...], order: tuple[str, ...] | None = None) -> str`; `order` defaults to `known`.
- Produces TypeScript: `export const localeOrder: readonly Locale[]` in `web/lib/generated/catalogs.ts`, written as `["de", "en", "fr"] as const satisfies readonly Locale[]`.

- [ ] **Step 1: Write the failing tests**

In `app/api/test_catalog_merge.py`, beside `write_catalog`:

```python
def write_registry(path: Path, languages: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"locales": languages}) + "\n", encoding="utf-8")


def test_the_registry_orders_the_languages_and_the_source_leads_the_views(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "en", "fr"])
    for code in ("de", "en", "fr"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})

    assert registry_locales(tmp_path) == ("de", "en", "fr")
    assert locales(tmp_path) == ("en", "de", "fr")
    typescript = typescript_catalogs(tmp_path, ("en", "de", "fr"), ("de", "en", "fr"))
    assert 'export const locales = ["en", "de", "fr"] as const;' in typescript
    assert 'export const localeOrder = ["de", "en", "fr"] as const' in typescript


@pytest.mark.parametrize("code", ["en_US", "x", "de-", "zh hans", f"de-{'a' * 9}", "de-" + "-".join(["abcdefgh"] * 8)])
def test_a_malformed_registry_code_stops_generation(tmp_path: Path, code: str) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["en", code])
    # Both catalogs exist so parity cannot raise: only the tag check can.
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "en"})
    write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})
    with pytest.raises(SystemExit, match=re.escape(code[:10])):
        locales(tmp_path)


def test_a_registry_without_the_source_locale_stops_generation(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "fr"])
    with pytest.raises(SystemExit, match="source locale"):
        locales(tmp_path)


def test_a_duplicate_registry_entry_stops_generation(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "en", "de"])
    with pytest.raises(SystemExit, match="twice"):
        locales(tmp_path)


def test_a_registry_entry_without_a_catalog_stops_generation(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "en", "fr"])
    for code in ("de", "en"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})
    with pytest.raises(SystemExit, match="i18n/fr.json"):
        locales(tmp_path)


def test_a_catalog_outside_the_registry_stops_generation(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "en"])
    for code in ("de", "en", "fr"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})
    with pytest.raises(SystemExit, match="i18n/fr.json"):
        locales(tmp_path)
```

In `app/api/test_capability_views.py`, extend `test_committed_typescript_catalogs_match_the_catalog_files` with an assertion against its own `_committed("web", "lib", "generated", "catalogs.ts")` string that `export const localeOrder = [` is present. Do not invent a `committed_typescript_catalogs` variable in the locale-list test.

- [ ] **Step 2: Run the tests red**

Run: `just test-file app/api/test_catalog_merge.py`
Expected: FAIL — `ImportError`/`AttributeError` for `registry_locales`; `typescript_catalogs` output has no `localeOrder`.

- [ ] **Step 3: Implement**

In `scripts/generate_capabilities.py`:

- `_LOCALE_TAG = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{1,8})*")` and `LOCALE_MAX_LENGTH = 64`; `REGISTRY = "i18n/registry/locales.json"`.
- `registry_locales(root)`: read `REGISTRY`; refuse a file that is not an object with one `locales` list of strings, a code that does not `fullmatch` `_LOCALE_TAG` or exceeds `LOCALE_MAX_LENGTH`, a code listed twice, a list without `SOURCE_LOCALE`; then list `root / "i18n"/*.json` stems and refuse both directions of parity. Messages name the file and the offender.
- `locales(root)`: `(SOURCE_LOCALE, *(code for code in registry_locales(root) if code != SOURCE_LOCALE))` — the glob goes.
- `typescript_catalogs(root, known, order=None)`: write `export const localeOrder = [...] as const satisfies readonly Locale[];` directly below the `locales` line.
- `main()` passes `order=registry_locales(root)`; the module docstring names the registry as the set and the order of languages; the comment above `SOURCE_LOCALE` says the source leads the views while the registry orders the switcher.
- Write `i18n/registry/locales.json`.

- [ ] **Step 4: Regenerate**

Run: `just generate`
Expected: `web/lib/generated/catalogs.ts` gains the `localeOrder` line; `app/generated/locales.py` changes only in its docstring.

- [ ] **Step 5: Run the tests green and prove parity**

Run: `just test-file app/api/test_catalog_merge.py`, `just test-file app/api/test_capability_views.py`, `CI=true just check-generated`, `CI=true pnpm --dir web exec vitest run lib/language.test.tsx`.
Expected: PASS. The switcher's existing pin "draws the design's order with endonym names and one tab stop" stays green because the registry order is `de, en, fr`.

- [ ] **Step 6: Update the contributor documentation**

In `CONTRIBUTING.md`'s i18n section: replace the paragraph "Never hardcode a locale list" with — the languages and their display order come from `i18n/registry/locales.json`; the generator refuses a registry entry without a catalog and a catalog without an entry, and writes the list into the generated views on the next `just generate`. Replace "Adding a language means one central catalog plus one file per capability that owns keys" with — one line in `i18n/registry/locales.json`, one central catalog and one file per capability that owns keys, then `just generate`.

- [ ] **Step 7: Task gate, review and commit**

Task gate: `just check`, `CI=true just check-generated`. Reviewer: the registry is the only list; `catalogs()` and its parity tests are untouched; no view changed its shape besides the added line. Commit: `refactor(i18n): read the languages and their order from a registry`, body: a language added as a file alone no longer appears in an order nobody chose, and a file dropped into `i18n/` no longer becomes a language.

---

## Task 2: The plural rule

**Files:**
- Create: `web/lib/catalogRules.test.ts`
- Modify: `docs/_shared/CONSTRAINTS.md` (rule 5), `REVIEW.md` (the `i18n/` bullet), `CONTRIBUTING.md` (the plural bullet)

No production code changes.

**Interfaces:**
- Produces (test-only): `requiredCategories(locale: string, type: Intl.PluralRulesOptions["type"]): string[]` — every category `Intl.PluralRules` reports, minus `many` when the complete set is exactly `one/many/other`.
- Produces (test-only): `missingCategories(locale: string, key: string, message: string): string[]` — each skipped category as `locale:key:category`; walks the message's plural and ordinal elements, nested ones included, through `new IntlMessageFormat(message, locale).getAst()` — the locale reaches parsing only for datetime skeletons, and `requiredCategories` constructs `Intl.PluralRules` on the same argument.

- [ ] **Step 1: Write the failing tests**

`web/lib/catalogRules.test.ts` imports `IntlMessageFormat` from `intl-messageformat`, `locales` from `./generated/catalogs`, and `merged` from `./test/catalogs` once Task 10 builds the bed.

```ts
it("names each category a message skips", () => {
  expect(missingCategories("ru", "count", "{n, plural, one {# роман} other {# романов}}")).toEqual([
    "ru:count:few",
    "ru:count:many",
  ]);
});

it("does not require a lone many", () => {
  expect(missingCategories("fr", "count", "{n, plural, one {# roman} other {# romans}}")).toEqual([]);
  expect(missingCategories("es", "count", "{n, plural, one {# libro} other {# libros}}")).toEqual([]);
});

it("asks a language without categories for other only", () => {
  expect(missingCategories("ja", "count", "{n, plural, other {# 冊}}")).toEqual([]);
});

it("applies the rule to ordinal messages with the ordinal categories", () => {
  // The report is sorted: the engine's category order differs between Node versions, and the rule names a set.
  expect(missingCategories("en", "rank", "{n, selectordinal, one {st} other {th}}")).toEqual([
    "en:rank:few",
    "en:rank:two",
  ]);
});

it("finds a plural nested in another branch", () => {
  const message = "{n, plural, one {{m, plural, one {# book} other {# books}}} other {#}}";
  expect(missingCategories("ru", "shelf", message)).toContain("ru:shelf:few");
});

it("lets the parser refuse a message without other", () => {
  expect(() => missingCategories("de", "k", "{n, plural, one {#}}")).toThrow();
});

it("knows every language and writes it in canonical case", () => {
  for (const code of locales) {
    expect(Intl.getCanonicalLocales(code)).toEqual([code]);
    const resolved = new Intl.Locale(new Intl.NumberFormat(code).resolvedOptions().locale);
    const wanted = new Intl.Locale(code);
    expect(resolved.language).toBe(wanted.language);
    expect(resolved.script).toBe(wanted.script);
  }
});

it("writes every plural message in every catalog with the categories its language requires", () => {
  const visited = new Set<string>();
  const missing = locales.flatMap((code) =>
    Object.entries(merged[code]).flatMap(([key, message]) => {
      const walked = walkMessage(code, key, message);
      if (walked.plurals > 0) visited.add(code);
      return walked.missing;
    }),
  );
  expect(missing).toEqual([]);
  // What the walk covered: an empty walk cannot pass as clean.
  expect([...visited].sort()).toEqual([...locales].sort());
});
```

- [ ] **Step 2: Run the tests red**

Run: `CI=true pnpm --dir web exec vitest run lib/catalogRules.test.ts`
Expected: FAIL — `missingCategories` is not defined. With the two functions present as empty stubs, four fixture tests fail on their assertions; the two expecting `[]` pass vacuously.

- [ ] **Step 3: Implement the two test helpers**

`requiredCategories` as the interface says. `walkMessage` narrows an element to a plural by `"pluralType" in element`, recurses into every option's `value` and into `value` arrays, counts the plural elements it walked, and collects the categories of `element.pluralType` that are absent from `element.options`; `missingCategories` returns its sorted `missing` list.

- [ ] **Step 4: Run the tests green**

Run: `CI=true pnpm --dir web exec vitest run lib/catalogRules.test.ts`
Expected: PASS — all 49 plural messages of each language satisfy the rule today.

- [ ] **Step 5: Write the rule down**

In `docs/_shared/CONSTRAINTS.md`, rule 5 reads after the change:

> 5. **English in code, tests and developer documentation; user-visible text in every catalog
> the app carries** through `i18n/<code>.json` for shared text and
> `app/capabilities/<id>/web/i18n/<code>.json` for capability text. The languages and their
> display order come from `i18n/registry/locales.json`, never from a list in code. Every catalog
> is sorted, carries the same keys, and writes every plural category its language has — except
> a lone `many` where the language's set is exactly `one/many/other`; `other` remains the
> runtime fallback. A missing key is a build error.

In `REVIEW.md`, the `i18n/` bullet ends: "…, a language outside `i18n/registry/locales.json`, or a plural message that skips a category its language requires (a lone `many` excepted)." In `CONTRIBUTING.md`, the plural bullet says: write a branch for every category `Intl.PluralRules("<code>")` reports, the one exception being a lone `many`; `web/lib/catalogRules.test.ts` refuses a message that skips a required category and names language, key and category.

- [ ] **Step 6: Task gate, review and commit**

Task gate: `just check`, `CI=true just test-frontend`. Reviewer: the rule text in the three documents says the same thing. Commit: `test(i18n): refuse a plural message that skips a required category`, body: a language with more categories than English can no longer be written as `one/other` without a red test naming the message.

---

## Task 3: Number words are catalog keys

**Files:**
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`
- Modify: `web/lib/numberWords.ts`, `web/lib/numberWords.test.ts`, `app/capabilities/writing/web/EditorColumn.tsx`
- Regenerate: `web/lib/generated/catalogs.ts`

**Interfaces:**
- Produces keys: `numberWords.01` … `numberWords.20` in the central catalog of every language, with today's words: English `one` … `twenty`; German `eins, zwei, drei, vier, fünf, sechs, sieben, acht, neun, zehn, elf, zwölf, dreizehn, vierzehn, fünfzehn, sechzehn, siebzehn, achtzehn, neunzehn, zwanzig`; French `un, deux, trois, quatre, cinq, six, sept, huit, neuf, dix, onze, douze, treize, quatorze, quinze, seize, dix-sept, dix-huit, dix-neuf, vingt`.
- Produces: `numberWord(value: number): string` and `capitalizedWord(value: number): string` — the word comes from the catalog of the active language through `t()`; the digit stands beyond `NUMBER_WORD_BOUND` (20) and for anything that is not a positive integer. The `locale` parameter goes: a language that is not active has no loaded catalog.

- [ ] **Step 1: Write the failing tests**

`web/lib/numberWords.test.ts` is rewritten around the active language:

```ts
it("writes one to twenty in the active language", () => {
  applyLocale("de");
  expect([numberWord(1), numberWord(7), numberWord(11), numberWord(20)]).toEqual(["eins", "sieben", "elf", "zwanzig"]);
  applyLocale("fr");
  expect(numberWord(17)).toBe("dix-sept");
  applyLocale("en");
  expect(numberWord(11)).toBe("eleven");
});

it("falls back to the digit beyond twenty and for anything that is not a positive integer", () => {
  expect([numberWord(0), numberWord(21), numberWord(2.5), numberWord(-3)]).toEqual(["0", "21", "2.5", "-3"]);
});

it("capitalizes the first letter only", () => {
  applyLocale("de");
  expect(capitalizedWord(1)).toBe("Eins");
  applyLocale("fr");
  expect(capitalizedWord(17)).toBe("Dix-sept");
});
```

- [ ] **Step 2: Run the tests red**

Run: `CI=true pnpm --dir web exec vitest run lib/numberWords.test.ts`
Expected: FAIL — `numberWord` wants two arguments and the catalog keys do not exist.

- [ ] **Step 3: Implement**

Add the twenty keys to each central catalog in sorted position. `web/lib/numberWords.ts` keeps `NUMBER_WORD_BOUND`, holds `WORD_KEYS = ["numberWords.01", …, "numberWords.20"] as const satisfies readonly MessageKey[]` and reads `t(WORD_KEYS[value - 1])`. In `EditorColumn.tsx`, the eyebrow's two calls drop their `locale` argument, and whatever became unused goes.

- [ ] **Step 4: Regenerate and run green**

Run: `just generate`, `CI=true pnpm --dir web exec vitest run lib/numberWords.test.ts app/capabilities/writing/web/EditorColumn.test.tsx`, `CI=true just check-generated`.
Expected: PASS; the editor's running head still reads "Kapitel Eins · Szene Zwei".

- [ ] **Step 5: Task gate, review and commit**

Task gate: `just check`, `CI=true just test-frontend`, `just test-e2e writing`. Reviewer: no number word is left in TypeScript. Commit: `refactor(i18n): write number words from the catalogs`, body: the words for one to twenty are catalog text now, so a new language writes them where it writes everything else.

---

## Task 4: The registry's order on the surfaces, and tag resolution

**Files:**
- Modify: `web/lib/locale.ts`, `web/lib/format.ts`, `web/lib/language.tsx`, `app/capabilities/settings/web/SettingsPage.tsx`, `app/capabilities/writing/web/BookSettings.tsx`
- Test: `web/lib/locale.test.ts` (new), `web/lib/locale.script.test.ts` (new), `web/lib/language.registry.test.tsx` (new), `web/lib/format.test.ts`, `app/capabilities/writing/web/BookSettings.test.tsx`
- E2E: `app/capabilities/settings/e2e/test_settings_e2e.py`

**Interfaces:**
- Consumes: `localeOrder`, `locales`, `Locale` from `web/lib/generated/catalogs`.
- Produces: `type ResolvedLocale = Readonly<{ catalog: Locale; formatLocale: string }>`.
- Produces: `matchLocale(tag: string | null | undefined): Locale | null` — the registry language a tag maps onto, or null. Order: the exact code (case-insensitive); then the same language and the same script; then, only when the tag names no script, the same language, a registry code without a script before one with. A tag that names a script no registry code of that language has matches nothing. Ill-formed and empty tags match nothing. Never throws.
- Produces: `resolveLocale(tag: string | null | undefined): ResolvedLocale` — the matched catalog with the canonical tag as `formatLocale` (a region is kept: `de-AT` reads `de`, formats `de-AT`); a tag that matches nothing gives `{ catalog: "en", formatLocale: "en" }`. Never throws, never rejects.
- Produces: `activeFormatLocale(): string` in `web/lib/locale.ts`; `formattingLocale()` in `web/lib/format.ts` keeps its name and reads it.
- Unchanged signatures: `activeLocale`, `chosenLocale`, `subscribeLocale`, `adoptServerLocale(locale: string | null)`, `applyLocale(locale: Locale | null)`. `adoptServerLocale` keeps exact membership: an unknown stored code is ignored, because the Settings API is what refuses it.

- [ ] **Step 1: Write the failing tests**

`web/lib/locale.test.ts` (real registry; `vi.stubGlobal("navigator", …)` as `web/lib/i18n.test.ts` does):

```ts
it("maps a regional tag onto its language and keeps the region for formatting", () => {
  expect(resolveLocale("de-AT")).toEqual({ catalog: "de", formatLocale: "de-AT" });
});

it("resolves an exact code to itself", () => {
  expect(resolveLocale("fr")).toEqual({ catalog: "fr", formatLocale: "fr" });
});

it.each(["tlh", "tlh-AA", "", "not a tag!", null, undefined])("resolves %s to the source language without throwing", (tag) => {
  expect(matchLocale(tag)).toBeNull();
  expect(resolveLocale(tag)).toEqual({ catalog: "en", formatLocale: "en" });
});

it("matches a known language whose region is unknown", () => {
  expect(matchLocale("fr-CA")).toBe("fr");
});

it("formats a chosen language with the browser's region when the browser speaks it", () => {
  vi.stubGlobal("navigator", { languages: ["de-AT", "de"], language: "de-AT" });
  applyLocale("de");
  expect(activeLocale()).toBe("de");
  expect(formattingLocale()).toBe("de-AT");
  applyLocale("fr");
  expect(formattingLocale()).toBe("fr");
});

it("keeps the browser's own tag when nobody chose", () => {
  vi.stubGlobal("navigator", { languages: ["de-AT"], language: "de-AT" });
  applyLocale(null);
  expect(formattingLocale()).toBe("de-AT");
});
```

`web/lib/locale.script.test.ts` mocks `./generated/catalogs` and follows the Global Constraints' rule for mocking the bed:

```ts
vi.mock("./generated/catalogs", async (importOriginal) => {
  const real = await importOriginal<typeof import("./generated/catalogs")>();
  return {
    ...real,
    locales: ["en", "zh-Hans"],
    localeOrder: ["zh-Hans", "en"],
    catalogs: { en: real.catalogs.en, "zh-Hans": { ...real.catalogs.en, "locale.name": "中文（简体）" } },
  };
});

beforeEach(() => vi.resetModules());

it("matches a longer tag onto the same language and script", async () => {
  const { matchLocale, resolveLocale } = await import("./locale");
  expect(matchLocale("zh-Hans-CN")).toBe("zh-Hans");
  expect(resolveLocale("zh-Hans-CN")).toEqual({ catalog: "zh-Hans", formatLocale: "zh-Hans-CN" });
});

it("matches the exact code", async () => {
  const { matchLocale } = await import("./locale");
  expect(matchLocale("zh-Hans")).toBe("zh-Hans");
});

it("does not match a script the registry does not carry", async () => {
  const { matchLocale, resolveLocale } = await import("./locale");
  expect(matchLocale("zh-Hant")).toBeNull();
  expect(resolveLocale("zh-Hant")).toEqual({ catalog: "en", formatLocale: "en" });
});
```

`web/lib/language.registry.test.tsx` adds `"pt-BR"` in the same manner and reads the component dynamically:

```ts
vi.mock("./generated/catalogs", async (importOriginal) => {
  const real = await importOriginal<typeof import("./generated/catalogs")>();
  return {
    ...real,
    locales: [...real.locales, "pt-BR"],
    localeOrder: [...real.localeOrder, "pt-BR"],
    catalogs: { ...real.catalogs, "pt-BR": { ...real.catalogs.en, "locale.name": "Português (Brasil)" } },
  };
});

beforeEach(() => vi.resetModules());

it("shows a language the registry adds, in the registry's order, without a code change", async () => {
  const { applyLocale } = await import("./locale");
  const { LanguageSwitcher } = await import("./language");
  applyLocale("de");
  render(<LanguageSwitcher variant="welcome" preSetup />);
  const radios = within(screen.getByRole("radiogroup")).getAllByRole("radio");
  expect(radios.map((radio) => radio.textContent)).toEqual(["DE", "EN", "FR", "PT-BR"]);
  expect(radios.map((radio) => radio.getAttribute("aria-label"))).toEqual([
    "Deutsch", "English", "Français", "Português (Brasil)",
  ]);
});
```

`app/capabilities/writing/web/BookSettings.test.tsx` gains: "the manuscript segment offers the registry's languages in its order" — the segment's options read `["DE", "EN", "FR"]`.

In `app/capabilities/settings/e2e/test_settings_e2e.py`:

```python
def test_the_language_cards_follow_the_registry_order(page: Page, installed: Stack) -> None:
    goto_settings(page)
    expect(page.get_by_role("heading", name=HEADING_DE)).to_be_visible()

    cards = page.get_by_role("radiogroup", name=LANGUAGE_LABEL_DE).get_by_role("radio")
    expect(cards).to_have_count(3)
    assert [card.get_attribute("aria-label") for card in cards.all()] == ["Deutsch", "English", "Français"]
```

`LANGUAGE_LABEL_DE` is the German label of the language section, copied literally from the settings capability's `de` catalog.

- [ ] **Step 2: Run the tests red**

Run: `CI=true pnpm --dir web exec vitest run lib/locale.test.ts lib/locale.script.test.ts lib/language.registry.test.tsx app/capabilities/writing/web/BookSettings.test.tsx`; `just test-e2e-file app/capabilities/settings/e2e/test_settings_e2e.py -k registry_order`.
Expected: FAIL — `matchLocale`, `resolveLocale` and `activeFormatLocale` do not exist; the `pt-BR` radio does not render. The settings E2E leg is a pin that is green before and after the change; its first run is read all the same.

- [ ] **Step 3: Implement resolution**

`web/lib/locale.ts`: canonicalize a tag with `Intl.getCanonicalLocales` inside `try`/`catch` and read `language` and `script` through `Intl.Locale`; implement `matchLocale` by the interface's order; `resolveLocale` as the interface says. The module keeps a format tag beside the active locale: `fromBrowser()` returns the first browser tag that matches, as a `ResolvedLocale`; a choice (`chosen`) formats with the first browser tag that maps onto it, else with its own code; `announce` stores both. `formattingLocale()` returns the stored tag instead of reading `navigator.language`.

- [ ] **Step 4: Point the three surfaces at the registry**

Delete `SWITCHER_ORDER`, `LANGUAGE_CARDS` and `LANGUAGES`; map over `localeOrder` in `LanguageSwitcher`, the settings cards and the manuscript segment.

- [ ] **Step 5: Run the tests green**

Run: the Step 2 commands; `CI=true pnpm --dir web exec vitest run lib/i18n.test.ts lib/format.test.ts lib/language.test.tsx app/capabilities/settings/web/SettingsPage.test.tsx`; `just test-e2e-file app/capabilities/settings/e2e/test_settings_e2e.py -k language_cards`.
Expected: PASS. The pins in `web/lib/i18n.test.ts` ("ignores a code the catalog does not carry", "follows the browser when nobody chose", "falls back to the source catalog when the browser speaks none of them") stay green unchanged.

- [ ] **Step 6: Prove no list is left**

Run: `rg -n "SWITCHER_ORDER|LANGUAGE_CARDS|\bLANGUAGES\b" web app --glob '!*.test.*'`
Expected: no output.

- [ ] **Step 7: Task gate, review and commit**

Task gate: `just check`, `CI=true just test-frontend`, `just test-e2e settings`, `just test-e2e writing`. Commit: `refactor(i18n): order the languages by the registry and resolve regional tags`, body: the order of the languages is the registry's, and a browser tag such as `de-AT` or `zh-Hans-CN` finds its catalog without a fallback to the machine's locale.

---

## Task 5: Both language columns at 64 characters

**Files:**
- Modify: `app/kernel/contracts/user.py`, `app/kernel/contracts/novel.py`, `app/capabilities/settings/schemas.py`, `app/capabilities/writing/metadata.py`, `app/kernel/interchange/format.py`
- Create: `app/kernel/db/migrations/versions/<revision>_widen_the_language_columns.py` via `just db-revision "widen the language columns"`
- Regenerate: `web/lib/api/openapi.json`, `web/lib/api/schema.d.ts` (`just generate`)
- Test: `app/kernel/db/tests/test_migrations.py`, `app/capabilities/settings/tests/test_settings.py`, `app/capabilities/writing/tests/test_metadata.py`, `app/capabilities/writing/tests/test_novel_management.py`, `app/kernel/tests/test_interchange_format.py`

**Interfaces:**
- `User.locale` and `Novel.language` are `String(64)`.
- `SettingsUpdate.locale: str | None = Field(max_length=64)`; the membership validator is unchanged.
- `LANGUAGE_TAG = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{1,8})*")` and `LANGUAGE_MAX_LENGTH = 64` in `app/capabilities/writing/metadata.py`; `_normalize_language` keeps folding the primary subtag to lowercase and refuses anything else by field name, as today.
- `_MAX_LENGTHS["language"] == 64` in `app/kernel/interchange/format.py`.
- Decided: a novel's language is not checked against the registry. Every registry code is a valid tag; the API's set is a superset of the registry's, so an archive in a language the app does not speak still imports.

- [ ] **Step 1: Write the failing tests**

`app/kernel/db/tests/test_migrations.py`, beside the provider-step replay and in its pattern (`WIDENING_STEP_PREDECESSOR = "12fc7ddcec6f"`, staged with `command.upgrade` to the predecessor, raw inserts, then upgrade to head):

```python
async def test_the_language_widening_keeps_every_stored_tag(url: str) -> None:
    # staged: one user with locale 'de', one with NULL; one novel with language 'en-GB', one with NULL
    ...
    assert user_locales == ["de", None]
    assert novel_languages == ["en-GB", None]
    assert column_width(url, "users", "locale") == 64
    assert column_width(url, "novels", "language") == 64
```

`column_width(url, table, column)` is a small helper over `information_schema.columns` in the same file.

`app/capabilities/writing/tests/test_metadata.py`:

```python
@pytest.mark.parametrize(("given", "expected"), [
    ("DE", "de"), ("en-GB", "en-GB"), ("  de  ", "de"), ("   ", None),
    ("zh-Hans-CN", "zh-Hans-CN"), ("de-CH-1906", "de-CH-1906"), ("hy-Latn-IT-arevela", "hy-Latn-IT-arevela"), ("yue", "yue"),
])
def test_language_folds_only_its_primary_subtag(given: str, expected: str | None) -> None: ...

def test_an_invalid_language_is_refused_by_name() -> None:
    for value in ("deutsch", "d", "de_DE", "x" * 17, "de-" + "-".join(["abcdefgh"] * 8)): ...
```

`app/capabilities/writing/tests/test_novel_management.py`: `test_patch_refuses_an_over_long_language` sends a 65-character tag of valid subtags; new:

```python
@pytest.mark.parametrize("code", ["zh-Hans-CN", "de-CH-1906", "hy-Latn-IT-arevela", "yue"])
async def test_patch_accepts_every_well_formed_tag(code: str) -> None: ...   # 200, and GET answers the same tag

@pytest.mark.parametrize("code", LOCALES)
async def test_every_registered_locale_is_a_valid_novel_language(code: str) -> None: ...
```

`app/capabilities/settings/tests/test_settings.py` (with `from app.capabilities.settings import schemas as settings_schemas`; `LOCALES` in the writing tests is `app.generated.locales.LOCALES`):

```python
async def test_a_long_registered_locale_is_stored(monkeypatch) -> None:
    monkeypatch.setattr(settings_schemas, "LOCALES", ("de", "en", "fr", "zh-Hans-CN"))
    ...  # PATCH {"locale": "zh-Hans-CN"} → 200; GET answers it

async def test_an_over_long_locale_is_refused() -> None: ...  # 65 characters → 422; the stored locale is unchanged
```

`app/kernel/tests/test_interchange_format.py`: `test_a_language_tag_wider_than_the_column_is_refused_by_name` (65 characters → `ArchiveError` whose reason names `64`) and `test_a_long_language_tag_round_trips` (`hy-Latn-IT-arevela`).

- [ ] **Step 2: Run the tests red**

Run: `just test-file app/kernel/db/tests/test_migrations.py`, `just test-file app/capabilities/writing/tests/test_metadata.py`, `just test-file app/capabilities/writing/tests/test_novel_management.py`, `just test-file app/capabilities/settings/tests/test_settings.py`, `just test-file app/kernel/tests/test_interchange_format.py`.
Expected: FAIL — the migration test finds no width 64; `zh-Hans-CN` and its fellows are refused; 64 characters exceed the columns.

- [ ] **Step 3: Change the models, then the revision**

Change both columns to `String(64)` and run `just test-file app/kernel/db/tests/test_migrations.py`: `test_empty_database_migrated_equals_the_models` goes red — the model and the revision are one commit. Then `uv run alembic heads` (expected: one head, `12fc7ddcec6f` at this plan's baseline), `just db-revision "widen the language columns"`, and edit the revision to exactly:

```python
def upgrade() -> None:
    op.alter_column("users", "locale", existing_type=sa.String(8), type_=sa.String(64), existing_nullable=True)
    op.alter_column("novels", "language", existing_type=sa.String(16), type_=sa.String(64), existing_nullable=True)


def downgrade() -> None:
    raise RuntimeError("downgrade is not supported; restore the pre-migration dump (design D6, ADR-103)")
```

- [ ] **Step 4: Align the validators**

`SettingsUpdate.locale` gets `Field(max_length=64)`. `_normalize_language` uses `LANGUAGE_TAG.fullmatch` and `LANGUAGE_MAX_LENGTH`. `_MAX_LENGTHS["language"]` is 64, its comment reading the new column width.

- [ ] **Step 5: Regenerate and run green**

Run: `just generate`; the Step 2 commands; `just test`.
Expected: PASS. `web/lib/api/openapi.json` shows `maxLength: 64` on the settings update's locale; the pinned `openapi-typescript@7.13.0` emits no `maxLength`, so `schema.d.ts` stays byte-identical.

- [ ] **Step 6: Task gate, review and commit**

Task gate: `just check`, `CI=true just check-generated`, `just test-e2e settings`, `just test-e2e writing`. Commit: `refactor(db): widen the language columns to the registry's width`, body states why the schema changed (REVIEW.md asks for it): a registry code may be up to 64 characters, and a novel's language is any well-formed tag of that width, so both columns hold what the validators accept.

---

## Task 6: The typed error codes

**Files:**
- Modify: `app/kernel/errors.py`, `app/kernel/llm/contract.py`, `app/kernel/llm/streaming.py`, `app/capabilities/chat/interviews.py`, `app/capabilities/chat/router.py`, `app/capabilities/knowledge/router.py`, `app/capabilities/prompts/router.py`, `app/capabilities/writing/router.py`
- Modify: `scripts/generate_capabilities.py` (new `typescript_error_codes`, the view count in its docstring)
- Create: `web/lib/generated/errorCodes.ts` (generated), `app/kernel/tests/test_error_codes.py`
- Test: `app/api/test_capability_views.py`, `app/kernel/tests/test_llm_streaming.py`

**Interfaces:**
- Produces: `class ErrorCode(StrEnum)` in `app/kernel/errors.py` with the 24 members of design §10, named in upper snake case (`ARCHIVE_INVALID = "archive_invalid"`, …).
- Produces: `coded(code: ErrorCode, **facts: object) -> dict[str, object]` — `{"code": code, **facts}`; `coded_detail(code: ErrorCode, detail: str = "", *, row: int | None = None, field: str | None = None)`.
- Produces: `error_code(failure: BaseException) -> ErrorCode`; `error_frame(code: ErrorCode, **params: str) -> str`; `error_events(code: ErrorCode = ErrorCode.UNKNOWN, **params: str)`; the interview refusals' `code: ErrorCode`, `InterviewValidationError(code: ErrorCode, detail: str)`. The three `ERROR_*` constants in `contract.py` go; nothing outside that file reads them.
- Produces TypeScript (generated): `ERROR_CODES`, `type ErrorCode`, `isErrorCode(value: unknown): value is ErrorCode` in `web/lib/generated/errorCodes.ts`.

- [ ] **Step 1: Write the failing tests**

`app/kernel/tests/test_error_codes.py`:

```python
def test_a_code_serializes_as_its_string() -> None:
    assert json.dumps(coded(ErrorCode.ORDER_MISMATCH, chapter_ids=["a"])) == '{"code": "order_mismatch", "chapter_ids": ["a"]}'

def test_the_stream_error_frame_carries_the_code() -> None:
    assert error_frame(ErrorCode.KEY_UNAVAILABLE) == 'event: error\ndata: {"code": "key-unavailable"}\n\n'

def test_the_three_stream_failures_map_to_their_codes() -> None:
    assert error_code(ModelNotFoundError("m")) is ErrorCode.MODEL_NOT_FOUND
    assert error_code(ProviderAuthError()) is ErrorCode.PROVIDER_AUTH
    assert error_code(RuntimeError("x")) is ErrorCode.UNKNOWN
```

The two typed failures are constructed as the contract's own tests construct them.

In `app/api/test_capability_views.py`, beside the other committed-view tests: `test_committed_typescript_error_codes_match_the_kernel` — the committed `web/lib/generated/errorCodes.ts` equals `typescript_error_codes()` byte for byte.

- [ ] **Step 2: Run the tests red**

Run: `just test-file app/kernel/tests/test_error_codes.py`, `just test-file app/api/test_capability_views.py`.
Expected: FAIL — `ErrorCode` does not exist; `errorCodes.ts` does not exist.

- [ ] **Step 3: Implement**

`ErrorCode` with the 24 members. `coded_detail`'s first parameter is `ErrorCode`. `coded` serves the seven inline `{"code": …}` refusal dicts in the chat, knowledge and writing routers, in the same key order so the wire bytes do not change. `contract.py` imports `ErrorCode` and returns members; the constants go. `streaming.py` types its two functions. The interview refusals annotate `code: ErrorCode` without a default; `InterviewValidationError` types its parameter.

- [ ] **Step 4: Generate the view**

`typescript_error_codes()` writes `ERROR_CODES = [...] as const` in declaration order, `export type ErrorCode = (typeof ERROR_CODES)[number];` and `isErrorCode`. `main()` adds `"web/lib/generated/errorCodes.ts"` to its outputs. Run `just generate`.
Expected: the file exists; `just check-generated` finds nothing stale afterwards.

- [ ] **Step 5: Run the tests green, and let the compiler vouch**

Run: `just test-file app/kernel/tests/test_error_codes.py`, `just test-file app/kernel/tests/test_llm_streaming.py`, `just test-file app/capabilities/chat/tests`, `just test-file app/api/test_capability_views.py`; `just typecheck`.
Expected: PASS. `just typecheck` is the enforcement: a refusal whose code is not a member does not pass it.

- [ ] **Step 6: Task gate, review and commit**

Task gate: `just check`, `just test`, `CI=true just check-generated`. Reviewer: the wire did not change — `app/kernel/tests/test_llm_streaming.py` pins the frame bytes and stays green. Commit: `refactor(kernel): type the error codes the wire carries`, body: a code the backend emits is a member of one list the compiler checks and the generator writes to TypeScript, so a code without a catalog sentence can no longer appear unnoticed.

---

## Task 7: One failure shape and the exhaustive mapping

**Files:**
- Create: `web/lib/api/errors.ts`, `web/lib/api/errors.test.ts`
- Modify: `web/lib/query.ts` (every request-failure `throw`, `WireError`, `createEntityFailure`, `assistantFailure`), `web/lib/query.test.ts`, and every importer of `WireError` from `web/lib/query.ts`
- Modify: `web/lib/updates.ts`, `web/lib/updates.test.ts`
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`
- Regenerate: `web/lib/generated/catalogs.ts`

**Interfaces:**
- Produces: `class ApiError extends Error` — `status: number | null`, `code: ErrorCode | null`, `detail: unknown`; `new ApiError(what: string, init: { status?: number | null; code?: unknown; detail?: unknown; extra?: Record<string, unknown> } = {})`. The message keeps today's console form: `` `${what}: ${status}` ``, or `` `${what}: transport` `` without a status. A `code` that is not an `ErrorCode` is stored as `null`. A request that threw before there was a response is wrapped in `class TransportError extends ApiError`, with `status` and `code` `null` and `cause` set to what the request threw.
- Produces: `wireCode(body: unknown): ErrorCode | null` — the code of `{"detail": {"code"}}` or of a bare `{"code"}`; `codeOf(error: unknown): ErrorCode | null` — an `ApiError`'s own code, else `wireCode` of its `detail`, else of its `body`; `statusOf(error: unknown): number | null`; `isNetworkFailure(error: unknown): boolean` — true for a `TransportError` and for the browser's own `TypeError`.
- Produces: `CODE_KEY: Record<ErrorCode, MessageKey>` — the mapping of design §10, verbatim:

```ts
const CODE_KEY: Record<ErrorCode, MessageKey> = {
  archive_invalid: "errors.refused",
  "embedding-mismatch": "errors.embeddingMismatch",
  "entity-invalid": "errors.refused",
  "entity-type-required": "errors.refused",
  "entity-type-unknown": "errors.refused",
  "extraction-failed": "errors.answerUnreadable",
  "key-unavailable": "errors.keyUnavailable",
  "mode-unknown": "errors.refused",
  "model-not-found": "errors.modelNotFound",
  "no-context": "errors.noContext",
  "not-found": "errors.notFound",
  order_mismatch: "errors.changedMeanwhile",
  "prompt-refused": "errors.promptUnavailable",
  "provider-auth": "errors.providerAuth",
  "provider-error": "errors.providerFailed",
  "provider-unavailable": "errors.providerUnavailable",
  "rate-limited": "errors.rateLimited",
  "relation-duplicate": "errors.refused",
  "relation-limit": "errors.refused",
  "relation-target-invalid": "errors.refused",
  "session-closed": "errors.closed",
  "suggestion-mismatch": "errors.changedMeanwhile",
  target_not_empty: "errors.refused",
  unknown: "errors.unexpected",
};
```

- Produces: `failureKey(error: unknown, fallback: MessageKey = "errors.unexpected"): MessageKey` — code first; then 404 `errors.notFound`, 429 `errors.rateLimited`, 5xx `errors.server`, any other status `errors.refused`; then `errors.network` for a rejected request; then the fallback.
- Produces: `useLocalizedError(): (error: unknown, fallback?: MessageKey) => string` — built on `useTranslation`; called while rendering.
- Produces in `web/lib/query.ts`: `function refused(what: string, response: Response, error?: unknown): ApiError`.

**New catalog keys**, seventeen, in the central catalogs in this sorted order:

| Key | English | German | French |
| --- | --- | --- | --- |
| `errors.answerUnreadable` | The answer could not be read. | Die Antwort war nicht lesbar. | La réponse n'a pas pu être lue. |
| `errors.changedMeanwhile` | This changed elsewhere in the meantime. Load it again and retry. | Das hat sich inzwischen anderswo geändert. Lade es neu und versuch es erneut. | Cela a changé entre-temps. Recharge-le et réessaie. |
| `errors.closed` | This was closed in the meantime. | Das wurde inzwischen geschlossen. | Cela a été clos entre-temps. |
| `errors.embeddingMismatch` | The embedding model has changed. The knowledge corpus must be embedded again before this works. | Das Embedding-Modell hat sich geändert. Der Wissenskorpus muss neu eingebettet werden, bevor das wieder funktioniert. | Le modèle d'embedding a changé. Le corpus de connaissances doit être vectorisé de nouveau avant que cela refonctionne. |
| `errors.keyUnavailable` | No key is stored for the AI provider this task uses. | Für den Provider dieser Aufgabe ist kein Schlüssel hinterlegt. | Aucune clé n'est enregistrée pour le fournisseur d'IA de cette tâche. |
| `errors.modelNotFound` | The AI model this task uses is no longer configured. | Das Modell dieser Aufgabe ist nicht mehr eingerichtet. | Le modèle d'IA de cette tâche n'est plus configuré. |
| `errors.network` | The server could not be reached. Try again. | Der Server ist nicht erreichbar. Versuch es erneut. | Le serveur est injoignable. Réessaie. |
| `errors.noContext` | There is no content for this request yet. | Für diese Anfrage gibt es noch keinen Inhalt. | Il n'y a pas encore de contenu pour cette requête. |
| `errors.notFound` | What you asked for was not found. | Das Gewünschte wurde nicht gefunden. | L'élément demandé est introuvable. |
| `errors.promptUnavailable` | The prompt behind this request is faulty. | Der Prompt hinter dieser Anfrage ist fehlerhaft. | Le prompt derrière cette requête est défectueux. |
| `errors.providerAuth` | The AI provider did not accept the stored key. | Der Provider hat den hinterlegten Schlüssel nicht akzeptiert. | Le fournisseur d'IA n'a pas accepté la clé enregistrée. |
| `errors.providerFailed` | The AI provider failed. Try again. | Der Provider hat versagt. Versuch es erneut. | Le fournisseur d'IA a échoué. Réessaie. |
| `errors.providerUnavailable` | No AI provider is configured for this task yet. | Für diese Aufgabe ist noch kein Provider eingerichtet. | Aucun fournisseur d'IA n'est encore configuré pour cette tâche. |
| `errors.rateLimited` | Too many requests in quick succession. Please wait a moment. | Zu viele Anfragen in kurzer Folge. Bitte kurz warten. | Trop de requêtes en peu de temps. Veuillez patienter un instant. |
| `errors.refused` | The request was refused. | Die Anfrage wurde abgelehnt. | La requête a été refusée. |
| `errors.server` | The server failed to answer. Try again. | Der Server hat nicht geantwortet. Versuch es erneut. | Le serveur n'a pas répondu. Réessaie. |
| `errors.unexpected` | Something unexpected went wrong. Try again. | Etwas Unerwartetes ist schiefgelaufen. Versuch es erneut. | Une erreur inattendue s'est produite. Réessaie. |

Where a term of art differs from the catalog's own — the French word for *prompt*, the German label of the AI rules section — the catalog's term wins; the reviewer reads the three languages side by side.

- [ ] **Step 1: Write the failing tests**

`web/lib/api/errors.test.ts`:

```ts
it("reads the code from each carrier the client builds", () => {
  expect(codeOf(new ApiError("x", { code: "rate-limited" }))).toBe("rate-limited");
  expect(codeOf(Object.assign(new Error("e"), { status: 422, detail: { code: "entity-invalid", detail: "…" } }))).toBe("entity-invalid");
  expect(codeOf(Object.assign(new Error("e"), { status: 422, body: { detail: { code: "prompt-refused" } } }))).toBe("prompt-refused");
  expect(codeOf(new ApiError("x", { code: "transport" }))).toBeNull();
});

it("names a failure by its code first, then its status family", () => {
  expect(failureKey(new ApiError("x", { status: 429, code: "rate-limited" }))).toBe("errors.rateLimited");
  expect(failureKey(new ApiError("x", { status: 404 }))).toBe("errors.notFound");
  expect(failureKey(new ApiError("x", { status: 422 }))).toBe("errors.refused");
  expect(failureKey(new ApiError("x", { status: 503 }))).toBe("errors.server");
});

it("names a request that never reached the server", () => {
  expect(failureKey(new TypeError("Failed to fetch"))).toBe("errors.network");
});

it("falls back when nothing names the failure", () => {
  expect(failureKey(new Error("bug"), "writing.shelf.error.title")).toBe("writing.shelf.error.title");
  expect(failureKey(new ApiError("no job to poll"))).toBe("errors.unexpected");
});

it("gives every code a sentence in every language", () => {
  for (const code of ERROR_CODES) {
    for (const language of locales) expect(catalogs[language][CODE_KEY[code]]).toMatch(/\S/);
  }
});

it("lets no request client throw a bare Error", () => {
  for (const file of ["lib/query.ts", "lib/updates.ts"]) {
    const source = readFileSync(join(WEB, file), "utf8");
    expect(source).not.toMatch(/throw new Error\(/);
  }
});
```

In `web/lib/query.test.ts`, the two existing refusal tests ("the dock's door throws the enriched refusal", "a refused 422 carries its detail across the mutation boundary") gain `toBeInstanceOf(ApiError)` and code assertions. The first keeps its existing model-change and 409 assertions; the second keeps its existing 422 and `detail` assertions.

In `web/lib/updates.test.ts`, the non-ok and missing-body cases reject with `ApiError`, keep their existing message pins, and expose statuses 503 and 200; `failureKey` names them `errors.server` and `errors.refused`.

- [ ] **Step 2: Run the tests red**

Run: `CI=true pnpm --dir web exec vitest run lib/api/errors.test.ts lib/query.test.ts lib/updates.test.ts`
Expected: FAIL — `web/lib/api/errors.ts` does not exist; the `errors.*` keys do not exist; `query.ts` and `updates.ts` throw bare errors.

- [ ] **Step 3: Implement the seam and the keys**

`web/lib/api/errors.ts` as the interface says. The seventeen keys go into the three central catalogs in sorted position; `just generate` carries them into the catalogs.

- [ ] **Step 4: Make the request clients throw one shape**

Every request-failure `throw` in `web/lib/query.ts` becomes `throw refused(what, response, error)`; the calls destructure `error` beside `data` and `response`. Preserve the `update_check_interval_days` fields added by #965 in `useSettings`, `SettingsChanges` and `useUpdateSettings`. `createEntityFailure` and `assistantFailure` build `ApiError` with the same `status`, `code` and `detail` they carry today (`row` and `field` through `extra`). `createEntityFailure`'s no-response case returns a `TransportError`; `assistantFailure`'s `provider-error` and `not-found` fallbacks are wire codes and stay. `SceneVersionConflict` stays its own class. `WireError` and its export go; its importers use `ApiError`. In `web/lib/updates.ts`, both the non-ok and missing-body branches use `refused("update check failed", response, error)` and pass no invented code.

- [ ] **Step 5: Run the tests green**

Run: `CI=true pnpm --dir web exec vitest run lib/api/errors.test.ts lib/query.test.ts lib/updates.test.ts`; `just typecheck`.
Expected: PASS. `just typecheck` is the other half of the gate: `CODE_KEY` cannot miss a member.

- [ ] **Step 6: Task gate, review and commit**

Task gate: `just check`, `CI=true just check-generated`, `CI=true just test-frontend`. Reviewer: the wire is unchanged; `SceneVersionConflict` is still thrown as its own class. Commit: `refactor(web): one failure shape behind the API client`, body: every request failure now carries its status and any stable code it had, and the mapping from code to catalog sentence is checked by the compiler.

---

## Task 8: Failures speak the reader's language

**Files:**
- Modify: `web/routes/__root.tsx`, `app/capabilities/writing/web/ShelfStates.tsx`, `ShelfPage.tsx`, `WorkspaceStates.tsx`, `WorkspacePage.tsx`, `ShelfBanner.tsx`, `NewBookDialog.tsx`, `app/capabilities/settings/web/ai-rules/providersSection.tsx`, `app/capabilities/prompts/web/refusal.tsx`, `app/capabilities/planning/web/routes.tsx`, `app/capabilities/knowledge/web/routes.tsx`, `app/capabilities/settings/web/routes.tsx`, `app/capabilities/prompts/web/routes.tsx`, `app/capabilities/writing/web/routes.tsx`, `app/capabilities/setup/web/setupStatusQuery.ts`
- Test: `web/routes/__root.test.tsx`, `app/capabilities/writing/web/ShelfPage.test.tsx`, `ShelfBanner.test.tsx`, `WorkspacePage.test.tsx`, `app/capabilities/settings/web/ai-rules/AiRulesPage.test.tsx`, `app/capabilities/prompts/web/PromptsPage.test.tsx`, `web/components/UpdateBanner.test.tsx`, `app/capabilities/settings/web/UpdatesSection.test.tsx`, `app/capabilities/setup/web/routes.test.tsx`, `app/capabilities/prompts/web/routes.test.tsx`, `app/capabilities/settings/web/routes.test.tsx`, `app/capabilities/knowledge/web/routes.test.tsx`, `app/capabilities/writing/web/routes.test.tsx`, `app/capabilities/planning/web/routes.test.tsx`
- E2E: `app/capabilities/prompts/e2e/test_prompts_e2e.py`

**Interfaces:**
- Consumes: `useLocalizedError` and `ApiError` from `web/lib/api/errors.ts`.
- Produces: the error components take the failure object, not a message: `ShelfError({ error: unknown; retrying: boolean; onRetry: () => void })`, `WorkspaceError(…)`, `BannerError(…)` with the same three props. Their callers keep the failure in the ref that held the message string (`lastError`), and the dialog keeps it in the state that held the string.
- Leaves unchanged: `UpdateBanner.tsx`, `ReleaseNotesDialog.tsx` and `UpdatesSection.tsx`; their existing localized copy and remote release content are pinned by tests.

- [ ] **Step 1: Write the failing tests**

- `web/routes/__root.test.tsx`: the route-error cases assert the alert has the text `catalogs[language]["errors.unexpected"]` and does not contain the thrown message; new: "a thrown failure with a status is named by its family" — a route throws `new ApiError("x", { status: 503 })`, the alert reads `errors.server` in the active language.
- `app/capabilities/writing/web/ShelfPage.test.tsx`: the error-alert case asserts the text `catalogs.de["errors.network"]` and not `"novels unavailable"`; new: "a language switch re-renders a failure that is on screen" — with the alert shown under `de`, `act(() => applyLocale("en"))`, and the alert reads `catalogs.en["errors.network"]`. The new-book dialog's refusal case asserts `catalogs.de["errors.refused"]` and not `"create refused"`. The shelf-list fixture throws a bare `TypeError("Failed to fetch")` and the dialog's refusal answers 422 without a code, because by the design's order a status-carrying 503 would read `errors.server`.
- `ShelfBanner.test.tsx`, `WorkspacePage.test.tsx`: their error faces assert the catalog sentence and not `"activity unavailable"` / `"novel unavailable"`.
- `app/capabilities/settings/web/ai-rules/AiRulesPage.test.tsx`: the refused-create face asserts `settings.refused`; the delete guard's 409 asserts `settings.ai.errors.guarded` and the key-store 503 `settings.ai.errors.keystore`, neither the backend's English (`"the provider still has models pointed at it: …"`, `"the key store refused"`), because the raw detail line no longer renders.
- `app/capabilities/prompts/web/PromptsPage.test.tsx`: the 422 save-gate face asserts the localized headline for its reason and not `"the assembled context exceeds the budget"`; the preview, live-test and reset-refusal cases do the same because the raw detail line no longer renders, and the reset cases assert the headline for each refusal's reason — `runtime` in most and `syntax` in the case the catalog labels Syntax.
- `app/capabilities/writing/web/routes.test.tsx`: the `/` gate's unreachable-status case asserts `t("errors.server")`, not the seam's English `"setup status unavailable"`.
- `web/components/UpdateBanner.test.tsx`: the failed-check case seeds `new ApiError("x", { status: 503 })` and asserts no banner or toast and no visible `"update check failed"` or `"503"`; the dismissal's empty catch stays because it renders nothing.
- `app/capabilities/settings/web/UpdatesSection.test.tsx`: after the refusal under `de`, `applyLocale("en")` and the alert reads `catalogs.en["settings.update.error"]`. Keep the capability-specific `t("settings.update.error")`; do not replace it with the generic `useLocalizedError()` sentence.

In `app/capabilities/prompts/e2e/test_prompts_e2e.py`, in `test_the_save_gate_refuses_by_name_and_the_honest_save_lands` and the preview's refusal: after the existing `to_contain_text(REFUSED_SYNTAX)`, add `expect(face).not_to_contain_text(re.compile(r"line \d+", re.IGNORECASE))`; Playwright builds a JavaScript `RegExp`, which has no inline `(?i)`.

- [ ] **Step 2: Run the tests red**

Run: `CI=true pnpm --dir web exec vitest run routes/__root.test.tsx app/capabilities/writing/web/ShelfPage.test.tsx app/capabilities/writing/web/ShelfBanner.test.tsx app/capabilities/writing/web/WorkspacePage.test.tsx app/capabilities/settings/web/ai-rules/AiRulesPage.test.tsx app/capabilities/prompts/web/PromptsPage.test.tsx components/UpdateBanner.test.tsx app/capabilities/settings/web/UpdatesSection.test.tsx`; `just test-e2e-file app/capabilities/prompts/e2e/test_prompts_e2e.py -k save_gate`. Vitest's root is `web`, so its filters are relative to it; the other seven filters are unchanged.
Expected: FAIL — the faces render raw messages and sentences.

- [ ] **Step 3: Translate at render**

- Root route's error component: `const localized = useLocalizedError();` and the alert renders `localized(error)`.
- `ShelfError`, `WorkspaceError`, `BannerError`: prop `error: unknown`; the mono line renders `localized(error)`. `ShelfPage`, `WorkspacePage`, `ShelfBanner` store the failure object in `lastError`.
- `NewBookDialog`: `setError(failure)`; the mono line renders `localized(error)`.
- `FamilyFace` in `providersSection.tsx`: the raw `detail` line and `detailLine` go.
- `refusal.tsx`: the raw `refusal.detail` line goes; the localized headline stays.
- `UpdateBanner`, `ReleaseNotesDialog` and `UpdatesSection`: no production rewrite. Their existing localized copy and remote release content stay; only the regression pins above land.

- [ ] **Step 4: Run the tests green**

Run: the Step 2 commands; `CI=true just test-frontend`.
Expected: PASS.

- [ ] **Step 5: Prove no face renders a raw failure**

Run: `rg -n "error\.message|\.message\)|err\.message|\{refusal\.detail\}|\{detail\}" web app --glob '*.tsx' --glob '!*.test.*'`
Expected: no output outside `web/lib/api/errors.ts` and the console logging of a failed catalog load.

- [ ] **Step 6: Task gate, review and commit**

Task gate: `just check`, `CI=true just test-frontend`, `just test-e2e prompts`, `just test-e2e settings`, `just test-e2e writing`. Reviewer follows one known code, one unknown failure and one network failure from the API to the visible line, checks that a face that keeps a failure in a ref re-renders on a language switch, and checks the update-check pins without replacing their capability-specific copy. Commit: `fix(i18n): show failures in the reader's language` with
`User-visible: A failure — a server that does not answer, a refused request, a missing book — appears in the reader's language on the shelf, in the workspace, in the new-book dialog, on the error page, in the AI rules and in the prompt editor; no face shows the backend's English sentence, and a language switch re-renders a failure that is on screen.`

---

## Task 9: One lazy module per language

**Files:**
- Modify: `scripts/generate_capabilities.py` (`typescript_catalogs`; new `typescript_endonyms`, `typescript_catalog_module`, `lazy_catalog_outputs`; `main()`)
- Create, generated: `web/lib/generated/catalogs/de.ts`, `web/lib/generated/catalogs/fr.ts`
- Regenerate: `web/lib/generated/catalogs.ts`
- Test: `app/api/test_catalog_merge.py`, `app/api/test_capability_views.py`

**Interfaces:**
- Produces generator: `typescript_endonyms(root: Path, known: tuple[str, ...]) -> str` — from each central catalog's `locale.name`; `typescript_catalog_module(root: Path, known: tuple[str, ...], locale: str) -> str`; `lazy_catalog_outputs(root: Path, known: tuple[str, ...]) -> dict[str, str]` — one entry per language other than the source, keyed by `web/lib/generated/catalogs/<identifier>.ts`.
- Produces TypeScript (generated, additive in this task): in `web/lib/generated/catalogs.ts` — `export type Catalog = typeof en_merged;`, `export type CatalogModule = { locale: Locale; default: Catalog };`, `export const endonyms: Record<Locale, string>`, `export const catalogLoaders: { [L in Exclude<Locale, "en">]: () => Promise<CatalogModule> }` with one literal `() => import("./catalogs/<identifier>")` per language. In each module — `export const locale = "<code>" as const;` and `export default <identifier>_merged satisfies Catalog;`.

- [ ] **Step 1: Write the failing tests**

`app/api/test_catalog_merge.py` (a root with `en`, `de` and `pt-BR` catalogs):

```python
def test_every_other_language_is_one_lazy_module(tmp_path: Path) -> None:
    for code in ("en", "de", "pt-BR"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"locale.name": code, "app.title": code})
    outputs = lazy_catalog_outputs(tmp_path, ("en", "de", "pt-BR"))
    assert set(outputs) == {
        "web/lib/generated/catalogs/de.ts",
        "web/lib/generated/catalogs/pt_BR.ts",
    }
    assert 'export const locale = "pt-BR" as const;' in outputs["web/lib/generated/catalogs/pt_BR.ts"]
    assert "export default pt_BR_merged satisfies Catalog;" in outputs["web/lib/generated/catalogs/pt_BR.ts"]


def test_the_loader_map_names_every_other_language_once(tmp_path: Path) -> None:
    typescript = typescript_catalogs(tmp_path, ("en", "de", "pt-BR"), ("de", "en", "pt-BR"))
    assert 'de: () => import("./catalogs/de"),' in typescript
    assert '"pt-BR": () => import("./catalogs/pt_BR"),' in typescript
    assert 'import("./catalogs/en")' not in typescript
```

The loader map is keyed by the locale code `pt-BR`; `pt_BR` names the module file and its merged object, never an object key.

In `app/api/test_capability_views.py`, extend `test_committed_typescript_catalogs_match_the_catalog_files`: every module `lazy_catalog_outputs` names is committed byte for byte.

- [ ] **Step 2: Run the tests red**

Run: `just test-file app/api/test_catalog_merge.py`, `just test-file app/api/test_capability_views.py`.
Expected: FAIL — the three functions do not exist.

- [ ] **Step 3: Implement**

The generator writes a module per non-source language with imports relative to `web/lib/generated/catalogs/`, a type-only import of `Catalog`, the merged object and the two exports. `typescript_catalogs` appends `endonyms`, `CatalogModule` and `catalogLoaders`; the eager `catalogs` map keeps every language for now — the runtime still reads it. `main()` merges `lazy_catalog_outputs` into its outputs; the module docstring lists the lazy modules beside the views.

- [ ] **Step 4: Generate and run green**

Run: `just generate`; `just test-file app/api/test_catalog_merge.py`; `just test-file app/api/test_capability_views.py`; `CI=true just check-generated`; `just typecheck`.
Expected: PASS. The two modules exist; nothing at runtime reads them yet, and `CI=true just test-frontend` stays green.

- [ ] **Step 5: Task gate, review and commit**

Task gate: `just check`, `CI=true just check-generated`, `CI=true just test-frontend`. Commit: `refactor(i18n): emit one lazy catalog module per language`, body: the generator now writes each non-source catalog as its own module with a loader map and the endonyms, so the shell can load a language when it is first read.

---

## Task 10: The catalog store and the test bed

**Files:**
- Create: `web/lib/catalog.ts`, `web/lib/catalog.test.ts`, `web/lib/catalog.failure.test.ts`, `web/lib/test/catalogs.ts`, `web/lib/test/setup.ts`, `web/lib/test/catalogs.test.ts`
- Modify: `web/vite.config.ts` (`test.setupFiles`), the test files that import `catalogs` from `generated/catalogs` (44 at the current baseline)

**Interfaces:**
- Consumes: `catalogs`, `catalogLoaders`, `Catalog`, `Locale`, `locales` from `web/lib/generated/catalogs`.
- Produces: `catalogFor(locale: Locale): Catalog` — never throws, never `undefined`; an unloaded language reads the source catalog. `isLoaded(locale: Locale): boolean`. `setCatalog(locale: Locale, catalog: Catalog): void`. `loadCatalog(locale: Locale): Promise<Catalog>` — resolved at once for the source language; otherwise one request per language, shared by parallel callers; rejects when the module cannot be fetched and leaves the store untouched. `resetCatalogs(): void` — forgets every catalog but the source one; the tests' starting point.
- Produces (test-only): `web/lib/test/catalogs.ts` exports `merged: Record<string, Catalog>` — every non-source module under `generated/catalogs/`, read with `import.meta.glob("../generated/catalogs/*.ts", { eager: true })` and keyed by each module's `locale`, with `merged.en = catalogs.en` seeded explicitly because no `en.ts` module exists. It also exports `de`, `en`, `fr`, and `preloadCatalogs(): void`, which calls `setCatalog` for every entry of `merged`. `web/lib/test/setup.ts` calls `preloadCatalogs()`, assigns a no-op to `window.scrollTo` (a dependency calls it on mount, and jsdom logged 980 lines of "Not implemented" while no test under `web/` or `app/` reads a scroll position), and is the one `setupFiles` entry.

- [ ] **Step 1: Write the failing tests**

`web/lib/catalog.test.ts` (calls `resetCatalogs()` in `beforeEach`):

```ts
it("always has the source catalog", () => {
  expect(catalogFor("en")).toBe(catalogs.en);
  expect(isLoaded("en")).toBe(true);
});

it("reads the source catalog for a language that is not loaded", () => {
  expect(catalogFor("de")).toBe(catalogs.en);
  expect(isLoaded("de")).toBe(false);
});

it("reads a language's own catalog once it is loaded", async () => {
  await loadCatalog("de");
  expect(catalogFor("de")).toBe(merged.de);
  expect(isLoaded("de")).toBe(true);
});

it("answers parallel loads of one language with the same catalog", async () => {
  const [first, second] = await Promise.all([loadCatalog("fr"), loadCatalog("fr")]);
  expect(first).toBe(second);
  expect(await loadCatalog("fr")).toBe(first);
});

it("loads the source language without a request", async () => {
  expect(await loadCatalog("en")).toBe(catalogs.en);
});
```

`web/lib/catalog.failure.test.ts` mocks `./generated/catalogs` and follows the Global Constraints' rule for mocking the bed:

```ts
vi.mock("./generated/catalogs", async (importOriginal) => {
  const real = await importOriginal<typeof import("./generated/catalogs")>();
  return { ...real, catalogLoaders: { ...real.catalogLoaders, de: () => Promise.reject(new Error("chunk")) } };
});

it("rejects a language whose module cannot be fetched and leaves the store untouched", async () => {
  vi.resetModules();
  const { catalogFor, isLoaded, loadCatalog, resetCatalogs } = await import("./catalog");
  const { catalogs } = await import("./generated/catalogs");
  resetCatalogs();
  await expect(loadCatalog("de")).rejects.toThrow("chunk");
  expect(isLoaded("de")).toBe(false);
  expect(catalogFor("de")).toBe(catalogs.en);
});
```

`web/lib/test/catalogs.test.ts`: "the bed holds every language before a test runs" — for each of `locales`, `isLoaded(code)` is true and `catalogFor(code)` is `merged[code]`.

- [ ] **Step 2: Run the tests red**

Run: `CI=true pnpm --dir web exec vitest run lib/catalog.test.ts lib/catalog.failure.test.ts lib/test/catalogs.test.ts`
Expected: FAIL — `web/lib/catalog.ts` does not resolve.

- [ ] **Step 3: Implement the store**

`web/lib/catalog.ts` as the interface says, on a `Map` of loaded catalogs seeded with the source and a `Map` of in-flight promises.

- [ ] **Step 4: Build the bed and move the tests off the eager table**

- `web/lib/test/catalogs.ts`: the eager glob, typed through a cast to `Record<string, CatalogModule>`; seed `merged.en = catalogs.en`; export `merged`, `de`, `en`, `fr`, `preloadCatalogs`.
- `web/lib/test/setup.ts` and `setupFiles: ["./lib/test/setup.ts"]` in `web/vite.config.ts`.
- In the test files that import `catalogs`: `catalogs.de` → `de`, `catalogs.fr` → `fr`, `catalogs.en` → `en`, and a dynamic `catalogs[<expression>]` → `merged[<expression>]`, with `de`, `en`, `fr`, `merged` imported from the test helper (`@shell/lib/test/catalogs` outside `web/`, `./test/catalogs` or `../test/catalogs` inside); an import of `generated/catalogs` keeps only `locales` and the types a file still uses; the local aliases the import replaces go; Biome sorts the imports.

- [ ] **Step 5: Run the tests green and prove the move**

Run: the Step 2 commands; `just typecheck`; `CI=true just test-frontend`.
Expected: PASS.

Run: `rg -n "catalogs\.(de|fr|en)\b" web app --glob '*.test.*'`; `rg -n "catalogs\[" web app --glob '*.test.*'`
Expected: the second has no output. The first has two hits, and they stay: the `vi.mock` factories in `web/lib/locale.script.test.ts` and `web/lib/language.registry.test.tsx` fabricate a registry entry on top of `real.catalogs.en` — the bed's own mocking, not a test's read of a language's catalog.

- [ ] **Step 6: Task gate, review and commit**

Task gate: `just check`. Reviewer: a test never takes its expected text from the store; the change in the test files is the import and the three identifiers and nothing else. Commit: `refactor(web): add the catalog store and move the tests off the eager table`, body: the store that will hand a language its catalog exists with its contract pinned, and the tests read each language's real catalog through one helper, so the eager table can shrink without a vacuous pass.

---

## Task 11: Catalogs load when they are read

**Files:**
- Modify: `web/lib/i18n.ts`, `web/lib/locale.ts`, `web/routes/__root.tsx`, `web/lib/language.tsx`, `app/capabilities/settings/web/SettingsPage.tsx`, `scripts/generate_capabilities.py` (`typescript_catalogs`)
- Regenerate: `web/lib/generated/catalogs.ts`
- Modify: `CONTRIBUTING.md` (the sentence on where the generator merges catalogs)
- Test: `web/lib/locale.loading.test.ts` (new), `web/lib/language.test.tsx`, `web/lib/language.registry.test.tsx` (its mock gains `endonyms`), `web/lib/i18n.test.ts`, `web/routes/__root.boot.test.tsx` (new), `app/capabilities/settings/web/SettingsPage.test.tsx`, `app/api/test_catalog_merge.py` (its hyphenated-locale case pins the eager table's old shape), `app/capabilities/writing/web/GoalSetter.test.tsx` (its case awaits the English save button after `choose("en")`, because activation is async)
- E2E: `app/capabilities/settings/e2e/test_settings_e2e.py`

**Interfaces:**
- Consumes: `catalogFor`, `isLoaded`, `loadCatalog` from `web/lib/catalog.ts`; `endonyms` from the generated module.
- Produces: `hydrateLocale(target: Locale): Promise<void>` in `web/lib/locale.ts` — loads `target`'s catalog; when it cannot be fetched, logs to the console and makes the source language active; never rejects; afterwards `isLoaded(activeLocale())` holds. `targetLocale(locale: Locale | null): Locale` — the code itself, the browser's language for `null`, the source when the browser speaks none of them. `activateLocale(locale: Locale | null): Promise<boolean>` — loads `targetLocale(locale)`, then calls `applyLocale`; on a failed load the active language stays and the call resolves `false`. `choose`'s guard has two clauses: a language is already selected only when `next === chosenLocale()` and `targetLocale(next) === activeLocale()`. The boot retains the reader's stored choice, a click on the row's language is a retry, and a restore announces a language only when its catalog is in the store, otherwise the source becomes active.
- Supersession: `hydrateLocale` and `activateLocale` share one counter in `web/lib/locale.ts`; each call takes the next number at start and calls `applyLocale` (or `reveal`) only while its number is still the latest. A superseded load still fills the store but activates nothing: `activateLocale` resolves `false`, so `choose` writes nothing, and `hydrateLocale` returns without revealing. The restore after a refused write stays under `patchCachedLocale`'s generation guard.
- Generated, changed: `catalogs` in `web/lib/generated/catalogs.ts` holds the source language only; nothing else in that file changes.

- [ ] **Step 1: Write the failing tests**

`web/lib/locale.loading.test.ts` mocks `./catalog` and follows the Global Constraints' rule for mocking the bed:

```ts
const control = vi.hoisted(() => ({
  failFr: true,
  releaseFr: null as (() => void) | null,
}));

vi.mock("./catalog", async (importOriginal) => {
  const real = await importOriginal<typeof import("./catalog")>();
  return {
    ...real,
    loadCatalog: async (locale: Locale) => {
      if (locale === "fr") {
        if (control.failFr) throw new Error("chunk");
        await new Promise<void>((resolve) => {
          control.releaseFr = resolve;
        });
      }
      return real.loadCatalog(locale);
    },
  };
});

beforeEach(() => {
  control.failFr = true;
  control.releaseFr = null;
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(async () => {
  control.releaseFr?.();
  control.releaseFr = null;
  await Promise.resolve();
  await Promise.resolve();
  vi.restoreAllMocks();
});

it("falls back to the source language when the first paint's catalog cannot be fetched", async () => {
  vi.resetModules();
  const { activeLocale, applyLocale, hydrateLocale } = await import("./locale");
  const { resetCatalogs } = await import("./catalog");
  resetCatalogs();
  applyLocale("en");
  await expect(hydrateLocale("fr")).resolves.toBeUndefined();
  expect(activeLocale()).toBe("en");
  expect(console.error).toHaveBeenCalled();
});

it("keeps the active language when a switch's catalog cannot be fetched", async () => {
  vi.resetModules();
  const { activateLocale, activeLocale, applyLocale } = await import("./locale");
  const { loadCatalog } = await import("./catalog");
  // `applyLocale` never announces a language without its catalog: the
  // German catalog is put in the store first, as the boot's hydration does.
  await loadCatalog("de");
  applyLocale("de");
  await expect(activateLocale("fr")).resolves.toBe(false);
  expect(activeLocale()).toBe("de");
  await expect(activateLocale("de")).resolves.toBe(true);
  expect(activeLocale()).toBe("de");
});

it("only the latest of two overlapping choices becomes active", async () => {
  vi.resetModules();
  const { activateLocale, activeLocale, applyLocale } = await import("./locale");
  const { isLoaded, loadCatalog } = await import("./catalog");
  control.failFr = false;
  // `applyLocale` never announces a language without its catalog: the
  // German catalog is put in the store first, as the boot's hydration does.
  await loadCatalog("de");
  applyLocale("de");

  const first = activateLocale("fr");
  await expect(activateLocale("en")).resolves.toBe(true);
  expect(activeLocale()).toBe("en");

  control.releaseFr?.();
  await expect(first).resolves.toBe(false);
  expect(activeLocale()).toBe("en");
  expect(isLoaded("fr")).toBe(true);
});
```

`web/lib/language.test.tsx`: "a superseded choice writes nothing" — the second of two quick choices activates and the first writes nothing.

`web/lib/language.test.tsx`: "a refused catalog keeps the previous language and writes nothing" — `choose("fr")` under `de` leaves `activeLocale()` at `de` and `api.PATCH` uncalled; beside it, a click on the row's language retries it and writes once, a retry whose catalog still fails keeps the source and writes nothing, a refused write restores the stored choice without announcing its missing catalog, and a stored follow whose browser catalog is missing restores the source.

`web/lib/i18n.test.ts`: "`t()` reads the store" — after `resetCatalogs()`, `applyLocale("de")` renders `nav.back` in English; after `await loadCatalog("de")`, in German.

`web/routes/__root.boot.test.tsx` drives the real boot with the router scaffolding of `__root.test.tsx`, in the same mocking manner: "the first paint waits for the catalog and speaks the row's language" — with the row's locale `fr` and the real loaders, the not-found heading reads the French catalog; "a catalog that cannot be fetched opens the page in the source language" — with `loadCatalog` rejecting for `fr`, that heading reads the English catalog.

In `app/capabilities/settings/e2e/test_settings_e2e.py`:

```python
def test_a_language_is_loaded_only_when_it_is_read(page: Page, installed: Stack) -> None:
    asked: list[str] = []
    page.on("request", lambda request: asked.append(request.url))
    goto_settings(page)
    expect(page.get_by_role("heading", name=HEADING_DE)).to_be_visible()
    page.get_by_text("Français", exact=True).click()
    expect(page.get_by_role("heading", name=HEADING_FR)).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name=HEADING_FR)).to_be_visible()
    await_settings(locale="fr")

    def module_requests(code: str) -> int:
        return sum(1 for url in asked if f"/lib/generated/catalogs/{code}.ts" in url)

    assert module_requests("de") >= 1, "the browser's language is fetched when it is read"
    assert module_requests("fr") >= 1, "a switched-to language is fetched when it is read"
    assert module_requests("en") == 0, "the source language is bundled, never fetched"
    # The controlled box settles after the awaited load; following the browser
    # also renames it, so click and assert the landed face.
    page.get_by_role("checkbox", name=FOLLOW_FR).click()
    expect(page.get_by_role("checkbox", name=FOLLOW_DE)).to_be_checked()
    await_settings(locale=None)
```

`HEADING_FR` and `FOLLOW_FR` are the French heading and the French follow-the-browser label, copied literally from the settings capability's `fr` catalog.

- [ ] **Step 2: Run the tests red**

Run: `CI=true pnpm --dir web exec vitest run lib/locale.loading.test.ts lib/language.test.tsx lib/language.registry.test.tsx lib/i18n.test.ts routes/__root.boot.test.tsx`; `just test-e2e-file app/capabilities/settings/e2e/test_settings_e2e.py -k loaded_only`.
Expected: FAIL — `hydrateLocale` and `activateLocale` do not exist; `t()` still reads the eager table; the E2E fails because the eager table serves French without any request for its module.

- [ ] **Step 3: Make the runtime read the store**

- `t()` in `web/lib/i18n.ts` reads `catalogFor(locale)[key]` in both branches of its lookup.
- `hydrateLocale` and `activateLocale` as the interface says.
- `web/routes/__root.tsx`: after the settings read succeeds — `adoptServerLocale(settings.data.locale)`, `await hydrateLocale(readPreSetupLocale() ?? activeLocale())`, `adoptServerTheme(…)`, `setReady(true)`.
- `useLanguageChoice` in `web/lib/language.tsx`: every path that makes a chosen language active — the pre-setup mirror at mount and `choose` — goes through `activateLocale`; the restore after a refused write stays a synchronous `applyLocale(previous)`, because that catalog was active before.
- `language.tsx` and `SettingsPage.tsx` read `endonyms[code]` instead of `catalogs[code]["locale.name"]`.

- [ ] **Step 4: Shrink the eager table**

`typescript_catalogs` emits `export const catalogs = { en: en_merged } as const satisfies Record<"en", Catalog>;` and no merged object for any other language. Run `just generate`.
Expected: `web/lib/generated/catalogs.ts` imports the English catalogs only.

- [ ] **Step 5: Run the tests green**

Run: the Step 2 commands; `CI=true just check-generated`; `CI=true just test-frontend`; `just test-e2e settings`.
Expected: PASS.

- [ ] **Step 6: Prove it in the build**

Run: `just build`; `ls web/dist/assets | grep -E '^(de|fr)-[A-Za-z0-9_-]+\.js$'`; `rg -l -F "Einstellungen" web/dist/assets`; `rg -l -F "Einstellungen" web/dist/assets --glob '!de-*.js'`; `ls -l web/dist/assets`.
Expected: exactly two lines from the first — one `de-…js`, one `fr-…js`; exactly one file from the second and its name starts with `de-`; no output from the third. A hit outside `de-*.js` that is not catalog text names another string only the German catalog has; the reviewer confirms where a hit comes from. The `ls -l` output goes beside the Task 0 baseline into the SDD task report and the pull request's verification table: the eager graph lost two catalogs.

- [ ] **Step 7: Update the contributor documentation**

`CONTRIBUTING.md`: the generator merges both into `web/lib/generated/catalogs.ts` for the source language and into one lazy module per other language under `web/lib/generated/catalogs/`, which the shell loads when that language is first read.

- [ ] **Step 8: Task gate, review and commit**

Task gate: `just check`, `CI=true just check-generated`, `CI=true just test-frontend`, `just test-e2e settings`, `just test-e2e writing` (the task changes the boot every route runs through; writing is its heaviest consumer). Reviewer: every path to an active language awaits its catalog; the pre-setup mirror included. Commit: `perf(i18n): load a language's catalog only when it is read` with
`User-visible: A reader of English no longer downloads the German and French catalogs; German and French readers fetch theirs once as a cached file. Nothing else changes on screen.`

---

## Task 12: Manuscript prose carries its language

**Files:**
- Modify: `web/globals.css`, `app/capabilities/writing/web/SceneEditor.tsx`, `EditorColumn.tsx`, `ZenMode.tsx`
- Test: `web/lib/fontStacks.test.ts` (new), `app/capabilities/writing/web/SceneEditor.test.tsx`, `EditorColumn.test.tsx`, `ZenMode.test.tsx`
- E2E: `app/capabilities/writing/e2e/test_workspace_e2e.py`

**Interfaces:**
- Produces: `SceneEditor({ …, language?: string | null })` — sets `lang` on the ProseMirror element (`editor.view.dom`) to `language` when it is set and removes it otherwise, in an effect on `[editor, language]`. `EditorColumn` and `ZenMode` pass `language={novel.language ?? null}`.
- Produces, in `web/globals.css` directly after the `:root` block, unlayered — three rules whose Han families are exactly:

| Rule | `--font-ui` adds | `--font-serif` adds |
| --- | --- | --- |
| `:lang(zh)` | `"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC"` | `"Songti SC", "SimSun", "Noto Serif CJK SC", "Source Han Serif SC"` |
| `:lang(ja)` | `"Hiragino Sans", "Yu Gothic", "Meiryo", "Noto Sans CJK JP"` | `"Yu Mincho", "Hiragino Mincho ProN", "Noto Serif CJK JP"` |
| `:lang(ko)` | `"Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans CJK KR"` | `"AppleMyungjo", "Batang", "Noto Serif CJK KR"` |

Each declaration has three parts, in order: every named family of the base stack in the base's order (emoji fonts included, the base's generic family left out), then the rule's Han families in the table's order, then the base's generic family last (`sans-serif` for `--font-ui`, `serif` for `--font-serif`). No generic family may stand before a Han family: a browser resolves a generic against the system's fallback list and would never consult the later Han families on fontconfig systems.

- [ ] **Step 1: Write the failing tests**

`web/lib/fontStacks.test.ts`, reading `web/globals.css` as `web/lib/tokens.test.ts` does:

```ts
it.each(["zh", "ja", "ko"])("gives %s its own stacks", (language) => {
  const start = CSS.indexOf(`:lang(${language}) {`);
  const block = CSS.slice(start, CSS.indexOf("}", start)).replace(/\s+/g, " ");
  expect(block).toContain("--font-ui:");
  expect(block).toContain("--font-serif:");
  expect(block).toContain(HAN_FAMILIES[language].ui.join(", "));
  expect(block).toContain(HAN_FAMILIES[language].serif.join(", "));
});

it("keeps the base stacks free of Han families", () => {
  const start = CSS.indexOf(":root {");
  const root = CSS.slice(start, CSS.indexOf("}", start));
  for (const family of EVERY_HAN_FAMILY) expect(root).not.toContain(family);
});
```

`HAN_FAMILIES` is the table above as literals, in the quotes `globals.css` uses; `EVERY_HAN_FAMILY` is the union derived from them (twenty-one families, none shared).

`app/capabilities/writing/web/SceneEditor.test.tsx`, following the neighboring cases' inline `body`, `onChange` and `label` props (there is no `baseProps` helper today):

```ts
it("carries the manuscript's language on its prose", async () => {
  const { container } = render(<SceneEditor body="Text" onChange={vi.fn()} label="Scene" language="ja" />);
  await waitFor(() => expect(container.querySelector(".ProseMirror")?.getAttribute("lang")).toBe("ja"));
});

it("leaves the prose to the interface's language when the manuscript names none", async () => {
  const { container } = render(<SceneEditor body="Text" onChange={vi.fn()} label="Scene" language={null} />);
  await waitFor(() => expect(container.querySelector(".ProseMirror")?.hasAttribute("lang")).toBe(false));
});
```

The repository carries no jest-dom, so the cases read the attribute directly.

`EditorColumn.test.tsx` and `ZenMode.test.tsx`: with `novel.language === "zh-Hans-CN"` the prose has `lang="zh-Hans-CN"`.

In `app/capabilities/writing/e2e/test_workspace_e2e.py`, beside `_goto_workspace`:

```python
def test_the_prose_carries_the_manuscripts_language(page: Page, installed: Stack) -> None:
    novel = _seed_klang()  # the book the file's workspace cases open, as they read its id
    patch_novel(novel["id"], language="ja")
    _goto_workspace(page, novel["id"])
    expect(page.locator(".ProseMirror")).to_have_attribute("lang", "ja")
```

- [ ] **Step 2: Run the tests red**

Run: `CI=true pnpm --dir web exec vitest run lib/fontStacks.test.ts app/capabilities/writing/web/SceneEditor.test.tsx app/capabilities/writing/web/EditorColumn.test.tsx app/capabilities/writing/web/ZenMode.test.tsx`; `just test-e2e-file app/capabilities/writing/e2e/test_workspace_e2e.py -k manuscripts_language`.
Expected: FAIL — no `:lang()` rule exists; `SceneEditor` has no `language` prop; the prose has no `lang`.

- [ ] **Step 3: Implement**

The three rules in `web/globals.css`, with a comment saying why the manuscript's `lang` picks the face. The `language` prop and its effect in `SceneEditor`; the two call sites pass `novel.language ?? null`.

- [ ] **Step 4: Run the tests green**

Run: the Step 2 commands; `CI=true just test-frontend`.
Expected: PASS.

- [ ] **Step 5: Task gate, review and commit**

Task gate: `just check`, `CI=true just test-frontend`, `just test-e2e writing`. Reviewer: no test asserts a glyph, a computed font or a pixel; the Latin `@font-face` rules and the font binaries are untouched. Commit: `fix(web): let manuscript prose carry its language and pick its face` with
`User-visible: A manuscript written in Chinese, Japanese or Korean reads in its language's own typeface, and screen readers hear the manuscript in its language.`

---

## Final Verification

- [ ] **Branch gate:** `CI=true just verify all` on the whole branch, once, plus `CI=true just check-generated` because `just verify` does not include the generated-files gate; read both outputs.
- [ ] **Whole-branch review** by a fresh reviewer who did not review a task. Every surviving finding becomes a `follow-up` issue with its `area:` label, hung under the wave's index issue from Task 0; nothing is dropped for being minor.
- [ ] **Before each push:** `pre-commit run` on the staged set and `pre-commit run --hook-stage pre-push`; outputs read.
- [ ] **The pull request's body** names the gate actually run with its read result; under Boundaries it ticks the registry and the typed union as approved (design §7); under UX review it ticks "All user-visible strings go through the merged catalogs" and "Errors say what happened and what to do next".
- [ ] **The title stays the plain sentence** from Task 0; the plan and the design are references in the body. The branch lands as a merge commit.

## Out of Scope

- Right-to-left layout, `dir` attributes and logical CSS.
- A fourth language; translation of novel content, demo novels, help articles or AI prompts.
- A palette; the ⌘K chip stays the interim it is.
- Server-side `<html lang>`, a FastAPI route for catalogs, JSON artifacts under `web/public/`, shell templating.
- Registry membership for `novels.language`.
- A new check script, hook, gate or mandatory document.
- Extending the formality overlay.
- Structured diagnostic parameters on the wire.
- Migrating the capability enrichers (`enrich`, `refused`) to `ApiError`.
- Import-report conflict codes as failures.
- A new error code or catalog key for the update check's code-less 409.
- Any assertion about rendered glyphs.

## Deviations

Execution departed from this plan's text in the places below; each entry names the cause and the coordinator's decision that ruled it. Gate evidence stays in the SDD task reports under `.superpowers/sdd/` (git-ignored), which record each departure's result; it is not repeated here.

- **Design §11, the deferred typo.** "dynamously" becomes "dynamically"; Task 0 deferred the correction to this commit.
- **Task 2, the parser's locale and the ordinal fixture's order.** `missingCategories` keeps `new IntlMessageFormat(message, locale)` because the locale reaches parsing only for datetime skeletons and `requiredCategories` builds `Intl.PluralRules` on the same argument; the ordinal fixture expects the sorted array because the engine's category order differs between Node versions and the rule names a set. Ruled: correct both places in the plan.
- **Task 1, the malformed-code test.** The test creates both catalogs so parity cannot raise and only the tag check can; the reviewer showed the parity message also matched the malformed code's first ten characters. Ruled: correct Step 1's text to the test as built.
- **Task 5, the `maxLength` expectation.** Step 5 pins `web/lib/api/openapi.json`, where the settings update's locale carries `maxLength: 64`; the pinned `openapi-typescript@7.13.0` emits none, so `schema.d.ts` stays byte-identical. Ruled: correct the expectation, with its cause.
- **Task 7, the German `errors.*` values.** The five values say `Provider` and `Modell`, not `KI-Anbieter` and `KI-Modell`; the design's sentence already let the catalog's own term win. Ruled: correct the plan's table only.
- **Task 8, five corrections.** The vitest filter is root-relative (`components/UpdateBanner.test.tsx`); the E2E regex uses `re.IGNORECASE` because Playwright builds a JavaScript `RegExp` with no inline `(?i)`; the file lists gain the writing `routes.test.tsx` and the six setup-status gates with their tests, whose removed pins now name the refusal's reason and the family sentence; the shelf fixture throws a bare `TypeError` and the dialog's refusal answers 422 without a code, because a status-carrying 503 would read `errors.server`; design §10 names the six gates and the two removed detail lines. Ruled: correct all five.
- **Task 9, the loader key.** The loader map is keyed by the locale code, `"pt-BR": () => import("./catalogs/pt_BR")`; `pt_BR` names the module file and its merged object, never an object key. Ruled: correct the assertion.
- **Task 10, the two `rg` hits.** The first search keeps two hits, the bed's own `vi.mock` factories in `web/lib/locale.script.test.ts` and `web/lib/language.registry.test.tsx`, which fabricate a registry entry on `real.catalogs.en`; the second has none. The "44 at the current baseline" stays because it was true at the plan's baseline. Ruled: name the two hits; the count and `setupFiles` stand.
- **Global Constraints, `CI=true`.** The rule applies to `just test-frontend` and `just check-generated`; `just check` and `just typecheck` ran without it as the gate lines prescribe. Ruled: narrow the sentence to the gates it means.
- **Task 11, six corrections.** The boot retains the reader's stored choice and a click on the row's language is a retry; the interface names `targetLocale`, `choose`'s two-clause guard and the fallback cases; the E2E clicks the controlled French checkbox and asserts the landed `FOLLOW_DE` face; `test_catalog_merge.py` and `GoalSetter.test.tsx` stay in the commit because Step 4 and the async activation change them; the task gate adds `just test-e2e writing`; one activation counter makes the latest call win, a superseded choice activates nothing and resolves `false`, and `hydrateLocale` returns without revealing. Ruled: correct all six.
- **Task 0, the baseline's branch.** The bundle baseline was recorded on the fresh `feat/i18n-hardening` branch at `main`'s tip, not "on `main`". Ruled: tighten the wording in both documents.
- **Task 1, the help fixture.** `scripts/tests/test_generate_help.py` stays in the commit: its fixture writes a registry for `locales()` and creates `web/` for `help_coverage`'s UI-only rule. Ruled: add it to the file list.
- **Task 2, the sweep and the red-phase count.** The sweep reads `merged` and asserts that every language of `locales` had a plural walked, so an empty walk cannot pass. The plan's red-phase count was too high because the `[]` fixtures pass vacuously; Step 2 states the count as built. Ruled: correct the test text and the count.
- **Task 7, the no-response failure.** `TransportError extends ApiError` carries a request that threw before there was a response; `isNetworkFailure` recognizes it and the browser's `TypeError`; `createEntityFailure`'s no-response case returns it, while `assistantFailure`'s `provider-error` and `not-found` fallbacks stay wire codes. Ruled: correct the interface and design §10.
- **Task 10, the scroll no-op.** `web/lib/test/setup.ts` also assigns a no-op to `window.scrollTo`, with its reason: a dependency calls it on mount, jsdom logged 980 lines of "Not implemented", and no test under `web/` or `app/` reads a scroll position. Ruled: name it in the plan's interface line; the design's sentence stands.
- **Task 12, the `:lang()` shape and the assertions.** Each declaration has three parts — the base's named families in order, the rule's Han families, then the base's generic family last — because a generic family before a Han family makes fontconfig resolve the generic and never consult the later Han families; `EVERY_HAN_FAMILY` is the union of the twenty-one quoted literals; the scene cases read `getAttribute` and `hasAttribute` because the repository carries no jest-dom. Ruled: correct both documents.

**Revalidated on 2026-11-26 against `main` `12186926e`:** the update-check wave (#965) moved the Alembic head to `12fc7ddcec6f`, added the update interval fields that Task 7 must preserve, and added `web/lib/updates.ts` plus update-check faces that need regression pins but no new error code or catalog key. The plan also corrects the current throw/test counts, the Task 1 committed-file anchor, the source-catalog seed in the test bed, the interchange pattern ownership and the inline `SceneEditor` test props.

**From the reviewed draft of 2026-11-25**, this revision already carries these changes: no server injection, JSON route or `web/public/i18n` artifacts; no registry flags and no number words in the registry; no fourth check script and no gate before `just generate`; no per-task reports under `docs/`; the plural rule with its lone-`many` exception, written into rule 5; the error inventory by symbol and by actual emitters, with the import-report codes out; translation at render; the overlay left as it is; the language order from the registry and pinned end to end; both language columns widened; one branch and one pull request; both documents in English.
