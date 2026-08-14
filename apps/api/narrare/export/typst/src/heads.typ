// narrare-roman · running heads + is-page-empty suppression (Slice 5b).
//
// Running heads (the small title at the top of each body page) follow the
// traditional English-fiction convention:
//
//   - Verso (even / left page)  → book title   (`config.title`)
//   - Recto (odd  / right page) → chapter title (the most recent level-1
//                                  heading body)
//
// Three pages never carry a running head:
//
//   1. Chapter openers — the opener IS its own title; a head above it is
//      redundant. Detected by "a level-1 heading starts on this page".
//   2. Blank versos — the deliberately-empty page left when a chapter ends
//      on a recto and the next chapter must start on a recto. Detected by
//      the `is-page-empty` pattern (below).
//   3. (Pages before the first chapter — no chapter title yet; the recto
//      head is skipped until a level-1 heading exists. Frontmatter heads
//      are a 5d concern.)
//
// ── `is-page-empty` — borrowed pattern (not a fork) ───────────────────
// The blank-page detection is the load-bearing pattern borrowed from
// `wonderous-book` (ADR-081 calls it "the cleanest blank-fillers
// observed"). It does NOT try to inspect page content (which is brittle
// for paragraphs that span page breaks); instead it makes the blank pages
// *discoverable* by wrapping the parity-forcing pagebreak in a pair of
// metadata markers. A page is empty iff it falls strictly between a
// `<narrare-empty-page-start>` and its matching `<narrare-empty-page-end>`.
//
// This module owns the whole mechanism — the marker-placing
// `detectable-pagebreak` (called by the chapter opener, `src/opener.typ`)
// and the `is-page-empty` detector (called by the running head below) —
// because the two markers exist solely to serve blank-page head
// suppression. The label names ARE the contract between the opener
// (where a blank is created) and the head (where it is suppressed).
//
// Upstream: https://typst.app/universe/package/wonderous-book (MIT-0).
// Mirrored here (not imported) so the package is fully vendored (D3) and
// the blank-detection logic lives next to the feature that uses it.

// Wrap a parity-forcing pagebreak in discoverable markers.
//
// Emits `<narrare-empty-page-start>` before the break and
// `<narrare-empty-page-end>` after it. When the break inserts one or more
// blank pages, those pages lie strictly between the markers and are
// detectable by `is-page-empty`. When the break is a no-op (already on the
// target parity), both markers land on the same page and nothing is
// between them.
//
// `weak: true` keeps the 5a behaviour: the first chapter (page 1, an
// already-empty recto) does not get a leading blank.
#let detectable-pagebreak(to: "odd", weak: false) = {
  [#metadata(none) <narrare-empty-page-start>]
  pagebreak(to: to, weak: weak)
  [#metadata(none) <narrare-empty-page-end>]
}

// True when the current page is a blank inserted by `detectable-pagebreak`.
//
// The current page number is strictly between a marker pair iff a
// detectable pagebreak skipped over it. `here()` is the header's location
// (this is called from inside the running-head context).
#let is-page-empty() = {
  let page-num = here().page()
  query(<narrare-empty-page-start>)
    .zip(query(<narrare-empty-page-end>))
    .any(((start, end)) => {
      start.location().page() < page-num and page-num < end.location().page()
    })
}

// Build the running-head content for the current page.
//
// Returns a `context` block (evaluated once per page by `set page`) that
// emits the appropriate head or nothing. Used from the package entry
// point as `set page(header: running-head(title: ..., author: ...,
// preset: ...))`.
//
//   title  — book title (content or string). Verso (even) head.
//   author — author (content or string). Reserved for non-default
//            presets; the "default" preset puts the book title on the
//            verso (the cleaner single-string verso per ADR-081).
//   preset — `config.running-head-preset` (forward-compat knob,
//            tieffiction-style). Only "default" is implemented; other
//            values behave as "default" until a later slice adds presets.
#let running-head(title: "Untitled", author: "Anonymous", preset: "default") = {
  context {
    let i = here().page()

    // (1) Blank verso → no head.
    if is-page-empty() { return }

    // (2) Chapter opener → no head (the opener is its own title).
    if query(heading.where(level: 1)).any(it => it.location().page() == i) {
      return
    }

    // Most recent level-1 heading before this page (the current chapter).
    let chapters = query(selector(heading.where(level: 1)).before(here()))

    if calc.even(i) {
      // Verso (even / left page) → book title.
      align(left, text(size: 0.9em)[#title])
    } else {
      // Recto (odd / right page) → current chapter title. Before the
      // first chapter there is no chapter title to show, so skip.
      if chapters == () { return }
      align(right, text(size: 0.9em)[#chapters.last().body])
    }
  }
}
