# Narrare release process — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one container image whose published bytes are the bytes the gates started, migrated and browsed.

**Architecture:** A multi-stage `Dockerfile` produces an app-only image; the database comes from `NARRE_DB_*` (external, the hosting and Unraid case) or from `docker-compose.release.yml` (bundled pgvector). The image is built and smoked nightly, built and fully gated when the release PR is approved, and published by re-tagging that digest when the release goes out. No second build after the tag.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · Alembic · PostgreSQL 17/18 + pgvector · Docker/Buildx · GitHub Actions · release-please.

**Spec:** `~/.opencode/plan/2026-11-06-release-process-design.md` (moves to `docs/superpowers/specs/` with this plan).

## Global Constraints

- Image content size ≤ **350 MB**; platform **`linux/amd64`** only.
- Container runs as **UID/GID 99:100**; the only writable path is `/backups`.
- `postgresql-client` **18** from PGDG in the image; gates against server **17** (bundled compose) and **18** (external).
- Database variables: `NARRE_DB_HOST`, `NARRE_DB_PORT` (default 5432), `NARRE_DB_NAME`, `NARRE_DB_USER`, `NARRE_DB_PASSWORD` (optional), `NARRE_DB_SSLMODE` (optional). `NARRE_DATABASE_URL` wins over all of them.
- `NARRE_KEYRING=off` and `NARRE_BACKUP_DIR=/backups` are set by the image.
- No all-in-one image. No ruleset edit: `ci-required` stays the only required check.
- Published image is the digest tested on the release PR; no rebuild after the tag.
- English in code, comments, tests and documentation; user text through the i18n catalog where it is user-visible.
- Conventional commits; `feat`/`fix` carry a `User-visible:` line; no `--no-verify`, no force push.

## Review Focus

1. **Passwords with URL metacharacters** (`@ : / # ? %`) and **empty passwords** (trust auth) — both must connect; a mangled password is the likeliest first-contact failure.
2. **Partially set `NARRE_DB_*`** or a variable set to an empty string — must refuse at startup naming the missing variables, never fall back to the localhost default.
3. **A reachable server without pgvector, or without `CREATE EXTENSION` privilege** — one sentence naming what is missing, non-zero exit; not a bare traceback.
4. **`/backups` not writable** (wrong owner on a host path) — the upgrade must refuse rather than migrate without a dump, and name the path.
5. **A digest that no longer exists at release time** — promotion fails loudly; `:<version>` never points at a rebuilt image.

---

### Task 0: The release PR can be green — already landed

