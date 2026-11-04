# Schema Migrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Narrare a replayable schema history so an upgrade can reach a database that already holds a user's manuscript, without ever discarding or half-changing it.

**Architecture:** Alembic as the engine, revisions written by a human from an `autogenerate` draft, models remain the only declaration of the schema. One async `env.py` under `app/kernel/db/migrations/`; one unexported function `prepare_database()` owns the unattended path (extensions → lock → version check → backup → upgrade → verify). Its correctness is pinned by four tests that run inside the existing `pytest app/` gate.

**Tech Stack:** Python 3.14, SQLAlchemy 2.1 (async, asyncpg), Alembic, PostgreSQL 17 + pgvector, pytest, `just`.

**Spec:** `docs/superpowers/specs/2026-10-30-schema-migrations-design.md`. Executors read both.

## Global Constraints

- English in code, tests and developer documentation; no user-visible string changes in this plan.
- Imports point one way: `api → capabilities → kernel`. `env.py` may not import a capability by name — capability models come from `app/generated/capabilities.py`.
- No new CI job. Every test below is collected by `just test` (`pytest app/ -v`).
- No `--no-verify`, no force push. Conventional commits; `feat`/`fix` carry a `User-visible:` line.
- The public recipe surface grows by exactly one: `db-revision`.
- Every DB-touching test runs against its own database created by `app/kernel/db/testsupport.py`; never against `narrare_v2_dev`.
- No test asserts that a dump tool is on `PATH` as a property of the product. The
  invariant is behavioural: a run with pending revisions either produces a restorable
  dump or migrates nothing. The repository's own toolchain test does require
  `pg_dump`/`pg_restore` (round trip in Task 3); a missing binary there is an install
  with a named package, never a skip.

## Review Focus

1. **Database has tables but no `alembic_version`, and the schema drifted** (hand-edited locally). Expected: refuse to start, name the difference. Never stamp.
2. **Database revision ahead of the app** (user downgraded the app). Expected: refuse, name both versions; the older app must not "fix" it.
3. **Two processes start at once** (`uvicorn --workers 2`, e2e next to a dev server). Expected: one migrates, the other waits, both serve.
4. **Upgrade killed mid-transaction** (`SIGKILL`). Expected: schema unchanged, no lock leak after the connection drops.
5. **No dump can be produced while revisions are pending** — tool absent, the command
   fails, the server is newer than the client, or the target directory is unwritable,
   including the case where only the compose container has the tool. Expected: nothing
   is migrated, and the message names both ways out.
6. **DB role without `CREATE EXTENSION` rights** (hosted later). Expected: one clear refusal before any DDL.
7. **A revision that deletes rows** (a plausible draft mistake). Expected: the snapshot gate with seeded prose goes red.

---

### Task 1: Alembic scaffold, naming convention, baseline, two gates

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (add `alembic`)
- Modify: `app/kernel/db/base.py` (metadata naming convention)
- Modify: `app/kernel/db/init.py` (`ensure_extensions` extracted; `init_schema` becomes "extensions + upgrade head")
- Create: `alembic.ini`, `app/kernel/db/migrations/env.py`, `app/kernel/db/migrations/script.py.mako`, `app/kernel/db/migrations/versions/<rev>_baseline.py`
- Create: `app/kernel/db/tests/__init__.py`, `app/kernel/db/tests/conftest.py`, `app/kernel/db/tests/test_migrations.py`
- Modify: `justfile` (`db-init`, `db-reset` end in `alembic upgrade head`)

**Interfaces:**
- Produces: `app.kernel.db.migrate.head_revision() -> str` (exactly one head, else raises `MigrationRefused`); `app.kernel.db.migrate.diff_against_models(config: Config, connection: Connection) -> list[Any]` (empty list means the migrated schema equals the models); `app.kernel.db.migrate.MigrationRefused(RuntimeError)`; `NARRE_DATABASE_URL` is the only URL source.
- Consumes: `app.kernel.db.testsupport.url_for`, `ensure_database`.

