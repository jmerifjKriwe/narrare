# E2E Coverage Matrix

Source of truth: `docs/superpowers/specs/2026-10-11-e2e-full-suite-design.md` §5.
Update the Status column with every suite task; gates reference audit
findings (`docs/superpowers/reports/2026-10-11-e2e-ui-audit.md`).

| Spec | Features | Audit gates | Status |
|---|---|---|---|
| *(foundation)* helpers + catalog + runner + smoke | — | E01 E04 | ✅ done (2026-10-12) |
| test_ai_writing.py | WRITE-002/003/004/005/006/007/009 | B01 B02 B08 B09 M06 | pending |
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
