# ADR-086 Ledger Migration Plan — Entries 6–39 (34 eager factories → lazy ModelResolution)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Slices use checkbox (`- [ ]`) syntax. One ledger entry per slice; check off the ADR entry in the SAME commit as its slice.

**Goal:** Clear ADR-086's migration ledger entries 6–39: replace every remaining construction-time `resolver.resolve(...)` / `token_limits_service.get_resolved_limits(...)` in DI factories with lazy first-use resolution via the landed `ModelResolution` primitives, so invalid request bodies yield `422` on ALL AI endpoints regardless of provider/DB state, and the FK-500 / 400-before-422 defect class is eradicated repo-wide.

**Base:** `50645efa` + the uncommitted working-tree batches (GIVEN — see §Coordination). Reference implementations are LANDED and production-proven in `1925bb76`: S2 (`ai_assist`), S3 (`memory`), S4a/S4b (`analysis`). This plan invents nothing new — it re-applies three proven patterns at scale.

**Not in scope:** the "Explicitly NOT in the ledger" list in ADR-086 (verified 2026-09-09); prompt/golden content changes (this migration is render-inert: resolution timing only); relocating router-resident factories (entry 14) unless a RULE-06 conflict forces it.

---

## 1. Reference patterns (all landed — copy, don't reinvent)

The three shapes every slice reduces to. Read these files before slice 1:

### Pattern S — mechanical (S2 `ai_assist`, S3 `memory`)

- **Factory** (`ai_assist/dependencies.py`, `memory/router_analysis.py`): replace
  `resolved = await resolver.resolve(intent, uid, novel_id)` + triad plumbing with
  `model_resolution = LazyModelResolution(lambda: resolver.resolve(<same args verbatim>))`,
  passed into the service ctor. Repos/registry/composer still wire eagerly.
- **Service** (`ai_assist/service.py:114-124`): ctor swaps `config`/`api_key`/`base_url`
  params for `model_resolution: ModelResolution`; gains idempotent
  `ensure_resolved()` (resolve → cache → reuse); every `registry.get_model(...)`
  call site reads the resolved triple from the cache. First-use call at the top of
  the entry-point method (post-validation by construction).
- **SSE router** (`ai_assist/router.py:96`): `await service.ensure_resolved()`
  BEFORE constructing the `StreamingResponse` → `ConfigurationError` stays a
  pre-header 400 (Decision 3).
- **Tests** (`tests/unit/api/ai_assist/test_dialogue_coach_service.py:276-282`):
  `test_no_resolution_at_construction` (fake resolver counts calls: 0 after factory)
  + `test_ensure_resolved_resolves_once_and_is_idempotent`. Existing service unit
  tests migrate mechanically to `StaticModelResolution` (as done for 20+ files in
  `1925bb76`).

### Pattern M-budget — deferred token-limits composition (S4b `analysis`)

Everything in S, plus (`analysis/dependencies_beta_reader.py:139-156`):
`get_resolved_limits` moves into a factory-defined async closure
(`compose_budget_assembler`) that awaits the (cached) routing resolution AND the
token-limits cascade, then composes the derived artifact (budgets, assembler,
capped config). Service receives the closure as
`Callable[[], Awaitable[X]]`, awaits + caches at first use
(`beta_reader_service.py:148-151`). RULE-18b: both cascades keep their sources —
only timing moves.

### Pattern M-graceful — degradation preserved, moved past validation

For factories that today swallow `ConfigurationError` (planning 20–24, entry 34):
the factory's try/except disappears from wiring; the SERVICE's first-use path does
`try: resolved = await resolution.resolve() except ConfigurationError: <degraded
state>` (log + AI-optional behavior, exactly as today). Degradation is service
policy (RULE-11 semantics per feature), not wiring — so NO new adapter primitive.

**Rejected alternative:** a `GracefulModelResolution` adapter returning
`ResolvedModel | None` in `dependencies_services.py` — forks the Protocol return
contract, multiplies primitives (RULE-04: S1 deliberately shipped exactly three),
and hides RULE-11 policy inside wiring. **Also rejected:** passing bare coroutine
factories per service — that is `ModelResolution` ad hoc, i.e. ADR-086 Option (e)
in disguise.

