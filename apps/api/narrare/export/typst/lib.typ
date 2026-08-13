// narrare-roman — public entry point.
//
// Vendored Typst package for manuscript PDF export (ADR-081 / IO-001).
// Loaded by `apps/api/narrare/export/renderers/typst.py` via the package
// namespace; never fetched at render time. Narrare owns this package —
// it is **not** a community fork.
//
// ── Slice 5a scope ───────────────────────────────────────────────────
// Geometric spine: paper + mirrored Satzspiegel + recto chapter starts
// + blank verso. Verified by the folio-count + recto-start probes in
// `tests/golden/export/test_geometric_spine.py`.
//
// ── Slice 5b scope ───────────────────────────────────────────────────
// Running heads: recto ≠ verso (verso = book title, recto = chapter
// title), suppressed on chapter openers and blank versos via the
// `is-page-empty` pattern. Verified by the running-header probe in
// `tests/golden/export/test_running_heads.py`.
//
// ── Slice 5c scope ───────────────────────────────────────────────────
// 4-phase page numbering (title suppressed → frontmatter roman → body
// arabic → backmatter arabic-continued). The folio lives in the page
// FOOTER, separate from the running head (header); both are suppressed
// on blank pages. Phase markers (`title-page`, `frontmatter`, `body`)
// delimit the sections. Verified by the folio-numbering probe in
// `tests/golden/export/test_numbering.py`.
//
// ── Slice 5d scope ───────────────────────────────────────────────────
// Table of contents: `#toc()` renders chapter entries with dot leaders
// and *phase-relative* folios (the same value the footer prints — they
// never disagree). Lives in the frontmatter; gated on `config.include-toc`
// via the `_toc-enabled` document state. The shared `phase-folio` helper
// (extracted from `numbering.typ` in this revision) is the single source
// of truth for the folio computation. Verified by the TOC probe in
// `tests/golden/export/test_toc.py`.
//
// ── Slice 5e scope ───────────────────────────────────────────────────
// Per-language (de/en/fr) smart quotes + hyphenation. Typst's smartquote
// engine converts straight quotes to language-appropriate typographic
// glyphs once `#set text(lang: ...)` is active; hyphenation is forced on
// so it also reaches non-justified spans. The glyph/pattern contracts
// live in `src/quotes.typ` / `src/hyphenation.typ`; the `set` rules
// themselves live here (Typst `set` rules are lexically scoped). Verified
// by the quotes/hyphenation probe in
// `tests/golden/export/test_quotes_hyphenation.py`.
//
// Sub-slices still to land:
//   5f  scene-break ornament + widow/orphan protection
//   5g  drop cap (optional, default OFF — @preview/droplet)
//
// Borrowed patterns (not forks): wonderous-book `is-page-empty`;
// tieffiction 4-phase numbering + header presets; folklore
// `major-break` ornament.

#import "src/paper.typ": paper-dimensions
#import "src/margins.typ": resolve-margins
#import "src/opener.typ": recto-opener
#import "src/heads.typ": running-head
#import "src/numbering.typ": body, folio-footer, frontmatter, title-page
#import "src/toc.typ": apply-toc-gate, toc
#import "src/quotes.typ": smart-quotes-enabled
#import "src/hyphenation.typ": hyphenate-for

// Sentinel kept for back-compat with the Slice-0 skeleton; not used by
// the entry point. Bumped when the public API changes.
#let narrare-roman-version = "0.1.0-5e"

