---
id: STATS-001
title: "Writing Statistics"
status: stable
area: analytics
mvp: false

ui_tooltip: "Track daily words, writing streaks, and your novel word goal."
ui_help_short: |
  See your daily words, keep your streak alive, and set a word-count
  goal for your novel — in the Analytics panel.
ui_help_long: |
  Every time your manuscript changes — you write, edit, restore a version,
  apply co-author suggestions, or import a manuscript — Narrare records the
  word delta. Open **Analytics** in the studio sidebar and check the
  **Writing** tab: a 90-day daily-words chart, words written today, your
  current and longest streak, and an all-time total. Pick a novel to also
  see its goal progress.

  A day counts as active when something was written on it (even edits that
  only *remove* words, like a cut, count as activity). Your current streak
  survives until the day actually ends — missing today is not a broken
  streak until tomorrow starts without you.

  Set a **writing goal** per novel in the novel's settings ("Writing" tab):
  a target word count. Progress always measures the novel's actual current
  word count — so words your manuscript already had before Narrare started
  counting still count toward the goal.
ui_available_in: [analytics]

service: analytics/writing_service.py
contract: analytics/contracts.py#WritingQueryServiceProtocol
router: analytics/router.py
prompt: ~
requires: [ADR-095]
---

# STATS-001 — Writing Statistics

> **Status:** ✅ Stable — v1 (delta-event writing stats + novel word goals)
> implemented 2026-10-08 (commits `a18856ed..dd9e7c49`) per
> [ADR-095](../../architecture/decisions/ADR-095-writing-activity-capture.md)
> (✅ Implemented). Design:
> [writing-stats spec](../../superpowers/specs/2026-10-07-stats001-writing-stats-design.md),
> plan: [2026-10-07-stats001](../../superpowers/plans/2026-10-07-stats001-writing-stats.md).

## What it does

Writing-activity tracking built on signed word-count deltas: every
content-write surface (chapter create/edit/version-restore/delete, co-author
apply, import commit) appends one event, and the read side derives a 90-day
daily-words chart, today's words, current/longest streaks, and an all-time
net total — plus a novel-scoped word goal (`target_words`) whose progress
measures the novel's live chapter word count. Shipped as the second
"Writing" tab in the `/analytics` panel; goals are edited in the novel
settings.

## Why it exists

Writers want to know: am I writing regularly? Is my streak alive? How close
is this novel to its target? v1 answers those with honest net numbers —
deletes and shrinks are visible as negative deltas, imports land on the day
they happened, and nothing is fabricated for the time before Narrare started
counting.

## How it works (User perspective)

1. Use Narrare normally — every manuscript change records its word delta
   automatically. Nothing to start or stop.
2. Open **Analytics** (studio sidebar) → **Writing** tab:
   - **Daily words** chart for the last 90 days (signed net per day).
   - **Words today**, **current streak**, **longest streak**, **total
     words** cards.
   - **Novel selector** ("All novels" by default) — narrowing also narrows
     every number on the tab.
3. Set a goal: open the novel's **Settings → Writing** tab, enter a target
   word count, save. The Analytics tab then shows a progress bar
   (`current of target (percent)`) whenever a novel is selected. Clear the
   field to remove the goal.

## How it works (Technical)

**Capture (ADR-095 D1–D3):** append-only table `writing_activity_events`
(Alembic `0045`): `user_id` FK RESTRICT, `novel_id`/`chapter_id` FK SET
NULL, `delta_words` signed INTEGER, `created_at` TIMESTAMPTZ set by the
recorder at write time (no server default — no late-sink drift), index
`(user_id, created_at)`. No snapshots, no stored aggregates.

**Recorder:** `WritingStatsRecorder` Protocol (RULE-03) +
`SqlWritingStatsRecorder` in `analytics/writing_stats_recorder.py` —
contract-first, **never-raises** (the guard lives in the recorder as the
single enforcement point; a failure logs `writing_stats_record_failed` and
the write path continues untouched), **zero deltas skipped** before any
session opens, persistence via `WritingActivityEventRepository` (RULE-08) in
its own short-lived session.

**Six emission surfaces (as-built):**

| Surface | Delta |
|---------|-------|
| Chapter create with content (`chapters/service.py`) | `+word_count` (added during review — create is a real write) |
| `update_content` (editor autosave PATCH) | `new − old` |
| `restore_version` | `restored − current` |
| Chapter delete | `−word_count` (honest net words) |
| Co-author apply (`coauthor_apply_service.py`) | `new − old` (reconstructed) |
| Import commit (`importing/service.py`) | one event per appended chapter, **day-of-import, no backdating** |

**Ruled excluded:** demo/sample seeding (`setup/demo_loader.py`, ruling
2026-10-08) — the loader writes chapters directly to the session, and
system-generated sample content is not user writing activity. Novel
deletion leaves historical events (`novel_id` SET NULL — activity ≠ current
manuscript).

**Read side (D4):** `GET /api/v1/analytics/writing` (auth; optional
`novel_id`, ownership-gated 404 foreign≡unknown), served by
`WritingQueryService` (`analytics/writing_service.py`), contract
`WritingQueryServiceProtocol` in `analytics/contracts.py`. UTC-day
bucketing mirroring the analytics repository's timezone pin; the window is
the last 90 days ending today, zero-filled.

