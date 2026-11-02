# UI System "Werkbank" (B pur) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the app's ad-hoc utility soup with one visual system — tokens, a six-step type scale, six primitives, one icon set — and re-set every surface on it, so the UI reads as a calm professional writing tool with real book objects instead of an admin panel.

**Architecture:** Tokens and the type scale live in `web/globals.css` (the one design surface). Six primitives in `web/ui/` carry the state matrix; capability folders consume them and never re-declare colours, radii or type sizes. A global icon rail plus a place-aware top bar form the shell. Surfaces are re-set one capability at a time, each with its own E2E suite as the gate, and the wave ends with a census sweep that proves the old vocabulary is gone.

**Tech Stack:** React 19, TanStack Router/Query, Tailwind v4 (`@theme inline`), React Aria Components, TipTap, Vite, Playwright (E2E), Vitest.

**Spec:** `docs/superpowers/specs/2026-10-31-narrare-ui-b-pur-design.md (repo-relative)`

## Global Constraints

- **≤3 production files per task.** Generated files (`web/lib/api/openapi.json`, `web/lib/api/schema.d.ts`, `web/lib/generated/*`) and test files do not count.
- **Tokens:** `--background oklch(0.965 0.008 85)`, `--card oklch(1 0 0)`, `--panel oklch(0.99 0.004 85)`, `--soft oklch(0.94 0.012 85)`, `--border oklch(0.9 0.006 85)`, `--rule oklch(0.94 0.008 85)`, `--primary oklch(0.42 0.09 45)`, `--muted oklch(0.53 0.01 85)` in light (AA on the deepened ground, spec §8.1), `--warning oklch(0.54 0.13 75)` in light (R19 — the old 0.6 failed AA on every light surface), `--radius 4px`, `--radius-lg 8px`. Dark counterparts: background `oklch(0.19 0.01 85)`, card `oklch(0.24 0.01 85)`, panel `oklch(0.215 0.01 85)`, soft `oklch(0.28 0.012 85)`, border `oklch(0.32 0.01 85)`, rule `oklch(0.3 0.01 85)`, muted unchanged `oklch(0.62 0.01 85)` — the spec §8.1 table is the authority where this line and it differ.
- **Type scale:** `text-meta` 11/1.45, `text-label` 12/1.45, `text-body` 13/1.55, `text-emph` 15/1.5, `text-title` 20/1.3, `text-hero` 28/1.1. Weights 400/500/600 only.
- **Density:** row 28 px, field 28 px, table row 26 px, label column 128 px, section gap 20 px, inline gap 8 px, icon 16 px.
- **Token laws:** one filled `--primary` per screen (L1); selection is `--soft` + 600, never a filled primary (L2); `--border` for edges, `--rule` for separators (L3); two radii only (L4); no card inside a card (L5).
- **Copy:** en/de/fr in the same commit as the string; German uses **du**; a missing key is a build error.
- **No new dependency.** Icons are inline SVG; no typography plugin; no icon package.
- **Word count rule (one rule, two implementations):** the number of whitespace-separated tokens of the body after `trim()`; an empty body counts 0.
- **Numbers:** formatted with `Intl.NumberFormat(activeLocale())` — `6.843` in de, `6,843` in en.
- **Done gate:** the touched capability's E2E suite green (`just test-e2e <capability>`), plus `just check`, `just test-frontend`, `just build`. No VRT.
- **Git:** conventional commits; `feat`/`fix` carry a `User-visible:` line; no `--no-verify`, no force push.
- **Desktop-first:** target ≥1024 px; nothing may overflow horizontally at 360 px.

## Review Focus

1. **A title of 80+ characters** (`"Echoes of the Thornwall and the Long Winter of the Border Lands"`) in a cover tile, a shelf card, the 224 px rail and the breadcrumb: the expected behaviour is three lines then ellipsis in the tile, one line + ellipsis elsewhere, and no row growing past 28 px.
2. **A novel with 60 chapters:** the rail scrolls inside its own column, is one tab stop with roving `tabindex`, `aria-current` sits on exactly one row, and Up/Down walk the list.
3. **A brand-new book** (no genre, no language, no chapters, empty body): the shelf card and the workspace must show neither `undefined`, `null`, `NaN`, nor a stray separator — and the workspace must say it has no chapters instead of rendering an empty card.
4. **German and French copy 20–35 % longer than English** inside 28 px rows, icon-only buttons and the dock's 384 px: no clipped label, no wrapped row, and every icon-only control has an accessible name.
5. **An unreachable API** on the shelf, on `/knowledge` and mid-chat-stream: a `Notice` with `role="alert"` and a working retry, never the empty state (F14) and never a silent stream (F16).