// ── Public API ───────────────────────────────────────────────────────
//
// `narrare-roman` is the package's only public entry point. The keys it
// reads from `config` ARE the stable Python↔Typst coupling surface —
// they mirror `NarrareRomanConfig` in
// `apps/api/narrare/export/contracts.py`. Changing a key is a
// coordinated Python+Typst change (the contract comment calls this out).
//
// Idiomatic use as a document-level show rule (the Slice-6 wrapper does
// exactly this):
//
//   #import "narrare-roman": narrare-roman, title-page, frontmatter, body
//
//   #show: narrare-roman.with(
//     config: (
//       paper-size: "b-format-129x198",
//       body-font: "Libertinus Serif",
//       body-size-pt: 11.0,
//       leading-ratio: 1.2,
//       margins: none,  // none → paper-specific default Satzspiegel
//       title: "My Novel",
//       author: "Jane Doe",
//       language: "en",
//     ),
//   )
//
//   #title-page[Book title + author]
//
//   #frontmatter[
//     Copyright, dedication (TOC content arrives in 5d).
//   ]
//
//   #body[
//     = Chapter One
//     ...
//   ]
//
// 5a reads only: paper-size, custom-width-mm, custom-height-mm,
// body-font, body-size-pt, leading-ratio, margins, language. 5b adds:
// title, author, running-head-preset. 5c adds the phase markers
// (title-page, frontmatter, body) — no new config keys (the numbering
// is structural, not configurable). 5d adds include-toc (gates `#toc()`
// — default true). 5e adds no new keys (smart quotes + hyphenation are
// driven by the existing `language` key). Later sub-slices extend the
// surface further (scene-break-style → 5f, …).
#let narrare-roman(
  config: (:),
  body,
) = {
  // ── Read config (kebab-case keys; defaults match NarrareRomanConfig).
  let paper-size = config.at("paper-size", default: "b-format-129x198")
  let custom-width-mm = config.at("custom-width-mm", default: none)
  let custom-height-mm = config.at("custom-height-mm", default: none)
  let body-font = config.at("body-font", default: "Libertinus Serif")
  let body-size-pt = config.at("body-size-pt", default: 11.0)
  let leading-ratio = config.at("leading-ratio", default: 1.2)
  let margins = config.at("margins", default: none)
  let language = config.at("language", default: "en")
  let title = config.at("title", default: "Untitled")
  let author = config.at("author", default: "Anonymous")
  let running-head-preset = config.at("running-head-preset", default: "default")
  let include-toc = config.at("include-toc", default: true)

  let page-dim = paper-dimensions(
    paper-size,
    custom-width-mm: custom-width-mm,
    custom-height-mm: custom-height-mm,
  )
  let resolved-margins = resolve-margins(paper-size, margins)

  // ── Paper + mirrored Satzspiegel.
  //
  // `margin: (inside: ..., outside: ...)` is binding-aware by default
  // (binding: left): inside faces the spine on every recto and verso,
  // mirrored automatically. No `flipping` flag exists in current Typst.
  set page(..page-dim, margin: resolved-margins)

  // ── Running heads (5b).
  //
  // Set as a separate `set page(header:)` rule so it composes with the
  // geometric setup above (Typst merges multiple `set page` rules).
  // `running-head` returns a `context` block evaluated once per page;
  // it suppresses itself on chapter openers and blank versos (see
  // `src/heads.typ`). `title`/`author`/`running-head-preset` are the
  // 5b config surface on `NarrareRomanConfig`.
  set page(
    header: running-head(
      title: title,
      author: author,
      preset: running-head-preset,
    ),
  )

  // ── Folio footer (5c).
  //
  // The page number lives in the FOOTER (bottom centre), separate from
  // the running head (header / top). `folio-footer` is a single context
  // block that determines the phase from markers placed by the phase
  // functions (`title-page`, `frontmatter`, `body`) and formats the
  // phase-relative number (roman for frontmatter, arabic for body,
  // suppressed on the title page and on blanks). Without phase markers
  // it renders nothing — so 5a/5b probe documents (which use none)
  // are unaffected. See `src/numbering.typ` for the 4-phase model.
  set page(footer: folio-footer())

  // ── Body font + leading.
  //
  // Bundled Libertinus Serif (D3) is the body font. The renderer
  // (Slice 6) passes `--font-path <package>/fonts` so the bundled OFL
  // files are the ones used — never a silent fallback. Missing
  // Libertinus at render time is a hard `ExportRenderError`, not a
  // fallback (the bake-off's headline fire&forget failure).
  //
  // Leading: `par(leading:)` is the inter-line gap. For a target
  // leading ratio R (line-to-line = R × font-size), the gap is
  // (R − 1) × 1em — expressed in `em` so it scales with font size.
  set text(font: body-font, size: body-size-pt * 1pt, lang: language)
  set par(leading: (leading-ratio - 1.0) * 1em, justify: true)

  // ── Smart quotes + hyphenation (5e).
  //
  // Typst's smartquote engine converts straight `"` / `'` to language-
  // appropriate typographic glyphs once `lang` is set (see `src/quotes.typ`
  // for the per-language glyph contract). `set smartquote(enabled: ...)`
  // is explicit and reserves the disable surface for a future config key.
  // Hyphenation is forced ON (not left at Typst's justified-only `auto`)
  // so it also reaches non-justified spans (see `src/hyphenation.typ`).
  // Both `set` rules live here — Typst `set` rules are lexically scoped.
  set smartquote(enabled: smart-quotes-enabled())
  set text(hyphenate: hyphenate-for(language))

  // ── Recto chapter openers + blank verso.
  //
  // Declared inline (not via a helper call) because Typst show rules are
  // lexically scoped — a rule set inside a called function would not
  // reach `body`. See `src/opener.typ` for the rationale + transform.
  show heading.where(level: 1): recto-opener

  // ── TOC gate (5d).
  //
  // Publish `config.include-toc` to the TOC component via document state
  // BEFORE the body is laid out — so a `#toc()` inside `#frontmatter[…]`
  // reads the configured value. The state update is emitted in the
  // content stream right before `body`; Typst has no mutable module
  // variables, and `set` rules are lexically scoped, so a cross-component
  // flag rides on document state (see `src/toc.typ`).
  apply-toc-gate(include-toc)

  body
}
