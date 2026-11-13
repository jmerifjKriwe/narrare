# Shelf Fidelity Repair — the shelf 1:1, with the drafted TopBar

> **Status:** Approved (owner 2026-11-13, "Ok"); builder check answered, both
> owner questions decided (D-5, D-6, §8). Plan:
> `docs/superpowers/plans/2026-11-13-shelf-fidelity.md`.
> **Authority:** implements the [Literary Modernism umbrella spec](2026-11-11-literary-modernism-frontend-design.md)
> (§6.1 norm, §6.6 shelf, §6.9 deviation log) and the v2 architecture norm.
> Value authority: `docs/design/stitch/DESIGN.md`; composition authority:
> `docs/design/stitch/screens/library/shelf.webp` / `shelf.html` / `shelf-dark.webp`.
> **Origin:** owner decision 2026-11-13, after the W3 side-by-side review: the repair
> starts with the Shelf, 1:1; missing features ship as layout-holding placeholders;
> an English gap document lists every placeholder and its replacement trigger.
> The drafted TopBar ships in the same wave (owner answer 2026-11-13), superseding D-2.
> **Base:** `feat/literary-modernism-w3` (owner decision 2026-11-13), stacked on the
> open W3 PR; the D-2 supersession and the §6.5 cover correction land in the specs
> as they exist on that branch.

---

## 1. Intent and why

The W3 comparison pairs showed that the shipped surfaces follow a watered-down
reading of the specs instead of the drafted composition, and the shelf — the pilot
that was supposed to prove 1:1 fidelity — carries the same drift: covers without
author/glyph/imprint, a smaller hero, an old TopBar, a genre select where the draft
draws a Filter button. The owner's binding condition (umbrella §3b) is 100 %
fidelity; a deviation ships only with explicit approval in the deviation log.
This wave brings the shelf and the shell's TopBar to the draft, honestly: every
drafted element ships; where the backend has no data yet, a placeholder holds the
draft's geometry so the layout never breaks, and the gap document plus follow-up
issues name what replaces it and when.

## 2. Goals, non-goals, anti-goals

**Goals**

- G1 — The shelf *is* `screens/library/shelf` (light) and `shelf-dark` (dark):
  header + metrics strip, hero card, cover composition, search/filter/view row,
  book grid, activity banner, 1:1.
- G2 — The TopBar is the drafted bar on every route: breadcrumb + save state left;
  search/palette door, library word count, language chip right. Supersedes D-2.
- G3 — Placeholders hold geometry: missing values render neutral ("—", empty bar
  track, flat labeled sparkline), never invented numbers; controls without an
  action render disabled. Layout identical to the draft in every state.
- G4 — An English gap document (`docs/design/stitch/shelf-gaps.md`) lists every
  placeholder: element, drafted value, interim render, the trigger that makes it
  real, follow-up issue number. Cross-referenced from the deviation log.
- G5 — Gates green: `just check`, writing suites, axe AA both themes, writing E2E;
  re-shot master frames; a shelf side-by-side pair (light + dark) in
  `docs/design/stitch/comparisons/` — the pair that is missing today.

**Non-goals**

