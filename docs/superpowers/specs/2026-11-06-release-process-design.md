# Release process — design

2026-11-06 · product owner: hosting is the majority case; Unraid is mandatory for
the owner; PostgreSQL + pgvector stays the one storage engine.

## Intent

A merge to `main` is not a release, and a tag is not an artefact. The release
process exists to make one statement true: **what a user pulls is byte-identical to
what the gates tested.** Hosting is the main consumer — it deploys the same image
that self-hosters use — so the container is not a convenience for a minority fork
of the product, it is the deployment unit.

Release-please already owns the version: it writes every copy (`pyproject.toml`,
`app/kernel/version.py`, both `package.json`, `openapi.json`, `uv.lock`), opens the
release PR, and tags on merge. This design adds nothing there.

## Anti-goals

- **No installer for Windows.** Rung 3 of ADR-101 stays unbuilt until a real user
  cannot install rung 1. A wheel probe (see below) is research, not product.
- **No all-in-one image** (application and database in one container). It would be a
  third artefact to build, test and version, for a user who is not the owner.
- **No Docker Desktop path.** An installer that installs a container runtime costs
  the user 2–10 GB of VM and userland for a writing application.
- **No second storage engine.** SQLite was measured and rejected (five engine-specific
  sites, but two dialects forever, or a storage decision that also changes hosting).

## Constraints (measured 2026-11-06)

- One process serves the product: FastAPI serves `web/dist`, so the frontend needs no
  second runtime in production (`app/api/main.py`).
- Schema: Alembic history; `prepare_database` runs in the lifespan, takes a `pg_dump`
  before any upgrade with pending revisions, and refuses rather than guesses
  (`app/kernel/db/migrate.py`, `backup.py`). The dump needs `pg_dump` on `PATH`.
- `NARRE_BACKUP_DIR` defaults to `./backups`; in a container that is the ephemeral
  layer.
- Provider API keys: OS keychain first, `NARRE_SECRET_KEY` (Fernet) as the fallback
  (`app/kernel/secrets.py`). A container has no keychain.
- `NARRE_DATABASE_URL` is the only database variable today, with a dev default that
  points at `localhost:5432/narrare_v2_dev` (`app/kernel/db/session.py`).
- CI: `changes` narrows a PR to affected capability suites and deliberately resolves
  a release PR to *no* suite, because its tree equals `main`'s (`scripts/affected.py`,
  `RELEASE`). `tests`, `frontend`, `build` and `lint-types` still run on that PR.
- Image payload: app 6 MB, `web/dist` 1.5 MB, production Python deps ~130 MB,
  `python:3.14-slim` ~150 MB. 182 MB of the local `.venv` is Playwright and Pyright.

## The shape: one image, three surfaces

Separated by who provides the database, not by software:

| Surface | Who | Database |
|---|---|---|
| `ghcr.io/<owner>/narrare:<version>` | hosting, Unraid, anyone with Postgres | external, via `NARRE_DB_*` |
| `docker-compose.release.yml` | anyone without Postgres | bundled `pgvector/pgvector:pg17` |
| `deploy/unraid/narrare.xml` | Unraid | external, one container |

The compose file is a convenience wrapper, not a second product. The Unraid template
is a second *surface*, not a second artefact.

## Components

### 1. Database configuration (`NARRE_DB_*`)

Decided: discrete parts are the source, `NARRE_DATABASE_URL` stays an override.

- `NARRE_DB_HOST`, `NARRE_DB_PORT` (default 5432), `NARRE_DB_NAME`, `NARRE_DB_USER`
  required together; `NARRE_DB_PASSWORD` optional (empty = trust auth);
  `NARRE_DB_SSLMODE` optional and, when unset, absent from the URL.
- Precedence: `NARRE_DATABASE_URL` → parts → the existing dev default.
- The URL is built with `sqlalchemy.URL.create`, never by string concatenation
  (passwords containing `@`, `:`, `#`; IPv6 hosts in brackets).
- Resolution lives in exactly one place (`session.py`); `init.py`, `prepare_database`
  and `alembic/env.py` keep receiving a finished URL.
- One startup log line names the source: `database NARRE_DB_* → narrare@postgres:5432/narrare`
  or `database default (localhost dev)` — the connection, never the password.
- Incomplete parts refuse at startup, naming the missing variables. Empty string is
  treated as unset.
- `PG*` (libpq) names were rejected: they collide with a developer machine's settings
  for a different database, even though `pg_dump` would read them for free.

### 2. The image

Multi-stage `Dockerfile`:

- `web` stage: `node:22-slim`, `pnpm install --frozen-lockfile`, `pnpm --dir web build`
  → `/src/web/dist`.
