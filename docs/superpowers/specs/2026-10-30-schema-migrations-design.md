# Schema migrations for Narrare

**Status:** accepted — approved by the product owner on 2026-10-30; recorded in [ADR-103](../../architecture/decisions/ADR-103-schema-migrations.md)
**Date:** 2026-10-30
**Decision taken:** Alembic with human-reviewed revisions (approach 1 of three)
**Boundary:** this crosses spec §8 / §9 D11 ("no migration tool while the product is
not live"). The product owner approved the crossing on 2026-10-30, so it is recorded
as a dated decision and the spec's D11 sentence is updated with it. Nothing else in
the architecture changes.

---

## 1. Intent

The schema has one source and no history: `app/kernel/db/init.py` runs
`metadata.create_all`, `just db-reset` throws the development database away. That is
correct while nobody holds data. The product is local-first and the user's own
Postgres holds the manuscripts (README). The first installation that keeps prose ends
`db-reset`, and `create_all` cannot take over: it creates missing tables, never alters
an existing one, so the app can no longer ship a schema change to a database that
exists.

Go-live therefore needs two things: a recorded, replayable history of schema changes,
and a startup path that applies it unattended to a database the app does not
administer.

**"Safe" here means four specific things:** never lose prose · never leave a
half-applied schema · never let running code meet a schema it does not expect ·
every applied change reproducible from the repository.

## 2. Goals

- A schema change ships as a reviewed file in the repo, in one commit with the model
  change that caused it.
- An upgrade runs on application start, offline, without a human watching.
- A failed or interrupted upgrade leaves the database exactly as it was.
- Two databases from the same release have byte-identical schema.
- The migrated schema is provably the models' schema — mechanically, in `just test`.
- Hosted operation later changes the *discipline* of a revision, not the tool.

## 3. Non-goals

- Zero-downtime migrations. There is no fleet and no concurrent writer; when there is,
  expand/contract (D10) is the answer, not a different tool.
- Downgrade scripts. The documented rollback is the backup D5 takes.
- Migrating v1 (`_scratch/api`) databases. That app is gone.
- Backfills and data movement inside Alembic (D8).

## 4. Anti-goals

- `autogenerate` as the authority. It cannot tell a rename (data moves) from a drop
  plus add (data is gone).
- A second declaration of the schema (HCL, SQL, a second model tree).
- A migration that runs at import time, in a request, or per test module.

## 5. Constraints measured in this repo

- 14 tables across four model modules (`contracts`, `jobs`, `llm`, `prompts`), 635
  lines of models.
- Three extensions required before the tables: `vector`, `pg_trgm`, `unaccent`.
- Two partial unique indexes (`provider_profiles` one default per user,
  `prompt_templates` one global per key), one GIN trigram index, one untyped
  `Vector()` column.
- `Base.metadata` carries no naming convention, so foreign keys and the unnamed
  unique constraints have no addressable name today.
- Tests create the schema from the models, per module (`reset_schema`, ~9 conftests);
  `just test` is `pytest app/ -v`; no xdist.
- One async URL (`asyncpg`) from `NARRE_DATABASE_URL`, read at import.
- Capabilities may own tables (`CONSTRAINTS.md`), while `kernel` importing a
  capability is forbidden (D13) — the migration environment must therefore reach
  capability models through the generated registry, not by hand.

## 6. Approaches considered

| | How | Trade-off | Verdict |
|---|---|---|---|
| **A Alembic** | models stay the single source; revisions are drafts from `autogenerate`, read and corrected by a human | every revision is read by a person; Alembic is blind to extensions, triggers and some index changes — the equality gate covers what it cannot see. One limit, stated plainly: the gate runs `compare_metadata`, which shares autogenerate's blind spots (primary keys among them), so a missing migration for an object Alembic cannot compare passes the gate | **chosen** |
| **B Declarative (Atlas)** | desired state as SQL/HCL, the tool plans, lints and detects drift | the schema is declared twice — the declaration spread v2 exists to remove — plus a foreign binary in the distribution; data steps are awkward | rejected |
| **C SQL-first runner** (dbmate, or ~150 lines of our own) | ordered `.sql` files plus a version table | no draft from the models, and lock, backup and checksums become ours to build; every change written twice | rejected |

A is the only one where the model change and the migration sit in one commit and the
second copy does not exist. Postgres DDL is transactional, which gives crash safety
nearly for free — the point of failure in practice is not the transaction, it is the
unattended upgrade on a stranger's machine, and that is what D5/D6 address.

## 7. Decisions

**D1 — Alembic, async, in the kernel.** `alembic.ini` at the repo root,
`script_location = app/kernel/db/migrations`, async `env.py`
(`async_engine_from_config` + `connection.run_sync`). The URL comes from
`NARRE_DATABASE_URL` only; `sqlalchemy.url` stays empty in the ini. `env.py` imports
the four kernel model modules and every capability module named by
`app/generated/capabilities.py`, so a new capability's tables are seen without a
kernel→capability import.

**D2 — The draft is a draft.** `autogenerate` produces the file; a human reads it and
fixes: `Vector()` needs `import pgvector.sqlalchemy`, partial indexes need
`postgresql_where`, a rename must become `op.alter_column` with `new_column_name` plus
whatever data move it needs. A revision whose message does not state *why* is a review
finding.

**D3 — Four gates in `app/kernel/db/tests/test_migrations.py`,** run by `just test`
and therefore by CI's existing `tests` job; no new job, no new recipe for the gate.

1. **Single head.** One head revision, no branch.
2. **Empty → head equals the models.** Upgrade an empty database to head, then run
   `autogenerate` with `compare_type=True` and `compare_server_default=True` and
   assert the diff is empty.
3. **Previous release → head, with prose.** Load the checked-in schema snapshot of the
   last release (`tests/fixtures/schema_<version>.sql`, `pg_dump --schema-only` at
   release time), seed a user, a novel and a chapter with text, upgrade, assert the
   text is unchanged and the point-2 diff is empty. This is the test that catches a
   migration that eats prose. The snapshot rule, explicit: releases after 0.2.0 ship
   their snapshot WITH the single `alembic_version` row; 0.2.0 keeps its
   bootstrap-exception shape (no row), because that release predates the history.
4. **Bootstrap.** A models-created database with no `alembic_version` is stamped, a
   drifted one is refused (D4).

`pytest-alembic` is the first choice for 1–3 if its async support fits; otherwise the
same checks are ~80 lines against `alembic.command`.

**D4 — Bootstrap.** `alembic_version` missing while tables exist: compare the database
with the metadata. Equal → stamp the baseline. Not equal → refuse to start and say
what differs. Guessing here is how data is lost.

**Update 2026-11-01 (CodeRabbit round 1):** the bootstrap compares against the
*baseline revision's replayed schema* — reflected from a scratch database on the same
server — and stamps that baseline, so the normal flow upgrades the database to head
through every revision it never had; a database equal to the models at head instead
stamps head (fix round 2, same day — `reset_schema`, the API suite's client fixture
and any `create_all` are that population). At the same bootstrap, constraint names a
pre-convention database carries (Postgres's `users_email_key`, `<table>_pkey`,
`<table>_<column>_fkey` defaults) are normalized to the naming convention (D9) — a
diff-pair rename for uniques, a catalog rename for PK and FK — instead of refusing
the database; genuine drift still refuses, by name.

**D5 — The unattended upgrade, on start, before the first request.** `pg_advisory_lock`
so two starts cannot interleave; when revisions are pending, a restorable dump first
into `NARRE_BACKUP_DIR` (default `./backups`, last 3 kept), then `upgrade head` in one
transaction, then a head check.

The dump is a precondition **of that run**, not a property of the installation: with
nothing pending, no dump tool is ever invoked. Its source is one setting,
`NARRE_BACKUP_COMMAND`, a command template taking `{url}` and `{file}`, defaulting to
`pg_dump` on `PATH`; the compose deployment sets the container form
(`docker compose … exec -T postgres pg_dump …`), which also settles client/server
version matching without a check of ours. When no dump can be produced, nothing is
migrated and the error names both ways out: install `postgresql-client`, or set
`NARRE_MIGRATION_BACKUP=skip` **after** taking your own copy.

The repository's own toolchain does require `pg_dump` and `pg_restore` — the release
snapshot (D3.3), support restores and the round-trip test need them — and a missing
binary there is an install with a named package, never a skip.

Honest about the limits: a `.dump` file is not user self-service; a non-technical
author cannot restore it. Its value is support ("send us this file") and the guarantee
that a copy of the state before the upgrade exists. The protection that actually keeps
prose alive is D10.

**Update 2026-10-31** (product owner): the dump runs only when revisions are pending
*and* the database holds tables — a fresh first boot takes no dump, because the dump
protects prose and an empty schema has none, and skipping it also keeps `pg_dump` out
of the first boot's requirements.

**D6 — Never migrate backwards.** If the database's revision is not in this app's
history, or is ahead of head, the app refuses to start and names both versions. A
downgraded app meets its own backup, not a rollback script.

**D7 — Extensions before revisions.** `CREATE EXTENSION IF NOT EXISTS` stays a
separate idempotent pre-step (`ensure_extensions`), not DDL inside a revision: on a
hosted database the app user may not be allowed to create them, and there the platform
owns that step.

**D8 — Data moves are jobs.** A re-embedding after a model switch, a backfill, a
`search_text` rebuild: `jobs` table, resumable, never a revision. A revision may set a
default and a `NOT NULL` once the job has filled the column — the expand/contract
shape of D10.

**D9 — Naming convention first.** `Base.metadata` gets
`naming_convention={"ix": "ix_%(table_name)s_%(column_0_N_name)s", "uq": "uq_%(table_name)s_%(column_0_N_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"}`
*before* the baseline revision is written, so every constraint has a name a later
revision can drop. This changes no DDL semantics; it changes names the database
assigns today, which is why it lands before the baseline and not after.

**D10 — Expand/contract is the standing rule for prose tables.** Additive first
(nullable column, backfill job, code reads both), destructive change (`DROP`, rename,
narrowing type) only in a later release, or in the same revision when a backup and an
explicit data move are part of it. The local case gets this for free: a user who
downgrades the app still has a database the older app can read.

**D11 — One baseline, then append-only.** Before 1.0 the history may be squashed into a
single baseline revision (`alembic stamp`ed onto existing development databases by
D4). After 1.0 history is append-only: revisions are never edited once released.

**D12 — Two schema paths, one gate.** Tests keep creating the schema from the models
(fast, no replay per conftest); `db-init` and `db-reset` end in `upgrade head`. The two
paths are kept identical by gate D3.2, not by discipline. Revisit when the gate first
goes red or replay exceeds ~5 s per conftest.

**D13 — Recipes.** `db-init` and `db-reset` change their last step to
`alembic upgrade head`; `just db-revision "message"` is added (+1 on the 21-recipe
target; this approval covers it). No other recipe changes.

**D14 — Documentation.** `CONTRIBUTING.md` gains one section, "Changing the schema":
change the model → `just db-revision` → read and fix the draft → add/edit the release
snapshot at release time → `just check && just test`. No standing rule is added to
`CONSTRAINTS.md`; the one bullet that names "a migration tool" as a boundary is
updated to name this decision (ADR) instead.

## 8. What is left to the builder

- `pytest-alembic` or the ~80-line version of D3 (whichever proves honest with
  `asyncpg` and the per-module reset).
- Backup retention count, the value `NARRE_BACKUP_COMMAND` takes in a compose install,
  and where `NARRE_BACKUP_DIR` is mounted there.
- Advisory-lock timeout, and what the user sees while an upgrade runs (one line in the
  UI is a separate, later decision).
- Revision message grammar and id style.
- Whether `reset_schema` survives as-is once migrations exist, or shrinks to
  `drop schema public cascade` plus `upgrade head`.

## 9. Consequences accepted

- One new dependency (`alembic`) and one new directory of files that must be read.
- Every schema change now costs a second, small artefact — the revision file —
  and a review of it.
- The startup path grows: lock, dump, transaction, head check. On a local install this
  is the difference between "upgrade" and "upgrade may have eaten my book".
- The spec's "no migrations" statement becomes history; the ADR records why.
