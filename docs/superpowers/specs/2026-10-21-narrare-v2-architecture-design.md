# Narrare v2 — Architecture Design

> **Status:** Accepted — the authority for the v2 build (ADR-100); §14 records
> where the built system is simpler than this document describes
> **Type:** Design spec (decisions and consequences, not a rulebook)
> **Supersedes in scope:** the governance layer described in §2; ADR-025, ADR-037,
> ADR-038, ADR-045, ADR-097, ADR-098 lose their subject matter (see §11)
> **Implementation plan:** separate artefact, not this document
> **Baseline measured:** 2026-10-21, this worktree, re-counted from disk

---

## 1. Status, context, question

Narrare is not in production and has no real users. That fact removes every
constraint that normally favours incremental change: no compatibility surface, no
data to migrate, no dual maintenance, no strangler pattern. The new architecture is
built beside the old code, capabilities are ported one at a time, and the old
application is deleted at the end (§11, D16).

The question this document answers:

> Why is every feature expensive, and what removes that cost?

The measured answer has four parts, and each has a decision attached:

1. **Declaration spread.** One fact is written in many places by hand — providers
   were declared 15 times, one intent in 8 surfaces. → *Facts live in the capability
   folder, views are generated* (D2, §3, §4).
2. **Governance mass.** 100 ADRs, 43 hooks, 33 check scripts, 95 recipes, 17 CI
   jobs — a tax paid on every change, mostly catching what a compiler catches
   better. → *Governance budget with a proposal-only rule* (D8, §8).
3. **Scope.** Fifteen capability areas, half of them speculative. → *Four core
   capabilities now; everything else re-decided on merit later* (D4, §11).
4. **Verification that does not prove the product works.** → *A green E2E through
   the real UI is the definition of done* (D7, §7).

The document records decisions already taken after a long design dialogue. It does
not re-open them, and it is not a rulebook: the standing rules of the repository are
a separate, much smaller artefact (§8).

---

## 2. Measured baseline

All numbers below were counted in this worktree on 2026-10-21 unless marked
otherwise. Two numbers from the design dialogue had moved and are corrected here.

| Surface | Measured now | Dialogue value | Target |
|---|---|---|---|
| ADRs (`docs/architecture/decisions/*.md`, excl. index/template) | **100** | 100 | ≤ 15 |
| Architecture rules (`docs/_shared/CONSTRAINTS.md`) | **23 numbered, 27 IDs, 1,389 lines** | 23 / 1,389 | ≤ 5 |
| Pre-commit hook ids in `.pre-commit-config.yaml` | **43** | 43 | ≤ 10 (6 planned) |
| `scripts/check_*.py` | **33** | 33 | ≤ 3 |
| Source LOC (`.py/.ts/.tsx` under `apps/` + `packages/`, incl. tests) | **321,912** | 318k | — (not a target) |
| Documentation | **406 files / 160,689 lines** | 406 / 161k | editorial only |
| Intent declaration surfaces | **8** — cited from the 2026-10-19 throughput spec, *not re-counted* | 8 | 0 hand-edited |
| Provider declaration surfaces | **1 hand-edited** (`llm/_providers/catalog.yaml`) + 2 generated; was 15 | 15 → 1 | 1 catalog entry |
| `justfile` public recipes | **95** | 95 | 21 |
| CI jobs | **7 in `ci.yml` (5 gates + `changes` + `nightly-guard`) + `release-please`** | 7 | ≤ 7 (5 gates + 2 scheduling guards) |
| Hand-written TS API type modules (`packages/web/lib/api/*.ts`) | **64** | — | 0 |

Corrections and notes:

- **ADRs: 100, matching the dialogue.** The dialogue value was right; a broader count
  that included INDEX/TEMPLATE produced the wrong 102.
- **CI jobs: 7, not 17.** The v1 surface (17 jobs across 5 workflows) was deleted with
  the cutover. `ci.yml` held 7 jobs at the cutover — 5 functional gates (`lint-types`,
  `tests`, `e2e`, `build`, `coverage`) plus `changes` and `nightly-guard` — and
  `release-please` runs separately. Since 2026-10-25 it holds 6: `coverage` ran the
  same pytest suite as `tests` a second time on every `main` push, so its covered
  invocation moved into `tests` and runs only there. The target is therefore ≤ 7,
  with the two scheduling guards called out as non-gate jobs.
