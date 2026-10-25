# WP0 — Documentation corrections after the frontend foundation

> **For agentic workers:** docs only. No code, no schema, no test changes. Twelve
> exact edits in three files, plus staging the two plan files (Task 4 is already
> applied — see there). Do not improvise wording; each replacement is quoted
> verbatim.

**Goal:** Make the two specs and `AGENTS.md` describe the tree as it is on
2026-10-25. The merge `17ebe4b2` built the frontend foundation, `kernel/jobs`, and
the knowledge depth; three documents still describe the tree before it.

**Why this is first:** the architecture spec is the stated authority. As long as it
says "TanStack Query never entered" and "kernel/jobs not built", an agent reading it
will hand-roll both. The failure is silent: a page under `web/routes/` still compiles
and is simply never mounted.

## Hard constraints

- Touch only the five paths in Task 13. Nothing else.
- No new rule, registry, gate, hook or mandatory document.
- No `just generate`: no OpenAPI, route or catalog changed.
- No `--no-verify`, no force push.
- English in every edited document.
- If any "OLD" block below does not match the file byte-for-byte, stop and report
  `BLOCKED` with the file and line. Do not paraphrase a near-match.

## Expected tree state before starting

`git status --porcelain` shows exactly two untracked files and nothing else:

```
?? docs/superpowers/plans/2026-10-25-v2-foundation.md
?? docs/superpowers/plans/2026-10-25-wp0-docs-corrections.md
```

Record `git rev-parse HEAD` as the base. Anything else dirty: stop.

---

## Task 1 — Architecture spec §13, the Query row

File: `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`

OLD:
```
| pgvector, Alembic, TanStack Query | same prove-it test, at first use; all three are expected to pass, none is exempt |
```

NEW:
```
| pgvector, Alembic, TanStack Query | **resolved 2026-10-25**: pgvector kept; Alembic removed (no migrations until go-live); TanStack Query entered with the frontend foundation |
```

## Task 2 — Architecture spec §13, the jobs row

OLD:
```
| `kernel/jobs` table and the single worker (§9 D10) | the first capability whose side effect must outlive its request — none exists today |
```

NEW:
```
| `kernel/jobs` table and the single worker (§9 D10) | **resolved 2026-10-25**: built with the knowledge phase; extraction and the whole-novel check run on it |
```

## Task 3 — Architecture spec §14, the section date

OLD:
```
## 14. As built, 2026-10-22
```

NEW:
```
## 14. As built, 2026-10-25
```

## Task 4 — Architecture spec §14, the frontend bullet

OLD:
```
- **A capability's frontend lives in `web/routes/<name>.tsx`, not in its
  folder.** A feature costs its backend folder, one route file, and one key in
  each of the three i18n catalogs. The generated route table (§3) is not
  built: listing the routes by hand in `web/router.tsx` is a few lines, and a
  generated view of them would have no second consumer; it returns when
  capabilities own many routes of their own.
```

