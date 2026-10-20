# E2E Coverage Matrix

Source of truth: `docs/superpowers/specs/2026-10-11-e2e-full-suite-design.md` §5.
Update the Status column with every suite task; gates reference audit
findings (`docs/superpowers/reports/2026-10-11-e2e-ui-audit.md`).

| Spec | Features | Audit gates | Status |
|---|---|---|---|
| *(foundation)* helpers + catalog + runner + smoke | — | E01 E04 | ✅ done (2026-10-12) |
| test_ai_writing.py (+ `_selection`, `_ws` split per RULE-04 400-line cap) | WRITE-002/003/004/005/006/007/009 | B01 B02 B08 B09 M06 | ✅ done (2026-10-13) — M06 fixed in-slice (accept guard + honest errors); co-author reachability (B09 residual) + N08 fixed in-slice per the 2026-10-13 PO rulings (Tasks 4–5) and pinned green |
| test_kb_management.py | KB-001/008 | B04 N14 M01 | ✅ done (2026-10-18) — 7 specs; two spec-forced product fixes landed (jsonb-null metadata seam + relationship-dialog overlay); M01 extract-storm pinned at exactly one POST |
| test_kb_management_merge.py | KB-009/005 | N15 N16 | ✅ done (2026-10-18) — 2 specs; merge via the REAL deterministic corpus job (N16), suggestions pinned as an API-surface probe (N15 — ADR-088 dormancy, see honest-gap notes) |
| test_kb_ai.py | KB-002/003/004 | B03 B05 B06 | ✅ done (2026-10-18) — 7 specs incl. both former xfail legs flipped green (F10 tags crash fixed upstream; Q2 interview via the `kb_assist_question` catalog capability, the designed E04 answer); D-1 pinned on the REAL orchestrator (panel-dispatch capture + wire refresh) |
| test_kb_ai_bulk.py | KB-007 + corpus | — | ✅ done (2026-10-18) — 2 specs; estimate → start → status → results on the REAL server-side job, incl. terminal-`cancelled` status and per-chapter results asserts |
| test_wiki.py | WIKI-001 | M11 N20 | ✅ done (2026-10-18) — 4 specs; N20 covered (fixed in Task 5, pinned graceful-empty green — no xfail rows this batch); staleness lifecycle + D-8 finalize path via the REAL event producer (see honest-gap notes) |
| test_analysis.py (+ `_streams`, `_voice` split per RULE-04 400-line cap) | ANAL-001..005/007/008/009 | B07 E03 N11 N12 N13 | ✅ done (2026-10-20) — 15 specs in three files; B07 pinned green (blocker-wave fix holds); E03 fixed in-wave (503 `NLP_NOT_CONFIGURED` + `NLPProviderError` handler; sentiment happy leg skipif-guarded on model presence — CI installs the models); N11 fixed in-wave (roster-gated attribution; REAL-stream prefix + panel pins, RED-discriminated by inverted probes); N12 fixed in-wave (readability AI phase composes the full response model; graceful-skip seam integration-pinned); N13 fixed in-wave (422 `WORD_COUNT_BELOW_MINIMUM` wire pin). Honest gaps: see analysis wave notes |
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

## kb + wiki wave notes (2026-10-18)

- **22 new specs** across five modules: `test_kb_management.py` (7),
  `test_kb_management_merge.py` (2), `test_kb_ai.py` (7, incl. both legs flipped
  from xfail to green), `test_kb_ai_bulk.py` (2), `test_wiki.py` (4). No xfail
  remains in this batch. New helpers: `kb_world` (seeding, mode navigation,
  `capture_json_response`, `track_posts` network counting) and `kb_interview`
  (`open_assisted_fields_view`, extracted to honor the RULE-04 400-line cap).
- **Product fixes landed in-slice and pinned green** (9 fix commits): the
  CONS-001 analyzer route-mode fix (the governed consistency path composes);
  M01 extraction `startedRef` + cancel guard; M11 wiki `entity_name` + paged
  generate-all + honest status; N20 graceful-empty (D-6 reversed the planned
  xfail); metadata/tags null-class schema defaults + FE guards (with the forced
  `schemas_references` split); F9-2 assist prompt-context feed, F9-1
  complete-with-name (BE + FE) with the REST transport switch, F9-3
  StrictMode-safe `useAIOperation` lifecycle; wiki staleness version-gate +
  system-session teardown commit + search scope; embeddings NaN zero-vector
  poisoning guard + novel-scoped search.
- **Mock catalog grew** (`tests/e2e/mocks/catalog_kb.py`):
  `kb_consistency_check` happy plus error variants for `kb_improve`,
  `kb_extraction`, `wiki_refresh` (Task 6), and `kb_assist_question`
  happy/error — the E04 designed answer for the interview Q1→Q2 leg,
  validated against the real session + question models.