- **CI jobs: 7 again, not 6.** Since 2026-10-31 the E2E gate is a matrix of
  per-capability suites (job `e2e-suites`, each entry named `e2e (<capability>)`)
  plus an aggregator named `e2e` (the required check); the matrix is one job
  definition, so the workflow holds seven. The local gate runs the suites a change
  touches; `just verify all` runs every one.
- **Recipes: the target is 21, not 22.** The §6 list has 21 entries; the 22 that
  stood here and in §12 was a miscount, corrected 2026-10-22.
- **LOC: 322k, not 318k.** Measured over Python, TypeScript and TSX in `apps/` and
  `packages/`, tests included. The old value is stale, not wrong in method.
- **Provider surfaces: the 15 → 1 consolidation is already banked** (ADR-099). One
  hand-edited catalog feeds two generated artefacts (Python, TypeScript). WP2a
  replaced that file with per-user profiles and a vendored models.dev snapshot
  (ADR-102); the row records the surface as it stood on 2026-10-21. The design
  therefore treats provider declaration as solved and only generalises the pattern.
- **Intent surfaces: 8 is inherited, not verified today.** Marked *unverified*; the
  design removes the surfaces entirely, so the exact count does not change a decision.

The point of the table is not the absolute size. It is the ratio: roughly 1,600 lines
of architecture rules and 33 check scripts to protect a 322k-line codebase, while
the failures that actually reached users were integration failures the checks did not
model.

---

## 3. Target structure

```
app/
  kernel/
    db/          session factory, scoped repository base, schema from the models
    auth/        auth boundary interface + fixed local-user implementation
    jobs/        jobs table + the single worker
    contracts/   shared domain types: Novel, Chapter, Scene, User
    events/      post-response recording (usage, statistics, memory writes)
    llm/         provider profiles, vendored model catalog, audit, one chat adapter
    prompts/     composition primitives shared by capabilities
  capabilities/
    writing/          capability.yaml, prompts, router/service/repository, tests, web/, e2e/
    knowledge/        same shape
    chat/             same shape
    setup/            same shape
  api/           FastAPI app: mounts capability routers, emits OpenAPI
web/             shell: frame, root route, API client, i18n, primitives, generated tables
i18n/            message catalogs (en, de, fr); user docs are generated from here
app/generated/       capability registry (Python); web/lib/generated/ the TS views
docs/
  architecture/decisions/  ≤ 15 ADRs
  user/              generated user documentation (en, de, fr)
scripts/             generate · new-capability · export-openapi · secrets
```

The frontend has two homes, and the tree carries both. `web/` is the **shell**: the frame
every capability is mounted in — `main.tsx`, `router.tsx`, the root route, the shared
libraries in `lib/` (API client, i18n, announcements, autosave, the proposal bus), the
React-Aria primitives in `ui/` (the only React-Aria import point) and the generated
composition tables. `app/capabilities/<name>/web/` is that **capability's own UI**: its
pages, its components and the `routes.tsx` it exports. The shell imports a capability's
components through the generated route table, so the frontend of a capability still
lives in that capability's folder; a capability imports the shell through the `@shell/*`
alias and never another capability, and the shell reaches capability code only through
the generated tables.

Two rules make this tree do work. **Dependencies point one way**: `api/ → capabilities/
→ kernel/`. A capability never imports another capability. **There is no central
registry**: the four capability folders and the files under `app/generated/` and
`web/lib/generated/` are the only places a capability is named.

`kernel/` holds what two or more capabilities need. Today that is a short list —
novel, chapter, scene, user, sessions, jobs, events, provider routing, prompt
composition. Anything else belongs in the capability that uses it.

---

## 4. The capability contract

A capability is one folder. Nothing outside that folder is edited to add it.

A folder contains: its `capability.yaml` facts file; the prompt text it owns; a
router that delegates immediately, a service that holds the logic, and a repository
that owns its tables; its schemas; its tests; and an `e2e/` spec that drives the real
UI (§7). Its frontend lives in a subfolder of the same capability folder and is
composed into the shell by the generated route table.

`capability.yaml` holds facts only: `id`, `title` (a user-visible label key),
`path`, `needs` and `nav`. It has no behaviour, no
schema, no prompt body. Its fields exist because at least two generated views read
them; a field nobody reads is deleted.

