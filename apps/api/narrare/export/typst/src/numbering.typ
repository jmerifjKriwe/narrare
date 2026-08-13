// narrare-roman · 4-phase page numbering (Slice 5c).
//
// The literary-book folio convention — the `tieffiction` 4-phase model
// re-implemented (not forked) per ADR-081:
//
//   Phase 1 — Title page    folio suppressed (no number shown).
//   Phase 2 — Frontmatter   lowercase roman (i, ii, iii, …).
//   Phase 3 — Body          arabic (1, 2, 3, …), restarting at 1.
//   Phase 4 — Backmatter    arabic continued from the body (no reset).
//
// ── Where the folio lives ───────────────────────────────────────────
// The page FOOTER (bottom centre), separate from the running head
// (header / top — Slice 5b). The two never collide: the head carries
// the book / chapter title; the folio carries the page number. Both
// are suppressed on blank pages via the shared `is-page-empty` pattern.
//
// ── Mechanism ───────────────────────────────────────────────────────
// A single `folio-footer` context block — set as the page footer by the
// entry point — queries phase-start markers to determine the current
// phase, then formats the *phase-relative* page number. No page-counter
// resets: the relative number is computed from the physical page number
// minus the phase-start page, so blank pages (which increment the
// physical count but have their folio suppressed by `is-page-empty`)
// are handled naturally — a suppressed folio still "uses up" its number,
// matching traditional book pagination.
//
// Phase markers (`title-page`, `frontmatter`, `body`) place the
// phase-start metadata labels and manage the page breaks between
// phases. The Slice-6 wrapper wraps each manuscript section in the
// appropriate marker.
//
// ── Backmatter (Phase 4) ────────────────────────────────────────────
// The clean choice: the backmatter continues the body's arabic
// numbering (no separate counter reset, no separate marker). A
// `#body[…]` call already establishes arabic folios; any content after
// the body chapters — appendices, author note, colophon — simply
// continues counting. This mirrors the majority of trade-fiction
// imprints and avoids a fifth marker for no functional gain.
//
// ── Composes with 5a + 5b ───────────────────────────────────────────
// 5a — the body phase marker uses `detectable-pagebreak(to: "odd")` so
//      the body starts on a recto; any inserted blank verso is
//      discoverable for folio + head suppression.
// 5b — the folio and the running head share the `is-page-empty`
//      suppression. The folio is in the footer; the head is in the
//      header.

#import "heads.typ": detectable-pagebreak, is-page-empty

// The folio (page number) footer.
//
// Set as the page footer by the entry point (`lib.typ`). Determines the
// current phase from phase-start markers and formats the phase-relative
// number:
//
//   - Body pages (at/after `<narrare-body-start>`): arabic.
//   - Frontmatter pages (at/after `<narrare-frontmatter-start>`,
//     before body): lowercase roman.
//   - Title page / pre-frontmatter: no folio.
//
// Suppressed on blank pages (shared `is-page-empty` check).
#let folio-footer() = {
  context {
    // (1) Blank page → no folio (shared is-page-empty suppression).
    if is-page-empty() { return }

    let page-num = here().page()
    let body-start = query(<narrare-body-start>)
    let fm-start = query(<narrare-frontmatter-start>)

    // (2) Body phase — arabic, relative to body-start.
    // (3) Frontmatter phase — roman, relative to frontmatter-start.
    // (4) Title page / pre-frontmatter → neither branch fires → no folio.
    if body-start.len() > 0 and page-num >= body-start.first().location().page() {
      let base = body-start.first().location().page()
      numbering("1", page-num - base + 1)
    } else if fm-start.len() > 0 and page-num >= fm-start.first().location().page() {
      let base = fm-start.first().location().page()
      numbering("i", page-num - base + 1)
    }
  }
}

// Phase 1 — title page.
//
// No folio, no phase marker. The title page is the first content of
// the document; it precedes every phase-start marker so `folio-footer`
// renders nothing here. No page break is forced — the title page simply
// starts on physical page 1.
#let title-page(content) = {
  content
}

// Phase 2 — frontmatter.
//
// Lowercase roman folios (i, ii, iii, …), starting at i. Starts on a
// new page after the title page. Frontmatter sections (copyright, TOC,
// dedication — the TOC content itself lands in Slice 5d) flow
// continuously; they are NOT forced onto rectos (that constraint
// applies to body chapters only, via `recto-opener`).
#let frontmatter(content) = {
  pagebreak(weak: true)
  [#metadata(none) <narrare-frontmatter-start>]
  content
}

// Phase 3 — body.
//
// Arabic folios (1, 2, 3, …), restarting at 1. Starts on a recto
// (odd) page; the `detectable-pagebreak` makes any inserted blank
// verso discoverable for folio + head suppression. The body-start
// marker establishes the phase boundary queried by `folio-footer`.
#let body(content) = {
  detectable-pagebreak(to: "odd", weak: false)
  [#metadata(none) <narrare-body-start>]
  content
}