---

## 2. Global constraints (binding on every slice)

1. **Timing-only invariant.** Preserve each factory's existing `LLMIntent`,
   user/project args, temperature overrides (`dataclasses.replace(...)`), and
   cascade call ORDER verbatim. What moves is WHEN, never WHAT.
2. **≤3 prod files per slice.** Typical: factory + service (+ router for SSE).
   If a slice needs a 4th, split it (sub-slices Lxx.a/Lxx.b) — never relax the cap.
3. **Render-inert tripwire.** No prompt templates, composer contexts, or goldens
   change. If a slice's diff touches `core/prompts/` or a golden shifts, STOP —
   that is scope leakage, not migration.
4. **RULE-11 loud propagation** on AI-mandatory endpoints; the graceful set is the
   sanctioned exception and must ASSERT its degradation (not just not-crash).
5. **MUST NOT change:** 401-no-auth nodes; ownership/IDOR gate ordering (gates stay
   ahead of resolution); P2 novel-guard 404 semantics (now post-validation); SSE
   happy-path with override; existing service unit-test outcomes (ctor migration
   aside).
6. **Ledger discipline.** Flip the ADR entry in the same commit (§6 convention).
   Never pre-check, never batch-check without the slice.
7. **Standard gates per slice:** targeted domain suites (§5), `just typecheck`
   (src+tests), ruff clean, `python scripts/check_architecture.py` exit 0,
   python-size gate (services gaining `ensure_resolved` may cross the 300-line
   RULE-04 threshold → split per module convention if so, and say so in the report).
8. **English; no new core-package changes; no `packages/core` imports of the
   abstraction** (it is API-app-local by design).

---

## 3. Ledger classification (all 34 entries)

Effort: **S** = Pattern S (factory+service ctor swap + first-use resolve).
**M** = extra deferral (budget composition / dual resolves / graceful
degradation / WS lifecycle). SSE column = router has `StreamingResponse`
(verified by sweep, not just ledger annotation — MORE routers stream than the
ledger marks).

