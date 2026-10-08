# STATS-001 — Writing Statistics v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delta-event writing statistics (dailies, streaks, heatmap data) + novel-scoped word goals, in a second `/analytics` tab. Binding: spec `docs/superpowers/specs/2026-10-07-stats001-writing-stats-design.md` (E-1..E-7); ADR-095 (flips at closure).

**Architecture:** `WritingStatsRecorder` (contract-first, never-raises) writes `writing_activity_events` from the four content-write surfaces; read-side UTC-day derivation in the analytics module; `writing_goals` JSONB on ProjectSettings (+0045) with live word-count progress; FE second tab.

## Global Constraints

English; Core DB-free where it lives in core (the recorder lives API-side — the write surfaces are API services; contract Protocol first); RULE-03/06/08/14; TDD; ≤3 files / ≤250 LOC per task (STOP+report if gate-forced beyond); conventional commits; never `--no-verify`/`-n`.

---

### Task E1: Table + model — `writing_activity_events` + Alembic 0045
Files: Create `apps/api/narrare/analytics/writing_models.py`; Create `apps/api/alembic/versions/0045_writing_activity_events.py`; Modify `apps/api/narrare/_app/models.py` (register). Columns per spec E-1 (user RESTRICT, novel/chapter SET NULL, signed delta_words, created_at no default). Round-trip test if DB reachable (mirror 0043/0044 pattern). Commit `feat(api): writing_activity_events table + Alembic 0045`.

### Task E2: Recorder — contract + `WritingStatsRecorder`
Files: Create `apps/api/narrare/analytics/writing_stats_recorder.py` (Protocol + impl: computes signed delta, skips zero, never-raises — own short-lived session, insert via repository, log-only failure); Modify `apps/api/narrare/analytics/repository.py` (insert method for the new row — RULE-08); Test create. Commit `feat(api): writing stats recorder (never-raises)`.

### Task E3: Write surfaces — wire the four call sites
Files: Modify `chapters/service.py` (update_content + restore path + delete), `coauthor_apply_service.py`, `importing/service.py` (one event per imported chapter). Tests per call site (recorder called with correct signed delta; zero-delta skipped; write proceeds on recorder failure). ≤3 files hard — if the three service files + tests exceed, STOP+report for re-slice (E3a chapters, E3b coauthor+import). Commit `feat(api): writing activity capture on all content-write surfaces`.

### Task E4: Read side — repository aggregation + service + endpoint
Files: Modify `analytics/repository.py` (UTC-day aggregation over events: dailies window, streak inputs); Create `apps/api/narrare/analytics/writing_service.py` + extend `contracts.py` (Protocol + `WritingReport` schema per E-5) + router entry `GET /analytics/writing` (auth, optional novel_id + ownership 404); goal block via ProjectSettings lookup + live `SUM(chapters.word_count)` (repository query). Tests: streak math (gaps/boundaries), scoping, goal block (set/None/pct), 404. Likely >3 files — pre-approved up to 6 for this composed read task (STOP+report if more). Commit `feat(api): GET /analytics/writing — dailies, streaks, goals`.

### Task E5: Goals storage — ProjectSettings `writing_goals` + settings PATCH
Files: Modify `apps/api/narrare/planning/`-or-wherever ProjectSettings lives (models + schemas + service field; locate first); Create migration `0046_writing_goals.py` (JSONB NULL); Tests (set/unset/round-trip; 422 garbage). Commit `feat(api): novel writing_goals setting + Alembic 0046`.

### Task E6: FE — hook + types
Files: `lib/api/analytics.ts` (+WritingReport types + fetch), `lib/hooks/useAnalyticsWriting.ts` (+novelId param), tests (msw). Commit `feat(web): useAnalyticsWriting hook`.

### Task E7: FE — Writing tab panel
Files: `components/analytics/WritingStatsPanel.tsx` (+ subcomponents if RULE-04 forces: DailyWordsChart, StreakCard, GoalProgress, NovelSelector — same dir), page.tsx tabs extension, i18n en/de/fr (`analytics.writing.*`), tests (chart/streak/goal/selector states). Pre-approved up to 8 files (FE slice + i18n trio). Commit `feat(web): writing stats tab (en/de/fr)`.

### Task E8: FE — goal editing in novel settings
Files: the novel settings surface component (locate; where ProjectSettings fields edit) + i18n + tests. Commit `feat(web): novel writing goal setting (en/de/fr)`.

### Task E9: Docs closure + ADR-095 flip
Files: `STATS-001-writing-stats.md` (v1-as-built; status → stable; CLI-retired already noted), `ADR-095-*.md` (→ ✅ Implemented), `INDEX.md` (row), feature INDEX row note, `CURRENT_STATE.md` entry. Full gate. Commit `docs: close STATS-001 v1 — ADR-095 implemented`.