The generator aggregates all capability files into views that are never hand-edited:
the Python registry, the TypeScript views, the docs index, and the typed web client.
Generated files carry a
"DO NOT EDIT" header and a named source. Where a view is simply derivable from
OpenAPI, there is no capability field for it at all.

New capability: one folder, its facts file, prompt, code, tests, `e2e/`. New
provider: one profile row in `/settings`, plus an adapter and one `PROFILE_KINDS`
value only if it is a new API shape (ADR-102).
New capability *field*: a change to the generator and every reading view — which is
why fields are added rarely and removed readily.

---

## 5. Knowledge model

Four kinds of knowledge, each in exactly one place, each written at the moment it
changes.

**Product text** — labels, tooltips, hints, errors — lives in the i18n catalog and is
rendered by the UI. A missing key is a type or build error, not the job of a check
script, so the locale-sync checker has nothing left to verify.

**User documentation** is generated from that catalog for short texts, with editorial
long-form kept in one location. There is no per-feature mandatory document and no
status history.

**Developer knowledge** is colocated with the code it describes, so it appears in the
same diff as the change it explains. A note about the job worker sits in `kernel/jobs/`.
Architecture prose that spans modules is the only thing that lives centrally.

**Decisions** are ADRs, and only for irreversible or expensive-to-reverse choices.
Target ≤ 15, not 100. Reversible choices are made and recorded in the diff.

Languages: source code and documentation in English; user-facing text and user
documentation in **en, de, fr**.

Consequence: reviewing a change means reading its diff, not cross-checking it against
four documents that were updated separately.

---

## 6. Gates and their justification

The governing principle: **a gate survives only if the compiler cannot catch the
failure and the failure has actually happened.** Everything else is deleted, and new
gates fall under §8.

**Local — pre-commit, target under 10 s, four hooks:** format, lint, typecheck of
changed files, secrets. Format and lint work on changed files only; the typecheck is
scoped to changed paths.

**Local — pre-push, target under 60 s, two hooks:** full typecheck, unit tests.

**CI — seven job definitions:** five functional gates (`lint-types`; `tests`, which
also uploads the coverage on a `main` push; `e2e-suites`, the per-capability
matrix, each entry named `e2e (<capability>)`; `e2e`, the aggregator behind which
the required check keeps its name; `build`) plus `changes` (range narrowing: a PR
against where it branched, a push to `main` answers none) and `nightly-guard`
(skip on unchanged `main`). The matrix runs the affected capabilities on a PR; a
push to `main` owes no E2E, because the merge tree is the tree the PR tested and a
direct push is covered by the nightly; the nightly runs every capability.
`release-please` runs separately. The wall clock is the longest capability suite —
the suites run side by side, the aggregator waits on them in seconds.

**`justfile` keeps 21 public recipes:**

```text
dev, dev-api, dev-web, dev-services, dev-services-stop, dev-setup,
check, verify, lint, typecheck, format,
test, test-file, test-e2e, test-frontend,
build, db-init, db-reset, db-shell,
generate, new-capability
```

`check` is the fast gate on changed files; `verify` is the full gate and composes it.
`test-file` runs one file, because that is the loop a developer lives in.
`db-init` creates the schema directly from the models — there are no migrations
while the product is not live; a schema change lands in the models and the
database is recreated.

Removed: eval-nightly, mutation-testing, warnings-summary, budget-report, the
architecture CI job, and the changes-detection maze. The second typechecker (pyrefly)
is removed; one typechecker, one answer. VRT and golden-baseline machinery is removed —
visual similarity to a baseline nobody reviews does not catch a product defect.
Kept: release-please, CHANGELOG, coverage badge.

Consequence: a developer can run the full local gate in under a minute and a half, and
every remaining gate names a failure that has occurred.

---

## 7. E2E defines "done"

A capability is done when its `e2e/` spec drives the **real UI** against the **real
backend and real database** and is green. Unit and integration tests support that
claim; they never replace it.

**The only fake sits at the outermost boundary: the LLM provider** — and any other
external, paid or non-deterministic service. The fake provider is a provider profile
of kind `fake` with the same interface as the real ones, so routing, prompt
composition, streaming and persistence all execute the production code path. Choosing
it is a configuration value, not a test branch.

**No internal mocks.** Services, repositories, prompt builders and routers are never
mocked. A test that needs a fake repository is testing the wrong layer.

