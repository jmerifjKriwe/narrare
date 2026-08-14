// narrare-roman · paper setup (Slice 5a).
//
// Maps the NarrareRomanConfig `paper-size` value (Python enum
// `PaperSize` in apps/api/narrare/export/options.py) to concrete page
// dimensions. The Python↔Typst coupling is a string match: the renderer
// (Slice 6) writes the PaperSize value verbatim into the config dict it
// passes to `narrare-roman`.
//
// B-format (129×198 mm) is the production default per ADR-081. Custom
// paper requires explicit width/height in mm; the function panics if
// they are missing — no silent fallback to a default size.

// Resolve `paper-size` to a dict spread-ready for `#set page(...)`.
//
// The returned dict carries either:
//   - `(paper: "a5" | "a4" | "letter")` — Typst's built-in size names, or
//   - `(width: <length>, height: <length>)` — explicit dimensions for
//     B-format and custom.
//
// Panics on an unknown `paper-size` value: an unknown paper is a contract
// mismatch between Python and Typst, not something to guess at.
#let paper-dimensions(
  paper-size,
  custom-width-mm: none,
  custom-height-mm: none,
) = {
  if paper-size == "b-format-129x198" {
    // B-format — 129 × 198 mm (production default, ADR-081).
    (width: 129mm, height: 198mm)
  } else if paper-size == "a5" {
    (paper: "a5")
  } else if paper-size == "a4" {
    (paper: "a4")
  } else if paper-size == "letter" {
    (paper: "letter")
  } else if paper-size == "custom" {
    if custom-width-mm == none or custom-height-mm == none {
      panic(
        "[narrare-roman] paper-size='custom' requires custom-width-mm and "
        + "custom-height-mm (in mm) — no silent fallback to a default size."
      )
    }
    (width: custom-width-mm * 1mm, height: custom-height-mm * 1mm)
  } else {
    panic(
      "[narrare-roman] unknown paper-size: " + str(paper-size)
      + " (expected one of: b-format-129x198, a5, a4, letter, custom)"
    )
  }
}
