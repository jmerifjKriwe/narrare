# syntax=docker/dockerfile:1

# Narrare is one process: FastAPI serves the API and the built shell. The image
# therefore carries a Python environment and a static bundle, no Node, no uv.
# Base images are pinned by digest — a mutable tag is a build from someone
# else's afternoon — and Dependabot's docker updater moves the pins.

# ── the shell ───────────────────────────────────────────────────────────────
# Node exists only here. The workspace metadata is copied first so that a
# source change does not re-run the install.
FROM node:22-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS web

WORKDIR /src
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY web/package.json web/
RUN corepack enable && pnpm install --frozen-lockfile
# The generated registries in web/lib/generated import capability views as
# ../../../app/capabilities/<name>/web/…; the build reads them, so the context
# needs them beside web/, not only web/.
COPY app/capabilities/ app/capabilities/
COPY i18n/ i18n/
COPY web/ web/
RUN pnpm --dir web build

# ── the Python environment ──────────────────────────────────────────────────
# Its own stage, so uv and the build cache stay out of the shipped image; the
# venv is path-stable because both stages sit on the same base.
FROM python:3.14-slim@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d AS deps

COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /bin/uv
# No bytecode: it adds a quarter of the environment's size to save milliseconds
# of import time on a server that starts once. Copies, not hard links: the venv
# is carried into another stage, where a link to /root/.cache would dangle.
ENV UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# ── the service ─────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# pg_dump must not be older than the server: a 17 client refuses a server 18,
# and a refused dump refuses the upgrade (`app/kernel/db/backup.py`). PGDG's
# current client is the floor; Debian's own is a release behind it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 \
      https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && printf '%s\n' \
      'deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main' \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-18 \
 && apt-get purge -y --auto-remove gnupg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=deps /app/.venv .venv
COPY app/ app/
COPY i18n/ i18n/
COPY alembic.ini ./
COPY --from=web /src/web/dist web/dist

# There is no OS keychain in a container, so the Fernet tier is the only one:
# without NARRE_SECRET_KEY, storing a provider key is refused by name
# (`app/kernel/secrets.py`). Backups are the one writable path, and the dump
# before a migration must survive the container that took it.
ENV NARRE_KEYRING=off \
    NARRE_BACKUP_DIR=/backups
RUN install -d -o 99 -g 100 /backups
VOLUME /backups

ARG VERSION=dev
ARG REVISION=
LABEL org.opencontainers.image.title="Narrare" \
      org.opencontainers.image.description="Local-first, AI-assisted creative writing." \
      org.opencontainers.image.source="https://github.com/jmerifjKriwe/narrare" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

# Unraid's convention, and harmless everywhere else: the app only writes below
# /backups, which the mount's owner decides.
USER 99:100
EXPOSE 8000

# No HEALTHCHECK: no route proves the database, and a check that passes while
# the database is unreachable is worse than no check. The gates prove liveness.
CMD [".venv/bin/python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