| # | Module / factory | Consumer service | Effort | Special notes |
|---|---|---|---|---|
| 6 | `analysis/dependencies_character_voice.py` — `get_character_voice_service` | `CharacterVoiceService` | S | SSE (`router_character_voice.py`). VOICE, novel-scoped. |
| 7 | `analysis/dependencies_coreference.py` — `get_coreference_service` | `CoreferenceService` | S | SSE (`router_coreference.py`). ANALYSE, novel-scoped. |
| 8 | `analysis/dependencies_voice_check.py` — `get_voice_check_service` | `CharacterVoiceCheckerService` | S | SSE (`router_voice_check.py`). `consumer_provider` closure is unrelated deferral — leave untouched. |
| 9 | `analysis/dependencies_author_voice.py` — `get_author_voice_service` | `AuthorVoiceService` | S | SSE (`router_author_voice.py`). |
| 10 | `analysis/dependencies_author_voice_drift.py` — `get_author_voice_drift_service` | AuthorVoiceDrift service | S | SSE (`router_author_voice_drift.py`) — ledger-marked. |
| 11 | `analysis/dependencies_voice_drift.py` — `get_voice_drift_service` | VoiceDrift service | S | SSE (`router_voice_drift.py`) — ledger-marked. Same `consumer_provider` note as #8. |
| 12 | `chat/dependencies.py` — `get_chat_service` | `ChatService` | S | SSE (`chat/router.py:84`). **DIRTY-TREE INTERSECTION**: `chat_service.py`, `chat/_context.py` are in the uncommitted batch — slice blocked until it lands (§7). Verify no anonymous branch (resolve is `UUID(user_id)`-mandatory today). |
| 13 | `consistency/deps.py` — `get_consistency_service` | `ConsistencyCheckerService` (+ staged orchestrator) | M | TWO eager resolves (fact-extraction + consistency) with temp overrides 0.2/0.3 → two `LazyModelResolution`s, overrides applied at first use. SSE (`consistency/router.py:106`). |
| 14 | `generation/router.py` — `_get_service` | `NameGeneratorService` | S | Factory lives in the router file (pre-existing layout; relocation OUT of scope). No SSE. `project_id` may be None — preserve. |
| 15 | `kb/_consistency_deps.py` — `get_consistency_service` | KB consistency service | M | TWO eager resolves (consistency + worldbuild) → dual lazy wiring. No SSE in kb module. |
| 16 | `kb/dependencies_extraction.py` — `get_extraction_service` | `ExtractionService` | S | KB_EXTRACT, novel-scoped. |
| 17 | `kb/dependencies_improve.py` — `get_kb_improve_service` | `KBImproveService` | S | |
| 18 | `kb/dependencies_session.py` — `get_kb_session_service` | `KBSessionService` | S | See `tests/integration/kb/_assist_fakes.py` (uncommitted) for fake-shape expectations. |
| 19 | `kb/dependencies_worldbuilding.py` — `get_worldbuilding_service` | `WorldbuildingService` | S | |
| 20 | `planning/_character_arc_factory.py` — `get_character_arc_service` | `CharacterArcService` | M | Graceful degradation (try/except `ConfigurationError` → `model_config=None`). Factory ALSO eagerly runs uid-scoped novel guard (`NotFoundError`) — see planning note below. |
| 21 | `planning/_service_factory.py` — `get_storyboard_service` | `StoryboardService` | M | Same planning shape as #20. |
| 22 | `planning/_timeline_analysis_factory.py` — `get_timeline_analysis_service` | TimelineAnalysis service | M | SSE (`planning/router_timeline_analysis.py:87`) — the only planning SSE endpoint. |
| 23 | `planning/_timeline_consistency_factory.py` — `get_timeline_consistency_service` | TimelineConsistency service | M | |
| 24 | `planning/_timeline_extraction_factory.py` — `get_timeline_extraction_service` | TimelineExtraction service | M | |
| 25 | `series/dependencies.py` — `build_band_summary_service` (via `get_band_summary_service`) | `BandSummaryService` | M | Resolve + eager `get_resolved_limits` (M-budget). **Shared with the in-process background task** (`generate_band_summary_inprocess`): lazy closure must capture the task's own session/resolver — first use then happens at task runtime with the session still open; assert that in tests. |
| 26 | `series/dependencies_consistency.py` — `get_series_consistency_service` | Series consistency service | S | ANALYSE, no project tier. |
| 27 | `series/dependencies_context_preview.py` — `get_series_history_preview_service` | Series history preview service | M | Resolve + `get_resolved_limits` (M-budget, S4b shape). |
| 28 | `series/dependencies_voice.py` — `get_series_voice_service` | Series voice service | S | VOICE, no project tier. |
| 29 | `series/dependencies_voice_drift.py` — `get_series_voice_drift_service` | Series voice drift service | S | |
| 30 | `wiki/dependencies.py` — `get_wiki_service` | `WikiService` | S | SUMMARIZE, novel-scoped, user-facing refresh only — startup listener stays operator-routed (out of ledger). |
| 31 | `writing/deps_coauthor.py` — `get_coauthor_service` | `CoauthorService` | M | Resolve + limits (M-budget). SSE (`router_coauthor.py:72`). `get_coauthor_apply_service` in same file is NOT in the ledger — do not touch beyond import hygiene. |
| 32 | `writing/deps_extend.py` — `get_extend_service` | `ExtendService` | M | M-budget. SSE. `extend_service.py` already has a pre-stream `prepare()` seam — anchor first-use resolve there. |
| 33 | `writing/deps_rewrite.py` — `get_rewrite_service` | `RewriteService` | M | M-budget. SSE. Same `prepare()` seam anchor (`rewrite_service.py:80+`). |
| 34 | `writing/deps_story_suggest.py` — `get_story_suggest_service` | `StorySuggestService` | M | **Graceful degradation** (factory swallows `ConfigurationError` — AI-optional): preserve degradation at first use, post-validation (Pattern M-graceful). SSE (`router_story_suggest.py:74`). |
| 35 | `writing/deps_style_variants.py` — `get_style_variant_service` | `StyleVariantService` | M | M-budget. SSE (`router_style_variants.py:86`). |
| 36 | `writing/deps_suggest.py` — `get_suggest_service` | `SuggestService` | S | Resolve-only. SSE (`router_suggest.py:81`). `prepare()` seam anchor (`suggest_service.py:117`). |
| 37 | `writing/deps_writing.py` — `get_writing_service` | `WritingService` | M | M-budget. SSE (`writing/router.py:94`). |
| 38 | `writing/summary_deps.py` — `get_summary_service` | SummaryService | M | M-budget. REST (no SSE). |
| 39 | `writing/router_sessions.py` — `interactive_session` (inline, via `resolve_ws_session_config`) | WS handler chain (`ws_factory.build_writing_session_handler` → turn service) | M | **WebSocket, not HTTP**: no body validation → 422 rationale N/A; goal is removing the eager model resolve from bootstrap (`ws_session_config.py:159-168`: resolve + `temp=0.7/max_tokens=output_limit` composition → lazy closure threaded into the handler). Token limits STAY at bootstrap (feed `ws_timeout`/handler ctor — deferring would restructure handler lifecycle; accepted residual, note in report). Resolution failure at first AI turn must surface as a typed error/close frame per existing WS conventions — never an unhandled mid-turn crash. **DIRTY-TREE INTERSECTION**: `router_sessions.py`, `ws_factory.py`, `ws_context_assembler.py` uncommitted — blocked until landed. May exceed 3 files (turn service) → pre-authorized split L39a (config threading) / L39b (turn-service first-use). |