Preconditions — a user, a novel, a chapter — may be prepared directly. The tested
flow itself runs through the UI: click, type, stream, observe the result that was
persisted.

Scheduling: locally the gate runs the suites a change touches — affected by
default, `all` on demand. On each PR the affected capabilities run in parallel
per capability behind one `e2e` check; a push to `main` owes nothing, because the
merge tree is the tree the PR tested; all of them nightly. A real
LLM provider is never used at any test level. Anything a test would pay for is faked
at the boundary.

Consequence: an E2E failure means the product is broken, not that a schema changed.
The suite is the only place where "works" has a definition.

---

## 8. Governance budget

Binding, quoted verbatim:

> **Governance budget.** New rules, registries, check scripts, hooks, required fields or mandatory documents are forbidden by default. An agent may only *propose* them, never implement them, and only with three statements: (1) which concrete failure it prevents, (2) what effort it creates for **every** future change, (3) which cheaper alternative exists (types, generation, colocation). Implementation only after explicit approval by the product owner. Existing rules are judged by the same standard and deleted when they serve no purpose.

The architecture is a decision, not a law. Any boundary may be proposed for
reopening with the same three statements: the failure it prevents, the effort it
creates, the cheaper alternative. Crossing a boundary — a capability importing
another, a second data store, a global store, a migration tool — needs the product
owner's explicit approval and is recorded as a dated decision. Until then, the
boundary stands.

Enforcement is social, not technical. An agent that believes a new gate is needed
stops and reports `NEEDS-APPROVAL` with the three statements, and builds nothing.
There is no checker that enforces the governance budget — that would be the failure
mode it prevents.

End-state targets: **rules ≤ 5, ADRs ≤ 15, hooks ≤ 10, check scripts ≤ 3** (only what
the compiler cannot do: secrets and licences), and **no mandatory per-feature
documents**.

The 16 decisions in this document are one-time architecture decisions, not standing
rules. The standing rules are the ≤ 5 that survive in `docs/_shared/CONSTRAINTS.md`.

---

## 9. Tenancy, auth, jobs, database

**Tenancy seam now, auth mechanism later (D9).** There is a 75 % likelihood that
Narrare will be hosted, so every user-owned row carries `user_id` from day one and all
data access goes through one scoped repository base. The auth boundary exists as a
single kernel interface with a fixed local-user implementation behind it. Login,
password reset, roles, invitations and hosting operations are deferred until the
operating model is decided.

The cost asymmetry is the whole argument: **the tenancy seam is cheap now and
expensive to retrofit across fifteen capabilities later; the auth mechanism is
additive whenever it arrives.** Adding `user_id` to a schema under construction costs
one column. Adding it later costs a migration, a repository rewrite and a query audit
in every capability.

**Jobs in Postgres (D10).** A `jobs` table with status, user, progress, error and retry
count; one worker claiming rows with `FOR UPDATE SKIP LOCKED`. No broker, no Redis, no
RabbitMQ. Jobs survive restarts, and the worker hides behind an interface so it can be
swapped if throughput ever demands it.

**Database (D11).** One schema, one source: the models. While the product is not live
there are no migrations — `db-init` creates the schema directly from the models, and a
schema change lands in the models and recreates the database. When the product goes
live, this is where a migration story would begin, not before.

**Side effects never in the request path (D14).** Usage, statistics and memory writes
are recorded after the response, through the jobs table where durability matters. The
measured example: a per-chapter statistics recorder added roughly two seconds to every
create in the current code. The response returns when the user's data is safe, not
when the bookkeeping is.

---

## 10. Generated client and cross-capability rule

**The TypeScript API client and its types are generated from the OpenAPI schema
(D12).** There are no hand-maintained `lib/api/*.ts` type declarations — 64 such
modules exist today, and hand-editing them is how the frontend and backend drifted.

**Capabilities do not import each other (D13).** Anything two capabilities need — novel,
chapter, scene, user — lives in the kernel and exists once. A capability folder is
self-contained: it can be read, changed, tested and deleted without opening another
capability.

Consequence: the import graph stays a tree, the shared domain vocabulary is small and
explicit, and deleting a capability in a later round removes exactly one folder.

---

## 11. Deletion list and cutover

