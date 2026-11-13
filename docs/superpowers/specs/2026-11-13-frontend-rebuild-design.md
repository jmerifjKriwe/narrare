# Frontend rebuild from the Stitch drafts — design

Status: design for owner approval · Date: 2026-11-13 · Mode: plan session
(build session moves this into `docs/superpowers/specs/` per AGENTS.md)

## Intent and why

The Stitch drafts under `docs/design/stitch/` and the live Stitch project
(`15314899202287259920`) are what narrare's UI should be; the implemented UI is
not, and the gap has been growing through three fidelity waves. The owner
decided to stop repairing and rebuild: delete the entire current frontend —
UI code, web unit tests, E2E suites — and port the UI screen by screen from
the Stitch drafts, starting with the welcome screen and the setup assistant.

The backend, the v2 capability architecture and the standing rules stay.
Design authority moves to Stitch: **nothing in the UI is invented locally.**

## Goals

- Every screen is ported from a Stitch draft (fetched via MCP or the owner's
  project export), 1:1 in geometry and tokens.
- Welcome screen and setup assistant are fully functional with **real
  backend** (owner chose "everything real, including import and templates" —
  staged across waves, nothing stays a placeholder at the end).
- Each wave ships its own E2E suite that drives real UI + backend + DB
  (rule 2 stays binding on the rebuild).
- All GitHub issues that live in the deleted code are closed with a reopen
  condition; backend bugs stay open.

## Non-goals

- No backend re-architecture, no new data store, no changes to the kernel or
  the provider seams beyond what the new setup fields need.
- No change to the stack: Vite + React + TanStack Router + TipTap + Tailwind,
  pytest + Playwright.
- Mobile screens (Narrare Pocket) are not part of the first program phases.

## Anti-goals

- Locally invented UI components, layouts, states or copy standing in for
  missing drafts. A gap is either a Stitch round or an honest placeholder
  (draft geometry, neutral `—` values, disabled controls) recorded in the
  gap doc.
- Keeping old UI alive alongside the rebuild ("strangler") — rejected: the
  owner explicitly wants the old frontend gone, and rebuilding screen by
  screen against old code doubles the work per screen.

## Authority and workflow (owner decisions, 2026-11-13)

1. **Stitch is the sole design authority.** Screens and their HTML source are
   fetched from the Stitch project via MCP (`list_screens` → `get_screen` →
   `download_file`, the HTML is in the response's `html` field) or from the
   owner's project export zip. Local work is porting only: React components,
   design tokens, i18n (en/de/fr), API wiring.
2. **Correction loop.** A draft that overlooked something (missing state,
   wrong data, contradiction with the backend) is not patched locally: the
   gap is named precisely and a new draft is requested via MCP
   (`edit_screens` for existing screens, `generate_screen_from_text` for new
   ones), including the information Stitch lacked. The corrected draft is
   re-exported into the archive, then ported.
3. **MCP blind spot (measured 2026-11-13).** `list_screens`/`get_project` do
   not return every screen: the owner's export zip contained six screens the
   API never showed. Before concluding "no design exists", check the project
   export zip. The zip lives at `docs/design/stitch_narrare.zip` until W0
   unpacks the new screens into the archive structure.
4. **Placeholders.** Features on a draft without a backend yet keep the
   draft's geometry with honest neutral values (`—`, empty bars, disabled
   controls — never invented numbers) and go into the English gap doc with:
   element, draft value, interim render, trigger that makes it real,
   follow-up issue. The gap doc records both kinds: **feature gaps**
   (backend missing) and **draft gaps** (Stitch overlooked something).

## Authoritative drafts for waves 0–3

From the owner's export (`docs/design/stitch_narrare.zip`):

| Screen | File | Role |
|---|---|---|
| Willkommen im Atelier | `willkommen_im_atelier_narrare/` | Welcome/landing screen |
| Projekt-Setup 1/4: Basis & Vorlage | `projekt_setup_start_oder_demo_vorlage_w_hlen_narrare/` | Wizard step 1 |
| Projekt-Setup 2/4: Dramaturgie & Struktur | `projekt_setup_dramaturgie_struktur_narrare/` | Wizard step 2 |
| Projekt-Setup 3/4: KI-Regeln & Tonalität | `projekt_setup_ki_regeln_tonalit_t_narrare/` | Wizard step 3 |
| Projekt-Setup 4/4: Bereitstellung & Start | `projekt_setup_bereitstellung_start_narrare/` | Wizard step 4 |
| Bücherregal: Filter geöffnet | `b_cherregal_filter_ge_ffnet_narrare/` | Later wave (shelf) |

Superseded: `willkommen_autoren_onboarding_narrare/` (the old combined
3-step draft) stays archived as a historical draft; W1 feeds its unique
elements (cover preview, genre tag pills, word-count gauge) into the
harmonization round.

