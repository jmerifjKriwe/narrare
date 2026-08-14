// narrare-roman · chapter drop cap (Slice 5g).
//
// A drop cap is the classic literary opener: the FIRST letter of a
// chapter's first paragraph set large, its lines wrapping beside it.
// Optional (config `drop-caps`, default OFF) — the classic form is a
// per-book choice, and the bake-off saw glyph collisions in community
// templates, so narrare-roman errs conservative: a 2-line cap with a
// small fixed gap (see Sizing below).
//
// The dropped capital itself is rendered by the VENDORED `droplet`
// package (`vendor/droplet/`, upstream 0.3.1, MIT — see its README for
// provenance). droplet is imported by RELATIVE path (`../vendor/…`),
// never via `@preview/droplet:…` — a relative import resolves inside the
// package tree and can never trigger a registry download at render time
// (the IO-001 D3 no-network constraint). Verified on Typst 0.15.1.
//
// ── Chapter-first-paragraph targeting (the hard part) ───────────────
// The cap must apply ONLY to the first paragraph after each level-1
// (chapter) heading. Two show-rule mechanisms were prototyped and
// REJECTED on Typst 0.15.1 (both verified empirically, not assumed):
//
//   1. `show par` + a consuming state flag (heading sets the flag,
//      first par clears it) — DOES NOT CONVERGE: the rule's output
//      depends on state that its own output mutates, so the layout
//      oscillates ("maximum grouping depth exceeded" with droplet in
//      the loop; an out-of-memory kill with a plain text restyle).
//   2. Query-based `show par` — introspection inside paragraph
//      realization risks circularity, and droplet's own grid-cell
//      paragraphs would need rule shadowing to avoid re-entry.
//
// The implemented mechanism is a PURE CONTENT TRANSFORM applied BEFORE
// realization: walk the body's top-level children; after each level-1
// heading, buffer the following INLINE run and wrap exactly that run in
// `dropcap[...]` when the paragraph closes. No show rules, no state, no
// introspection → nothing can oscillate or recurse, and when the feature
// is OFF the entry point does not even call the transform (byte-neutral
// by construction — no pass-through rule is registered either).
//
// The walk DESCENDS into transparent sequences (`child.has("children")`):
// the document the entry point receives nests the manuscript inside a
// phase function's result (`#body[…]`, see `src/numbering.typ`), which
// surfaces as one sequence child at the top level. Bare sequences are
// pure groupings — semantic containers (lists, blocks, headings, the
// TOC) are ELEMENTS with fields, never bare sequence children, so the
// recursion cannot leak into them (the TOC renders entries as text, not
// heading elements; verified against `src/toc.typ`).
//
// ── Typst 0.15.x wrinkles the walker respects (empirically pinned) ──
//   · Markup headings expose `depth` pre-realization (`=` → 1); `level`
//     is style-dependent and errors "not known at this point" outside
//     layout. pandoc (post F-1 shift) emits `=` chapters → `depth: 1`.
//   · Closures CANNOT mutate outer bindings ("variables from outside
//     the function are read-only"); a closure-based accumulator
//     silently drops content. All accumulation here happens in the
//     for-body via `+=` rebinds (which DO rebind outer scope) — no
//     closures.
//
// ── Conservative paragraph admission ────────────────────────────────
// A chapter earns a cap only if its first paragraph consists purely of
// the inline elements in `_inline-funcs` (prose: text, spaces, quotes,
// emphasis, links, …). A chapter opening with a list, quote, figure,
// divider, inline code, or anything unrecognized simply renders without
// a cap — never a broken layout (droplet cannot split containers/lists,
// per its README). Spaces (`space` is not a global constructor in
// 0.15.x — `[ ].func()` is the canonical derivation, same as droplet's
// own `util.typ`) and parbreaks are structural, not prose content.
//
// ── Config ──────────────────────────────────────────────────────────
// `config.drop-caps` (default `false`, mirroring
// `NarrareRomanConfig.drop_caps` / `PdfOptions.drop_caps`) gates the
// whole transform in the entry point. Sizing is fixed, not configured:
//
//   height  2 lines  — the conservative literary default (droplet
//                      scales the glyph so its BOUNDS span exactly two
//                      body lines, incl. leading); 3-line caps collide
//                      more easily (the bake-off lesson).
//   gap     0.25 em  — a hair of air between the cap and the aside
//                      text (~2.75 pt at 11 pt body). droplet's grid
//                      columns structurally cannot overlap; the gap
//                      keeps the optical separation comfortable.
//   justify auto     — inherits the body's `par(justify: true)` (5a).

