# PLAN-001 Wave-3 Follow-ups (d) + (e) + (f) Report — zero-write static guard, scene_repo seam removal, story-suggest hoist

**Status:** OK
**Branch:** `chore/plan001-followups-wave3` (HEAD `1a35693e`)
**Date:** 2026-10-11
**Cap:** treated as three sub-slices, one per item (declared):
(d) 0 production files / +95 test LOC; (e) 3 production files / +14 gross / net +1 production LOC
(code change is pure deletion — the +1 is docstring clarification), 5 test files net −41;
(f) 2 production files / +42 gross / net +18 production LOC, 2 test files +53/−3.
Each item is one logical unit with its own red→green cycle; production-file counts are
within ≤3 per sub-slice (tests excluded, house convention).
**Git:** nothing staged or committed (task constraint honored; verified `git status`).

## (d) Zero-write static guard — mechanical source scan

T8 documented that SceneAIService's zero-DB-write property was enforced only
behaviorally (fake call-recording + HTTP pin in `test_scene_ai_guards.py`).
A behavioral guard only bites when the write path is actually exercised; a
one-line write slipped into an untested branch would land unnoticed.

**Fix:** new sibling module `tests/unit/api/planning/test_scene_ai_zero_write_static.py`
— a plain substring scan over the complete scene-AI source surface
(`scene_ai_service.py`, `_scene_ai_support.py`, `_scene_ai_factory.py`) that
fails naming **file : line : pattern** when any deny-list write call appears.

Deny-list (conservative — every entry is an unambiguous DB write on a
repo/session object): `.bulk_replace(` (the aggregate-PUT write the design
routes around), `.add(` / `.add_all(` (session staging), `.merge(`,
`.delete(`, `.flush(` (pushes staged writes), `.commit(` (transaction
boundary), `session.execute(` (raw SQL; also matches `self._session.execute(`
— services must never touch a session, only repositories do).

Allow-list rationale (documented in the module docstring): read-shaped calls
(`.get(`, `.get_by_id(`, `.list_by_chapter(`, `.list_by_novel(`) and the
composer/registry/agent seams (`.resolve(`, `.prepare(`, `.build(`, `.run(`)
are deliberately NOT denied — a guard that false-positives on the legitimate
path gets disabled, and a guard that never runs guards nothing. Comments and
docstrings count too (plain substring scan — mechanical, immune to
AST-escape tricks).

**Mutation proof (the guard bites):**
- RED: temporarily injected `await self._scene_repo.bulk_replace(chapter_id, [])`
  into `SceneAIService.draft` →
  `test_scene_ai_sources_contain_no_repo_or_session_write_calls` FAILED with
  `scene_ai_service.py:101: '.bulk_replace(' → await self._scene_repo.bulk_replace(...)`
  (file + line + pattern in the assertion message).
- GREEN: probe removed → `1 passed`. Probe fully reverted; production tree
  carries no trace (`grep MUTATION-PROBE` clean).

Companion behavioral proof (`TestZeroWrites`) stays in place — now two-layered
enforcement, and after (e) the scene surface can't even attempt a write.

## (e) scene_repo seam removal — root-cause resolution of an unused injection

`SceneAIService`'s injected `scene_repo` was dead at runtime (T8 finding):
`refine` receives the scene in the request, `draft` needs no scene read, and
zero-write is the design — proposals are applied by the client via the
aggregate PUT. An injected-but-unused repository is not harmless: it invites
future writes through a surface whose contract is "never writes", and it
forces every test to construct and wire a fake that proves nothing.

**Removed across the whole seam (atomic — a partial removal leaves the tree
broken at every construction site):**
1. `scene_ai_service.py`: ctor parameter + `self._scene_repo` assignment +
   `ScenePlanRepositoryProtocol` TYPE_CHECKING import; module docstring now
   states the no-scene-repo design and the two-layer enforcement.