- No backend features: no streak/goal/target/status/series/imprint data is added.
  Existing follow-ups (#781–#786, #788) keep their triggers.
- Workspace and zen repair are later waves; this wave touches the shelf and the
  shared TopBar (and the shared Cover primitive, which the workspace rail's
  book-switcher also wears — it inherits the corrected composition).
- No re-routing or behaviour changes: search, filter, view toggle, menus, dialogs,
  navigation keep their semantics.

**Anti-goals**

- Invented numbers or states no draft shows; placeholders are neutral, never fake.
- A composition invented locally for an undrafted detail (the Filter panel) —
  that goes through a Stitch round (§7), per umbrella §6.8.
- Old-neutral tokens anywhere on the touched surfaces.

## 3. Constraints

- Tokens only in `web/globals.css`; capabilities carry utilities. Existing
  `light-dark()` pairs; AA 4.5:1 text / 3:1 icons in both themes.
- Icons stay the hand-drawn 16 px / 1.5-stroke set (O-3); cover motifs are drawn
  in that language, not Material Symbols.
- Copy through en/de/fr catalogs; draft labels inform `de`.
- UI tasks by the UI Agent, reviewed by the Reviewer (models per AGENTS.md standing
  preference); whole-branch review at the end; push after each green group.
- Interim comments live beside the element and end in their issue number.
- The deviation log stays the single record of departures; this wave adds none
  silently (placeholder semantics are an owner decision, recorded as such).

## 4. Approaches considered

| Approach | Verdict |
|---|---|
| **A — One wave: shelf 1:1 + drafted TopBar + gap doc** (chosen, owner 2026-11-13) | The TopBar stands in every draft screen; without it the shelf can never be 1:1. One fidelity gate judges both. |
| B — Shelf only, TopBar later | Rejected by owner: the comparison would keep showing two different bars. |
| C — Re-baseline (approve shipped composition as norm) | Rejected: contradicts the owner's 100 % condition. |

## 5. Surface map

### 5.1 TopBar (shell, all routes)

Drafted composition (shelf.webp head band): left — book glyph + breadcrumb
`Manuscripts / <active book>` (book in `text-emph`, truncation with full accessible
name) + save chip; right — search-styled palette door ("Search or prompt…" + the
palette keycap inside the field), library word-count chip (Σ `word_count` over the
user's novels, tabular, derived — real), language chip (globe + EN/DE/FR, compact
menu, real).

- Save chip keeps the shell's `shell.sync*` vocabulary (deviation #2, approved):
  one status owner feeds it; idle must not claim "saved" for a clean chapter.
- Breadcrumb's second slot and the shelf hero share **one** active-novel source
  (the builder pins the derivation; the hero already picks the active book).
- The settings gear leaves the bar where the rail owns settings (the draft's rail
  carries it); routes without a rail keep a gear. Palette keyboard contract,
  skip link, and `data-focus="2"` gating stay exactly as they are.
- The bar keeps its rail-axis alignment arithmetic (current TopBar comment).

### 5.2 Header and metrics strip

- Eyebrow `Atelier & Archiv` (area-writing) + dot + session line (existing derived
  seasonal label); h1 in `prose-heading-1` at the draft's scale (text-3xl,
  `text-primary`), description in `text-body`.
