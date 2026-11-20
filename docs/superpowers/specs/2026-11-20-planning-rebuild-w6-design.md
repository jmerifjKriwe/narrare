# Planning rebuild W6 — design

Date: 2026-11-20 · Status: awaiting owner approval after builder check
Continues the frontend rebuild (W0 demolition → W1 harmonization → W2 Welcome/Setup → W3 Shelf → W4 Workspace → W5 Knowledge — fully merged: #913 `e9ff009c`, #912 `89d568b2`, #923 merged 2026-11-19T17:11:56Z). W6 branches from post-#923 `narrare/main`; the knowledge E2E pattern and the W5 gap ledgers are on main.

## Intent and why

The planning capability gets its three web surfaces on the complete existing
backend, ported from **harmonized** Stitch drafts — the W5 pattern: brief
Stitch with the real fields, let it redraw what drifts, port only truth.
The wave opener retires the two small W5 follow-ups (#910, #911) so the
index thins before it grows again.

Planning is next because: backend complete (scenes aggregate, timeline
events CRUD, storyboard with structures/remap), drafts exist, and the
rebuild order (W5+ = Planning/Chat/Settings) names it first.

## Goals

- Three surfaces, real fields only: **Chronologie** (timeline events),
  **Storyboard** (chapter stages across four structures, scene drill-in),
  **Kausalitätsleiste** (the harmonized, shrunk causality strip over scene
  conflict→resolution chains).
- Stitch harmonization rounds for all three drafts before any porting.
- The knowledge E2E pattern repeated: a planning E2E suite (no LLM
  dependency — pure CRUD + deterministic structure math), de-DE, per-suite
  DB, two workers.
- The W6 gap ledger with follow-up children for everything honestly
  disabled (the invented causality/what-if scope, beat-sheet export,
  versioning tags, sync buttons, attachments, priority flags, syuzhet
  semantics).
- Three PRs: A (opener fixes + timeline) · B (storyboard + scenes) ·
  C (causality strip + E2E + ledger + wave gate).

## Non-goals

- No new backend. The existing planning API is the boundary; a missing
  endpoint is an honest disabled door + gap row (W5's create-entity
  ruling), never a shim.
- No chat, no settings — later waves.
- No what-if/multiverse engine — the causality draft's invented scope is
  gap rows, not deferred promises.

## Anti-goals

- Fake fields, dead-promise buttons, invented scores or percentages.
- A causality screen that is 95 % disabled area — the harmonized draft
  must be a real screen over real fields or it does not ship.

## Constraints

- The five standing rules (`docs/_shared/CONSTRAINTS.md`); rule 1 (no
  cross-capability imports) — findings badges and entity chips read
  knowledge's public cache keys only if the shell exposes them; otherwise
  they stay out (disclose per surface).
- SDD: task briefs → implementer → reviewer → fix round → re-review →
  whole-branch review → PR. Every dispatch names models. Quota reality:
  qwencloud dead until 2026-12-13 — both seats ride zai-coding-plan/glm-5.3
  (owner's standing seat-swap pattern; disclosed in every dispatch).
- Stitch alone designs: harmonization via Stitch MCP with real-field
  briefings; owner approves corrected drafts before porting.
- i18n: three catalogs, sorted parity, du-tone.
- Merge commits, conventional grammar, `User-visible:` for feat/fix/docs.

## Approaches (picked in conversation)

- **A — Harmonize-first, full scope (owner's pick).** Stitch rounds for
  drifting drafts, then port all three screens in three PRs. Costs rounds;
  never lies about fields.
- B — Port as drawn with gap rows. Rejected: the causality screen would be
  almost entirely disabled — a hollow screen is what W5's harmonization
  exists to avoid.
- C — Split: timeline-only mini-wave first. Rejected by owner (full scope).

## Decided in conversation

- **Novel-wide scene-derived data (builder check, my call — veto it if you
  disagree):** there is no bulk scenes endpoint, and none is built. One
  capability-local fan-out hook (e.g. `useNovelScenes`) reads the chapters
  list once, then each chapter's scene aggregate through the query seam —
  parallel, cached per chapter, invalidated per chapter on aggregate
  writes. A novel's chapter count (dozens, local-first single user) makes
  this honest; both the Kausalitätsleiste and the timeline's scene-status
  counters ride the same hook instead of inventing two mechanisms.
- **Kausalmatrix: harmonize and shrink.** The what-if/multiverse draft is
  replaced by a real-fields draft (working name Kausalitätsleiste): the
  scenes' conflict→resolution as an honest causal chain strip. The
  invented scope (branches, divergence %, twist parameters, anchors,
  paradox counters) becomes gap rows in the W6 ledger. The strip is a
  FRESH Stitch generate from the real-fields briefing (the old draft is
  retired chrome, not an edit round). **Fallback pre-authorized by the
  owner (2026-11-20):** if the owner rejects the first strip draft as too
  thin, PR C shrinks to two surfaces (timeline, storyboard) complete and
  honest, and causality waits as its own small wave for a better draft or
  a real backend — the wave does not block on redrafts.
- **Scenes live in the storyboard drill-in.** Scene editing (the
  chapter-aggregate PUT with its version stamp) happens through the
  storyboard's scene view. No workspace scene dock this wave — the
  aggregate's `version_updated_at` stays the prepared seam for a later
  dock ("the dock compares its snapshot against" — the schema already
  says so).
- **Wave opener:** #910 (last-relation focus drop) and #911 (TopBar mobile
  overflow) on the wave branch before the first surface, closing both from
  their own commits.
- **Routes:** `/novels/$novelId/planning/timeline`, `.../storyboard`,
  `.../causality` — root-parented like knowledge's, sub-navigation as the
  drafts' sibling-door mechanism draws it after harmonization.

## Draft↔backend delta (the harmonization brief's seed)

Real fields (the API is the authority):
- Scenes: title, purpose, conflict, resolution, beats[], status, position —
  per chapter, aggregate read/save with version stamp.
- Timeline events: title, description, chapter_id?, position?, date_label
  (free text), character_names (free text, no KB linkage).
- Storyboard: **five** structures (three-act — the default every unremapped
  novel reads — plus heros-journey, save-the-cat, five-act, seven-point)
  tiling the unit interval; chapters with stage assignments;
  suggest_stage(ratio); remap. The switcher offers all five.

Draft drift to harmonize away:
- chronology-timeline: two-track syuzhet semantics, "Konsistenzprüfung/
  Abgleichen" buttons, Kausalitätslücken counter, archive attachments,
  Schlüsselmoment flags, scene-status counters (computable, but the
  draft's wording promises checks that don't run).
- three-act-storyboard: scene-in-act conflation (real model: chapters in
  stages, scenes under chapters), version tags ("v2.4"), beat-sheet
  export, findings badges (cross-capability), fixed three-act vocabulary
  vs the four real structures.
- causality-matrix-plot-twist: everything except the chain-over-scenes
  idea; the old 12-area rail is retired chrome.

## Left to the builder

- Task breakdown and PR contents refinement at plan time (the W5 shape:
  ~8 tasks, one implementer/reviewer pair each).
- Exact catalog keys, testids, and the sub-navigation mechanism the
  harmonized drafts draw.
- The harmonization brief wording per draft (from the delta above).
- E2E legs per surface; the flake rules (two workers, ports, stack down).