---

### P1 — Tokens, radii, type scale

**Files:**
- Modify: `web/globals.css`
- Test: none (nothing consumes the new tokens yet; the gate is the untouched E2E suites)

**Interfaces:**
- Produces: CSS custom properties `--soft`, `--rule`, `--radius`, `--radius-lg`; `@theme inline` entries `--color-soft`, `--color-rule`, `--radius-*`, `--text-meta` … `--text-hero`; deepened `--background`.

- [ ] **Step 1:** Replace the `:root` block with the values in Global Constraints, keeping `--focus`, `--success`, `--warning`, `--danger`, `--scrim`, `--overlay-shadow` unchanged, and mirror the six new/changed values in the `prefers-color-scheme: dark` block.
- [ ] **Step 2:** Extend `@theme inline` with `--color-soft`, `--color-rule`, `--radius-control: var(--radius)`, `--radius-surface: var(--radius-lg)` and the six `--text-*` entries with their line heights.
- [ ] **Step 3:** Run `just build`. Expected: PASS; `rg -c 'text-sm' web/globals.css` returns nothing (no page changed yet).
- [ ] **Step 4:** Run `just test-e2e writing`. Expected: PASS — the deepened background changes pixels, not behaviour.
- [ ] **Step 5:** Commit: `feat(ui): one token set with soft/rule surfaces, two radii and a six-step scale` + `User-visible: the page ground is a shade warmer, so white cards read as raised again.`

### P2 — EB Garamond subset for the prose surface

**Files:**
- Create: `web/public/fonts/eb-garamond-latin.woff2`, `web/public/fonts/OFL.txt`
- Modify: `web/globals.css`

**Interfaces:**
- Produces: `font-family: "EB Garamond", Georgia, "Times New Roman", serif` available on `.ProseMirror`.

- [ ] **Step 1:** Fetch the OFL EB Garamond release (v1.x from the upstream repo), then subset:
  `pyftsubset EBGaramond-Regular.ttf --unicodes="U+0020-007E,U+00A0-00FF,U+2013-2014,U+2018-201D,U+2026,U+00AB,U+00BB" --flavor=woff2 --layout-features="kern,liga" --output-file=web/public/fonts/eb-garamond-latin.woff2`
  Expected: a file under 60 KB. Copy the upstream `OFL.txt` beside it.
- [ ] **Step 2:** Add `@font-face` (`font-display: swap`, `font-weight: 400`) and change `.ProseMirror`'s `font-family` to the new stack. Keep `font-size: 1.125rem; line-height: 1.75; max-width: 34rem` (the file's existing values).
- [ ] **Step 3:** Remove the dead `class: "prose"` from `web/ui/markdown-editor.tsx:66` (no typography plugin is installed, so it styles nothing — F27); the `.ProseMirror` rules are the editor's styling.
- [ ] **Step 4:** Run `just build`, then `just test-e2e writing`. Expected: PASS; the editor renders serif, `rg -n 'eb-garamond' web/dist/assets/*.css` finds the URL, and `rg -n 'class: "prose"' web/ui` returns nothing.
- [ ] **Step 5:** Commit: `feat(ui): the prose surface wears the brand serif` + `User-visible: chapter text is set in EB Garamond instead of Georgia.`

### P3 — `Button` and `Field`

**Files:**
- Create: `web/ui/Button.tsx`, `web/ui/field.tsx`
- Test: `web/ui/buttonClasses.test.ts` (pure class matrix — the project allows component tests only in the editor layer, so behaviour is pinned by E2E/axe, the matrix by a unit test)

**Interfaces:**
- Produces:
  `Button({ variant?: "primary"|"secondary"|"ghost"|"icon" = "secondary", size?: "sm"|"md" = "md", icon?, label?, type?, disabled?, onClick?, children? })` — `label` is required when `variant === "icon"` and becomes `aria-label`.
  `buttonClass(variant, size): string` (the exported matrix) and `BUTTON_VARIANTS` / `BUTTON_SIZES`.
  `Field({ label, hint?, error?, id?, children })`, `Input`, `Select`, `Textarea` (native elements with the one focus treatment).