- runtime stage: `python:3.14-slim`, `uv` from its published image, `uv sync --no-dev`,
  then `COPY app/ i18n/ alembic/ alembic.ini pyproject.toml uv.lock .` and
  `COPY --from=web .../dist ./web/dist`.
- `postgresql-client` installed: without `pg_dump` the first upgrade with pending
  revisions refuses to migrate (`MigrationRefused`). The client must not be older
  than the server — a `pg_dump` 17 against a server 18 refuses — so the client comes
  from PGDG at the newest version the project supports, not from the base image's
  distribution.
- `ENV NARRE_KEYRING=off` — the probe must not race a backend that does not exist.
- `ENV NARRE_BACKUP_DIR=/backups`.
- Non-root user, `EXPOSE 8000`, bind `0.0.0.0`.
- `CMD` runs `uvicorn` from the synced environment (`uv run --no-sync`), not
  `uv run`, which would re-resolve at start.
- OCI labels: `version`, `revision`, `source`.
- Size gate: content size ≤ 450 MB. Measured composition of the first real
  build: the Debian `python:3.14-slim` base ~200 MB, the Python environment
  ~105 MB, the PostgreSQL client ~76 MB (55 MB of it perl, which Debian's
  packaging of the client requires), the app and its bundle ~6 MB.

### 3. `docker-compose.release.yml`

`app` + `pgvector/pgvector:pg17`, named volumes for the database and for `/backups`,
`depends_on: condition: service_healthy`, healthchecks on both, `restart:
unless-stopped`, configuration from a user-owned `.env` (never committed). The app
image is referenced as `:latest` with the version pinned in the comments and the
install page — a version literal here would be a sixth copy for release-please to
miss. Operation by digest is documented for anyone who wants immutability.

### 4. `deploy/unraid/narrare.xml`

One container, no compose. Fields: `NARRE_DB_HOST/PORT/NAME/USER/PASSWORD` (password
masked), `NARRE_SECRET_KEY` (masked, generated once, kept with the backups),
`NARRE_BACKUP_DIR=/backups` with a host path mapping, the published port, and an
icon. The description states the prerequisite in one sentence: **the database must be
able to `CREATE EXTENSION vector`** — plain Postgres images cannot.

### 5. Startup diagnostics

- `prepare_database` gets a preflight: query `pg_available_extensions` for `vector`,
  `pg_trgm`, `unaccent` and refuse with one sentence naming what is missing and what
  to do. Today a missing binary surfaces as a raw SQLAlchemy traceback, which is the
  most likely first-contact failure.
- The refusal is the only channel: the UI is served by the process that failed, so a
  startup dependency error can never be shown in the browser. Do not add a
  "diagnostic mode" server.

### 6. Release workflow

- **Nightly** (only when `main` moved since the last successful one, as today): build
  the image and smoke it — empty database, entrypoint, migrations, `GET /` and one
  asset. No push: GHCR stays clean, and the build cache (`type=gha`) keeps the
  release-time build short. A broken `Dockerfile` is found within a day, on `main`,
  through the existing `ci/nightly` issue instead of a blocked PR.
- **Release PR update** (every merge): only a version-bump gate — `uv sync --locked`,
  `pnpm install --frozen-lockfile` and `test_committed_openapi_document_matches_the_app`.
  The heavy jobs are legitimate skips for this branch in `ci-required`: the tree
  differs from `main` only in the version copies, and those three are the only things
  a version bump can break.
- **Release PR approval** (`pull_request_review`, `state == approved`): the artefact
  gates, reported through `ci-required` — the ruleset's only required check, so no
  ruleset edit (`docs/architecture/github.md`). The image is built here and kept as
  `:sha-<head>` until the release.
- **Reconciliation with the recorded platform design** (`2026-11-05-github-platform-design.md`):
  `publish.yml` keeps its trigger (`release: published`), its `environment: release`
  approval, provenance, SBOM, Cosign and release assets. What changes is its first
  step: it promotes the digest built and tested on the release PR instead of building
  a second image. Attestation and signature attach to the promoted digest, so the
  published artefact is the tested one.
- **Merge:** release-please tags and writes the GitHub Release; a promotion job
  retags the tested digest (`docker buildx imagetools create`) as `:<version>`,
  `:<major.minor>` and `:latest` — no rebuild — and appends the digest, the image
  size and the database extension versions to the release notes.
- **Degraded path:** if the PR image is gone (retention), the promotion job fails
  rather than rebuilding, because a rebuild is not the tested artefact.
- Release notes carry two generated lines: the schema revision delta (from
  `alembic heads` against the previous tag) and whether a pre-migration dump will be
  taken. Breaking changes stay hidden in the version number by
  `bump-minor-pre-major`; the notes are where they are visible.

### 7. E2E against the artefact

