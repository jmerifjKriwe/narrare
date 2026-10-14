# E2E Coverage Matrix

Source of truth: `docs/superpowers/specs/2026-10-11-e2e-full-suite-design.md` §5.
Update the Status column with every suite task; gates reference audit
findings (`docs/superpowers/reports/2026-10-11-e2e-ui-audit.md`).

| Spec | Features | Audit gates | Status |
|---|---|---|---|
| *(foundation)* helpers + catalog + runner + smoke | — | E01 E04 | ✅ done (2026-10-12) |
| test_ai_writing.py (+ `_selection`, `_ws` split per RULE-04 400-line cap) | WRITE-002/003/004/005/006/007/009 | B01 B02 B08 B09 M06 | ✅ done (2026-10-13) — M06 fixed in-slice (accept guard + honest errors); co-author reachability (B09 residual) + N08 fixed in-slice per the 2026-10-13 PO rulings (Tasks 4–5) and pinned green |
| test_kb_management.py | KB-001/008/009 | B04 B06 M01 N14 N15 N16 | pending |
| test_kb_ai.py | KB-002/003/004/005/007 + corpus | B03 B05 B06 | pending |
| test_wiki.py | WIKI-001 | M11 | pending |
| test_analysis.py | ANAL-001..005/007/008/009 | B07 E03 N11 N12 N13 | pending |
| test_import_export.py | SETUP-003, export | N18 | pending |
| test_stats_budget.py | STATS-001/002 | M02 | pending |
| test_volumes_scenes.py | WRITE-011, PLAN-001 | M09 M10 | pending |
| test_series_scratchpad.py | SERIES-001..004, NOTES-001 | N02 | pending |
| test_settings_auth.py | SETUP-004, auth, i18n | M03 M04 M05 M07 M08 N04 N05 N06 | pending |
| test_onboarding.py | SETUP-001/002, ONBOARD-001 | N17 | pending |

Existing pre-foundation specs (auth, wizard, editor, chapters, dashboard,
settings, KB worldbuilding, WS ticket, hero flow) are maintained in place.

## ai-writing wave notes (2026-10-13)

- **14 new specs** across three modules: `test_ai_writing.py` (7),
  `test_ai_writing_selection.py` (5), `test_ai_writing_ws.py` (2).
- **Product fixes landed in-slice and pinned green:** M06 trio (localized
  empty-form 422 + accept guard, honest stream-error and truncated-stream
  handling), co-author reachability via the bubble-menu entry (B09 residual),
  WS origin gate honoring test mode (N08; production posture unit-pinned).
- **Mock catalog grew** (`tests/e2e/mocks/catalog_writing.py`):
  `generation_stream/truncated`, `rewrite_stream/happy|error`,
  `story_suggest/happy|error`, `coauthor_stream/happy|error`.
- **Helpers:** `editor_ai` (editor prep: `prepare_ai_chapter`, `editor_text`,
  `focus_editor_end`, `open_generation_panel`, `click_panel_generate`),
  `ws_probe` (`WritingSocketTracker`, extracted from the ADR-084 gate), and
  `foundation.make_authed_request` (bearer-merge factory promoted at its
  third consumer).
- **Open product findings (backlog, not audit gates):** `AI_WS_LIMITER` is
  global in fact — `SingleBucketFactory` ignores the per-user key
  (`apps/api/narrare/_app/rate_limiter_dep.py`), so the 3 WS connects/min
  budget is shared per API process across all users and chapters; and
  interactive-mode Save-to-Chapter is a dead UI path — the prose buffer fills
  only via `user_feedback accept` (never sent by the FE) or interview
  auto-append, so Save always errors "Prose buffer is empty". Both are
  documented in the `test_ai_writing_ws.py` module docstring.

## Runtime budget (spec §7 — full local suite ≤ 25 min)

| Module | Target | Measured |
|---|---|---|
| test_ai_writing.py (WRITE-002/007) | ≤ 3 min | 23.84 s / 24.73 s (7 specs, two consecutive runs — Task 10; Task 7's 5-spec iteration: 24.19 s / 27.45 s) |
| test_ai_writing_selection.py (WRITE-003/004/006/009) | ≤ 2 min | 17.81 s / 18.64 s (5 specs, two consecutive runs — Task 9; Task 8's 2-spec iteration: 12.68 s / 10.73 s) |
| test_ai_writing_ws.py (WRITE-005 + N08 pin) | ≤ 90 s | 10.94 s / 10.99 s (2 specs, two consecutive runs — Task 11) |

Wave total ≈ 53 s for all 14 specs (sum of one run per module) — the
ai-writing additions consume under a minute of the 25-minute budget.
