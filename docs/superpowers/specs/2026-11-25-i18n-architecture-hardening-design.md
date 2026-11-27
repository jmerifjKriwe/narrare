# Localization hardening — design

**Date:** 2026-11-25
**Status:** Approved — the owner settled the five open questions and approved the design and
13-task plan on 2026-11-26. This text was revalidated against `main` `12186926e` after the
update-check wave (#965).
**Lane:** A — it changes a schema, types the wire's error vocabulary and changes how catalogs load.
**Supersedes in scope:** `docs/superpowers/specs/2026-11-09-server-injected-i18n-design.md`
(proposed, never built) and `docs/superpowers/plans/2026-11-09-server-injected-i18n-plan.md`.
**Implementation plan:** `docs/superpowers/plans/2026-11-25-i18n-architecture-hardening.md`.

## 1. Intent

Narrare speaks three languages and has to be able to speak a fourth without a code change in
five places. Today it cannot, and most of the ways it fails are quiet:

- **Languages are lists in code.** The switcher, the settings cards and the manuscript segment
  each hold `["de", "en", "fr"]`; twenty number words sit in a TypeScript table. The order
  DE|EN|FR is a design contract that one unit test holds (`web/lib/language.test.tsx`,
  "draws the design's order") and no end-to-end test does.
- **A locale code is trusted.** Any JSON file dropped into `i18n/` becomes a language, and an
  unknown tag handed to `Intl` silently resolves to the machine's default locale.
- **Plural messages are unchecked.** Each language carries 49 plural messages. Nothing compares
  them with the categories `Intl.PluralRules` reports, so a language with more categories than
  English can be written as `one/other` and nobody hears of it.
- **Failures reach the reader as English prose.** `web/lib/query.ts` has 57 throw sites in
  five shapes, 31 of them nothing but an English sentence with no status and no code;
  `web/lib/updates.ts` adds one bare status-only failure, currently swallowed or hidden behind
  localized settings copy. Seven faces render raw text. None of the 24 codes the backend emits
  has a shared `errors.*` sentence today; specific capability keys cover some of them, but a
  sentence that speaks of the entity, the interview or the test is wrong on any other face.
- **Every reader downloads every catalog.** The three merged catalogs are in the eager bundle
  whatever language the reader chose.
- **Han-script manuscript text has no declared face**, and the prose carries no `lang`, so the
  browser cannot choose glyphs, hyphenation or a screen reader's voice by the manuscript's
  language.
- **Two columns are too narrow for the tags the registry will carry.** `users.locale` is 8
  characters wide; `novels.language` is 16 with a two-subtag pattern.

The owner decided on 2026-11-26 that every one of these is a requirement. Right-to-left layout
stays out.

## 2. Requirements

- **R1 — One ordered list of languages.** `i18n/registry/locales.json` names every language the
  app carries and the order the switcher, the settings cards and the manuscript segment show
  them in. No list of languages lives in code. A registry entry without a catalog, and a
  central catalog without an entry, stop `just generate`.
- **R2 — Every code is a real tag.** A registry code is a well-formed tag of at most 64
  characters that `Intl` knows and that is written in canonical case. An unknown tag never
  resolves to the machine's default locale.
- **R3 — Number words are catalog text.** The words for one to twenty are twenty central
  catalog keys per language, like every other user-visible string.
- **R4 — The plural rule.** A plural message writes every category its language has, except a
  lone `many` where the language's set is exactly `one/many/other`. A unit test pins the rule
  against the real merged catalogs and names language, key and category. Rule 5 of
  `docs/_shared/CONSTRAINTS.md` says so.
- **R5 — Tags resolve without throwing.** Any browser or stored tag maps onto a registry
  language — the exact code, then the same language and script, then the same language when the
  tag names no script — and keeps its region for dates and numbers. A tag that maps onto
  nothing resolves to the source language. Only the Settings API refuses an unknown stored code.
- **R6 — Both language columns hold any registry code.** `users.locale` and `novels.language`
  are 64 characters wide. A novel's language is any well-formed tag up to that width. Every
  registry code is one. The API does not check it for registry membership.
- **R7 — Codes are typed end to end.** The kernel owns an `ErrorCode` union of every code a
  failure can carry; the generator writes it to TypeScript; a refusal that is not a member does
  not type-check on either side.
- **R8 — Every failure speaks the reader's language.** One `ApiError` shape leaves the API
  client. An exhaustive mapping names a catalog key for every code and every status family. A
  face translates when it renders, never when it catches, so a language switch re-renders a
  failure that is on screen. No face renders the wire's own sentence.
- **R9 — Only the catalog that is read is downloaded.** The source catalog stays in the eager
  bundle. Every other language is one lazy module the generator emits and the shell loads once,
  on demand, through a small store. The first paint waits for the catalog it needs. A chunk
  that cannot be fetched makes the source language active at boot and leaves the active language
  unchanged on a switch.
- **R10 — Manuscript prose carries its language.** The editor's prose element has `lang` set to
  the novel's language, and `:lang()` rules give Chinese, Japanese and Korean text their
  language's own font stacks. Nothing is asserted about glyphs.

## 3. Non-goals

- Right-to-left layout, `dir` attributes, logical CSS.
- A fourth language, and any translation of novel content, demo novels, help articles or AI
  prompts.
- A command palette. The ⌘K chip stays the honest interim it is (#882).
- Server-side `<html lang>` and any templating of the shell. Accepted loss, owner decision: the
  document's language is set client-side, as today.
- Registry membership for `novels.language`. Section 13 states the decision.
- A new check script, hook, gate or mandatory document. The plural rule is a unit test; the
  generator that already runs checks the registry.
- Extending the formality overlay. It stays supported as it is: a sparse, currently empty
  generated map with no control that sets it.
- Structured diagnostic parameters on the wire, such as a line number as a parameter instead of
  a sentence. It needs a wire change per endpoint and stays a candidate for a follow-up.
- Migrating the capability enrichers to `ApiError` — `enrich` in the prompts and the settings
  AI-rules query modules, `refused` in the writing workspace module. The seam reads their
  shapes structurally.
- A new error code or catalog key for the update check's code-less 409. Its faces already
  speak the reader's language; the status fallback covers the failure.

## 4. Anti-goals

- A language that has to be registered anywhere but in the registry.
- A test that passes vacuously. Comparing rendered text with the store's own fallback is the
  failure mode: tests read a language's real catalog, never the store.
- A gate whose verdict depends on the machine it runs on.
- A raw sentence from the backend reaching a face, or a stored message string freezing the
  language a failure is shown in.
- An assertion about rendered glyphs.

## 5. Constraints

- The five standing rules. Rule 5 is amended as R1 and R4 say; the plan's Task 2 pins the text.
  The amendment is the owner's decision of 2026-11-26.
- The governance budget, spec §8. Section 7 carries the three statements for what this design
  adds.
- Lane A: design, plan, one implementer and one reviewer per task, a whole-branch review, new
  E2E legs.
- Rule 2: the only permitted fake is the LLM provider at its boundary. No test intercepts an API
  answer. A failed load is therefore proven by component tests with a rejecting query, and the
  real-refusal faces by the existing prompts and settings legs.
- E2E runs against the Vite dev server (`app/kernel/testing/stack.py`). The lazy modules take
  the same code path there as in the build, which is why this design needs no production-only
  route to test.
- Everything under `web/`, `i18n/`, `app/api/` and `app/kernel/` is a shared surface for the
  affected resolver (`scripts/affected.py`, `SHARED`). CI owes all six E2E suites for every push
  of this branch.

## 6. Approaches considered

### 6.1 Where the list of languages and its order live

- **Catalog filenames (status quo).** No maintenance, but the order is whatever `sorted()`
  gives — EN|DE|FR against a DE|EN|FR contract — and a stray JSON file under `i18n/` becomes a
  language.
- **A list in the generator.** It is the hardcoded list this design removes, moved.
- **An ordered registry file (chosen).** One line per language carries the set and the order.
  The generator, which already loads everything, enforces parity in both directions and writes
  every view from it.

### 6.2 How a non-source catalog reaches the browser

- **Eager, as today.** Rejected by R9.
- **JSON artifacts, a FastAPI route and injection into the shell.** This is the proposed design
  of 2026-11-09; rejected. It moved a German reader's catalog out of a cached asset into the
  uncached shell on every app start. It depended on serving files from the build root, which
  production does not do today (#727, open, major). Its only production path — the templating
  and the route — is driven by no E2E: the suites run against Vite, and the container gate runs
  the chat suite on release pull requests only.
- **Lazy modules through dynamic `import()`, emitted by the generator (chosen).** Only the
  source language is in the eager bundle. Each other language is an immutable, cached asset
  under `/assets/`, which production already serves. Dev, E2E and production take one code
  path. The first paint already waits for the settings read (`web/routes/__root.tsx`), so
  awaiting one small cached chunk adds no flash. Two costs: the 44 test files that import the
  generated catalogs move to a test helper that imports the real catalogs eagerly, and the
  document's `lang` stays client-set.

### 6.3 Where the plural rule is enforced

- **A build-time check script.** Rejected. It would be a fourth check script against a budget
  of three, and its verdict would depend on the runner's ICU version. It also read as wrong on
  day one: French has `one/many/other` under CLDR 48 and none of its 49 plural messages writes
  `many`.
- **Inside the generator.** Rejected. Python's standard library has no plural rules; it would
  need a dependency.
- **A unit test against the merged catalogs (chosen).** It runs in a suite that is already a
  gate, and it pins R4's lone-`many` exception so French stays valid without a maintenance
  table.

### 6.4 How a failure reaches the reader

- **Raw text (status quo).** English prose on a German face.
- **Translating when the failure is caught.** Rejected. The message becomes a string in state
  and freezes the language it was caught in; the language switch is client-side and does not
  reload.
- **Keeping the failure and translating when the face renders (chosen).** The face holds the
  failure object and reads the catalog key during render through `useTranslation`, so a
  language switch re-renders it.
- **How the mapping stays complete.** A hand-written TypeScript list beside a Python test is a
  second list to keep in sync, and a grep over the backend is a check script. The typed kernel
  union plus its generated view makes a code without a sentence a compile error on either side
  — types and generation, the alternatives spec §8 names.

### 6.5 A face for Han-script manuscript text

- **One fixed list of CJK families in the base stacks.** This was the reviewed draft; rejected.
  A list cannot tell Chinese from Japanese glyphs. Simplified-Chinese families before Japanese
  ones give Japanese text Chinese forms wherever both are installed, and Korean was not in the
  list at all. Its E2E could not go red: the runner has no CJK fonts and the project measures
  no glyphs (`.github/workflows/_e2e.yml`).
- **Web font packages.** Rejected. Megabytes per language for text the reader wrote.
- **`lang` on the prose and `:lang()`-scoped stacks (chosen).** The manuscript's own language
  picks the face, assistive technology hears the right language, and the system's own Han fonts
  do the rendering.

### 6.6 Topology

- **One pull request per task.** Rejected. Lane A prescribes one whole-branch review, and
  sequential pull requests would have none.
- **One branch, one pull request, one commit per task (chosen).** Every commit leaves the tree
  green and the app behaving. The coordinator pushes after each green task group, so review
  never meets a wall of commits.

## 7. Governance budget

Spec §8 asks three statements for every new rule, registry, check script, hook, required field
or mandatory document.

**The ordered registry, `i18n/registry/locales.json`.**

1. *Failure prevented:* a language added as a catalog file alone appears in an order nobody
   chose, and a file dropped into `i18n/` becomes a language the app then requires everywhere.
2. *Effort per change:* none for a change that adds no language. Adding one is one registry
   line besides the catalogs it needs anyway. The generator that already runs refuses the line
   without a catalog and the catalog without the line.
3. *Cheaper alternative:* deriving the set from the filenames, as today, and keeping the display
   order in the frontend. Rejected, because that order is a list in code, and a numeric sort key
   inside each catalog is a new required key plus a sort rule.

**The typed `ErrorCode` union and its generated view** (`app/kernel/errors.py`,
`web/lib/generated/errorCodes.ts`).

1. *Failure prevented:* a code the backend emits without a catalog sentence shows a generic line
   forever, and nothing notices.
2. *Effort per change:* a new code is one enum member and one mapping entry. The compiler
   refuses the missing half of either, and `just generate` carries the member to TypeScript.
3. *Cheaper alternative:* none without a second list. A hand-written union plus a Python test is
   that list; a scan of the backend's sources is a check script.

**The plural-rule unit test, `web/lib/catalogRules.test.ts`.**

1. *Failure prevented:* a language with more categories than English, written as `one/other`,
   produces wrong grammar at runtime. `intl-messageformat` falls back to `other` silently.
2. *Effort per change:* none beyond writing the branches a language needs. The test runs in the
   suite that already gates.
3. *Cheaper alternative:* none in the compiler — an ICU message is an opaque string to it. A
   build-time script was rejected in 6.3.

Nothing else is added: no hook, no gate, no required field, no mandatory document. Task reports
stay in `.superpowers/sdd/`, which is git-ignored. The lazy modules and the catalog store are
generated views and ordinary code.

## 8. The locale registry

**File.** `i18n/registry/locales.json` is one object with one key:

```json
{ "locales": ["de", "en", "fr"] }
```

The array is the set of languages in display order. The source language must be a member.

**What a code is.** A tag matching `[a-z]{2,3}(-[A-Za-z0-9]{1,8})*`, at most 64 characters: a
two- or three-letter primary subtag in lowercase, then well-formed subtags in canonical case.
The unit test of section 9 additionally requires that `Intl` knows the code and that
`Intl.getCanonicalLocales` returns it unchanged.

**What the generator does with it** (`scripts/generate_capabilities.py`, which already imports
from `app`):

- It reads the registry and refuses a file that is not such an object, a code that is
  malformed or too long, a duplicate, and a registry without the source locale, naming the
  offender.
- It refuses a registry entry without `i18n/<code>.json` and a central catalog the registry
  does not list.
- `registry_locales(root)` returns the registry order. `locales(root)` keeps its shape — the
  source language first, the rest in registry order — because the generated TypeScript `locales`
  tuple leads with the source and the docs views order by it.
- `typescript_catalogs` writes `localeOrder` beside `locales`:
  `export const localeOrder = ["de", "en", "fr"] as const satisfies readonly Locale[];`

**Who reads the order.** The switcher (`web/lib/language.tsx`), the settings cards
(`app/capabilities/settings/web/SettingsPage.tsx`) and the manuscript segment
(`app/capabilities/writing/web/BookSettings.tsx`) map over `localeOrder`. The three constants
they held are deleted. The manuscript segment lists every registry language: the design has no
flags for user-interface and manuscript languages, because the two sets are the same and a flag
would be a required field nothing reads.

**Adding a language** is one registry line, one central catalog and one file per capability
that owns keys, then `just generate`.

**Removing a language** is the reverse. The generator writes views and does not delete them, so
`web/lib/generated/catalogs/<identifier>.ts` goes by hand; a stale module fails
`just typecheck`, because its catalog imports are gone.

## 9. The plural rule

**Rule.** A plural or ordinal message writes every category `Intl.PluralRules` reports for its
language — except a lone `many`, where the language's complete set is exactly `one/many/other`.
Those languages (French, Portuguese, Spanish, Italian, Catalan today) use `many` for large
numbers only. A language whose set has more, such as Russian or Arabic, writes all of them.
`other` remains the runtime fallback: `intl-messageformat` 12.1.4 reads it when a branch is
missing, which is why the rule is about grammar, not about crashes.

**Where it is pinned.** `web/lib/catalogRules.test.ts` walks every message of every merged
catalog with the parser `intl-messageformat` already carries, and collects
`language:key:category` for each missing branch. It also requires that every registry language
is known to `Intl` and written in canonical case. Its fixtures use languages whose CLDR
categories have been stable for years: Russian, French, Japanese, and English ordinals.

**Rule 5, amended.** The plan's Task 2 replaces the sentence about plural categories with this
one: *"Every catalog is sorted, carries the same keys, and writes every plural category its
language has — except a lone `many` where the language's set is exactly `one/many/other`;
`other` remains the runtime fallback. A missing key is a build error."* `REVIEW.md` and
`CONTRIBUTING.md` say the same in their own words.

## 10. Failures

**The wire does not change.** A refusal stays `{"detail": {"code": …, "detail": …}}` and a
stream still ends with `event: error` and `{"code": …}`.

**Typed codes.** `app/kernel/errors.py` owns `class ErrorCode(StrEnum)` with the 24 codes a
failure can carry: `archive_invalid`, `embedding-mismatch`, `entity-invalid`,
`entity-type-required`, `entity-type-unknown`, `extraction-failed`, `key-unavailable`,
`mode-unknown`, `model-not-found`, `no-context`, `not-found`, `order_mismatch`,
`prompt-refused`, `provider-auth`, `provider-error`, `provider-unavailable`, `rate-limited`,
`relation-duplicate`, `relation-limit`, `relation-target-invalid`, `session-closed`,
`suggestion-mismatch`, `target_not_empty`, `unknown`. Every place that emits one is typed:
`coded_detail(code: ErrorCode, …)`, a second helper `coded(code: ErrorCode, **facts)` for the
refusals that carry their own facts instead of a sentence, `error_frame`, `error_events`,
`error_code` and the interview refusals' `code`. The import-report conflicts
(`app/kernel/interchange/engine.py`) are report entries in a 201 body, not failures, and stay
out. The generator writes the members to `web/lib/generated/errorCodes.ts`:
`ERROR_CODES`, `type ErrorCode` and the guard `isErrorCode`.

**One failure shape.** `web/lib/api/errors.ts` exports `class ApiError extends Error` with
`status: number | null`, `code: ErrorCode | null` and `detail: unknown`. `web/lib/query.ts`
has 57 throw sites in five shapes today; its request-failure sites lose their bare English
messages and carry the response's status, code and detail. `web/lib/updates.ts` uses the same
helper for its non-ok and missing-body branches, without inventing a code.
The root error face binds a code-less failure to its status, so all six copies of the setup-status
`queryFn` — the five capability routes and `app/capabilities/setup/web/setupStatusQuery.ts` —
change together in this task: the thrown failure carries the response's status and any body code and detail,
a 2xx without a body stays a status-less failure (`errors.unexpected`), and each gate has a
503 → `errors.server` test. `SceneVersionConflict` remains its own domain exception. The console
message keeps today's form (`create refused: 422`). A request that never reached the server is
the browser's own `TypeError`, or the `TransportError` this seam wraps it in; `isNetworkFailure`
recognizes both.

**The mapping.** `CODE_KEY: Record<ErrorCode, MessageKey>` is exhaustive by type. Each code
names a sentence in the shared catalog:

| Codes | Key |
| --- | --- |
| `archive_invalid`, `entity-invalid`, `entity-type-required`, `entity-type-unknown`, `mode-unknown`, `relation-duplicate`, `relation-limit`, `relation-target-invalid`, `target_not_empty` | `errors.refused` |
| `order_mismatch`, `suggestion-mismatch` | `errors.changedMeanwhile` |
| `not-found` | `errors.notFound` |
| `session-closed` | `errors.closed` |
| `rate-limited` | `errors.rateLimited` |
| `embedding-mismatch` | `errors.embeddingMismatch` |
| `key-unavailable` | `errors.keyUnavailable` |
| `model-not-found` | `errors.modelNotFound` |
| `provider-auth` | `errors.providerAuth` |
| `provider-unavailable` | `errors.providerUnavailable` |
| `provider-error` | `errors.providerFailed` |
| `prompt-refused` | `errors.promptUnavailable` |
| `no-context` | `errors.noContext` |
| `extraction-failed` | `errors.answerUnreadable` |
| `unknown` | `errors.unexpected` |

A failure without a code is named by its status: 404 `errors.notFound`, 429
`errors.rateLimited`, 5xx `errors.server`, any other status `errors.refused`. A request that
did not reach the server is `errors.network`; anything else is the face's own fallback, or
`errors.unexpected`. The order is code, then status, then network, then fallback.

**Two sentences for one code, by design.** A capability's own face keeps its specific sentence
(`prompts.live.error.rateLimited` speaks of test runs; `knowledge.create.refused.not-found`
speaks of the entity). A generic face — the shelf, the workspace, the root error page — shows
the shared sentence. Each key has one owner.

**Render, not catch.** `useLocalizedError()` returns a function to call while rendering; it is
built on `useTranslation`, so a language switch re-renders the text. The faces keep the failure
object in state or in a ref and never a message string. The seven faces are the root route's
error page, the shelf error, the shelf banner, the workspace error, the new-book dialog, the AI
rules' detail line and the prompt editor's refusal face.

**The update-check faces already speak the reader's language.** `UpdateBanner` shows nothing
when a check fails, `UpdatesSection` renders `settings.update.error`, and release notes are
remote content rather than failure prose. The plan converts `updates.ts` to `ApiError` and pins
`UpdateBanner` and `UpdatesSection` against raw status text and a language switch; release notes
stay untouched. It adds no code, wire field or catalog key for the coded-less 409.

**Accepted trade-offs.** The mono diagnostic lines that showed a failure's own message go; the
console keeps them. The AI rules' 409 delete guard no longer names the models that block the
deletion, nor the remedy, and the prompt editor's refusal no longer names the line of a template
error; both sentences survive only as follow-ups. Where a face shows a stable code in parentheses
(`The test failed (HTTP 503)`), it stays: a code is not prose.

## 11. Catalogs on demand

**Generated shape.** `web/lib/generated/catalogs.ts` keeps `locales`, `localeOrder`, `Locale`,
`Catalog` and the source catalog, and gains:

```ts
export const endonyms: Record<Locale, string>;                       // each language's own name
export const catalogs = { en: en_merged } as const satisfies Record<"en", Catalog>;   // the source, eagerly bundled
export const catalogLoaders: { [L in Exclude<Locale, "en">]: () => Promise<CatalogModule> };
```

`CatalogModule` is `{ locale: Locale; default: Catalog }`. One module per other language lives
at `web/lib/generated/catalogs/<identifier>.ts` and ends with
`export default <merged> satisfies Catalog`, so a missing key is still a compile error.

**The store.** `web/lib/catalog.ts` holds the loaded catalogs and one in-flight promise per
language: `catalogFor(locale)` never throws and never returns `undefined` — an unloaded
language reads the source catalog; `loadCatalog(locale)` resolves immediately for the source
language and otherwise loads the module once; `isLoaded`, `setCatalog` and `resetCatalogs`
complete it.

**When a catalog loads.** Every path that makes a language active awaits its catalog first:

- **Boot.** The root route already waits for the settings read. It then calls
  `hydrateLocale(target)` with the pre-setup mirror's language or the adopted one, and only
  then opens the ready gate. A chunk that cannot be fetched makes the source language active, so
  the page never renders half translated. `hydrateLocale` never rejects. The stored choice stays
  the reader's — the row, the mirror and `chosen` — and a language counts as already selected
  only when it is both the stored choice and the active one.
- **A switch.** `activateLocale(locale)` loads, then applies. If the chunk cannot be fetched
  the active language stays as it was and the call resolves `false`; a click on the row's
  language while the source fallback shows is a retry through `activateLocale`, and takes
  `choose`'s ordinary path only when the retry succeeds. The pre-setup mirror takes the same
  path.
- **`applyLocale`.** It records the choice but announces only a catalog the store holds: a
  language whose catalog is not there leaves the choice stored and makes the source active, so
  the restore after a refused write announces `previous` only when its catalog is in the store
  (for `null`, the browser's language it would resolve to). `adoptServerLocale` announces
  directly at the boot, behind the closed ready gate.

**What this replaces.** The eager table loses every non-source language in the same commit that
makes the runtime read the store. Nothing else changes for the reader: endonyms come from the
generated `endonyms`, and the formality overlay stays where it is.

**Tests.** A setup file puts every merged catalog into the store before each test file, so every
test that switches a language keeps working (125 `applyLocale` call sites at the current
baseline). Tests read a language's real catalog from `web/lib/test/catalogs.ts`, never from the
store — that is the anti-goal of section 4. The helper seeds the source catalog beside the lazy
modules. A test that mocks a module of that bed resets the module registry first and imports what it tests
dynamically, because the setup file has already evaluated those modules.

**Proof.** Component tests cover the store, hydration and a failed switch. A settings E2E leg
records the module requests the dev server answers: German and French are fetched when they are
read, English never. `just build` shows one chunk per non-source language and no German string
outside it. The baseline for the before-and-after sizes is recorded on the fresh branch at
`main`'s tip in Task 0.

**Numbers.** The spec of 2026-11-09 measured the catalog-bearing chunk at 127,660 bytes raw and
32,845 bytes gzip for three languages, and each merged catalog at 26–29 KB raw. Two catalogs
leave the eager graph. Task 11 records what the build actually shows.

## 12. Manuscript fonts and language

**`lang` on the prose.** `SceneEditor` takes an optional `language: string | null` prop and
sets it as the `lang` attribute of the ProseMirror element — the element that already declares
`font-family: var(--font-serif)`. `EditorColumn` and `ZenMode` pass `novel.language`. A novel
without a language leaves the attribute off, and the prose inherits the interface's language.

**Stacks by language.** Three rules follow the base tokens in `web/globals.css`. They are
unlayered and come later in the file, so they win over `:root` on any element whose language
they match, and their custom properties inherit to everything below it:

```css
:lang(zh) { --font-ui: …"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
            --font-serif: …"Songti SC", "SimSun", "Noto Serif CJK SC", "Source Han Serif SC", serif; }
:lang(ja) { --font-ui: …"Hiragino Sans", "Yu Gothic", "Meiryo", "Noto Sans CJK JP", sans-serif;
            --font-serif: …"Yu Mincho", "Hiragino Mincho ProN", "Noto Serif CJK JP", serif; }
:lang(ko) { --font-ui: …"Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans CJK KR", sans-serif;
            --font-serif: …"AppleMyungjo", "Batang", "Noto Serif CJK KR", serif; }
```

Each declaration has three parts, in order: the base token's named families in the base's order
(emoji fonts included, its generic family left out), then the rule's Han families in the table's
order, then the base's generic family last (`sans-serif` for `--font-ui`, `serif` for
`--font-serif`). No generic family may stand before a Han family: a browser resolves a generic
against the system's fallback list and would never consult the later Han families on fontconfig
systems. A Latin word inside the manuscript still reads in the brand face, and every other
language keeps the base stacks and the system's own choice.

**What is proven, and how.** A unit test reads `web/globals.css` as text and pins the three
rules and that the base stacks name no Han family — the precedent is `web/lib/tokens.test.ts`.
Component tests pin the attribute. One writing E2E leg opens a book whose language is Japanese
and asserts `lang="ja"` on the prose. No test asserts a glyph, a computed font or a pixel: the
E2E runner has no CJK font, and the project decided not to measure glyphs.

## 13. Persistence and validation of language tags

**Both columns are 64 characters wide.** One Alembic revision widens `users.locale` from 8 and
`novels.language` from 16. Its `downgrade` raises, as the revisions before it do (ADR-103).

**The Settings API validates membership.** `SettingsUpdate.locale` accepts at most 64
characters and, as today, only a registry code. An unknown stored code is refused with 422.

**A novel's language is any well-formed tag — decided, and not registry membership.** The API
accepts every tag matching `[a-z]{2,3}(-[A-Za-z0-9]{1,8})*` up to 64 characters, with the
primary subtag folded to lowercase. Every registry code is such a tag. The API does not check a
novel's language against the registry, because archives carry languages the app does not
speak: a book written in Italian imports, exports and round-trips although Italian is not a
registry language. A membership check would refuse such archives and break existing imports.
The manuscript segment offers the registry's languages; the API's set is a superset of it.

**The interchange guard follows.** The archive parser has no language regex today; its width
table gives `language` 64 characters, so an export of anything the column holds imports again.
The BCP 47 pattern changes only in `app/capabilities/writing/metadata.py`: it gains several
subtags, digits and up to eight characters per subtag, and keeps refusing a one-letter code, an
underscore, a dangling dash or a word.

## 14. Review focus

The five inputs the requirements imply that a person is most likely to meet:

1. A language switch while a failure is on screen — the failure re-renders in the new language.
2. A catalog chunk that cannot be fetched — the first paint falls back to the source language, a
   switch stays where it was, nothing hangs.
3. A tag the registry does not carry verbatim — `de-AT`, `zh-Hans-CN`, `tlh` — resolves or falls
   back without throwing; only the Settings API refuses.
4. A plural message that skips a category its language requires — refused with language, key
   and category, while French stays valid without `many`.
5. A manuscript in a Han language under a German interface — the prose carries its `lang` and
   reads its own stacks.

## 15. Tasks and pull request

One branch, `feat/i18n-hardening`; one pull request; one commit per task; a whole-branch review
at the end. Every commit leaves the tree green and the app behaving.

| Task | Seam | Commit |
| --- | --- | --- |
| 0 | Design and plan into the repository; the superseded pair marked; the wave's follow-up index issue | `chore(docs)` |
| 1 | The registry; generator parity; `localeOrder` | `refactor(i18n)` |
| 2 | The plural-rule unit test; rule 5, `REVIEW.md`, `CONTRIBUTING.md` | `test(i18n)` |
| 3 | Number words as catalog keys | `refactor(i18n)` |
| 4 | The three surfaces read `localeOrder`; `matchLocale` and `resolveLocale` | `refactor(i18n)` |
| 5 | Both columns 64 wide; the novel language's pattern; the interchange guard | `refactor(db)` |
| 6 | `ErrorCode` in the kernel; the generated TypeScript view | `refactor(kernel)` |
| 7 | `ApiError`, the one helper in `query.ts` and `updates.ts`, the exhaustive mapping, the `errors.*` keys | `refactor(web)` |
| 8 | The seven faces translate at render; update-check regression pins; the real-refusal legs | `fix(i18n)` |
| 9 | One lazy module per language, `catalogLoaders`, `endonyms` | `refactor(i18n)` |
| 10 | The catalog store; the test bed; tests read real catalogs | `refactor(web)` |
| 11 | The runtime reads the store; the eager table shrinks; the E2E and bundle proofs | `perf(i18n)` |
| 12 | `lang` on the prose; `:lang()` stacks; the writing E2E leg | `fix(web)` |

The three groups depend only inside themselves: Tasks 1 to 5 on the registry, Tasks 6 to 8 on
the typed codes, Tasks 9 to 12 on the lazy modules and the store. Task 7 alone edits
`web/lib/query.ts`; the update-check interval fields added by #965 survive that rewrite. The
order above is the order of the plan.

## 16. Left to the builder

- The German and French sentences for the `errors.*` keys are written in the plan. Where a term
  of art differs from the catalog's own — the French word for *prompt*, the German label of the
  AI rules section — the catalog's term wins, and the reviewer reads the three languages side by
  side.
- The French literals the settings E2E leg leans on are copied from the French catalog, as the
  German ones are today.
- How the pre-setup mirror is applied inside `useLanguageChoice` is read from the file; the rule
  is that every path to an active language awaits its catalog.
- The Alembic revision identifier is whatever `just db-revision` issues at execution; the head
  this design was revalidated against is `12fc7ddcec6f`.
