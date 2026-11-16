# Frontend Rebuild — W4: the writing workspace (design)

> **Status:** Draft for owner approval (plan session; the build session moves this
> into `docs/superpowers/specs/` per AGENTS.md — move, never copy).
> **Type:** Wave design under the frontend rebuild program
> (`docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md`, repo
> `narrare-w3`). Amends the v2 architecture spec
> (`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`)
> where noted (§5 data model).
> **Design authority:** the Stitch drafts under `docs/design/stitch/` — for W4 the
> five scene-centric workspace variants, reconciled into ONE authoritative draft by
> the wave's Stitch round (§7). `DESIGN.md` + `dark-tokens.md` own values.
> **Historical:** the Literary Modernism W3 spec (2026-11-12) and its PR #808 are
> dead (rebuild decision 2026-11-13); its surface notes informed the audit only.
> **Origin:** owner decisions 2026-11-16 (card round + data-model choice A).

---

## 1. Intent and why

The workspace is where the user actually writes. W4 ports the **scene-centric**
composition the five variant drafts show (owner chose it over the chapter-centric
base draft), backed by a **new prose-scene data model**: prose lives in scenes,
chapters group them. The wave ships the chrome the drafts presuppose, real AI
continuation with a prompt parameter, ghost text, real goals, the book-settings
family the shelf's gap doc already assigned here, and zen focus — everything real
per the program, honest placeholders only where data legitimately does not exist
yet (dock contents → knowledge wave; audio → later wave; pagination/versioning/
history → gap rows with their later-wave triggers).

W4 is the program's largest wave: the scene model ripples through the just-shipped
W3 backend (activity diffs, duplicate, export, word counts, demos, both E2E
suites). The owner chose five smaller PRs over one wave PR (§9).

## 2. Goals, non-goals, anti-goals

**Goals**

- G1 — One harmonized scene-centric workspace draft (light + dark + states) from
  the Stitch round; the port matches it 1:1 in geometry and tokens.
- G2 — Prose scenes backend-real: kernel contract + migration, chapter/scene CRUD
  and reorder (both levels), autosave, derived word counts, activity tracking on
  scene writes, duplicate/export/setup-demo adaptation.
- G3 — Chrome (icon rail + topbar) from a dedicated round draft, **app-wide**
  (owner, 2026-11-16): it frames every post-setup surface — the shelf AND the
  workspace; welcome/wizard stay standalone (their drafts are chrome-less guided
  flows). Book-switcher (real novels menu), sync dot derived from autosave
  state, theme toggle (real tri-state), user block (`author_name`, fallback
  email label, no tier), word chip, language chip as the **real switcher** (D17;
  the language contract is extracted in W4 — row 12 closes), ⌘K chip
  honest-disabled (palette is a later shell wave). Shelf gap row 20 (shelf chrome deferred to
  the shell wave) is superseded: W4 delivers it.
- G4 — Continuation is scene-based with an **optional prompt parameter** (real,
  bounded by the prompts system). Ghost text is frontend logic riding the
  continuation stream: italic preview at the scene tail, `[Tab]` accepts, Esc
  dismisses (ghost owns Esc first). Prompt bar: input + quick pills send real
  prompts; Stil trigger neutral `—` + gap (no style presets exist).
- G5 — Zen mode: pomodoro timer and Absatz-/Satz-/Normal focus dimming are
  frontend-real; soundscape controls render disabled + gap (audio wave); sepia
  is **cut** (D18 — theme stays tri-state); scene overline (setting/story_time)
  real when present; word counter real (today + session).
- G6 — Book-settings family complete and real: per-novel status, target_words,
  author, genre/blurb/language, the four wizard settings (typology, dramatic form,
  AI role, canon strictness), series link/volume; user-level `author_name` and
  `daily_goal_words`; per-chapter target. Surface from a round draft.
