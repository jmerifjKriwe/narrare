# STATS-001 — Writing Statistics v1 (with Goals) — Design

- **Date:** 2026-10-07
- **Status:** PO-ratified (decision sheet item E: delta-events, WITH targets; sequencing C→D→B→A→E)
- **Feature:** `docs/features/analytics/STATS-001-writing-stats.md` (status flips at closure; CLI retired by the foundation PR)
- **ADR:** ADR-095 — Writing Activity Capture (on main since PR #241) records every decision below; flips to Implemented with this cycle

---

## 1. Decisions (binding; mirrors ADR-095)

| # | Decision | Ruling |
|---|----------|--------|
| E-1 | Capture model | **Delta events** on content-write surfaces; NO snapshots, NO session tracking, NO manual entry (all rejected — see ADR-095). New table `writing_activity_events` (user_id FK RESTRICT, novel_id FK SET NULL, chapter_id FK SET NULL NULL, `delta_words` signed INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL, UTC). |
| E-2 | Write surfaces (exhaustive) | `chapters/service.py update_content` (editor PATCH incl. version-restore path), chapter **create-with-content**, chapter delete (negative net words), co-author apply (`coauthor_apply_service.py`), import commit (`importing/service.py append_chapters` — one event per imported chapter, **day-of-import attribution, no backdating**). Zero-delta events skipped (empty creates/restores). Written by a contract-first `WritingStatsRecorder` (never-raises — RULE-11 graceful class, log-only on failure; stats capture must never break a write). **Ruled excluded (2026-10-08): demo/sample seeding** (`setup/demo_loader.py`) — system-generated sample content is not user writing activity, unlike user-initiated import. Novel-deletion cascade leaves historical events (activity ≠ current manuscript). |
| E-3 | Derivation | Dailies/streaks/heatmap **derived at read time** over the events (UTC-day bucketing mirroring `analytics/repository.py`); streak = consecutive days with ≥1 event; calendar heatmap from daily totals; hour-of-day derivable later (timestamps kept). |
| E-4 | Goals (PO addition) | Novel-scoped `writing_goals` on `ProjectSettings` (JSONB: `{target_words: int | None}` v1 — room to grow). **Progress = live `SUM(chapters.word_count)` for the novel** (NOT the activity-event sum — events have a day-0 boundary; pre-existing manuscript words must count). Goals read state; dailies read events. |
| E-5 | API | `GET /api/v1/analytics/writing` (auth; optional `novel_id` query param — ownership-gated when present, 404 foreign≡unknown) returning: dailies for the last N days (N=90 v1), current + longest streak, today's words, totals; and when `novel_id` present: the goal block `{target_words, current_words, progress_pct}`. Novel list for the selector: existing novels endpoint. Goal set/unset: extend the project-settings PATCH surface (mirror sibling field patterns; RULE-14 migration if ProjectSettings gains a column — JSONB column `writing_goals` NULL, migration 0045). |
| E-6 | FE | Second tab "Writing" in the existing `/analytics` PanelTabs: daily-words bar chart (Recharts, no new dep), streak card (current/longest), today's words, optional novel selector → goal progress bar when a target is set. Goal editing lives in the novel settings surface (where sibling ProjectSettings fields are edited). i18n en/de/fr (`analytics.writing.*` + settings keys). |
| E-7 | Import honesty | Imported words attribute to the import day (documented in the panel help: history begins when Narrare first saw the novel); deletes are negative deltas (net-words honesty). |

## 2. Testing Strategy

Recorder: called on every surface (unit tests per call site); zero-delta skip; never-raises (failure ⇒ log, write proceeds); signed deltas correct (increase/decrease/restore-to-identical ⇒ 0 ⇒ skip). Repository: UTC-day aggregation, streak math (gaps, month/year boundaries, leap Feb), user/novel scoping, half-open windows. Service/router: default window, novel filter + ownership 404, goal block math (pct rounding, no-target ⇒ None). FE: chart renders dailies, streak card, goal progress bar states, novel selector, i18n parity. Migration 0045 round-trip.

## 3. Out of Scope

Session tracking · manual entry · hour-of-day heatmap (v1 renders day heatmap only; data supports later) · per-chapter breakdowns · goal types beyond target_words · export of writing stats · notifications/streak reminders.
