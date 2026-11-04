# Narrare v2 — UI system: Werkbank (B pur)

**Date:** 2026-10-31 · **Status:** draft for owner approval · **Owner decision:**
B pur, chosen twice in the design dialogue (2026-10-31), the second time with the
A+B hybrid rendered beside it.

**Authority:** implements the web frontend under
`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` (ADR-100).
Where the two disagree, that document wins; this one governs the visual system and
the surfaces it re-sets. It supersedes the *visual* decisions of
`2026-10-22-frontend-design.md` §5.1 and §5.7 (tokens, `ui/` layer, start page) and
leaves its behaviour decisions untouched.

**Design dialogue:** this session, 2026-10-31. Three directions were drawn and
compared across five screens (A Manuskript, B Werkbank, C Atelier), then B and the
hybrid were drawn on the same four hard screens (knowledge with relations, review
queue, palette, states). C was dropped by the owner after the first comparison.

---

## 1. Intent and why

The owner's complaint is not colour: the palette is fine, the *surface* is wrong.
Measured in the code, the whole UI is six utilities repeated about five hundred
times — 176 × `text-sm`, 59 × `border-border`, 56 × `border`, 47 × `rounded-md`,
43 × `text-danger`, 29 × `bg-card`, 10 × `bg-primary` — with one shadow, one icon
(⚙) and one typographic idea (a serif inside the editor). Every page is the same
`mx-auto max-w-2xl` column. Nothing in the app is a book: the shelf is a list of
bordered rows, the continue-hero is a card with a text link, chapters are stacked
buttons, and the active chapter is a 56 px solid sepia block.

The product is a local-first, AI-assisted writing tool. Its chrome should be a
quiet professional tool; its *objects* — books, chapters, entities, proposals —
should carry the identity. B pur does exactly that: it invests in density,
controls, state and book objects, and keeps the frame still.

## 2. What the owner decided, and what that rules out

Chosen: **B pur** — a dense, calm application shell. Cards, panels, chips and
filled primary buttons stay; the book identity lives in generated covers, a
chapter index with word counts, a real toolbar and a proper state vocabulary.

Ruled out by that choice, and not to be reintroduced without a new decision:

- A's paper-and-ink register (hairline rows instead of cards, serif headings,
  underline-only fields) as the *general* idiom.
- C's editorial layout (display serif, sepia bands, asymmetric pages).
- A hybrid in which the app's surfaces are paper: the owner saw it and chose B.

Two exceptions were put to the owner and are recorded as designer calls in §10:
prose keeps a serif face, and the editor surface stays a card (as drawn in B).

## 3. Goals

- One visual vocabulary: every page is composed from six primitives and the token
  set, so a new page cannot invent a seventh button.
- Density as a law, not a taste: row 28, field 28, table row 26, label column 128,
  section gap 20, icon 16.
- Book objects in the UI: deterministic covers, a chapter index with word counts
  in the workspace, and per-book metadata on the shelf — genre, language, last
  touched, plus chapter and word counts from the derived aggregate (T5b).
- One navigation (the icon rail) and one place indicator (the top bar).
- Every state the product already honours — outage, empty, refresh failure,
  unsaved, job running — expressed by one primitive instead of hand-built markup.
- Measurable: the census that produced the diagnosis becomes the acceptance test.

## 4. Non-goals

- No mobile design (the phone is not a target; 360 px must merely not break).
- No manual dark-mode toggle; the system decides.
- No new dependency: no icon package, no typography plugin, no UI kit.
- No visual regression testing (deleted by the frontend spec; stays deleted).
- No new product features: word counts are derived from existing data; no target
  word count, no reading progress, no covers as uploads.
- No change to behaviour contracts: URL-as-state, autosave, leave guard, ghost
  text, the four honesty states, the keyboard contract.

## 5. Anti-goals

- A second palette or per-capability styling. Tokens stay the one design surface.
- Decorative badges, chips as ornaments, gradients as identity.
- Cards inside cards; a panel that exists only to hold one line.
- Icons without accessible names; icon-only controls whose meaning lives in a
  `title` attribute alone.
- A restyle that leaves the old classNames in place "for now".

## 6. Constraints (binding)

