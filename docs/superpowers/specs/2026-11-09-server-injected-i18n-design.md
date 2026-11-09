# Spec: Server-Injected Locale Catalogs

**Date:** 2026-11-09
**Status:** Proposed
**Author:** Coordinator
**Depends on:** the fourth and fifth locale catalogs landing first (they are
data-only additions and are not part of this work)

---

## 1. Problem

The web bundle carries every locale catalog eagerly. `web/lib/generated/catalogs.ts`
statically imports all catalogs for all capabilities; the build emits one
`i18n-*.js` chunk that every page load downloads, parses and keeps, although
exactly one locale is active.

Measured on the committed build (2026-11-09):

| Item | raw | gzip |
|---|---|---|
| `assets/i18n-BdvN4P-J.js` | 127 660 B | 32 845 B |
| en catalog (merged) | 26 747 B | 6 581 B |
| de catalog (merged) | 28 901 B | 7 500 B |
| fr catalog (merged) | 29 258 B | 7 476 B |
| `assets/index-*.js` | 371 421 B | 116 000 B |

At three locales, two thirds of that chunk is waste on every session. Two more
locales are planned, which brings the eager chunk to roughly 185 KB raw / 48 KB
gzip: about a third of the main chunk's gzip weight, paid by every reader for
text they cannot read.

## 2. Goals

- Only the active locale's text is in the first paint, and it costs no extra
  round trip in production.
- The other locales load on demand: on a language switch, and for the command
  palette's cross-locale search when it opens.
- `t()` stays synchronous and pure. No caller, no component and no test learns
  an asynchronous i18n API.
- `MessageKey` stays a compile-time key union; a typo at a call site stays a
  build error.
- Locale parity, sorting and required keys stay enforced at generation time.
- Dev and production behave the same towards the client: the same fetch path
  exists in both, production merely pre-answers it.

## 3. Non-Goals

- No i18n library (i18next, Lingui, Paraglide, FormatJS runtime). The generated
  catalog plus `IntlMessageFormat` is already smaller and stricter; a library
  would replace a compile-time union with runtime lookups.
- No partial catalogs and no runtime fallback-to-English for missing keys. The
  parity gate stays; it is what makes the key union trustworthy.
- No service worker, no hashed catalog filenames, no localStorage copy of a
  catalog (a second source of truth that goes stale after a deploy).
- No change to key names, ICU syntax, sorting, or the formality overlay model.
- No SSR framework, no hydration: the shell stays a SPA; only the one JSON blob
  is templated in.

## 4. Design

### 4.1 Delivery artifact

The generator writes one merged catalog per locale:

```
web/public/i18n/<locale>.json
{
  "messages": { "<key>": "<text>", ... },
  "overlay":  { "<key>": "<formal text>", ... }
}
```

- `messages` is the capability-merged catalog the generator already builds.
- `overlay` is the sparse formal-register variant for that locale (`{}` for the
  source locale, which has no formality distinction).
- `web/public` is Vite's `publicDir`: dev serves the files directly, and the
  build copies them to `dist/i18n/` verbatim.
- The files are generated and committed. `just check-generated` gains
  `web/public/i18n` in its watched-path list; that extends an existing gate and
  creates no new one (§8).

`web/lib/generated/overlays.ts` disappears; the overlay travels with its locale.

### 4.2 Type source

`web/lib/generated/catalogs.ts` keeps exactly what a type needs and nothing
else:

```ts
export const locales = ["en", "de", "fr"] as const;
export type Locale = (typeof locales)[number];

/** The source catalog: the type's origin and the runtime fallback. */
export const catalogs = { en: en_merged } as const;
export type Catalog = typeof en_merged;
export type MessageKey = keyof Catalog;
```

- `catalogs.en` still exists, so `MessageKey`, `keyof typeof catalogs.en` in the
  generated registries, and every `catalogs.en[...]` in tests keep working
  unchanged.
- No de/fr data is in the bundle. `catalogs` is not `Record<Locale, …>`; code
  that iterated all locales is rewritten (see 4.6).
- The plan lands this in two steps — data artifacts first, this shrinkage last —
  so every commit in between still renders every locale.
- The compact English object stays in the source but is bundled once (6.6 KB
  gzip) as the source catalog and the failure fallback.
- **Trade-off, stated openly:** "a locale missing a key" moves from a `tsc`
  error at the generated assignment to a `just generate` failure
  (`scripts/generate_capabilities.py` already raises with the locale and the
  missing keys). `just generate` runs in `check-generated`, which CI runs on
  every PR; `just verify` deliberately does not. This is a weaker *local* gate
  and a stricter *message*; the plan makes the generator check the named
  invariant.

### 4.3 Server: the shell carries the active catalog

`_serve_shell` (`app/api/main.py`) resolves the locale and templates the shell:

