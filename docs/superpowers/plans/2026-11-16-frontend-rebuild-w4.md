# Frontend Rebuild — W4 (Schreib-Workspace) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The scene-centric writing workspace at 1:1 from the wave's Stitch round — prose scenes as the writing unit, app-wide chrome, real continuation with prompt parameter and ghost text, real goals, the full book-settings family, zen focus — shipped as five sequential PRs.

**Architecture:** Writing owns prose scenes (`Scene` under `Chapter`, model A); `ScenePlan` stays planning's, FK deferred to the planning wave. Continuation becomes scene-based with an optional bounded prompt parameter. Chrome (rail + topbar) is shell-owned in `web/` and frames shelf + workspace. The Stitch round (PR1) produces the one harmonized authority the ports follow.

**Tech Stack:** unchanged — FastAPI + SQLAlchemy async + Alembic, Vite + React + TanStack Router + TipTap + Tailwind v4 tokens, vitest, pytest + Playwright; Stitch MCP for the round.

**Spec:** `docs/superpowers/specs/2026-11-16-frontend-rebuild-w4-design.md`. Drafts: `docs/design/stitch/screens/writing/` (round output supersedes), `screens/shell/` chrome round output. Gap doc: `docs/design/stitch/gaps/2026-11-16-w4.md`.

## Global Constraints

- Models rev. 6, named per dispatch: implementer/UI `qwencloud/qwen4-max-preview`, reviewer `zai-coding-plan/glm-5.3`; one implementer + one reviewer per task, whole-branch review per PR.
- No deferred findings, any severity; flakes get root-cause fixes.
- Rule 2 (green E2E per capability), rule 4 (user_id on user-owned rows), rule 5 (en/de/fr catalogs, sorted, same keys, du-tone).
- Conventional commits: visible `feat(writing)`/`feat(web)`/`feat(settings)` with real `User-visible:` lines; round/archive/gap-doc work `chore(docs)`; backend tooling hidden types; `Assisted-by: OpenCode (<model>)` trailer everywhere.
- Five PRs, sequential to main, push after every green task group; branch base: `feat/shelf-rebuild` until #860 merges, then main.
- E2E: two xdist workers max, per-suite DB, isolated ports, de-DE contexts repeat locale; `pnpm`/vitest checks need `CI=true` in the shared checkout.
- Audit obligation: round output is re-audited (logical errors, unintended features) before porting; owner decides.
- Stitch alone designs — no invented UI; honest neutrals (`—`, disabled) + gap rows otherwise.

## Review Focus

