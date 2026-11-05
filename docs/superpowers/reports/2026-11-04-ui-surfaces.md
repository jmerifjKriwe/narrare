# UI surfaces — typography, one column, narrow, theme · task report

Branch `fix/prose-typography`, worktree from `main` (`ffd7ab44`). Seven commits.
The first (`2cc7ec41`) carries the prose typography (its own report,
`2026-11-04-prose-typography.md`, and an independent review on a separate model).
The other six answer the review of the rendered UI: dark mode, 360 px, focus,
hover, settings and the dock.

| commit | surface |
| --- | --- |
| `1ee65b57` | the top bar's column and the icon/label gap |
| `819947c7` | `Row`/`GridList` flush, dense panel header inset |
| `f1a11182` | padded lists and the settings nav meet their headings |
| `78569eec` | the workbench: container 1200, dock height, narrow rail, one drawer |
| `44f2911a` | the shelf: language names, stacked hero, header wrap, title-only hover |
| `3ca48f96` | `color-scheme` |

## What changed, and why

**One left edge.** Measured on the README frames: the bar's place at 217 px, the
shelf heading at 241, the workbench's at 249. The bar centred a 1200 container in
the viewport while every page centred its own in the column the 48 px rail
leaves. The header now takes the rail's width as padding at the route's own
breakpoint, and the workbench container moves 1152 → 1200 (also the bar's and the
shelf's width), so bar, shelf and workspace start at 240. The knowledge (672) and
settings (1000) pages keep their reading measures and stay centred in their own
column; the bar's place cannot meet them, which is the one mismatch left.

**One inset.** `Row` carried `px-3` and every padded surface added its own on
top: chat sources began 12 px right of "Chat", knowledge hits 9 px right of
"HITS", the settings nav 12 px right of its heading. `Row`/`GridList` gained
`flush`; the padded surfaces pass it and own the single gutter. A dense panel's
header now follows its body's 10 px measure, so header and rows share an edge.

**The writing surface's air.** With the dock open the prose column was exactly
544 and the text touched the card's edge (4 px to the first glyph). The 1200
container leaves 592 with the dock open, so the measure centres with 24 px each
side; the measure itself is unchanged (F25), and the E2E that pins the container
now pins 1200.

**The dock's height.** `max-h-[50vh]` cut the entity list mid-row while 200 px of
the page stood unused. The dock now takes the height it needs up to the rail's
own cap (`calc(100dvh-16rem)`), keeps its title in place, and scrolls its body.

**Narrow.** Below 1024 the rail started open, so a phone visit landed on a
drawer over the text. Absence in the URL is now the breakpoint's decision (the
validator no longer writes `rail=true`); the toggle writes the explicit boolean.
Opening a dock retires an open rail drawer — the rail holds nothing that can be
lost — while opening the rail over a live dock covers it one z-step above,
without unmounting it: the dock's in-progress ask survives behind the drawer.
The place in the bar yields below
sm instead of truncating to "Dea…", and the shelf's two actions wrap to their
own line instead of overlapping.

**Shelf.** The raw language code (`en`) becomes the catalog's name ("English");
the continue-hero stacks below sm; the hover underline applies to the title only
(the whole card's five lines used to underline).

**Theme.** `color-scheme: light`/`dark` per theme, so scrollbars and native
option lists follow the tokens.

## Verification

One gate run covers the set (the tree was complete when it ran):

| gate | result |
| --- | --- |
| `just check` | ruff clean, pyright 0/0/0, tsc clean |
| `just test` | **691 passed** |
| `just test-frontend` | 33 files, **258 passed** |
| `just build` | ✓, 89 packages |
| `just test-e2e all` | **117 passed** |

Rendered proof (real stack, real API, real browser; images in
`/tmp/opencode/ui-review/`, not committed): light/dark shelf and workspace,
hover, keyboard focus, palette, settings, 360 px shelf, workspace, chat drawer
and rail drawer. The prose before/after is measured through `getComputedStyle`
in the T1 report.

Tests rewritten for changed contracts, in the same commits:
- `test_viewport_e2e.py` — the rail starts closed below 1024 and opens from the
  toolbar; the container pin moves to 1200; the dock's open retires the rail.
- `test_coherence_e2e.py` — the workspace face asserts the rail by width.
- `test_chat_e2e.py` — the normalized URL keeps `dock` and no longer gains
  `rail=true`; absence is a decision, not a default.

## Deviations, with reasons

- **Files per commit** exceeded the wave's 3-production-file rule in three
  commits (4, 5 and 5 files). The slices are one concern each — primitives,
  call sites, the workbench — and splitting them further would have separated a
  contract from its consumers. The whole set passed one `verify all`.
- **Container 1152 → 1200** deviates from §8.7's arithmetic. It is what gives
  the prose air with the dock open, and it puts the workbench on the same axis
  as the bar and the shelf; the F25 guarantee (a fixed measure) is untouched.
- **The bar's place is hidden below sm.** A 40 px fragment of the book title is
  worse than none when the page's own h1 is one line below.
- **Independent review** covers T1 only. T2–T6 were verified by the gates and
  the rendered sweep; a separate-model review of those six commits is still
  owed before merge.

## Open, not fixed here

1. **Real italics** — the subset has no italic face; `em` and blockquotes are
   synthesized. Needs EB Garamond Italic and `pyftsubset` (not installed).
2. **Soft line breaks** — a Markdown body wrapped at 80 columns keeps each
   newline inside the paragraph (ProseMirror's `white-space: pre-wrap`), so it
   renders as a hard break. Needs a product decision.
3. **The bundled demo's metadata block** (`## status`, …) now renders as real
   headings — a content fix, not a UI one.
4. **Dark covers** — the sepia cover reuses `--primary`, which in dark mode is
   the same bright fill as the primary action; a dedicated cover token would
   keep the object quieter than the button.
5. **Flaky gates** (from the T1 report): the chapter-selection race in
   `test_chapters_e2e.py` and the beforeunload assertion in
   `ChapterEditor.test.tsx` — `follow-up`, `area: writing`, `kind: flake`.
6. **Settings hub affordance** — its "doors" are headings with a hover
   underline only; the nav repeats the same three destinations.