1. **Locale.** Read `User.locale` for the requesting user (`current_user_id`;
   the row lives on `User`, see `app/capabilities/settings/service.py`). If the
   stored value is a known locale, use it; otherwise match `Accept-Language` on
   the primary subtag against `locales`; otherwise `en`.
2. **Catalog.** Read `dist/i18n/<locale>.json`. If the file is missing (an older
   build), serve the shell unchanged and let the client fetch.
3. **Template.**
   - Replace `<html lang="en">` with `<html lang="<locale>">` so the
     document's language is right before any script runs.
   - Insert before `</head>`:
     `<script type="application/json" id="narre-catalog">…</script>` with the
     merged entry and the locale. Replace `<` with `\u003c` in the serialized
     JSON so a message can never close the script element.
   - The source locale is **not** injected: the client already bundles `en`.
4. **Failure.** Any database error is caught; the handler falls back to
   `Accept-Language`/`en`. The shell must render when the database is
   unreachable — that is exactly when the user needs the page that reports it.

A new route serves the artifacts for the switch path:

```
GET /i18n/<locale>.json   → dist/i18n/<locale>.json, Cache-Control: no-store
```

Only a filename produced by the generated `locales` tuple is served; the same
realpath prefix check as `/assets/{path}` applies. A miss is a 404; the shell
catch-all already refuses suffixed paths, so `/i18n/de.json` never answers
HTML.

**Known adjacent defect, not fixed here.** The built shell has no route for
root-level files at all: `_serve_shell` serves `/assets/{path}` and
`/THIRD-PARTY-NOTICES.txt`, and the catch-all 404s every suffixed path. The
build's `/fonts/*.woff2` (referenced from the CSS) and the favicons are
therefore unreachable in production, and no E2E sees it because the spawned
stack runs Vite. This route is deliberately narrow so the i18n work does not
grow into that repair; if the root-file gap is fixed first, the catalogs should
ride on that handler instead of a second one. The gap is filed as #727.

### 4.4 Client: synchronous reads, async only at the edges

New module `web/lib/catalog.ts`:

```ts
type CatalogEntry = { messages: Record<string, string>; overlay: Record<string, string> };

catalogFor(locale): CatalogEntry      // loaded entry, else the bundled source
isLoaded(locale): boolean
setCatalog(locale, entry): void
loadLocale(locale): Promise<void>     // fetch /i18n/<locale>.json, cache
loadAllLocales(): Promise<void>       // Promise.all over locales
allCatalogs(): Partial<Record<Locale, CatalogEntry>>
subscribeCatalogs(listener): () => void
catalogsVersion(): number             // increments on setCatalog; a stable snapshot
```

- `catalogFor` never returns `undefined`: an unloaded locale falls back to the
  source catalog. That is the failure net, not the normal path.
- `i18n.ts` reads `catalogFor(activeLocale())` once per call; the formatter
  cache key stays `locale + formatLocale + formality + key`. Because the active
  locale is only announced after its catalog is loaded, a cached formatter can
  never serve the previous language.
- `locale.ts` gains `hydrateLocale(locale: Locale | null): Promise<void>`:
  resolve the target (given value → browser → source), `await loadLocale(target)`,
  and only then `applyLocale(target)`. `applyLocale` stays synchronous and keeps
  its current meaning for tests and callers that already hold the catalog.
- Boot: `catalog.ts` reads `#narre-catalog` at module load, registers the entry
  and sets `document.documentElement.lang`. `locale.ts` initialises `active`
  from the injected locale, else browser, else source.
- `__root.tsx`: the existing `ready` gate awaits `hydrateLocale(settings.data.locale)`
  before `setReady(true)`. The catalog fetch joins the settings request the gate
  already waits for; in production the catalog is already there and the await
  resolves without a request. The gate's comment is updated: no flash, because
  the first paint still waits for the language.
- Switch (`LanguageSwitcher.choose`): `await hydrateLocale(next)` **before**
  applying and persisting. The UI keeps the old language for the duration of one
  local fetch (milliseconds). A load failure shows the existing refusal path and
  leaves the previous choice in place; a persist failure rolls back as today
  (the loaded catalog is harmless).
- Palette (`Palette.tsx`): on open, `void loadAllLocales()` and subscribe to
  `subscribeCatalogs`; `matchesAllLocales` takes the loaded message maps as a
  parameter instead of importing the table. Until the load lands, the search
  covers the active locale and the source — a window measured in milliseconds on
  a local service; the module comment in `commands.ts` is updated to say so.
- Endonyms (`LanguageSwitcher`): a tiny generated
  `web/lib/generated/endonyms.ts`, built from each catalog's `locale.name`
  (already in `REQUIRED_DOC_KEYS`, so a new locale without it fails generation).

### 4.5 What the first paint costs

