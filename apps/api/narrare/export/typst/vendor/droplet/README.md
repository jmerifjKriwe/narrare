# Vendored: `@preview/droplet` 0.3.1

Dropped capitals for Typst, vendored into the narrare-roman tree so
`typst compile` NEVER reaches the network at render time (IO-001 plan D3 —
no render-time package fetch). narrare-roman imports this copy via a
RELATIVE file path (`src/drop_cap.typ` → `../vendor/droplet/src/lib.typ`),
never via `@preview/droplet:…` — relative imports resolve inside the
`--root` package tree and cannot trigger a registry download under any
circumstances.

## Provenance

| Field    | Value |
|----------|-------|
| Package  | `droplet` (namespace `preview`) |
| Version  | `0.3.1` (latest on the registry at vendoring time) |
| Author   | Eric Biedert |
| License  | MIT (see `LICENSE` — permissive; vendoring + sublicensing allowed, notice retained) |
| Source   | <https://github.com/EpicEricEE/typst-droplet> |
| Registry mirror | <https://github.com/typst/packages/tree/main/packages/preview/droplet/0.3.1> |
| Vendored | 2026-08-14 (branch `feat/io-001-followups`, Slice 5g) |
| Compiler | upstream manifest declares minimum `0.11.0`; verified working on Typst **0.15.1** (see `src/drop_cap.typ` + the `test_drop_cap.py` probes) |

## Layout

Upstream sources with one deviation: `src/droplet.typ` had 4 instances of
trailing whitespace stripped by the repo's `trailing-whitespace` pre-commit
hook (whitespace-only, no semantic change — Typst ignores it). `assets/`
(example SVG/typ demo material, ~120 KB, not needed for compilation) was
excluded:

```
vendor/droplet/
├── LICENSE              upstream MIT (retained verbatim — required)
├── README.upstream.md   upstream README (API documentation)
├── typst.toml           upstream package manifest (provenance reference)
└── src/                 upstream sources (droplet.typ whitespace-normalized, see above)
    ├── lib.typ          entry point (re-exports `dropcap` from droplet.typ)
    ├── droplet.typ      the dropcap implementation
    ├── extract.typ      first-letter extraction
    ├── split.typ        word-boundary paragraph splitting
    └── util.typ         helpers (inline detection, to-string, …)
```

## Updating

Re-download from the registry mirror (file-exact, paths above), replace
`src/` + `typst.toml` + `LICENSE`, let the pre-commit whitespace hook
re-normalize (deviation above), bump the version row in this table,
then run the drop-cap probes (`tests/golden/export/test_drop_cap.py`) —
they are the empirical compatibility gate for a new droplet/Typst pair.
