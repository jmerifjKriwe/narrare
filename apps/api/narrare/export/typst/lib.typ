// narrare-roman — public entry point.
//
// Vendored Typst package for manuscript PDF export (ADR-081 / IO-001).
// Loaded by `apps/api/narrare/export/renderers/typst.py` via the package
// namespace; never fetched at render time.
//
// ── Slice 0 scope ──────────────────────────────────────────────────────
// This is the package SKELETON: the shape that Typst can import without
// error, plus the bundled Libertinus Serif font (see `fonts/`). No book
// features are implemented here yet. They land incrementally in Slice 5
// (sub-slices 5a–5g), each verified by its Golden-Pages probe (Slice 7):
//
//   5a  paper + mirrored margins + recto chapter starts + blank verso
//   5b  running heads (recto ≠ verso) + `is-page-empty` suppression
//   5c  4-phase numbering (frontmatter römisch → body arabisch)
//   5d  table of contents
//   5e  per-language (de/en/fr) smart quotes + hyphenation
//   5f  scene-break ornament
//   5g  drop cap (optional, default OFF — @preview/droplet)
//
// Borrowed patterns (not forks): wonderous-book `is-page-empty`; tieffiction
// 4-phase numbering + header presets; folklore `major-break` ornament.
//
// Once a sub-slice lands, its module is re-exported from `src/` here.

// Placeholder sentinel so the package has a stable, importable surface from
// day one. Removed once the first real export (Slice 5a) lands.
#let narrare-roman-version = "0.1.0"
