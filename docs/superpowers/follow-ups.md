# Follow-ups

Open findings are GitHub issues, one per finding, label `follow-up`:

    gh issue list --label follow-up --state open --limit 300

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
| WP5 UI coherence | #423 |

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