- **Honest-gap notes:**
  - **N15** (KB-005 suggestions) is pinned as an **API-surface probe only**:
    the endpoint contract is healthy, but the UI has zero consumers (ADR-088
    dormancy). A UI leg is deliberately out of scope until a consumer exists.
  - **N16** (KB-009 merge) is **corpus-job-gated**: the review UI arms only
    after a COMPLETED corpus job's dedup block, and the seeds must be
    calibrated NEAR-duplicates meeting the REVIEW threshold (exact dupes are
    suppressed by design) — the spec documents this reachability constraint
    rather than fixing it. Structurally, the merge spec depends on
    `complete_wizard` persisting a provider server-side (the suite's first
    server-side LLM E2E).
  - **D-8 parity note** (chapter-finalize → wiki summary): there is no manual
    chapter-status UI; the `chapter.finalized` event path is the only producer,
    so the spec drives the real chapter PATCH and observes the event-driven
    generation.
  - **Runner lever:** `test_kb_ai.py` makes ~7 AI-limited calls under one
    module user, so `NARRARE_RATE_LIMIT_ANALYSIS=100` is exported by
    `scripts/run_e2e.sh` as of this commit (2026-10-18) — inert under the
    runner's own `NARRARE_E2E_TEST` mode (limiter dep + pacer short-circuit)
    and biting only in live-stack runs without the flag (defensive, same
    precedent as `NARRARE_RATE_LIMIT_WS=100`).
- **Carried backlog (unchanged from the ai-writing wave):** the global
  `AI_WS_LIMITER` bucket and the interactive-mode Save-to-Chapter dead path
  stay backlog, documented in the `test_ai_writing_ws.py` module docstring.
- **Hardening notes (reviewer minors, backlog):** a DB-level integration pin
  for the embeddings NaN guard, and extra cancel-timing margin in the bulk
  cancel spec.
- **FLAKE_WATCH:** one unattributed blank-page failure (all-white screenshot,
  not reproduced in 4 subsequent green runs) and one long-uptime dev-stack
  renderer-crash episode (~4 h uptime; a full restart restored everything) —
  both recorded verbatim in the 2026-10-15 kb-wave SDD ledger. Neither
  reproduced after the documented fixes; watch on the next full-suite run.

## analysis wave notes (2026-10-20)

- **15 new specs** across three modules: `test_analysis.py` (5 + 1 sentiment
  skipif), `test_analysis_streams.py` (6), `test_analysis_voice.py` (4).
  New helper: `analysis_world` (`ANALYSIS_TRIGGERS` accessible-name map —
  toolbar triggers name themselves by TOOLTIP, not visible label, a trap
  documented in Task 8; `open_analysis_panel` with the `?panel=` URL-sync
  toggle guard; `sentiment_models_available`; `seed_voice_profile`).
  Mock catalog grew (`tests/e2e/mocks/catalog_analysis.py`): `beta_reader`,
  `coreference_stream`, `character_voice_stream`, `consistency_stream`,
  `consistency_check` happy+error, and NEW `pov` happy+error (Task 7) so
  the POV panel content is deterministic independent of TestModel.
- **Product fixes landed in-slice and pinned green** (6 fix commits): N12
  readability kb-supply (the AI sentence phase never composed — live-probed
  `PromptVariableError` swallowed by graceful-skip; compose path now runs
  and the skip seam is integration-pinned); N13 beta-reader min-words 422
  `WORD_COUNT_BELOW_MINIMUM` (was a silent 500-escape; wire body pinned);
  E03 spaCy provider 503 `NLP_NOT_CONFIGURED` (error-class contract +
  `NLPProviderError` handler, integration-pinned); N11 pt1 character-voice
  roster gate (action-beat garbage attractors In/Order/About/Ahead demoted
  before the progress event); N11 pt2 drift + check roster fold
  (PO-approved 6-file fold); M05 seven-panel error-copy i18n fold
  (PO-approved; EN `aiActions.errorConnection` copy pinned in the
  coreference + character-voice + voice-check panels, DE copy asserted
  absent).
- **Honest-gap notes:**
  - **Sentiment (ANAL-002) is skipif-guarded on the spaCy models:** the
    runner venv lacks `en_core_web_md`, so the REAL deterministic leg
    skips with the documented reason (`just install-nlp-models` hint +
    E03/D-3 stance); the 503 degradation is integration-pinned
    (`tests/integration/analysis/test_sentiment_degradation.py`); CI's
    `test-e2e` installs the models, so the nightly exercises the real leg.
  - **Voice-check real-stream leg dies under TestModel (E04):** the checker
    agent's output validator raises `ModelRetry` with a stored profile, so
    the agent phase always dies in-band before any result event. The spec
    pins the deterministic roster prefix (`"1 speaking character(s) (1
    with stored profiles)"` — also the N11 pt2 pin) plus the honest panel
    degradation; a `voice_check_stream` catalog fixture is the recorded
    follow-up for a real result-card pin.
  - **CONS-001 stream content is pinned as the catalog subset:** the exact
    stage vocabulary (`extracting_facts → checking_consistency`) and result
    fields are asserted on the captured wire of the mocked stream, plus the
    rendered "Consistent" in the panel; a REAL-stream content leg has no
    deterministic pre-agent event to pin today. Task-9 review minors (a
    `[DONE]`-terminated-wire assert, full-vocabulary + DE-negation pins)
    are queued for the next touch.
  - **The beta-reader deep-dive (Phase 2) is not E2E-covered:** a
    catalog-mocked Phase 1 yields a fake `cache_key`, and a real Phase 1 is
    E04-blocked under TestModel — documented as follow-on coverage.
  - **Drift/check agent-classification tails are structural pins only**
    (TestModel synthesizes empty agent fields; E04 strictness) — the
    roster-gated prefixes are the discriminating pins.
  - **`userMessage`-based German fallbacks OUTSIDE the seven analysis
    panels** (ChatPanel, DialogueCoachPanel, kb/ConsistencyCheckPanel + the
    systemic `userMessage` mapper cleanup) remain the M05 wave's slice.
