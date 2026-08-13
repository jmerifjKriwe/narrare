// narrare-roman · per-language hyphenation (Slice 5e).
//
// Typst hyphenates automatically once a language is known
// (`#set text(lang: ...)` — set by the entry point from `config.language`).
// For justified paragraphs hyphenation is on by default (`text.hyphenate`
// is `auto`); this module owns the hyphenation FEATURE and the decision to
// force it on unconditionally (so hyphenation also applies to any
// non-justified spans), even though the `set text(hyphenate: ...)` rule
// itself must live in the entry point (Typst `set` rules are lexically
// scoped — see `quotes.typ` for the same constraint).
//
// Language-aware patterns (Typst's bundled hyphenation, probe-verified):
//
//   de  —  long compounds break at morpheme boundaries
//          (e.g. `Geschwindig­keits­über­schrei­tungs­kontrolle`).
//   en  —  standard English hyphenation.
//   fr  —  French hyphenation.
//
// The hyphen at a break point is a SOFT HYPHEN (U+00AD) in the text layer;
// it renders visibly only at line ends. Per-span `#text(lang: …)` spans
// hyphenate by their own language, not the document's.
//
// `hyphenate-for(language)` returns `true` for every supported language —
// de/en/fr all hyphenate. The entry point applies
// `set text(hyphenate: hyphenate-for(language))`.

// Whether to force hyphenation on for a given document language.
//
// All three supported languages (de/en/fr) hyphenate, so this is `true`.
// The decision is factored out so a future language that should NOT
// hyphenate (none today) has a single home.
#let hyphenate-for(language) = {
  if language == "de" or language == "en" or language == "fr" {
    true
  } else {
    // Unknown language — default to Typst's auto behaviour (hyphenate when
    // the language is known and the paragraph is justified).
    true
  }
}
