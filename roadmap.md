# Roadmap

Where Narrare is, what "finished" means for it, and in which order the rest happens.
Written for two readers: someone deciding whether to follow or contribute, and the
owner deciding what comes next. It is a plan, not a promise — dates are deliberately
absent, and every phase names the condition that lets it start.

The inventory behind it is [`docs/features/INDEX.md`](docs/features/INDEX.md): one row
per feature, with its current state. When the two disagree, the inventory is right and
this page is stale; fix it in the same change.

## What Narrare is

A local-first writing studio. You write in scenes, the AI knows your book's canon
because the canon lives in the same app, and the model is the only part that leaves
your machine. The architecture is in
[`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`](docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md).

## Where it stands

Four surfaces are real, with a backend and a browser test behind each: the shelf,
welcome and setup, the scene-centric workspace, and knowledge (dock, graph, dossiers,
sources). Planning is landing: the chronology is merged, the storyboard is in review,
the causality strip is still open, and the capability's E2E suite is owed by the last
of the three. Two more have a complete backend and no surface at all: settings and
prompts. Chat answers a single question and does not remember it. Everything else —
analysis, revision, import and export, production, series, notes, mobile — has
designs, and no code.

That is the honest baseline: the rebuild replaced the frontend of what existed, and
added the scene model underneath it. It did not add whole feature families.
**Feature completeness is therefore mostly backend work**, not interface work, and the
order below follows the contracts, not the drafts.

## What "feature complete" means

1. **Parity first.** Writing, knowledge, chat and setup do what v1 did — with a
   surface, a backend, and an end-to-end test for each.
2. **Every drafted area has a verdict.** A Stitch draft is a proposal, never a scope
   decision. Each area is decided once: build, later, or drop — with the reason and
   the condition that reopens it.
3. **No undrafted code.** Where Stitch is the only designer, a feature without a
   draft waits for one. Drafts are part of the critical path, not decoration.
4. **Done means done.** A feature counts when its surface, its backend, its E2E and
   its three language catalogs exist, and its remaining gaps are written down in a
   ledger — not when a screen renders.

Feature complete is end of Phase 3. A first public 1.0 is plausible at the end of
Phase 2; that is a quality decision, not a scope one.

## Phase 0 — Settle the record

**Now.** The rebuild's last tasks, and one honest inventory.

- Close W6: the storyboard PR, then the causality strip with its E2E and its gap
  ledger.
- Archive the v1 corpus; make the live inventory the single list.
- Decide what v1 never registered: audio dictation and the pocket app. The publishing
  area has its own open decision, below.

**Exit:** every feature appears once, with a state; no document claims a surface that
does not exist; no area is undecided by accident.

## Phase 1 — Finish the rebuild

**Backend already there; the surfaces are missing.** After this phase the app is
usable without touching an API or a `.env` file.

- **Settings.** The screen the gear opens: providers, keys, models, per-task
  assignment, token budgets, theme, language. Needs a prompt preview endpoint
  (what a prompt renders before it runs).
- **Prompts.** The override editor with its diff against the shipped prompt, from
  the 2026-11-15 drafts.
- **Assistant sessions.** A conversation that ends in a typed proposal the user
  accepts. Two waves on one substrate: the entity interview first (session
  tables, the interview prompt key, `POST /api/knowledge/entities`, the panel on
  the graph page), then the free chat with streaming and the prose sink in the
  workspace dock. The design is
  [`2026-11-20-assistant-sessions-design.md`](docs/superpowers/specs/2026-11-20-assistant-sessions-design.md).

**Not in this phase, though it looked like it:** the command palette and the help
centre. The palette draft is universal search — scenes, canon and events beside the
commands — and that needs a cross-capability search contract plus a command
registry. It is contract 2.9 below. The help centre has a content contract and no
renderer; it waits for the content.

**Design first:** the entity panel is drawn (drifted); the free chat and the prose
sink have no draft of their own. Each round is a task in its wave.

**Exit:** configure a model, run an interview that creates an entity, and edit the
interview's prompt — all in the UI.

## Phase 2 — Contracts

Each contract is one small wave with its own E2E. They come before the feature waves
because eleven analysis reports must not become eleven schemas.

| # | Contract | What it establishes | Unlocks |
|---|---|---|---|
| 2.1 | Uniform run | A run is a job with stored results, findings and one usage record; one query reads them | Analysis, planning AI, plot checks, title and name lists, prompt history |
| 2.2 | Proposal and diff | An AI change is a proposal with hunks; acceptance is explicit and per hunk | Rewrite, variants, inline suggestions, co-author, scene drafts |
| 2.3 | Voice profile | One profile shape for an author and for a character | Author voice, character voice, drift, voice check |
| 2.4 | Versions and comments | Append-only scene versions with diffs; comments anchored to a passage | Revision history, editorial comments |
| 2.5 | Interchange | DOCX, Scrivener and ePub in; PDF, ePub and DOCX out, downloaded from the browser | Import studio, export and typesetting |
| 2.6 | Series | A series owns canon and voice; volumes share them | Series architecture, cross-volume generation and drift |
| 2.7 | Notes | A scratchpad outside every novel | Notes |
| 2.8 | Stats and cost | Read endpoints over activity and the model-call audit | Writing stats, cost view |
| 2.9 | Command and search | Fill the generated command registry (it exists and is empty) from each capability's actions, and add one read endpoint that searches scenes, canon and events | The command palette, and every command-only action after it |
| 2.10 | Help content | A renderer over the per-capability help files that already exist, with coverage visible | The help centre |

