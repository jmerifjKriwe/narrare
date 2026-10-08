# ADR-095 — Writing Activity Capture (STATS-001 v1)

> **Status:** ✅ Implemented (per Gate 12 — implementation complete
> 2026-10-08: branch `feature/stats001-writing-stats`, commits
> `a18856ed..dd9e7c49`; binding spec
> `docs/superpowers/specs/2026-10-07-stats001-writing-stats-design.md`, plan
> `docs/superpowers/plans/2026-10-07-stats001-writing-stats.md` — see the
> Implementation Report below)
> **Date:** 2026-10-07
> **Deciders:** Architecture Agent; Project Owner (ratified: delta-event
> capture · read-time derivation · goals with own storage)
> **Related:** ADR-093 (analytics module + UTC bucketing precedent;
> never-raise philosophy applied to the recorder), ADR-091 (import commit
> surface), ADR-023 (co-author apply surface), ADR-011 (version restore
> surface), `docs/features/analytics/STATS-001-writing-stats.md` (over-scoped
> v0 spec — to be amended), `docs/features/analytics/STATS-002-cost-tracking.md`

---

## Context

The old STATS-001 spec promises sessions, streaks, a heatmap, and targets —
over-scoped, and no capture substrate exists. What does exist:

- `Chapter.word_count` (maintained on every content write).
- Exactly four content-write surfaces (verified): chapters
  `update_content` (`chapters/service.py:87`, driven by the editor autosave
  PATCH), `restore_version` (`:184`, writes via the same repository call at
  `:202`), `delete` (`:162`); co-author apply
  (`writing/coauthor_apply_service.py:104–108`, writes via
  `chapter_repo.update_content`); import commit
  (`importing/service.py:172` → `append_chapters` at `:213`, bulk-writes
  word counts).
- An in-process event bus (`narrare_core.events`, Q-016
  `chapter.finalized` precedent) — but no general subscriber infrastructure.
- No novel-level writing goal anywhere. `word_target`
  (`writing/schemas.py:47`, `ge=100, le=50000`) is a **per-request draft
  length for generation** — a request parameter, not a goal.

Narrare is a local-first app that is routinely closed overnight — any
capture design that relies on a running scheduler silently loses data.

---

## Decision Drivers

- **Capture must not depend on app uptime** (local-first; closed overnight).
- **Honest numbers**: net deltas including deletes; no fabricated history.
- **One source of truth**: store events, derive aggregates at read time —
  no second stored aggregate to drift against the events.
- **Stats must never break writing** (ADR-093 D1 philosophy).
- **No new dependencies** (Recharts already present).
- RULE-03 (contract-first), RULE-06 (module split), RULE-08 (repository).

---

## Options Considered

### Option A — Daily word-count snapshots (nightly / on-first-write job)

**Pros:** simple read side.
**Cons:** a scheduler must run; a local-first app that is closed overnight
misses snapshots silently — permanent gaps, backfill impossible. Rejected
as the primary capture mechanism.

### Option B — Delta events on content writes, dailies/streaks/heatmap derived at read time (chosen)

**Pros:** capture happens exactly when writing happens (uptime-independent);
signed deltas are honest (deletes visible); event timestamps enable later
hour-of-day analytics at zero extra capture cost.
**Cons:** pre-feature history is invisible to dailies (documented day-0
boundary); the recorder must be wired into every write surface (review
trigger).

### Option C — Full session tracking (heuristic start/end sessions)

**Cons:** the heaviest option, and the old spec itself admits its
heuristics miss quick edits. Rejected for v1.

Also rejected: **manual entry** (friction + dishonest data), **event-bus
publication** (the bus exists but has no general subscriber infrastructure —
a direct contract-first recorder is simpler and type-safe), and **reusing
`word_target` as the goals source** (it is a per-request generation
parameter — see decision 5).

---

## Decision

**We choose Option B**, in six decisions:

1. **Delta-event table.** New append-only table `writing_activity_events`:
   `id` PK, `user_id` FK `users` **RESTRICT** (history must not be silently
   erased — `usage_records` precedent), `novel_id` FK `novels` **SET NULL**
   (history outlives the novel — same precedent), `chapter_id` FK
   **SET NULL**, nullable (chapter deletion is a *normal flow* — the delete
   event survives with a nulled reference), `delta_words` INTEGER **signed**,
   `created_at` `DateTime(timezone=True)` set explicitly at write time.
   Index `(user_id, created_at)` mirroring `usage_records`. Alembic
   migration (RULE-14). No updates, no snapshots, no aggregates stored.

