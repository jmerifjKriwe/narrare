# WP2b — Context Budget and Continuation Assembly Design

**Date:** 2026-10-26 · **Status:** approved by the product owner, 2026-10-27
**Authority:** Fahrplan `docs/superpowers/plans/2026-10-25-v2-foundation.md` §5.4 (WP2),
narrowed by this design; architecture spec `2026-10-21-narrare-v2-architecture-design.md`.
Second half of the WP2 split (WP2a: providers, catalog, keychain, settings route — own
design doc). Builds on **merged WP2a**: the budget reads the resolved profile's
`context_window`/`max_output_tokens`/`temperature`.

## Intent

Continuation's context grows from one bounded tail into four budgeted slices. Today
`continuity_prompt` sends the novel title, chapter title, the last 4 000 characters of
the chapter (`NARRE_CONTEXT_CHARS`), and one instruction — nothing else. WP2b builds
the one allocator the kernel owns (`app/kernel/context.py`), with named slices and
token↔character conversion driven by the resolved profile, and fills continuation's
slices with what WP1 made available: the entities the tail actually references, the
predecessor chapters, and the novel's own genre/blurb as style hints. The 60/25/10/5
split the Fahrplan calls "kept" is v1 heritage (the v1 `WritingContextAssembler`); v2
has none of it — this design rebuilds it on v2 data.

## Goals

- **`app/kernel/context.py`, one allocator:** input is the resolved profile's
  `context_window` and `max_output_tokens`; `chars_per_token` is a **kernel constant
  in this module** (default **3.5** — German is token-hungry; not a profile field,
  WP2a D8). Output is a named character budget per slice. The budgets are **derived
  in characters and are an estimate, not a token guarantee**: real token counts vary
  by tokenizer, model and content, so the arithmetic keeps the margin implicit in
  3.5 rather than claiming exact token accounting (a provider-specific tokenizer is
  the trigger to revisit). The four budgets sum to
  `floor((context_window − max_output_tokens) × chars_per_token)` under one integer
  rule: every slice takes its floor, the remainder goes to the immediate-text slice,
  and a slice whose floor is zero stays zero — it is omitted at assembly time, never
  given free space (a small window loses style hints before it distorts the ratio).
  The window arithmetic **refuses a zero-room pair**: after the profile/catalog merge,
  `max_output_tokens >= context_window` raises `BudgetImpossibleError` naming the
  effective pair and the model — no clamp and no zero-input budget, because a
  continuation with no input room is not a usable call; the writing router maps the
  error to its one-frame error response (the `KeyUnavailableError` precedent), so the
  user sees why. The settings gate already refuses a both-set pair (shipped); this
  boundary check catches the catalog/profile merges the gate cannot see. The
  no-negative-slice invariant therefore holds by construction, and the reservation
  sent as `max_tokens` is always below `context_window`. The output reservation is not part of the input budget, so the
  input never exceeds `context_window − max_output_tokens`. **The reservation
  reaches the wire unconditionally:** continuation always sends `max_tokens` — the
  profile's `max_output_tokens`, or the 1 024 fallback when it is unset — so the
  reserve that sized the input budget is also the output limit the endpoint
  enforces, and input + reserved output never exceed the window (the anti-goal).
  `temperature` is sent only when the profile sets it. A profile carrying **one
  unset limit** gets that limit's default alone (`context_window` 8 192,
  `max_output_tokens` 1 024) — the allocator never receives `None`. The allocator is
  pure: same inputs, same budgets. Prompt scaffolding (section headings, title
  lines, the instruction) counts inside its slice — nothing rides free.
- **Continuation slices, 60/25/10/5 (code defaults):**
  - *Immediate text (60 %):* the chapter tail, as today, but budget-bounded instead of
    `NARRE_CONTEXT_CHARS`-bounded.
  - *Referenced entities (25 %):* the novel's entities whose `name` or an alias
    appears **case-insensitively** in the immediate text; their Markdown bodies in
    order of first occurrence until the slice is full; a body that no longer fits
    degrades to name + type; **if even that floor exceeds the remaining slice, the
    entity is skipped** — the slice never overflows, and the skip is silent (the
    budget is a bound, not a queue). A unit test pins both degradations.
  - *Recent chapters (10 %):* predecessors in `position` order, nearest first, their
    tails, until the slice is full.
  - *Style hints (5 %):* the novel's `genre` and `blurb`.
- **`NARRE_CONTEXT_CHARS` is deleted** from the tree; the allocator is the one context
  path. Continuation sends `temperature` when the profile sets it, and **always**
  sends `max_tokens` — the profile's `max_output_tokens` or the 1 024 fallback — so
  the reserve is a wire cap, not a planning number (an environment-tier or fake
  continuation therefore sends `max_tokens=1024` where it today sends nothing;
  recorded as the intended change).
- **The fake's `Usage` follows the constant:** the fake's `len // 4` divisor becomes
  integer division by the kernel constant — `int(len(text) / chars_per_token)` (floor,
  the same integer rule) — because `Usage` carries integer counts and the audit stores
  them as such; `compute_cost` never sees a fractional token count. The replacement
  WP0-A's plan promised WP2 (kernel-internal import, no boundary crossing); the
  pinning test moves with it.
- **Boundary:** writing reads novels, chapters and entities through the kernel's scoped
  repository base over the shared `kernel/contracts` models — no capability import
  (the models are shared domain by construction; `ENTITY_TYPES` in contracts is the
  precedent).
- **Fake stays answer-neutral:** the continuation prompt carries no `PURPOSE:`/
  `SOURCE:` marker before or after this change, so the fake's `CHUNKS` path and the
  ghost-text E2E are unaffected.