**Exit:** every family below can be built as a variant of a contract, not as a new
subsystem.

## Phase 3 — Waves

Each wave is the house cycle: a Stitch harmonization round, a port, an E2E suite, a
gap ledger, one index of follow-ups.

1. **Assistant modes** — the entity interview's siblings: stub elaboration (the same
   mode, prefilled from the row), the novel interview, the scene and chapter
   brainstorm. Each is a prompt key, a slot list and a sink on the session
   substrate — which is why they come before the families that would otherwise
   each grow their own dialogue box.
2. **Analysis** — readability and coreference first (deterministic, no model), then
   beta reader, sentiment, POV, voice profiles and drift. The drafts exist for four
   screens; seven families still need one.
3. **Writing AI** — rewrite, new chapter, inline suggestions, unblock, co-author.
   Rides the proposal contract.
4. **Planning AI** — gap analysis, character arcs, scene drafts; the storyboard's
   remaining extras.
5. **Editing** — revision history and editorial comments. Rides the version model.
6. **Import, export, typesetting** — the studio the drafts draw, on the interchange
   contract.
7. **Production** — cover, blurb, marketing, exposé, agency. Only after the verdict:
   this is the area furthest from "a tool for writing".
8. **Series and stats** — the series canvas and the numbers.
9. **Pocket** — last, and deliberately: it is the only wave that needs a new
   foundation (auth, sync, offline) and that foundation decides the hosting model.

## Phase 4 — Release hardening

E2E for every capability, an accessibility sweep, the French catalogs, user
documentation and in-app help, a packaged install (not only a container image), and
the follow-up indices closed or consciously parked. The 108 open follow-ups are paid
inside the waves that own them; this phase is the remainder.

## Why this order

- **Settings before features.** Without it a writer cannot point the app at a real
  model after setup. Every later feature is unusable until this is fixed.
- **Chat before analysis.** It is core scope, and it is the host the sparring,
  dialogue coach and co-author surfaces will reuse.
- **Contracts before families.** The eleven analysis families share one shape; the
  writing features share one diff; the editing features share one version model.
  Building the shape once is what keeps each wave a folder plus a test.
- **Drafts before code.** Where Stitch is the designer, a wave without a harmonized
  draft is not ready — the round is a task in the wave, not a follow-up after it.
- **Pocket last.** It is the only area that forces the hosting and auth decision
  (spec §13), and that decision is expensive to reverse.

## Not planned

These are decisions, not omissions. Each returns only on its condition, recorded in
the inventory's "Decided not now" table.

MCP and A2A adapters (an external agent driving Narrare), the LLM wiki layer, editor
graphs, sensitivity review, the literary and plot suites, learning from accept/reject,
workflow scripting, shortcut remapping, external folder sync — and audio dictation,
which has a draft but was never registered as a feature.

## Design debt

What the roadmap waits for, and why it blocks.

| Area | Missing | Blocks |
|---|---|---|
| Chat | The entity panel's harmonization round (the draft carries invented scores and a graph preview); no draft for the free chat, the prose sink or the session list | Phase 1's assistant surface, and cut 2 |
| Analysis | A hub draft and seven families (emotional curve, readability, POV, coreference, author voice, character voice, drift) | Wave 3.2 |
| Editing | A harmonization round: real fields instead of mock ones, plus states | Wave 3.5 |
| Production | A verdict, then a harmonization round for the screens v1 never built | Wave 3.7 |
| Import | A verdict on audio dictation; states for the import studio | Wave 3.6 and one open decision |
| Stats | A cost and usage view | Contract 2.8 |
| Pocket | States, plus the auth and sync story | Wave 3.9 |
| Knowledge, planning | State sheets (empty, loading, error, many) | Later waves; row-level gaps carry the interim |

Dark mode needs no separate draft per screen: the shell's token ladder carries it, and
only a draft that claims its own colours gets one.

Every row the inventory marks `idea` has no draft at all. The table above names the
ones a planned wave cannot start without; the rest can wait without blocking anything.

## Open decisions

| Decision | Why it matters | Decides |
|---|---|---|
| Does Narrare ship publishing surfaces? | Production is the area furthest from writing; the criterion is whether it earns its permanent cost | Wave 3.7 |
| Is there a mobile app? | It forces auth and sync, and with them the hosting model | Wave 3.9 |
| Hosting: self-hosted single user or a service? | The tenancy seam exists, the answer does not; it decides auth | Before Wave 3.9, ideally before 1.0 |
| How deep is a series? | Shared canon across volumes is schema-heavy; a volume grouping is cheap | Contract 2.6 |
| Is a 1.0 allowed before feature completeness? | It changes what the next two phases optimise for | After Phase 2 |

## How this page stays true

A wave updates three things in the commit that closes it: the phase it finished, the
inventory rows it made real, and its gap ledger. A phase that grows is split into two,
never stretched. A phase that loses its reason is deleted, and the inventory says why.

Open findings are GitHub issues labelled `follow-up`, each under its wave's index;
[`docs/superpowers/follow-ups.md`](docs/superpowers/follow-ups.md) lists the indices.
They are the day-to-day work; this page is the shape it adds up to.