- **Runtime budget (D-8, PO-confirmed ≤ 7 min added):** measured actuals
  recorded in the Runtime budget table below — the batch lands at
  ≈ 1.2–2.2 min for all 15 specs, and the full suite stays within the
  ≤ 25 min target.

Next waves per spec §5: `test_import_export.py`, then
`test_stats_budget.py`, `test_volumes_scenes.py`,
`test_series_scratchpad.py`, `test_settings_auth.py` (the M05 wave — it
inherits this wave's seven-panel i18n down-payment plus ChatPanel,
DialogueCoachPanel, kb/ConsistencyCheckPanel, and the systemic
`userMessage` mapper cleanup), `test_onboarding.py`. PO-backlog candidates
surfaced by this wave: beta-reader Phase 2 deep-dive E2E coverage
(E04-blocked on a real Phase 1), a `voice_check_stream` catalog leg, an FE
i18n key rendering the 422 `WORD_COUNT_BELOW_MINIMUM` body in the
beta-reader panel, the `AnalysisError`→`NarrareError` wholesale re-base
decision (D-2 alternative 3), and the drift agent-classification content
pins once a validator-loose fixture strategy exists for
`CharacterVoiceDriftAgent`.

## Runtime budget (spec §7 — full local suite ≤ 25 min)

| Module | Target | Measured |
|---|---|---|
| test_ai_writing.py (WRITE-002/007) | ≤ 3 min | 23.84 s / 24.73 s (7 specs, two consecutive runs — Task 10; Task 7's 5-spec iteration: 24.19 s / 27.45 s) |
| test_ai_writing_selection.py (WRITE-003/004/006/009) | ≤ 2 min | 17.81 s / 18.64 s (5 specs, two consecutive runs — Task 9; Task 8's 2-spec iteration: 12.68 s / 10.73 s) |
| test_ai_writing_ws.py (WRITE-005 + N08 pin) | ≤ 90 s | 10.94 s / 10.99 s (2 specs, two consecutive runs — Task 11) |
| test_kb_management.py (KB-001/008) | ≤ 3 min | 22.3–25.1 s (7 specs; three stable consecutive runs 22.3/22.5/22.6 s — Task 7; post-fix-round runs 23.21/23.55 s, then 25.13 s after the honest teardown revert) |
| test_kb_management_merge.py (KB-009/005) | ≤ 2.5 min | 13.41–15.56 s (2 specs, four runs across three pytest-randomly seeds — Task 8; corpus polling dominates at ~2 s) |
| test_kb_ai.py (KB-002/003/004) | ≤ 2.5 min | 72.9–76.1 s in the spec-readd era (7 specs, ~20 green runs, two legs xfail at the time); post-flip module 7/7 green, fastest full-module run 25 s (slice report) |
| test_kb_ai_bulk.py (KB-007) | ≤ 1.5 min | 16.40 s solo (2 specs — Task 10) |
| test_wiki.py (WIKI-001) | ≤ 1.5 min | 20.97 s solo (4 specs — Task 11); combined with bulk: 35.04/35.43/35.88 s × 3 seeds |
| test_analysis.py (ANAL-001/002/004 + N12/N13 pins) | ≤ 2.5 min | ≈ 22–28 s (5 passed + 1 sentiment skip, three consecutive runs; 8 consecutive green runs after the fix round — Task 8) |
| test_analysis_streams.py (ANAL-005/008 + CONS-001 stream) | ≤ 2.5 min | 27.2–38.7 s (6 specs, three consecutive runs across pytest-randomly seeds — Task 9) |
| test_analysis_voice.py (ANAL-007/009 + N11 pt2) | ≤ 2 min | 23.5–62.7 s (4 specs; four runs 28.4/35.0/62.7/60.6 s — Task 10; 23.48 s post-fix re-run with tightened pins) |

ai-writing wave total ≈ 53 s for all 14 specs (sum of one run per module).
KB + wiki batch total (D-9, PO-confirmed ≤ 11 min added on
`E2E_FRONTEND_MODE=dev`): **≈ 1.7–2.5 min for all 22 specs** (sum of one run
per module; the range is driven by the two `test_kb_ai` measurements) — the
batch consumes well under a quarter of its budget, and the full suite stays
within the ≤ 25 min target. Analysis batch total (D-8, PO-confirmed
≤ 7 min added): **≈ 1.2–2.2 min for all 15 specs** (sum of one run per
module; the voice module's spread covers its four runs incl. one slow
outlier) — under a third of the batch budget, suite target intact.
