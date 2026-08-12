# Golden-Pages Acceptance Test Harness

The fire&forget robustness gate for manuscript export
([ADR-081](../../../docs/architecture/decisions/ACCEPTED/ADR-081-manuscript-export-pipeline.md) §"Quality gate", [IO-001](../../../docs/architecture/implementation-plans/IO-001-export-pipeline.md)).

Promoted from the disposable `_scratch/bake-off/` PyMuPDF probes (gitignored)
to a committed harness + corpus here. Each probe returns an objective metric;
together they are the acceptance test that a format renders correctly and
deterministically.

## Status — Slice 0 (scaffold only)

This directory tree (`corpus/`, `harness/`, `baselines/`) is the committed
**scaffold**. The probe implementations and corpus fixtures land in
**Slice 7** (Golden-Pages harness); the per-feature inline checks land with
their Slice 5 sub-slices. Nothing here runs yet — the layout exists so the
harness has a home from day one.

## Layout

```
tests/golden/export/
├── corpus/      committed manuscript fixtures (normalized TipTap HTML)
├── harness/     PyMuPDF-based probe library (Slice 7)
└── baselines/   committed expected values (regenerated via `just golden-update`)
```

## Corpus fixtures (Slice 7)

Committed, varied manuscript fixtures in the `NormalizedManuscript.semantic_html`
shape:

| Fixture | Exercises |
|---------|-----------|
| `de-prose.html` | normal German prose |
| `de-long-compounds-belastungsprobe.html` | long-compound stress (the bake-off *Belastungsprobe*) |
| `mixed-dialogue-de-en-fr.html` | de/en/fr dialogue + per-span `lang` |
| `chapter-opener.html` | chapter opener (recto start, optional drop cap) |
| `scene-break.html` | scene-break ornament |
| `novella/` (multi-chapter) | TOC, 4-phase numbering, running heads across a real booklet |

## Probe → assertion map (Slice 7)

Each probe returns an objective metric (no "looks about right" — every
assertion is machine-checkable):

| Probe | Asserts |
|-------|---------|
| `byte_reproducibility` | sha256 of two consecutive Typst renders is **identical** (the decisive Typst property) |
| `text_layer_tounicode` | copy of "find"/"Flame" yields correct codepoints (the SILE-disqualifying test — run against Typst to catch any ToUnicode regression) |
| `folio_numbering` | frontmatter folios are roman numerals; body folios are arabic (4-phase) |
| `running_header` | present on body recto+verso; **absent** on chapter openers + blank versos |
| `recto_start` | every chapter opener is on a recto (odd) page |
| `right_edge_max_error` | ≤ committed baseline (drift detection — Typst has no expansion) |
| `word_gap_stdev` | ≤ committed baseline (grey-value uniformity) |
| `scene_break_present` | the asterism renders (not as literal `* * *` text) |

## Baselines & regeneration

Baselines (sha256 of golden PDFs per fixture, max right-edge error, expected
folio counts) are **committed** and regenerated intentionally via a documented
`just golden-update` command (mirrors the VRT baseline workflow). Unintentional
drift = CI failure. Drift is the signal that `narrare-roman`, Typst, or pandoc
changed rendering — a human reviews and either fixes the regression or blesses
the new baseline.

## CI wiring (Slice 7)

- New pytest marker `@pytest.mark.golden_pages`, collected in the
  `test-integration` job (needs Postgres for the novel/chapter fixtures + the
  toolchain binaries installed via `scripts/install_export_toolchain.sh`).
- EPUBCheck gating: the EPUB-renderer golden test invokes `epubcheck` on the
  rendered EPUB; any validation error fails the test. EPUBCheck is provisioned
  by the toolchain script (`INSTALL_EPUBCHECK=1`) in CI only — it is not in the
  release image (PDF/EPUB/MD don't need it at runtime).

> Note: EPUBCheck is invoked from this test harness, **not** from production
> code. It is therefore deliberately **outside** RULE-08 confinement scope
> (only the two production render binaries, `typst` and `pandoc`, are
> confined to their renderer adapters).