- [ ] **Step 1:** Write the failing test over `buttonClass`: every variant contains `focus-visible:ring-2` and `focus-visible:ring-focus` and none contains `text-sm` or `rounded-md`; `primary` contains `bg-primary text-primary-foreground`; `secondary` and `ghost` and `icon` contain no `bg-primary`; `md` is 28 px (`h-7`) and `sm` is 24 px (`h-6`).
- [ ] **Step 2:** Run `just test-frontend`. Expected: FAIL — `Cannot find module './Button'`.
- [ ] **Step 3:** Implement the matrix exactly: primary `bg-primary text-primary-foreground hover:brightness-95 active:brightness-90`; secondary `border border-border bg-card hover:bg-soft`; ghost `text-muted hover:bg-soft`; icon `grid place-items-center text-muted hover:bg-soft`; all: `rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50`; `md` = `h-7 px-2.5 text-body`, `sm` = `h-6 px-2 text-label`.
- [ ] **Step 4:** `Field` renders `<label>` + control + optional hint/error (`role="alert"` on the error, `aria-describedby` wiring); `Input`/`Select` are `h-7 rounded-[var(--radius)] border border-border bg-card px-2 text-body`, `Textarea` the same with `min-h-7` (it grows — §8.3; a fixed `h-7` would pin multi-line fields to one row), all three with the same focus ring and `disabled:opacity-50` — never `focus:outline-none` with a border change.
- [ ] **Step 5:** Run `just test-frontend` and `just build`. Expected: PASS.
- [ ] **Step 6:** Commit: `feat(ui): Button and Field carry the state matrix` + `User-visible: buttons and inputs now share one hover, focus and disabled look.`

### P4 — `Row` and `Panel`

**Files:**
- Create: `web/ui/Row.tsx`, `web/ui/Panel.tsx`
- Test: `web/ui/rowClasses.test.ts`

**Interfaces:**
- Produces:
  `Row({ as = "button", selected?, current?, leading?, trailing?, href?, onClick?, className?, children })` — `selected` applies `bg-soft` + `font-semibold` + `inset 2px 0 0 var(--primary)`; `current` sets `aria-current="true"`.
  `rowClass(selected: boolean): string` — also the class string for React Aria `GridList.Item` consumers (the entity list).
  `Panel({ title?, actions?, dense?, children })`.

- [ ] **Step 1:** Failing test over `rowClass`: it contains `h-7`, contains no `bg-primary`, no `rounded-md`, no `border-border`; `selected` adds `bg-soft` and `font-semibold`.
- [ ] **Step 2:** Run `just test-frontend`. Expected: FAIL.
- [ ] **Step 3:** Implement `Row` (`h-7 flex items-center gap-2 px-3 text-body`, `--rule` bottom border, `data-selected` styling per L2, `aria-current` only from `current`) and `Panel` (`rounded-[var(--radius-lg)] border border-border bg-card`, header `text-label uppercase tracking-[0.1em] text-muted` on `--rule`).
- [ ] **Step 4:** Run `just test-frontend`, `just build`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(ui): Row and Panel replace stacked bordered buttons` + `User-visible: a selected chapter is a soft row with an edge marker, not a filled brown block.`

### P5 — `Table` and `Notice`

**Files:**
- Create: `web/ui/Table.tsx`, `web/ui/Notice.tsx`
- Test: `web/ui/noticeClasses.test.ts`

**Interfaces:**
- Produces:
  `Table<T>({ columns: {key,label,align?,width?}[], rows: T[], rowKey: (row:T)=>string, dense? })` — a real `<table>`, `--rule` between rows, `tabular-nums` and right alignment for `align="right"`.
  `Notice({ tone: "info"|"warning"|"danger"|"quiet", live?: "status"|"alert"|"none", action?, children })`.
  `noticeClass(tone): string`.

- [ ] **Step 1:** Failing test over `noticeClass`: `danger` contains the danger token and no `border`; `quiet` contains `text-muted`; no tone contains `text-sm`, `rounded-md` or `bg-primary`.
- [ ] **Step 2:** Run `just test-frontend`. Expected: FAIL.
- [ ] **Step 3:** Implement both. `Notice` maps `live` to `role="alert"` / `role="status"` / no role. `Table` renders `<thead>` with `text-meta uppercase tracking-[0.1em] text-muted` and cells at `h-[26px] text-body`.
- [ ] **Step 4:** Run `just test-frontend`, `just build`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(ui): Table and Notice give data and failure one shape each` + `User-visible: errors, empty states and loading share one quiet form instead of red text everywhere.`

