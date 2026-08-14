// narrare-roman · per-language smart quotes (Slice 5e).
//
// Typst converts straight quotes (`"` `'`) into language-appropriate
// typographic quotes automatically once `#set text(lang: ...)` is set (the
// entry point sets the document language from `config.language`). This
// module owns the smart-quote FEATURE — the single home for the
// per-language glyph contract and the enabled/disabled decision — even
// though the actual `set smartquote(...)` rule must live in the entry point
// (Typst `set` rules are lexically scoped: a `set` inside this module's
// helper would not reach the document body).
//
// Per-language quote forms (Typst's smartquote defaults, probe-verified):
//
//   en  →  " … "    (U+201C / U+201D)    and  ' … '   (U+2018 / U+2019)
//   de  →  „ … "    (U+201E / U+201C)    and  ‚ … '   (U+201A / U+2019)
//   fr  →  « … »    (U+00AB / U+00BB)    with narrow no-break spaces
//
// Per-span language: pandoc maps `<span lang="xx">…</span>` to
// `#text(lang: "xx")[…]`, so a German quotation inside an English document
// takes German glyphs for that span only (probe-verified). No extra work is
// needed here — Typst handles inline `#text(lang: …)` switches natively.
//
// ── Borrowed pattern ────────────────────────────────────────────────
// Not a fork: Typst's built-in smartquote engine IS the implementation;
// this module documents its behaviour per language and reserves the
// `smart-quotes-enabled()` decision surface for a future disable flag.

// Whether smart quotes are on for the document.
//
// Typst's default is on; this reserves the surface for a future
// `disable-smart-quotes` config key without changing the contract today.
// The entry point applies `set smartquote(enabled: smart-quotes-enabled())`.
#let smart-quotes-enabled() = true

// Per-language typographic double-quote glyphs — the SSOT contract for what
// each language renders (the Python probe asserts these independently).
//
// `open` / `close` are the bracketing glyphs Typst produces for straight
// `"` at the given language. French additionally inserts a narrow
// no-break space inside the guillemets (U+202F) — not modelled here; the
// probe checks for the guillemet glyphs themselves.
#let quote-glyphs = (
  en: (open: "\u{201c}", close: "\u{201d}"),
  de: (open: "\u{201e}", close: "\u{201c}"),
  fr: (open: "\u{ab}", close: "\u{bb}"),
)