- Standing rules: `docs/_shared/CONSTRAINTS.md` — one capability one folder, no
  capability imports, shell is the only shared point, en/de/fr, green E2E is the
  done gate, governance budget (this design adds no gate, no hook, no registry).
- Capability `web/` folders carry utilities only, never a palette
  (`web/globals.css` states this; it stays true).
- Generated client only; no hand-written API types.
- Each task touches ≤3 production files (owner's reviewability rule); the wave is
  therefore ~11 tasks, not one.
- E2E stays the definition of done; a behaviour-changing task rewrites the E2E it
  changes, in the same task.
- Desktop-first: the layout target is ≥1024 px; below it panels overlay and nothing
  may overflow horizontally at 360 px.

## 7. Approaches considered

| # | Direction | What it trades | Verdict |
|---|---|---|---|
| A | **Manuskript** — paper ground, hairline rules, serif headings and values, underline fields, no cards | Strongest fit for a book; but forms become registers with no visible controls, every dense screen costs ~40 % more height, and the idiom fights settings, providers and prompts | Rejected by owner (seen on 3 screens, then on settings) |
| B | **Werkbank** — app shell with icon rail, cards, panels, chips, real controls, dense rows, covers | Cheapest and most familiar; risks the "admin panel" reading it is meant to fix — identity must come from objects and discipline, not from the frame | **Chosen** |
| C | **Atelier** — display serif, asymmetric editorial layout, colour as material | Highest identity, highest cost, breaks on dense pages | Rejected by owner after the first comparison |
| AB | **Hybrid** — A's ground and type with B's mechanics (28 px controls, grid rows, tabular numbers), no cards | Keeps the writing surface literary and the dense pages usable; needs two surface idioms in one app | Rejected by owner (drawn on the same four screens as B) |

Why B can work despite being the familiar vocabulary: the current UI is B *without*
the system — no scale, no density, no primitives, no book objects, and sepia used
as a 100 % fill for selection. B pur fixes those four things. If it does not, the
original complaint returns; §9's census is what proves it did.

## 8. The design

### 8.1 Tokens (`web/globals.css`, the one design surface)

| Token | Light | Dark | Role |
|---|---|---|---|
| `--background` | `oklch(0.965 0.008 85)` (was 0.985/0.005) | `oklch(0.19 0.01 85)` | page ground; one step deeper so `--card` separates |
| `--card` | `oklch(1 0 0)` | `oklch(0.24 0.01 85)` | raised content: cards, panels with content |
| `--panel` | `oklch(0.99 0.004 85)` | `oklch(0.215 0.01 85)` | chrome: top bar, icon rail, chapter rail, dock |
| `--soft` **new** | `oklch(0.94 0.012 85)` | `oklch(0.28 0.012 85)` | selection and hover fill (never primary) |
| `--muted` | `oklch(0.53 0.01 85)` (was 0.55) | `oklch(0.62 0.01 85)` (unchanged) | secondary text. Deepened in light mode because the deepened ground dropped the old value to 4.39:1 — below WCAG AA; the new pair measures ≈4.8:1. Found in T1 when axe failed 24 E2E tests; muted-on-ground is a legitimate app-wide combination, so the token moves, not two elements |
| `--border` | `oklch(0.9 0.006 85)` | `oklch(0.32 0.01 85)` | surface and control edges |
| `--rule` **new** | `oklch(0.94 0.008 85)` | `oklch(0.3 0.01 85)` | separators inside content: table rows, list rows, panel headers |
| `--primary` | `oklch(0.42 0.09 45)` | `oklch(0.72 0.1 60)` | the one primary action |
| `--focus` | unchanged | unchanged | the focus ring, everywhere |
| `--success` / `--danger` | unchanged | unchanged | states, through `Notice` only |
| `--warning` | `oklch(0.54 0.13 75)` (was 0.6) | unchanged | states, through `Notice` only. Deepened in light mode: the old value measured 3.63:1 on the page ground and 4.02:1 on a card — below AA on every light surface, so `tone="warning"` was unusable. The new value measures 4.64 / 5.14 / 5.01 on ground / card / panel. Found in T3's review; no consumer existed yet, so nothing else moved |
| `--radius` **new** | `4px` | — | controls: buttons, fields, rows |
| `--radius-lg` **new** | `8px` | — | surfaces: cards, panels, dialogs |
| `--scrim`, `--overlay-shadow` | unchanged | — | overlays only |

Token laws:

- **L1** A filled `--primary` appears at most once per screen (the primary
  action — interactive controls only; a cover's ground is an object surface, not
  an action, and is governed by §8.6).
- **L2** Selection is `--soft` + weight 600, optionally a 2 px `--primary` edge.
  A selected row is never a filled primary block. This alone removes the rail's
  shouting.
- **L3** `--border` for edges, `--rule` for separators. A table never uses
  `--border` between rows.
- **L4** Two radii, no others. `rounded-full` only for filter pills and avatars.
- **L5** A card never sits inside a card; `--panel` never contains `--card` content
  except in overlays.

### 8.2 Type scale (`@theme inline`, so `text-meta` … `text-hero` exist)

| Token | Size / line | Use |
|---|---|---|
| `text-meta` | 11 px / 1.45 | counts, keyboard hints, timestamps, table headers |
| `text-label` | 12 px / 1.45 | field labels, group eyebrows and panel headers (uppercase + 0.1em tracking) |
| `text-body` | 13 px / 1.55 | all UI text, table cells, list rows |
| `text-emph` | 15 px / 1.5, 600 | card titles, section titles |
| `text-title` | 20 px / 1.3, 600 | the page title, one per page |
| `text-hero` | 28 px / 1.1, 600 | the continue-hero's book title and numerals only |

Weights: 400, 500, 600. Nothing else. Tracking: `-0.01em` on `text-title` and
`text-hero`, `0.1em` on uppercase labels, none elsewhere.

Prose (the editor only): EB Garamond 600 for the chapter heading, EB Garamond 400
at 18 px / 1.75 for the body (the file's existing value; an earlier draft said 1.72, which never existed), measure 34 rem (544 px). The font ships as a
self-hosted subset (~50 KB, already a follow-up issue); until it lands, the
existing Georgia stack is the fallback and nothing else changes.

### 8.3 Density law

```
row          28 px   (chapter rows, entity rows, palette rows, list rows)
field        28 px   (input, select, textarea minimum; textarea grows)
table row    26 px
label column 128 px  (settings rows, form grids)
section gap  20 px
inline gap   8 px
icon         16 px, stroke 1.5
panel padding 10 px / 12 px
```

No element may be taller than its content requires. Vertical air is a consequence
of grouping, never a style.

### 8.4 Primitives (`web/ui/`, six)

Each carries a state matrix — rest / hover / active / focus-visible / disabled /
selected — and is the only place its utilities appear.

| Primitive | API | Notes |
|---|---|---|
| `Button` | `variant: primary \| secondary \| ghost \| icon`, `size: sm(24) \| md(28)`, optional `icon`, `label` | `icon` requires an accessible name (catalog key or `label`); `title` alone is not enough |
| `Field` | `label`, `hint`, `error`, `children` = `Input \| Select \| Textarea` | one focus treatment: `ring-2 ring-focus`; never `focus:outline-none` with a border change |
| `Row` | `as: button \| a \| div`, `selected`, `leading`, `trailing` | 28 px; selected = L2. A **visual** primitive: the chapter rail and palette use it directly (plain elements today, no role change), the entity list keeps its React Aria `GridList` and applies the same token classes to its items — buying behaviour instead of rebuilding it |
| `Panel` | `title?`, `actions?`, `dense?`, `children` | 8 px radius, `--border`, header on `--rule` |
| `Table` | `columns`, `rows`, `dense` | a real `<table>`; tabular numerals right-aligned; `--rule` between rows |
| `Notice` | `tone: info \| warning \| danger \| quiet`, `action?`, `live: status \| alert \| none` | the only error/empty/loading vocabulary |

No `Tooltip` primitive: an icon-only control gets its accessible name from the
catalog (`aria-label`), which satisfies the anti-goal; a visible hover tooltip is
not required and would be a seventh component.

Spacing rule (checked, not a primitive): capability folders carry no `ml-*`,
`mr-*`, `mt-*` or `mb-*` between sibling controls. Groups use `gap`. This is the
rule that kills the toolbar's `ml-3` chain.

### 8.5 Icons (`web/ui/icons.tsx`, inline SVG, no dependency)

16 icons at 16 px, stroke 1.5, currentColor: books, write, knowledge, chat,
settings, focus, rail-hide, rail-show, close, export, import, search, plus, check,
cross, chevron-down. Replaces the ⚙ glyph (which renders as an emoji on some
platforms). Every icon-only control gets a catalog key in en/de/fr.

### 8.6 Covers

Generated, deterministic, no files: a cover is a rounded 3:4 tile whose ground is
one of three token-derived tones — sepia (`--primary`), ink (dark,
foreground-derived), pale (`--rule`-derived) — chosen by a stable hash of the
title; the title is set in the serif face on the tile, 3 lines, ellipsis (the
clamp the shelf pins; an earlier draft said 2). Genre and
language do not affect the tone. No fourth tone, no gradients beyond a single
inner shade, no uploaded artwork. Three tones are enough for a shelf of ten books;
a rainbow is not.

### 8.7 Surfaces

The shell frame is global: the **icon rail** is shell chrome on every route, the
**top bar** carries the place (breadcrumb), ⌘K, settings and the language control.
Rail entries, top to bottom: a fixed Home (the shelf, `/`), then the generated
`nav` (chat, knowledge), then Settings anchored at the bottom. `writing` stays
`nav: false` — the shelf *is* home, not a destination — so no `capability.yaml`
change and no `just generate` work enters this wave. The per-page back links
(`nav.back`, `settings.back`) stay: they are the breadcrumb's pointer twin, and
six E2E suites click them.

Page titles: a shell hook `usePageTitle(key, params?)` sets `document.title` to
`<page> — Narrare`; every page calls it once, and a data-driven page passes its own
string (the workspace passes the book title). The page's `h1` stays in the page
body — the E2E assert `heading` with the book title, and one `h1` per page is the
accessibility constraint.

| Surface | Layout | What changes |
|---|---|---|
| **Shelf** `/` | fluid, max 1200; continue-hero full width; card grid 3 / 2 / 1 columns | hero gets a cover; grid cards replace the row list; "+ Buch" is the one primary action; import is secondary. Card metadata = genre, language, last touched, chapter count and word count (the last two from the derived aggregate, T5b) |
| **Workspace** `/novels/$id` | **one** container width (max 1152) in every state; rail 224; dock 384; prose measure fixed 544, centred in whatever column remains | opening the dock no longer changes the text measure; rail rows 28 px with `aria-current`; toolbar = icon buttons in one `gap` group; collapse control moves out of the list; focus depth 2 gets a visible hint. **Runhead** (inside the editor card, above the text): book title · chapter title on the left, save state on the right. **Footer** (inside the card, below the text): chapter word count and "Kapitel n von m". Both hide at focus depth 2, where only the text remains (the E2E asserts chrome-free). Word count = whitespace-separated tokens of the chapter's Markdown body, counted client-side |
| **Knowledge** | dock `/novels/$id/wissen` at 384 px; `/knowledge` stays the global documents-and-search page | dock: entity list keeps its RAC `GridList` roles (the dock E2E asserts `gridcell`/`row`), restyled through `Row`'s token classes; relations = a real `<table>` split into outgoing/incoming — **no chapter column and no mention list: neither has a data source** (`RelationRead` carries ids, type, note; there is no mention index and no passage-to-chapter link). `/knowledge`: documents become a `Panel` list with one "+ Dokument" dialog, and search becomes one field with the existing `limit`, **no filter pills** (the API has no filter dimension) |
| **Chat** `/chat` | single column, max 640 | input + ask on one row; answer in `Notice`-free prose block; sources as `Row`s; the dock tab keeps `aria-pressed` |
| **Prompts** `/prompts/settings` | nav 200 + content 56 rem, max 1000 | panels replace the free-floating sections; the prompt body keeps its editor |
| **Settings** `/settings` | nav 200 + content 56 rem, max 1000 | cluster nav as a vertical `Row` list; provider rows on the 128 px label grid; one primary action per sub-page |
| **Setup** `/setup` | card max 448, no `min-h-screen` | demo entries get covers. The top bar **stays**: it carries the language control, which is the one thing a first-run user needs and cannot reach any other way. The nav links bounce back here until setup is complete — accepted |

Page titles: one `text-title` per page; the browser title becomes
`<page> — Narrare` (WCAG 2.4.2).

### 8.8 States

One vocabulary, four honesty levels, unchanged in meaning:

| State | Primitive | Shape |
|---|---|---|
| Loading | `Notice tone="quiet" live="status"` + skeleton rows | skeleton bars are `--rule` 8 px, pulsing only under `prefers-reduced-motion: no-preference` |
| Outage (nothing to show) | `Notice tone="danger" live="alert"` + secondary retry | names the failure; retry is one press |
| Empty (real emptiness) | `Notice tone="quiet"` + primary action | names the emptiness, offers the first step |
| Refresh failed (content stays) | `Notice tone="quiet" live="status"` + text retry | quiet, beside the work |
| Save | `SaveIndicator` unchanged | beside the editor, in the runhead |
| Job | `Row` + 1 px progress rule + cancel | no card, no badge |

### 8.9 Selection, focus, keyboard

- Chapter selection uses `aria-current="true"` + `--soft` (L2), not `aria-pressed`.
  The rail is a single tab stop with roving `tabindex` and Up/Down.
- Dock tabs keep `aria-pressed` (they toggle a panel — that *is* a toggle).
- One focus treatment (`ring-2 ring-focus`), including the ProseMirror surface,
  which today has `outline: none` and no ring at all.
- Overlays below 1024 px (rail, dock) get a scrim and a focus trap, or they stop
  being overlays; the palette already does this through React Aria.
- Depth 2 shows a one-line hint ("Esc zeigt die Leiste wieder") that fades after a
  few seconds; it is not chrome, it is the way back.
- The leave guard's `window.confirm` becomes a React Aria dialog (the app's only
  native modal today).

### 8.10 Dark mode

Same roles, system-following. `--card` sits one step above `--background`;
`--soft` is a step above `--card`; `--rule` is dimmer than `--border`. No second
palette, no toggle.

## 9. Findings

Thirty findings from the two audit passes. "Fixes" means this wave closes it; the
issue number is created at build start, and the fixing task closes it with
`Closes #n`. Every finding becomes an issue before the branch merges, per
`AGENTS.md`.

| # | Finding | Where it closes |
|---|---|---|
| F1 | ~500 repeated utilities, no scale (176 `text-sm`, 59 `border-border`, …) | §8.1–8.4; census §11 |
| F2 | every page the same 672 px column; 380 px of paper at 1440 | §8.7 |
| F3 | nothing is a book: rows instead of shelf, card instead of title page | §8.6–8.7 |
| F4 | editor has no running head, word count or footer | §8.7 workspace |
| F5 | active chapter is a 56 px solid sepia block | L2, §8.9 |
| F6 | no primitive → hover/spacing drift (`ml-3` toolbar) | §8.4 + spacing rule |
| F7 | six chrome items in the bar; ⚙ the only icon; nav duplicated in bar and rail | §8.5, §8.7 (one navigation) |
| F8 | knowledge page is three stacked forms | §8.7 knowledge |
| F9 | interaction states inconsistent (hover present, absent, arbitrary) | §8.4 state matrix |
| F10 | hand-built skeletons and error markup | §8.8 |
| F11 | `--card` white on warm ground: paper and card not separated | §8.1 |
| F12 | `min-h-screen` under the bar overflows the setup page by the bar's height | §8.7 setup |
| F13 | 43 × `text-danger` as the only error idiom | `Notice` |
| F14 | knowledge first GET ignores status: an outage reads "No documents yet" (`KnowledgePage.tsx:24`) | knowledge task |
| F15 | `reembed()` returns silently on refusal (`KnowledgePage.tsx:90`) | knowledge task |
| F16 | streamed chat answer has no `aria-live`/`announce` (`ChatPanel.tsx:113`) | chat task |
| F17 | `document.title` is "Narrare" on every page (`__root.tsx:31`) | §8.7 |
| F18 | editor surface has no focus indicator (`globals.css:101`) | §8.9 |
| F19 | two focus languages: `focus:outline-none` + border change in 3 fields | `Field` |
| F20 | `aria-pressed` carries "current selection"; no `aria-current`; 40 tab stops in the rail | §8.9 |
| F21 | `window.confirm` is the only native modal (`NovelPage.tsx:350`) | §8.9 |
| F22 | rail/dock overlays have no scrim and no focus containment below 1024 | §8.9 |
| F23 | depth 2 has no visible exit and no hint | §8.9 |
| F24 | `animate-pulse` ignores `prefers-reduced-motion` (`NovelsPage.tsx:123`) | §8.8 |
| F25 | opening the dock shrinks the prose measure 544 → 464 px | §8.7 workspace |
| F26 | collapse control is a full-width button above the chapter list | §8.7 workspace |
| F27 | `class: "prose"` is dead: no typography plugin (`markdown-editor.tsx:66`) | §8.2 (removed, not installed) |
| F28 | hero and shelf show no per-book metadata (genre, language, last touched) | §8.7 shelf |
| F29 | relation list is one flat string with `→`/`←` arrows; no direction split | §8.7 knowledge |
| F30 | the continue-hero can name no chapter; no percentage exists in the data; `RelationRead` carries no chapter; there is no mention index | §8.7: chapter line, percentage, relation chapter column and mention list are **dropped**, not invented |

Four of my own drafts were wrong and are recorded here so the plan does not inherit
them: the hero's chapter line and the "34 %" figure had no data source, the
relations table's chapter column and the "7 Erwähnungen in 3 Kapiteln" block had
none either (F30), and the first B sketch drew two navigations for the same
destinations (F7).

## 10. Phasing (≤3 production files per task)

| # | Task | Files | Gate |
|---|---|---|---|
| T1 | Tokens, radii, type scale, `--soft`, `--rule` | `web/globals.css` | `just check`, `just build` |
| T1b | EB Garamond subset (`pyftsubset`, OFL licence file) + `@font-face` | font file, licence, `web/globals.css` | `just build`, `just test-e2e writing` |
| T2 | `Button`, `Field` + state matrix | 2 | `just test-frontend`, `just build` |
| T3 | `Row`, `Panel`, `Table`, `Notice` | 3 | ditto |
| T4 | Icon module + catalog keys for icon-only controls | 1 + i18n ×3 | `just check`, i18n test |
| T5 | Shell frame: icon rail, top bar, `usePageTitle` | 3 | `just test-e2e writing`, `knowledge` |
| T5b | Derived `chapter_count` + `word_count` on `NovelRead` (no new table, no new user action) | 3 | `just test`, `just test-e2e writing` |
| T6 | Cover component + shelf | 2 | `just test-e2e writing` |
| T7 | Workspace: rail, toolbar, dock, runhead/footer, focus hint, leave dialog | 3 | `just test-e2e writing` |
| T8 | Knowledge dock: entities, relations table, `buttons.ts` deleted | 3 | `just test-e2e knowledge` |
| T9 | Knowledge page: documents, search, review queue (+F14, F15) | 3 | `just test-e2e knowledge` |
| T10 | Chat (+F16) and prompts | 3 | `just test-e2e chat`, `prompts` |
| T11 | Settings, setup (+F12) | 3 | `just test-e2e settings`, `setup` |
| T12 | Palette and the old `ui/` vocabulary (`ProposalCard`, `JobStatus`, `TextField`) | 3 | `just test-e2e chat`, `writing` |
| T13 | Census sweep, E2E corrections, follow-up issues | — | `just verify all` |

The wave lands as 3–4 PRs (T1–T6, T7–T11, T12–T13), each with the capability E2E
it touches. Every surface task migrates the `TextField`/`buttons.ts` consumers it
already touches; nothing is left "for now", and nothing is migrated twice.

## 11. Verification

**The census is the acceptance test.** The same command that produced the
diagnosis runs before and after; the target is not "fewer" but a named residue:

```
rg -o --no-filename 'className="[^"]*"' app/capabilities/*/web/*.tsx web/components/*.tsx \
  | sed 's/className="//;s/"$//' | tr ' ' '\n' | sort | uniq -c | sort -rn
```

Targets after T11. Capability folders carry the full set; `web/components/`
(shell chrome, not primitives) carries the drift set — the shell owns its
hairlines, so `border-border`/`rounded-lg` are legal there on chrome, while
type/colour/spacing drift is not:

- `text-sm` = 0 (the scale is `text-body` and friends; `text-sm` survives only
  inside `web/ui/`)
- `bg-primary` = 0 outside `Button` and `Cover` (a cover's ground is an
  object surface, §8.6)
- `border-border` = 0 in capability folders (legal on `web/components` chrome, R42)
- `rounded-md` / `rounded-lg` = 0 in capability folders (rounded-lg legal on `web/components` chrome, R42) (radii come from tokens)
- `ml-*` / `mr-*` between siblings = 0
- `text-danger` = 0 outside `Notice`

Plus the standing gates: `just check`, `just test`, `just test-frontend`,
`just build`, `just test-e2e <capability>` per task, `just verify all` at the end,
axe inside every E2E flow (already wired), and no VRT.

E2E pins that must survive or be rewritten deliberately in the task that touches
them: `whitespace-pre-wrap` on the chat answer (computed style), a non-transparent
`bg-primary` on the ask button, `aria-pressed` on dock tabs, and `aria-pressed` on
chapter rows (this one *changes* to `aria-current` in T6 — the three assertions in
`test_autosave_e2e.py` and `test_chapters_e2e.py` are rewritten in that task).

## 12. Calls made by the designer (rejectable)

1. **Prose keeps a serif face** (EB Garamond, subset, Georgia until it lands).
   **Owner-confirmed 2026-10-31.** The one typographic fact a writing tool should
   not lose.
2. **The editor surface stays a card**, as drawn in B. The owner chose the panel
   knowingly.
3. **Percentage dropped, absolute counts kept.** No new `target_words` field for a
   figure nobody asked for.
4. **Covers: three token tones, hashed by title.** No artwork, no uploads, no
   fourth tone.
5. **Icons are inline SVG**, not a package: 16 glyphs do not justify a dependency
   and a governance-budget entry.
6. **Dock tabs keep `aria-pressed`**; only the chapter selection moves to
   `aria-current`. Toggles stay toggles.
7. **`text-sm` may survive inside `web/ui/` only.** The census target is
   capability folders, not the primitives.
8. **Setup keeps the top bar** (it carries the language control, the one thing a
   first-run user cannot reach otherwise); only `min-h-screen` is removed. The nav
   links bouncing back to setup until it completes is accepted.
9. **The icon rail is global**, with a fixed Home first, the generated `nav`
   (chat, knowledge) after it, and Settings anchored at the bottom. `writing`
   stays `nav: false`; the per-page back links stay.
10. **Page titles come from a shell hook** (`usePageTitle`), and each page's `h1`
    stays in the page body.
11. **`Row` is a visual primitive, not a Ria item.** The chapter rail and palette
    use plain elements (as today); the entity list keeps its `GridList` roles and
    only adopts the token classes. `Table` is a real `<table>`.
12. **No `Tooltip` primitive.** An icon-only control's meaning is its catalog
    `aria-label`; a visible hover tooltip is not required.
13. **The relations table loses its chapter column and the mention list**, because
    neither has a data source. Same rule as the percentage: nothing invented.
14. **The shelf shows genre, language and last touched**, plus chapter and word
    counts from the derived aggregate (T5b).
15. **The old `ui/` vocabulary is replaced in this wave**, not left beside the new
    one (anti-goal: no restyle that keeps the old classNames). That is T12.

## 13. Decisions on the open questions

Taken with the owner on 2026-10-31:

1. **The entity list stays in the dock.** `/novels/$id/wissen` at 384 px is
   restyled (T8); `/knowledge` stays documents + search (T9). No new route, no
   novel selector, no new feature.
2. **The shelf gets real numbers.** T5b derives `chapter_count` and `word_count`
   on `NovelRead` — no new table, no new user action.
3. **Prose is serif** (EB Garamond subset, T1b). The writing surface is the one
   literary place in B pur.

Still open:

4. **Wave size.** Fifteen tasks in 3–4 PRs, or T12 (the old `ui/` vocabulary) split
   into its own wave? The anti-goal forbids leaving two vocabularies side by side,
   so the recommendation is to keep it in.

## 14. Left to the builder

- Exact `@theme` wiring for the type and radius tokens (Tailwind v4 mechanics).
- The `Button`/`Field` prop names beyond the table above, and whether `Field`
  wraps React Aria or stays a styled native control.
- The cover hash function and the tile's inner shading.
- Whether the dock overlay below 1024 px becomes a scrimmed sheet or stops being
  an overlay at all (either satisfies §8.9).
- The palette's grouping and the roving-tabindex details.
- The `fr` translation pass, as its own commit (the standing rule).