### P6 — Icon set

**Files:**
- Create: `web/ui/icons.tsx`
- Test: `web/ui/icons.test.tsx`

**Interfaces:**
- Produces: `icons` (16 entries: `books, write, knowledge, chat, settings, focus, railHide, railShow, close, export, import, search, plus, check, cross, chevronDown`), `IconName`, `Icon({ name, size = 16 })` — inline SVG, `stroke="currentColor"`, `strokeWidth={1.5}`, `aria-hidden="true"` (the accessible name belongs to the control, not the glyph).

- [ ] **Step 1:** Failing test: every name in `icons` renders an `<svg>` with `aria-hidden="true"`, `viewBox="0 0 16 16"` and `width === height === size`.
- [ ] **Step 2:** Run `just test-frontend`. Expected: FAIL.
- [ ] **Step 3:** Draw the sixteen glyphs on a 16×16 grid, no fills, no emoji.
- [ ] **Step 4:** Run `just test-frontend`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(ui): sixteen inline glyphs replace the lone gear` + `User-visible: tools are drawn as icons instead of sentences.`

### P7 — Catalog keys for icon-only controls

**Files:**
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`

**Interfaces:**
- Produces: `shell.navHome`, `shell.navAria` ("Hauptnavigation"), `workspace.railToggle`, `workspace.dockToggle`, `workspace.focusToggle`, `novels.exportAria`, `knowledge.newDocument`, `palette.aria`, `chat.answerReady` (the announcement P15 uses).

- [ ] **Step 1:** Add all nine keys to `en`, then `de` (du-Form), then `fr` in the same commit. Values are one to three words; none repeats an existing key.
- [ ] **Step 2:** Run `just test-frontend` (the catalog test asserts key parity). Expected: PASS.
- [ ] **Step 3:** Commit: `feat(i18n): name the icon-only controls in three languages` + `User-visible: icon buttons announce themselves to screen readers in en, de and fr.`

### P8 — Shell frame: icon rail, page-title hook

**Files:**
- Create: `web/components/IconRail.tsx`, `web/lib/pageTitle.ts`
- Modify: `web/routes/__root.tsx`
- Test: `web/lib/pageTitle.test.tsx`

**Interfaces:**
- Produces:
  `PageTitleProvider` + `usePageTitle(title: string)` (sets `document.title = \`${title} — Narrare\``, publishes the value to the top bar) + `usePageTitleValue()`.
  `IconRail()` — fixed Home (`/`) first, then `nav` from `web/lib/generated/capabilities`, Settings anchored at the bottom; each entry a `Button variant="icon"` with the catalog name; `aria-label` on the `<nav>` from `shell.navAria`.

- [ ] **Step 1:** Failing test: `usePageTitle("Romane")` sets `document.title === "Romane — Narrare"` and restores the previous title on unmount; two providers do not leak.
- [ ] **Step 2:** Run `just test-frontend`. Expected: FAIL.
- [ ] **Step 3:** Implement `pageTitle.ts` and mount `PageTitleProvider` + `IconRail` in `__root.tsx` (rail inside the shell, before `<main>`). `writing` stays `nav: false`; Home is a shell constant pointing at `/`.
- [ ] **Step 4:** Run `just test-frontend`, `just build`, `just test-e2e writing`. Expected: PASS. The top bar still shows its old links — P9 removes them; note this in the task report.
- [ ] **Step 5:** Commit: `feat(shell): a global rail and per-page titles` + `User-visible: every page can be left and re-entered from the rail, and each tab now says where you are.`

### P9 — Top bar becomes place + actions

**Files:**
- Modify: `web/components/TopBar.tsx`
- Test: `app/capabilities/writing/e2e/test_novels_e2e.py`

**Interfaces:**
- Consumes: `usePageTitleValue()` (P8), `Icon`, `Button` (P3, P6), `shell.navAria`.
- Produces: a bar with the breadcrumb (place) on the left, ⌘K hint, Settings icon and `LanguageSwitcher` on the right; **no** capability links (the rail owns navigation).