**Planning guard note (entries 20–24, binding):** the factories eagerly run a
**uid-scoped** novel guard (`novel_repo.get_by_id(novel_id, uid)` → 404). The
resolver's internal P2 guard must NOT be assumed equivalent (existence vs
ownership scoping — verify before relying on it). Default ruling: move the
uid-scoped guard INTO the service's first-use path, immediately BEFORE
`resolve()`, preserving gate-before-resolution ordering. Do not drop it.

**Effort mix: 17 S / 17 M.**

---

## 4. Slice plan (dependency-ordered batches, ≤3 prod files each)

Slices are named `L<ledger-entry>`; one entry per slice (no two entries share a
service file, so pairing always breaks the 3-file cap). Gate slice `G1` closes
the ledger. Session packing at 8–10 slices/session follows in §8.

### Batch A — analysis SSE wave (validates Pattern S + pre-header at scale)
Rationale first: 6 structurally identical SSE slices compound the S2 pattern and
prove the pre-header contract six times over before anything harder.
- [ ] A1 / L06 — `dependencies_character_voice` + `character_voice_service` + `router_character_voice` (3 files)
- [ ] A2 / L07 — coreference triple (3 files)
- [ ] A3 / L08 — voice_check triple (3 files)
- [ ] A4 / L09 — author_voice triple (3 files)
- [ ] A5 / L10 — author_voice_drift triple (3 files)
- [ ] A6 / L11 — voice_drift triple (3 files)

### Batch B — non-SSE warm-down
- [ ] B1 / L14 — `generation/router.py` factory + name-generator service (2 files)
- [ ] B2 / L30 — `wiki/dependencies.py` + wiki service (2 files)

### Batch C — kb domain
- [ ] C1 / L16 — extraction (2 files)
- [ ] C2 / L17 — improve (2 files)
- [ ] C3 / L18 — session (2 files)
- [ ] C4 / L19 — worldbuilding (2 files)
- [ ] C5 / L15 — `_consistency_deps` dual-resolve (2–3 files: factory + service [+ staged orchestrator])

### Batch D — series domain
- [ ] D1 / L26 — consistency (2 files)
- [ ] D2 / L28 — voice (2 files)
- [ ] D3 / L29 — voice_drift (2 files)
- [ ] D4 / L27 — context_preview, M-budget (2–3 files)

### Batch E — writing core wave (prepare-seam anchors)
- [ ] E1 / L36 — suggest, S (2 files)
- [ ] E2 / L33 — rewrite, M-budget (3 files: factory + service + `router_rewrite`)
- [ ] E3 / L32 — extend, M-budget (3 files)
- [ ] E4 / L31 — coauthor, M-budget (3 files)

### Batch F — writing budget rest + series background task
- [ ] F1 / L35 — style_variants, M-budget (3 files)
- [ ] F2 / L37 — writing, M-budget (3 files)
- [ ] F3 / L38 — summary, M-budget (2 files, REST)
- [ ] F4 / L25 — band summary, M-budget + background-task invariant (2–3 files)