- [ ] **Step 1: Write the failing gate test**

`app/kernel/db/tests/test_migrations.py`, with a module fixture that creates the database `narrare_v2_migrations` via `ensure_database` and yields `url_for("narrare_v2_migrations")`:

```python
def test_migrations_have_one_head() -> None:
    assert head_revision().count(",") == 0 and head_revision()


def test_empty_database_migrated_equals_the_models(url: str) -> None:
    command.upgrade(alembic_config(url), "head")
    assert diff_against_models(alembic_config(url), connect(url)) == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `just test-file app/kernel/db/tests/test_migrations.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.kernel.db.migrate'`.

- [ ] **Step 3: Add the dependency and the scaffold**

`uv add alembic`. Create the scaffold by hand (not `alembic init`): `alembic.ini` with `script_location = app/kernel/db/migrations` and **no** `sqlalchemy.url`; `script.py.mako` default; `env.py` following the async template — `connectable = async_engine_from_config(...poolclass=pool.NullPool)`, `config.set_main_option("sqlalchemy.url", environ["NARRE_DATABASE_URL"])`, `target_metadata = Base.metadata`, `context.configure(connection=..., target_metadata=..., compare_type=True, compare_server_default=True, render_item=_render_item)` where `_render_item` renders `Vector` as `pgvector.sqlalchemy.Vector()` and `script.py.mako` imports it.

- [ ] **Step 4: Make `env.py` see every table**

In `env.py`, import `app.kernel.contracts.models`, `app.kernel.jobs.models`, `app.kernel.llm.models`, `app.kernel.prompts.models`, then for each `CAPABILITIES` id from `app.generated.capabilities`, `import_module(f"app.capabilities.{id}.models")` under `suppress(ModuleNotFoundError)`. Comment why: kernel may not name a capability.

- [ ] **Step 5: Add the naming convention before the baseline exists**

`class Base(DeclarativeBase): metadata = MetaData(naming_convention={...})` with the five keys from design D9. Run `just test` — the 9 capability suites must stay green; only constraint names change.

- [ ] **Step 6: Write `migrate.py` minimally and the baseline revision**

`head_revision()` reads `ScriptDirectory.from_config(config).get_heads()`, raises `MigrationRefused` on 0 or >1. `diff_against_models` uses `MigrationContext.configure(connection, opts={"compare_type": True, "compare_server_default": True})` + `autogenerate.compare_metadata`. Then `uv run alembic revision --autogenerate -m "baseline"` against an empty database holding only the three extensions; read the generated file and assert by eye that it contains the two partial unique indexes with `postgresql_where`, the GIN `gin_trgm_ops` index, and `pgvector.sqlalchemy.Vector()`.

- [ ] **Step 7: Switch `init_schema` to `upgrade head`**

`init.py` keeps `reset_schema` exactly as it is (tests create from the models). `ensure_extensions(database_url)` becomes a public function; `init_schema` = `ensure_extensions` + `command.upgrade(config, "head")`. Update `justfile`: `db-init` unchanged in name, `db-reset` gains the same final step.

- [ ] **Step 8: Run the gates**

Run: `just test-file app/kernel/db/tests/test_migrations.py` → PASS. Then `just test` → PASS. Then `just db-reset && just db-init` → both print the schema line and a second `db-init` is a no-op.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock alembic.ini app/kernel/db justfile
git commit -m "feat(db): replayable schema history from the models