2. **`WritingStatsRecorder` — contract-first, never-raises.** A Protocol
   (RULE-03) in the analytics module:
   `record(user_id, novel_id, chapter_id, old_words, new_words)` → persists
   `delta_words = new − old`; **zero deltas are skipped** (chapter create
   starts empty, restores to identical content, empty-chapter deletes
   produce no rows). The call is guarded — any failure logs a warning and
   the write path continues untouched (ADR-093 D1 philosophy: stats must
   never break writing). API-owned, persisting via its repository (RULE-08);
   no Core change — the delta arithmetic is trivial and Core purity would
   buy nothing.

3. **Emission surfaces (verified) and rulings.** The recorder is called
   from: chapters `update_content` (covers editor autosave **and**
   `restore_version`, which routes through the same repository call);
   chapter **delete** = negative delta (`old = chapter.word_count`,
   `new = 0`) — honest net words; co-author apply (old → reconstructed);
   **import commit** — one event per appended chapter, **attributed to the
   day-of-import, no backdating** (`created_at` = commit time; the import
   day honestly shows the spike). Import dedup/undo stays out of scope
   (ADR-091 append-only ruling unchanged).

4. **Read-time derivation.** Dailies, streaks, and the heatmap are computed
   at query time from the events — UTC-day bucketing mirroring the
   analytics repository (`date_trunc('day', created_at AT TIME ZONE 'UTC')`
   — same session-timezone pin and rationale). A day counts as active iff
   it has ≥1 event (zero deltas are never stored); daily values are signed
   net sums. New endpoint `GET /api/v1/analytics/writing` (+ optional
   `novel_id` filter), user-scoped, in the existing analytics module.

5. **Writing goals (PO-ratified addition) — own storage, cumulative-words
   basis.** Storage: a novel-scoped `writing_goals` JSONB NULL column on
   `ProjectSettings` — typed sub-model precedent `adaptive_settings`
   (ADR-069 D2) and `author_voice` (ADR-074); v1 shape
   `{"target_words": <int>}`. **Progress basis: the cumulative words of the
   novel** — live `SUM(chapters.word_count)` at read time. Explicitly NOT
   the activity-event sum (events begin at deployment; a novelist's
   pre-existing words would be invisible → dishonest progress — the same
   day-0 boundary that dailies accept is *not* acceptable for goals, so
   goals read state, not events). Explicitly NOT `word_target` — a
   per-request generation parameter. Novel-scope over user-scope: the
   progress basis is novel-scoped, a user-level goal would need novel
   disambiguation anyway, and daily-habit goals (words/day) are out of
   scope v1 (YAGNI — streaks already serve habit visibility).

6. **FE: second tab.** A writing tab in the existing `PanelTabs`
   (`packages/web/app/(studio)/analytics/page.tsx` — v1 ships one tab and
   was built for more): dailies chart (Recharts — present), streak card,
   heatmap from daily totals, goal progress card. TS type mirror (RULE-16),
   i18n en/de/fr (RULE-17). The STATS-001 feature file is amended to this
   scope (and loses its stale CLI promises).

---

## Rationale

Root-cause chain (2× why):

1. **Symptom:** no writing statistics exist despite a spec promising them.
2. **Why?** The spec was written around sessions/snapshots — concepts that
   need either a scheduler (uptime) or heuristics (gaps) Narrare cannot
   guarantee.
3. **Why?** Writing in Narrare already funnels through a handful of content
   write surfaces that maintain `word_count` — the true signal (net words
   over time) is derivable at the moment of writing, not only at night.
4. **Design:** capture signed deltas at the four verified surfaces, derive
   everything else at read time. Option A loses data by construction when
   the app is closed; Option C is the heaviest and still misses quick
   edits; B is the simplest mechanism that is honest *and*
   uptime-independent. Goals measure manuscript state (live totals);
   dailies measure activity (events) — two different questions, two
   deliberate bases.

---

## Consequences

**Positive:**

- Capture is correct regardless of app uptime; no scheduler exists or is
  needed.
- Honest net accounting: deletes and restores are visible as deltas.
- Event timestamps make hour-of-day/behavioral analytics derivable later
  with zero additional capture.
- Zero new dependencies; analytics module patterns (bucketing, module
  split) are reused.

**Negative / Trade-offs:**

- Pre-feature history is invisible in dailies/heatmap/streaks (documented
  day-0 boundary; goals deliberately unaffected — decision 5).
- Append-only growth (small rows; pruning/archival is a future decision —
  review trigger).
- Every future content-write surface must remember the recorder (drift =
  silent gaps — review trigger).