## Decisions log (owner, 2026-11-13)

- Demolition is big-bang; **plumbing stays**: Vite/Tailwind config, i18n
  engine, API client, `globals.css` tokens, router scaffolding, `just`
  targets, CI. UI code, web unit tests and E2E suites go.
- Standalone welcome screen (exists: "Willkommen im Atelier") in front of the
  setup assistant (the found 4-step flow).
- Wizard structure follows the found flow; the old combined draft and the
  screen-architecture blueprint are reconciled by a Stitch round (W1), not by
  local judgement.
- Everything real, including import and templates — staged across waves.
- German copy uses **du** (the drafts' Sie forms are adapted during porting;
  layout unchanged). English and French follow their usual conventions.
- Demo cards in step 1 carry the **three real demos** (Dead Signal, Echoes of
  the Thornwall, Im Stillen Wald) with their real titles, genres and blurbs
  in the draft's card layout. Winterhaus and The Salt Road exist only as
  screenshot seeds, not as demos.
- PR #808 (W3 workspace literary modernism) is closed; the `feat/shelf-fidelity`
  branch and its worktree are abandoned.
- Frontend/E2E issues are closed per the mechanism below.
- **One PR per wave** (owner): main carries the interim honestly; release-please
  release PRs stay unmerged until the program's end — nothing unusable is
  released; issue closures land wave by wave with their PR.
- **Post-setup landing** (owner): a W1 Stitch round designs the "setup
  complete / returning user" state (empty shelf + return chrome); W2 ports it
  as the minimal destination of the wizard's last step and of every later
  visit. No locally invented landing.
- **Demo semantics** (owner): archive content wins for novel fields (title,
  genre, chapters come from the demo); the user's typology, AI role and canon
  strictness still bind onto the imported project; the title/genre inputs in
  step 1 disable when a demo card is chosen.
- Welcome screen and setup assistant ship as **one wave** (agent call): one
  shipping milestone, one E2E suite from welcome to landing.
- **Tests of kept plumbing survive W0** and move with their code — the
  token/type gates are the porting program's drift mitigation; only tests of
  deleted UI code go (agent call, resolves the doc's own contradiction).
- **W1 ends with an owner checkpoint**: the harmonized drafts are reviewed in
  Stitch before porting starts; the owner can waive it (agent call).

## Waves

### W0 — Demolition and scaffold

- Delete: `web/components`, `web/ui`, `web/routes`, `web/lib` UI logic that is
  page-specific, all `app/capabilities/*/web/` UI, the web unit tests of
  deleted UI code, all `app/capabilities/*/e2e/` suites, showcase specs. Keep
  plumbing (above), everything under `app/` that is not UI, and the tests of
  kept plumbing — they move with their code (`tokens.test.ts` and friends are
  the drift gates the risk section relies on).
- Boot state: the app starts to a bare welcome route; every other capability
  has no page. Generated views (`web/lib/generated/*`) and the shell's route
  mounting must compile with capability `web/` folders gone — stubs or
  generator adjustments are part of W0; `just check`, `just check-generated`,
  `just test`, `just test-frontend` and `just verify` must be green at the
  end of W0.
- i18n: shared catalogs lose the keys of deleted UI (en/de/fr parity is a
  build error, so cleanup is mechanical and gate-checked).
- Archive: unpack the six new screens from
  `docs/design/stitch_narrare.zip` into `docs/design/stitch/screens/<area>/`
  (naming per README), update the README table, delete the zip.
- Issues: close per the mechanism below; add the wave's row to
  `docs/superpowers/follow-ups.md`.
- Close PR #808, delete the shelf-fidelity worktree and branch.

### W1 — Stitch harmonization (design only, MCP)

- Merge round: feed the found flow + the old combined draft +
  screen-architecture blueprint to Stitch; ask for the reconciled wizard
  (bring in cover preview, genre pills, word-count gauge where they add).
- State rounds: empty/loading/error/validation states for every wizard step,
  dark variants, FR added to the drafts' DE/EN language switch (rule 5:
  three catalogs).
- Du-tone: have Stitch re-issue affected copy in du, or adapt during porting
  (layout unchanged) — porting-side adaptation is the default.
- Landing round: the "setup complete / returning user" state (owner decision)
  — the wizard's final destination and the root route for a set-up instance.
- Re-export corrected drafts into the archive, then the **owner checkpoint**:
  the owner reviews the harmonized drafts in Stitch; porting starts only
  after their OK (waivable).

### W2 — Welcome screen and setup assistant, everything real

One shipping milestone (the owner approved merging the former W2/W3): the
welcome screen and the wizard port together, and one E2E suite covers
welcome → full wizard → post-setup landing.

- Port "Willkommen im Atelier" (du-tone) with the three entry paths: wizard
  start (real), demo world (real), import (disabled + gap-doc entry until
  the import wave).