Landed on `main` as `afec30ac` ("fix(ci): the OpenAPI writer prints whole numbers
release-please keeps", 2026-11-06) while this plan was written; nothing is left to do.
For the record, the cause was not the version bump: release-please rewrites
`web/lib/api/openapi.json` through Go's `encoding/json`, which prints an integral
float as an integer (`20.0` → `20`), while `scripts/export_openapi.py` dumped
pydantic's floats verbatim. `just check-generated` compares bytes, so the two could
never agree on a release branch. The writer now prints the canonical form and the
committed document is regenerated; the round trip is a no-op. Tests live in
`app/kernel/tests/test_export_openapi.py`, and `just check-generated` stays in the
version-bump gate (Task 7) so a regression reddens a release PR instead of a merge.

---

### Task 1: Database configuration from `NARRE_DB_*`

**Files:**
- Create: `app/kernel/db/url.py`
- Modify: `app/kernel/db/session.py`
- Modify: `app/api/main.py` (log line in `lifespan`)
- Test: `app/kernel/db/tests/test_url.py`

**Interfaces:**
- Produces: `class DatabaseConfig: url: URL; source: str`
  `def resolve(env: Mapping[str, str] | None = None) -> DatabaseConfig`
  `class DatabaseConfigurationError(RuntimeError)`
  `DRIVERNAME = "postgresql+asyncpg"`
- Produces: `session.DATABASE_CONFIG: DatabaseConfig`, `session.DATABASE_URL: str` (rendered, password included).

- [ ] **Step 1: Write the failing tests**

```python
def test_url_wins_over_parts():
    cfg = resolve({"NARRE_DATABASE_URL": "postgresql+asyncpg://u:p@h:5432/d",
                   "NARRE_DB_HOST": "other", "NARRE_DB_NAME": "x", "NARRE_DB_USER": "y"})
    assert cfg.url.database == "d"
    assert cfg.source == "NARRE_DATABASE_URL"

def test_parts_compose_and_encode_a_hostile_password():
    cfg = resolve({"NARRE_DB_HOST": "postgres", "NARRE_DB_NAME": "narrare",
                   "NARRE_DB_USER": "narrare", "NARRE_DB_PASSWORD": "p@ss:w/rd#1"})
    assert make_url(cfg.url.render_as_string(hide_password=False)).password == "p@ss:w/rd#1"

def test_ipv6_host_is_bracketed():
    cfg = resolve({"NARRE_DB_HOST": "fe80::1", "NARRE_DB_NAME": "d", "NARRE_DB_USER": "u"})
    assert "[fe80::1]" in cfg.url.render_as_string(hide_password=False)

def test_incomplete_parts_name_what_is_missing():
    with pytest.raises(DatabaseConfigurationError) as exc:
        resolve({"NARRE_DB_HOST": "postgres", "NARRE_DB_NAME": ""})
    assert "NARRE_DB_NAME" in str(exc.value) and "NARRE_DB_USER" in str(exc.value)

def test_unset_everything_reports_the_dev_default():
    cfg = resolve({})
    assert cfg.source == "default (localhost dev)"
    assert cfg.url.database == "narrare_v2_dev"

def test_bad_port_is_refused_by_name():
    with pytest.raises(DatabaseConfigurationError) as exc:
        resolve({"NARRE_DB_HOST": "h", "NARRE_DB_NAME": "d", "NARRE_DB_USER": "u",
                 "NARRE_DB_PORT": "5432x"})
    assert "NARRE_DB_PORT" in str(exc.value)

def test_sslmode_becomes_the_asyncpg_query_parameter():
    cfg = resolve({"NARRE_DB_HOST": "h", "NARRE_DB_NAME": "d", "NARRE_DB_USER": "u",
                   "NARRE_DB_SSLMODE": "require"})
    assert cfg.url.query["ssl"] == "require"
```

- [ ] **Step 2: Run to verify they fail**

Run: `just test-file app/kernel/db/tests/test_url.py`
Expected: collection error — `app.kernel.db.url` does not exist.

- [ ] **Step 3: Implement `resolve`**

Precedence: `NARRE_DATABASE_URL` → parts → dev default
(`postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_v2_dev`, source
`"default (localhost dev)"`). An empty string counts as unset. Required together:
host, name, user; each missing name appears in the error. Port must parse as int.
`NARRE_DB_SSLMODE` is validated against
`{"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}` and passed as
`query={"ssl": mode}`. Build with `URL.create(DRIVERNAME, username=…, password=…,
host=…, port=…, database=…, query=…)` — never by string concatenation. `source` is
one human line: `"NARRE_DATABASE_URL"`, `"NARRE_DB_* → narrare@postgres:5432/narrare"`
or the default marker; it must never contain the password.

- [ ] **Step 4: Run to verify they pass**

Run: `just test-file app/kernel/db/tests/test_url.py`
Expected: PASS (7 tests).

- [ ] **Step 5: Wire it in and log the source**

`session.py`: `DATABASE_CONFIG = resolve()`, `DATABASE_URL = DATABASE_CONFIG.url.render_as_string(hide_password=False)`. `main.py`'s lifespan logs `database: %s` with `DATABASE_CONFIG.source` **before** `prepare_database`.

- [ ] **Step 6: Prove the wiring still installs and runs**

Run: `just check` then `just test-file app/kernel/db/tests/test_migrations.py`
Expected: both green; no test sets `NARRE_DB_*`.

- [ ] **Step 7: Commit**

```bash
git add app/kernel/db/url.py app/kernel/db/session.py app/api/main.py app/kernel/db/tests/test_url.py
git commit -m "feat(kernel): configure the database from NARRE_DB_* parts" --trailer "User-visible: A container can be pointed at an existing Postgres without URL-encoding a password."
```

---

### Task 2: Refuse a database that cannot provide the extensions

**Files:**
- Modify: `app/kernel/db/migrate.py` (`ensure_extensions`, new helpers)
- Test: `app/kernel/db/tests/test_migrations.py` (extend)

**Interfaces:**
- Produces: `REQUIRED_EXTENSIONS: tuple[str, ...] = ("vector", "pg_trgm", "unaccent")`
  `def extension_refusal(missing: Sequence[str]) -> str`
  `def missing_extensions(available: Collection[str]) -> list[str]`
- Consumes: `MigrationRefused` (exists).

- [ ] **Step 1: Write the failing tests**

```python
def test_extension_refusal_names_every_missing_extension():
    text = extension_refusal(["vector", "unaccent"])
    assert "vector" in text and "unaccent" in text and "pg_trgm" not in text
    assert "pgvector" in text  # says what to do, not only what is wrong

def test_missing_extensions_keeps_the_required_order():
    assert missing_extensions({"pg_trgm"}) == ["vector", "unaccent"]
    assert missing_extensions(set(REQUIRED_EXTENSIONS)) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `just test-file app/kernel/db/tests/test_migrations.py`
Expected: FAIL — names not defined.

- [ ] **Step 3: Implement, and consult the catalog before creating**

`ensure_extensions` keeps one transaction and now begins with
`SELECT name FROM pg_available_extensions WHERE name = ANY(:names)`; if
`missing_extensions(...)` is non-empty it raises `MigrationRefused(extension_refusal(...))`
before any `CREATE EXTENSION`. The three `CREATE EXTENSION IF NOT EXISTS` statements
iterate `REQUIRED_EXTENSIONS` instead of literal names. The message names the missing
extensions and says to use a pgvector-capable server or install the extension; it is
one sentence, no traceback terms.

- [ ] **Step 4: Run to verify they pass**

Run: `just test-file app/kernel/db/tests/test_migrations.py`
Expected: PASS, including the existing upgrade/refusal gates.

- [ ] **Step 5: Prove the real path still installs all three**

Run: `just test-file app/kernel/db/tests/test_migrations.py -k extension`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/kernel/db/migrate.py app/kernel/db/tests/test_migrations.py
git commit -m "feat(kernel): name the extension a database cannot provide" --trailer "User-visible: A container pointed at a plain Postgres says which extension is missing instead of printing a traceback."
```

---

### Task 3: The image, and its nightly build

**Files:**
- Create: `Dockerfile`, `.dockerignore`
- Modify: `.github/workflows/nightly.yml` (job `container`; add it to `nightly-result`'s `needs`)
- Modify: `.github/dependabot.yml` (docker entry at `/`)

**Interfaces:**
- Produces: image `narrare` listening on `8000`, running as `99:100`, with
  `python -m app.kernel.db.init`-free startup (the lifespan migrates), `pg_dump` 18 on
  `PATH`, `NARRE_KEYRING=off`, `NARRE_BACKUP_DIR=/backups`.

- [ ] **Step 1: Write `.dockerignore`**

Exclude `.git`, `.venv`, `node_modules`, `web/node_modules`, `web/dist`, `docs`,
`_scratch`, `backups`, `coverage.xml`, `.github`, `**/__pycache__`, `**/tests`,
`**/e2e`. `web/dist` is excluded because the `web` stage produces it.

- [ ] **Step 2: Write the `Dockerfile`**

Stage `web` from `node:22-slim` (digest-pinned, trailing `# node:22-slim` comment):
copy `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `web/package.json`, `web/`, then
`corepack enable`, `pnpm install --frozen-lockfile`, `pnpm --dir web build`.

Stage runtime from `python:3.14-slim` (digest-pinned), `TARGETARCH` unused (amd64
only):
`apt-get install` `curl gnupg ca-certificates`, add the PGDG key
(`https://www.postgresql.org/media/keys/ACCC4CF8.asc`), the source
`deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main`,
then `postgresql-client-18`; remove the lists. Copy `uv` from
`ghcr.io/astral-sh/uv:<pinned>` into `/bin`. Copy `pyproject.toml` and `uv.lock`,
run `uv sync --no-dev --frozen`, then copy `app/ i18n/ alembic/ alembic.ini`, then
`--from=web /src/web/dist ./web/dist`.

`ENV NARRE_KEYRING=off NARRE_BACKUP_DIR=/backups`, `VOLUME /backups`, `USER 99:100`,
`EXPOSE 8000`, OCI labels (`org.opencontainers.image.version` /
`.revision` / `.source` / `.licenses`), and
`CMD ["uv", "run", "--no-sync", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
No `HEALTHCHECK`: there is no route that proves the database, and a check that passes
without one is worse than none.

- [ ] **Step 3: Build it and look at the size**

Run: `docker build -t narrare:local . && docker image inspect narrare:local --format '{{.Size}}'`
Expected: under `350000000` bytes.

- [ ] **Step 4: Start it against a throwaway pgvector server**

Run:
```bash
docker network create narrare-smoke
docker run -d --name pg --network narrare-smoke -e POSTGRES_USER=narrare \
  -e POSTGRES_PASSWORD=narrare -e POSTGRES_DB=narrare pgvector/pgvector:pg17
docker run -d --name app --network narrare-smoke -p 8080:8000 \
  -e NARRE_DB_HOST=pg -e NARRE_DB_NAME=narrare -e NARRE_DB_USER=narrare \
  -e NARRE_DB_PASSWORD=narrare -e NARRE_SECRET_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  narrare:local
docker logs -f app   # until uvicorn reports startup complete
```
Expected: the log carries `database: NARRE_DB_* → narrare@pg:5432/narrare`, the
migrations reach head, and `curl -sf http://127.0.0.1:8080/ | head -c 200` answers the
shell HTML. `curl -sf` on `/assets/<file from index.html>` answers 200.

- [ ] **Step 5: Prove the first boot really migrated**

Run: `docker exec pg psql -U narrare -d narrare -c '\dt' | head` and
`docker exec pg psql -U narrare -d narrare -c "select name from pg_available_extensions where name in ('vector','pg_trgm','unaccent')"`
Expected: the tables exist, `alembic_version` is present, and all three extensions are listed.

- [ ] **Step 6: Add the nightly job**

In `nightly.yml`, job `container` (needs `gate`), same guards as the other jobs: build
with `cache-from/to: type=gha` (no push), run the smoke of Step 4 against a Postgres
service container, assert the shell and one asset, and fail when the size exceeds
350 MB. Add `container` to `nightly-result`'s `needs` and to its result check.

- [ ] **Step 7: Re-enable the Dependabot docker updater**

`.github/dependabot.yml`: a `docker` entry at `/` with the established grouping and
cooldown shape.

- [ ] **Step 8: Verify the workflow files**

Run: `just lint` (actionlint and zizmor run in CI's `workflow-lint`; run the local
probe the workflow does) and `docker build` once more after the change.
Expected: no workflow lint error; the image still builds.

- [ ] **Step 9: Commit**

```bash
git add Dockerfile .dockerignore .github/workflows/nightly.yml .github/dependabot.yml
git commit -m "feat(container): ship the app as one image, built and smoked nightly" --trailer "User-visible: Narrare is installable as a container image for the first time."
```

---

### Task 4: The compose file, and the install page

**Files:**
- Create: `docker-compose.release.yml`
- Create: `docs/user/install.md`
- Modify: `docs/user/INDEX.md` (link)

**Interfaces:**
- Consumes: the image and variables from Tasks 1–3.

- [ ] **Step 1: Write the compose file**

`app` (`image: ghcr.io/jmerifjKriwe/narrare:latest`) with
`NARRE_DB_HOST=postgres`, `NARRE_DB_NAME/USER/PASSWORD` from `${…:?}` style
substitutions with the dev-compatible defaults, `NARRE_SECRET_KEY` from `${NARRE_SECRET_KEY:?}`,
`NARRE_BACKUP_DIR=/backups`, volumes `backups:/backups`, port `8000:8000`,
`depends_on: postgres: condition: service_healthy`, `restart: unless-stopped`.
`postgres` from `pgvector/pgvector:pg17` (digest-pinned), volume `pgdata`,
`healthcheck: pg_isready -U narrare -d narrare`.

- [ ] **Step 2: Prove the default path end to end**

Run:
```bash
printf 'NARRE_SECRET_KEY=%s\n' "$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" > .env
docker compose -f docker-compose.release.yml up -d --wait
curl -sf http://127.0.0.1:8000/ >/dev/null && echo shell-ok
```
Expected: `shell-ok`; `docker compose ps` shows both services healthy.

- [ ] **Step 3: Prove a restart keeps the data**

Complete the setup flow through the API (read `app/capabilities/setup/router.py` for
the route and body), create one chapter, then `docker compose restart app` and re-read
the chapter.
Expected: same content before and after the restart.

- [ ] **Step 4: Prove the dump lands on the volume and survives a recreate**

Run: `docker compose exec app pg_dump --version` (expect `pg_dump (PostgreSQL) 18`)
and `docker compose down && docker compose up -d --wait`; the chapter from Step 3 is
still readable.
Expected: data survives; `docker compose exec app ls -la /backups` is the host-mapped
volume (write a file there from the host and see it in the container).

- [ ] **Step 5: Write `docs/user/install.md`**

Three sections — compose (default), own Postgres (the `CREATE EXTENSION vector`
prerequisite, the privilege it needs, the `NARRE_DB_*` variables, `NARRE_SECRET_KEY`
generated once and kept with the backups), Unraid (link to Task 5's section) — then
**upgrade** (`docker compose pull`, backup first, where the pre-migration dumps land)
and **restore** (`pg_restore` into a fresh database).

- [ ] **Step 6: Commit**

```bash
git add docker-compose.release.yml docs/user/install.md docs/user/INDEX.md
git commit -m "feat(deploy): a compose stack a user without Postgres can run" --trailer "User-visible: Install Narrare with docker compose and no source checkout."
```

---

### Task 5: The Unraid template

**Files:**
- Create: `deploy/unraid/narrare.xml`
- Test: `app/kernel/db/tests/test_unraid_template.py`
- Modify: `docs/user/install.md` (Unraid section)

**Interfaces:**
- Consumes: `REQUIRED_EXTENSIONS`-unrelated; the variable names from Task 1.

- [ ] **Step 1: Write the failing test**

```python
TEMPLATE = Path(__file__).resolve().parents[4] / "deploy/unraid/narrare.xml"

def test_template_names_every_database_variable():
    text = TEMPLATE.read_text()
    for name in ("NARRE_DB_HOST", "NARRE_DB_PORT", "NARRE_DB_NAME",
                 "NARRE_DB_USER", "NARRE_DB_PASSWORD", "NARRE_DB_SSLMODE"):
        assert f'Name="{name}"' in text

def test_secrets_are_masked_and_backups_are_a_path():
    text = TEMPLATE.read_text()
    assert 'Name="NARRE_SECRET_KEY"' in text and 'Mask="true"' in text
    assert 'Name="NARRE_BACKUP_DIR"' in text and "/backups" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `just test-file app/kernel/db/tests/test_unraid_template.py`
Expected: FAIL — the template does not exist.

- [ ] **Step 3: Write the template**

One `<Container>` with `<Name>Narrare</Name>`, `Repository` = the GHCR image,
`Network` bridge, `Privileged` false, port `8000`, Path `/mnt/user/appdata/narrare/backups`
→ `/backups` (`rw`), and the `Config` entries from Step 1 plus `NARRE_SECRET_KEY`
(masked, description "generate once, keep it with your backups") and the port. The
description states the prerequisite: the database must be able to
`CREATE EXTENSION vector`; plain Postgres images cannot. Icon and Category per the
Community Applications conventions.

- [ ] **Step 4: Run to verify it passes, and lint the XML**

Run: `just test-file app/kernel/db/tests/test_unraid_template.py && xmllint --noout deploy/unraid/narrare.xml`
Expected: PASS; `xmllint` silent.

- [ ] **Step 5: Commit**

```bash
git add deploy/unraid/narrare.xml app/kernel/db/tests/test_unraid_template.py docs/user/install.md
git commit -m "feat(deploy): an Unraid template with one container and an external database" --trailer "User-visible: Narrare installs on Unraid as a single container next to an existing Postgres."
```

---

### Task 6: Let the E2E harness attach to a running server

**Files:**
- Modify: `app/kernel/testing/stack.py`
- Test: the existing `app/capabilities/*/e2e/` suites plus one run against a container

**Interfaces:**
- Produces: `NARRE_E2E_ATTACH` — when set to a base URL (`http://127.0.0.1:8080`), the
  stack spawns nothing, resets nothing, and reports that URL as both the API and the
  web origin. `NARRE_DATABASE_URL` still names the database for SQL seeding.

- [ ] **Step 1: Read the harness and write down the two assumptions to break**

Record, in the commit message: the stack spawns `uvicorn` (`_spawn_api`) and resets a
per-run database (`_reset`); and it exposes two origins (API port, web port). Attach
mode must keep the default path byte-identical.

- [ ] **Step 2: Add the mode**

`NARRE_E2E_ATTACH` short-circuits `_prepare`/`_reset`/`_spawn_api`: no `initdb`, no
schema reset, no process. The API base and the web base both become the attach URL.
Seeding that the fixtures do over SQL keeps working against `NARRE_DATABASE_URL`.

- [ ] **Step 3: Prove the default path is untouched**

Run: `just test-e2e`
Expected: every capability suite green, exactly as before (real Postgres on :5433, spawned server).

- [ ] **Step 4: Prove the attach path against the image**

Start the stack of Task 3 Step 4 on port 8080, then run one suite with
`NARRE_E2E_ATTACH=http://127.0.0.1:8080 NARRE_DATABASE_URL=postgresql+asyncpg://narrare:narrare@127.0.0.1:5432/narrare just test-file app/capabilities/writing/e2e/`.
Expected: green, driven by the image's own shell and API on one origin.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/testing/stack.py
git commit -m "test(harness): attach the E2E stack to a running container"
```

---

### Task 7: The release PR owes a version-bump gate, and approval owes the artefact gates

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/_test.yml` only if a reusable needs a new input (prefer not)

**Interfaces:**
- Produces job `version-bump` (release branch only); jobs `container`, `container-e2e`,
  `container-upgrade`, `container-external` (release review only), all aggregated by
  `ci-required`.
- Consumes: Tasks 3 and 6.

- [ ] **Step 1: Make the heavy jobs skip on the release branch**

`lint-types`, `tests`, `frontend`, `build`, `e2e-suites` gain a condition: not a
release PR (`pull_request.head.ref == 'release-please--branches--main--components--narrare'`
and head repo == base repo, the same test `ci.yml` already makes for `--release-pr`).
`ci-required` learns that on a release PR those four skips are legitimate **and** that
`version-bump` must have succeeded.

- [ ] **Step 2: Add the version-bump job**

Cheap job, release branch only: `uv sync --locked`, `pnpm install --frozen-lockfile`
and `just check-generated`. It exists because those are the only things a version bump
can break — and `check-generated` is the gate that has been red on #288 since
2026-10-25 (Task 0 fixes the cause; this job keeps it from coming back).

- [ ] **Step 3: Prove the normal path is unchanged**

Run: `just check`; then push a scratch branch and open a PR that touches one capability.
Expected: the usual jobs run, `version-bump` is skipped, `ci-required` green.

- [ ] **Step 4: Prove the release branch runs only the cheap gate**

Open a PR from a branch named `release-please--branches--main--components--narrare`
in a scratch clone (or dispatch the workflow against it).
Expected: `version-bump` green; the four heavy jobs skipped; `ci-required` green and
naming them as legitimate skips.

- [ ] **Step 5: Add the approval trigger and the four artefact jobs**

`ci.yml` gains `pull_request_review: types: [submitted]`; every existing job gets
`if: github.event_name != 'pull_request_review'`; the aggregator gets a second mode
(review + `state == approved` + release branch) where only the four artefact jobs are
owed. `container` builds the image and runs the smoke; `container-e2e` runs `writing`
via `NARRE_E2E_ATTACH`; `container-upgrade` starts the previous release's image,
seeds a book, then the new image, and compares the chapter text; `container-external`
runs the image against a Postgres service whose app role cannot create extensions and
asserts the refusal sentence, then against a server 18 with the same data.

- [ ] **Step 6: Prove the review mode**

Approve a scratch release PR.
Expected: exactly the four artefact jobs run; `ci-required` is green only when all four
are; a deliberately broken `Dockerfile` on the same branch turns `container` red and
`ci-required` red.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(release): artefact gates run on approval, not on every merge" --trailer "User-visible: A release image is started, migrated and browsed before it is published."
```

---

### Task 8: Publish by promoting the tested digest

**Files:**
- Create: `.github/workflows/publish.yml`
- Modify: `.github/workflows/release-please.yml` (delete the dead `publish` job)
- Modify: `docs/architecture/github.md` (the workflow map row for `publish.yml`)

**Interfaces:**
- Consumes: the `:sha-<head>` image from Task 7 Step 5.

- [ ] **Step 1: Write `publish.yml`**

`on: release: published` + `workflow_dispatch` (inputs: `tag`). `environment: release`
with required reviewers, permissions `contents: write`, `packages: write`,
`id-token: write`, `attestations: write`. Steps: resolve the release's commit →
the `:sha-<head>` tag built on the release PR; `docker buildx imagetools create` to
`:<version>`, `:<major.minor>`, `:latest`; `docker buildx imagetools inspect` for the
digest; SBOM from the registry image (syft, CycloneDX); `actions/attest-build-provenance`
on the digest; keyless Cosign sign; upload the SBOM and a bundle README as release
assets; append the digest and size to the release body.

- [ ] **Step 2: Make the failure path say so**

Any failure after the release exists edits the release body with a warning block
naming the step and the missing tags. No step rebuilds the app image.

- [ ] **Step 3: Prove a missing digest fails loudly**

Dispatch `publish.yml` with `tag: v0.2.0` (a release with no image).
Expected: the promotion step fails with "no such manifest"; `:0.2.0` is not created;
the release body carries the warning.

- [ ] **Step 4: Prove the happy path**

Cut a release from a scratch tag whose `:sha-<head>` image exists.
Expected: `:<version>`, `:<major.minor>`, `:latest` all resolve to the same digest as
`:sha-<head>` (`imagetools inspect` on all four); the release body names the digest.

- [ ] **Step 5: Delete the dead job and update the map**

Remove the `if: false` `publish` job from `release-please.yml` (it is what the platform
design scheduled for deletion), and update the `publish.yml` row in
`docs/architecture/github.md` from *(dormant)* to its trigger and jobs.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/publish.yml .github/workflows/release-please.yml docs/architecture/github.md
git commit -m "feat(release): publish the digest the gates tested" --trailer "User-visible: The published image is the one that passed the gates, not a second build."
```

---

## Self-review

**Spec coverage:** Task 0 is not in the design — it is the defect that kept the
release PR red since 2026-10-25, and it landed on `main` as `afec30ac` before this
plan was executed. `NARRE_DB_*` → Task 1. Extension preflight → Task 2. Image, UID,
`pg_dump` 18, size gate, nightly → Task 3. Compose + install/upgrade/backup docs →
Task 4. Unraid → Task 5. Attach-mode E2E → Task 6. Version-bump gate, release-branch
skips, approval-triggered gates, upgrade gate, external-database gate, `ci-required`
without a ruleset edit → Task 7. Digest promotion, SBOM, attestation, Cosign, failure
path → Task 8. Every design section maps to a task.

**Deliberate gaps:** the `writing` suite is the one artefact suite (design §7 explains
why one and why that one); `affected.py`'s classification of `deploy/` and
`docker-compose.release.yml` is left to the implementer of Task 7 (either class is
defensible; the gates do not depend on it).