- G7 — Inspector dock as drafted geometry with honest placeholders; the knowledge
  wave fills it. Cover miniature real (writing's own data).
- G8 — Gates green per PR; the writing E2E suite grows with each PR (setup suite
  adapts in PR2); axe AA both themes; fidelity screenshots at PR5.

**Non-goals** (later waves / separate work)

- Real dock contents (findings, entity spotlight, lore graph, chat composer,
  context chips), entity tags in prose, causality pills — knowledge/chat waves.
  W4 renders their drafted geometry neutral/disabled (my call, extends D4).
- Planning wave surfaces: scene dramaturgy editing (purpose/conflict/beats),
  storyboard UI, timeline UI. `ScenePlan` stays untouched in W4; the planning
  wave adds the nullable FK to the prose scene (model A, §5).
- Soundscape audio (assets + playback) — own later wave.
- Import studio (DOCX/Scrivener/ePub) — own later wave (program).
- Pagination, manuscript versioning, revision history — gap rows; editing and
  production waves own the drafted surfaces (`revision-history`,
  `export-typesetting`).
- Chapter-level export formats (PDF/EPUB/DOCX) — production wave; W4's ribbon
  export renders disabled + gap (novel-level ZIP/path export exists and stays the
  shelf's action).
- Command palette (⌘K) — shell wave; the chip is honest-disabled.
- Mobile (Narrare Pocket).

**Anti-goals**

- Locally invented UI, states, copy or numbers standing in for missing drafts
  (Stitch is sole authority; gaps go to the round or the gap doc).
- The drafts' mock figures shipping as data (48.219 words, 500 W. goal, 82 %,
  FOLIO 12, „Akt I – Höhepunkt" as facts — real data or documented neutral).
- A mix of old neutral and new parchment tokens; new palette outside shell tokens.
- German-only copy (en/de/fr parity, du-tone).
- Deferred review findings, any severity (wave rule since W2).

## 3. Constraints

- The five standing rules (`docs/_shared/CONSTRAINTS.md`): especially rule 2
  (green E2E per capability), rule 4 (user_id on every user-owned row), rule 5
  (en/de/fr catalogs, sorted, same keys, plural categories, du-tone).
- v2 architecture spec stays structural authority: capability folders, `@shell/*`
  one-way imports, generated views, scoped repositories. §5 is the amendment.
- Governance budget (spec §8): no new mandatory gate/registry/check script.
- UI work by subagents, models rev. 6: implementer/UI `qwencloud/qwen4-max-preview`,
  reviewer `zai-coding-plan/glm-5.3`, named per dispatch; whole-branch review per PR.
- Conventional commits; user-visible ports `feat(writing)`/`feat(web)` with real
  `User-visible:` lines; backend/tooling hidden types; `Assisted-by` trailer.
- **Audit obligation (owner 2026-11-16):** every draft (archived AND round output)
  is checked for logical errors and features drawn as fact that were never
  intended. Findings are explained to the owner; the owner alone decides (rework
  via Stitch, placeholder, or cut). No agent-side UI decisions.
- **PR split (owner 2026-11-16):** large waves ship as several smaller PRs, each
  with its own gates/E2E, sequential to main; main carries the interim honestly;
  release-please PRs stay unmerged until program end.
- E2E stack: 9-GB machine, two xdist workers max, per-suite DB, isolated ports
  (parallel sessions share the checkout).
- W4 builds on the open shelf PR #860 (`feat/shelf-rebuild`); the build session
  starts after its merge or stacked on it.

## 4. Approaches considered (owner chose)

| Decision | Alternatives | Chosen |
|---|---|---|
| Composition | base chapter-centric draft / Stitch-reconciled / scene-centric variants | **Scene-centric, new data model** (D1). The round still reconciles the five variants into one authority — they differ among themselves. |
| Scene model | A: two tables, FK in planning wave / B: merge substrate into writing / C: markers in chapter body | **A** (D2). Spec-consistent (capabilities own their data; cross-FK like today's `ScenePlan.chapter_id`), no rework of the fresh storyboard substrate. C rejected: cannot carry drafted scene metadata. |
| Chrome | integrated-suite as authority / dedicated round draft / later wave | **W4, dedicated round draft** (D3). |
| Dock | findings+entity real / frame+neutral / whole dock later | **As drafted, placeholders, knowledge wave fills** (D4). |
| Prompt bar | real prompt parameter / disabled+gap / Stitch cut | **Real parameter in W4** (D5). |
| Zen | reduced via round / timer+focus real, audio later / full incl. audio / own wave | **Timer+focus real, audio later** (D6). |
| Book settings | full family+draft / status+target only / defer+fix dialog note | **Full family + Stitch draft** (D7). |
| Goals | neutral+gap / both real / daily only / cut | **Both fields real** (D8). |
| User block | email label / profile field+Stitch / cut name+tier | **`author_name` profile field + Stitch; tier cut** (D9). |
| Sync | autosave-derived / round relabel / cut | **Autosave-derived** (D10). |
| Invented details | program default / round cleanup / per-item | **Program default: neutral/stumm + gap rows** (D11). |
| Wave shape | one PR / 5 PRs / 3 PRs | **5 PRs**, re-cut for the scene model (D12, §9). |

## 5. Data model — amendment to the v2 architecture spec

**Writing owns prose scenes.** New kernel contract `Scene` (UserOwned via
chapter → novel, same pattern as `Chapter`):

- `id`, `chapter_id` (FK chapters, CASCADE), `position` (unique per chapter,
  deferrable — the chapters invariant pattern, #521), `title` (String 200,
  default `""`, localized placeholder when empty), `body` (Text, default `""`),
  `setting` (String, nullable — the drafted Ort overline), `story_time`
  (String, nullable — the drafted in-story datetime **label**, same pattern as
  `TimelineEvent.date_label`; not a timestamp), `created_at`, `updated_at`.
- `word_count` derived (whitespace-token util the chapters already use).

**Chapter** becomes a grouping shell: `body` column **dropped** (data migrates);
`target_words` (nullable int) added; `word_count` = Σ scene words (derived);
title/position/order unchanged. **Novel** `word_count` = Σ chapter words
(unchanged shape). `ChapterRead` gains derived `word_count` + `scene_count`;
`SceneRead` carries `word_count`.

**User** (kernel contract) gains `author_name` (String, nullable) and
`daily_goal_words` (int, nullable). Daily goal is **user-level/atelier scope**
(my call — consistent with the shelf banner's atelier aggregate); chapter target
is per-chapter.

**Planning `ScenePlan` untouched in W4.** The planning wave adds a nullable
`scene_id` FK → writing `Scene` and reconciles ordering (model A's deferred link).
No dual-write, no sync logic in W4.

**Migration (one revision):**

1. Create `scenes`; wrap each existing chapter body into ONE scene
   (position 1, title `""`, setting/story_time NULL). Demos/archive content
   unchanged — setup import wraps chapter bodies into scenes the same way
   (setup service adaptation rides PR2).
2. Drop `chapters.body`; add `chapters.target_words`, `users.author_name`,
   `users.daily_goal_words`.
3. Word-count derivation chain updated (scene → chapter → novel); shelf figures
   keep their shape.

**Backend adaptation (all PR2 unless noted):**

- Activity: `DailyWords` hooks move from chapter writes to **scene**
  create/update/delete diffs (old body before update; deletes negative; same-day
  upserts accumulate). Aggregate endpoint unchanged (atelier-level).
- Duplicate: copies chapters **and scenes** (positions, titles, bodies,
  setting/story_time) in one transaction; archive not copied (W3 rule stays).
- Export: assembles scenes per chapter in position order (markdown manuscript);
  `ExportDone` shape unchanged.
- Continuation: **scene-based** endpoint `POST /api/writing/scenes/{id}/continue`
  replaces the chapter endpoint (no UI consumes the old one post-rebuild).
  Context = scene tail + preceding scenes + chapter + novel facts, budgeted by the
  resolved provider; the assembly is book-level reading order, nearest first:
  the active scene's tail, then the chapter's earlier scenes (reverse), then
  earlier chapters' scenes (reverse), chapter titles as separators, novel facts
  as today — the chapter predecessors logic refined, not replaced. **Optional
  prompt parameter** (PR4) bounded by the bounded-prompts system (bounds follow
  the chat `question` precedent); refusal maps to the coded error frames the
  chapter endpoint already uses.
- Series: new minimal `POST /api/writing/series` (title, user-owned); linking
  and volume ride the existing `NovelUpdate` pair (must name an owned series).
  D7's "full family" needs the create — without it the surface's main action 500s.
- Reorder: chapter-order PUT stays; scene-order PUT per chapter added (same
  whole-set contract: stored ids in position order, 409 on mismatch).
- Setup/interchange: the blank path creates novels with **zero chapters** (the
  empty-book state is real — the round brief's state draft); `import_archive` —
  the demo path and the later import wave's engine — wraps every landed chapter
  body into one scene. The archive format stays **chapter-shaped**: exports
  assemble scene prose per chapter in order (scene boundaries are workspace
  structure, not a manuscript export fact); imports reconstruct one scene per
  chapter.
- Book settings PATCH: `NovelUpdate` gains `target_words` and the four wizard
  fields (validated at the service boundary like `status`, against setup's
  vocabularies); `author_name` / `daily_goal_words` ride the existing settings
  PATCH (`SettingsUpdate`'s present-and-nullable pattern extended — the
  settings capability owns the user row).
- Shelf hero door (gap row 3): resumes the **last-edited scene** (updated_at);
  label names chapter + scene honestly.

## 6. Surface map (geometry from the harmonized round draft)

The five variants are the composition reference until the round lands one
authority. Elements below are the audit-verified inventory; the round owns final
geometry, states and copy.

### 6.1 Chrome (rail + topbar)

- Icon rail: brand head; book-switcher (active novel cover chip + name,
  `unfold_more` menu of real novels, navigates); nav (Library/Editor/Knowledge/
  Timeline/Settings — later-wave targets honest-disabled or route-stubbed per
  round); sync dot + label from autosave state (gespeichert/ausstehend/
  fehlgeschlagen — never „Sync Online"); theme toggle (system/light/dark, real);
  user block (author_name or email label, avatar chip, **no tier**).
- Topbar: breadcrumb `Manuscripts / <book>`, save state (one `status` owner with
  the editor foot), book word chip (real Σ), language chip as the **real
  switcher** (D17 — one extracted language contract: the chrome's switcher and
  the three pre-setup copies share it), ⌘K
  search chip disabled + gap (palette wave).

### 6.2 Explorer column (left)

- Novel identity card (title, genre, cover chip — real).
- Daily target ring/card: atelier today words (DailyWords) vs user daily goal —
  real; goal absent → honest neutral + setter affordance per round.
- Tension arc: stage label derivable from the storyboard API (real); the curve
  itself placeholder + gap (no tension data).
- Scene tree: chapters → scenes, drag reorder both levels, active scene marker,
  per-scene/per-chapter word counts (tabular), status neutral + gap (no
  chapter/scene status field); new-chapter / new-scene buttons (real CRUD).
- Shelf mini-card (cover at small size, real).

### 6.3 Editor column (center)

- Ribbon: breadcrumb + scene-code badge (derived, catalog prefix), chapter-target
  pill (real when target set, neutral `—` otherwise; setter per round), focus
  toggle (F9 ↔ zen relationship per round), history disabled + gap, export
  disabled + gap.
- Scene header: chapter eyebrow + written-out scene ordinal (locale number-words
  util en/de/fr, bound + digit fallback), title (EB Garamond), setting/story_time
  overline (real when present), sepia rule.
- Prose: EB Garamond editorial, drop cap on first paragraph, selection tokens,
  autosave (rebuilt frontend logic: debounce, flush on scene switch, leave
  guard), running head `book — author` (novel.author, book alone when null),
  foot autosave line + word count (one status owner with topbar).
- Ghost text: italic area-writing/70 preview at scene tail, `[Tab]` keycap pill,
  accept inserts + saves, Esc dismisses; streaming/error states per round.
- Floating prompt bar: Stil trigger neutral `—` + gap; inline input real;
  „Weiterschreiben" primary (continuation, no prompt); quick pills real prompts
  (send via the prompt parameter); disabled/busy/error states honest.
- FOLIO / „Seite x von y": omitted (no pagination; gap row).

### 6.4 Inspector dock (right)

As drafted by the round (the variants' inspector: tabs/cards). W4 renders the
geometry with honest placeholders: finding card neutral (knowledge wave; the
findings API exists but D4 defers content), entity spotlight neutral, atmosphere
grid neutral, chat composer disabled + gap, ⌘J disabled + gap, layout-tune
disabled + gap. **Cover miniature real** (cover system + target + word count +
progress — writing's own data).

### 6.5 Zen mode

Centered scene prose; Absatz-/Satz-/Normal dimming presets (frontend-real);
pomodoro timer (frontend-real: start/pause/reset per round); word counter (today
real via DailyWords + session delta); scene overline real; soundscape controls
disabled + gap (audio wave); sepia **cut** (D18); **F9 toggles zen on/off, Esc
exits** (D19); ghost text reachable.

### 6.6 Book-settings surface (round draft)

Per-novel: title, author, genre, blurb, language, status (draft|revision|final),
target_words (arbitrary positive int), typology/dramatic form/AI role/canon
strictness (the wizard's vocabularies), series link + volume (create series,
link, set volume). User-level: author_name, daily_goal_words. All PATCH real;
the dialog's inheritance note („änderbar, sobald der Workspace da ist") becomes
true. Grouping/placement is the round's design, owner checkpoints.

## 7. Stitch round brief (PR1)

**Inputs:** five variant drafts + base `workspace` + `zen-focus` +
`integrated-suite` (chrome reference) + `DESIGN.md` + `dark-tokens.md` + the
backend facts (§5: what is real, what is gap) + the audit list (§8).

**Produces (one harmonized authority each, light + dark):**

1. Scene-centric workspace (reconciles the five variants; knowledge/chat
   elements rendered as honest placeholder geometry).
2. State drafts: loading, error, empty book, no scenes, **empty chapter** (owner
   2026-11-16: deleting the last scene is allowed and leaves the chapter — tree
   entry without scenes + editor empty state „Erste Szene starten"), long
   titles, many chapters/scenes, continuation streaming + error, autosave
   failed, leave guard.
3. Chrome draft (app-wide, owner 2026-11-16): rail + topbar + states (switcher
   open, sync states, user menu, author_name edit affordance), framing BOTH the
   shelf and the workspace (shelf views behind the chrome, light + dark); the
   language chip is drawn in **both variants (A: direct switcher with open menu,
   B: user-menu row)** as checkpoint tiles — **decided: A** (D17); the chip is
   the switcher, the contract is extracted in W4.
4. Book-settings surface (§6.6) + goal setters (daily + chapter) placement —
   **decided: inline at the element** (D20), the settings surface carries the
   user daily goal too.
5. Zen draft: timer/focus real, audio disabled — **sepia cut** (D18); the
   drafts were regenerated without any sepia control.
6. Focus semantics — **decided (D19): F9 toggles zen on/off; Esc exits.**

**Checkpoint decisions (owner, 2026-11-16 — all six points settled):** sepia
cut (D18); placeholders stay visibly neutral as drafted (D21); goal setters
inline (D20); F9 toggles zen (D19); author names: both, as drafted (D22);
language control: variant A — the chip is the switcher and the language
contract is extracted in W4 (D17).

**Recipe (W1, verified):** `generate_screen_from_text` (edit_screens is
session-blind); designSystem assets light `485a76ff…` / dark `ca5cbb89…`,
modelId GEMINI_3_8_FLASH, DESKTOP; HTML check via get_screen → download_file
(HTML entities distort text checks). Owner checkpoint in Stitch → owner exports
zip → implementer unpacks into the archive (README rows, superseded marks).

**Audit obligation applies to round output:** re-check for logical errors and
unintended features before porting; owner decides.

## 8. Missing data — interim + gap doc + follow-ups

Gap doc: `docs/design/stitch/gaps/2026-11-16-w4.md` (English, feature gaps +
draft gaps, each with trigger + follow-up issue). One index issue
(`follow-up-index`) at wave open; one child per row (`follow-up` + area label).
Interim renders live in code beside the element, ending in the child number.

| Drafted element | Interim in W4 | Trigger / wave |
|---|---|---|
| Dock finding card content | neutral geometry | knowledge wave (findings API exists) |
| Entity spotlight / GEN-4 / „Wiki öffnen" | neutral / omitted | knowledge wave |
| Atmosphere grid | neutral | knowledge wave (no fields) |
| Chat composer / ⌘J | disabled | chat wave |
| Lore graph / context chips | neutral geometry | knowledge wave |
| Entity tags in prose / causality pills | neutral geometry | knowledge wave |
| „Entwurf v2.4" badge | novel.status word, no version | versioning feature |
| Chapter/scene status lines | neutral dot, no line | status field |
| FOLIO / „Seite x von y" | omitted | pagination |
| History button | disabled | editing wave (`revision-history`) |
| Ribbon export (PDF/EPUB/DOCX) | disabled | production wave (`export-typesetting`) |
| Soundscape presets + volume | disabled | audio wave |
| Sepia toggle | cut (D18) — removed from the drafts | resolved at checkpoint |
| Stil trigger | neutral `—` | style presets feature |
| Tension arc curve | placeholder curve (stage label real) | tension data |
| Dekor-Spines (story-specific) | generic or removed by round | round |
| „Workspace-Layout" tune | disabled | layout customization feature |
| ⌘K chip | disabled | shell palette wave |
| Revision counter (variants) | omitted | versioning |

**Shelf gap rows W4 resolves (close from commits):** 3 (hero door → workspace
resume), 7 (status setter), 8 (series editor — incl. the new create endpoint),
9 (target edit), 10 (arbitrary targets), 19 (per-book settings — the dialog note
becomes true), **20** (app-wide chrome delivers the shelf's rail/topbar —
owner, 2026-11-16, supersedes the shell-wave deferral), **25** (daily-goal
field lands in PR2 — the banner's „Heutiges Schreibziel"/remainder lines read
`daily_goal_words` in the same commit, honest neutral when unset; the hero-book
goal pin ends). Row 12 (language contract) resolves in W4: the checkpoint
picked the extracted switcher (D17).

## 9. PR split (5, owner; re-cut for the scene model)

| PR | Content | Gates/E2E |
|---|---|---|
| 1 | Stitch round + archive refresh + gap-doc skeleton + index issue (design only) | archive sanity, README parity; `chore` |
| 2 | Scene data model + migration + backend adaptation (activity/duplicate/export/setup/word counts/scene continuation endpoint) + app-wide chrome port (shelf re-chromed + read-only workspace tree/prose) + shelf banner daily-goal lines (rows 25, 20) | backend TDD, migration test, both E2E suites adapt + green (incl. chrome on both surfaces), chrome vitest/axe |
| 3 | Scene editor real: TipTap, autosave, chapter/scene CRUD + reorder both levels, leave guard, live word counts, scene metadata editing | writing E2E editing legs, vitest, axe |
| 4 | Continuation + ghost text + prompt parameter + prompt bar (input/pills real, Stil neutral) | fake-provider E2E (stream, accept, dismiss, prompt, refusal frames), vitest |
| 5 | Zen (timer/focus) + book-settings surface + goals + author profile + series-create endpoint + dock placeholders + fidelity gate | E2E settings/zen legs, axe both themes, screenshots vs harmonized draft |

Sequential to main; push per green task group; each PR honestly usable alone;
no findings deferred. **Fallback (owner approval needed):** if PR2 grows too
large, chrome moves to PR3 — the 5-PR shape is the owner's, deviations ask.

## 10. Verification

- Per PR: `just check`, `just test-file` on touched tests, `just verify` before
  merge; writing + setup E2E suites green (both adapt in PR2); vitest for new web
  logic; backend TDD (model, migration, derivations, user scoping, reorder
  contracts).
- axe AA both themes on workspace routes (existing E2E axe leg pattern).
- Fidelity (PR5): E2E screenshots of the workspace + zen, light/dark, next to the
  harmonized round drafts; re-shot master frames in `assets/screenshots/`.
- E2E stack: two workers max, per-suite DB, isolated ports, de-DE contexts
  (hand-made contexts repeat locale).
- Gap doc complete; every interim references its child issue; shelf rows closed
  from commits.

## 11. Decisions (owner, 2026-11-16)

- **D1** — Scene-centric composition, new data model (over the chapter-centric
  base draft).
- **D2** — Model A: writing owns prose scenes; planning `ScenePlan` stays, FK in
  the planning wave.
- **D3** — Chrome ships in W4 from a dedicated Stitch round draft.
- **D4** — Dock as drafted; placeholders now, knowledge wave fills.
- **D5** — Prompt parameter real in W4.
- **D6** — Zen timer + focus presets frontend-real; audio later.
- **D7** — Book-settings family complete + Stitch draft.
- **D8** — Daily goal AND chapter target real backend fields.
- **D9** — `User.author_name` profile field + Stitch; tier cut.
- **D10** — Sync display derived from autosave state.
- **D11** — Invented details follow the program default (neutral/stumm + gap).
- **D12** — Five smaller PRs (re-cut for the scene model).
- **D13** — Audit obligation: drafts checked for logical errors / unintended
  features; owner alone decides after explanation.
- **D14** — Large waves split into smaller PRs (program amendment).
- **D15** — Chrome is app-wide in W4: shelf and workspace both framed; row 20's
  shell-wave deferral superseded (2026-11-16, builder-check follow-up).
- **D16** — Deleting a chapter's last scene is allowed and leaves an empty
  chapter — a real state the round drafts; chapters may hold zero scenes
  (2026-11-16, builder-check follow-up).
- **D17** — Language control: variant A — the topbar chip is a real switcher;
  the language contract is extracted in W4 (row 12's trigger fires inside the
  wave; three pre-setup copies + one owned switcher) (checkpoint, 2026-11-16).
- **D18** — Sepia mode is cut (checkpoint, 2026-11-16); theme stays tri-state.
- **D19** — F9 toggles zen on and off; Esc exits as drafted (checkpoint).
- **D20** — Goal setters sit inline at the element (ring + chapter-target pill),
  as drafted; the settings surface carries the user daily goal as well
  (checkpoint).
- **D21** — Placeholder treatment stays visibly neutral as drafted (checkpoint).
- **D22** — Both author names exist as drafted: per-book `novel.author` (running
  head, book settings) and profile `User.author_name` (user block, atelier
  section) (checkpoint).

## 12. My calls (settled without the owner — check while reading)

- Scene `setting`/`story_time` as nullable label strings (drafted overline real
  when present; `story_time` a label like `TimelineEvent.date_label`, not a ts).
- Migration wraps each chapter body into one scene, title `""` (localized
  placeholder); `chapters.body` dropped.
- New chapters start with **zero scenes** (D16: empty chapters are a real
  state — the round's „Erste Szene starten" empty state is the canonical
  new-chapter experience; no auto-create). Scene delete is always allowed.
  Scene reorder is **within-chapter** in W4; cross-chapter moves are not drafted
  anywhere — no gap row, just absent.
- Zen timer is session-only (no persistence; nothing drafted shows any).
- Daily goal user-level/atelier scope; chapter target per chapter.
- Scene continuation endpoint replaces the chapter endpoint; prompt optional,
  bounded; refusal frames unchanged.
- Knowledge/chat-dependent variant elements (entity tags, lore graph, chat
  composer, causality pills) render geometry + neutral/disabled; later waves make
  real (extends D4's principle to the whole composition).
- Cover miniature real (writing's own data).
- Stil trigger neutral `—` + gap; ⌘K chip disabled + gap; ribbon export/history
  disabled + gap.
- Tension arc stage label from storyboard API; curve placeholder + gap.
- Shelf hero door resumes last-edited scene; label names chapter + scene.
- Shelf banner (gap row 25): the daily-goal and remainder lines read
  `daily_goal_words` in PR2, the commit that lands the field (gap law); the
  hero-book goal pin ends; honest neutral when unset.
- Series-create endpoint (`POST /api/writing/series`, title) rides PR5 — D7's
  full family needs it; link/volume stay on `NovelUpdate`.
- Continuation context: book-level reading order, nearest first (scene tail →
  chapter's earlier scenes → earlier chapters' scenes), budget-sliced — the
  chapter-predecessors logic refined, not a new product claim.
- Language chip: passive display (see §7.3); no switcher in W4.
- Chrome components live shell-owned in `web/` from the start (the rail names
  every capability's areas — it is app chrome, not writing's; the shell wave
  grows it, no capability-local copy to extract later).
- Badge renders `novel.status` word without version; status lines neutral until
  a status field exists.
- PR2 fallback split (chrome → PR3) only with owner approval.

## 13. Left to the builder / plan

- Exact files, task order, class strings, i18n keys, E2E updates per PR.
- TipTap scene-editor architecture (one instance swapping scenes vs per-scene),
  autosave debounce/flush/leave-guard semantics rebuild, ghost stream handling.
- Timer implementation; number-words util bound/fallback; migration revision
  chain; user-profile PATCH route placement.
- Round brief's exact prompts; task count/grouping per PR (writing-plans).
- Spec amendment text for the v2 architecture doc (scene model, continuation
  unit, activity source) — committed by the build session with the design.

---

*Drafted 2026-11-16 (plan session). Builder check pending; owner approval gates
the plan (superpowers:writing-plans).*