The capability suites are the only definition of "works" this project has. They run on
the tree for every affected PR and all of them nightly; **one** of them runs against
the image, because the artefact question is narrower: does the UI served from
`web/dist`, the API and the first-boot migration work inside the container? The other
seven re-test the application, which `main` already proved.

The chosen suite is `chat`: it drives the shell from `web/dist`, the API, the database,
an embedding-backed retrieval and a streamed answer, all on one origin, and it has no
outage test. That last point decides it — `writing` and `knowledge` stop and restart the
API process to simulate an unreachable backend, which a container cannot offer a test
process; attached, eighteen `writing` tests fail for that reason alone, and a gate that
skips them is not the gate this design promised.

The harness needs one new mode (`app/kernel/testing/stack.py`): **attach** — do not
spawn uvicorn, do not reset the database, take both origins from the environment.

- One container with its own Postgres service, so the suite meets a virgin application
  and the container's own first boot runs the migrations. No reset path exists against
  the container, and none is wanted: the first boot is what ships.
- The API and the shell share one origin in the image (`app/api/main.py` serves
  `web/dist`), where the harness assumes two (uvicorn and Vite). Attach mode collapses
  both to the container's port.
- Preconditions that the current fixture seeds through SQL still do so against the
  suite's database; nothing is seeded through a test-only route.
- The mode is opt-in and the existing path is unchanged: eight capability suites
  depend on this harness, and a regression there reddens every one of them.

### 8. Documentation

A user-facing install page under `docs/user/` (only `INDEX.md` exists today) covering
the three surfaces: compose with bundled Postgres, own pgvector Postgres (the
`CREATE EXTENSION vector` prerequisite and the privileges it needs), Unraid template;
then upgrade (backup, pull, restart, where the pre-migration dumps land) and restore
(`pg_restore` into a fresh database).

## Gates

| Gate | Proves | Blocks |
|---|---|---|
| image content size ≤ 450 MB | no dev tooling shipped | the release |
| container starts on an empty database | entrypoint, migrations, extension preflight | the release |
| `GET /` and one `/assets/*.js` | the shell is served from the image, 200 not 404 | the release |
| seed via API, restart, seed still readable | the bundled-Postgres topology works | the release |
| image against a separately provisioned pgvector server whose app role cannot create extensions, plus the incomplete-`NARRE_DB_*` refusal | the hosting and Unraid topology, the only new runtime code | the release |
| the `chat` suite's Playwright run against the container | the UI, the API and the migrations inside the artefact, on one origin | the release |
| previous version + seeded book → new version → same chapter text | upgrade path with dump | the release (from the second image on; the first image has no predecessor to pull) |
| digest recorded in the release notes | what you pull is what was tested | approval |

## Decisions

Decided with the product owner while planning:

- Discrete `NARRE_DB_*` over `PG*`; `NARRE_DATABASE_URL` stays the override.
- One app-only image; the compose file supplies the database. No all-in-one image.
- `pg_dump` ships in the image; dumps go to `/backups`.
- The Unraid template lives in the repository and is versioned with the release.
- **The image is built and tested on the release PR; the published image is that
  digest, promoted by re-tagging.** No second build after the tag.
- `linux/amd64` only. arm64 is a later decision with its own build and gates, not a
  silent second target.
- Unraid runs as fixed UID/GID 99:100; no PUID/PGID, no root entrypoint.
- PostgreSQL client 18 from PGDG; gates against 17 (bundled compose) and 18
  (external server). A client older than the server refuses to dump, and a refused
  dump refuses the upgrade.
- **The window between `release: published` and a promoted image is accepted.**
  `:latest` only moves on a successful promotion; a failed promotion edits the
  release notes with the failure instead of leaving the page silent.
- A release PR still owes no browser suite for its *diff* (its tree is `main`'s); it
  owes the capability suites against the *artefact*, which is a different question.
- Build and smoke the image in the nightly (cache warm, nothing published) and run
  the full artefact gates on approval of the release PR. No image build on ordinary
  PRs or on merges.

## Left to the builder

- Exact Dockerfile layering and build-cache strategy; which files enter the context.
- Healthcheck command (there is no `/health` route today; decide between adding a
  `SELECT 1` route and probing `/`).
- How the promotion job finds the tested digest (PR comment, job artefact, or
  `:sha-<head>` lookup), and how a failure edits the release notes.
- Whether the preflight lives in `prepare_database` or beside it.
- The Unraid template's category, icon and exact field order.
- How the harness seeds a capability's preconditions when it cannot reset: which
  fixtures call `reset_schema` today and what they do in attach mode.
- Whether the nightly's container job is new or folded into the existing `build` job.
- Which `affected.py` class `deploy/` and `docker-compose.release.yml` join: today
  `deploy/` is unknown (all suites) and `docker-compose*.yml` is inert.
