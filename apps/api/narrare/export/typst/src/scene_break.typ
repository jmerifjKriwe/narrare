// narrare-roman · scene-break ornament (Slice 5f).
//
// A scene break is a deliberate pause inside a chapter — a visual breath
// between scenes, rendered as a small centred typographic ornament rather
// than a blank line or a literal row of asterisks. This is the `folklore`
// `major-break` pattern (borrowed, not forked — see ADR-081): three glyphs
// centred on their own line, set off from the surrounding body by vertical
// space.
//
// ── How scene breaks surface in Typst ───────────────────────────────
// The normaliser (Slice 1) canonicalises scene breaks to `<hr>` in the
// semantic HTML. pandoc (`--to=typst`) maps `<hr>` to a `#divider()` call
// (empirically confirmed with pandoc 3.10.1 — see the Slice 5f report).
// `divider` is a Typst 0.15.x built-in element (the pandoc standalone
// template only *polyfills* it for typst < 0.15: `#let divider = if
// "divider" in std { divider } else { horizontalRule }`). The non-
// standalone output the renderer (Slice 6) feeds to narrare-roman therefore
// contains bare `#divider()`, which by default renders as a horizontal
// rule.
//
// This module restyles that construct as the book ornament via a
// `show divider` rule — exactly the seam ADR-081 anticipated ("style
// THAT construct as the ornament"). The rule is declared in the entry
// point (`lib.typ`); this module exports the transform it wires up
// (Typst `show` rules are lexically scoped — a rule set inside a called
// function would not reach `body`; see `src/opener.typ` for the same
// constraint and pattern).
//
// ── Config ──────────────────────────────────────────────────────────
// `config.scene-break-style` selects the ornament (default `"asterism"`
// = the centred spaced `* * *`). Only `"asterism"` is implemented today;
// the surface is reserved so a future slice can add glyphs (a fleuron, a
// dingbat) without changing the contract. An unknown style falls back to
// the asterism so a typo never produces a broken render.

// The divider → ornament transform.
//
// Returns a function `(it) => content` for use as
// `show divider: scene-break(style: config.scene-break-style)`. The
// `it` argument is the divider element (carries no fields narrare-roman
// needs — it is purely the marker pandoc emits for `<hr>`); the rendered
// ornament ignores it and draws fresh centred glyphs.
//
// `style` — the ornament id from `config.scene-break-style`. Today only
// `"asterism"` is honoured; any other value renders the asterism too
// (graceful fallback, never a broken layout).
#let scene-break(style: "asterism") = (it) => {
  // Only the asterism is implemented; reserve the surface for more.
  let glyphs = "* * *"

  // Centred block on its own line, set off from the body by vertical
  // space so it reads as a deliberate pause (the `folklore` major-break).
  // `v(..., weak: true)` collapses at a page top/bottom so the ornament
  // never leaves an awkward gap when a scene break lands at a page
  // boundary. The glyphs render slightly larger than the body for
  // presence; they come from a STRING literal so Typst does not parse
  // the `*` as emphasis markup.
  align(
    center,
    block[
      #v(1.2em, weak: true)
      #text(size: 1.6em, glyphs)
      #v(1.2em, weak: true)
    ],
  )
}