| | en reader | de reader |
|---|---|---|
| 5 locales, eager (today's shape) | ~48 KB gzip | ~48 KB gzip |
| this design (bundled source + inline active) | ~6.6 KB gzip | ~14 KB gzip |

Savings: ~34 KB gzip on first load per reader, and each further locale adds no
first-load cost. The palette's first open pays ~30 KB gzip once per session
(four locale files, HTTP-cached); the language switch pays ~7.5 KB gzip.

### 4.6 Consequences elsewhere

- `web/lib/commands.ts` (`matchesAllLocales`) and `Palette.tsx`: parameter
  instead of module import; the comment that says "The catalogs are already in
  the bundle" is false after this change and is rewritten.
- `web/components/LanguageSwitcher.tsx`: endonyms from the generated table.
- `web/lib/i18n.test.ts`: imports the three `web/public/i18n/*.json` artifacts
  and keeps every existing gate — same keys, no empty strings, every message
  parses as ICU, the conflict-code table, the formal register.
- `web/lib/commands.test.tsx`: passes the loaded message maps.
- The generated registries (`capabilities.ts`, `docks.ts`, `settingsPages.ts`)
  are unchanged: `keyof typeof catalogs.en` still exists. The generator's
  pinning tests change where the shape changes (catalogs in Task 6, overlays
  test removed).
- `web/lib/generated/overlays.ts` is deleted; `i18n.ts` no longer imports it.

### 4.7 Dev, production, E2E

- **Dev** (`just dev`): Vite serves `web/public/i18n/*.json`; the shell is not
  templated; the client fetches the active catalog. One code path, the same
  failure handling.
- **Production / container:** FastAPI templates the shell; the client finds the
  catalog already loaded and makes no request.
- **E2E (spawned stack):** dev-shaped, so the suites exercise the fetch path.
  The templating path is pinned by `app/api/test_spa.py` and exercised by the
  container gate (`NARRE_E2E_ATTACH`), which runs the image itself.

## 5. Constraints

- No new standing rule, checker, hook or required field (CONSTRAINTS §8).
- Generated files are regenerated with `just generate`; `check-generated` gains
  the new watched path and nothing else.
- Rule 5 unchanged: same keys in every catalog, sorted, capability text in the
  capability catalog. The delivery format changes; the source format does not.
- The shell stays `no-store`; the catalog route is `no-store` too (it changes
  only with a release, and a language switch is rare).
- The server only serves files from `dist/i18n/` whose names are in the
  generated `locales` tuple, with the realpath prefix check used for assets.
- Injected JSON escapes `<` as `\u003c`.

## 6. Risks

- **HTML templating.** A markup change in `index.html` (the `<html lang="en">`
  literal, the `</head>` anchor) would silently disable injection. The server
  test asserts both replacements, and the fallback fetch keeps the app working
  when a replacement misses.
- **Dev/prod divergence.** The injected path is not exercised by the spawned
  E2E. Mitigation: `test_spa.py` covers templating and fallback; the container
  gate covers the real image.
- **Database read on the shell path.** One indexed row per document load; caught
  and fallen back on failure. The shell must not become a second health check.
- **Test priming.** Component tests that render de/fr must load the catalogs
  first (`beforeAll: await loadAllLocales()` or `setCatalog` from the JSON
  fixture). A test that forgets will assert English and fail loudly, not
  silently.
- **The lost `tsc` parity check.** Covered by the generator's check, executed by
  CI's `check-generated`; a local `just check` alone no longer proves parity.
  The plan states this in the report rather than hiding it.
- **Palette window.** Cross-locale search is complete only after the load; on a
  local service the gap is milliseconds. If the load fails, the search is
  narrower for that session — the palette still works.

## 7. Decisions Made

1. **Delivery:** catalogs as data served per locale, not as JS chunks. JSON has
   no module wrapper, is usable by both the server and the client, and cannot
   drift from the inline copy.
2. **Injection vs. fetch:** production injects; dev fetches. Same client code.
3. **Source locale:** bundled, as type origin and fallback; never injected.
4. **Overlay:** folded into the locale artifact; a locale is one file.
5. **Switcher:** awaits the catalog before announcing; no mixed-language frame.
6. **Palette:** loads all locales on open; behavior preserved, cost deferred to
   the moment it is needed.
7. **Type unit:** `catalogs.en` stays; `MessageKey` and the generated registries
   are untouched.

## 8. Expected Verification

- `just check-generated` — the artifacts exist, are committed and match the
  sources.
- `just test-file app/api/test_spa.py` — injection (lang + script), the source
  locale not injected, a missing artifact falls back, `/i18n/<locale>.json`
  serves and 404s correctly.
- `just test-frontend` — catalog store, fallback, switch, palette search, all
  existing i18n gates over the JSON artifacts.
- `just test-e2e settings` — a language switch survives a reload; German pages
  render (via the fetch path).
- `just build` plus two mechanical checks: no German UI string in
  `web/dist/assets/*.js` (`rg -l "Einstellungen" web/dist/assets` finds
  nothing) and `web/dist/i18n/` carries every locale. The measured asset sizes
  go into the report.