1. **Reorder contracts both levels** — chapter and scene order PUTs take the whole set, refuse a mismatch with 409 + stored ids, positions unique per parent (deferrable). Pinned by service tests in Tasks 5 and 13.
2. **Word-count chain** — scene Σ → chapter Σ → novel, no double counting after migration; duplicate/export/activity re-derive from scenes. Pinned by repository/service tests in Tasks 4 and 6.
3. **User scoping** — every new endpoint (scenes, scene order, series, settings fields) 404s foreign rows; scenes inherit ownership via chapter. Pinned per-endpoint tests, Tasks 5/7/8/19.
4. **Honest empty states** — empty book, empty chapter („Erste Szene starten"), goal unset, no drafts' mock numbers anywhere. Pinned by vitest + E2E in Tasks 11/13/14.
5. **Stream honesty** — continuation accept/dismiss/prompt/refusal frames and the leave guard never lose or fake edits. Pinned by fake-provider E2E in Task 17.

---

### Task 1: Stitch round — generate the harmonized authority (PR: `chore/w4-stitch-round`)

**Files:** Stitch project `15314899202287259920` via MCP; nothing in-repo yet.
- [ ] Generate per design §7 with the W1 recipe (`generate_screen_from_text`, designSystem assets light `485a76ff…` / dark `ca5cbb89…`, GEMINI_3_8_FLASH, DESKTOP): (1) harmonized scene-centric workspace, light + dark; (2) state sheet (loading, error, empty book, empty chapter, long titles, many chapters/scenes, continuation streaming/error, autosave failed, leave guard); (3) chrome (rail + topbar) framing shelf AND workspace, light + dark, states (switcher open, sync states, user menu); (4) book-settings surface (per-novel fields incl. series create/link/volume, user author_name + daily goal); (5) zen v2 (timer/focus real, audio disabled, sepia as open variant).
- [ ] Verify each via `get_screen` → `download_file` HTML check (entities distort text); re-generate on gaps.
- [ ] **Owner gate:** owner reviews in Stitch; on OK owner exports the zip to `docs/design/stitch_narrare.zip`.

### Task 2: Unpack the round, open the wave's books

**Files:** `docs/design/stitch/screens/{writing,shell,library}/` + README rows + superseded marks; `docs/design/stitch/gaps/2026-11-16-w4.md`; GitHub index issue + children.
- [ ] Unpack per README naming; mark superseded (base `workspace.html`, `integrated-suite` chrome parts); delete the zip.
- [ ] Re-audit the round output against design §8's table (audit obligation); surprises go to the owner before any port task starts.
- [ ] Gap doc skeleton (English, feature + draft gaps, trigger + follow-up issue per row, design §8 rows); open the `follow-up-index` issue + one child per row (`area: writing`/`area: web`/`area: settings`, kinds where they apply); add the wave row to `docs/superpowers/follow-ups.md`.
- [ ] PR 1 (`chore(w4)`… hidden type; body links spec/plan), merge after review green.

### Task 3: Kernel contracts — Scene, Chapter.target_words, User fields (PR: `feat/w4-scene-model`)

**Files:** `app/kernel/contracts/novel.py` (+`Scene` beside `Chapter`), `app/kernel/contracts/user.py` (+`author_name`, `daily_goal_words`); contract tests.
**Interfaces (produces):** `Scene(id, chapter_id FK CASCADE, position int, title str=" ", body Text="", setting str|None, story_time str|None, created_at, updated_at)` with `UniqueConstraint("chapter_id","position", deferrable=True, initially="DEFERRED")`; `Chapter.target_words: int|None`; `User.author_name: str|None`, `User.daily_goal_words: int|None`.
- [ ] Failing contract tests (unique positions deferrable; cascade on chapter delete), implement, `just test-file`, commit `chore(writing)` (internal model, hidden type).

### Task 4: Migration — wrap bodies, drop chapters.body, new columns

**Files:** new Alembic revision (`just db-revision`); migration test.
- [ ] For every chapter: insert Scene(position=1, title="", body=chapter.body, setting/story_time NULL); then drop `chapters.body`; add `chapters.target_words`, `users.author_name`, `users.daily_goal_words`.
- [ ] Migration test: chapters with bodies end as one scene each with equal prose; word counts re-derive; rollback clean. Commit hidden type.

### Task 5: Writing backend — scene CRUD, order, reads (TDD)

**Files:** `app/capabilities/writing/{schemas,repository,service,router}.py` + tests.
**Interfaces (produces):** `SceneCreate(title="", body="", setting=None, story_time=None)`, `SceneUpdate` (present-only semantics like `ChapterUpdate`), `SceneOrderUpdate(ids: list[UUID])` → PUT `/api/writing/chapters/{id}/scene-order` (whole set, 409 mismatch), `SceneRead(id, chapter_id, position, title, body, setting, story_time, word_count, updated_at)`; scenes under `/api/writing/chapters/{chapter_id}/scenes` + `/scenes/{scene_id}` (POST/PUT/DELETE); `ChapterRead` gains `word_count`, `scene_count`; `NovelRead.word_count` now Σ scenes (repository expression swap). Scene delete always allowed (D16 — empty chapters are real).
- [ ] Tests: CRUD + scoping (404 foreign), order contract (409 names stored ids), derived counts, empty chapter reads honestly, localization placeholder for empty title. Commit `feat(writing)` with `User-visible:` (scenes as the writing unit).

### Task 6: Backend adaptation — activity, duplicate, export, import, setup

**Files:** `app/capabilities/writing/service.py`, interchange engine (`import_archive` path), `app/capabilities/setup/service.py` + tests.
- [ ] `DailyWords` hooks move to scene create/update/delete (old-body diff before update; deletes negative; same-day upserts); chapter delete accounts its scenes' words (Σ-scene negative).
- [ ] Duplicate copies chapters + scenes (positions, titles, bodies, setting/story_time) in one transaction; archive stays uncopied.
- [ ] Export assembles scene prose per chapter in order (archive format stays chapter-shaped); `import_archive` wraps every landed chapter body into one scene (demos ride this).
- [ ] Tests: create→update→delete nets, duplicate equality, export/import round-trip chapter-shaped; both E2E suites' seeding adapts (chapter-body PUTs become scene writes). Commit hidden type where behavior-invisible, else `feat(writing)`.

### Task 7: Scene continuation endpoint (no prompt yet)

**Files:** `app/capabilities/writing/{service,router}.py`, `prompts.py` + tests.
**Interfaces (produces):** `POST /api/writing/scenes/{scene_id}/continue` (SSE, same frames/headers as today); chapter endpoint removed; prompt context = scene tail → chapter's earlier scenes (reverse) → earlier chapters' scenes (reverse), budget-sliced nearest-first, chapter titles as separators, novel facts as today.
- [ ] Fake-provider tests: stream, done/error frames, 404 foreign, budget refusal frames unchanged. Commit `feat(writing)`.

### Task 8: Settings + novel PATCH extensions

**Files:** `app/capabilities/settings/{schemas,service,router}.py`, `app/capabilities/writing/schemas.py` + tests.
**Interfaces (produces):** `SettingsUpdate` gains `author_name: str|None`, `daily_goal_words: int|None` (present-and-nullable pattern); `NovelUpdate` gains `target_words: int|None` + `author_typology`/`dramatic_form`/`ai_role`/`canon_strictness` validated against setup's vocabularies (shared constants, not copied literals).
- [ ] Tests: PATCH semantics (absent ≠ null), vocabulary refusal (422), scoping. Commit `feat(settings)`/`feat(writing)`.

### Task 9: Shelf banner reads the daily goal (gap row 25)

**Files:** `app/capabilities/writing/web/ShelfBanner.tsx` + `activity.ts` (aggregate carries goal progress) + vitest; shelf E2E adjust.
- [ ] „Heutiges Schreibziel"/remainder lines read `daily_goal_words` (activity endpoint extension); unset → honest neutral; hero-book pin copy ends. `Closes` the row-25 child from this commit. Commit `feat(writing)`.

### Task 10: Chrome — rail + topbar, app-wide (PR2 continues)

**Files:** `web/components/{IconRail,TopBar}.tsx` + tests; `web/routes/__root.tsx` wiring; shell i18n keys; shelf page wrapped.
- [ ] Port from the round's chrome draft (§7.3): book-switcher (real novels menu, navigates), sync dot from autosave state (PR2 interim: static „gespeichert" until Task 12 wires it live — honest, no invented states), theme toggle tri-state (real), user block (author_name → email fallback, no tier), breadcrumb, word chip (real Σ), language chip as the **real switcher** (D17 — extract the language contract: one owner for the chrome's switcher and the three pre-setup copies; `Closes` the row-12 child), ⌘K chip disabled + gap row.
- [ ] Frames shelf AND workspace routes; welcome/wizard stay standalone. vitest + axe both themes; both E2E suites pin the chrome. Commit `feat(web)`.

