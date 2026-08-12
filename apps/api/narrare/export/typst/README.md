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

## Current state — Slice 5a (geometric spine)

The **geometric spine** is implemented and probe-verified:

- **Paper size** — B-format 129 x 198 mm (default), A5, A4, Letter, or custom
  (`paper-size`, `custom-width-mm`, `custom-height-mm`).
- **Mirrored Satzspiegel** — binding-aware `inside`/`outside` margins
  (`margins`); paper-specific defaults (B-format: 96 mm measure).
- **Recto chapter starts** — every level-1 heading opens on a recto (odd)
  page (`pagebreak(weak: true, to: "odd")`).
- **Blank verso** — a chapter ending on a recto leaves a counted blank verso.
- **Body font + leading** — bundled Libertinus Serif (OFL), `leading-ratio`
  via `par(leading: (ratio - 1) * 1em)`.

Verified by `tests/golden/export/test_geometric_spine.py` (folio-count,
recto-start, blank-verso, mirrored-margin, and no-silent-font-fallback
probes via PyMuPDF). Bundled Libertinus Serif is the body font with no
fallback (`--font-path fonts/`).

The remaining scope-floor features land in **Slice 5b through 5f**, each
verified by its own probe before merge:

| Sub-slice | Feature |
|-----------|---------|
| 5b | Running heads recto ≠ verso + suppression on openers/blanks (`is-page-empty`) |
| 5c | 4-phase numbering (frontmatter roman → body arabic) |
| 5d | Table of contents |
| 5e | Per-language (de/en/fr) smart quotes + hyphenation |
| 5f | Scene-break ornament + widow/orphan protection |

Drop cap (5g) is an **optional fast-follow**, OFF by default.

See the Slice 5 sub-slice map in
[IO-001-export-pipeline.md](../../../../../../docs/architecture/implementation-plans/IO-001-export-pipeline.md)
for the file-by-file breakdown.

## Validate locally

```sh
bash scripts/install_export_toolchain.sh   # installs Typst
typst compile --root . <(echo '#import "apps/api/narrare/export/typst": *')
```