NEW:
```
- **A capability's frontend lives in its own folder, under `web/`.**
  `web/router.tsx` mounts only the generated route table
  (`web/lib/generated/routes.ts`), built by `scripts/generate_capabilities.py`
  from every `app/capabilities/*/web/routes.tsx`; a capability that exports
  `dockRoutes` also appears in the generated dock registry. Capabilities import
  the shell through the one-way `@shell` alias and never each other; the
  generated table is the single composition point. Component tests live beside
  their components in the capability folder. A new route is a `routes.tsx`
  change plus `just generate`.
```

**Applied 2026-10-25 in `53d87beb` — skip this task.** The bullet now reads
exactly as NEW above; it landed together with §3's shell wording, §4's
composition sentence and §3's tree line. The OLD block is gone, so re-running
this task would have nothing to match.

## Task 5 — Architecture spec §14, the jobs bullet

OLD:
```
- **`kernel/jobs`, `kernel/events` and `kernel/prompts` are not built.** No
  feature needs background work yet, so standing rule 3 holds trivially; the
  jobs table and worker arrive with the first capability that needs them (§13).
  Prompts live in the two capabilities that have them, joined only by
  `SOURCE_PREFIX` in the provider contract.
```

NEW:
```
- **`kernel/jobs` is built; `kernel/events` and `kernel/prompts` are not.**
  The knowledge phase needed durable work (extraction, the whole-novel check),
  so the table, the single worker and the stale-row sweep landed there (§13).
  Prompts still live in the capabilities that own them, joined only by the
  `SOURCE_PREFIX` and `PURPOSE_PREFIX` markers in the provider contract; a
  prompt registry arrives with the override system.
```

## Task 6 — Architecture spec §14, the prove-it bullet

OLD:
```
- **Prove-it outcomes:** pydantic-ai removed (a streaming completion over a
  fixed prompt needs one async method), mem0 removed (pgvector plus
  `kernel/retrieval.py` covers the ground), pgvector kept, Alembic removed
  (§6). TanStack Query never entered: the generated client was enough.
```

NEW:
```
- **Prove-it outcomes:** pydantic-ai removed (a streaming completion over a
  fixed prompt needs one async method), mem0 removed (pgvector plus
  `kernel/retrieval.py` covers the ground), pgvector kept, Alembic removed
  (§6). TanStack Query entered with the frontend foundation: multi-surface
  invalidation and job polling were the hand cache the generated client alone
  could not replace.
```

## Task 7 — Architecture spec §14, the CI counts

OLD:
```
  every job through one guard. 9 tests, ~29 s at five capabilities.
```

NEW:
```
  every job through one guard.
```

## Task 8 — Architecture spec §8, the reopen procedure

Insert a new paragraph between the governance-budget blockquote (ends
`deleted when they serve no purpose.`) and the sentence `Enforcement is social, not
technical.` Keep one blank line on each side.

INSERT:
```
The architecture is a decision, not a law. Any boundary may be proposed for
reopening with the same three statements: the failure it prevents, the effort it
creates, the cheaper alternative. Crossing a boundary — a capability importing
another, a second data store, a global store, a migration tool — needs the product
owner's explicit approval and is recorded as a dated decision. Until then, the
boundary stands.
```

## Task 9 — Frontend spec §5.3, the palette status

File: `docs/superpowers/specs/2026-10-22-frontend-design.md`

OLD:
```
- **Keyboard contract:** Tab accepts ghost text, Esc discards it, F9 focuses,
  ⌘K opens the palette (entity search, commands, chapter jump). The mouse is
  never required.
```

NEW:
```
- **Keyboard contract:** Tab accepts ghost text, Esc discards it, F9 focuses,
  ⌘K opens the palette (entity search, commands, chapter jump). The palette is
  the one part not built; it lands with the coherence phase, and until then
  chapter and entity navigation have a pointer path only.
```

## Task 10 — Frontend spec, a new §5.12 for settings

Insert before the line `## 6. Phasing (input for the implementation plan)`, with one
blank line on each side.

INSERT:
```
### 5.12 Settings (`/settings`)

Settings becomes a destination of its own: `settings/web/routes.tsx` mounts
`/settings`, and the top bar's gear links to it (`nav: false` — it is a control,
not a browsing destination). Sections: language, providers, prompts. It stays a
capability (its HTTP surface already is), so the generated route table and the
one-way `@shell` import need no exception.
```

## Task 11 — Frontend spec §7, the phone

OLD:
```
- **Desktop-first.** Small viewports: panels become overlays; the phone is
  not a target.
```

NEW:
```
- **Desktop-first.** The phone is not a design target: no mobile layouts, no
  touch gestures. Every page must still not overflow horizontally at 360 px, and
  panels become overlays there. Checked by eye, not by a gate.
```

## Task 12 — AGENTS.md

File: `AGENTS.md`

OLD:
```
- One capability is one folder under `app/capabilities/<name>/`. A capability never
  imports another capability; shared domain lives in `app/kernel/`.
```

NEW:
```
- One capability is one folder under `app/capabilities/<name>/`, including its
  frontend under `web/`; routes are generated, so a new one needs `just generate`.
  A capability never imports another capability; shared domain lives in
  `app/kernel/`, shared UI in the shell.
```

Then append one bullet to the same `## Rules` list, directly after the
`Never add a rule, …` bullet:

```
- A boundary can be reopened. The spec's §8 names the procedure: three statements
  and the product owner's explicit approval.
```

## Task 13 — Stage the two plan files

```
git add docs/superpowers/plans/2026-10-25-v2-foundation.md
git add docs/superpowers/plans/2026-10-25-wp0-docs-corrections.md
```

They are part of this commit: the foundation plan moved into the repo, and this
brief is its WP0 slice.

---

## Verify (read every output)

1. No stale claim survives. The plans under `docs/` are excluded: this brief
   quotes the old wording in its own OLD blocks, so an unglobbed sweep matches
   itself and can never come back clean.

   ```
   rg -n "web/routes/<name>|TanStack Query never entered|9 tests, ~29 s|Desktop-first\.\*\* Small" docs AGENTS.md --glob '!docs/superpowers/plans/**'
   ```

   Expected: no matches.

2. No stale jobs claim. Same exclusion, same reason — Task 5's OLD block is in
   this file.

   ```
   rg -n "kernel/jobs.*not built|not built.*kernel/jobs" docs AGENTS.md --glob '!docs/superpowers/plans/**'
   ```

   Expected: no matches.

3. The new facts are present, once each where they should be:

   ```
   rg -c "resolved 2026-10-25" docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md
   rg -n "As built, 2026-10-25" docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md
   rg -n "5.12 Settings" docs/superpowers/specs/2026-10-22-frontend-design.md
   rg -n "A boundary can be reopened" AGENTS.md
   rg -n "under \`web/\`; routes are generated" AGENTS.md
   ```

   Expected: `2`, one line, one line, one line, one line.

4. The diff touches exactly five files:

   ```
   git diff --stat HEAD
   ```

   Expected paths: the architecture spec, the frontend spec, `AGENTS.md`, and the two
   plan files. Anything else is a deviation.

5. `just check` — run it and read the output. It does not cover markdown, but the
   gate is the gate; a failure means the tree was not clean to begin with.

## Commit

```
docs(spec): the as-built state after the frontend foundation

The architecture spec's §14 still described the pre-merge tree: the frontend in
web/routes, TanStack Query never entered, kernel/jobs not built. Merge 17ebe4b2
built all three. This records the tree as it is on 2026-10-25.

- §13: TanStack Query and kernel/jobs move from open to decided.
- §14: frontend location, jobs, prove-it outcomes, CI counts.
- §8: the reopen procedure (three statements + owner approval).
- frontend spec: palette status, /settings as a route, phone wording.
- AGENTS.md: the capability folder includes web/; the reopen pointer.
- docs/superpowers/plans/: the foundation plan and this brief move into the repo.
```

## Report

Terse, pipe-delimited, English, nothing else:

```
status: DONE|BLOCKED
files: <staged paths>
ledger: <n>/13 tasks, one token each>
verify: <rg counts, diff --stat, just check result>
deviations: none | <what and why>
concerns: none | <what>
```

## Dispatch

Launch with `background: true`. Write the returned session id and the base commit to
`.opencode/dispatches/wp0-docs.progress` in the same turn, with the current task
number and the next verify command. If the provider kills the dispatch: read
`git log --oneline <base>..HEAD` and `git status --porcelain` before deciding
anything; commits or edits present means resume the same session, not reset.
