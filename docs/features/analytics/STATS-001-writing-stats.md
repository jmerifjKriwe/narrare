---
id: STATS-001
title: "Writing Statistics"
status: planned
area: analytics
mvp: false

ui_tooltip: "Track writing progress with detailed statistics, streaks, and session data."
ui_help_short: |
  Track your writing progress with detailed statistics, streaks, and session data.
  Monitor daily word counts, writing habits, and progress toward your goals
  with visual charts and actionable insights.
ui_help_long: |
  ## Writing Statistics

  Track your writing progress and build productive habits.

  **Session Tracking**
  - **Session Types**: Writing, Editing, Review
  - **Automatic Tracking**: Start/end times, word counts, duration
  - **Session History**: Complete record of all writing sessions
  - **Manual Entry**: Add past sessions or correct data

  **Statistics Calculated**
  - **Daily Stats**: Words written, sessions, duration, average pace
  - **Weekly Stats**: Aggregated totals with daily averages
  - **Streaks**: Current streak, longest streak, last write date
  - **Progress**: Cumulative word count, target completion estimates
  - **Averages**: Words per day, words per session, session duration

  **Progress Tracking**
  - Daily word count additions (visual chart)
  - Cumulative progress charts
  - Remaining words to target
  - Implied completion dates based on pace
  - Target vs actual comparison

  **Habit Building**
  - Streak visualization (calendar view)
  - Writing time heatmap (best hours to write)
  - Day-of-week analysis
  - Productivity patterns identified

  **How it works:**
  1. Writing sessions tracked automatically
  2. View stats in Analytics panel:
     - **Dashboard**: Overview with key metrics
     - **Calendar**: Streak and session visualization
     - **Charts**: Word count, pace, progress trends
     - **History**: Detailed session log
  3. Set word count targets for motivation
  4. Export data for external analysis

  **Best practices:**
  - Start/end sessions consistently for accurate data
  - Focus on streaks over daily totals for habit building
  - Review weekly stats to identify productivity patterns
  - Set realistic word count targets for your genre
  - Use data to optimize your writing schedule

  Available in the **Analytics** panel (`/analytics`) in the studio sidebar.
ui_available_in: [analytics]

service: analytics/service.py
contract: analytics/contracts.py#AnalyticsServiceProtocol
router: analytics/router.py
prompt: ~
requires: [ADR-021]
---

# STATS-001 — Writing Statistics

## What it does

Comprehensive writing progress tracking with session management, streak monitoring, and statistical analysis. Automatically tracks writing sessions and provides visual charts for habits, progress, and productivity patterns.

## Why it exists

Writers want to know their progress. Am I writing enough? What's my average pace? When do I write most productively? Is my streak alive? Writing statistics provide the data writers need to understand their habits, set realistic goals, and build sustainable practices.

## How it works (User perspective)

1. Sessions tracked automatically when you:
   - Open a chapter for writing
   - Make significant edits
   - Manually start/end session
2. View stats in Analytics panel:
   - **Dashboard**: Key metrics at a glance
   - **Calendar**: Visual streak and session view
   - **Charts**: Word count trends, pace, progress
   - **History**: Detailed session log with filters
3. Set word count targets:
   - Daily target
   - Weekly target
   - Novel completion target
4. See progress visualizations:
   - Target vs actual
   - Completion date estimates
   - Streak counters
5. Export data for external tools

## How it works (Technical)

**Architecture per ADR-021:** Pure Python computation — word counts, sentence counts, paragraph counts, character counts. No NLP library needed, no LLM calls. Exact deterministic results.

**Entry point:** `analytics/router.py` → GET endpoints at `/api/v1/analytics/stats`
**Service:** `AnalyticsService` in `analytics/service.py`
**Contract:** `AnalyticsServiceProtocol` in `analytics/contracts.py`

**Session tracking:**
```python
class WritingSession:
    id: UUID
    novel_id: UUID
    chapter_id: UUID | None
    session_type: "writing" | "editing" | "review"
    start_time: datetime
    end_time: datetime | None
    word_count_start: int
    word_count_end: int | None
    duration_seconds: int | None
```

**Statistics calculation:**
- Daily: Sum of sessions per day
- Weekly: Aggregated daily stats
- Streaks: Consecutive days with activity
- Averages: Mean of metric over period
- Pace: Words per day/week/month

**Progress tracking:**
- Cumulative: Total words across all sessions
- Remaining: Target - current
- Pace-based: Days remaining at current rate
- Target-based: Days needed at target pace

## Constraints & Edge Cases

- Session detection is heuristic-based (may miss quick edits)
- Manual session entry required for past data
- Streaks reset if day missed (no grace period)
- Pace estimates assume consistency (may not reflect reality)
- Timezone issues can affect day boundaries
- Deleted chapters affect historical word counts
- No ML-based prediction (simple extrapolation only)

## Related Features

- [STATS-002](STATS-002-cost-tracking.md) — Cost tracking
- [WRITE-001](../writing/WRITE-001-editor.md) — Writing session source
- [LEARN-001](../learning/LEARN-001-feedback-loop.md) — Habit optimization
- [INFRA-005](../infra/INFRA-005-memory-layer.md) — Session data storage

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-06-22` — ADR-021 applied: specified as pure Python deterministic computation (no LLM dependency)
- `2026-10-07` — CLI access formally retired (PO decision): no CLI substrate exists, a CLI would have to bypass the service layer/user scoping or duplicate HTTP+auth plumbing, and the Analytics panel + CSV export cover the value; `ui_available_in` reduced to `[analytics]`.