- Backend: `novels.target_words` (nullable int); author typology, dramatic
  form, AI role and canon strictness as per-novel settings (placement:
  novel-level columns or a `novel_settings` table — left to the plan; AI
  role should land where the prompts capability can read it); genre already
  exists on `Novel` and is wired through setup.
- Setup API: extend `POST /api/setup` to accept genre, target words,
  typology, form, AI role, canon strictness, demo choice (demo exists).
  Demo semantics per the owner decision above.
- Port steps 1–4: real demos in the cards (title/genre/blurb from the demo
  metadata; stat chips like entity counts render honestly from what the
  archive reports or neutral `—` — gap-doc entries until the knowledge
  capability supplies them), real fields, honest progress on step 4 derived
  from what setup actually created.
- Port the W1 landing draft as the minimal post-setup destination.
- E2E: welcome + full wizard + landing against real backend + DB;
  fake-provider rule unchanged.

### W3+ — Remaining screens

Bücherregal (drafts exist, incl. filter-open state) → Schreib-Workspace →
Knowledge/Planning/Chat/Settings → production/analysis screens. Same cycle
per screen: fetch → check → Stitch round on gaps → port → E2E. Import
studio (DOCX/Scrivener/ePub parsing on the existing interchange engine) and
dramaturgical template content (Hero's Journey etc.) are their own later
waves, real, not placeholders, per the owner's scope decision.

## Closing the frontend/E2E issues

Labels alone do not separate cleanly: capability areas (`area: writing`,
`area: settings`, …) mix UI issues with backend bugs, and `kind: test-gap`
also covers kernel/repository tests that survive. Mechanism:

1. Preselect by label: all `area: web`; every issue whose subject is an
   e2e/web test (`kind: test-gap`, `kind: flake` where the subject is an
   e2e or web suite); `follow-up-index` issues whose children all close.
2. Triage the preselection by subject: close what lives in deleted code;
   keep backend logic bugs (e.g. the merge deadlocks, the export backup
   strand, the cached passage search) and kernel/tooling/ci/docs issues —
   they survive the demolition. Keep infrastructure findings about the
   kept plumbing (e.g. the production build-files 404) open.
3. Close with a standard comment: closed by the frontend rebuild decision,
   the code it lived in is removed; reopen condition = the rebuilt screen
   reintroduces it. An index closes with its last child.
4. The wave index in `docs/superpowers/follow-ups.md` records the closure
   batch.

## Constraints (binding)

- The five standing rules (CONSTRAINTS.md), especially rule 2 (green E2E per
  capability) and rule 5 (en/de/fr catalogs, sorted, same keys, plural
  categories).
- The v2 architecture spec stays the structural authority: capability
  folders, `@shell/*` one-way imports, generated views, scoped repositories.
- Governance budget (spec §8): no new mandatory gate, registry or check
  script comes with this program.
- Frontend & UI work runs through subagents (one implementer + one reviewer
  per task, one whole-branch review), models per AGENTS.md standing
  preference rev. 5: UI Agent `opencode/deepseek-v4.1-flash-free`, Reviewer
  `zai-coding-plan/glm-5.3`, Coding Agent `zai-coding-plan/glm-5.3-flash`.
- Conventional commits; frontend deletion waves use hidden types
  (`chore`, `refactor`, `test`); user-visible ports use `feat(web)`/`fix(web)`
  with a real `User-visible:` line. Nothing is committed before review is
  green; PRs pushed per green task group.

## Risks

- **App unusable beyond setup for the program's duration** — accepted by the
  owner; the interim is a local build, not a release. One PR per wave;
  release-please release PRs stay unmerged until the program's end.
- **Generated views / shell routing with empty capability web folders** —
  W0 must solve compilation of `just check-generated`; unknown effort, to be
  scoped in the plan.
- **Draft HTML vs Tailwind v4 utilities** — drafts use CDN Tailwind with
  arbitrary values; porting maps them onto the token utilities in
  `globals.css`, which is porting, not redesign. Drift goes through the
  contrast/type gates the shell already has (`tokens.test.ts`).
- **Stitch MCP blind spot** — new screens may be invisible to `list_screens`;
  the export zip is the cross-check.
- **Fonts**: EB Garamond + Plus Jakarta Sans are already self-hosted; the
  drafts' occasional "Newsreader" mentions are drift — DESIGN.md tokens win.

## What is left to the builder/plan

- Exact demolition list (file-level) and the stub strategy for generated
  views and route mounting.
- Schema placement of the four wizard settings (columns vs table) and their
  service/repository seams, within the kernel contracts.
- The concrete close-list of the ~200 open issues (label preselect + subject
  triage) as a checklist in the W0 task.
- The du-tone copy catalogue keys and the i18n parity pass after the
  capability catalogs shrink.
