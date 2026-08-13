// narrare-roman · justified body + widow/orphan protection (Slice 5f).
//
// Two body-text invariants of a typeset book live here:
//
//   1. Justified body — flush left AND right margins (the trade-fiction
//      default for prose). Already established by the entry point (5a's
//      `set par(justify: true)`); documented here as the body module's
//      concern, NOT re-set (a second identical rule would be dead code).
//   2. Widow / orphan protection — no chapter ends with a stranded last
//      line at the top of the next page (a widow) or begins with a
//      stranded first line at the bottom of the previous page (an
//      orphan). Gated on `config.widow-orphan-protection` (default true).
//
// ── Typst 0.15.x widow/orphan API (a wrinkle) ───────────────────────
// The IO-001 plan prose mentions `#set par(orphan-limit: 2,
// widow-limit: 2)`. That API does NOT exist in Typst 0.15.x — it was the
// pre-0.15 spelling and was removed. Typst 0.15 prevents widows and
// orphans AUTOMATICALLY through its optimised line breaker (the
// `pagebreak` reference doc states: "Typst automatically manages
// pagination to prevent widows and orphans"). The fine-tuning surface is
// the `text(costs: ...)` dictionary: each cost is a percentage of the
// default, where `100%` is the default and `0%` disables that
// prevention. The keys are SINGULAR — `widow` and `orphan` (empirically
// confirmed; the plural spellings are rejected).
//
// So narrare-roman exposes the configured on/off switch as:
//
//   widow_orphan_protection = true  →  costs at the default level
//                                     (widow: 100%, orphan: 100%),
//                                     i.e. Typst's built-in prevention.
//   widow_orphan_protection = false →  costs: (widow: 0%, orphan: 0%),
//                                     i.e. prevention disabled.
//
// As with the other body-typography `set` rules (leading, justify,
// hyphenate, smartquote), the `set text(costs: ...)` rule itself lives
// in the entry point — Typst `set` rules are lexically scoped (a `set`
// inside this module's helper would not reach the document body). This
// module owns the DECISION (which costs dict the configured flag maps
// to); the entry point owns the APPLICATION.

// The `text(costs: ...)` dictionary for the configured protection state.
//
// `enabled` — `config.widow-orphan-protection` (default true). Returns
// the costs dict the entry point applies via `set text(costs: …)`.
// `true` maps to Typst's default prevention (100% / 100%); `false`
// disables it (0% / 0%). Returning the dict (rather than the entry
// point branching) keeps the on→costs mapping in this single home, so a
// future finer-grained knob (e.g. a configurable limit count) has one
// place to change.
#let widow-orphan-costs(enabled) = {
  if enabled {
    // Default-level prevention (100% = Typst's built-in default).
    (widow: 100%, orphan: 100%)
  } else {
    // Prevention disabled — widows and orphans may occur.
    (widow: 0%, orphan: 0%)
  }
}
