# Follow-ups

Open findings are GitHub issues, one per finding, label `follow-up`:

    gh issue list --label follow-up --state open --limit 300

Each finding carries exactly one `area:` label (writing, knowledge, chat, settings,
setup, brand, kernel, web, tooling, ci, docs — where it lives) and, where its nature
is one, a `kind:` label (test-gap, docs-drift, flake, a11y, i18n, race, security);
`AGENTS.md` states the rule. Index issues carry neither.

Each wave's findings sit under an index issue that lists them. The index carries
`follow-up-index`, not `follow-up`, so the query above returns findings only, and an
index closes with its last child. Every open finding's body names the id it carried on
this page ("Formerly `F-46`"), so the plans and commit messages that cite an open id
still resolve; a closed id is in the table the Archive section points to.

| Findings from | Index |
|---|---|
| WP1 entity depth | #305 |
| WP2b context budget | #306 |
| WP3 markdown, demo, export | #307 |
| Reviews and audits outside a wave | #308 |
| WP4 prompt overrides | #375 |
| v2 foundation deferrals (§11) | #407 |
| WP5 UI coherence | #423 |
| Schema migrations | #487 |
| UI vocabulary purge (2026-10-31 plan) | #526 |
| Prose typography and UI surfaces (2026-11) | #587 |
| GitHub platform (2026-11-05) | #607 |
| WP6 chapter and novel management | #635 |
| Provider presets and model profiles (2026-11) | #732 |
| Literary Modernism shelf pilot (2026-11) | #780 |
| W0 frontend rebuild (2026-11-13) — closed the frontend/E2E batch: 123 issues (spec: `docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md`); the wave's own nine follow-ups hang under index #841 | #307, #487, #780, #815, #831 closed with their last children; #841 open with children #842–#850 |
| Shelf rebuild W3 (2026-11-15) — the shelf at `/` with everything real (plan: `docs/superpowers/plans/2026-11-15-shelf-rebuild-w3.md`; ledger: `docs/design/stitch/gaps/2026-11-15-shelf.md`, 27 rows); two owner decisions hang under index #861 | #862 landing fate, #863 hero quick menu |
| W2 welcome/setup rebuild (2026-11-14) — the procedural cover module's three findings were fixed in-wave (none deferred) | #855 open with children #856–#858 (all three close when the branch lands) |
| Frontend rebuild W4 (2026-11-16) — the scene-centric writing workspace, zen focus, book settings + series create, the goal setters and the dock close (spec: `docs/superpowers/specs/2026-11-16-frontend-rebuild-w4-design.md`, plan: `docs/superpowers/plans/2026-11-16-frontend-rebuild-w4.md`; ledger: `docs/design/stitch/gaps/2026-11-16-w4.md`, 24 rows). Five PRs: #888 drafts (+ #889 round-2 corrections), #894 scene model + workspace read, #897 editor, #901 continuation, PR5 zen + settings + fidelity gate. The round audit's owner decisions and the shelf-ledger handover closed in-wave | #865 open with children #866–#883 (gap rows, until their waves land), #896, #898–#900, #902, #903 (master frames), #905 (inheritance source, owner decision); #884–#887 closed (round-2 #889), #890–#893 closed from their port commits, #895 closed from `adaa4a4d` (rides PR5, closes on merge) |
| Knowledge rebuild W5 (2026-11-19) — the knowledge capability's four surfaces (dock, lore graph, dossiers, sources) on the complete existing backend (spec: `docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md`, plan: `docs/superpowers/plans/2026-11-19-knowledge-rebuild-w5.md`; SDD ledger: `.superpowers/sdd/2026-11-19-knowledge-rebuild-w5/progress.md`; gap ledger: `docs/design/stitch/gaps/2026-11-19-knowledge.md`, 12 rows). Three PRs: A dock, B graph+dossiers, C sources+E2E. Opened with Task 1 (dock scaffolding + findings) | #907 open with children #908 (zen guard test load flake), #910 (last-relation focus drop, a11y), #911 (TopBar mobile overflow, area: web), #914 (create-entity door), #915 (dossier profile areas), #916 (AI sparring), #917 (original-document view, a11y), #918 (re-embed door), #919 (shelf hero lore door, area: writing), #920 (INDEX.md dead path, docs-drift), #921 (job enqueue concurrency guard, race), #922 (surface scaffolding hook) |
| Planning rebuild W6 (2026-11-20) — the planning capability's three surfaces (Chronologie, Storyboard, Kausalitätsleiste) on the complete existing backend (spec: `docs/superpowers/specs/2026-11-20-planning-rebuild-w6-design.md`, plan: `docs/superpowers/plans/2026-11-20-planning-rebuild-w6.md`; SDD ledger: `.superpowers/sdd/2026-11-20-planning-rebuild-w6/progress.md`; gap ledger: `docs/design/stitch/gaps/2026-11-20-planning.md`, 22 rows). Three PRs: A opener + chronology, B storyboard + scene drill-in, C causality strip + E2E + ledger. Opened with Task 7 (the gap ledger) | #927 open with children #928 (route-leave dirty-copy loss, a11y), #929 (structures registry read endpoint), #930 (GET→PUT last-writer-wins window, race), #932 (remap-422 refusal face browser-unreachable, test-gap, area: web) |