```json
{
  "dailies": [ { "date": "2026-10-01", "words": 412 },
               { "date": "2026-10-02", "words": -35 } ],
  "streaks": { "current": 4, "longest": 12 },
  "today_words": 412,
  "total_words": 83450,
  "goal": { "target_words": 50000, "current_words": 42000,
            "progress_pct": 84.0 }
}
```

- **Dailies:** signed net sum per UTC day, zero-filled across the window.
- **Streaks:** event-count basis — a day is active iff it has ≥1 stored
  event (zero deltas are never stored). Current streak anchors on today
  when today is active, else yesterday (**today-grace**: a streak survives
  until the day ends; 0 when neither today nor yesterday is active).
  Longest is over all recorded history.
- **`total_words`:** the ALL-TIME signed net sum for the scope —
  deliberately not window-capped.
- **`goal`:** present only for a novel-scoped request whose novel has a
  target set (`null` otherwise). `current_words` is the live
  `SUM(chapters.word_count)`; `progress_pct` rounded to one decimal; a
  non-positive target reads as unset.

**Goals storage (D5):** `ProjectSettings.writing_goals` JSONB NULL
(Alembic `0046`), v1 shape `{"target_words": int | null}`; set/unset via
the project-settings PATCH surface (strict `extra="forbid"` request —
garbage ⇒ 422; unset = `{"target_words": null}`, whole-object replace).
Reads go through `settings/writing_goals.py` (`parse_target_words` +
`ProjectSettingsGoalSource` over a strictly read-only repository read —
never auto-creates). Corrupt stored rows degrade to "no goal" everywhere
(the settings response field is deliberately loose) — a hand-edited row can
never 500 a read.

**Frontend (D6):** second "Writing" tab in the `/analytics` `PanelTabs`
(`WritingStatsPanel` + `DailyWordsChart` via Recharts — no new dependency),
`useAnalyticsWriting` hook, goal editing in the novel settings "Writing"
tab (`WritingGoalsTab`; cleared input ⇒ explicit unset; invalid drafts
blocked with a validation message). i18n `analytics.writing.*` +
`settings.writing.*` (en/de/fr).

## Constraints & Edge Cases

- **Day-0 boundary:** events begin at deployment — dailies, streaks, and
  the total see nothing earlier. Goals are deliberately unaffected (they
  read manuscript state, not events).
- **Phantom-delta residual:** content that predates the ledger (pre-feature
  chapters, demo samples) has no positive events, yet deleting or shrinking
  it still records the negative delta — a day can show a net-negative entry
  for words the ledger never saw as positive. Accepted honest
  net-accounting of a bounded ledger (ADR-095 Implementation Report).
- **The total is lifetime activity, not current manuscript size:** novel
  deletion leaves its events counting in the user-scoped total; goals
  measure the live novel word sum instead.
- **Capture is best-effort by design:** a recorder failure never breaks a
  write — it logs a warning and that delta is lost.
- **Import honesty:** an import shows as a spike on the import day; no
  backdating to when the text was originally written.
- **UTC day boundaries:** a session near midnight can split a writing
  evening across two UTC days (same pin as the cost tracker).
- **No heatmap in v1:** the FE renders the daily-words bar chart; daily
  totals already carry the heatmap data (hour-of-day analytics derivable
  later from event timestamps at zero capture cost).
- **Deleting a user is blocked by design** (`user_id` RESTRICT — history
  must not be silently erased).

## Related Features

- [STATS-002](STATS-002-cost-tracking.md) — AI Cost Tracking (shares the
  `/analytics` panel and the never-raise/best-effort philosophy)
- [WRITE-001](../writing/WRITE-001-editor.md) — editor autosave is the
  primary delta source
- [WRITE-006](../writing/WRITE-006-co-author.md) — co-author apply surface
- [SETUP-003](../setup/SETUP-003-import.md) — import commit surface
- [SET-002](../settings/SET-002-project-settings.md) — ProjectSettings
  carries the goal

## Status & History

- `project-init` — Added to registry as planned feature.
- `2026-06-22` — ADR-021 applied: originally specified as pure Python
  deterministic computation (sessions/heatmap/targets — over-scoped v0).
- `2026-10-07` — CLI access formally retired (PO decision): no CLI substrate
  exists; the Analytics panel covers the value; `ui_available_in` reduced
  to `[analytics]`.
- `2026-10-07` — Re-scoped to v1 and ratified:
  [ADR-095](../../architecture/decisions/ADR-095-writing-activity-capture.md)
  (delta-event capture, read-time derivation, novel-scoped `writing_goals`);
  binding spec `2026-10-07-stats001-writing-stats-design.md` (E-1..E-7).
- `2026-10-08` — **v1 implemented** (commits `a18856ed..dd9e7c49`): table +
  Alembic 0045/0046, recorder + six surfaces, `GET /analytics/writing`,
  FE Writing tab + goal editing, i18n en/de/fr. Reviews approved with one
  fix round each (E3 added the create-with-content surface; E4 fixed the
  streak basis to event-count + all-time total; E5 made corrupt goal rows
  degrade gracefully; E8 closed the FE fix round). **Status → `stable`.**

**Deferred (registered out-of-scope v1):** session tracking · manual entry
· hour-of-day heatmap (data already captured) · per-chapter breakdowns ·
goal types beyond `target_words` (daily targets, deadlines, per-user goals)
· export of writing stats · notifications/streak reminders.
