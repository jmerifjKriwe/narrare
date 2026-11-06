# Visual identity and shell chrome — design

Origin: the review of [#587] (follow-up index: prose typography and UI surfaces),
2026-11-06. The owner chose the approaches below; no new follow-up issues are
filed for this work. Three open issues close from it: #573 (the dialog's
off-scale title), #544 (the prompts drift, its diff markers included) and #555
(the platform-blind ⌘K keycap).

The wave is three commits on one branch, one PR: **A** the mechanical fixes,
**B** the visual identity, **C** the shell chrome. A is independent; B and C
touch the same token file and are ordered B before C so the theme conversion
happens once.

[#587]: https://github.com/jmerifjKriwe/narrare/issues/587

## 1. Why

The #587 review left eleven points. Six are mechanical and need no decision
(A). Five are one question in disguise — how much identity the app carries
outside its prose — and its three parts are the type scale (B1), the book
objects (B2) and colour (B3). Two more are shell chrome whose recorded
decisions (no tooltip primitive, system-only dark) are now the thing being
reopened (C1, C2).

The app is typographic on purpose: generated covers, one accent, a compact
scale. The review's finding is not that the decisions were wrong; it is that
the app stopped at the first answer. This wave takes the second one without
adding artwork, a second store, or a seventh primitive.

## 2. Decisions

| Part | Chosen | Rejected, and why |
| --- | --- | --- |
| B1 | +1 step on `text-meta`, `text-label`, `text-body` only: 12 / 13 / 14 px. Titles stay 15 / 20 / 28. | Full +1 (12/13/14/16/21/30): moves the three pinned E2E sizes and the hero for no complaint the review made. Keeping the titles also keeps the prose/UI relationship intact. |
| B2 | Typographic composition keyed to the cover tone, three cover tokens with their own dark values. No files. | Artwork per book: upload, storage, ZIP-export inclusion, import mapping, licensing, backup, and the shelf's identity moves from the app's type to the user's pictures. A generated motif (patterns) reads as decoration without information. |
| B3 | Four area hues used as navigation identity only — the rail entry's icon. | Status colours elsewhere (breaks "state colours surface through Notice"), tinted page grounds (doubles surface maintenance and makes the covers compete). |
| C1 | The rail expands over the page on hover and focus; permanent labels on coarse pointers. | Permanent 168 px (the 48 px column is load-bearing, `IconRail.tsx:62-66`), a native `title` (no touch, unstyled), a tooltip primitive (§12.12 rejects a seventh component). |
| C2 | Tri-state theme (`system` / `light` / `dark`) stored on the user row, `light-dark()` tokens, a local paint hint. | Browser-only storage: paints light then flips on a dark screen, and does not travel. System-only: the request. |

## 3. Goals, non-goals, anti-goals

**Goals.** A shelf whose books look designed rather than tinted; UI text that
survives a long session; four areas distinguishable where they meet; a rail a
newcomer can read; a theme the user owns; the reviewer's mechanical findings
gone without a follow-up list.

**Non-goals.** No new primitives, no artwork pipeline, no second data store,
no per-device theme, no restyle of spacing or radii, no new page other than the
appearance settings page.

**Anti-goals.** Two class vocabularies side by side; a colour that means two
things (area vs action vs state); invented data on a cover; a setting that
outlives the server row as a second source of truth.

## 4. Part A — the mechanical six

### A1 Scale drift

- `web/lib/save.tsx:162` (`text-sm text-danger`) and `:169` (`text-sm text-muted`)
  become `text-meta`. The runhead's chapter title beside them is `text-body`
  (`ChapterEditor.tsx:249`); a save status a step below it is the scale's answer.
- `web/ui/Dialog.tsx:35` `text-lg font-semibold` becomes `text-emph
  font-semibold`. `text-title` is "the page title, one per page" (§8.2); a modal
  is not a page.
- `app/capabilities/prompts/web/PromptsPage.tsx:565` `text-lg font-semibold`
  becomes `text-emph font-semibold`, matching `LanguagePage.tsx:20` and every
  other settings `h2`.

#573 and #544 close from the commit that carries this.

### A2 The palette gets a door

`web/components/TopBar.tsx:65-70` is an `aria-hidden` `<span>`; the palette's
only entry is the key listener in `__root.tsx:77-95`. On a touch device or for a
mouse-only user it is unreachable.

- The chip becomes a `<button type="button">` with a catalog `aria-label`
  ("Befehlspalette öffnen"), the keycap paint and the standard focus ring.
  `Shell` passes `onOpenPalette` to `TopBar`; `setPaletteOpen(true)` is the
  handler (the toggle stays on the keyboard path).
- The glyph comes from a `paletteKey()` helper: `⌘K` on macOS, `Strg K`
  elsewhere. `workspace.shortcutHints` gains a `{key}` placeholder in en/de/fr,
  so the palette footer tells the truth on Linux too. #555 closes here.
- `palette.searchLabel` gains its ellipsis in all three catalogs (A6).

### A3 Leave guards outside the editor

`useBlocker` exists only in `NovelPage.tsx:439`. Two forms with explicit Save
lose typed text silently:

- **Prompt editor** (`PromptsPage.tsx:286` section, `:334-343` textarea). It is
  inline, so closing it discards without a route change. Dirty witness: the
  loaded `detail.effective_content` vs `content`. Guard: a confirm Dialog on
  close (the shell's `Dialog`, the same ask-before-leaving pattern as
  `NovelPage`'s guard, without the async flush) plus `useBlocker` for route
  changes.
- **Provider form** (`ProvidersPanel.tsx:478-514`). Dirty witness: the form
  against `EMPTY_FORM` / the editing profile's values. Guard: `useBlocker` plus
  a confirm on the form's own Cancel.

**Three doors, one predicate.** The guard also covers re-targeting: the prompt
list's Edit buttons stay live while an editor is open (`onEdit` swaps the
target and the load effect resets `content`), and `startEditing(profile)`
replaces a dirty provider form. A dirty form asks before close, before a
re-target and before a route change; the buttons stay enabled so the reason
stays visible.

Pristine forms never ask. The two predicates are pure functions and are pinned
by unit tests; one prompts E2E drives the close-confirm.

### A4 `text-danger`'s scope (a documentation fix, no class change)

The spec's target "`text-danger` = 0 outside `Notice`" (§11) was measured by a
census command that scans `app/capabilities/*/web/*.tsx` and
`web/components/*.tsx` — never `web/ui/` or `web/lib/`. Three legitimate status
lines live in the unmeasured folders: `field.tsx:137` (a field's error),
`JobStatus.tsx:68` (a failed job row), `save.tsx:162` (the save indicator). Each
is `role="alert"`/`role="status"`, none is a notice surface.

The rule is narrowed to what the census measured and the three files are named
as the exemption. Routing them through `Notice` would put `flex items-center
gap-2 px-3 py-2` inside a form field and a runhead — the wrong shape for the
wrong reason.

The prompts diff view is the fourth surface: its markers become `border-success`
(added) and `border-danger` (removed) — `--primary` means an action and must not
also mean an added line — and §11 names the diff view beside the three status
lines. That is #544's other half.

### A5 Technical inputs

`ProvidersPanel.tsx`: profile name, `baseUrl` and `model` get
`spellCheck={false} autoComplete="off"`; the API key keeps `type="password"` and
gets `autoComplete="new-password" spellCheck={false}`. The API key currently has
no `autoComplete`, so password managers may offer to save a one-time secret.

### A6 The ellipsis

`palette.searchLabel` ends with `…` in en, de and fr.

## 5. Part B1 — the scale

`web/globals.css:123-134`:

```
--text-meta:  0.75rem    (was 0.6875rem)
--text-label: 0.8125rem  (was 0.75rem)
--text-body:  0.875rem   (was 0.8125rem)
--text-emph / --text-title / --text-hero unchanged
```

Leading stays attached to the token. What follows from it:

- **No E2E pin moves.** The pinned sizes are hero 28, shelf card 15, page h1 20
  (`test_novels_e2e.py:78-90`, `test_shell_chrome_e2e.py:141`) — all outside the
  three changed steps.
- **Density holds.** Table cells are `h-[26px]` (`Table.tsx:84,92`) and take
  14 px at 1.55 = 21.7 px; the small button is `h-6` with `text-label`
  (13 × 1.45 = 18.9); fields and rows are 28 px.
- **The five light screenshots refresh** (`scripts/screenshots.py`). No
  behaviour changes.
- **Consequence to look at:** label 13 and body 14 are one pixel apart; field
  labels keep `font-medium` (500). The rendered sweep decides whether that reads
  as a hierarchy. If it does not, the fallback is label at 12 (still a +1 on
  meta and body) and it is recorded in the task report — not silently changed.
- **Gate (needs approval, §12):** a unit test that pins the six token values as
  written and sweeps off-scale utilities (`text-sm|text-base|text-lg|text-xl`)
  outside `web/ui/`. #544 and #573 both ask for exactly this gate.

## 6. Part B2 — typographic covers

### Tokens

Six cover tokens with light/dark pairs (via `light-dark()`, see C2), all warm:

| Token | Light | Dark |
| --- | --- | --- |
| `--cover-pale-ground` | `oklch(0.94 0.008 85)` | `oklch(0.30 0.012 85)` |
| `--cover-pale-ink` | `oklch(0.25 0.01 85)` | `oklch(0.90 0.005 85)` |
| `--cover-sepia-ground` | `oklch(0.42 0.09 45)` | `oklch(0.44 0.06 45)` |
| `--cover-sepia-ink` | `oklch(0.98 0.005 85)` | `oklch(0.96 0.01 85)` |
| `--cover-ink-ground` | `oklch(0.25 0.01 85)` | `oklch(0.16 0.01 85)` |
| `--cover-ink-ink` | `oklch(0.98 0.005 85)` | `oklch(0.90 0.005 85)` |

`Cover.tsx` no longer borrows `--primary` / `--foreground` / `--rule`; the dark
"ink" tile is dark and the sepia is desaturated, which is #590's fix. Title ink
on every ground clears 4.5:1 in both themes (decorative, but it is text).

### Composition (deterministic, from the same hash)

- **pale:** no frame; eyebrow top, title bottom-left.
- **sepia:** 1 px inset frame at 5 px + a 5 px spine strip, both in the ink at
  ~35 % / ~18 %; eyebrow top, title bottom-left.
- **ink:** no frame; eyebrow top at 0.6 opacity, title centred vertically (the
  current behaviour).

The eyebrow is `genre` when the book has one, else `language`; uppercase, 8 px,
0.08 em tracking, 0.7 opacity. **No counts on the cover** — the shelf card
already carries chapter and word counts; repeating them is decoration.

The title keeps the 3-line clamp and the serif face. The tile stays
`aria-hidden`: the card link names the book.

### API and tests

`Cover({ title, size, genre?, language? })`; the **three** call sites pass the
fields they already hold: `NovelsPage.tsx:119,349` and
`app/capabilities/setup/web/SetupPage.tsx:139`, where the demo entries carry a
`language` and no genre — the eyebrow falls back to the language there, which
is the first screen a user ever sees. The tile carries
`data-cover-tone="pale|sepia|ink"`; `test_novels_e2e.py:78` moves from the class
selector (`div.bg-rule, div.bg-primary, div.bg-foreground`, which the new tokens
break) to `[data-cover-tone]`. `Cover.test.tsx`'s hash pins stay.

Spec §8.6 gains the composition and the tokens. The census line "`bg-primary` = 0
outside `Button` and `Cover`" tightens to "outside `Button`".

## 7. Part B3 — area hues

Four tokens, light/dark pairs, used in exactly one place: the rail entry's icon
(rest and active). Candidate values, chosen by measurement:

| Area | Light | Dark |
| --- | --- | --- |
| writing | `oklch(0.50 0.10 45)` | `oklch(0.78 0.08 45)` |
| knowledge | `oklch(0.48 0.08 110)` | `oklch(0.76 0.07 110)` |
| chat | `oklch(0.48 0.06 235)` | `oklch(0.76 0.05 235)` |
| settings | `oklch(0.45 0.02 85)` | `oklch(0.74 0.02 85)` |

Requirement: at least 3:1 against `--panel` in both themes (icons are non-text,
so the text threshold does not apply). The values here are the starting point;
the builder measures and adjusts lightness, keeping the hue.

Mapping: Home → writing, `nav` entry id → its id (`chat`, `knowledge`), the
Settings anchor → settings. The active entry keeps the L2 treatment (soft fill,
600) and takes the full-strength hue; at rest the icon takes the same hue.

**Never** on: a button, a link other than the rail, a Notice, a cover, or any
text. A census grep (`area-` utilities outside `IconRail.tsx`) is optional and is
folded into the B1 gate if that is approved.

My call: **no new eyebrows.** The mock showed a coloured "Wissen" eyebrow, but
`/knowledge` has no eyebrow today; adding one only to carry a colour is
decoration without information. The rail is where the four areas are compared.

## 8. Part C1 — the rail

`IconRail.tsx` keeps its 48 px column in the layout; the `<nav>` inside it is
absolutely positioned in a 48 px slot and grows to 168 px on `:hover` and
`:focus-within`, over the page, with `--overlay-shadow` and `z-20`.

- The icon's x stays 12 px in both states (`justify-start`, `pl-1.5`): the
  collapsed 48 px column centres a 24 px icon at 12 px, so the expansion moves
  nothing.
- Labels are always in the DOM, `whitespace-nowrap`, opacity 0 → 1, clipped at
  rest by `overflow-hidden`. The transition is 140 ms, disabled under
  `prefers-reduced-motion`.
- `aria-label` per link stays; the visible label is the same catalog string, so
  no i18n work.
- `(hover: none)`: slot and rail are 168 px at rest, labels visible, no
  transition. A touch tablet gets names; a pointer device keeps the page axis.
- No new primitive, no portal, no JS state — CSS only.

Pins: at rest width 48 and label opacity 0; on hover 168 and 1; after Tab into
the rail 168; in a `has_touch` context 168 at rest; and `main`'s x does not
move across the hover (no layout shift).

## 9. Part C2 — the theme

### Data

`app/kernel/contracts/models.py:44` — `User.theme: Mapped[str | None] =
mapped_column(String(8))`, sibling of `locale`. `None` = follow the system;
values `light`, `dark`. Migration via `just db-revision "add users.theme"`.

`app/capabilities/settings/{schemas,service,router}.py` mirror `locale` with one
deliberate difference: the theme gets **its own write endpoint**,
`PATCH /api/settings/theme`, instead of joining `SettingsUpdate`.
`SettingsUpdate` is present-and-nullable on purpose — `{}` is a client bug, and
a field with a default cannot tell that apart from "hand it back". Two required
fields in one body would force `LanguageSwitcher` to send a theme it does not
own (and the theme control to send a locale it does not own), so a stale read
could clobber the other setting. The new endpoint adds `SettingsThemeUpdate
{ theme: str | None }` and leaves the language contract byte-for-byte intact;
`LanguageSwitcher.tsx` is not touched.

`SettingsRead` gains `theme` (a response field is additive). Read returns
`None` when no user row exists; a write raises `SetupRequiredError` → 409,
exactly as `write_locale` does. `just generate` refreshes
`web/lib/api/schema.d.ts` and `openapi.json`.

### Web

- `web/lib/query.ts`: `useSettingsQuery` returns `{ locale, theme }` (an outage
  still resolves to `{ locale: null, theme: null }`).
- `web/lib/theme.ts`: `applyTheme(theme)` sets or removes
  `document.documentElement.dataset.theme` and writes or removes the hint
  `localStorage["narrare.theme"]`; `adoptServerTheme` is the boot call in
  `__root.tsx`, beside `adoptServerLocale`. The store is free of requests, like
  `locale.ts`.
- `web/index.html`: three lines before the module script read the hint and set
  the attribute. This is the only reason the hint exists: a dark-system user who
  chose light must not see a dark page until the query answers.
- The hint is a cache, never a source: after the settings answer it is
  overwritten, and nothing reads it afterwards.

### CSS

Every colour token becomes `light-dark(<light>, <dark>)`;
`:root { color-scheme: light dark }`, `[data-theme="light"] { color-scheme:
light }`, `[data-theme="dark"] { color-scheme: dark }`. The
`@media (prefers-color-scheme: dark)` token block is deleted — the OS choice is
now what `light-dark()` follows when no attribute is set. `--scrim` and
`--overlay-shadow` stay theme-constant. Native controls keep following
`color-scheme`, as today.

Browser floor: `light-dark()` is Chrome 123+, Safari 17.5+, Firefox 120+ — above
the `oklch` / Tailwind v4 floor this app already has.

### Settings page

A new settings-owned cluster **Darstellung** at `/settings/appearance`:
`SettingsLayout.tsx`'s `CLUSTERS`, a route in `routes.tsx`, and a page with one
`Field` + `Select` (System / Hell / Dunkel) persisted on change through
`PATCH /api/settings/theme`, the way `LanguageSwitcher` persists the language
(apply locally first, restore on refusal, invalidate `["settings"]`). No new
component; no segmented control (that would be a new primitive).

i18n keys in en/de/fr: `settings.clusterAppearance`, `settings.appearance.*`
label, hint and three options.

### Gates

- Backend: a settings test for the default (`None`), the round trip, the
  validator and the no-user case (read `None`, write 409), beside the locale
  tests. The existing `PATCH /api/settings` tests must pass unchanged — that is
  the proof the language contract did not move.
- E2E (`settings` suite): choose Dunkel → reload → `html[data-theme="dark"]` and
  a body background different from light; choose System → the attribute is
  gone. One more case with `color_scheme="dark"` and no stored theme pins the
  system fallback (`data-theme` absent, body dark).
- Screenshots: **two chosen-dark images** (shelf, workspace) shot with
  `color_scheme="light"` and the user row seeded `theme="dark"`. That proves the
  claim the feature makes — the setting beats the system — rather than what the
  media query already did. Dark is unpinned today; this is the first gate it
  gets.

Spec: §8.1 gains the theme law (system is the fallback, the user row is the
source, the paint hint is a cache).

## 10. What changes where

**A.** `web/lib/save.tsx`, `web/ui/Dialog.tsx`,
`app/capabilities/prompts/web/PromptsPage.tsx`, `web/components/TopBar.tsx`,
`web/routes/__root.tsx`, `web/components/Palette.tsx`,
`app/capabilities/settings/web/ProvidersPanel.tsx`, `i18n/{en,de,fr}.json`,
`docs/_shared`-adjacent spec §11, plus the prompt/provider dirty predicates and
their tests.

**B.** `web/globals.css`, `web/ui/Cover.tsx`, `web/components/IconRail.tsx`,
`app/capabilities/writing/web/NovelsPage.tsx`,
`app/capabilities/setup/web/SetupPage.tsx`, `Cover.test.tsx`,
`test_novels_e2e.py`, `assets/screenshots/*`, spec §8.1/§8.2/§8.6/§8.11.

**C.** `app/kernel/contracts/models.py`, a migration,
`app/capabilities/settings/{schemas,service,router}.py` + tests,
`app/capabilities/settings/web/{SettingsLayout,routes,AppearancePage}.tsx`,
`web/lib/{query,theme}.ts`, `web/routes/__root.tsx`, `web/globals.css`,
`web/index.html`, generated API files, `i18n/*`, `scripts/screenshots.py`,
`app/capabilities/settings/e2e/test_settings_e2e.py`, spec §8.1.

## 11. Verification

- `just check`, `just test-frontend`, `just build` after each commit group.
- Backend: `just test-file app/capabilities/settings/tests/<new>.py`, then
  `just verify settings`.
- E2E: `just test-e2e writing`, `knowledge`, `chat`, `settings`, `prompts` —
  the suites the three parts touch. `just verify all` before the merge.
- New cells are written red first: the theme API test, the theme E2E, the rail
  pins, the palette-button E2E, the cover-tone selector, the two dirty
  predicates, the scale pin (if approved).
- The screenshots are re-shot once, after C, in light and dark, and the diff is
  read, not just produced.

## 12. Risks and approvals

1. **Scale gate — NEEDS-APPROVAL (§8).** A new unit test that sweeps off-scale
   utilities is a gate. Failure it prevents: the `text-lg` / `text-sm` drift
   that #544 and #573 both record as uncaught. Effort per future change: none —
   it runs with the existing frontend suite. Cheaper alternative: pin the six
   token values only, no sweep; then the next `text-lg` is invisible again.
2. **Area hues.** Four new tokens and a rule that can be broken. The contrast
   measurement is the gate; if a hue cannot clear 3:1 at an honest lightness,
   the area keeps the neutral ink.
3. **The rail on a coarse pointer** gives up 120 px of the page axis. This is a
   deviation from the desktop layout, recorded, not hidden.
4. **`light-dark()` and the browser floor.** The repository states no floor
   (no `browserslist`; `tsconfig` targets ES2022), and it already requires
   `oklch` and Tailwind v4. `light-dark()` is Chrome 123 / Safari 17.5 /
   Firefox 120 (early-to-mid 2024). The call: **modern browsers only, no
   fallback**, and the floor is written into the spec so the next token can
   assume it. Reversing it means two duplicated token blocks keyed on
   `[data-theme]` — the same behaviour, a worse maintenance shape.
5. **The theme hint** is a client-side cache. If it ever becomes readable as a
   second source, the design is broken: the server row decides.
6. **One PR with a migration.** The migration is additive (`nullable=True`) and
   reversible.

## 13. Sequence

1. **A** — the six fixes, their tests, #544/#573/#555 closed in the commits.
2. **B1** — the three token values; screenshots; the scale pin if approved.
3. **B2** — cover tokens, composition, call sites, the E2E selector, #590 closed.
4. **B3** — area tokens, the rail icon hue, the contrast measurement.
5. **C1** — the rail expansion and its pins.
6. **C2** — model, migration, API, theme module, CSS conversion, settings page,
   E2E, two dark screenshots.

B1 before B2 because the cover composition is sized against the new `text-label`.

## 14. Calls I made (check these while reading)

- `text-danger` stays where it is; the spec's rule is narrowed to the folders
  its census measured.
- Cover eyebrow = genre or language, no counts; the setup demo passes its
  language.
- Area hue on the rail icon only, no new eyebrows.
- The rail expands on coarse pointers permanently rather than inventing a
  tooltip.
- Theme on the user row, hint in `localStorage` as a paint cache.
- The theme writes through its own `PATCH /api/settings/theme`, so
  `SettingsUpdate` and `LanguageSwitcher` do not move.
- A dirty form asks at three doors: close, re-target, navigation.
- Modern browsers only; `light-dark()` with no fallback.
- The two dark screenshots prove chosen dark, not system dark; the system
  fallback is an E2E case.
- No full +1 of the title steps.

## 15. Left to the builder

- The four area hue values, by measurement (hue and intent fixed).
- The cover frame geometry and the eyebrow's exact size.
- The rail's expanded width (168 px is a starting point) and the transition.
- Test file names and where the dirty predicates live.
- Whether the scale sweep lands (approval 1) or only the token pin.