**Constraints touched:** RULE-03 (recorder Protocol first), RULE-04 (task
sizing), RULE-06 (analytics module split; router thin), RULE-08 (repository
owns SQL), RULE-10 (tests per slice), RULE-11 (day-0 boundary and net
deltas documented, not hidden), RULE-14 (Alembic migration), RULE-16/17
(TS mirror + i18n at first use), RULE-20 (feature-file amendment).

---

## Sustainability Check

1. **Correct in 3 months?** Yes — the write surfaces are stable, load-bearing
   paths; UTC-day derivation matches the proven cost bucketing.
2. **Hard-to-undo coupling?** None: the table is additive; dropping the
   recorder calls removes capture without touching writing behavior.
3. **Simplest correct solution?** Yes (see Rationale) — Option B is the
   only option that is both honest and uptime-independent.
4. **Intent clear?** This ADR + the binding implementation spec (wire
   shapes, streak definition details, migration, tests).

---

## Implementation Notes

- Module homes: `apps/api/narrare/analytics/writing_stats_*.py` sibling
  files (`contracts` / `models` / `repository` / `service` / `router`) —
  RULE-06 split, the `kb/bulk_extraction/` sibling precedent; the analytics
  core files stay untouched.
- Recorder calls: one guarded line each in `chapters/service.py`
  (`update_content` incl. the restore path, `delete`),
  `writing/coauthor_apply_service.py`, `importing/service.py` (commit).
