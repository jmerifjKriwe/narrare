# Literary Modernism — the Narrare frontend on the Stitch drafts

> **Status:** Proposed — owner approval pending after the builder check
> **Type:** Design spec for the frontend's visual system and its migration waves
> **Authority:** implements on top of the
> [v2 architecture design](2026-10-21-narrare-v2-architecture-design.md) (ADR-100) and the
> [frontend design](2026-10-22-frontend-design.md); supersedes the *visual* decisions of the
> [UI command focus norm](2026-11-06-narrare-ui-command-fokus-design.md) (§5.1–5.2, §6) and
> [visual identity](2026-11-06-visual-identity-and-shell-design.md) (B1 scale, B3 hue usage,
> C1 rail behaviour where they conflict with the drafts). Their architecture norms stand:
> the Platz-Atlas (§5.7), single-active dock, canvas routes, command palette, AI patterns.
> **Norm for every value:** [`docs/design/stitch/DESIGN.md`](../../design/stitch/DESIGN.md)
> and the screens under `docs/design/stitch/screens/`, exported 2026-11-11.
> **Origin:** owner decision 2026-11-11 — the Stitch drafts beat the current UI; the whole
> frontend moves onto them. Pilot first (Shelf), waves after.

---

## 1. Intent and why

The app's chrome is a neutral, near-white system; the owner has seen the Stitch exploration
("Literary Modernism": warm parchment grounds, terracotta sepia, EB Garamond prose on
Plus Jakarta Sans chrome, book-object covers) and wants *that* app. Not an adaptation of it —
that system, at 100 % fidelity.

The measured good news, and the reason this is a migration and not a rebuild: the drafts and
the landed shell share one anatomy. Rail 48 px / 168 px, exactly one right dock, canvas
routes, ⌘K palette, a 34-rem prose measure in EB Garamond 18/31.5, three typographic cover
tones, five area identity hues, a tri-state light/dark theme. The work is re-tokening the
shell, rebuilding the chrome components to the drafts, and re-skinning surface by surface.

## 2. Goals, non-goals, anti-goals

**Goals**

- G1 — The app *is* `DESIGN.md`: every colour, size, radius and shadow in the app comes from
  the Literary Modernism tokens, 1:1.
- G2 — Themeable by construction: the `light-dark()` + `color-scheme` mechanism is untouched;
  every token lands as a pair, AA-measured (4.5:1 text, 3:1 icons) in both modes. A future
  theme is a new value table over the same names.
- G3 — Pilot proof first: tokens → chrome → the Shelf rebuilt 1:1 against
  `screens/library/shelf`, held side-by-side in the PR, before any other surface moves.
- G4 — The gates keep proving it: axe (AA both themes), `typeScale.test`, E2E screenshots
  into `assets/screenshots/`, the `/design` gallery showing the live token pairs.

**Non-goals** (later waves, separately planned)

- Building any screen whose capability does not exist yet (export studio, analysis suite,
  series architecture, agency manager, audio studio, Pocket). Those drafts stay blueprints in
  `docs/design/stitch/` and are built when their features are, directly in this system.
- Re-routing, re-composing or re-architecting anything. Routes, docks, canvas and palette
  behaviour stay as the command focus norm fixed them.
- Artwork, a second data store, a Storybook, a Tailwind CDN in the app. The drafts' HTML is
  reference material; the app keeps its own Tailwind v4 build and self-hosted fonts.

**Anti-goals** (failure even if it technically runs)

- A mix of old neutral and new parchment tokens anywhere in the tree.
- Invented components, values or states that no draft shows. Gaps go to Stitch (§6.8), not
  to imagination.
- German-only copy: the drafts speak German, the app speaks en/de/fr through its catalogs;
  draft labels inform the *de* catalog, never a hard-coded string.

## 3. Constraints

- The shell owns the tokens (`web/globals.css`); capabilities carry utilities, never a
  palette (`globals.css:3-8`). Every new value enters through `--token` names in
  `light-dark()` form.
- UI work is implemented and reviewed by subagents, one implementer and one reviewer per
  task, whole-branch review at the end (repo rule, standing model preference 2026-11-09).
