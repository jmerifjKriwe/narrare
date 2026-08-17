# pandoc vendor area — DOCX manuscript format (C3)

Holds the committed `reference.docx` that `PandocDocxRenderer`
(`apps/api/narrare/export/renderers/pandoc_docx.py`) passes to pandoc via
`--reference-doc` — unconditionally, with no template toggle (design
§6.1 + §11; the D7 no-silent-fallback principle applied to document
styles). The pandoc/typst vendor split mirrors `export/typst/` (engine
assets live under an engine-named directory).

## The manuscript format (design §6.1, binding)

| Property | Style | OOXML |
|---|---|---|
| Times New Roman 12 pt | `Normal` (+ `Heading2`) | `w:sz 24` half-points |
| 1.5 line spacing | `Normal` | `w:spacing w:line="360" w:lineRule="auto"` |
| 0.5″ first-line indent, every paragraph | `BodyText` (inherited by `FirstParagraph`) | `w:ind w:firstLine="720"` twips |
| Centred chapter headings | `Heading2` (chapters are `<h2>` in the assembled HTML) | `w:jc w:val="center"` |
| Title page in Times 14 pt | `Title` | `w:sz 28` |

## Provenance + regeneration

The asset is a deterministic patch of **pandoc's own default
`reference.docx`** (pandoc 3.10.1 — the pinned version from
`scripts/install_export_toolchain.sh`), produced by
`scripts/generate_reference_docx.py` (pure stdlib; fixed zip timestamps +
sorted entries → byte-reproducible for a given pandoc version).

Regenerate when the pandoc pin changes (or a format property is
deliberately changed):

```sh
pandoc --print-default-data-file reference.docx > /tmp/reference-base.docx
python scripts/generate_reference_docx.py \
  --base /tmp/reference-base.docx \
  --output apps/api/narrare/export/pandoc/reference.docx
```

Then regenerate the golden baseline (the two drift together):

```sh
uv run pytest tests/golden/export/test_docx_golden.py -v -m golden_pages \
  --golden-update -p no:xdist
```

Review both diffs, then commit. The generator never spawns pandoc
(RULE-08); the extraction command above is a shell command, not code.
The committed asset is pinned by
`tests/unit/api/export/test_reference_docx_asset.py` (style properties, no
pandoc needed) and by the reproducibility check in
`tests/golden/export/test_docx_golden.py` (asset == generator(pandoc
default) for the installed pandoc).