User-visible: an upgrade can now reach an existing database instead of requiring it to be discarded."
```

---

### Task 2: `prepare_database` — extensions, versions, bootstrap, refusal

**Files:**
- Create: `app/kernel/db/migrate.py` (grows from Task 1)
- Modify: `app/kernel/db/tests/test_migrations.py`

**Interfaces:**
- Produces: `@dataclass class MigrationOutcome: from_revision: str | None; to_revision: str; bootstrapped: bool; backup: Path | None`; `async def prepare_database(database_url: str, *, backup: bool = True, backup_dir: Path | None = None) -> MigrationOutcome`; `async def current_revision(connection: AsyncConnection) -> str | None`.

- [ ] **Step 1: Write the four failing tests**

```python
async def test_fresh_database_is_upgraded(url):          # from_revision is None, bootstrapped False
async def test_models_created_database_is_stamped(url):  # create_all, then prepare_database → bootstrapped True, no DDL
async def test_drifted_database_is_refused(url):         # create_all, ALTER TABLE chapters DROP COLUMN title → MigrationRefused naming "title"
async def test_database_ahead_of_the_app_is_refused(url):# upgrade head, then UPDATE alembic_version SET version_num='zzzz' → MigrationRefused naming 'zzzz' and head
```

- [ ] **Step 2: Run them to verify they fail**

Run: `just test-file app/kernel/db/tests/test_migrations.py -k prepare`
Expected: FAIL — `ImportError: cannot import name 'prepare_database'`.

- [ ] **Step 3: Implement in this order inside `prepare_database`**

1. `ensure_extensions` — failures surface as `MigrationRefused` with the GRANT hint.
2. open one connection; `pg_advisory_lock(hashtext('narrare_migrations'))` (Task 3 adds it; this task takes the simple path).
3. `current = await current_revision(conn)` — `SELECT version_num FROM alembic_version` inside `suppress(ProgrammingError)`/undefined-table.
4. `current is None and tables_exist`: `diff_against_models` → `[]` ⇒ `command.stamp(config, head)`; non-empty ⇒ `MigrationRefused` listing `op[0]` and `op[1]` of each diff entry.
5. `current` not in `{r.revision for r in ScriptDirectory...walk_revisions()}` ⇒ `MigrationRefused(f"database is at {current}, this app knows {head}")`.
6. `command.upgrade(config, "head")` — run via `asyncio.to_thread`.
7. re-read the revision; a mismatch is a hard `MigrationRefused`.

- [ ] **Step 4: Run the four tests, then the whole suite**

Run: `just test-file app/kernel/db/tests/test_migrations.py` → PASS, then `just test` → PASS.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/db/migrate.py app/kernel/db/tests/test_migrations.py
git commit -m "feat(db): refuse to guess — bootstrap, drift and downgrade are named refusals"
```

---

### Task 3: Lock, backup, and the failure paths

**Files:**
- Create: `app/kernel/db/backup.py`
- Modify: `app/kernel/db/migrate.py`, `app/kernel/db/tests/test_migrations.py`
- Modify: `.env.example`, `CONTRIBUTING.md` (prerequisites)

**Interfaces:**
- Produces: `async def dump_database(database_url: str, directory: Path, *, keep: int = 3) -> Path` (raises `BackupFailed`); `def backup_command(url: str, file: Path) -> list[str]` resolving `NARRE_BACKUP_COMMAND` (a template with `{url}` and `{file}`) or `["pg_dump", "--format=custom", "--no-owner", "--file", …, url]`; `MigrationOutcome.backup: Path | None`, set whenever a revision was pending. Env: `NARRE_BACKUP_DIR` (default `./backups`), `NARRE_MIGRATION_BACKUP` = `pg_dump` (default) | `skip`, `NARRE_BACKUP_COMMAND` (unset by default).

- [ ] **Step 1: Install the toolchain the repository needs**

`pg_dump` and `pg_restore` are absent on this host (`command not found`). Install `postgresql-client-17` — the repository's own snapshot and round-trip tests need them; nothing about the shipped app depends on that being on `PATH` (design D5).

- [ ] **Step 2: Write the failing tests**

