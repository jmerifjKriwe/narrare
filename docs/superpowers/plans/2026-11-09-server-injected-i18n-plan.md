# Implementation Plan: Server-Injected Locale Catalogs

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop shipping every locale in the first paint. The build emits one
data artifact per locale; production templates the active one into the shell;
the client fetches a locale only on a switch or when the palette needs all of
them. `t()` stays synchronous.

**Architecture:** The generator writes `web/public/i18n/<locale>.json`
(`{messages, overlay}`) and a type-only source module. FastAPI's shell handler
resolves the locale from the user row and inlines that one artifact; a
`/i18n/<locale>.json` route serves switches. The client keeps a small catalog
store with a synchronous read and a source-locale fallback.

**Tech Stack:** Python 3.14, FastAPI, Vite/React/TanStack Router, existing
`just generate`.

**Spec:** `docs/superpowers/specs/2026-11-09-server-injected-i18n-design.md`

**Dispatch:** implementer `zai-coding-plan/glm-5.3-flash`; reviewer
`opencode-go/deepseek-v4.1-flash`. The reviewer does not edit, stage, commit or
push.

**Task report:** `docs/superpowers/reports/2026-11-09-i18n-report.md`, one
section per task with the gate run and its result, written as the work happens.

**Prerequisite:** the fourth and fifth locale catalogs are merged and
`just generate` is clean on the branch's base. This plan is written against
`locales` as a generated tuple and never hardcodes a count; the fixture is real
five-locale data, not a projection.

**Ordering rule:** every task leaves the tree green and the app behaving as
before. The generated table keeps every locale until Task 6, when no reader is
left; the eager bytes disappear in that commit, not earlier.

## Global Constraints

- No new standing rule, checker, hook or required field (CONSTRAINTS §8).
  `just check-generated` gains one watched path; that is an extension.
- Generated files are regenerated with `just generate`, never hand-edited.
- Rule 5 is unchanged: same keys in every catalog, sorted, capability text in
  the capability catalog. Only the delivery format changes.
- English in code and tests.
- No i18n library, no partial catalogs, no service worker, no localStorage copy.
- The shell and the catalog route stay `no-store`.
- A user-visible change is done only with a green E2E (rule 2).

---

## Task 1: The generator emits locale data

**Files:**
- Modify: `scripts/generate_capabilities.py`
- Modify: `app/api/test_capability_views.py`
- Create (generated): `web/public/i18n/<locale>.json`,
  `web/lib/generated/endonyms.ts`

**Interfaces:**
- New `json_catalogs(known, loaded, overlays) -> dict[str, str]` returns
  path → serialized JSON for every locale.
- New `typescript_endonyms(loaded) -> str`.
- `typescript_catalogs` and `typescript_overlays` are **unchanged** in this
  task; the table keeps every locale until Task 6.

- [ ] **Step 1: Write the failing tests**

In `app/api/test_capability_views.py`:

1. New `test_committed_json_catalogs_match_the_catalog_files`: for every locale,
   the committed `web/public/i18n/<locale>.json` equals the generator's output,
   parses to `{"messages": …, "overlay": …}`, and its `messages` keys equal the
   source catalog's key set exactly.
2. New `test_committed_endonyms_match_the_catalog_files`: every locale's
   `locale.name` appears in `web/lib/generated/endonyms.ts`.

Run: `just test-file app/api/test_capability_views.py`
Expected: both new tests fail (the files do not exist).

- [ ] **Step 2: Implement**

- `json_catalogs`:
  `json.dumps({"messages": messages, "overlay": overlays.get(locale, {})}, ensure_ascii=False, indent=2, sort_keys=True) + "\n"`.
- `typescript_endonyms`:
  `export const endonyms: Record<Locale, string> = { "de": "Deutsch", … };`
  built from each catalog's `locale.name` (already in `REQUIRED_DOC_KEYS`).
- `main()`: add the JSON outputs and the endonym view to `outputs`. The write
  loop already creates parent directories.

- [ ] **Step 3: Regenerate and run the tests**

Run: `just generate`
Expected: `wrote web/public/i18n/en.json` (and every other locale), `wrote
web/lib/generated/endonyms.ts`.