- i18n rule 5, a11y gates and the E2E-green definition of done apply to every wave.
- **Owner conditions (2026-11-11), binding:** (a) theme capability is preserved — see G2;
  (b) 100 % fidelity to the drafts. A deviation ships only with the owner's explicit
  approval, recorded in the deviation log (§6.9). Missing screens or unresolved detail
  questions are clarified *by Stitch* — a round in the `narrare` Stitch project via MCP,
  exported into `docs/design/stitch/` — not invented locally.

## 4. Approaches

| Way | Verdict |
| --- | --- |
| **A — Vertical slice** (chosen): W0 tokens + fonts, W1 chrome primitives, W2 the Shelf 1:1 as the pilot proof; each wave small, green and reviewable. | The anatomy already matches (§1), so tokens move the whole app onto parchment in one honest step and every later wave is composition work. Nothing behind a flag, nothing thrown away. |
| B — Bubble replica: the Shelf as a flag-gated route with draft-local styles, tokens extracted afterwards. | Rejected: a second palette beside the shell-tokens rule, and the work is discarded at extraction. Fastest picture, wrong debt. |
| C — Parallel build: a complete second UI under `/next`, switch when finished. | Rejected: weeks of dual maintenance while the E2E gates keep proving the old UI; delivers nothing A does not deliver sooner. |

Pilot surface inside A: **Shelf**, not the writing workspace. The Shelf is the smallest
surface that proves the whole system — cover composition with spine and frame, card
surfaces, eyebrow labels, controls, the empty/hero states — while the workspace (~6,900
lines, docks, ghost text, editor chrome) is wave 3 and profits from every primitive the
pilot has already hardened. The owner chose this order on 2026-11-11.

## 5. What supersedes what