```python
async def test_dump_and_restore_round_trip(url):   # toolchain: dump into tmp_path, pg_restore into a fresh scratch DB,
                                                   # a seeded novel title is present there. Missing binary → fail naming postgresql-client-17.
async def test_pending_revision_writes_a_dump(url, tmp_path):   # outcome.backup exists and starts with b"PGDMP"
async def test_up_to_date_database_writes_no_dump(url, tmp_path) # second run → backup is None, file count unchanged
async def test_failing_backup_command_migrates_nothing(url, monkeypatch):
    # NARRE_BACKUP_COMMAND="false {url} {file}" → BackupFailed; SELECT from alembic_version raises UndefinedTable
async def test_concurrent_starts_migrate_once(url):             # two prepare_database calls via asyncio.gather → both return, one row in alembic_version
```

- [ ] **Step 3: Run them to verify they fail** — `just test-file app/kernel/db/tests/test_migrations.py -k "dump or backup or concurrent"`; expect `ImportError`.

- [ ] **Step 4: Implement `dump_database`**

Resolve the command with `backup_command`, run it through `asyncio.to_thread` with `check=True`-equivalent (non-zero exit → `BackupFailed(stderr)`), after `directory.mkdir(parents=True, exist_ok=True)`; delete dumps beyond `keep` by mtime. Call it inside `prepare_database` **after** the lock and **before** `upgrade`, only when `backup=True` and revisions are pending; `NARRE_MIGRATION_BACKUP=skip` short-circuits. The URL passed to the command is `database_url` with `+asyncpg` removed.

- [ ] **Step 5: Make the lock real**

Hold the advisory lock on its own connection for the duration of the upgrade (a second connection, not the transaction Alembic opens), release it in `finally`. The concurrent test must pass on both orderings.

- [ ] **Step 6: Run the tests, then the suite** — `just test` → PASS.

- [ ] **Step 7: Document the three variables in `.env.example`** (each with the one working line for the compose form of `NARRE_BACKUP_COMMAND`), add `postgresql-client-17` to CONTRIBUTING's prerequisites, then commit:

```bash
git add .env.example CONTRIBUTING.md app/kernel/db
git commit -m "feat(db): dump before the first revision, lock against two starts

User-visible: an upgrade takes a copy of the database first, and refuses to start without one."
```

---

### Task 4: The snapshot gate — a release, upgraded with prose

**Files:**
- Create: `app/kernel/db/tests/fixtures/schema_0.2.0.sql`
- Modify: `app/kernel/db/tests/test_migrations.py`

**Interfaces:**
- Consumes: `prepare_database`, `diff_against_models`.

- [ ] **Step 1: Write the failing test**

```python
async def test_release_snapshot_upgrades_without_losing_prose(url):
    # load fixtures/schema_0.2.0.sql into the empty database
    # INSERT a user (LOCAL_USER_ID), a novel "Die Prüfung" and a chapter body "Wort für Wort"
    # prepare_database(url, backup=False)
    # assert the chapter body is byte-identical, the novel title unchanged,
    # and diff_against_models(...) == []
```

- [ ] **Step 2: Run it to verify it fails** — fixture missing → FAIL.

- [ ] **Step 3: Produce the fixture once, by hand, and commit it**

```
just db-reset
docker compose -f docker-compose.dev.yml exec -T postgres \
  pg_dump -U narrare -d narrare_v2_dev --schema-only --no-owner > \
  app/kernel/db/tests/fixtures/schema_0.2.0.sql
```

It must contain no `alembic_version` row and no `CREATE EXTENSION` (the harness adds them); check both with `rg`.