- Metrics: three cards — book count (real), Σ words (real), streak ("—" #781) —
  each with the drafted 32 px icon square; CTAs Import (secondary) + New book
  (primary) on the same row, right-aligned, as drafted.

### 5.3 Hero card

- Cover per §5.4 at hero size; right column: `Aktuell in Arbeit` pill + sync line
  (existing real source); title `prose-heading-1` + series line slot (placeholder
  "—" #786); blurb = the book's description in `prose-editorial`, line-clamp-3,
  no invented quotation marks; stats row: real word count + "/ — Wörter" target
  slot + empty bar track (#783), chapter count (real), last-edited relative time
  (real); CTAs Continue (primary, real) + Outline & scenes (secondary, real —
  opens planning, #787 closed).

### 5.4 Cover primitive (shared, rebuilt to the draft)

One composition for all four tones (the hash-tone system stays, owner-approved):
spine gradient at the left; top block — eyebrow (genre, else language) + title in
the brand serif italic at the draft's step (grid: `prose-heading-2`, hero:
`prose-heading-1`); middle — genre motif glyph (hand-drawn stroke language;
sci-fi target, mystery house, literary waves, historical cloud; unknown genre →
neutral ring motif); foot — author line (`novel.author`, real; null → "—").
Sepia keeps its gold inset frame. Hero adds: amber rule under the eyebrow, and a
foot row with imprint slot (placeholder "—", new issue) + the drafted corner motif
(decorative, aria-hidden). The current bottom-aligned/centered variants go away —
the screen wins over the umbrella §6.5 prose ("title bottom-aligned"), which the
build session corrects in the spec text (no deviation: we ship the screen).
Geometry from shelf.html: grid w-36 h-52, hero w-48 h-72, radii and spine widths
as drafted; dark grounds per shelf-dark.

### 5.5 Search / filter / view row

- Search field h-9 w-72, drafted placeholder copy (figures/tags join later, #785);
  matches titles now (real).
- Filter button (tune glyph) as drafted; its panel is **not drafted** → Stitch
  round G-F1 (§7) answers the composition before implementation; the panel then
  carries the existing genre filter (real client state).
- Right: `Ansicht:` + grid/list icon toggle (real client state).

### 5.6 Book grid cards

Cover on the drafted ground pad with the `more_horiz` menu (real actions) at the
top right; body: title `text-title` + status pill (interim "Entwurf" for all,
#784); blurb `text-meta` line-clamp-2 (real); stats row "N / — Wörter" + "—"
percent slot + empty bar track (#783); foot chapter count + relative time (real).
Hover lift/shadow as drafted. List view keeps its behaviour, re-tokened.

### 5.7 Activity banner

Icon square + "Heutiges Schreibziel: — Wörter" + neutral subline (no invented
progress sentence); right: WOCHENSCHNITT "— W/Tag" + flat labeled placeholder
sparkline + "Statistiken öffnen" rendered disabled (#788). Geometry as drafted so
the banner holds the page foot.

### 5.8 Workspace band trim (consequence of the D-2 supersession, owner 2026-11-13)

The drafted bar owns the shell facts on **every** route, so the W3 workspace band
(`WorkspaceToolbar`) loses its duplicated left cluster — breadcrumb, save chip,
language chip, book word count move to the bar. The band keeps only workbench
controls: chapter selector, focus (F9), history (disabled), export, dock tabs,
rail toggle, rail filter. Its pinned ribbon tests update with it. The bar's save
chip is fed by the shell's sync bridge (`__root.tsx` `useSyncStatus`, passed as a
prop like `IconRail`'s `sync`) — one status owner on every route. The workspace
spot-check (§9) shows one bar plus the trimmed ribbon, as `workspace.html` draws.

### 5.9 Dark accent hues — screen wins (owner 2026-11-13)

`shelf-dark.html`'s literal pill and accent hues bind over the dark token card's
tolerated deltas (umbrella §6.1: the screen is what the owner approved). New
shell `light-dark()` pairs carry the status pills — active `#1B3520/#66BB6A`
(rule `#25502C`), draft `#192D3E/#64B5F6` (rule `#234561`), planning
`#2C2C28/#E0E0E0` (rule `#3D3D37`), review `#3A2814/#FFB74D` (rule `#5A3C1C`) —
light halves extracted from `shelf.html`; the area-writing dark accent becomes
`#E28659`. Every pair ships with measured AA in both themes; a value that fails
the gate goes to a Stitch round, never a quiet adjustment. `dark-tokens.md`'s
delta tolerance is logged as superseded; the deviation log records the
supersession, not the hues themselves.

### 5.10 States

The drafted undrafted-state screens (shelf-empty, shelf-states: skeleton, error
notice, dense grid, long titles) already exist from W2; the re-composition keeps
them 1:1 and re-shoots them in the dark leg.

## 6. Placeholder semantics and the gap list

Semantics (owner decision 2026-11-13): geometry identical to the draft; values
neutral where the app has no truth ("—", empty track, flat labeled curve); derived
where it has truth; never an invented number; a control whose action does not
exist renders disabled with `aria-disabled` and an explanatory title. Every
placeholder carries a code comment ending in its issue number.

The gap document (`docs/design/stitch/shelf-gaps.md`, English, committed with the
wave) carries exactly this table, kept current as issues close:

| # | Element | Draft shows | Interim render | Real-data trigger | Issue |
|---|---|---|---|---|---|
| 1 | Metrics streak | "14 Tage" | "—" | streak/session tracking | #781 |
| 2 | Banner goal / weekly / sparkline | 750 / 840 W/Tag / curve | "—", "—", flat labeled curve | goals + session tracking | #782 |
| 3 | Target (hero + cards) | "/ 60.000 Wörter" + % + bar | real words, "—" target, "—" %, empty track | per-book target field | #783 |
| 4 | Status pills | Entwurf/Planung/Lektorat | "Entwurf" for all | book status field | #784 |
| 5 | Search scope | "Titel, Figuren oder Tags…" | titles only | searchable figures/tags | #785 |
| 6 | Hero series line | "Band I • …" | "—" | series/band field | #786 |
| 7 | Statistics / goal doors | "Statistiken öffnen" | disabled button | statistics surface | #788 |
| 8 | Hero imprint + foot row | "Atelier Opus IV" | "—" (corner motif stays decorative) | imprint/series field | #832 |
| 9 | Hero eyebrow form | "Roman • Sci-Fi" | genre alone | book form/kind field | #833 |
| 10 | Cover author | "Calder" | author real; null → "—" | none (real data) | — |
| 11 | Filter panel | button only in draft | Stitch-round composition, genre filter real | round export G-F1 | #834 (panel states) |

New issues are filed at the wave's opening under a new index row in
`docs/superpowers/follow-ups.md` (labels per AGENTS.md: `follow-up`,
`area: writing`, `severity: minor` — the pilot precedent). Index #831; children
#832 (imprint), #833 (form/kind), #834 (filter panel states). #781–#786/#788 stay
under the pilot index #780. The committed English gap doc is
`docs/design/stitch/shelf-gaps.md`.

## 7. Stitch round (gap protocol)

- **G-F1 — Filter panel composition. — ANSWERED 2026-11-13.** One batched round in
  the `narrare` Stitch project produced `screens/library/shelf-filter` (light) and
  `shelf-filter-dark` (dark): the panel anchored under the Filter button — header
  FILTERN + close, Genre checkbox rows with live per-genre counts, footer
  Zurücksetzen + selection count, live filtering, no apply action. The exports are
  authority for the **panel only** (the dark export's surrounding page drifted and
  is not normative; `shelf`/`shelf-dark` stay the page authority — README). The
  no-genres edge state and any further panel states join #834, never a local
  invention. Task 9 builds from the exports.

## 8. Deviation log and spec corrections

- D-2 (TopBar frozen as W1 shipped) is **superseded** by owner decision
  2026-11-13; the build session records the supersession in the W3 spec's
  decisions and the umbrella §5 table.
- Umbrella §6.5 cover prose corrected to the screen's composition (§6.1
  screen-wins); no deviation entry needed — the wave ships the screen.
- Deviation #2 (sync vocabulary) carries into the new bar's save chip unchanged.
- Placeholder semantics recorded as an owner decision, not a deviation.
- **D-5 (owner 2026-11-13):** the workspace band loses its duplicated left
  cluster (§5.8); `WorkspaceToolbar` and its tests are in this wave.
- **D-6 (owner 2026-11-13):** screen wins for the dark pill/accent hues (§5.9);
  the dark-tokens delta tolerance is superseded and logged.

## 9. Verification

- `just check` after each task group; `just test-file` on every touched test;
  `just verify` before the PR; writing E2E green.
- axe AA both themes on the shelf route; component tests assert token names and
  placeholder neutrality (no fake numbers), truncation with full accessible names.
- Re-shot master frames `05-shelf.png` / `06-shelf-dark.png`; new side-by-side
  pairs (light + dark) in `docs/design/stitch/comparisons/` via the fidelity
  compositor; **owner approves the pairs before merge**.
- TopBar spot-check side-by-side on the workspace route: one drafted bar plus the
  trimmed ribbon (§5.8), no duplicated facts.
- Whole-branch review by a fresh Reviewer against this doc; findings become
  issues or fixes before merge.

## 10. Process

- Build session (after the owner switches agents) moves this doc to
  `docs/superpowers/specs/2026-11-13-shelf-fidelity-design.md`, writes the plan to
  `docs/superpowers/plans/`, commits both; tasks run UI Agent
  (`opencode/deepseek-v4.1-flash-free`) + Reviewer (`zai-coding-plan/glm-5.3`),
  coordinator `zai-coding-plan/glm-5.3`; push after each green group.
- Conventional commits with real `User-visible:` lines for feat/fix; the gap doc
  and spec moves are `chore(docs)`; agent commits carry the `Assisted-by` trailer.

## 11. Builder check

Dispatched fresh-builder check (2026-11-13) returned two questions that change the
plan; both were put to the owner and decided the same day:

1. **Workspace band vs. the drafted bar** → the band loses its duplicated left
   cluster; the shell sync bridge feeds the bar's save chip; `WorkspaceToolbar`
   and its tests are in this wave (§5.8, decision D-5).
2. **Dark pill/accent hues vs. the token card's delta tolerance** → the screen
   wins; new `light-dark()` pairs carry the drafted hues, AA measured; the
   tolerance is superseded (§5.9, decision D-6).

Everything else the check found was pinned by the doc, answered by the archive
(the empty-shelf bar variant, the uniform breadcrumb across knowledge screens),
or builder-level (§12). The coordinator's earlier fallback check had already
verified the drafted TopBar is uniform across the library, knowledge and
planning screens, so §5.1's single-bar rule holds on every route.

## 12. Left to the builder

- Exact classes/geometry translation, task split and order, i18n keys, motif SVG
  paths, active-novel derivation, Filter panel implementation after G-F1, E2E and
  screenshot updates, issue bodies for the new follow-ups.