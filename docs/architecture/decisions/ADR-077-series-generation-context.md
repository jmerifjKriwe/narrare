# ADR-077 — Series Generation Context (SERIES-002 — Spec 2: Series History Tier + Band Summaries)

> **Status:** ✅ Implemented (implemented 2026-08-02 across all layers + committed; Core → Backend → Frontend vertical slices. Originally planned as "ADR-076" — see §Numbering Note below.)
> **Date:** 2026-08-02
> **Deciders:** Architecture Specialist; Coordinator (plan-driven execution of the Spec 2 design)
> **Supersedes:** —
> **Related:**
> ADR-075 (Series Foundation — Spec 1; this ADR is its Spec 2 successor and consumes the `find_merged_for_novel` + `SeriesSettings` hooks Spec 1 pre-built),
> ADR-025 (Feature Adoption Infrastructure — `{{series_history}}` is a governed SYSTEM_VAR registered in `variable_registry.py` per the RULE-22 producer→consumer contract),
> ADR-067 (Reusable KB-Context Provider — the `SeriesHistoryProvider` Backend→Core bridge mirrors the `KBContextProvider` pattern),
> ADR-074 (Author Voice Storage — the `{{series_history}}` variable is a sibling generation variable to `{{author_voice}}`),
> ADR-022 (LLM Wiki — the recency-window "sacrifice older first" budget discipline echoes the WikiSummary token discipline),
> CONSTRAINTS.md RULE-02/02a/02b/03/04/06/07/11/14/17/22,
> CR-04 (cross-feature coherence — the KB-Redirect reuses Spec 1's scope repository)

> **Scope of this ADR:** the **Series Generation Context** — how writing a
> novel that belongs to a series receives the *state-at-(N−1)* of the prior
> bands at generation time. That is: the `BandSummary` per-novel summary
> entity, the `BandSummaryAgent` that produces it, the **Recency-Window**
> `SeriesHistoryTier` that assembles the `{{series_history}}` prompt block, the
> **Triple-Trigger** generation policy, the **KB-Redirect** that switches the
> KB read-path to Canon+Overlay for series novels, and the user-facing
> **Band Summary Card** (auto-generated text + manual override).
>
> Out of scope here: Series Voice Hierarchy (Spec 3), Cross-Novel Drift
> (Spec 4), Series Export (Spec 5). Each is downstream program work flagged in
> ADR-075's program decomposition but not designed here.

> **Numbering Note.** The Spec 2 implementation plan and the Alembic migration
> `0038_band_summaries.py` docstring both reference "ADR-076" as the planned
> home for this decision. Between the Spec 2 implementation (2026-08-02) and
> the writing of this ADR, the number **ADR-076 was claimed** by
> [ADR-076](ADR-076-current-state-volatility-policy.md) (CURRENT_STATE.md
> Volatility Policy, 2026-08-03). Rather than rename an already-accepted,
> CI-enforced ADR (the volatility policy backs `check_current_state_facts.py`
> + a pre-commit hook), this decision takes the next free number, **ADR-077**.
> The migration docstring's "ADR-076" reference is now a stale pointer to this
> ADR-077 (minor doc-debt; see Review Trigger).

---

## Context

### Why this ADR exists

ADR-075 (Spec 1) delivered the Series foundation: the `Series` entity, the
hybrid KB (Series-Canon + Novel-Overlay), and the `SeriesSettings` sibling —
and deliberately stopped short of *generation*. Its Review Trigger recorded
the open Spec 2 question:

> *"When Spec 2 (Series Generation Context) is implemented — verify generation
> calls `KBRepository.find_merged_for_novel()` correctly … and that the token
> budget for the merged set is sane."* — ADR-075 Review Trigger

Spec 1 pre-built the `find_merged_for_novel()` method and left the
`SeriesSettings.author_voice` column empty, but writing book N of a series
still saw **no prior-band context**. A series writer generating book 3 had to
re-explain the magic system, re-state where book 2 ended, and re-introduce
characters the AI had "met" before — the exact cross-novel drift Spec 1's data
model was built to prevent, now needing a generation-time consumer.

**This ADR is that consumer.** It closes ADR-075's Spec 2 Review Trigger.

### Verified state (grounded, not assumed — per architectural-discipline §7)

| Concern | State | Location |
|---------|-------|----------|
| `find_merged_for_novel` (Canon + latest-Overlay merge) | EXISTS — pre-built in Spec 1; Spec 2 consumes it via the KB-Redirect. | `apps/api/narrare/kb/scope_repository.py` |
| `SeriesSettings.context_window_size` | **DID NOT EXIST** before this ADR — now added (migration `0038`, default 3). | `apps/api/narrare/series/models.py:65`, `packages/core/narrare_core/series/schemas.py:43` |
| `band_summaries` table | **DID NOT EXIST** before this ADR — now created (migration `0038`). 1:1 to `novels` (`novel_id` PK + unique FK `ON DELETE CASCADE`). | `apps/api/narrare/series/band_summary_models.py`, `apps/api/alembic/versions/0038_band_summaries.py` |
| `{{series_history}}` governed variable | **DID NOT EXIST** before this ADR — now a registered SYSTEM_VAR (RULE-22). | `packages/core/narrare_core/prompts/variable_registry.py:114`, `route_table.py:108` |
| Writing pipeline `series_history` kwarg | **DID NOT EXIST** before this ADR — now threaded through `WritingContext` → `WritingPipeline.generate` → `{{series_history}}`. | `packages/core/narrare_core/writing/{models.py,pipeline.py,_stages.py,context_assembler.py}` |

### Where this sits in the Series program

Spec 2 is the second of five sequential specs (ADR-075 §program-level
decomposition). It depends on Spec 1 (implemented) and is itself a prerequisite
for Spec 4 (Cross-Novel Drift, which extends the series-history read path).

---

## Decision Drivers

- **RULE-02/02a/02b** — The band-summary prompt is a governed Mode-1 template
  (`_bundled/analysis/{lang}/band_summary/system.md`) resolved via
  `PromptComposer`; chapter summaries flow as runtime content in the agent run
  prompt (category 3 — user channel), never as an inline service f-string.
  `{{series_history}}` is a SYSTEM_VAR assembled by the Backend, not built in
  a service.
- **RULE-03** — `BandSummaryRepositoryProtocol`,
  `BandSummaryServiceProtocol` (`band_summary_contracts.py`) exist before the
  service/repository. The Core `SeriesHistoryTier` + `BandSummaryData` value
  type exist before the Backend provider.
- **RULE-04/06** — Modularise; one responsibility per file. Band-summary
  persistence (`band_summary_models.py`), generation (`band_summary_service.py`),
  auto-trigger (`band_summary_auto_trigger.py`), the history tier
  (`context/series_history.py`), and the Backend bridge
  (`series_history_provider.py`) are each their own module.
- **RULE-07** — `SeriesHistoryTier` is pure Core (zero `apps/` imports, no I/O);
  every DB read lives in the Backend `SeriesHistoryProvider`. Core defines the
  contract; Backend fetches the data.
- **RULE-11** — Graceful degradation everywhere: a standalone novel, band 1 (no
  prior bands), a missing summary row, an empty window, or a too-small token
  budget all yield an empty `{{series_history}}` block — generation proceeds
  unchanged, never crashes.
- **RULE-14** — The `band_summaries` table + the `series_settings.context_window_size`
  column land in ONE atomic Alembic migration (`0038`) with `upgrade()` +
  `downgrade()`.
- **RULE-17** — Frontend `BandSummary` / `BandSummaryOverrideRequest` types
  mirror the backend Pydantic schemas (snake_case preserved).
- **RULE-22 / CR-04** — `{{series_history}}` is a governed SYSTEM_VAR with a
  fixed producer→consumer contract; the KB-Redirect reuses Spec 1's
  `find_merged_for_novel` rather than introducing a second merge path.

---

## Options Considered

### Decision 1 — How to represent "what happened in prior bands"

**Option A — Replay raw chapter summaries.** Inject the prior bands' chapter
summaries directly into the prompt.
- **Rejected.** Token-explosive (a 10-book series × 30 chapters = hundreds of
  summaries), unbounded, and offers no curation. The AI drowns in detail and
  the prompt budget collapses.

**Option B — One summary per band, generated once, overrideable.** *(CHOSEN.)*
A `BandSummary` row per novel holds an auto-generated `full_summary`
(multi-paragraph) + `short_summary` (one sentence) + an optional user
`override`. The tier selects which to use based on recency. Bounded
(one row/band), curatable (override), and token-aware (short vs full).

**Option C — Per-band wiki entries.** Reuse the LLM Wiki (ADR-022).
- **Rejected as the primary path.** The Wiki summarises *KB entities*, not
  *narrative progress across a band*. The recency-window + override semantics
  are band-specific. (Wiki summaries remain a complementary context source.)

### Decision 2 — Recency strategy (which bands get the full summary)

**Option A — All bands equal.** Every prior band gets its full summary.
- **Rejected.** Does not scale (Perry-Rhodan 1000 books) and wastes tokens on
  ancient bands the current book barely references.

**Option B — Fixed last-N window.** The last `K` bands get the full summary;
older bands get only the one-sentence `short_summary`.
- **CHOSEN.** `K = SeriesSettings.context_window_size` (default 3, user-tunable).
  Respects recency (recent events matter most), bounds the token cost, and
  degrades gracefully (older bands still contribute a sentence).

### Decision 3 — Token-budget pressure policy

**Option A — Uniform truncation.** Cut every entry proportionally.
- **Rejected.** Mangles every summary; no band stays coherent.

**Option B — Sacrifice older first.** Emit newest-first; the first entry that
  doesn't fit fully is truncated to the remaining headroom (if meaningful);
  all older entries are dropped.
- **CHOSEN.** Keeps the most recent context intact and coherent; older context
  is the cheapest to lose. Mirrors the "keep most recent" discipline.

### Decision 4 — KB read-path for series novels (the KB-Redirect)

**Option A — Keep per-novel KB query.** `WHERE novel_id = X` (the standalone
  path). Silently excludes Series-Canon.
- **Rejected.** A series novel generating book 3 would not see the shared
  magic system / canon characters — the entire point of Spec 1's hybrid KB.

**Option B — Redirect to merged Canon+Overlay.** *(CHOSEN.)* Series novels use
  `find_merged_for_novel()` (Canon + latest-Overlay, Overlay wins on slug
  collision — the method Spec 1 pre-built); standalones keep the per-novel
  query. The `SeriesHistoryProvider.resolve_kb_fetch_mode()` encodes the
  decision: `"merged"` for series novels, `"per_novel"` otherwise.

### Decision 5 — When to generate a band summary (the Triple-Trigger)

Three independent generation paths, all funnelling through
`BandSummaryService.generate`:
1. **Manual** — explicit `POST /series/{id}/novels/{novelId}/band-summary`
   (the "Regenerate" button in the Band Summary Card).
2. **Auto on series completion** — when the series transitions to `completed`,
   `enqueue_band_summaries` best-effort enqueues a generation task per member
   novel (TaskIQ; individual failures are logged, never abort the transition —
   RULE-11).
3. **Lazy on-demand** — `get_or_generate()` returns an existing summary if
   present, else generates one. Used so the tier never blocks on a missing row.

*(CHOSEN — covers explicit, lifecycle, and just-in-time generation without
forcing a batch job or a manual-only flow.)*

---

## Decision

**Option B (per-band summary) + Decision 2 (fixed last-N window) + Decision 3
(sacrifice older first) + Decision 4 (KB-Redirect to merged) + Decision 5
(Triple-Trigger).**

- A **`BandSummary`** row (1:1 to `Novel`, `novel_id` PK + unique FK
  `ON DELETE CASCADE`) holds `full_summary`, `short_summary`, optional
  `override`, and `generated_at`. Produced by **`BandSummaryAgent`** (Core,
  one LLM call, governed Mode-1 template) from the band's chapter summaries.
- **`SeriesHistoryTier`** (pure Core) assembles the `Previously in this
  series:` block: the last `context_window_size` bands (default 3) contribute
  `override or full_summary`; older bands contribute only `short_summary`.
  Entries emit newest-first; under token-budget pressure the oldest entries
  are truncated then dropped (default budget 512 tokens).
- **`SeriesHistoryProvider`** (Backend) pre-fetches `BandSummaryData` from the
  three repositories, calls the tier, and returns the string the writing
  service injects into **`{{series_history}}`** (a governed SYSTEM_VAR).
- **KB-Redirect:** series novels read the merged Canon+Overlay KB; standalones
  keep the per-novel query. `resolve_kb_fetch_mode()` is the single decision
  point.
- **Triple-Trigger** generation: manual POST, auto on series→completed, lazy
  `get_or_generate`.
- **Override precedence:** within the recency window, `override` replaces the
  generated full summary (empty-string override falls back to `full`); outside
  the window the override is ignored (it curates the full record only).
- **Frontend:** `BandSummaryCard` (expandable: title, generated-at, full text,
  regenerate) + `BandOverrideEditor` (textarea + save/clear override), backed
  by `useBandSummary` / `useGenerateBandSummary` /
  `useUpdateBandSummaryOverride` / `useClearBandSummaryOverride` TanStack hooks.

---

## Rationale

The per-band-summary model is the **proportionality** answer: a single
generated + overrideable row per band bounds the token cost (one row, not
N chapters), respects curation (the user can correct the AI's summary), and
separates "what the AI summarised" (`full`/`short`) from "what the author
wants carried forward" (`override`).

The recency-window is the **scaling** answer: it keeps Spec 2 tractable for
long serieses (only the last K bands carry full summaries) without losing
older context entirely (the one-sentence `short_summary` still anchors the AI).
The "sacrifice older first" budget policy ensures that under pressure the
*most recent, most relevant* context is always the last to go.

The KB-Redirect is the **CR-04 coherence** answer: Spec 1 built
`find_merged_for_novel` and a backward-compatible scope model precisely so
that the first series-aware consumer (generation, here) could opt into Canon
without a second merge implementation. Redirecting — not rebuilding — keeps
one merge path, one invariant, one test surface.

RULE-11 (graceful degradation) is load-bearing: every failure mode (standalone
novel, band 1, missing summary, empty window, tiny budget) collapses to an
empty `{{series_history}}` string, so a series novel with no summaries
generated yet simply generates without history — never an error.

### Sustainability check

1. **Correct in 3 months?** Yes — Spec 3 (Voice) and Spec 4 (Drift) extend
   the same `SeriesSettings` + series-history read path; none requires undoing
   Spec 2.
2. **Hard-to-undo coupling?** Minimal — additive table + column (one atomic
   migration with downgrade), one new governed variable, one new agent. A
   standalone novel sees no series-history UI and an empty `{{series_history}}`.
3. **Simplest correct solution?** Yes — one summary row per band, one tier,
   one redirect. Option A (replay chapters) would be simpler to build but
   wrong (unbounded tokens).
4. **Design intent clear?** Yes — `band_summary_*`, `series_history_provider`,
   `context/series_history` each name their single responsibility.

---

## Consequences

**Positive:**

- **Closes ADR-075's Spec 2 Review Trigger** — generation now consumes the
  merged Canon+Overlay KB and receives prior-band state.
- **Bounded, curatable series memory.** One row per band; the author can
  override any auto-generated summary; the recency window keeps tokens sane.
- **Additive, backward-compatible migration.** Existing standalone novels are
  unaffected (empty `{{series_history}}`, per-novel KB path).
- **One merge path.** The KB-Redirect reuses Spec 1's `find_merged_for_novel`
  — no second implementation, no invariant drift.

**Negative / Tradeoffs:**

- One atomic Alembic migration adds a table + a column (accepted; standard
  Spec cost, with `upgrade()` + `downgrade()`, RULE-14).
- Band summaries must be *generated* to be useful — a brand-new series with no
  completed band has empty history. Mitigated by the lazy `get_or_generate`
  trigger and the auto-trigger on series completion.
- The `context_window_size` setting is read by the tier but, at the time of
  this ADR, **not yet exposed on the settings PATCH/GET API surface** — the
  column exists and the provider reads it (default 3), but
  `SeriesSettingsUpdateRequest`/`SeriesSettingsResponse` do not yet carry the
  field. The user-facing slider to change it is open frontend+backend work
  (tracked in SERIES-002). The default of 3 keeps the feature correct in the
  interim.
- The token estimate in the tier uses a chars/4 heuristic (no `tiktoken` in
  Core) — deliberately conservative; the writing pipeline's real budgeting
  happens at the assembler level.

**Constraints introduced:**

- Series-aware generation MUST route the KB read through
  `resolve_kb_fetch_mode` → `find_merged_for_novel`, not a raw per-novel query
  — otherwise Canon is silently excluded (RULE-11).
- A new band-summary subtype/field MUST preserve the override-precedence
  invariant (`override > full_summary` in window; override ignored outside).
- `{{series_history}}` MUST be assembled by the Backend provider and injected
  as a pre-built string — services do not construct it inline (RULE-02b).

---

## CR-04 Cross-Feature Impact (coherence)

Series history is **consumed by generation** and **produced by the series +
band-summary services**. This ADR requires coherence end-to-end:

- **Producer (BandSummaryService / SeriesService).** Writes `BandSummary` rows
  (generate / override) and enqueues generation on series completion. The
  `band_summaries` table is new data.
- **Consumer (generation read path).** The writing service calls
  `SeriesHistoryProvider.assemble_series_history(novel_id)` and threads the
  result into `{{series_history}}`. The KB read is redirected via
  `resolve_kb_fetch_mode`.
- **Existing consumers (standalone novels).** Unaffected: a standalone novel
  has `series_id IS NULL` → empty history, per-novel KB. Backward compatible by
  construction (the variable defaults to `""`, the KB path defaults to
  `"per_novel"`).

This is the CR-04 lesson: the `{{series_history}}` variable and the KB-Redirect
are defined together with their consumer impact. Because the history block is
**new data** (empty for standalones), the cross-feature surface is **additive**
— no existing consumer sees series history unless it is in a series — but the
override-precedence and merged-KB invariants are fixed **here**.

---

## Retrofit-Plan

### 1. Inventory of affected paths

**Core** (`packages/core/narrare_core/`):
- `context/series_history.py` — `BandSummaryData` (frozen dataclass),
  `SeriesHistoryTier` (recency-window assembly + budget). Pure, no I/O.
- `agents/band_summary_agent.py` + `agents/band_summary_types.py` — the agent
  + `BandSummaryDeps`/`BandSummaryOutput`.
- `prompts/variable_registry.py` + `prompts/route_table.py` — `series_history`
  registered as a SYSTEM_VAR + allowed on the writing routes.
- `writing/{models.py,pipeline.py,_stages.py,context_assembler.py}` —
  `series_history` kwarg threaded through `WritingContext` →
  `WritingPipeline.generate` → `{{series_history}}`.

**Backend** (`apps/api/narrare/series/`):
- `band_summary_models.py` — `BandSummary` ORM (1:1 to Novel).
- `band_summary_contracts.py` — `BandSummaryRepositoryProtocol`,
  `BandSummaryServiceProtocol` (RULE-03, before implementation).
- `band_summary_repository.py`, `band_summary_service.py` (generate /
  get_or_generate / update_override), `band_summary_auto_trigger.py`
  (`enqueue_band_summaries`), `router_band_summary.py`, `tasks.py`
  (TaskIQ enqueue), `dependencies.py`.
- `series_history_provider.py` — Backend→Core bridge + KB-Redirect
  (`resolve_kb_fetch_mode`).
- `service.py` — `update_series` calls `enqueue_band_summaries` on the
  →`completed` transition.

**Alembic** — `apps/api/alembic/versions/0038_band_summaries.py` — atomic
`upgrade()` + `downgrade()` (RULE-14): `band_summaries` table +
`series_settings.context_window_size` (default 3).

**Frontend** (`packages/web/`):
- `components/series/BandSummaryCard.tsx` + `BandOverrideEditor.tsx`.
- `lib/hooks/useBandSummary.ts` (4 hooks) + `lib/api/series.ts` (band-summary
  methods) + `types/series.ts` (`BandSummary` types).
- i18n: `series.bandSummary.*` (en/de/fr).

### 2. Test update plan

- **Core tier tests** — recency-window selection, override precedence
  (in/out of window), budget "sacrifice older first", graceful empty cases,
  truncation boundary.
- **Backend service tests** — generate / get_or_generate / update_override;
  auto-trigger enqueue (best-effort, no abort); KB-Redirect mode resolution.
- **Provider tests** — standalone → `""`; band 1 → `""`; series novel with
  prior bands → assembled block; `TestKBRedirect` covers merged vs per_novel.
- **Writing-service wiring tests** — provider present → forwards
  `series_history`; provider absent → empty (backward compatible).
- **Core variable tests** — `{{series_history}}` in SYSTEM_VARS,
  `WritingContext` default `""`.
- **Frontend tests** — BandSummaryCard loading/empty/populated/override-active
  states; BandOverrideEditor save/clear dirty gating.

---

## Risks Surfaced

These are NOT blockers; acknowledged and mitigated:

1. **`context_window_size` not yet on the settings API surface.** The column
   exists and the provider reads it (default 3), but the PATCH/GET settings
   schemas do not yet carry the field, so the user cannot change it from the
   UI today. Mitigated by the sensible default; the slider is tracked as open
   work in SERIES-002. Low risk (feature works at default; tunability pending).
2. **Perry-Rhodan scale (1000 books).** The recency-window bounds the
   full-summary count to K; older bands contribute one sentence each. At
   extreme scale even the short-summary tail may exceed budget — mitigated by
   "sacrifice older first". Spec 4 (Drift) may revisit pagination/priority.
3. **Band-summary freshness.** A summary generated at band-2-time may be stale
   by band-8. Mitigated by the auto-regenerate on series completion + manual
   regenerate; full staleness tracking is a Spec 4 concern.
4. **Token heuristic (chars/4).** Conservative; the assembler-level budget is
   authoritative. Low risk.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02a/02b | ✅ | Band-summary prompt is a governed Mode-1 template (`_bundled/analysis/{lang}/band_summary/system.md`) via `PromptComposer`; chapter summaries are runtime user-channel content; `{{series_history}}` is a pre-built SYSTEM_VAR string, never an inline service f-string. |
| RULE-03 | ✅ | `BandSummaryRepositoryProtocol` / `BandSummaryServiceProtocol` (`band_summary_contracts.py`) + Core `SeriesHistoryTier` / `BandSummaryData` defined before the service/provider. |
| RULE-04/06 | ✅ | One responsibility per file: `band_summary_{models,repository,service,auto_trigger}.py`, `series_history_provider.py`, Core `context/series_history.py`. `band_summary_auto_trigger.py` was split from `service.py` to respect the 300-line limit. |
| RULE-07 | ✅ | `SeriesHistoryTier` is pure Core (no `apps/` imports, no I/O); all DB reads in the Backend `SeriesHistoryProvider`. Dependency direction Backend→Core. |
| RULE-11 | ✅ | Standalone / band-1 / missing-summary / empty-window / tiny-budget all yield `""`; generation proceeds unchanged. Auto-trigger enqueue failures are logged, never abort the status transition. |
| RULE-14 | ✅ | `band_summaries` table + `series_settings.context_window_size` in ONE migration (`0038`) with `upgrade()` + `downgrade()`. |
| RULE-17 | ✅ | Frontend `BandSummary` / `BandSummaryOverrideRequest` mirror the backend schemas (snake_case). |
| RULE-22 / CR-04 | ✅ | `{{series_history}}` governed SYSTEM_VAR (producer→consumer contract); KB-Redirect reuses Spec 1's `find_merged_for_novel` — one merge path, one invariant. |

---

## Review Trigger

- [ ] **Settings-API exposure of `context_window_size`** — when the
      `SeriesSettingsUpdateRequest`/`SeriesSettingsResponse` are extended to
      carry `context_window_size` and the frontend slider lands, verify the
      round-trip (PATCH → provider read → tier window) and add the
      `series.settings.contextWindow.*` i18n consumption test. *(Tracked in
      SERIES-002.)*
- [ ] **Stale "ADR-076" pointer** — the `0038_band_summaries.py` migration
      docstring references "ADR-076" as this decision's home. Update it to
      ADR-077 (or accept the stale pointer — low-impact, doc-only).
- [ ] When **Spec 4 (Cross-Novel Drift)** is implemented — verify the
      series-history read path performance for long serieses and whether the
      short-summary tail needs priority ranking.
- [x] **ADR-075 Spec 2 Review Trigger — CLOSED by this ADR (2026-08-02):**
      generation calls `find_merged_for_novel()` (via the KB-Redirect) and the
      token budget for the merged set is governed by the recency-window +
      "sacrifice older first" policy.

---

## Cross-References

- **ADR-075** — Series Foundation (Spec 1); this ADR is its Spec 2 successor
  and closes its Spec 2 Review Trigger.
- **ADR-025** — Feature Adoption Infrastructure (`{{series_history}}` governed
  SYSTEM_VAR).
- **ADR-067** — Reusable KB-Context Provider (the `SeriesHistoryProvider`
  Backend→Core bridge mirrors `KBContextProvider`).
- **ADR-074** — Author Voice Storage (`{{series_history}}` is a sibling
  generation variable to `{{author_voice}}`).
- `docs/features/series/SERIES-002-generation-context.md` — the user-facing
  feature spec.
- `packages/core/narrare_core/context/series_history.py` — the tier.
- `apps/api/narrare/series/series_history_provider.py` — the Backend bridge.