A new wave opens its index and adds a row here. A fix closes its issue from the
commit that lands it: `Closes #<n>`. Nothing is dropped for being minor:
`severity: minor` is a defect the product survives, `severity: major` is one it
should not ship again.

## Decided not to act

The ten rows below are the set settled before this page became an index, and they are
frozen — not a place to file new decisions. A finding decided against today closes as
an issue carrying the condition that re-opens it. `Trigger` carries that condition for
these ten; re-open one as a new issue and leave its row alone.

| ID | Opened | Topic | Trigger | Where | Severity | Origin | Status |
|---|---|---|---|---|---|---|---|
| F-35 | 2026-10-26 | `str()` coercion of corrupt proposals | `None`-typed proposals coerce to "None"; unreachable because the parse refuses non-strings. Re-open only if parsing loosens. | `—` | minor | WP1 final review | parked |
| F-36 | 2026-10-26 | `IntegrityError` fallbacks mislabel non-unique | Deadlocks are not `IntegrityError`, so the fallback labels them as absence; unreachable today. Re-open if the error mapping changes. | `—` | minor | WP1 final review | parked |
| F-37 | 2026-10-26 | `_resolve_proposals` 500 on a corrupt row | Unreachable; the parse refuses the row first. Re-open if parsing loosens. | `—` | minor | WP1 final review | parked |
| F-38 | 2026-10-26 | `add_relation` and Accept discriminate one constraint differently | The two paths handle the same constraint differently. Re-open if a path with a free-text type appears. | `—` | minor | WP1 final review | parked |
| F-39 | 2026-10-26 | Fake candidate "Der" | Ruling-accepted fake output. Re-open only if fake behavior changes. | `—` | minor | WP1 final review | parked |
| F-40 | 2026-10-26 | `entityTypeLabel` shares the prototype slot | Unreachable because types are validated. Re-open if free-text types are allowed. | `—` | minor | WP1 final review | parked |
| F-41 | 2026-10-26 | Direct-API note `""` stored verbatim | Backend normalization is out of scope. Re-open if a new consumer normalizes notes. | `—` | minor | WP1 final review | parked |
| F-42 | 2026-10-26 | Relations key without `novelId` | Entity UUIDs are global and the server scopes reads. Re-open with a new consumer of the key. | `—` | minor | WP1 final review | parked |
| F-43 | 2026-10-26 | Missing relations pending state | Cosmetic; no spinner while relations load. Re-open if the load becomes user-visible. | `—` | minor | WP1 final review | parked |
| F-44 | 2026-10-26 | E2E does not pin announced-once, queue order, the eight-type filter or merge fold | Covered unit- and API-side; an E2E regression would be silent. Re-open when the E2E covers the extraction surface. | `—` | minor | WP1 final review | parked |

## Archive

Until 2026-10-29 this page carried every finding as a table: 101 rows. The 26
closed ones name their fix commit in `Status`; the 65 open ones became issues
#309 to #373. The table is this file one commit before the commit that replaced it:
`git show <sha>^:docs/superpowers/follow-ups.md`, where `git log --diff-filter=M --
docs/superpowers/follow-ups.md` names the candidates, newest first.