- [ ] **Step 4: Run the test, then the suite** — PASS, `just test` PASS.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/db/tests
git commit -m "test(db): a release snapshot upgrades with its prose intact"
```

---

### Task 5: Startup runs it

**Files:**
- Modify: `app/api/main.py` (lifespan), `app/api/tests/` (the existing app-startup test)
- Modify: `app/api/conftest.py` if `init_schema`'s new meaning changes its comment

**Interfaces:**
- Consumes: `prepare_database` from Task 2/3.

- [ ] **Step 1: Write the failing test**

```python
def test_startup_migrates_before_the_worker(client):   # TestClient(app) on a models-created DB → SELECT 1 FROM alembic_version succeeds
def test_startup_refuses_a_drifted_database(client_factory):  # expect RuntimeError whose message names the missing column
```

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Call it first in `lifespan`** — `await prepare_database(DATABASE_URL)` before `validate_configuration()`, with the comment that a configuration check against an older schema reports the wrong problem.

- [ ] **Step 4: Run the API tests, then the full gate** — `just test` and `just test-e2e` (the e2e stacks start the real API, so this proves the bootstrap on a models-created database end to end).

- [ ] **Step 5: Commit**

```bash
git add app/api
git commit -m "feat(db): migrate on startup, before the first worker or request

User-visible: starting the app on an older database upgrades it instead of failing on a missing column."
```

---

### Task 6: The authoring path and the records

**Files:**
- Modify: `justfile` (`db-revision "message"` recipe, and the header's "22 public recipes" line → 23)
- Modify: `AGENTS.md` (root — the "22 recipes" line in Verify)
- Modify: `CONTRIBUTING.md`
- Create: `docs/architecture/decisions/ADR-103-schema-migrations.md`
- Modify: `docs/architecture/decisions/INDEX.md`, `docs/_shared/CONSTRAINTS.md` (the one bullet), `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md:319-322` (D11) — plus moving the design doc into `docs/superpowers/specs/`

- [ ] **Step 1: Add the recipe**

```make
# Draft a revision from the models: just db-revision "add chapters.word_count"
db-revision message:
    uv run alembic revision --autogenerate -m "{{message}}"
```

- [ ] **Step 2: Run it** — `just db-revision "probe"`, confirm the file appears and is empty of operations (schema is current), then `rm` it and run `just db-revision --help`-style check that the recipe lists under `just --list` (23 recipes).

- [ ] **Step 3: Write ADR-103** from `_TEMPLATE.md`: decision, the three statements §8 requires (failure prevented: an upgrade that needs `db-reset`; effort: one reviewed file per schema change; cheaper alternative: none that keeps one declaration), the rejected approaches from the design, and the consequences. Add the INDEX row, newest first.

- [ ] **Step 4: Update the two authority pages** — spec §9 D11 says the migration story begins at go-live *and* names this decision; `CONSTRAINTS.md`'s "a migration tool crosses a boundary" bullet points at ADR-103 instead of forbidding the tool.

- [ ] **Step 5: Write the CONTRIBUTING section** "Changing the schema": model → `just db-revision` → read it (rename vs drop, `postgresql_where`, `Vector()`) → gates → snapshot refresh at release time → commit both files together.

- [ ] **Step 6: Run the full gate** — `just check && just test`.

- [ ] **Step 7: Commit**

```bash
git add justfile CONTRIBUTING.md docs
git commit -m "docs(db): record the migration decision and how a schema change is shipped"
```

---

## Self-review

- Design D1–D14 mapped: D1/D2/D9/D11 → Task 1; D4/D6 → Task 2; D5 → Task 3 (+ D7 in Task 1 step 7); D3.3 → Task 4; D5 wiring → Task 5; D8 is a rule, stated in ADR-103 and CONTRIBUTING; D12 → Task 1 step 7 (two paths, one gate); D13/D14 → Task 6.
- Every Review Focus line has an owning test: 1 → T2 drifted; 2 → T2 ahead; 3 → T3 concurrent; 4 → T3 lock release + the transactional upgrade (no test can assert a SIGKILL cheaply; the property is Postgres's, and T4's snapshot proves the transaction boundary); 5 → T3 failing backup command + round trip; 6 → T2 extensions refusal; 7 → T4 prose snapshot.
- Names held constant across tasks: `prepare_database`, `MigrationOutcome`, `MigrationRefused`, `BackupFailed`, `diff_against_models`, `head_revision`, `dump_database`, `ensure_extensions`, `current_revision`.
