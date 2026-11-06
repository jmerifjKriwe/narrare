# Installing Narrare

Narrare is one container image. It serves the interface and the API on port
`8000`, and it needs a PostgreSQL with the `vector` extension. Where that
database comes from is the only choice to make:

| Your situation | Use |
| --- | --- |
| You want it running in a minute | [the compose installation](#the-compose-installation) — the database comes with it |
| You already run a Postgres | [your own database](#your-own-database) — one container, four values |
| You run Unraid | [Unraid](#unraid) — one template, one container |

Every path needs one secret and one writable directory:

```bash
# Generate the key once. It encrypts the provider keys you store in the app.
# A new key makes the old ones unreadable, so keep it with your backups.
docker run --rm --entrypoint /app/.venv/bin/python \
  ghcr.io/jmerifjKriwe/narrare:latest \
  -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## The compose installation

For a machine without a PostgreSQL of its own. Download
`docker-compose.release.yml` from the repository root, put it in an empty
directory, and write a `.env` beside it:

```dotenv
NARRE_SECRET_KEY=<the key you generated above>
# Optional: change the port, or the database credentials.
# NARRE_PORT=8000
# NARRE_DB_PASSWORD=narrare
```

```bash
docker compose -f docker-compose.release.yml up -d
```

Open <http://localhost:8000>. Two volumes are created: `pgdata` holds the
database, `backups` holds the dump taken before every schema upgrade. Both
belong to you — a copy of them is a complete backup.

## Your own database

One container. Narrare speaks to the database through six variables, of which
three are required:

| Variable | Meaning |
| --- | --- |
| `NARRE_DB_HOST` | the server's hostname or IP, as seen from the container |
| `NARRE_DB_NAME` | an existing, empty database |
| `NARRE_DB_USER` | a user that may create tables **and extensions** in it |
| `NARRE_DB_PASSWORD` | optional; a server with trust authentication needs none |
| `NARRE_DB_PORT` | optional, defaults to `5432` |
| `NARRE_DB_SSLMODE` | optional: `disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full` |

`NARRE_DATABASE_URL` (a full URL) overrides all six if you prefer one value.

**The database must be able to provide `vector`, `pg_trgm` and `unaccent`.** A
plain `postgres:17` image cannot: it ships no pgvector. Check before you start:

```sql
SELECT name FROM pg_available_extensions WHERE name IN ('vector', 'pg_trgm', 'unaccent');
```

Three rows means Narrare can start. If Narrare is told to start against a
server that cannot provide them, it refuses at startup and names the missing
extension; it does not run half-configured.

```bash
docker run -d --name narrare --restart unless-stopped -p 8000:8000 \
  -e NARRE_DB_HOST=192.168.1.10 \
  -e NARRE_DB_NAME=narrare \
  -e NARRE_DB_USER=narrare \
  -e NARRE_DB_PASSWORD='…' \
  -e NARRE_SECRET_KEY='…' \
  -v /srv/narrare/backups:/backups \
  ghcr.io/jmerifjKriwe/narrare:latest
```

## Unraid

The template lives in the repository at `deploy/unraid/narrare.xml`. Add it
through **Docker → Add Container**, or paste its address into the template
field. It asks for exactly the variables above, plus `NARRE_SECRET_KEY` and a
host path for `/backups` (for example
`/mnt/user/appdata/narrare/backups`).

The database is *not* part of the template: point `NARRE_DB_HOST` at the
container name of your Postgres (both containers on the same Docker network)
or at the host's address. That Postgres must have pgvector — the common
`postgresql16` template does not, so use a pgvector image or add the extension.

## Upgrading

The application migrates its own schema at startup, and before it applies any
revision it writes a `pg_dump` into `/backups`. Nothing else is required:

```bash
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
# or, for a single container:
docker pull ghcr.io/jmerifjKriwe/narrare:latest && docker restart narrare
```

Two things to know:

- **Take your own copy first.** The automatic dump runs only when there are
  pending revisions and the database already holds tables; it is a safety net,
  not a backup plan.
- **A failed dump stops the upgrade.** If `pg_dump` cannot write (a wrong
  owner on `/backups`, a full disk), Narrare refuses to migrate and says which
  path failed. That is deliberate: an upgrade without a restorable copy is the
  one thing this application will not do silently.

## Restoring

```bash
# What is there: one custom-format archive per upgrade that had work to do.
ls /srv/narrare/backups        # narrare-20261106T180300123456.dump
```

`pg_restore` needs to reach the database, and the image carries version 18 of
it (new enough for every server from 16 up). Run it from the image, on the
network your database is on, with the backups mounted read-only:

```bash
docker run --rm --network narrare_default \
  -v /srv/narrare/backups:/backups:ro \
  --entrypoint pg_restore ghcr.io/jmerifjKriwe/narrare:latest \
  --clean --no-owner \
  --dbname='postgresql://narrare:PASSWORD@postgres:5432/narrare' \
  /backups/narrare-20261106T180300123456.dump
```

`--clean` replaces what the dump contains, so restore into the database you
mean to overwrite. `narrare_default` is the compose project's network; for a
single container, use the network your PostgreSQL is on and its container name
or host.