2. `contracts.py`: `SceneAIServiceProtocol` docstring updated (the Protocol
   never declared the ctor or a `scene_repo` member — its only members are
   `draft`/`refine` — so the contract change is the documented injection
   surface, not a signature). `ScenePlanRepositoryProtocol` itself stays:
   `ScenePlanService` and story-suggest use it fully.
3. `_scene_ai_factory.py`: `ScenePlanRepository(session)` wiring + import
   removed. `ScenePlanService`'s scene repo (`scene_service.py`:
   `list_by_chapter` / `bulk_replace` aggregate-PUT save path) untouched;
   likewise `StoryboardService`'s (`service.py`: `list_by_novel`) — both
   verified fully used.
4. Tests: `_scene_ai_test_helpers.py` (`_make_service`, `_AiWorld`),
   `test_scene_ai_service.py` (7 tests), `test_scene_ai_guards.py`
   (all fixtures/params; `_READ_METHODS` back to novel/chapter only),
   `test_scene_ai_prompt_path_compliance.py`, `test_scene_ai_factory_wiring.py`
   (no longer patches `ScenePlanRepository`).
5. `test_scene_repo_is_never_written_even_on_graceful_path` DELETED — with no
   scene repo injected, "the scene repo is never written" is trivially true;
   the meaningful guarantees are the novel/chapter behavioral zero-write test
   and the (d) source scan. Documented here as intentional.

**DECLARED DEVIATION (coordinator-sanctioned, per task):** the plan's T8
interface block mandates `scene_repo` as the first ctor parameter; reality is
that it was dead. Removed per root-cause-first instead of plan-literal.

## (f) Story-suggest hoist — scene fetch out of the outline-existence gate

T15-documented bug: `_story_suggest_support.py` fetched scenes INSIDE the
`outline is not None` gate, so a chapter with scene plans but no outline row
rendered an empty `chapter_outline` slot (pinned by
`test_chapter_outline_empty_when_outline_missing`). Root cause: the gate
conflated two independent facts — scene plans persist independently of the
outline row (ADR-096: outlines carry stage + notes only), so outline
existence must not gate the scene fetch.

**Fix:**
1. `_story_suggest_support.py`: the scene fetch now runs whenever a chapter
   is targeted; the outline is fetched independently (`None` when the repo
   or the row is missing) and both flow into the renderer. Stage/notes
   semantics unchanged: they still require the outline row.
2. `_outline_render.py`: `render_chapter_outline(outline: ChapterOutline | None, ...)`
   — `outline=None` renders the scene blocks alone (one render path, no
   drift); empty result still returns `""` so the caller degrades cleanly.
3. Pinning test FLIPPED: `test_chapter_outline_renders_scenes_when_outline_missing`
   (outline-missing + scenes → rendered scene blocks, no Stage/Notes) +
   `test_chapter_outline_empty_when_outline_missing_and_no_scenes`
   (outline-missing + no scenes → empty, as before). Renderer-level:
   `TestRenderChapterOutlineWithoutOutlineRow` (2 tests).

**T15 contract note update:** the `chapter_outline` slot is now
"numbered scene blocks whenever scene plans exist (with or without an
outline row) + stage/notes when the outline row exists" — previously
"stage + scenes + notes only when the outline row exists". The RULE-11
empty cases are unchanged: no `chapter_id`, or nothing at all to render.
Semantic side effect (intended): scenes also render when `outline_repo`
is `None` but a scene repo carries scenes; the existing
`test_chapter_outline_empty_when_no_outline_repo` test stays green (it wires
neither repo, so nothing renders).

## TDD evidence

- **(d)** mutation cycle: RED (probe injected) → fail naming file+line+pattern;
  GREEN (probe removed) → `1 passed`. Both runs recorded above.
