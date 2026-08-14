// narrare-roman · mirrored Satzspiegel (Slice 5a).
//
// Binding-aware inside/outside margins for bound-book layout. In Typst,
// `#set page(margin: (inside: ..., outside: ..., top: ..., bottom: ...))`
// is automatically mirrored across the spread: with the default
// `binding: left`, the `inside` margin faces the spine on every page —
// left on recto (odd), right on verso (even). No explicit `flipping`
// flag exists in current Typst (0.15.x); the `inside`/`outside` keys
// ARE the mirroring mechanism.
//
// Default measure (text-block width) per paper, tuned so the B-format
// text block lands at ~96 mm (the bake-off baseline):
//
//   B-format (129 mm wide) → inside 18 mm + outside 15 mm = 33 mm
//                            ⇒ measure = 129 − 33 = 96 mm ✓
//
// Inside > outside leaves room for the binding (the typical Western-book
// asymmetry). Override via NarrareRomanConfig.margins (Python
// MirroredMargins → Typst dict with the four `*_mm` keys in mm).

// Default margins per `paper-size`. Returns a dict of Typst length
// values spread-ready for `#set page(margin: ...)`.
#let default-margins(paper-size) = {
  if paper-size == "b-format-129x198" {
    // ~96 mm measure (the bake-off baseline). Inside 18 > outside 15
    // for the binding gutter.
    (inside: 18mm, outside: 15mm, top: 22mm, bottom: 22mm)
  } else if paper-size == "a5" {
    // A5 (148 mm wide) → 115 mm measure.
    (inside: 18mm, outside: 15mm, top: 22mm, bottom: 22mm)
  } else if paper-size == "a4" {
    // A4 (210 mm wide) → 165 mm measure.
    (inside: 25mm, outside: 20mm, top: 25mm, bottom: 25mm)
  } else if paper-size == "letter" {
    // US Letter (216 mm wide) → 176 mm measure.
    (inside: 22mm, outside: 18mm, top: 22mm, bottom: 22mm)
  } else {
    // Custom / unknown paper — conservative defaults (the caller picked
    // custom paper, so the right answer is a sane fallback, not a panic;
    // they can always override via `margins`).
    (inside: 20mm, outside: 18mm, top: 22mm, bottom: 22mm)
  }
}

// Resolve effective margins: override-if-given, else paper default.
//
// `margins-override` is the Typst translation of the Python
// `MirroredMargins` model — a dict with the four `*_mm` keys holding
// numbers (millimetres). `none` (or empty) means "use the paper default".
#let resolve-margins(paper-size, margins-override) = {
  if margins-override == none {
    return default-margins(paper-size)
  }
  // The Python MirroredMargins model uses snake_case keys with `_mm`
  // suffixes (inside_mm, outside_mm, top_mm, bottom_mm). Translate to
  // Typst length values.
  (
    inside: margins-override.at("inside_mm") * 1mm,
    outside: margins-override.at("outside_mm") * 1mm,
    top: margins-override.at("top_mm") * 1mm,
    bottom: margins-override.at("bottom_mm") * 1mm,
  )
}