### Batch G — graceful-degradation wave (highest judgment load — after pattern fluency)
- [ ] G1 / L20 — character_arc (2–3 files; planning guard note applies)
- [ ] G2 / L21 — storyboard (2–3 files)
- [ ] G3 / L22 — timeline_analysis (3 files, SSE pre-header)
- [ ] G4 / L23 — timeline_consistency (2–3 files)
- [ ] G5 / L24 — timeline_extraction (2–3 files)
- [ ] G6 / L34 — story_suggest, graceful + SSE (3 files)

### Batch H — consistency dual + SSE
- [ ] H1 / L13 — `consistency/deps.py` dual-resolve, temp overrides at first use (3 files: deps + service/orchestrator + router)

### Batch I — dirty-tree entries (BLOCKED until §7 preconditions)
- [ ] I1 / L12 — chat (2–3 files: dependencies + chat_service [+ router pre-header line])
- [ ] I2 / L39 — writing WS session bootstrap (3 files, or L39a/L39b split)

### Batch J — whole-ledger gate
- [ ] J1 / G1 — ledger-empty sweep + architecture prevention check + ADR close-out (§6)

**Dependency order:** A→B→C→D→E→F→G→H→I→J. Hard edges: I1/I2 after §7;
J1 strictly last. All other edges are soft (risk-graduation ordering: identical-S
first, budget-M mid, graceful-M late).

---

## 5. Per-slice regression contract + verification protocol

Every slice's PR must show, beyond the standard green gates:

**Regression contract (unit):**
1. `test_no_resolution_at_construction` — factory invoked with a call-counting
   fake resolver → 0 resolve calls (and 0 `get_resolved_limits` for M-budget).
2. First-use: entry point triggers exactly ONE resolve; idempotent on repeat
   (S2 naming: `test_ensure_resolved_resolves_once_and_is_idempotent`). M-budget:
   cascade + composition each exactly once, cached.
3. RULE-11: fake resolver raising `ConfigurationError` propagates from the entry
   point un-swallowed — EXCEPT graceful entries, which instead ASSERT the
   degraded outcome (AI-optional response shape + `logger.info` call).
4. Existing service unit tests: mechanical ctor migration to
   `StaticModelResolution`; outcomes unchanged.

**Regression contract (integration):**
5. Invalid body → **422** node for every migrated endpoint (SSE or REST).
6. SSE endpoints additionally: valid body + unconfigured provider → 400 with NO
   SSE headers sent (pre-header proof — assert `text/event-stream` absent on the
   error response).
7. Happy-path with `app.dependency_overrides` / `StaticModelResolution` —
   byte-identical streaming/JSON behavior (render-inert tripwire; goldens, if any
   exist in the domain, MUST NOT shift — a shift halts the slice).

**Verification protocol (commands, per slice):**
```
pytest tests/unit/api/<domain> tests/integration/<domain> -m "not schema_mutating"
just typecheck && just lint && python scripts/check_architecture.py
python scripts/check_python_size.py   # (or repo equivalent — see Makefile/justfile)
```
Session end (in addition): full `pytest -m "not schema_mutating"` (baseline
12,497 passed), schema_mutating suite, and a porcelain pre-flight before each
commit: exactly the slice's expected file set dirty — anything else halts.

---

## 6. Ledger check-off convention + whole-ledger gate (J1)

**Check-off convention (binding, mirrors entries 1–5):** in the SAME commit as
the slice, flip in `docs/architecture/decisions/ADR-086-lazy-model-resolution.md`:
`N. [ ] ...` → `N. [x] ... *(<slice-id> — landed YYYY-MM-DD: lazy wiring +
first-use resolve[, SSE pre-header][, deferred budget composition][, degradation
preserved])*` — annotation lists only what that slice actually did.

**J1 gate steps:**
1. **Ledger empty:**
   `rg -n "^\d+\. \[ \]" docs/architecture/decisions/ADR-086-lazy-model-resolution.md`
   → 0 matches (numbered-unchecked is unique to the ledger; Review-Trigger
   checkboxes are prose-indented and excluded by the anchor).
