// narrare-roman · recto chapter opener + blank verso (Slice 5a).
//
// Chapter openers (level-1 headings, post F-1 promotion in Slice 6)
// start on a recto (odd) page. A chapter ending on a recto leaves a
// blank verso — that blank page must exist as a real, counted page in
// the folio (later sub-slice 5b suppresses its running head via the
// `is-page-empty` pattern, not the page itself).
//
// `pagebreak(weak: true, to: "odd")`:
//   - `weak: true`  — skip the break when the current page is already
//                     empty (so the very first chapter opens on page 1,
//                     not page 3).
//   - `to: "odd"`   — force the next content onto a recto (odd) page,
//                     inserting a blank verso if the previous chapter
//                     ended on a recto.
//
// F-1 (`--shift-heading-level-by=-1`) is applied at the pandoc call in
// Slice 6, so by the time the body reaches `narrare-roman`, chapters
// are level-1 headings.
//
// ── Why a heading-transform function, not a setup helper ───────────
// Typst's `show` rules are lexically scoped: a rule declared inside a
// called function does NOT propagate to the caller's body. The package
// entry point (`narrare-roman`) must own the `show heading.where(...)`
// declaration. This module exports the transform the entry point wires
// up — keeping the opener logic in one place without breaking scope.

// Heading transform: push a level-1 heading onto the next recto (odd)
// page. Used as `show heading.where(level: 1): recto-opener` from the
// entry point.
#let recto-opener(it) = {
  pagebreak(weak: true, to: "odd")
  it
}