**Core scope for the new build (D4):** writing (novel, chapter, editor), knowledge
base, chat, setup.

**Not ported, and why.** Each of these is a standing obligation whose value has not
been demonstrated on a working kernel:

| Area | Why it is not ported now |
|---|---|
| analytics, statistics, budgets | reporting on writing that does not yet exist |
| series, volumes | structural complexity before the single-novel path is proven |
| notes, wiki, evidence | knowledge surfaces the KB may subsume |
| consistency checking | an LLM feature whose product value is unmeasured |
| adaptive, coaching | a second behaviour on top of an unproven first |
| events, metrics | observability for a system with no users |
| templates, prompt customisation | configuration before the prompts are stable |
| importing/export | data movement for data that does not exist |
| advanced auth | deferred with the hosting model (§9) |

Each returns only after the kernel works, one area at a time, on the criterion: **does
this feature earn the effort it permanently creates?** That question is asked in the
same form for every candidate, and a "later" answer is a decision, not a backlog item.

Also deleted outright, not deferred: the second typechecker, VRT/golden machinery,
and every gate listed in §6. Tests are not ported (D15) — each capability brings its
own, and only behaviour is tested, not the existence of wiring. No coverage threshold.

**The feature corpus is an input, not the scope.** `docs/features/` registers 92
features. On 2026-10-21 the index says 72 stable, 15 planned, 3 idea and 2
deprecated or retired — and the per-file status lines are free text, so the index is
the only consistent source. That status is a claim, not evidence. The port scope is
behaviour that exists, is reachable through the UI and has a runnable path in the old
code; every registered feature inside a core area is therefore triaged once — doc
status, code evidence (router, service, exercised path), verdict — and only a `port`
verdict enters the build. Exactly three registered features in the four core areas
were never built: WRITE-008 (multi-draft generation), WRITE-013 (writing workflows)
and KB-010 (editor-integrated knowledge graph). They are parked with the other
unbuilt candidates, never ported silently. The feature files themselves are not
migrated into a capability: a capability's user-visible documentation is generated
(D5), and `docs/features/` stays in the tree as the v1 product history, explicitly
non-binding — its `INDEX.md` says so.

**Cutover (D16).** The old application stays runnable until the last core capability is
ported, then is deleted in one change. Work happens on a dedicated branch and worktree;
git history is the archive of the old system, so no compatibility shim, no feature
flag, no dual-write and no legacy adapter is written at any point.

---

## 12. Success criteria

The design succeeds when all of these are true, and they are checked by doing the work,
not by a document:

1. **Adding a capability touches only its folder** plus generated output. A reviewer
   can confirm this from the diff alone.
2. **Adding a provider is one profile row** — and an adapter only for a new API
   shape.
3. **A capability is done only with a green E2E** through the real UI, real backend and
   real database, with the fake provider at the boundary.
4. **The §2 numbers reach their targets**: ADRs ≤ 15, rules ≤ 5, hooks ≤ 10, check
   scripts ≤ 3, recipes 21, CI jobs ≤ 7 (5 gates + 2 scheduling guards), zero hand-written API type modules.
5. **The local gate runs in under 10 s and under 60 s**, and a capability port is a
   folder plus a test, not a tour of the repository.

---

## 13. Open decisions

| Decision | Trigger that resolves it |
|---|---|
| Hosting model: self-hosted single-tenant vs multi-tenant service | early in the build, before the auth UI is designed; the tenancy seam (§9) is already in place either way |
| Auth mechanism (sessions, OIDC, magic link) | after the hosting model — it follows from single- vs multi-tenant, not the reverse |
| pydantic-ai: keep or replace | prove-it list (D3): name the effort it saves against a thin client over the provider interfaces; outcome recorded in the kernel PR that first needs agent orchestration |
| mem0: keep or replace | prove-it test during the knowledge-base port; if pgvector plus a small retrieval layer covers the same ground, mem0 goes |
| pgvector, Alembic, TanStack Query | **resolved 2026-10-25**: pgvector kept; Alembic removed (no migrations until go-live); TanStack Query entered with the frontend foundation |
| Capability inventory for the port and its order | the implementation plan, separate artefact — deliberately not fixed here |
| Migration story (Alembic or equivalent) | going live with a user's data — until then the models are the schema (§6, §9 D11; `app/kernel/db/init.py` carries the ruling) |
| `kernel/jobs` table and the single worker (§9 D10) | **resolved 2026-10-25**: built with the knowledge phase; extraction and the whole-novel check run on it |