Run: `just test-file app/api/test_capability_views.py`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_capabilities.py app/api/test_capability_views.py \
  web/lib/generated/endonyms.ts web/public/i18n
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor(i18n): generate locale catalogs as data artifacts"
```

---

## Task 2: The catalog store

**Files:**
- Create: `web/lib/catalog.ts`
- Create: `web/lib/catalog.test.ts`

**Interfaces:**
- Produces the API named in the spec §4.4:
  `catalogFor`, `isLoaded`, `setCatalog`, `loadLocale`, `loadAllLocales`,
  `allCatalogs`, `subscribeCatalogs`, `catalogsVersion`, plus
  `injectedCatalog(): { locale: Locale; entry: CatalogEntry } | null`.

- [ ] **Step 1: Write the failing tests**

`catalog.test.ts` (node environment; `vi.stubGlobal("fetch", …)`; the injected
case gets a `// @vitest-environment jsdom` file-level docblock or moves to
`catalog.dom.test.ts`):

1. Before a load, `catalogFor("de")` returns the source catalog's messages and
   an empty overlay.
2. `loadLocale("de")` fetches `/i18n/de.json` once; a second call makes no
   second request; `isLoaded("de")` turns true.
3. `loadAllLocales()` fetches every non-source locale once and leaves them
   available through `allCatalogs()`.
4. A rejected fetch rejects `loadLocale` and leaves the fallback in place — no
   half-installed entry.
5. `setCatalog` installs an entry and increments `catalogsVersion`; subscribers
   are notified exactly once.
6. `injectedCatalog()` parses `#narre-catalog` when present and returns `null`
   without it; malformed JSON returns `null` rather than throwing.

- [ ] **Step 2: Run and watch them fail**

Run: `pnpm --dir web exec vitest run catalog`
Expected: cannot resolve `./catalog`.

- [ ] **Step 3: Implement `catalog.ts`**

- `const loaded = new Map<Locale, CatalogEntry>()`.
- `SOURCE: CatalogEntry = { messages: catalogs.en, overlay: {} }`.
- `catalogFor(locale)` returns `loaded.get(locale) ?? SOURCE`.
- `loadLocale` keeps an in-flight `Map<Locale, Promise<void>>` so two callers
  share one request; on success `setCatalog`, on failure delete the in-flight
  entry and rethrow.
- `catalogsVersion()` returns a counter that `setCatalog` increments; it is the
  stable `useSyncExternalStore` snapshot.
- `injectedCatalog()` reads the element by id, `JSON.parse`, validates the locale
  against `locales` and the two object fields, returns `null` on any mismatch.
  Guard `document` with `typeof document === "undefined"`, the way `locale.ts`
  already does, so the module loads in the node test environment.

- [ ] **Step 4: Run the tests**

