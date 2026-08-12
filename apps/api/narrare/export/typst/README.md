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

## Current state — Slice 0 (skeleton)

This is the **package skeleton**: a valid `typst.toml` manifest, an importable
`lib.typ` entry point, and the bundled font. **No book features are
implemented yet.** They land incrementally in **Slice 5** (sub-slices 5a–5g),
each verified by its Golden-Pages probe before merge.

See the Slice 5 sub-slice map in
[IO-001-export-pipeline.md](../../../../../../docs/architecture/implementation-plans/IO-001-export-pipeline.md)
for the file-by-file breakdown.

## Validate locally

```sh
bash scripts/install_export_toolchain.sh   # installs Typst
typst compile --root . <(echo '#import "apps/api/narrare/export/typst": *')
```