### Task 11: Read-only workspace — route, tree, prose

**Files:** `app/capabilities/writing/web/{WorkspacePage,routes}` (+`routes.tsx`), `ExplorerColumn.tsx`, `EditorColumn.tsx` (read-only), `workspace.ts` (queries), i18n catalogs (en/de/fr, du-tone) + tests.
- [ ] Route under writing's tree (e.g. `/novels/$id`); explorer column (identity card, daily ring real, tension arc label from storyboard API + placeholder curve + gap row, scene tree with words, shelf mini-card); editor column read-only (scene header incl. setting/story_time, EB Garamond prose, drop cap, running head `novel.author` — book alone when null); dock renders round geometry with neutrals (cover miniature real).
- [ ] Shelf hero „Weiterschreiben" door wires to the last-edited scene (updated_at), label names chapter + scene — `Closes` the row-3 child.
- [ ] Empty book / empty chapter states per the round sheet. vitest; writing E2E gains read legs; `just verify` both suites; PR 2 open (plain title), merge after review green.

### Task 12: Editor real — TipTap, autosave, leave guard (PR: `feat/w4-editor`)

**Files:** `EditorColumn.tsx` → editor components (`SceneEditor.tsx`, `useAutosave.ts`), `workspace.ts` mutations + tests.
- [ ] TipTap scene editor; autosave (debounce, flush on scene switch/unload), one status owner feeding topbar save state, card foot and the rail sync dot (Task 10's interim ends); leave guard on unsaved edits. `feat(writing)`.

### Task 13: CRUD + reorder UI, live counts, metadata

**Files:** `ExplorerColumn.tsx`, `workspace.ts`, i18n + tests.
- [ ] Chapter/scene create/rename/delete (last scene allowed → empty chapter state), drag reorder both levels (chapter order + scene order endpoints), live word counts, scene title/setting/story_time editing; new chapters start with zero scenes. `feat(writing)`.

### Task 14: Editing E2E + PR 3

**Files:** `app/capabilities/writing/e2e/test_workspace_e2e.py` (+conftest scenes seeding).
- [ ] E2E: write/edit/reorder/delete via real UI, autosave indicator, leave guard, empty-chapter flow, axe both themes. `just verify`; PR 3, merge after review green.

### Task 15: Prompt parameter (PR: `feat/w4-continuation`)

**Files:** `app/capabilities/writing/{schemas,service,prompts}.py` + tests.
**Interfaces (produces):** `SceneContinue(prompt: str | None)` body on the continue endpoint; prompt bounded (chat `question` 1–2000 precedent), rendered into the continuation prompt under the bounded-prompts system; refusal frames unchanged.
- [ ] Fake-provider tests: prompt flows into the call, bound refusal 422/frame, no prompt = today's behavior. Commit `feat(writing)`.

### Task 16: Ghost text + prompt bar

**Files:** `SceneEditor.tsx` (ghost layer), `PromptBar.tsx`, `workspace.ts` + tests.
- [ ] Continuation streams into the ghost preview at the scene tail (italic, area-writing/70, `[Tab]` keycap pill); Tab accepts → insert + save; Esc dismisses (ghost owns Esc first); typing dismisses. Prompt bar: Stil trigger neutral `—` + gap row; input + quick pills send real prompts; busy/error honest. `feat(writing)`.

### Task 17: Continuation E2E + PR 4

- [ ] Fake-provider E2E: stream → ghost → accept inserts; dismiss; prompt round-trip; refusal frames; leave guard during stream. `just verify`; PR 4, merge after review green.

### Task 18: Zen mode (PR: `feat/w4-zen-settings`)

**Files:** `ZenMode.tsx`, `workspace.ts`, i18n + tests.
- [ ] Per round zen draft: centered scene prose, Absatz-/Satz-/Normal dimming (frontend-real), pomodoro timer (session-only), today/session word counters (real), scene overline, soundscape controls disabled + gap row, sepia **cut** (D18 — no sepia control ships), **F9 toggles zen on/off, Esc exits** (D19), ghost reachable. `feat(writing)`.

### Task 19: Book settings + series + goals + author profile

**Files:** `BookSettings.tsx` (+dialog per round draft), `web/` settings extensions, `app/capabilities/writing/router.py` (+`POST /api/writing/series`) + tests.
**Interfaces (produces):** `POST /api/writing/series` `{title}` → `SeriesRead` (user-owned); surface edits per-novel status/target/author/genre/blurb/language + four wizard fields + series create/link/volume; user author_name + daily goal; chapter target setter per round affordance.
- [ ] Backend TDD (series create + scoping), surface port, dialog-note truth („änderbar, sobald der Workspace da ist"); `Closes` rows 7/8/9/10/19 children. `feat(writing)`.

### Task 20: Dock placeholders final + gap doc completion

**Files:** `InspectorDock.tsx`, gap doc, follow-up issues.
- [ ] Dock per round geometry: findings/entity/atmosphere/chat/⌘J/layout neutral or disabled, each in-code interim naming its child issue; cover miniature real. Gap doc rows complete; every interim references its child. `feat(writing)` + `chore(docs)`.

### Task 21: Fidelity gate + wave close + PR 5

- [ ] E2E screenshots (workspace + zen, light/dark) beside the round drafts in the PR; re-shot master frames `assets/screenshots/`; axe both themes; zen/settings E2E legs; `just verify`; PR 5, merge after whole-branch review; wave ledger rows in `docs/superpowers/follow-ups.md`; spec amendment committed with the design (build session moves spec+plan into `docs/superpowers/`).
