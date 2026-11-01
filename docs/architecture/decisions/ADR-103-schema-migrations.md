# ADR-103 — Schema migrations: Alembic with reviewed revisions, applied on startup

> **Status:** ✅ Accepted
> **Date:** 2026-10-31
> **Deciders:** Architecture Agent; the spec §8 boundary crossing ("a migration
> tool") approved by the product owner on 2026-10-30
> **Supersedes:** — (updates the stance of spec §9 D11, "no migrations while the
> product is not live", which was a spec decision, not an ADR)

---

## Context

The schema had one source and no history: the models registered on the `Base`
in `app/kernel/db/base.py` — the kernel modules `app/kernel/contracts/models.py`,
`app/kernel/jobs/models.py`, `app/kernel/llm/models.py` and
`app/kernel/prompts/models.py`, plus each capability's `models.py` — are the
single declaration, and `app/kernel/db/init.py` created the database with
`metadata.create_all`. `create_all` creates missing tables and never alters an
existing one, and the only way to apply a model change was `just db-reset` — drop the
database, recreate it. That is correct while nobody holds data, and wrong the moment
someone does: Narrare is local-first (ADR-101) and the user's own Postgres holds the
manuscripts. On the first installation that keeps prose, the schema was frozen — no
schema change could ever ship to it, except by discarding the manuscript.

Spec §8 names "a migration tool" as a boundary crossing needing the product owner's
explicit approval. The approval was given on 2026-10-30; the full design — approaches
weighed, decisions D1–D14, what was left to the builder — is
[`docs/superpowers/specs/2026-10-30-schema-migrations-design.md`](../../superpowers/specs/2026-10-30-schema-migrations-design.md).
This record states the decision and its cost.

---

## Decision Drivers

- "Safe" means four things: never lose prose · never leave a half-applied schema ·
  never let running code meet a schema it does not expect · every applied change
  reproducible from the repository.
- One declaration of the schema: the models. v2 exists to remove duplicated
  declarations; the migration tooling must not add a second one.
- The upgrade runs unattended, on application start, on a machine the app does not
  administer.
- Tests create the schema from the models per module; the gates must run inside the
  existing `just test` — no new CI job, no new gate recipe.
- The governance budget (spec §8): a boundary crossing is proposed with three
  statements — the failure it prevents, the effort per future change, the cheaper
  alternative. They are in Rationale below.

---

## Options Considered

### Option A — Alembic, revisions reviewed by a human

The models stay the single source. `just db-revision` drafts a revision from the
models with `autogenerate`; a person reads it and corrects what autogenerate cannot
know. Startup applies pending revisions.

**Pros:**
- The model change and the migration sit in one commit; no second declaration exists.
- Revisions are plain Python with full DDL reach; Postgres DDL is transactional, so
  crash safety comes nearly for free.

**Cons:**
- Every schema change costs a second, small artefact — the revision file — and a
  review of it.
- Alembic is blind to extensions, triggers and some index changes; a mechanical
  equality gate must cover what it cannot see.

### Option A′ — Alembic on autopilot (rejected inside A)

`autogenerate` as the authority: draft, apply, done. Rejected: it cannot tell a
rename (data moves) from a drop plus add (data is gone) — exactly the confusion that
eats prose.

### Option B — Declarative diffing (Atlas)

Desired state declared as SQL/HCL beside the models; the tool plans, lints and
detects drift.

**Pros:** drift detection against a declared state.

**Cons:** the schema is declared twice — the declaration spread v2 exists to remove —
plus a foreign binary in the distribution; data steps are awkward.

**Rejected.**

### Option C — SQL-first runner (dbmate, or ~150 lines of our own)

Ordered `.sql` files plus a version table.

**Pros:** no ORM coupling; the applied SQL is literally what is in the repo.

**Cons:** no draft from the models, so every change is written twice (models, SQL);
the advisory lock, backup and checksums become ours to build.

**Rejected.**

---

## Decision

**We choose Option A: Alembic, async, in the kernel — a baseline revision
(`b47f335cacca`) plus append-only history, applied on startup.**

> **2026-11-01 (CodeRabbit round 1):** the bootstrap compares an unversioned database
> against the *baseline revision's replayed schema* and stamps the baseline — the
> upgrade to head follows through the normal flow; a database equal to the models at
> head instead stamps head (fix round 2, same day).
> **2026-11-01 (CodeRabbit round 1):** constraint names are normalized to the naming
> convention (D9) at bootstrap — a pre-convention database's Postgres defaults are
> renamed, not held against the database.

`prepare_database()` (`app/kernel/db/migrate.py`) runs first in the lifespan
(`app/api/main.py`) and takes any database the app meets to head: advisory lock, so
two starts on that database cannot interleave (the lock is per-database, as a
server hosting several Narrare databases requires) → `ensure_extensions` (the three
extensions stay a separate idempotent pre-step) → a database with tables but no
`alembic_version` is **bootstrapped** — its constraint names are normalized to the
convention, then it is compared against the baseline revision's replayed schema
(equal → stamped at the baseline, the upgrade carrying it to head), else against
the models at head (equal → stamped at head), else **refused by name**
(`MigrationRefused`) *(update 2026-11-01, CodeRabbit round 1: the original
"compared against the models and stamped" described the one-revision history,
where baseline and head coincide; baseline first, models at head second)* → when
revisions are pending and the database holds tables, a restorable dump first
(an empty first boot takes none — product owner, 2026-10-31; design D5)
(`dump_database`, `app/kernel/db/backup.py`, into `NARRE_BACKUP_DIR`, last 3 kept,
command template `NARRE_BACKUP_COMMAND`) → `upgrade head` in one transaction → a
head check. A database ahead of the app's history is also refused. The development
recipes end in the same path (`app/kernel/db/init.py`), so there are two schema
paths and one gate that keeps them identical.

---

## Rationale

The three statements the governance budget (spec §8) requires for a boundary
crossing:

1. **The concrete failure it prevents:** an upgrade that could only reach an
   existing database by discarding it. `create_all` cannot alter a table; the only
   way an *alteration* reached an installed database was `just db-reset`, which
   destroys the manuscript. With a user's data in place, the schema was permanently
   frozen — the product could ship code but never schema.
2. **The effort it creates for every future change:** one reviewed revision file,
   authored beside the model change it migrates, plus the gates that already run in
   `just test` (`app/kernel/db/tests/test_migrations.py`). No new CI job, no new
   recipe beyond `db-revision` itself.
3. **The cheaper alternative considered and rejected:** none that keeps one
   declaration of the schema. Declarative diffing (Option B) is a second declaration
   behind a foreign binary; SQL-first (Option C) writes every change twice and gets
   no draft from the models. Both re-introduce the drift the single-model-source
   decision exists to prevent.

The shipped decisions, one line each — the design doc carries the reasoning:

| | Decision | Where it lives |
|---|---|---|
| D1 | Alembic, async `env.py`, URL from `NARRE_DATABASE_URL` only; capability models reach the migration environment through the generated registry | `alembic.ini`, `app/kernel/db/migrations/env.py` |
| D2 | The draft is a draft — a human reads it (renames, `postgresql_where`, `pgvector.sqlalchemy.Vector`) | CONTRIBUTING.md, "Changing the Schema" |
| D3 | Four gates inside `just test`: one head · empty→head equals the models · release snapshot upgrades with prose · bootstrap/refusal paths | `app/kernel/db/tests/test_migrations.py` |
| D4 | Bootstrap: equal → stamp, not equal → refuse and say what differs | `prepare_database` in `app/kernel/db/migrate.py` |
| D5 | Unattended upgrade on start: lock → dump when pending and tables exist — an empty first boot takes none (product owner, 2026-10-31) → one transaction → head check; every dump failure is a named refusal (`BackupFailed`) | `app/kernel/db/migrate.py`, `app/kernel/db/backup.py` |
| D6 | Never migrate backwards: ahead of head or unknown revision → refuse, name both versions | `prepare_database` in `app/kernel/db/migrate.py` |
| D7 | Extensions before revisions: `ensure_extensions` stays outside the revision history | `app/kernel/db/migrate.py` |
| D8 | Data moves are jobs, never revisions (a rule, not code) | stated here and in CONTRIBUTING.md |
| D9 | Naming convention on `Base.metadata` before the baseline, so every constraint has a droppable name | `app/kernel/db/base.py` |
| D10 | Expand/contract for prose tables: additive first, destructive later or with an explicit data move | stated here; discipline of each revision |
| D11 | One baseline (`b47f335cacca`), then append-only; squash allowed once, before 1.0 | `app/kernel/db/migrations/versions/` |
| D12 | Two schema paths (tests from models, `db-init`/`db-reset` via upgrade), one equality gate | `app/kernel/db/tests/test_migrations.py`, `app/kernel/db/init.py` |
| D13 | Recipes: `db-init`/`db-reset` upgrade; `just db-revision "message"` added | `justfile` |
| D14 | Documentation: this ADR and the CONTRIBUTING section; the CONSTRAINTS bullet names the approval instead of forbidding the tool | this file, CONTRIBUTING.md, `docs/_shared/CONSTRAINTS.md` |

---

## Consequences

**Positive:**
- A schema change reaches an installed database; the manuscript survives the
  upgrade, and the release-snapshot gate proves it on every `just test`.
- The history is replayable: two databases from the same release have provably the
  models' schema.
- A failed or interrupted upgrade leaves the database as it was — the upgrade's
  transaction rolls back — and a copy of the pre-upgrade state exists
  as a dump. Amended 2026-11-01 (CodeRabbit round 2): on an unversioned database
  the bootstrap's constraint renames and the baseline stamp commit before the
  upgrade and remain; the pre-upgrade dump is the restore point, and nothing
  automatically reverts the database as a whole.

**Negative / Tradeoffs:**
- Every schema change costs a second, small artefact — the revision file — and a
  review of it. There is no model-only schema change anymore.
- Startup grows: lock, dump, upgrade, verify run before the first worker or request.
- Downgrade is restore-from-backup, never a downgrade script: a downgraded app
  refuses a database ahead of its history. Honest limit: a
  `.dump` file is support-grade, not user self-service.

**Constraints introduced:**
- Data moves (backfills, re-embeddings) go through the `jobs` table, never through a
  revision (design D8).
- Destructive change on prose tables follows expand/contract (design D10).
- The CONSTRAINTS.md boundary bullet now names this ADR as the recorded approval
  instead of forbidding the tool.

---

## Implementation Notes

Everything below is shipped and checked by `just test`:

- `alembic.ini` — repo root; `sqlalchemy.url` stays empty, the URL comes from
  `NARRE_DATABASE_URL` only.
- `app/kernel/db/migrations/env.py` — async; imports the kernel model modules and
  every capability module named by `app/generated/capabilities.py`, so a new
  capability's tables are seen without a kernel→capability import.
- `app/kernel/db/migrations/versions/b47f335cacca_baseline.py` — the baseline.
- `app/kernel/db/migrate.py` — `prepare_database`, `ensure_extensions`,
  `head_revision`, `diff_against_models`, `current_revision`, `MigrationOutcome`,
  `MigrationRefused`.
- `app/kernel/db/backup.py` — `dump_database`, `backup_command` (the
  `NARRE_BACKUP_COMMAND` template taking `{url}` and `{file}`), `BackupFailed`;
  retention keeps the newest 3 in `NARRE_BACKUP_DIR` (default `./backups`,
  git-ignored; the settings in `.env.example`).
- `app/kernel/db/init.py` — `db-init`/`db-reset` end in `prepare_database`
  (backup off: development data is disposable — the dump exists to protect
  user prose).
- `app/api/main.py` — the lifespan calls `prepare_database` before configuration
  validation and the jobs worker.
- `app/kernel/db/tests/test_migrations.py` — the gates; the release snapshot is
  `app/kernel/db/tests/fixtures/schema_0.2.0.sql`, checked in.
- CI installs `postgresql-client-17` from PGDG in the existing tests job
  (`.github/workflows/ci.yml`) — the repository's own snapshot, restore and
  round-trip paths need a real `pg_dump`/`pg_restore`.
- The authoring flow is CONTRIBUTING.md → "Changing the Schema"; the recipe is
  `just db-revision "message"` (`justfile`).

**ADR status:** ✅ Accepted — the decision is in force; the boundary approval it
records was given on 2026-10-30.

---

## Review Trigger

*When should this decision be revisited?*

- [ ] When hosted operation changes the *discipline* of a revision (reviewed
      unattended upgrades on stranger's machines), not the tool
- [ ] When the equality gate (empty→head equals the models) first goes red, or
      replay exceeds ~5 s per conftest — the two-paths-one-gate tradeoff (design D12)
      is then re-judged
- [ ] Before 1.0, if the history is squashed into a new single baseline — allowed
      once (design D11); after 1.0 history is append-only and this ADR stops being
      editable in its revision-related claims