- **(e)** RED first: all test fakes/fixtures rewired to the seam-free ctor
  → `20 failed / 7 passed`, representative failure:
  `TypeError: SceneAIService.__init__() missing 1 required positional
  argument: 'model_registry'` (production ctor still demanded the removed
  slot — failing for the right reason). GREEN after production removal:
  `tests/unit/api/planning/` → `216 passed`.
- **(f)** RED first: `3 failed / 10 passed` (renderer None-outline ×2,
  flipped pinning test ×1). One test-expectation correction during green:
  the new renderer test initially asserted exact equality but the Core
  renderer legitimately emits the `Purpose:` line inside the scene block —
  assertion relaxed to content assertions (`Scene 1: …` present,
  `Stage:`/`Notes:` absent), no production change involved.
  GREEN: `tests/unit/api/writing/` → `822 passed`.

## Review fix round (verdict APPROVED, 1 MINOR + 2 NITs — all applied)

1. **MINOR (report)** — the item-(e) section misattributed `ScenePlanService`
   to `service.py`; reality: `service.py` = `StoryboardService`
   (`scene_repo` → `list_by_novel`), `ScenePlanService` lives in
   `scene_service.py` (`list_by_chapter` / `bulk_replace`). Corrected above;
   both repos verified intact, so the substance held — documentation fix only.
2. **NIT (scan set)** — the 3-file scan set is now GLOB-derived
   (`scene_ai*.py` + `_scene_ai*.py` in `apps/api/narrare/planning/`) instead
   of hardcoded, so a future 4th scene-AI module is auto-covered. A new
   `test_scan_set_is_non_empty_and_covers_known_modules` pins the set as
   non-empty and containing the three known modules (the glob can neither
   match air nor silently drop a module); the vanished-file trip assertion
   stays in the scan loop.
3. **NIT (deny-list)** — added repo-verb writes `.create(` / `.update(` /
   `.save(` for the still-injected novel/chapter repos. False-positive check:
   zero occurrences of all three patterns in the three scanned modules
   (grep-verified); the service touches those repos ONLY via
   `get_by_id`-class reads (the ownership guards) — allow/deny boundary now
   documented in the module docstring.

**Re-proof the guard bites (both probes, recorded):**
- Deny-list probe: injected `await self._novel_repo.create(novel)` into
  `SceneAIService.draft` → scan test FAILED naming
  `scene_ai_service.py:101: '.create(' → await self._novel_repo.create(novel)`
  → probe removed → `2 passed`.
- Glob probe: temporarily created
  `apps/api/narrare/planning/scene_ai_extra.py` (containing a
  `.bulk_replace(` comment line) → scan test FAILED naming
  `scene_ai_extra.py:2: '.bulk_replace('` (the future module was
  auto-covered; the scan-set containment test stayed green) → probe module
  removed → `2 passed`. Exactly the 3 known scene-AI modules remain.

## Gates

- `uv run --all-packages pytest tests/unit/planning/ tests/unit/api/planning/ tests/unit/api/writing/ tests/integration/planning/ -q` → **1192 passed** (224s)
- `just check-architecture` → **exit 0** (3305 files, 13 approved exceptions, no-growth gates OK, RULE-10 test-existence 0 missing)
- `just typecheck-file <13 changed files>` → **0 errors, 0 warnings** (prod strict + tests basic)
- `uv run pyright` (full project, strict) → **0 errors** (seam removal touches typed interfaces — full run mandatory)
- `just lint-file <13 changed files>` → ruff check + format: **all passed**

## Self-review

- Root cause + alternatives documented per item; no workarounds.
- Public methods typed; no `Any` introduced; router untouched (factory
  signature unchanged — `router_scenes.py` needs no edit).
- DI consistent: the removed dependency is gone everywhere it was wired,
  nothing instantiated ad hoc.
- Tests: happy/error/edge preserved; the only deletion is the test made
  meaningless by the seam removal (documented); no bare except; structlog
  untouched.
- English throughout; no commits, nothing staged.
