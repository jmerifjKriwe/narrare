# UI Command Focus: Backlog Design (Atlas Remainder)

Status: 2026-11-10 · State: draft for the next planning · Location: `docs/superpowers/specs/`

The place atlas (`2026-11-06-narrare-ui-command-fokus-design.md`, §5.7 — the atlas is the German-language design record) gives
each feature family exactly one home. This page records what remains open after the
frontend-remainder slice: per family, what exists today, which backend contract is
missing, which UI shape is already decided, where the entry point is, and which
single decision the next planning session must make first.

Sources against which every "exists today" statement is verified (no assumptions):
`app/capabilities/planning/router.py`, `app/capabilities/knowledge/router.py`,
`app/capabilities/writing/router.py`, `app/capabilities/settings/router.py`,
`app/capabilities/chat/router.py`, `app/capabilities/prompts/router.py`,
`web/lib/generated/routes.ts`, `web/lib/generated/docks.ts`,
`app/capabilities/planning/web/routes.tsx`. Endpoint paths below name only routes
verified via `grep` in these files; everything else is stated as a prose contract
("it needs …"), not as an invented path.

## What is already built (not open, listed only for delineation)

- **Timeline + storyboard-substrate slice (earlier):** timeline canvas
  (`/planning`, from PR #768), storyboard read API
  (`GET storyboard`, `PUT …/stage`, `POST …/remap` in
  `planning/router.py`) and storyboard canvas (`/planning/storyboard`).
- **This slice:** structure canvas (`/planning/structure`, proportion bars,
  purely reading on the storyboard read API) and neighbourhood lens
  (`NeighborhoodLens.tsx`, on `GET /entities/{id}/relations` in
  `knowledge/router.py`).
- **Built even earlier (backend present, UI present):** KB merge
  (`POST /entities/{entity_id}/merge`, `MergeEntityDialog.tsx`) — marked as
  done below, no open row. Knowledge-graph CRUD (relation and
  entity endpoints in `knowledge/router.py`, `GraphPage.tsx`). Scene persistence
  (`GET`/`PUT scenes`, `SceneDock.tsx`). Timeline-event CRUD
  (`timeline-events` endpoints). Extraction (`POST /extraction/{novel_id}`),
  consistency job + findings (`POST /consistency/{novel_id}`,
  `GET …/findings`), suggestions (`…/suggestions`, accept/discard). Chat
  (`POST /chat/ask`, chat dock). Prompts CRUD + diff (`prompts/router.py`).
  Manuscript export (`POST …/export`) and import (`POST …/import`) in
  `writing/router.py`. Consistency dock (`ChecksPanel.tsx`).

## Closed by the frontend-only pass (2026-11-10)

Built on this branch, verified in code, so the rows below no longer list
them as open:

- **Graph pan/zoom with reset and clamped view** (`GraphPage.tsx`:
  `clampGraphView` keeps every node inside the viewport, one action resets
  to the full view).
- **Storyboard drag & drop** (`StoryboardPage.tsx`: cards drag onto another
  stage column and write through the existing `PUT …/stage`; a refused move
  snaps the card back).
- **Slash door into the palette** (`slashPalette.ts`, `Palette.tsx`: typing
  `/` in an empty paragraph opens the palette with `/` prefilled — a door
  into the palette, not a second menu; anywhere else `/` stays a normal
  character).
- **Shortcut registry + read-only Shortcuts cluster** (`web/lib/shortcuts.ts`
  lists only bindings verified against their listeners; the settings cluster
  renders them read-only and states that remapping is not on offer).
- **Storyboard remap preview + Apply confirm dialog** (`StoryboardPage.tsx`:
  `RemapForm` in a `Dialog` previews via `POST …/remap` with `confirm: false`
  and applies with `confirm: true`; a refused remap surfaces, then retries).
- **Three additional structure adapters** — `save-the-cat`, `five-act`, and
  `seven-point` join `three-act` and `heros-journey` in
  `app/capabilities/planning/structures.py` (five structures total). The
  storyboard/structure view is registry-driven via the generated
  `web/lib/generated/structures.ts` (`just generate` regenerates it), so a
  sixth structure is a registry entry plus `just generate`.

## Planning area (nav area "Planen", landing: timeline)

| Family (IDs) | Atlas slot (P-no.) | Exists today | What is missing (backend contract in prose) | UI shape (decided) | Entry point | First decision of the next planning |
|---|---|---|---|---|---|---|
| Timeline (PLAN-004) | Nav-area landing canvas (P1) | Event CRUD and timeline canvas exist. | AI extraction (read time expressions from chapters, propose them as events), character age (birth dates on KB entities + age computation), temporal consistency check. Spec: `docs/features/planning/PLAN-004-timeline.md` and `PLAN-004-architecture.md` (which foresee exactly this foundation). | Canvas stays, findings land as a list beside it; no second slot. | Timeline canvas (`/planning`). | Extraction contract first: proposal table (analogous to KB suggestions with accept/discard) or direct event creation? |
| Storyboard (PLAN-005) | Canvas route under planning | Read API, stage assignment (`PUT …/stage`), remap with preview (`POST …/remap`), canvas, drag & drop (cards onto stage columns), and the remap preview + Apply confirm dialog (`RemapForm` in a `Dialog` in `StoryboardPage.tsx`: `confirm: false` preview, `confirm: true` apply) exist. | **Partly backend-open:** AI remap (content-aware mapping from chapter summaries, per the PLAN-005 spec) runs nowhere — the service maps by position ratio and the dialog surfaces no AI signal. The preview + Apply confirm dialog itself is built, not open. | Card grid full width, no dock. | Timeline landing (only door to the sibling canvas). | AI remap: automatic when summary coverage suffices or explicit opt-in? |
| Story structure (PLAN-003) | Canvas route under planning | Structure canvas (proportion bars, reading) and registry (`planning/structures.py`, default `three-act`) exist — five structures total (`three-act`, `heros-journey`, `save-the-cat`, `five-act`, `seven-point`), and the view is registry-driven via the generated `web/lib/generated/structures.ts`. | **No backend needed — freely plannable:** a sixth structure is a registry entry plus `just generate` (pure configuration, no migration). Follow-up: `app/capabilities/planning/web/stageNames.ts` keeps a hand-maintained stage-key list parallel to the backend registry — a sixth structure would render raw keys there; consider generating it or deriving it from `structures.ts`. Structure switching runs via the existing `POST …/remap`. | Spatial act/chapter visualisation, no reading beside the text. | Storyboard canvas (cross-link) and command line. | Which structures belong in the registry (fixed set vs. user-defined)? |
| Scene planning (PLAN-001) | Dock tab "Planen" (switcher, P2) | Scene CRUD (`GET`/`PUT scenes`) and `SceneDock.tsx` (draft/hold/save) exist. | AI drafting and refinement: endpoints that propose a scene breakdown from chapter + KB context, or revise a scene on instruction; draft as proposal, saving stays explicit. Spec: `docs/features/planning/PLAN-001-scene-planning.md` (names the service, contract, router, and prompt files of the v1 planning). | Dock beside the editor, editor stays visible. | Planning dock on the workspace. | Proposal storage: scene drafts as their own proposal table or as non-binding draft in dock state (nothing persisted until save)? |
| Gap analysis (PLAN-002) | Dock tab "Planen" (switcher) | Nothing (no endpoint, no table). | Finding run: endpoint deriving missing transitions, unresolved threads, unused entities, and time jumps from manuscript + timeline events + KB, plus finding storage with status (open/discarded/fixed). Spec: `docs/features/planning/PLAN-002-gap-analysis.md`. | Finding list beside the text, no surface. | Planning dock (switcher entry) and command line. | Share the finding model with CONS-001 findings or own table (different lifetime: plan vs. fact)? |
| Character arc (PLAN-006) | Dock tab "Planen" (switcher, P3) | Nothing (no endpoint, no table). | Arc session: endpoint generating a multi-phase arc (phases, turning points, relationships, inner conflict) from start/target state + KB character, plus storage for saved arcs per character. Spec: `docs/features/planning/PLAN-006-character-arc.md`. | Dock reading beside the manuscript; comparison via command into the same tab. | Planning dock (switcher entry). | Persist arcs (own table per character) or prompt session without storage (new each time)? |

## Analysis area (nav area "Analysieren", landing: hub)

All eleven ANAL families share one pattern (command → report) and the same
missing foundation: there is **no** analysis backend — no endpoint, no
report table (verified: no `analysis` capability directory, no
analysis route in `generated/routes.ts`). Specs: `docs/features/analysis/ANAL-001`
through `ANAL-011`. The contract is the same per family: one run endpoint
(as a job, since LLM runs are long, following the `POST /consistency/{novel_id}`
→ 202 + result-query pattern) plus report storage with rerun.

| Family (IDs) | Atlas slot (P-no.) | Exists today | What is missing (backend contract in prose) | UI shape (decided) | Entry point | First decision of the next planning |
|---|---|---|---|---|---|---|
| Beta reader (ANAL-001) | Nav-area hub landing (P4) | Nothing. | Report run + storage as above; spec: `docs/features/analysis/ANAL-001-beta-reader.md`. | Hub landing, human face of the hub. | "Analysieren" entry (rail). | Report format: one free-text assessment or structured finding sections (adopt/discard per item)? |
| Sentiment (ANAL-002) | Dock tab "Analyse" (switcher) | Nothing. | Trend values per chapter/scene (table: time series) + run endpoint; spec: `docs/features/analysis/ANAL-002-sentiment.md`. | One report among many in the switcher. | Analysis dock, command line. | Storage granularity: per chapter or per scene? |
| Readability (ANAL-003) | Dock tab "Analyse" (switcher) | Nothing. | Score run (deterministically possible, no LLM needed) + score storage; spec: `docs/features/analysis/ANAL-003-readability.md`. | Score view in the switcher. | Analysis dock, command line. | **No-backend-needed check:** if purely deterministic and computable live, storage is dropped — that is the first question, not the technology. |
| POV analysis (ANAL-004) | Dock tab "Analyse" (switcher) | Nothing. | Perspective-break finding grid (run + finding storage); spec: `docs/features/analysis/ANAL-004-pov.md`. | Finding grid in the switcher. | Analysis dock, command line. | Merge with gap analysis (PLAN-002) or separate finding tables? |
| Coreference (ANAL-005) | Dock tab "Analyse" (switcher) | Nothing. | Reference-check run + findings; spec: `docs/features/analysis/ANAL-005-coreference.md`. | One check among many. | Analysis dock, command line. | Deterministic (rules, like CONS-001) or LLM run (jobs)? |
| Sensitivity review (ANAL-006) | Dock tab "Analyse" (switcher) | Nothing. | Flag list (run + findings with severity); spec: `docs/features/analysis/ANAL-006-sensitivity.md`. | Flag list in the switcher. | Analysis dock, command line. | Severity model, and whether flags reuse CONS-001 findings. |
| Author voice (ANAL-007) | Dock tab "Analyse" (switcher) | Nothing. | Profile comparison (voice-profile storage + delta run); spec: `docs/features/analysis/ANAL-007-voice-author.md`. | Profile comparison in the switcher. | Analysis dock, command line. | Profile model: where does the reference profile live (author level, table)? |
| Character voice (ANAL-008) | Dock tab "Analyse" (switcher) | Nothing. | Like ANAL-007, per character; comparison against voice-checker dock is reading; spec: `docs/features/analysis/ANAL-008-voice-character.md`. | Profile comparison in the switcher. | Analysis dock, command line. | Attach character profiles to KB entities or own profile table? |
| Voice drift (ANAL-009) | Dock tab "Analyse" (switcher) | Nothing. | Delta view across chapters (time series like sentiment); spec: `docs/features/analysis/ANAL-009-voice-drift.md`. | Delta view in the switcher. | Analysis dock, command line. | Build on ANAL-007/008 profiles (then only plannable after them) or standalone? |
| Plot analysis (ANAL-011) | Dock tab "Analyse" (switcher, P5) | Nothing. | Finding list beside the text (run + findings); structure canvas stays complementary; spec: `docs/features/analysis/ANAL-011-plot-analysis.md`. | Dock, no double home with the planning canvas. | Analysis dock, command line. | Delineation from PLAN-002 findings (two lists or one with source)? |
| Literary suite (ANAL-010) | Canvas route under analysis (P6) | Nothing. | Multi-dimensional report (only ANAL canvas); spec: `docs/features/analysis/ANAL-010-literary-suite.md`. | Only canvas beside the hub (breaks 352 px). | Analysis dock → cross-link "Suite öffnen". | Suite as collective run over the individual reports (orchestration) or own run with own contract? |

## Writing area (home shelf, no new rail entry)

Writing backend today: manuscript CRUD, chapter CRUD + ordering,
continuation (`POST …/continue` as SSE run) in `writing/router.py`. There is
**no** LLM endpoint for rewriting, variants, voice, research, titles,
names, or sessions (verified via `grep` in `writing/router.py` +
`service.py`: only `continue`). Specs: `docs/features/writing/WRITE-00x`,
`docs/features/ai_assist/ASSIST-00x`, `docs/features/generation/GEN-00x`.

| Family (IDs) | Atlas slot (P-no.) | Exists today | What is missing (backend contract in prose) | UI shape (decided) | Entry point | First decision of the next planning |
|---|---|---|---|---|---|---|
| Multi-draft (WRITE-008) | Dock tab "Schreiben" (switcher, P7) | Nothing. | Variant run: generate 2–5 drafts in parallel from passage + focus instruction, each with focus label and strengths/weaknesses; storage for adopted/compared sentences. Spec: `docs/features/writing/WRITE-008-multi-draft.md`. | Comparison editor column + dock, max. 3 side by side, toolbar language like diff. | Writing dock (switcher). | Persist variants (resumable) or transient (discarded after decision)? |
| Co-author (WRITE-006) | Dock tab "Schreiben" (switcher) | Nothing (only `continue` as building block). | Session model: multi-turn co-author session with history and adoption contract (diff/accept per proposal). | Running session with surface, no one-shot. | Writing dock (switcher). | Session history in its own table or as prompt-history entries? |
| Unblock tools (WRITE-009) | Dock tab "Schreiben" (switcher, P8) | Nothing. | Exercise/impulse session: prompt runs (no text change without adoption). | Reading surface beside the editor, no one-shot. | Writing dock (switcher). | Does this need backend at all, or is it a prompt library on `continue` (then "no backend needed")? |
| Voice checker (WRITE-010) | Dock tab "Schreiben" (switcher) | Nothing. | Writing-feedback run against reference profile (reads ANAL-007/008 profiles, writes nothing). | With the text, counterpart to ANAL-007..009. | Writing dock (switcher). | Only plannable after ANAL-007/008 profiles — respect the ordering. |
| Context inspector (WRITE-014) | Dock tab "Schreiben" (switcher) | Nothing (KB search `POST /search` exists as building block). | Inspector query: what the model currently sees (context window, cited KB facts) — reading endpoint, no generation. | Inspectable surface, no transient hit. | Writing dock (switcher). | Format: raw context or curated "used facts" list? |
| Plot check (ASSIST-001) | Dock tab "Schreiben" (switcher) | Nothing. | Finding run against manuscript + KB; spec: `docs/features/ai_assist/ASSIST-001-plot-check.md`. | Findings need the manuscript beside them. | Writing dock (switcher). | Own findings or shared with ANAL-011/PLAN-002 (three lists are two too many)? |
| Dialogue coach (ASSIST-004) | Dock tab "Schreiben" (switcher) | Nothing. | Multi-turn dialogue session with adoption contract; spec: `docs/features/ai_assist/ASSIST-004-dialogue-coach.md`. | Session, multi-turn. | Writing dock (switcher). | Like co-author session: one session model for both or one per family? |
| Research (GEN-002) | Dock tab "Schreiben" (switcher, P9) | Nothing (document upload `POST /documents` exists as storage). | Research run: source suggestions for passage/question, reading beside the prose; storage optional (found again in documents). | List in 352, no graph case. | Writing dock (switcher). | Persist sources (documents table) or transient? |
| Workflows (WRITE-013) | Command-only | Jobs building block (`/api/jobs/{job_id}`) exists. | Multi-step runs as command sequences with `JobStatus`; no new backend, only orchestration per workflow. | No surface, status via `JobStatus`. | Palette. | First workflow as template (which one?), rest follows the template without planning. |
| Inline suggestions (WRITE-007) | Command-only | Nothing (ghost-text rendering is also missing, but that is frontend). | Proposal run: ghost text for the cursor position from manuscript + KB context (latency-critical, streaming). | Surface is the editor itself. | Editor (automatic/shortcut). | Latency budget and cancellation semantics before the contract. |
| Rewrite (WRITE-004) | Command-only | Nothing. | Rewrite run: passage + instruction → proposal with diff (hunk accept/discard, pattern from §5.5). | Transient + diff, no dock. | Palette / editor selection. | Proposal transient or storable as draft variant (bridge to WRITE-008)? |
| Slash commands | Command-only | Mechanics exist (palette + `commands.ts` register). **Built:** the slash door — typing `/` in an empty paragraph opens the palette with `/` prefilled. | The alias mechanics need no backend — the slash door is built (a door into the palette, not a second menu); each target action needs its own family contract (see above). | Slash is the door into the palette, not a second menu. | Editor (`/`). | Alias catalogue: which actions get aliases (all or curated)? |
| Prompt history | Command-only | Jobs API exists; prompts CRUD + diff exist. | Run history per prompt (which run, which input, rerun): storage + query, jobs table as building block. | List in the palette, no surface. | Palette (rerun row). | History as its own table or fixed part of jobs storage? |
| Title suggestions (ASSIST-002) | Command-only | Nothing. | One-shot list + adopt (smallest LLM contract: input manuscript context, output N titles). | Transient, adopting inserts. | Palette. | Template contract for all one-shot lists (titles, names): define once, use twice. |
| Name generator (GEN-001) | Command-only | Nothing. | Like titles: one-shot list + adopt. | Transient. | Palette. | See titles (shared contract). |
| Series (SERIES-001..004) | Canvas route under writing (P10) | Nothing (no series model, no cross-volume endpoints). | Series contract: volume management (creation/ordering), generation context across volumes, voice hierarchy, cross-volume drift. Specs: `docs/features/series/SERIES-001` through `-004`. | Shelf-adjacent canvas, no rail entry. | Shelf card. | Series model first (volumes as novel group): without it no sub-contract is buildable. |
| Writing stats (STATS-001) | Canvas route "Auswertung" under writing | Nothing. | Time series from existing data (word counts, sessions): aggregation query, no new writing table needed, only a read endpoint. Spec: `docs/features/analytics/STATS-001-writing-stats.md`. | Charts need width, no dock. | Shelf card. | Which v1 metrics (words/time suffices as start)? |
| Cost tracking (STATS-002) | Canvas route "Auswertung" (tab, P11) | Model/provider management exists (`settings` router). | Usage log per run (tokens/cost) + query for the tab; keys/quotas stay in settings. Spec: `docs/features/analytics/STATS-002-cost-tracking.md`. | Tab of the stats canvas, no double home. | "Auswertung" canvas. | Log obligation: every LLM run writes one usage record (cross-cutting over all families). |

## Knowledge area (existing rail entry)

| Family (IDs) | Atlas slot (P-no.) | Exists today | What is missing (backend contract in prose) | UI shape (decided) | Entry point | First decision of the next planning |
|---|---|---|---|---|---|---|
| Knowledge graph (KB-008) | Canvas route under knowledge | Full-graph canvas (`GraphPage.tsx`) + graph CRUD (entities, relations, proposals, extraction) exist. Pan/zoom built (clamped view, one-action reset). | Frontend remainder: large graphs (layout/clustering) — decision: no clustering until a real novel exceeds the node cap. Cross-cutting note: hybrid KB references (vector + keyword) as retrieval improvement concern `POST /search`, but are a later contract addition, not a blocker. | Full page, no dock. | Knowledge entry (rail). | Display budget: from which node count is clustering applied (binding number)? |
| Editor graph (KB-010) | Dock tab "Wissen" (switcher, P12) | Neighbourhood lens (`NeighborhoodLens.tsx`) on `GET /entities/{id}/relations` — this slice. | Done except polish; cross-link "Im Graphen öffnen" exists as decision, verify implementation. | Local lens beside the selection. | Knowledge dock. | None — accept as built, rest as normal bugs. |
| Worldbuilding (KB-006) | Dock tab "Wissen" (switcher) | Entity CRUD exists as storage building block; no guided creation. | Guided creation session: questions → entity drafts → adoption into entity table (`POST` entity endpoints present as building block). | Conversational, not spatial. | Knowledge dock (switcher). | Question catalogue as prompt library (then "no backend needed") or own session storage? |
| KB merge (KB-009) | Dock tab "Wissen" (switcher, P13) | **Built:** `POST /entities/{entity_id}/merge` + `MergeEntityDialog.tsx`. | Nothing open. | Pair decision beside the entries. | Knowledge dock. | None — done, no planning subject. |

## Settings area (existing anchor, cluster per `settingsRoutes`)

| Family (IDs) | Atlas slot (P-no.) | Exists today | What is missing (backend contract in prose) | UI shape (decided) | Entry point | First decision of the next planning |
|---|---|---|---|---|---|---|
| Consistency rules (CONS-002) | Settings cluster (P14) | Rule checker (CONS-001: job + findings + dock) exists; rules themselves do not (no rule endpoint in `knowledge/router.py`). | Rule CRUD: rule table (pattern, severity, on/off) + integration into the checker run. Spec: `docs/features/consistency/CONS-002-rules.md`. | Rule CRUD with toggles is configuration. | Settings hub (own cluster). | Rule language: free-text patterns or structured conditions (fixes table schema)? |
| Shortcuts (SET-004) | Settings cluster | Keyboard guidance of the palette exists. **Built:** the shortcut registry (only bindings verified against their listeners) and the read-only Shortcuts cluster — remapping is explicitly NOT available. | Rebinding is the open remainder and needs a backend-shaped contract: one dispatcher for every listener site + conflict resolution + where the override lives (as the spec foresees: `docs/features/settings/SET-004-shortcuts.md`). | Configuration beside the other clusters. | Settings hub (own cluster). | Rebinding first: one dispatcher for every listener site, conflict resolution, or override storage? |
| Prompt UX (PROMPT-001..003 + custom UX) | Settings cluster | Homed: prompts CRUD + diff (`prompts` capability, `settingsPages` row). | Nothing fundamental; custom-UX parts (own variables, preview) as extension of the existing contract. | No rebuild, atlas confirms. | Settings hub (prompts cluster). | Which custom-UX parts in v1 (variables first)? |
| External sync (IO-003) | Settings cluster (P15) | Nothing. | Sync contract: target configuration (credentials/schedules, cluster page) + "sync now" run as job with progress. Spec: `docs/features/io/IO-003-sync.md`. | Configuration with home; sync button on the cluster page. | Settings hub (own cluster). | First sync target (one provider as template)? |
| Manuscript export (IO-001) | Command-only | **Backend present:** `POST …/export` in `writing/router.py`. | **No backend needed — freely plannable:** one-shot job + `JobStatus` + download as palette action. Spec: `docs/features/io/IO-001-export.md`. | No surface. | Palette. | Export formats v1 (which formats, which options)? |
| Import/corpus pass (IO-002, incl. SETUP-003) | Command-only | **Backend present:** `POST …/import` in `writing/router.py`. | **No backend needed — freely plannable:** job with progress, entry via shelf command. Spec: `docs/features/io/IO-002-import.md`. | No surface. | Shelf command. | Corpus-pass scope (text only, or KB extraction in the same run)? |

Already homed, no open rows (precedence from atlas §5.7):
CONS-001 checker (consistency dock), free-form chat (CHAT-001, chat dock),
KB-005 proposals and KB-002..004-/KB-007 improve/extract (command lines
or knowledge dock), learning surfaces (LEARN-001/002, only via atlas amendment).

Cross-cutting deferrals from the task-3 brief, where they live above: hybrid
KB references → KB-008 row; scene AI → PLAN-001; storyboard DnD/AI remap/
extra structures → PLAN-005/PLAN-003 (backend present); timeline AI/age/
consistency → PLAN-004; graph pan/zoom → KB-008 (frontend); stats/cost →
STATS-001/002; series → SERIES row; shortcuts → SET-004 (frontend);
consistency rules → CONS-002; external sync → IO-003; worldbuilding → KB-006;
multi-draft/co-author/unblock/voice/context/plot-check/dialogue-coach/research →
their writing rows; command-only-with-LLM (rewrite, titles, names,
inline, workflows, prompt history) → their command rows.

## Ordering recommendation

Three items unlock the most atlas rows — in this order:

1. **Uniform LLM-run contract (jobs + finding/report storage + usage record).**
   Why: all eleven ANAL reports, gap analysis, plot check, voice families, and
   the one-shot lists (titles, names, rewrite) need the same shape —
   run-as-job, result storage with status, rerun from prompt history,
   one usage record per run for STATS-002. One template instead of eleven contracts;
   readability (ANAL-003) and coreference (ANAL-005) clarify along the way whether
   they need the template at all (deterministic → no storage).
   Directly unlocks: ANAL-001..011, PLAN-002, ASSIST-001, STATS-002,
   prompt-history rerun.

2. **Voice-profile model (ANAL-007/008) before its consumers.**
   Why: author voice, character voice, and voice drift share one
   profile schema; voice checker (WRITE-010) and character voice read the same
   model. Fix the profile schema first (where the reference profile lives, whether
   the character profile hangs off the KB entity), then four rows are pure
   run variants following template 1. Unlocks: ANAL-007/008/009, WRITE-010.

3. **Series model (SERIES-001) before series UI.**
   Why: the series canvas is the only open canvas route with a new
   data model (volume group over novels). Without the group model no
   sub-contract (generation context, voice hierarchy, drift) is buildable; with it
   the canvas is a reading aggregation of existing building blocks. Unlocks:
   SERIES-001..004 and the series canvas as entry point.

After that, the remaining "no backend needed" rows (export/import commands)
are free frontend planning with no backend dependency — they can run in parallel
once capacity exists and need no further backend planning. Storyboard DnD,
the shortcuts registry and cluster, graph pan/zoom, extra structures, and
slash aliases are built — see "Closed by the frontend-only pass" above.
