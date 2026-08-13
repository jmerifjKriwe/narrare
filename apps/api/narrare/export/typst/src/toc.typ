// narrare-roman · table of contents (Slice 5d).
//
// Lists chapter (level-1) entries with their page numbers, styled cleanly
// with a dot leader. The TOC lives in the **frontmatter** phase (Slice 5c's
// frontmatter — roman folios), so a typical document places `#toc()`
// inside its `#frontmatter[...]` block.
//
// ── Page numbers match the printed folios ───────────────────────────
// The page number shown for each entry is the *phase-relative folio* —
// the same value `folio-footer` prints in the page footer (computed by the
// shared `phase-folio` helper in `numbering.typ`). Body chapters show arabic
// restarting at 1; a frontmatter chapter (rare) would show roman. The TOC
// and the footers therefore never disagree — a reader navigates by the
// number they see printed.
//
// ── Gating on config.include-toc ────────────────────────────────────
// `toc()` renders nothing when `config.include-toc` is false. The entry
// point (`lib.typ`) reads that key and publishes it to this module via the
// `_toc-enabled` state (Typst has no mutable module variables, and `set`
// rules are lexically scoped, so a cross-component flag rides on document
// state — see `apply-toc-gate`). Default `true` (matches the
// NarrareRomanConfig default), so a `#toc()` with no gate renders.
//
// ── Outline entry customisation ─────────────────────────────────────
// Typst 0.15.x exposes `show outline.entry` (no `entry:` parameter on
// `outline` — that arrived in a later Typst). Each `outline.entry` carries
// `level`, `element` (the heading), and `fill` (the dot leader). The page
// number is computed from `it.element.location()`, not stored on the entry,
// so a custom entry is the only way to show the phase-relative folio.

#import "numbering.typ": phase-folio

// Document state carrying `config.include-toc`. Updated once by the entry
// point (via `apply-toc-gate`) before any `#toc()` is laid out.
#let _toc-enabled = state("narrare-include-toc", true)

// Publish `config.include-toc` to the TOC component.
//
// Called by the package entry point; emits a state update at the document
// root so every later `#toc()` reads the configured value.
#let apply-toc-gate(include-toc) = {
  _toc-enabled.update(include-toc)
}

// The TOC entry: heading title + dot leader + phase-relative folio.
//
// `level == 1` chapters render in bold (the book's primary structure);
// deeper levels (if a future slice adds them) render in regular weight.
//
// The dot leader (`it.fill`, a Typst `repeat`) MUST be wrapped in
// `box(width: 1fr)` — a bare `#it.fill` consumes all remaining inline
// width and pushes the folio onto a new line (three lines per entry
// instead of one). The `1fr` box constrains the repeat to the space
// between title and folio, yielding the canonical single-line layout
// `Chapter Title . . . . . . 1`.
#let _toc-entry(it) = {
  context {
    let phys = it.element.location().page()
    let folio = phase-folio(phys)
    // Fallback to the physical page number when no phase marker precedes
    // the entry (a document with chapters but no frontmatter/body markers).
    if folio == none { folio = str(phys) }

    v(0.5em, weak: true)
    block(width: 100%)[
      #if it.level == 1 {
        strong(it.element.body)
      } else {
        it.element.body
      }
      #box(width: 1fr)[#it.fill]
      #box[~#folio]
    ]
  }
}

// The table-of-contents component.
//
// Place inside `#frontmatter[…]`. Renders the outline (chapter entries with
// phase-relative folios + dot leader) when `config.include-toc` is true;
// renders nothing when it is false.
#let toc() = {
  context {
    if not _toc-enabled.get() { return }

    show outline.entry: _toc-entry
    outline(
      title: text(size: 1.3em, weight: "bold")[Contents],
      depth: 1,
    )
  }
}
