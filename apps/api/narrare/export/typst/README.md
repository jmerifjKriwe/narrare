# narrare-roman

Bespoke **Typst package** for manuscript PDF export — vendored in-repo
([ADR-081](../../../../../../docs/architecture/decisions/ACCEPTED/ADR-081-manuscript-export-pipeline.md) / [IO-001](../../../../../../docs/architecture/implementation-plans/IO-001-export-pipeline.md)).

Loaded by `apps/api/narrare/export/renderers/typst.py`; never fetched at
render time. Narrare owns this package — it is **not** a community fork.

## Scope floor (D5)

The minimum viable book layout, verified by Golden-Pages probes (Slice 7):

- **Recto chapter starts** — every chapter opener on a recto (odd) page.
- **Blank verso** — the back of a recto opener is a deliberate blank.
- **Mirrored Satzspiegel** — symmetric inside/outside margins for bound books.
- **Running heads** — recto ≠ verso; suppressed on chapter openers and blanks.
- **4-phase numbering** — frontmatter folios in roman numerals, body in arabic.
- **Table of contents.**
- **Per-language smart quotes + hyphenation** (de / en / fr).
- **Widow / orphan protection** (justified body).
- **Scene-break ornament.**

Drop cap (5g) is an **optional fast-follow**, OFF by default.

## Borrowed patterns (not forks)

| Pattern | Borrowed from | Used for |
|---------|---------------|----------|
| `is-page-empty` | wonderous-book | blank-page running-head suppression |
| 4-phase numbering + header presets | tieffiction | frontmatter / body folio scheme |
| `major-break` | folklore | scene-break ornament |

## Font — Libertinus Serif (OFL)

Production body font, bundled for **reproducible output with no silent font
fallback** (the bake-off's headline fire&forget failure). Four variants live
in `fonts/`:

- `libertinus-serif-regular.otf`
- `libertinus-serif-italic.otf`
- `libertinus-serif-bold.otf`
- `libertinus-serif-bolditalic.otf`

License: [SIL Open Font License 1.1](fonts/LICENSE-OFL.txt), upstream
<https://github.com/alerque/libertinus> (vendored at v7.051). The same font
directory also feeds the EPUB renderer (pandoc `--epub-embed-font`) — one
bundled font, two embedding mechanisms, one font policy (D7).

## Current state — Slice 5f (scope floor complete)

The **geometric spine**, **running heads**, **4-phase numbering**, **table of
contents**, **per-language smart quotes + hyphenation**, **scene-break
ornament**, and **widow/orphan protection** are implemented and
probe-verified — the D5 scope floor (5a–5f) is complete:

- **Paper size** — B-format 129 x 198 mm (default), A5, A4, Letter, or custom
  (`paper-size`, `custom-width-mm`, `custom-height-mm`).
- **Mirrored Satzspiegel** — binding-aware `inside`/`outside` margins
  (`margins`); paper-specific defaults (B-format: 96 mm measure).
- **Recto chapter starts** — every level-1 heading opens on a recto (odd)
  page (`pagebreak(weak: true, to: "odd")`).
- **Blank verso** — a chapter ending on a recto leaves a counted blank verso.
- **Body font + leading** — bundled Libertinus Serif (OFL), `leading-ratio`
  via `par(leading: (ratio - 1) * 1em)`.
- **Running heads** — recto (odd) carries the **current chapter title**,
  verso (even) carries the **book title** (`title`, `author`,
  `running-head-preset`). Suppressed on chapter openers and on blank
  versos via the borrowed `is-page-empty` pattern (wonderous-book).
- **4-phase numbering** — title page (folio suppressed) → frontmatter
  (lowercase roman i, ii, iii) → body (arabic 1, 2, 3, reset at first
  chapter) → backmatter (arabic continued). The folio lives in the page
  **footer** (bottom centre), separate from the running head (header);
  both are suppressed on blank pages. Phase markers `title-page`,
  `frontmatter`, `body` delimit the sections (borrowed from
  tieffiction's 4-phase model). The shared `phase-folio` helper is the
  single source of truth for the folio computation — used by both the
  footer and the TOC, so they never disagree.
- **Table of contents** — `#toc()` (placed inside `#frontmatter[…]`)
  lists chapter entries with dot leaders and *phase-relative* folios
  (the same value the footer prints). Gated on `config.include-toc`
  (default true) via document state; renders nothing when false.
- **Per-language smart quotes + hyphenation** — Typst's smartquote engine
  converts straight quotes to language-appropriate typographic glyphs once
  `#set text(lang: …)` is active (en `"…"`, de `„…"`, fr `«…»`). Hyphenation
  is forced on (not left at Typst's justified-only `auto`) so it also
  reaches non-justified spans. The glyph/pattern contracts live in
  `src/quotes.typ` / `src/hyphenation.typ`.
- **Scene-break ornament** — a scene break (the normaliser's `<hr>`, which
  pandoc maps to `#divider()`) renders as a centred, spaced `* * *`
  asterism (the `folklore` `major-break` pattern), set off from the body
  by vertical space — not a literal asterisk paragraph. Gated on
  `config.scene-break-style` (default `"asterism"`; the surface is
  reserved for more glyphs). Wired via `#show divider` in
  `src/scene_break.typ`.
- **Widow / orphan protection** — ON by default (Typst 0.15 prevents
  widows and orphans automatically via its optimised line breaker;
  narrare-roman exposes the on/off switch as `text(costs: …)`, mapped
  from `config.widow-orphan-protection`). The pre-0.15
  `par(orphan-limit/widow-limit)` API no longer exists — see
  `src/body.typ`. Justified body is set by the entry point (`set
  par(justify: true)`, Slice 5a).

Verified by `tests/golden/export/test_geometric_spine.py` (folio-count,
recto-start, blank-verso, mirrored-margin, and no-silent-font-fallback
probes), `tests/golden/export/test_running_heads.py` (running-header
present-on-body, recto≠verso, absent-on-openers, absent-on-blanks probes),
`tests/golden/export/test_numbering.py` (frontmatter-roman, body-arabic,
body-resets-to-1, title-suppressed, blank-folio-suppressed probes),
`tests/golden/export/test_toc.py` (TOC-present-with-phase-relative-folios,
TOC-absent-when-disabled probes),
`tests/golden/export/test_quotes_hyphenation.py` (per-language quote-glyph
probes for de/en/fr + hyphenation-breaks-long-compound probe), and
`tests/golden/export/test_scene_break.py` (scene-break-renders-centred-
ornament + widow-orphan-protection-engages probes) via PyMuPDF.
Bundled Libertinus Serif is the body font with no fallback
(`--font-path fonts/`).

The D5 scope floor is **complete**. The only remaining Slice-5 item is the
**optional fast-follow**:

| Sub-slice | Feature |
|-----------|---------|
| 5g | Drop cap, default OFF (`@preview/droplet`) |

See the Slice 5 sub-slice map in
[IO-001-export-pipeline.md](../../../../../../docs/architecture/implementation-plans/IO-001-export-pipeline.md)
for the file-by-file breakdown.

## Validate locally

```sh
bash scripts/install_export_toolchain.sh   # installs Typst
typst compile --root . <(echo '#import "apps/api/narrare/export/typst": *')
```