| Decision in force today | New rule |
| --- | --- |
| UI type = the system sans, six steps 12/13/14/15/20/28 (visual-identity B1) | UI type = **Plus Jakarta Sans**, self-hosted; the drafts' ten steps, §6.3 — 12/13/14/15/20/28 keep their roles, eyebrow 11 and hero 700 join, prose 18/31.5 (already landed) stays |
| Anti-goal "no All-Caps-Eyebrows" (command focus §2) | **Lifted by the owner.** `eyebrow-tracked` (11 px / 600 / 0.08 em / uppercase) is the drafts' section marker and enters the scale as `text-eyebrow`. The `·`-meta-string and `—`-label bans stand. |
| Dock width 352 px (`w-88`, command focus §5.7 workbench arithmetic) | Dock width **21 rem / 336 px** (`dock-width` in DESIGN.md). The workbench arithmetic re-derives from it; the single-left-edge rule (F25) is kept. |
| Cover tokens with theme-darkened values (visual-identity B2) | Cover grounds/inks take DESIGN.md's values. DESIGN.md defines covers theme-constant; whether dark mode keeps them constant or gets own values is gap G-2 (§7), first Stitch round. |
| Area hues as nav-icon identity only, magenta planning hue (command focus §5.1) | **Amended by the owner (O-2):** area hues are identity accents *within their own area's surfaces* — rail icons, eyebrow labels, sparkline, progress fill, status-pill text, one cover ground — with DESIGN.md's values (`#914F2F`, `#606127`, `#3A637B`, `#834D7E`, `#5A5549`); never a control's fill. The `typeScale` gate's allowlist widens accordingly. Dark-mode values are gap G-1 (§7). |
| Controls 28 px / 4 px, two radii (DESIGN.md "Components", the two-radius rule) | **Amended by the owner (O-2):** the screens win. Button ladder sm/md/lg = 28 (dense floor) / 36 / 40 px at 8 px radius (a draft's compact 32 px button takes md); icon buttons p-1/p-1.5, cards 12 px, pills full — a three-radius ladder (4 small controls / 8 controls / 12 surfaces) plus pills. |
| Icons: the drafts' Material Symbols (~25 glyphs, 18–20 px font) | **Decided by the owner (O-3):** the app's hand-drawn 16 px / 1.5-stroke set stays the icon language and is extended with the missing glyphs; Material Symbols is not adopted. Logged as deviation #1 (§6.9). |
| Primary `oklch(0.42 0.09 45)` / peach dark | Primary **`#743B1F` light / `#D39562` dark**, `on-primary` from DESIGN.md. |

Everything else the command focus norm fixed — Platz-Atlas, one active dock, palette
behaviour, AI patterns, focus-ring duty, forced-colors fallbacks — carries forward unchanged.

## 6. The design

### 6.1 Norm and sources

`DESIGN.md` is the single value authority; the exported screens are the composition
authority (HTML for structure, WebP for the rendered result). Where DESIGN.md and a screen
disagree, the screen wins (it is what the owner approved) and the difference is logged.
The archive documents how to refresh it (`docs/design/stitch/README.md`).

### 6.2 Colour tokens

Mechanism unchanged: every token is a `light-dark()` pair resolved by `color-scheme`,
surfaced through `@theme inline` under its existing name. Values from DESIGN.md:

| Shell token | Light | Dark | DESIGN.md source |
| --- | --- | --- | --- |
| `--background` | `#F6F3ED` | `#16140F` | `bg-canvas-light` / `bg-canvas-dark` |
| `--panel` | `#FDFCF9` | `#1C1914` | `bg-panel-light` / `bg-panel-dark` |
| `--card` | `#FFFFFF` | `#211F1A` | `bg-card-light` / `bg-card-dark` |
| `--soft` | `#EFEBE2` | `#2C2922` | `bg-soft-light` / `bg-soft-dark` |
| `--border` | `#E0DEDA` | `#35332D` | `border-light` / `border-dark` |
| `--rule` | `#EEEBE5` | `#302D28` | `rule-light` / `rule-dark` |
| `--foreground` | `#1E1B16` | `#DFDEDA` | `on-background` / `text-foreground-dark` |
| `--muted` | `#6E6B65` | `#89867F` | `text-muted-light` / `text-muted-dark` |
| `--primary` | `#743B1F` | `#D39562` | `cover-sepia` / `override-tertiary` |
| `--primary-foreground` | `#FAF8F5` | `#1D140D` | button spec, "Buttons · Primary" |
| `--focus` | `#8F4622` | `#F2AD73` | `amber-focus` / `amber-focus-dark` |
| `--success` | `#21763C` | — | `state-success` (dark: G-1) |
| `--warning` | `#9A6100` | — | `state-warning` (dark: G-1) |
| `--danger` | `#AC3031` | — | `state-danger` (dark: G-1) |
| `--area-writing` … `--area-settings` | `#914F2F` `#606127` `#3A637B` `#834D7E` `#5A5549` | — | `area-*` (dark: G-1) |
| `--cover-pale/sepia/ink/slate` + inks | `#EEEBE5` `#743B1F` `#24211C` `#3A637B` | — | `cover-*`; the slate ground is the drafted `area-chat` cover tone (O-2) (dark: G-2) |

Every pair ships with its measured contrast in the PR. A draft value that fails the gate is
not quietly adjusted: it goes to a Stitch round (§6.8) or to the owner, and the outcome is
logged.

The drafts speak a fuller surface ladder than the shell's seven tokens: `surface-container-lowest
… highest`, `surface`, `surface-variant`, `outline(-variant)`, `secondary(-container)` and
the `inverse-*` pairs appear in DESIGN.md *and* in the screens' compositions. W0 lands that
ladder as shell tokens under the shell's naming, so compositions translate without literal
hexes. Where a screen's literal tone differs from DESIGN.md's named value (the Shelf's cards
sit on `#FFF8F2`, not `bg-card-light`'s `#FFFFFF`), the screen wins and the resolution is
logged (§6.1).

### 6.3 Typography

Two families, one pipeline, no CDN:

- **EB Garamond** (prose engine) — already self-hosted as static 400/600 subsets. The
  drafts also set italic prose (blockquotes); an italic 400 instance joins the subset if no
  drafted surface needs more. Prose stays 18 px / 31.5 px / 34 rem — already landed.
- **Plus Jakarta Sans** (shell & chrome engine) — self-hosted the same way: static
  instances 400/500/600/700, `font-display: swap`, latin + latin-ext (de/fr), subset per
  the established pipeline. It becomes the root UI family; the system sans remains the
  fallback stack.

Scale (line-height on the token, per `@theme inline`):

| Token | px / lh | Weight | Notes |
| --- | --- | --- | --- |
| `text-eyebrow` | 11 / 16 | 600 | +0.08 em tracking, uppercase — new |
| `text-meta` | 12 / 17 | 400 | |
| `text-label` | 13 / 18 | 500 | |
| `text-body` | 14 / 22 | 400 | |
| `text-emph` | 15 / 22 | 600 | |
| `text-title` | 20 / 26 | 600 | |
| `text-hero` | 28 / 32 | 700 | real 700 cut of PJS (EB Garamond keeps 600 max) |
| `prose-heading-1/2` | 26 / 34, 21 / 28 | 600 | EB Garamond, headings inside prose |
| `prose-editorial` | 18 / 31.5 | 400 | EB Garamond, `.ProseMirror` — landed |

Tabular figures (`font-variant-numeric: tabular-nums`) on counters, word counts and token
counts, as DESIGN.md demands.

### 6.4 Geometry and elevation

- Rail 48 px fine / 168 px open (`--rail-width`, unchanged); dock **21 rem**; prose measure
  34 rem (unchanged); content container 75 rem.
- Radii, per O-2 from the screens: a three-step ladder — 4 px small controls, 8 px controls
  (buttons, inputs), 12 px surfaces (cards) — plus full pills, reserved for filter pills,
  badges and avatars. `--radius-sm/-control/-surface` carry it.
- Elevation as tokens, from DESIGN.md's tiers: `--shadow-card` (Tier 2 ambient warm shadow,
  per theme) joins the existing `--overlay-shadow` (Tier 3). Tier 1 panels stay flat with
  hairline borders; no decorative shadows on list rows or form elements.