The prove-it test is a written sentence in the PR that introduces the dependency, not
a document: *what it saves, what it costs, what smaller thing would replace it.* A
dependency that cannot answer is removed.

---

## 14. As built, 2026-10-25

The five capabilities — writing, knowledge, chat, setup, settings — are built.
These are the places the code is simpler than §3–§6 describe, recorded here so
the authority and the tree cannot disagree silently. Each entry names the
trigger that would build the missing piece.

- **Registration is by convention, mounting by folder; the facts live in
  `capability.yaml`.** `app/api/main.py` mounts every
  `app/capabilities/<name>/router.py` it finds and cross-checks, at startup,
  that the generated registry (`app/generated/capabilities.py`) names exactly
  those capabilities — a router without a facts file stops the boot. Three
  views are generated, none hand-edited: the Python registry, the TypeScript
  nav data (`web/lib/generated/capabilities.ts`, rendered by the home page,
  title keys checked against the i18n catalog by the compiler) and
  `docs/user/INDEX.md`. Fields, each read by at least two views: `id`,
  `title`, `path`, `needs`, `nav`. A new capability is one folder plus
  `just generate`.
- **A capability's frontend lives in its own folder, under `web/`.**
  `web/router.tsx` mounts only the generated route table
  (`web/lib/generated/routes.ts`), built by `scripts/generate_capabilities.py`
  from every `app/capabilities/*/web/routes.tsx`; a capability that exports
  `dockRoutes` also appears in the generated dock registry. Capabilities import
  the shell through the one-way `@shell` alias and never each other; the
  generated table is the single composition point. Component tests live beside
  their components in the capability folder. A new route is a `routes.tsx`
  change plus `just generate`.
- **`kernel/jobs` is built; `kernel/events` and `kernel/prompts` are not.**
  The knowledge phase needed durable work (extraction, the whole-novel check),
  so the table, the single worker and the stale-row sweep landed there (§13).
  Prompts still live in the capabilities that own them, joined only by the
  `SOURCE_PREFIX` and `PURPOSE_PREFIX` markers in the provider contract; a
  prompt registry arrives with the override system.
- **Prove-it outcomes:** pydantic-ai removed (a streaming completion over a
  fixed prompt needs one async method), mem0 removed (pgvector plus
  `kernel/retrieval.py` covers the ground), pgvector kept, Alembic removed
  (§6). TanStack Query entered with the frontend foundation: multi-surface
  invalidation and job polling were the hand cache the generated client alone
  could not replace.
- **CI runs the E2E of the affected capabilities on each PR, in parallel per
  capability behind one `e2e` check; a push to `main` owes nothing; all of them
  nightly (§6):** a `changes` job narrows a PR to the capabilities
  it touched — everything when kernel, api, the generated views, web, i18n or
  the tooling moved — so a documentation-only change runs no browser, and the
  merge tree a push lands is the tree the PR already tested. The nightly runs
  only when `main`
  carries a commit the last successful nightly did not test; an unchanged `main`
  skips every job through one guard, and a direct push to `main` is covered by it.
- **Recipes: 21** — the count §6 lists; the earlier 22 in §2 and §12 was a
  miscount (see §2's corrections).
- **The web shell is a Vite SPA, not Next.js.** Every page was a client
  component, so Next contributed a file router and a dev proxy while costing a
  third runtime in the packaging ladder (ADR-101) and a `next start` process in
  production. `just build` now emits `web/dist`, FastAPI serves it
  (`app/api/main.py`), and the routes are TanStack Router's — typed, so a `to=`
  naming no route is a build error. The TypeScript gate moved from `next build`
  to an explicit `tsc --noEmit` in `just typecheck`, keeping `just check`'s
  coverage unchanged. i18n stays framework-free JSON: the compiler, not a
  library, checks the catalogs.
- **Providers are data, not a catalog file (§4, §12.2).** Per-user
  `ProviderProfile` rows with per-task assignment, a vendored models.dev snapshot
  for prices and limits, and two key-storage tiers: OS keychain first, then
  Fernet under `NARRE_SECRET_KEY` (`app/kernel/secrets.py`). The audit names the
  profile and a real cost. The decision and its consequences are ADR-102.