- [ ] **Step 1:** Add the failing E2E assertion in `test_novels_e2e.py`: on `/`, `expect(page.get_by_role("navigation", name="Hauptnavigation")).to_be_visible()` and `expect(page.get_by_role("link", name="Wissen")).to_have_count(1)` — one entry, in the rail only.
- [ ] **Step 2:** Run `just test-e2e writing`. Expected: FAIL (`2` links today).
- [ ] **Step 3:** Rewrite `TopBar` per the interface; keep the skip link first and the `data-focus="2"` chromeless behaviour.
- [ ] **Step 4:** Run `just test-e2e writing`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(shell): the bar carries the place, not the map` + `User-visible: one navigation instead of two, and the current page is named at the top.`

### P10 — Derived chapter and word counts on `NovelRead`

**Files:**
- Modify: `app/capabilities/writing/schemas.py`, `app/capabilities/writing/repository.py`, `app/capabilities/writing/service.py`
- Test: `app/capabilities/writing/tests/test_novel_counts.py`

**Interfaces:**
- Produces: `NovelRead.chapter_count: int` and `NovelRead.word_count: int` (defaults 0); `list_novels()` returns rows with both filled.

- [ ] **Step 1:** Failing test: a novel with two chapters (bodies `"eins zwei drei"`, `"vier"`) reports `chapter_count == 2` and `word_count == 4`; a novel with no chapters reports `0` and `0`; a chapter with `body == ""` contributes 0.
- [ ] **Step 2:** Run `just test-file app/capabilities/writing/tests/test_novel_counts.py`. Expected: FAIL — unexpected keyword/attribute.
- [ ] **Step 3:** Add a grouped aggregate query in the repository:
  `count(c.id)` and `coalesce(sum(array_length(regexp_split_to_array(btrim(c.body), '\s+'), 1)) filter (where btrim(c.body) <> ''), 0)` grouped by `c.novel_id`; the service joins it onto the rows; the schema declares the two fields with `0` defaults.
- [ ] **Step 4:** Run `just test-file …`, then `just generate` (regenerates `openapi.json`, `schema.d.ts`, `web/lib/generated/*`). Expected: PASS, and `rg -n 'chapter_count' web/lib/api/schema.d.ts` finds it.
- [ ] **Step 5:** Run `just test-e2e writing`. Expected: PASS (the payload only grew).
- [ ] **Step 6:** Commit: `feat(writing): novels report their chapter and word counts` + `User-visible: a book can say how long it is without opening it.`

### P11 — Cover and shelf

**Files:**
- Create: `app/capabilities/writing/web/Cover.tsx`
- Modify: `app/capabilities/writing/web/NovelsPage.tsx`
- Test: `app/capabilities/writing/e2e/test_novels_e2e.py`

**Interfaces:**
- Consumes: `NovelRead.chapter_count`/`word_count` (P10), `Button`, `Row`, `Panel`, `usePageTitle`, `Icon`, `activeLocale()`.
- Produces: `Cover({ title, size = "md" })` — 3:4 tile, three token tones by `hash(title) % 3`, serif lettering, 3-line clamp.

- [ ] **Step 1:** Add the failing E2E assertions: (a) one card per novel with `Kapitel` and `Wörter` (`expect(card).to_contain_text("4 Kapitel")`, `"6.843 Wörter"`); (b) no percentage anywhere (`expect(page.get_by_text("%")).to_have_count(0)`); (c) a novel created with an 80-character title keeps its card height equal to a short-titled card's and its title span satisfies `scrollWidth <= clientWidth + 1` (Review Focus 1); (d) a book with title only renders neither `undefined` nor `null` and no dangling separator (Review Focus 3).
- [ ] **Step 2:** Run `just test-e2e writing`. Expected: FAIL on (a)–(c).
- [ ] **Step 3:** Implement `Cover`: 3:4 tile, tone `hash(title) % 3` over the three token tones, serif lettering, 3-line clamp with `overflow-hidden`, `aria-hidden` on the tile's text when the card already names the book.
- [ ] **Step 4:** Re-set `NovelsPage`: hero card (cover + title + genre + last touched + one primary "Weiter"), grid 3/2/1, `text-title` heading, "+ Neues Buch" primary, import secondary, `usePageTitle(t("novels.heading"))`; optional fields render conditionally, never as empty labels.
- [ ] **Step 5:** Replace the hand-built skeleton with `Notice tone="quiet" live="status"` plus three skeleton rows on `--rule`, and gate the pulse on `motion-safe:` so `prefers-reduced-motion: reduce` stops it (F24).
- [ ] **Step 6:** Run `just test-e2e writing`, `just test-frontend`, `just build`. Expected: PASS.
- [ ] **Step 7:** Commit: `feat(writing): the shelf shows books, not rows` + `User-visible: the start page shows covers, length and last-touched per book, with one clear way back in.`

### P12 — Workspace

**Files:**
- Modify: `app/capabilities/writing/web/NovelPage.tsx`, `app/capabilities/writing/web/ChapterEditor.tsx`
- Create: `web/lib/words.ts`
- Test: `app/capabilities/writing/e2e/test_chapters_e2e.py`, `test_viewport_e2e.py`, `test_focus_e2e.py`

**Interfaces:**
- Consumes: `Row`, `Button`, `Icon`, `Notice`, `Panel`, `usePageTitle`.
- Produces: `countWords(markdown: string): number` in `web/lib/words.ts` (the shared rule); a workspace with one container width (max 1152), rail 224, dock 384, `.ProseMirror` measure fixed at 544.

- [ ] **Step 1:** Add the failing assertions: (a) the active chapter carries `aria-current="true"` and no `aria-pressed`; (b) with the dock open, `.ProseMirror` width is 544 ±1 at 1280×800; (c) the runhead shows `Buch · Kapitel` and the save state, the footer shows `2.107 Wörter` and `Kapitel 2 von 4`; (d) at focus depth 2 both are hidden; (e) the rail is one tab stop (`[aria-current]` row has `tabindex="0"`, every other row `-1`) and its list has `overflow-y: auto` (Review Focus 2); (f) a book with no chapters shows the empty state, not an empty card (Review Focus 3).
- [ ] **Step 2:** Run `just test-e2e writing`. Expected: FAIL on all six.
- [ ] **Step 3:** Re-set the rail: `Row` per chapter (28 px, word count trailing via `countWords`), `aria-current`, roving `tabindex` + Up/Down, collapse control moved to the toolbar band, ellipsis on the title.
- [ ] **Step 4:** Re-set the toolbar as one `gap` group of `Button variant="icon"`; replace `window.confirm` with a React Aria dialog (F21); add the depth-2 hint line (F23).
- [ ] **Step 5:** Give the below-1024 rail and dock a scrim and focus containment, or stop them being overlays (F22) — either satisfies §8.9; record the choice in the task report.
- [ ] **Step 6:** Rewrite `ChapterEditor`'s frame: runhead (book · chapter left, `SaveIndicator` right), footer (words + position), both hidden at depth 2; keep the editor card.
- [ ] **Step 7:** Fix the container: one `max-w-[1152px]` in both states; the editor column keeps 544 and centres.
- [ ] **Step 8:** Run `just test-e2e writing`, `just test-e2e chat` (dock tabs), `just test-frontend`, `just build`. Expected: PASS — rewrite the `aria-pressed` assertions in `test_autosave_e2e.py:112,221,238` and `test_chapters_e2e.py:380,383` to `aria-current` in this task.
- [ ] **Step 9:** Commit: `feat(writing): the workbench keeps its measure and names its chapter` + `User-visible: opening a panel no longer reflows the text, and the chapter list shows length and current position.`

### P13 — Knowledge dock

**Files:**
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx`, `app/capabilities/knowledge/web/EntityRelationsSection.tsx`
- Delete: `app/capabilities/knowledge/web/buttons.ts` (its imports move to `Button`)
- Test: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py`, `test_entity_depth_e2e.py`

**Interfaces:**
- Consumes: `Button`, `Field`, `Table`, `Notice`, `rowClass` (the `GridList.Item` styling from P4), `Icon`.
- Produces: relations rendered as two `Table`s ("Verweist auf", "Wird verwiesen von") with columns Typ / Ziel — **no chapter column** (no data).

- [ ] **Step 1:** Add the failing assertions: `expect(page.get_by_role("table")).to_have_count(2)` inside the relations section; the entity list still exposes `gridcell` roles (`expect(page.get_by_role("gridcell")).to_have_count(n)`).
- [ ] **Step 2:** Run `just test-e2e knowledge`. Expected: FAIL on the table count, PASS on gridcell (roles preserved).
- [ ] **Step 3:** Re-set `EntitiesPanel` on `rowClass` + `Field` + `Notice` (loading/empty/error); re-set `EntityRelationsSection` as two tables with a `Panel` header, the add/edit forms on `Field`, and delete-confirmation as a dialog; delete `buttons.ts` and import `Button` everywhere it was used.
- [ ] **Step 4:** Run `just test-e2e knowledge`, `just build`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(knowledge): relations are a table, not a sentence with arrows` + `User-visible: an entity's links are readable at a glance, outgoing and incoming separately.`

### P14 — Knowledge page: documents, search, review queue

**Files:**
- Modify: `app/capabilities/knowledge/web/KnowledgePage.tsx`, `app/capabilities/knowledge/web/ExtractionPanel.tsx`, `app/capabilities/knowledge/web/ChecksPanel.tsx`
- Test: `app/capabilities/knowledge/e2e/test_knowledge_e2e.py`, `test_extraction_e2e.py`, `test_consistency_e2e.py`
- Test (unit): `app/capabilities/knowledge/web/documents.test.ts`

**Interfaces:**
- Consumes: `Panel`, `Row`, `Field`, `Notice`, `Button`, `Table`.
- Produces: `readDocuments(result: { data?: KnowledgeDocument[]; response: { ok: boolean } }): { kind: "ok"; documents: KnowledgeDocument[] } | { kind: "failed" }` in `KnowledgePage.tsx` (exported for the unit test).

- [ ] **Step 1:** Failing unit test: `readDocuments` returns `kind: "failed"` for a non-ok response with no data, and `kind: "ok"` with `[]` for an ok response with no data. Failing E2E: the documents area is a `Panel` list with exactly one "+ Dokument" control, and a refused re-embed shows a `Notice tone="danger"`.
- [ ] **Step 2:** Run `just test-frontend` and `just test-e2e knowledge`. Expected: FAIL.
- [ ] **Step 3:** Re-set `KnowledgePage`: one search `Field` at the top, documents as a `Panel` list with one "+ Dokument" dialog, hits as `Row`s with the snippet, and the four states through `Notice` (F14, F15 — no silent `return`, no empty state on failure).
- [ ] **Step 4:** Re-set `ExtractionPanel` (job row + progress rule + proposal rows, expanding form) and `ChecksPanel` (findings as rows with `Button`s).
- [ ] **Step 5:** Run `just test-frontend`, `just test-e2e knowledge`, `just build`. Expected: PASS.
- [ ] **Step 6:** Commit: `feat(knowledge): documents, search and review share one surface` + `User-visible: a failed knowledge load says so instead of claiming the library is empty.`

### P15 — Chat and prompts

**Files:**
- Modify: `app/capabilities/chat/web/ChatPanel.tsx`, `app/capabilities/prompts/web/PromptsPage.tsx`, `web/ui/ProposalCard.tsx`
- Test: `app/capabilities/chat/e2e/test_chat_e2e.py`, `app/capabilities/prompts/e2e/test_prompts_e2e.py`

**Interfaces:**
- Consumes: `Button`, `Field`, `Row`, `Panel`, `Notice`, `Icon`, `announce` from `web/lib/announce.ts`, `chat.answerReady` (P7).
- Produces: the streamed answer is announced once, on completion, with `t("chat.answerReady")` — not per delta.

- [ ] **Step 1:** Add the failing assertions: after a streamed answer, the live announcer contains the answer's first six words; the ask button keeps a non-transparent `bg-primary`; the answer still computes `white-space: pre-wrap`.
- [ ] **Step 2:** Run `just test-e2e chat`. Expected: FAIL on the announcement only.
- [ ] **Step 3:** Call `announce(...)` once when the stream ends without error (F16); re-set the panel on `Field`/`Button`/`Notice`; sources as `Row`s.
- [ ] **Step 4:** Re-set `PromptsPage` on `Panel` + `Field` + `Button` (the body editor keeps `MarkdownEditor`).
- [ ] **Step 5:** Run `just test-e2e chat`, `just test-e2e prompts`, `just build`. Expected: PASS.
- [ ] **Step 6:** Commit: `feat(chat): a finished answer is spoken once` + `User-visible: screen readers announce the answer when it is complete, and chat and prompts look like the rest of the app.`

### P16 — Settings and setup

**Files:**
- Modify: `app/capabilities/settings/web/SettingsLayout.tsx`, `app/capabilities/settings/web/ProvidersPanel.tsx`, `app/capabilities/setup/web/SetupPage.tsx`
- Test: `app/capabilities/settings/e2e/test_settings_e2e.py`, `test_profiles_e2e.py`, `app/capabilities/setup/e2e/test_setup_e2e.py`

**Interfaces:**
- Consumes: `Row`, `Field`, `Panel`, `Button`, `Notice`, `Cover`.
- Produces: settings as nav 200 + content 56 rem (max 1000) on the 128 px label grid; setup card max 448 with no `min-h-screen` and covers on the demo entries.

- [ ] **Step 1:** Add the failing assertions: the setup page does not scroll at 1280×800 (`expect(page.evaluate("document.scrollingElement.scrollHeight <= window.innerHeight")).to_be_truthy()`); the settings cluster nav is a list of `Row`s (`get_by_role("navigation")` contains `link` per cluster); each provider row exposes its label and control in one row (28 px).
- [ ] **Step 2:** Run `just test-e2e settings` and `just test-e2e setup`. Expected: FAIL on the setup scroll assertion.
- [ ] **Step 3:** Re-set `SettingsLayout` (vertical `Row` nav) and `ProvidersPanel` (label grid 128 px, one primary action per sub-page, `Notice` for save failures).
- [ ] **Step 4:** Re-set `SetupPage`: drop `min-h-screen`, keep the top bar (language control), demo entries with `Cover`.
- [ ] **Step 5:** Run both suites, `just build`. Expected: PASS.
- [ ] **Step 6:** Commit: `feat(settings): one grid for every provider row` + `User-visible: settings and first run stop scrolling on a laptop screen and share the app's row rhythm.`

### P17 — Palette and the old `ui/` vocabulary

**Files:**
- Modify: `web/components/Palette.tsx`, `web/ui/JobStatus.tsx`
- Delete: `web/ui/TextField.tsx` (all consumers moved to `Field` in P11–P16)
- Test: `web/components/Palette.test.tsx`, `app/capabilities/knowledge/e2e/test_extraction_e2e.py`

**Interfaces:**
- Consumes: `Row` (plain, not React Aria — the palette's focus management stays as built), `Field`, `Notice`, `Button`.
- Produces: palette rows at 28 px on `--rule`, group labels in `text-label`, no `text-sm`/`rounded-md` left in the file.

- [ ] **Step 1:** Failing test: palette rows are 28 px and the selected row keeps its existing `aria-selected`/`data-selected` contract; `JobStatus`'s progress bar is a 1 px rule with a 2 px fill and carries `role="progressbar"` with `aria-valuenow`.
- [ ] **Step 2:** Run `just test-frontend`. Expected: FAIL.
- [ ] **Step 3:** Re-set both files; delete `TextField.tsx` and prove nothing imports it (`rg -n 'TextField' web app/capabilities` returns nothing).
- [ ] **Step 4:** Run `just test-frontend`, `just test-e2e knowledge`, `just test-e2e writing`, `just build`. Expected: PASS.
- [ ] **Step 5:** Commit: `refactor(ui): the last old-vocabulary components join the system` + `User-visible: the command palette and job progress match the rest of the app.`

### P18 — Census, E2E sweep, follow-up issues

**Files:**
- Test: all suites; no production files

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1:** Run the census and record the numbers in the task report:

```
rg -o --no-filename 'className="[^"]*"' app/capabilities/*/web/*.tsx web/components/*.tsx \
  | sed 's/className="//;s/"$//' | tr ' ' '\n' | sort | uniq -c | sort -rn
```

  Targets in `app/capabilities/*/web/` and `web/components/`: `text-sm` 0, `bg-primary` 0 (outside `Button` and `Cover` — a cover's sepia ground is an object surface, spec §8.6), `border-border` 0, `rounded-md` 0, `rounded-lg` 0, `text-danger` 0, `ml-`/`mr-` between siblings 0. `text-sm` may survive only in `web/ui/`.
- [ ] **Step 2:** Run `just verify all`. Expected: PASS. Any red is fixed here, not deferred.
- [ ] **Step 3:** Re-run the five Review Focus inputs by hand against the running app (long title, 60 chapters, empty book, de/fr copy, outage) and record the observation for each in the task report.
- [ ] **Step 4:** File one GitHub issue per finding that survived, label `follow-up`, under the wave's index issue; close each finding this wave fixed with `Closes #n` in its own commit.
- [ ] **Step 5:** Commit: `chore(ui): the census proves the old vocabulary is gone` + `User-visible: the whole app now speaks one visual language.`