Run: `pnpm --dir web exec vitest run catalog`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/catalog.ts web/lib/catalog.test.ts
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "feat(web): hold locale catalogs in a loadable store"
```

---

## Task 3: `t()` reads the store, and the boot loads the locale

**Files:**
- Modify: `web/lib/i18n.ts`
- Modify: `web/lib/i18n.test.ts`
- Modify: `web/lib/locale.ts`
- Modify: `web/routes/__root.tsx`

The two halves ship together: an `i18n.ts` that reads the store without a boot
that fills it would render English for a German user between commits.

- [ ] **Step 1: Rewrite the catalog gates over the JSON artifacts**

`i18n.test.ts` imports `web/public/i18n/*.json` for every locale instead of
`catalogs[candidate]`, and `beforeAll` installs them into the store
(`setCatalog`) so `applyLocale` stays synchronous. Every assertion survives:

- same keys in every locale,
- no empty strings,
- every message parses as ICU,
- the conflict-code table renders in every locale,
- the formal register serves the overlay and falls through where it is silent,
- plural rules use each locale's categories.

Add the hydration cases here (or in a new `web/lib/locale.test.ts`):

1. `hydrateLocale("de")` loads and only then announces — a subscriber sees one
   notification, and `activeLocale()` is still the previous locale while the
   fetch is pending (use a deferred promise).
2. A rejected load leaves the active locale unchanged.
3. With `#narre-catalog` present, the module's initial `activeLocale()` is the
   injected locale and `catalogFor` already has its messages.
4. `document.documentElement.lang` follows the announced locale.

- [ ] **Step 2: Run and watch it fail**

Run: `pnpm --dir web exec vitest run i18n`
Expected: `i18n.ts` still reads `catalogs[locale]`; `hydrateLocale` is not
exported.

- [ ] **Step 3: Implement**

`i18n.ts`:

```ts
const entry = catalogFor(locale);
const message =
  formality === "formal" && locale !== "en"
    ? (entry.overlay[key] ?? entry.messages[key])
    : entry.messages[key];
```

`MessageKey` stays `keyof typeof catalogs.en`. Drop the `overlays` import. The
formatter cache is unchanged: the active locale is only announced after its
catalog is loaded, so the key can never name the wrong language.

`locale.ts`:

```ts
const injected = injectedCatalog();
let active: Locale = injected?.locale ?? fromBrowser() ?? SOURCE;

export async function hydrateLocale(locale: Locale | null): Promise<void> {
  const target = locale ?? fromBrowser() ?? SOURCE;
  await loadLocale(target);      // throws on failure; caller decides
  adoptServerLocale(locale);     // the one place that sets `chosen` + announces
}
```

`adoptServerLocale` and `applyLocale` stay synchronous and keep their meanings;
`hydrateLocale` is the one async edge.

`__root.tsx`'s effect:

```ts
useEffect(() => {
  if (!settings.isSuccess) return;
  adoptServerTheme(settings.data.theme);
  void hydrateLocale(settings.data.locale)
    .catch(() => {})            // the store already falls back to the source catalog
    .finally(() => setReady(true));
}, [settings.data, settings.isSuccess]);
```

The comment is rewritten: the gate still prevents a wrong-language first paint,
and now it also covers the catalog. A failed load keeps the previous locale (the
store's fallback is the source catalog), and the page renders — never nothing.

- [ ] **Step 4: Run the tests**

Run: `pnpm --dir web exec vitest run`
Expected: pass; the app still renders every locale (Task 6 has not removed the
eager table yet).

- [ ] **Step 5: Commit**

```bash
git add web/lib/i18n.ts web/lib/i18n.test.ts web/lib/locale.ts web/routes/__root.tsx
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "feat(web): load the chosen locale before the first paint

User-visible: the app opens in the chosen language without a flash of another."
```

---

## Task 4: The switcher and its endonyms

**Files:**
- Modify: `web/components/LanguageSwitcher.tsx`

- [ ] **Step 1: Implement**

- Options render `endonyms[code]` from the generated table (no catalog read).
- `choose`: `await hydrateLocale(next)` — it loads **and** applies, so do not
  call `applyLocale` a second time. The existing `try/catch` handles both a load
  failure and a refused write, restoring the previous choice with
  `applyLocale(previous)` (whose catalog is still loaded). Update the comment:
  the page keeps the old language while the new one is fetched, and that is the
  intended behaviour, not a stall.

- [ ] **Step 2: Run the gates**

Run: `just check` and `just test-frontend`
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add web/components/LanguageSwitcher.tsx
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor(web): the language switcher names each language from the registry"
```

---

## Task 5: The palette's cross-locale search

**Files:**
- Modify: `web/lib/commands.ts`
- Modify: `web/components/Palette.tsx`
- Modify: `web/lib/commands.test.tsx`

- [ ] **Step 1: Write the failing test**

`matchesAllLocales(titleKey, query, entries)`:

1. A German word finds the row when the German entry is passed, even from an
   English active locale.
2. Without the German entry the same query does not match (the documented
   narrowing, not an accident).
3. Whitespace and case handling are unchanged.

- [ ] **Step 2: Implement**

- `matchesAllLocales` takes `messages: ReadonlyArray<Record<string, string>>` and
  searches them; no module-level catalog import.
- `Palette.tsx`: on open, `void loadAllLocales().catch(() => {})` (a locale that
  fails to load narrows the search for this session; the palette still works);
  subscribe with
  `useSyncExternalStore(subscribeCatalogs, catalogsVersion, catalogsVersion)` so
  the row list recomputes when the entries land; pass
  `Object.values(allCatalogs()).map((entry) => entry.messages)`. `catalogsVersion()`
  is a number — a snapshot function that returned a fresh object would re-render
  forever. The module comment that claims the catalogs are already in the bundle
  is replaced with the truth: the palette loads them when it opens, and until
  then it searches what is loaded.

- [ ] **Step 3: Run the tests**

Run: `pnpm --dir web exec vitest run commands`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add web/lib/commands.ts web/components/Palette.tsx web/lib/commands.test.tsx
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor(web): the palette loads the locales it searches over its own path"
```

---

## Task 6: The eager table loses every non-source locale

**Files:**
- Modify: `scripts/generate_capabilities.py`
- Modify: `app/api/test_capability_views.py`
- Delete: `web/lib/generated/overlays.ts`
- Regenerate: `web/lib/generated/catalogs.ts`

Nothing reads de/fr from the table any more (Tasks 3–5), so this is the commit
that removes the bytes.

- [ ] **Step 1: Update the pinning test first**

`test_committed_typescript_catalogs_match_the_catalog_files` asserts the new
shape: `export const locales = [...]`, `export const catalogs = { "<source>":`,
`export type MessageKey`, and **no** `import de_`/`import fr_` line.
Delete `test_committed_typescript_overlays_match_the_overlay_files`.

Run: `just test-file app/api/test_capability_views.py`
Expected: the changed test fails.

- [ ] **Step 2: Implement**

- `typescript_catalogs`: import only the merged source catalog; emit `locales`,
  `Locale`, `catalogs = { "<source>": <source>_merged } as const`, `Catalog`,
  `MessageKey = keyof Catalog`. The header states that other locales are data
  files.
- Remove `typescript_overlays` and its `outputs` entry.
- Delete `web/lib/generated/overlays.ts`.

- [ ] **Step 3: Regenerate and run the gates**

Run: `just generate`
Expected: `wrote web/lib/generated/catalogs.ts`; no overlays view.

Run: `just test-file app/api/test_capability_views.py`, `just check`,
`just test-frontend`
Expected: pass.

Run: `just build`
Expected: the build succeeds and the i18n chunk no longer carries de/fr (the
mechanical proof is Task 9).

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_capabilities.py app/api/test_capability_views.py \
  web/lib/generated
git rm web/lib/generated/overlays.ts
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "perf(i18n): stop bundling the locales the reader cannot read"
```

---

## Task 7: The shell carries the catalog

**Files:**
- Modify: `app/api/main.py`
- Modify: `app/api/test_spa.py`

- [ ] **Step 1: Write the failing tests**

In `test_spa.py`, extend `_dist` to write `i18n/<locale>.json` for two locales.
Pin:

1. A shell request for a user whose row stores `de` answers
   `<html lang="de">` and a `#narre-catalog` element whose JSON parses to the
   German messages.
2. The source locale is not injected: an `en` request carries no
   `#narre-catalog`.
3. Without a stored locale, `Accept-Language: fr` picks French.
4. A missing `dist/i18n/<locale>.json` serves the shell unchanged (no script).
5. A message containing `</script>` is escaped as `\u003c/script`.
6. `GET /i18n/de.json` returns the file, `no-store`; `GET /i18n/xx.json` and a
   traversal path are 404.

- [ ] **Step 2: Run and watch them fail**

Run: `just test-file app/api/test_spa.py`
Expected: no `lang` replacement, no script, 404 on `/i18n/de.json`.

- [ ] **Step 3: Implement**

- `_serve_shell`: `SessionDep` + `UserDep`; read `User.locale`; resolve
  `stored → Accept-Language (primary subtag) → "en"`; wrapped in
  `try/except Exception` that falls back to the header path. The `get_session`
  dependency does not open a connection when it yields (`async_sessionmaker`
  connects on first use, `pool_pre_ping` included), so the handler body — not
  dependency resolution — is where a database failure appears and can be
  caught. If in doubt, point a test at a closed port; do not add a retry.
- Read `dist/i18n/<locale>.json` per document request (a few KB; the shell is
  `no-store` anyway); if absent, return the shell as today.
- Replace `<html lang="en">` and insert the JSON script before `</head>`,
  escaping `<` as `\u003c` in the serialized text. Keep
  `Cache-Control: no-store`.
- New route `/i18n/{name}`: accept only `<locale>.json` from the generated
  locales, resolve inside `dist/i18n`, serve with `no-store`, 404 otherwise.
  Register it **before** the `/{full_path:path}` catch-all — FastAPI matches in
  registration order, and the catch-all is registered last in `_serve_shell`.
  This route is deliberately narrow: the missing root-file route (fonts,
  favicons, filed as #727) is a separate defect, not repaired here. If it
  is repaired first, serve the catalogs through that handler and delete this
  one.

- [ ] **Step 4: Run the tests**

Run: `just test-file app/api/test_spa.py`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add app/api/main.py app/api/test_spa.py
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "feat(api): ship the active locale inside the shell

User-visible: the app's first paint is already in the chosen language, without
a catalog request."
```

---

## Task 8: The generated-files gate

**Files:**
- Modify: `justfile` (`check-generated` watched paths)

- [ ] **Step 1: Extend the watched paths**

Add `web/public/i18n` beside `web/lib/generated` in the `git status
--porcelain` argument list. Nothing else changes; the recipe's contract (only
generated paths, fail on drift) stays.

- [ ] **Step 2: Regenerate and compare**

Run: `just check-generated`
Expected: pass, no diff. If it reports `web/public/i18n` as untracked, the
Task 1 commit missed the artifacts — fix that, do not add an exclusion.

- [ ] **Step 3: Commit**

```bash
git add justfile
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "chore(i18n): let the generated-files gate watch the catalog artifacts"
```

---

## Task 9: Prove it in the browser and in the bundle

**Files:**
- Modify: `app/capabilities/settings/e2e/test_settings_e2e.py`

- [ ] **Step 1: Extend the language E2E**

In `test_a_chosen_language_survives_a_fresh_browser` (and the register test
beside it):

- Assert the switch requests `/i18n/de.json`:
  `with page.expect_response(lambda r: r.url.endswith("/i18n/de.json")): …`.
- After the fresh context, assert the boot requests the same file (the spawned
  stack is dev-shaped, so the fetch path is the one under test) and that the
  page renders German.

- [ ] **Step 2: Run the E2E**

Run: `just test-e2e settings`
Expected: pass, including their axe assertions.

- [ ] **Step 3: Build and measure**

Run: `just build`
Then:

```bash
rg -l "Einstellungen" web/dist/assets            # expect no output (exit 1)
ls web/dist/i18n                                  # expect one file per locale
ls -l web/dist/assets/i18n-*.js 2>/dev/null || true
```

Record the asset sizes in the report and compare them with the spec's table
(§1). The proof is the first command: a German UI string must no longer be in
the JavaScript bundle. If it is, something still imports a locale eagerly.

- [ ] **Step 4: Commit**

```bash
git add app/capabilities/settings/e2e
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "test(settings): prove the chosen catalog is fetched, not shipped

User-visible: switching language downloads one catalog instead of carrying
all of them."
```

---

## Task 10: Verify and report

- [ ] `just check`
- [ ] `just check-generated`
- [ ] `just test`
- [ ] `just test-frontend`
- [ ] `just test-e2e settings`
- [ ] `just build` + the two checks from Task 9
- [ ] Report: every gate with its exit status, the measured bundle numbers, the
  before/after table, and the one accepted cost (generation-time parity instead
  of `tsc` parity) stated in the deviations section.

## Review Focus

- `t()` never awaits and never throws: the active locale is announced only
  after its catalog is loaded, and the store's fallback is the source catalog.
- The formatter cache cannot serve the previous language: the announce order is
  load → apply.
- The shell's DB read is caught: an unreachable database still renders the
  shell, in `Accept-Language` or English.
- The injected JSON is escaped; a message cannot break out of the script tag.
- `/i18n/<name>` serves only generated locale filenames from `dist/i18n`, with
  the same realpath check as `/assets`.
- The palette's search is complete after its load and never silently loses the
  active locale.
- No German or French UI string remains in `web/dist/assets/*.js`.
- The E2E proves the fetch, not only the rendered language.
- `web/lib/generated/overlays.ts` is gone and nothing imports it.
- No commit in the sequence left the app rendering the wrong language.