### 6.5 Chrome components (W1 scope)

From DESIGN.md "Components" and the Shelf/workspace screens, in the shell's own primitives
(`web/components`, `web/ui`):

- Buttons, per O-2 from the screens: ladder sm/md/lg = 28 (dense floor) / 36 / 40 px,
  8 px radius (a draft's compact 32 px button takes md) — primary `cover-sepia` fill with
  bright text and `shadow-sm`, secondary on card/panel grounds with `surface-container`
  hover, ghost borderless, destructive outlined `state-danger`. Amber focus ring, 2 px,
  1 px offset, on every interactive element.
- Inputs and selects follow the drafted shells (the Shelf fixes the search field's geometry);
  custom chevron on selects; no native unstyled widget. DESIGN.md's 28 px row remains the
  floor for dense forms no draft shows.
- Icons, per O-3: the hand-drawn 16 px / 1.5-stroke set in `web/ui/icons.tsx` stays the
  language; it is extended with the ~20 concepts the drafts introduce (bookmark-collection,
  edit-note, hub, radar, waves, foggy, ink-highlighter …). A drafted Material Symbols glyph
  names the *concept*; the glyph drawn for it is the app's own. No icon font, no CDN.
- Cover composition, three tones (pale / sepia / ink): 3:4 aspect, 5 px embossed spine on
  the left, sepia gets the 1 px gold inset frame at 5 px offset, title bottom-aligned EB
  Garamond (pale: eyebrow top-left), card footer with chapter count, tabular word count,
  status pill.
- Keycap badges (`⌘`, `K`, `Tab`, `Esc`) for palette and ghost-text affordances.
- Notice and finding cards: 1 px border, severity rule on top (warning amber / danger
  rust), side-by-side quotes, action bar with primary *Übernehmen* / ghost *Verwerfen*
  pairs.
- Table headers: the component pins 600 (`font-semibold`) as the cell's own weight — the
  browser's `th` bold was accidental (Task 4 fix round, 2026-11-11). W1's chrome and
  eyebrow re-composition owns the drafted table-header treatment.
- Ghost text: 50 % opacity, warm sepia tint, `[Tab]`/`[Esc]` keycap trailer.

Copy for all of the above flows through the i18n catalogs (de informed by the drafts, en/fr
by translation); state colors and severity semantics through Notice as today.

### 6.6 The Shelf pilot (W2 scope)

The writing capability's home route rebuilt **1:1 against `screens/library/shelf`** — the
whole drafted page, exactly as drafted (owner decision O-1, 2026-11-11): hero card with the
active book and its "Weiterschreiben in Kapitel 3" CTA, the metrics strip, the
search/filter/view-toggle row, the book grid with status pills, per-book targets and the
`more_horiz` quick menu, the activity banner with Schreibziel, Wochenschnitt and sparkline,
and the shelf's empty state. Where the current shelf has a state the draft does not show
(loading, error, long titles, >12 books), the state is resolved by a Stitch round — not
improvised (gap G-4).

**Missing data, honestly.** The draft shows data the app does not carry. Per O-1, every
drafted element ships anyway; each missing field renders from the least-invented honest
source — derived where the app has truth, a neutral value where it has none, never an
invented number — and every one of them is a dedicated follow-up issue (below):

| Drafted field | Interim logic | Follow-up |
| --- | --- | --- |
| "Sync Online · Vor X synchronisiert" | derived from the real autosave state (`web/lib/dirty.ts`, save timestamps) | none — real data |
| Metrics: "4 Romane", total words | derived: book count, Σ `word_count` | none — real data |
| Metrics: Schreibstreak | neutral: "—" until tracked | issue |
| "Heutiges Schreibziel: 750 Wörter", Wochenschnitt, sparkline | neutral: 0 / flat until goals exist | issue |
| Per-book target "3.384 / 60.000 Wörter" | real `word_count`; target neutral: progress bar hidden until the field exists | issue |
| Status pills (Entwurf / Planung / Lektorat) | draft default "Entwurf" for every book until the field exists | issue |
| Search "Titel, Figuren oder Tags" | matches titles now (real); figures/tags join when they are searchable | issue |
| Filter row, grid/list toggle | pure client state | none |
| `more_horiz` menu (duplicate, export, archive) | existing actions | none |

**Follow-up discipline (owner demand, 2026-11-11):** when W2 opens, one index issue is
filed (label `follow-up-index`) and one child issue per row above marked "issue" (label
`follow-up`, plus `area:` naming where it lives), each stating the trigger that makes it
bite and the interim logic it replaces; the wave adds its row to
`docs/superpowers/follow-ups.md`. The interim logic lives in code next to the field and
references the child issue, so no missing backend is ever silently forgotten.

Acceptance is the side-by-side: an E2E screenshot of the route next to the archived WebP in
the PR, plus the re-shot master frame in `assets/screenshots/`. The comparison runs on
seeded demo books (the E2E stack already seeds them), so the artifact is deterministic —
not on whatever the instance happens to hold. Cover tone stays derived from the book (hash)
over the tones the screens show, including the drafted slate ground now that O-2 admits an
area hue as a cover ground; a stored, user-chosen tone is a later product decision, out of
scope.

### 6.7 Theme capability

Unchanged mechanism, new values: tri-state `system`/`light`/`dark` on the user row,
`color-scheme` resolves the pairs, native controls follow. The dark values are DESIGN.md's
("Midnight Ink"), and every dark pair carries its own measured AA values in the PR. A
future theme is a value table over the same token names; no component changes.

### 6.8 Gap protocol (Stitch rounds)

A gap is anything the drafts do not answer: a state, a dark value, a breakpoint behaviour,
a component variant. The loop:

1. The wave's task names the gap precisely (screen, element, question).
2. One Stitch round in the `narrare` project (generate/edit via MCP, or the owner at
   stitch.withgoogle.com) answers it.
3. The answer is exported into `docs/design/stitch/` (archive stays the norm's home).
4. Only then is it implemented — from the export, not memory.

Known gaps for the first round are §7. Rounds are batched: a wave collects its gaps and
asks once.

### 6.9 Deviation log

Every departure from the drafts, however small, lands here with date, the drafted value,
the shipped value, the reason, and the owner's approval. Empty today:

| Date | Draft says | We ship | Why | Approved |
| --- | --- | --- | --- | --- |
| 2026-11-11 | Icons are Material Symbols (~25 glyphs, 18–20 px icon font) | The app's hand-drawn 16 px / 1.5-stroke set, extended with the drafted concepts | The app's own iconography stays the icon language; a second font and visual system would break it. Drafted glyphs name concepts, not faces. | Owner, O-3, 2026-11-11 |

## 7. Open gaps for the first Stitch round

- **G-1 — dark values for the state and area hues. — ANSWERED 2026-11-11** (S0 round):
  [`dark-tokens.md`](../../design/stitch/dark-tokens.md), from the Midnight-Ink token card.
- **G-2 — covers on dark ground. — ANSWERED 2026-11-11:** the dark Shelf exists
  (`screens/library/shelf-dark`); covers keep their own inks, raised where needed for
  legibility on `#16140F` (sepia ground `#5D2F17`, slate ground `#284457` in the render).
- **G-3 — primary/`on-primary` in dark mode. — ANSWERED 2026-11-11:** `#D39562`/`#1D140D`
  measures 7.7:1; binding.
- **G-4 — the Shelf's undrafted states. — ANSWERED 2026-11-11** (the G-4 round,
  run at W2's opening per the gap protocol): `screens/library/shelf-empty` (the empty
  state) and `screens/library/shelf-states` (loading skeleton, the error notice with its
  retry, the dense many-books grid, the long-title card).
- **G-5 — `muted` on `soft` fails AA in the norm itself** (measured 4.46:1 light /
  3.99:1 dark; surfaced by Task 3). The app keeps off that pairing, and no norm value is
  adjusted locally: the round decides (adjusted value or blessed exception), batched with
  G-4.

The first round ran as **task S0 of the plan** (complete): the dark shelf
(`shelf-dark`), the token card (`midnight-ink-swatches`), and the extracted values with
their divergences (`dark-tokens.md`) are in the archive. No dark value is derived
locally; the coordinator ran the round via MCP.

**Owner decisions (2026-11-11, builder check round):**

- **O-1 — pilot shelf: literal 1:1 as drafted.** Every drafted element ships; missing data
  renders from the least-invented honest source and every gap becomes a dedicated follow-up
  issue under the wave's index issue (§6.6). The recomposition option was dropped.
- **O-2 — screens amend the norms.** Area hues become identity accents within their area's
  surfaces (never a control fill); the component ladder grows to 32/36/40 px buttons and a
  4/8/12 px radius ladder; the `typeScale` gate's allowlist widens. See §5, §6.4, §6.5.
- **O-3 — hand-drawn icons stay.** The app's 16 px / 1.5-stroke set is extended with the
  drafted concepts; Material Symbols is not adopted. Deviation #1, §6.9.

## 8. Waves

| Wave | Scope | Proves | Plan |
| --- | --- | --- | --- |
| **S0** | first Stitch round: G-1, G-2, G-3, G-4, exported into the archive | the norm is complete before code moves | blocking, before W0 |
| **W0** | `globals.css` values per §6.2 (full surface ladder), PJS self-hosted, scale per §6.3, `--shadow-card`, dock 21 rem | the parchment ground under every existing surface, theme intact, gates green | this spec's plan |
| **W1** | chrome primitives per §6.5: buttons, inputs/select, covers, keycaps, notices/findings, ghost text, rail/topbar/dock chrome restyle | every control matches the drafts' component specs | this spec's plan |
| **W2** | the Shelf 1:1 per §6.6, `/design` gallery on the new pairs, re-shot master frames | the pilot: a real surface indistinguishable from its draft | this spec's plan |
| W3 | writing workspace, docks, ghost text in vivo | the heart | separate plan |
| W4+ | knowledge, planning canvases, chat, prompts/settings — one wave per area | the rest of the app | separate plans |

W0–W2 are one branch and one PR after this spec's plan; W3+ each get their own plan when
their turn comes, built on the hardened primitives.

## 9. Verification

Per wave: `just check`, the touched suites, axe AA in **both** themes, `typeScale.test`
updated to §6.3, E2E screenshots re-shot into `assets/screenshots/`, and — the fidelity
gate — a side-by-side (implemented surface vs archived WebP) in the PR description. The
`/design` route keeps showing the live token pairs as the living proof the command focus
norm demanded.

## 10. Left to the builder

- The oklch/hex form of each value pair (the app speaks oklch today; hex→oklch conversion
  is mechanical, the rendered result must not drift — keep hex where conversion rounds
  visibly).
- Subsetting and file layout for the PJS instances, mirroring the EB Garamond pipeline.
- Which existing components map to which drafted primitive, and the W1 task order.
- The E2E side-by-side mechanics (a comparison artifact per PR, not a new gate).