#import "../vendor/droplet/src/lib.typ": dropcap

// Element constructor of a markup space (no global `space` in 0.15.x).
#let _space = [ ].func()

// Inline (prose) element constructors a capped paragraph may contain.
// Anything else closes the pending run — conservative by design.
#let _inline-funcs = (
  text,
  _space,
  smartquote,
  strong,
  emph,
  underline,
  overline,
  highlight,
  sub,
  super,
  link,
)

// True iff `child` is a chapter (level-1) heading in the markup sense
// pandoc produces (`= Title` → heading with `depth: 1`).
#let _is-chapter-heading(child) = {
  child.func() == heading and child.depth == 1
}

// Wrap the buffered inline run as a dropped-capital paragraph.
#let _droplet-cap(run, height-lines, gap-em) = {
  dropcap(height: height-lines, gap: gap-em * 1em, run.join())
}

// The content transform: `body` with each chapter's first paragraph
// drop-capped (see the module header for the mechanism + rejection
// record). Pure — no show rules, no state, no introspection.
//
// `height-lines` / `gap-em` default to the conservative sizing above;
// they exist as parameters so probes can exercise the transform in
// isolation, not as a config surface (5g ships fixed values).
#let apply-drop-caps(body, height-lines: 2, gap-em: 0.25) = {
  // A single-element body (no `.children`) has no chapter/paragraph
  // structure to walk — return it untouched.
  if not body.has("children") {
    return body
  }

  let out = ()
  let pending = false
  let buf = ()

  for child in body.children {
    if child.has("children") {
      // Transparent sequence (e.g. a phase function's result embedding
      // the manuscript) — descend with fresh walker state; a chapter
      // heading and its first paragraph always share one sequence.
      out += (
        apply-drop-caps(child, height-lines: height-lines, gap-em: gap-em),
      )
    } else if pending {
      if child.func() == parbreak {
        // Paragraph boundary: a buffered run IS the chapter's first
        // paragraph — cap it and consume the pending mark. An EMPTY
        // buffer (blank lines directly after the heading) stays
        // pending; consecutive parbreaks merge at layout anyway.
        if buf.len() > 0 {
          out += (_droplet-cap(buf, height-lines, gap-em),)
          buf = ()
          pending = false
        }
        out += (child,)
      } else if _is-chapter-heading(child) {
        // A new chapter opener ends any unflushed run UNcapped (the
        // defensive case — a well-formed body always carries a
        // parbreak between paragraph and next heading).
        if buf.len() > 0 {
          out += (buf.join(),)
          buf = ()
        }
        pending = false
        out += (child,)
        pending = true
      } else if child.func() in _inline-funcs {
        buf += (child,)
      } else {
        // Block-level or unrecognized element closes the pending run.
        // If prose was buffered, it ended right here — cap it; if the
        // chapter opened with this element (empty buffer), no cap.
        if buf.len() > 0 {
          out += (_droplet-cap(buf, height-lines, gap-em),)
          buf = ()
        }
        pending = false
        out += (child,)
      }
    } else {
      out += (child,)
      if _is-chapter-heading(child) {
        pending = true
      }
    }
  }

  // Body ended mid-paragraph after a chapter opener: flush the tail.
  if buf.len() > 0 {
    out += (_droplet-cap(buf, height-lines, gap-em),)
  }

  out.join()
}