- Read side: UTC-day aggregation in the repository (mirror
  `analytics/repository.py`'s timezone pin); streak definition details
  (today-grace rule) are spec-level.
- Goals: `ProjectSettings.writing_goals` column + typed sub-model +
  settings read/write through the existing settings family; progress =
  live chapter word-count sum per novel.
- Tests (RULE-10): delta math incl. zero-skip; never-raises guard; delete =
  negative delta; import day-of-import attribution; UTC-day bucketing
  (integration, mirroring `test_migration_0043_round_trip.py`); goal
  progress vs. pre-existing words.

**ADR Implementation Completeness Gate (Gate 12):** flip INDEX to
"✅ Implemented" only when the table + migration, recorder wiring on all
four surfaces, read endpoint, goals storage + progress, FE tab, i18n, and
tests are complete.

---

## Implementation Report (2026-10-08)

Implemented on branch `feature/stats001-writing-stats`, commits
`a18856ed..dd9e7c49`, per the binding spec
`docs/superpowers/specs/2026-10-07-stats001-writing-stats-design.md`
(decisions E-1..E-7) and plan
`docs/superpowers/plans/2026-10-07-stats001-writing-stats.md`. Mapping to
the decisions above:

- **D1 (delta-event table):** `analytics/writing_models.py`
  (`WritingActivityEventRow`) + Alembic `0045` — FK rulings as decided
  (user RESTRICT, novel/chapter SET NULL), signed `delta_words` without a
  CHECK, `created_at` stamped by the recorder (no server default), index
  `(user_id, created_at)` + `novel_id`.
- **D2 (recorder):** `analytics/writing_stats_recorder.py` —
  `WritingStatsRecorder` Protocol (RULE-03) + `SqlWritingStatsRecorder`;
  the never-raise guard lives in the recorder (the single enforcement
  point — call sites stay guard-free by contract), zero deltas skip before
  any session opens, explicit attribution (no ContextVars — call sites know
  the user/novel/chapter), persistence via `WritingActivityEventRepository`
  (RULE-08) in its own short-lived session.
- **D3 (surfaces):** chapters `create` (with content), `update_content`,
  `restore_version`, `delete` (negative delta), co-author apply, and import
  commit (one event per appended chapter, day-of-import) — see the
  refinement notes below.
- **D4 (read side):** `analytics/writing_{repository,service,models}.py` +
  `WritingQueryServiceProtocol` (contracts) + `GET /api/v1/analytics/writing`
  (auth; optional `novel_id`, ownership 404 foreign≡unknown).
- **D5 (goals):** `ProjectSettings.writing_goals` JSONB NULL (Alembic
  `0046`), v1 shape `{"target_words": int | null}`, PATCH via the
  project-settings surface (strict request / graceful response), progress =
  live `SUM(chapters.word_count)` via the `GoalSource` seam
  (`ProjectSettingsGoalSource` over a strictly read-only
  `get_writing_goals` repository read — never auto-creates).
- **D6 (FE):** second "Writing" tab in the `/analytics` `PanelTabs`
  (`WritingStatsPanel` + `DailyWordsChart`, TanStack Query hook
  `useAnalyticsWriting`), goal editing in the novel settings "writing" tab
  (`WritingGoalsTab`), i18n en/de/fr (`analytics.writing.*` +
  `settings.writing.*`). TS type mirror (RULE-16).

**Where the implementation refined the decision text (factual):**

1. **A sixth capture surface was added during review: chapter
   create-with-content.** The original enumeration had four surfaces
   (update/restore/delete/co-author/import); review found `ChapterService.create`
   accepted `content` and persisted a computed `word_count` without calling
   the recorder — an incomplete surface enumeration at implementation time,
   not a design gap. Create now records `delta_words = chapter.word_count`
   right after a successful `repo.create`; empty creates arrive as 0 and are
   skipped inside the recorder.
2. **`restore_version` has its own explicit call site** (recording
   `restored − current`), rather than relying solely on "routes through the
   same repository call" — same semantics as decided, wired explicitly.
3. **Streak basis is event-count, not word-count.** Decision 4's
   "a day counts as active iff it has ≥1 event" is the implemented contract
   (review-fixed: an early implementation used a word-sum basis; a day with
   a net-zero word total from real activity is still an active day).
4. **The report total is ALL-TIME, not window-bounded.** `total_words` is
   the all-time signed net `SUM(delta_words)` for the scope; a 90-day number
   labelled "total" would mislabel it (the window bounds only
   dailies/streaks/today).
5. **Demo/sample seeding is ruled OUT of capture (2026-10-08, coordinator
   ruling).** `setup/demo_loader.py` writes chapters directly to the session
   (bypassing `ChapterService`), so seeding produces no events — and is
   *meant* to produce none: system-generated sample content is not user
   writing activity, unlike user-initiated import.
6. **Goals-response graceful degradation (review fix).** JSONB is
   schemaless, so a hand-edited corrupt row (top-level non-dict, wrong-typed
   target) must degrade to "no goal", never fail a read: the accessor guards
   with `isinstance(data, dict)`, the settings *response* field is
   deliberately loose (`object | None`) so reads never 500, while the
   *request* side stays strict (`extra="forbid"`, 422 on garbage). Unknown
   v1 keys in hand-edited rows are tolerated on read; app-written rows are
   guaranteed clean.
7. **The v1 FE renders the 90-day daily-words bar chart, streak/today/total
   cards, the novel selector, and the goal progress bar — no calendar
   heatmap.** Daily totals are already the heatmap's data; rendering it is a
   later slice (the decision's heatmap mention is data-satisfied, not
   yet rendered).

**Honest residuals (documented, not hidden — RULE-11):**

- **Day-0 boundary:** events begin at deployment; dailies/streaks/total see
  nothing earlier (goals deliberately unaffected — decision 5).
- **Phantom-delta residual (day-0 corollary):** content that predates the
  ledger — pre-feature chapters and demo-seeded samples — has no positive
  events, yet deleting or shrinking that content still records its negative
  delta. A day can therefore show a net-negative entry for words the ledger
  never saw as positive. Accepted: it is the honest net-accounting behavior
  of a bounded ledger, and goals (state basis) are unaffected.
- **Novel-deletion cascade leaves history** (as decided): `novel_id` is
  SET NULL and the events keep counting in the user-scoped total — the
  all-time total is lifetime writing activity, not "words in current
  manuscripts".

Reviews: E3/E4/E5/E8 approved, one fix round each (E3: create-with-content
surface + DI wiring proofs; E4: event-count streak basis + all-time total;
E5: corrupt-row graceful degradation; E8: FE goal-editing fix round). FE
suite at closure: 450 files / 3877 tests green; backend suites green through
E5; the full final gate runs in the Platform finisher.

Gate 12 satisfied — table + migrations 0045/0046, recorder wiring on all
six surfaces, read endpoint, goals storage + live progress, FE tab + goal
editing, i18n, and tests all complete; INDEX flipped to ✅ Implemented in
the same docs pass.

---

## Review Triggers

- [ ] A new content-write surface appears (e.g. DOCX import follow-up,
      chapter merge/split) → it must call the recorder; a forgotten call is
      a silent statistics gap.
- [ ] Event volume becomes a concern (years of daily writing) → pruning or
      archival decision; do not silently truncate.
- [ ] Hour-of-day or behavioral analytics are requested → derive from
      existing timestamps; do not re-capture.
- [ ] Goals expand (daily targets, per-user goals, deadlines) → revisit the
      storage shape (the JSONB sub-model can carry more, but the basis
      decision — state vs. events — must be re-made consciously).
- [ ] Snapshot-grade accuracy is ever required (billing, contests) → out of
      scope here; new ADR.