2. **Factory sweep:** `rg -n "= await resolver\.resolve|= await .*get_resolved_limits" apps/api/narrare -g '*.py'`
   → every remaining hit is service-layer or inside a `LazyModelResolution`
   closure; adjudicate + document the survivor list in the ADR Implementation
   Notes (append "Post-migration sweep YYYY-MM-DD: ...").
3. **Prevention check (Review Trigger #1):** extend `scripts/check_architecture.py`
   with a rule forbidding `await resolver.resolve(`/`await ...get_resolved_limits(`
   in factory bodies of `dependencies*.py`/`deps*.py`/factory router files,
   allowlisting the inside-a-`LazyModelResolution(...)` closure idiom; update its
   baseline; commit separately from any entry slice.
4. **ADR close-out:** status block gains "ledger entries 6–39 migrated
   (YYYY-MM-DD)"; tick Review-Trigger checkbox #1. New-AI-endpoint rule (#3)
   stays open as a standing review item.
5. Full gates re-run (§5 session-end set) + `git status` clean-tree confirmation.

---

## 7. Coordination with the uncommitted working tree

The GIVEN batch (30 dirty files) intersects this plan at: `chat/chat_service.py`,
`chat/_context.py` (I1) and `writing/router_sessions.py`, `ws_factory.py`,
`ws_context_assembler.py` (I2). **Hard precondition:** I1/I2 execute only after
those batches are committed/landed; executors re-read the then-current files and
locate targets semantically (line numbers in this plan will have drifted).
No other slice touches dirty files (verified: analysis/kb/planning/series/wiki/
generation/consistency factories+services are clean at `50645efa`).

---

## 8. Session estimate (8–10 slices/session)

| Session | Batches | Slices | Focus |
|---|---|---|---|
| 1 | A + B | 8 | Analysis SSE wave + warm-down |
| 2 | C + D | 9 | kb + series |
| 3 | E + F | 8 | Writing budget wave + band summary |
| 4 | G + H | 7 | Graceful degradation + consistency dual |
| 5 | I + J | 3 | Dirty-tree entries + whole-ledger gate (light; reserve for J1 adjudication) |

**Total: 35 slices (34 entries + 1 gate), 10 batches, 5 sessions** (4 heavy at
7–9 slices, 1 light). Effort mix 17 S / 17 M / 1 gate.

---

## 9. Risks / open items for executors

1. **L39 scope risk** — turn-service first-use may push past 3 files → split
   L39a/L39b is pre-authorized; do not compress.
2. **L25 background-task invariant** — lazy closure must capture the in-process
   task's session; first use must occur before session close. Test it explicitly.
3. **Planning ownership guard** (entries 20–24) — do not substitute the resolver's
   internal guard for the uid-scoped factory guard without verifying scoping
   equivalence; default is move-into-service (§3 note).
4. **Suite growth** — cap integration-node additions at ~2 per slice; prefer
   parametrizing the 422/400-pre-header pair.
5. **File-size ratchets** — `ensure_resolved` additions may cross RULE-04
   thresholds in already-large services (`writing` services especially); split
   per module convention and record as a deviation with justification.
6. **Chat anonymous path** — I1 must re-verify auth posture at execution time;
   if an optional-auth branch exists by then, only the authenticated plane
   migrates and the branch keeps its current semantics (flag in report).

## Plan Self-Review (executed)

- Coverage: all 34 ledger entries enumerated with module/factory/service/effort/
  notes; every entry mapped to exactly one slice; gate slice included.
- Alternatives: graceful-adapter and ad-hoc-coroutine alternatives evaluated and
  rejected (§1); band-summary and WS residuals documented rather than silently
  scoped out.
- Rules checked: RULE-03/04 (reuse landed primitives, no new abstractions),
  RULE-06 (pre-header call is delegation), RULE-11 (loud vs sanctioned graceful
  set), RULE-18/18b (cascade sources unchanged), RULE-19 (SessionDep factories
  untouched), RULE-20 (SSE compliance preserved).
- Render-inertness enforced as a tripwire (goldens must NOT shift).
- Session math: 35 slices ÷ 8–10/session → 5 sessions.