## Non-goals

- **Check and extraction keep WP0-C's caps:** the 20 000-character extraction bound and
  the check's chapter grouping are *data limits*, not context composition. §5.4's
  "every ad-hoc cap" narrows to `NARRE_CONTEXT_CHARS`; §5.4's second sentence ("the
  check and the extraction use the budget per chapter") is **dropped** (decided
  2026-10-26: reopening WP0-C's landed caps is risk without visible gain — 20 k chars
  ≈ 5.7 k tokens fits every real window).
- No embedding/trigram reference detection — the exact name/alias scan is the whole
  detector; §9.1's dedup tiers stay where they are.
- No suggested/pinned entity tiers (v1's richer splits stay v1), no rewrite/extend
  flows, no chat budget, no tokenizer (`tiktoken` stays rejected — estimates only).
- WP3's Markdown round-trip untouched: bodies are Markdown in, Markdown out — plain
  text here.

## Anti-goals

No silent overflow: a slice is visibly bounded and the allocator's numbers are
assertable. No unbounded growth with chapter or entity count — fixed fractions of a
fixed window. No second context path beside the allocator. No capability cross-import.

## Constraints

House rules as always (one capability one folder, generated routes, scoped
repositories, en/de/fr same commit, conventional commits with `User-visible:`, E2E on
real stack with the fake only at the LLM boundary, `assert_accessible`,
`just check`/`just verify`). Provability rides the row WP0-A built: the slices are
asserted on `LlmCall.prompt_text`, not on prose.

## Approaches (build decomposition)

1. **Allocator only, slices deferred** — rejected by the product owner 2026-10-26: one
   filled slice is ceremony without product value; the data exists since WP1.
2. **Allocator + assembly + check/extraction migration** — rejected 2026-10-26:
   reopens WP0-C's just-landed caps for no user-visible gain.
3. **Allocator + continuation assembly** — **chosen** (product owner, 2026-10-26).
   Tasks, house pattern:
   - **T1** `kernel/context.py` allocator: budgets, defaults, token↔char; property
     tests (`hypothesis`, accepted in §2): the four integer budgets sum exactly to
     `floor((context_window − max_output_tokens) × chars_per_token)` on ordered
     pairs, equality and greater-than are refused with `BudgetImpossibleError`
     (never clamped), no slice negative, zero-floor slices stay zero and are omitted
     at assembly, one unset limit falls back alone, and a tiny window degrades
     deterministically.
   - **T2** Assembly in writing: reference scan, predecessor tails, style hints; the
     rebuilt prompt; unit tests over fixture novels (entities found by alias,
     case-insensitive; predecessor order nearest-first; slice fill stops at budget;
     **a catalog/profile merge where the catalog's window falls below the profile's
     reservation is refused by name**).
   - **T3** Wiring: profile facts flow into the request (`temperature` when set;
     `max_tokens` always — the effective reservation); `NARRE_CONTEXT_CHARS`
     deleted; existing continuation tests green.
   - **T4** E2E + Fahrplan overwrite (§5.4 narrowed as above).

## Decisions (2026-10-26, product owner)

- **D1 — Four slices, 60/25/10/5 as code defaults** (overridable only in code, not per
  request).
- **D2 — Reference detection** is the case-insensitive exact name/alias scan over the
  immediate text, first-occurrence order; no fuzzy tier (that is §9.1, later).
- **D3 — Budget defaults** 8 192 / 1 024 when no profile resolves; they feed the
  arithmetic **and** the request: the effective reservation is sent as `max_tokens`
  (profile value or fallback), while `temperature` stays absent when unset.
- **D4 — WP0-C caps stay** (see Non-goals); recorded against §5.4.
- **D5 — Baseline:** the WP2b plan is written against **merged WP2a**, naming the
  landed symbols (`ResolvedProvider` and its facts) from the tree, not from a design;
  the small-`context_window` E2E profile is created through the real settings form,
  which WP2a ships.
- **D6 — Integer rule:** per-slice floor, remainder to the immediate-text slice,
  zero-floor slices omitted at assembly (never padded); the arithmetic is an estimate
  in characters, not a token guarantee.
- **D7 — Missing limits:** each unset limit falls back to its default independently
  (8 192 / 1 024); the allocator never receives `None`.
- **D8 — Zero-room boundary:** a merged pair with `max_output_tokens >=
  context_window` is refused (`BudgetImpossibleError`, naming the pair), never
  clamped — a zero-token window is not a usable continuation. The profile gate
  refuses both-set pairs; the boundary catches catalog/profile merges.

## Left to the builder

- Prompt section wording (English prompt text) and slice headings.
- Body degradation mechanics (name+type floor, skip when the floor does not fit; hard
  cut at the budget, no sentence surgery).
- Unit vs E2E split; i18n surface is minimal (no new UI beyond what exists).

## Done criterion

E2E on the real stack: a novel whose open chapter's tail names an entity (by alias,
different case), with predecessor chapters and a genre/blurb set; run a continuation;
assert on `LlmCall.prompt_text` that the referenced entity's name/body, a
predecessor's tail and the genre are present. With a small-`context_window` profile
the same prompt measurably shrinks (slice bounds hold — assert the prompt's section
lengths against the computed budgets). Ghost text still streams; `assert_accessible`;
`just verify` green. `NARRE_CONTEXT_CHARS` gone from the **runtime source files**
(`rg -n NARRE_CONTEXT_CHARS app web` clean; design and history documents may name
it — this document does).

## Carry-forward

WP1 final-review findings fold into the WP2b implementation plan as binding
constraints; they are not design input. WP2a review findings likewise — WP2b builds on
merged WP2a.
