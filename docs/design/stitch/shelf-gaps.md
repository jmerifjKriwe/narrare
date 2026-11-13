# Shelf — what is still a placeholder, and what replaces it

> **Status:** living document, committed with the Shelf fidelity repair (2026-11-13).
> Keep it current: when a follow-up issue closes, update its row here in the same
> commit. This is the single English list of every element on the shelf (and the
> shell's TopBar) that ships as a placeholder because the backend has no data yet.
>
> **Authority:** the composition norm is `screens/library/shelf.webp` / `shelf.html`
> (light) and `shelf-dark.webp` / `shelf-dark.html` (dark). The design decision is
> `docs/superpowers/specs/2026-11-13-shelf-fidelity-design.md` (§6 is this table's
> source). Values: `DESIGN.md`.

## Why placeholders exist

The owner's condition is 100 % fidelity to the drafts: **every drafted element
ships**, even where the app has no data for it yet. Dropping an element would break
the layout the owner approved; inventing a number would be a lie. So each missing
value renders as a **neutral that holds the draft's geometry** — the slot stays the
same size, in the same place, with the same type step, but its content is honestly
empty until the real source exists.

## The placeholder rules (owner decision 2026-11-13)

1. **Geometry is identical to the draft.** A placeholder never shrinks, moves or
   restyles its slot. The layout is the layout, full stop.
2. **Values are neutral where the app has no truth:** an em dash `—` for a missing
   number or name, an **empty bar track** for a missing progress target, a **flat,
   labeled curve** for a missing sparkline. Never an invented number, never a fake
   percentage, never a fabricated quote.
3. **Values are derived where the app has truth:** word counts, chapter counts,
   last-edited times, the book count, the library word total, the author name —
   these are real and render as themselves.
4. **A control whose action does not exist renders disabled**, with `aria-disabled`
   and an explanatory `title`, so it holds its place without promising behaviour.
5. **Every placeholder carries a code comment ending in its issue number**, beside
   the element it hides, so the neutral can never be mistaken for the finished
   thing and the replacement is one search away.

## The gap list

"Interim render" is what ships today. "Real-data trigger" is the backend or surface
that must exist before the neutral can become the drafted value. Each row's issue
carries the full trigger and the field's likely shape.

| # | Element | Draft shows | Interim render | Real-data trigger | Issue |
|---|---|---|---|---|---|
| 1 | Metrics streak | "14 Tage" | `—` | streak / session tracking | [#781](https://github.com/jmerifjKriwe/narrare/issues/781) |
| 2 | Banner goal / weekly / sparkline | 750 / 840 W/Tag / curve | `—`, `—`, flat labeled curve | goals + session tracking | [#782](https://github.com/jmerifjKriwe/narrare/issues/782) |
| 3 | Target (hero + cards) | "/ 60.000 Wörter" + % + bar | real words, `—` target, `—` %, empty track | per-book target field | [#783](https://github.com/jmerifjKriwe/narrare/issues/783) |
| 4 | Status pills | Entwurf / Planung / Lektorat | "Entwurf" for all | book status field | [#784](https://github.com/jmerifjKriwe/narrare/issues/784) |
| 5 | Search scope | "Titel, Figuren oder Tags…" | titles only | searchable figures / tags | [#785](https://github.com/jmerifjKriwe/narrare/issues/785) |
| 6 | Hero series line | "Band I • …" | `—` | series / band field | [#786](https://github.com/jmerifjKriwe/narrare/issues/786) |
| 7 | Statistics / goal doors | "Statistiken öffnen" | disabled button | statistics surface | [#788](https://github.com/jmerifjKriwe/narrare/issues/788) |
| 8 | Hero imprint + foot row | "Atelier Opus IV" | `—` (corner motif stays decorative) | imprint / series field | [#832](https://github.com/jmerifjKriwe/narrare/issues/832) |
| 9 | Hero eyebrow form | "Roman • Sci-Fi" | genre alone | book form / kind field | [#833](https://github.com/jmerifjKriwe/narrare/issues/833) |
| 10 | Cover author | "Calder" | author real; null → `—` | none — real data already | — |
| 11 | Filter panel | button only in draft | Stitch-round composition (`shelf-filter` / `shelf-filter-dark`), genre filter real | round export G-F1; further states | [#834](https://github.com/jmerifjKriwe/narrare/issues/834) |

### Reading the rows

- **Rows 1–7** are the pilot's missing-data children; they stay under the pilot
  index [#780](https://github.com/jmerifjKriwe/narrare/issues/780). This wave
  re-renders them at the draft's geometry but does not add their data.
- **Rows 8–9 and 11** are newly named by this repair and sit under the new index
  [#831](https://github.com/jmerifjKriwe/narrare/issues/831).
- **Row 10 (author)** is *not* a gap: `Novel.author` already exists. It is listed so
  the reader knows the cover's author line is real, and that a null author renders
  `—` by the same neutral rule — not because the field is missing.
- **Row 4 (status)** ships "Entwurf" for every book as the interim pill. The pill
  *component* is real and wears the drafted hues in both themes (see below); only
  the per-book status value is a placeholder until #784.
- **Row 11 (Filter panel)** is a composition gap, not a data gap: the draft draws
  only the button, so the panel goes through a Stitch round (G-F1) before it is
  built — never invented locally. The genre filter inside it is real client state;
  the states the export does not cover are #834.

## What is *not* a placeholder

These ship real and are listed so nobody mistakes them for gaps:

- **TopBar word chip** — the sum of `word_count` over the user's novels (derived,
  real). The breadcrumb's second slot is the active novel (max `updated_at`), the
  same source the shelf hero uses.
- **TopBar save chip** — fed by the shell's one sync bridge (`useSyncStatus`), in
  the approved `shell.sync*` vocabulary (deviation #2). It is a live status, not a
  placeholder.
- **Language chip** — the real locale switcher.
- **Hero / card word counts, chapter counts, last-edited times** — real.
- **Status pill hues** — the drafted light *and* dark hues are real tokens
  (`light-dark()` pairs), measured AA in both themes. The dark screen's hues win
  over the old token-card delta tolerance (owner decision D-6, spec §5.9).

## How a placeholder becomes real

1. Land the real source the row's issue names (a field, an endpoint, a surface).
2. Replace the neutral with the derived value at the element the code comment
   marks; delete the interim comment.
3. Update the row here (or remove it if nothing is left) in the same commit.
4. Close the issue from that commit: `Closes #<n>`. The index closes with its last
   child.

No placeholder is removed by deleting its slot — the slot is the draft's, and it
stays. Only the neutral content is replaced.