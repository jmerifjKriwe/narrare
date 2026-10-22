# ADR-101 — Local-first means a local service, not an embedded database

> **Status:** ✅ Accepted
> **Date:** 2026-10-22
> **Deciders:** Product owner
> **Related:** [ADR-100](ADR-100-v2-greenfield-rebuild.md), spec §9 (tenancy seam), §13 (open decisions)

---

## Context

The spec leaves the hosting model open (§13) with the trigger "early in the build,
before the auth UI is designed". The auth boundary is now built as a fixed local
user (`app/kernel/auth/`), the storage core is PostgreSQL 17 + pgvector, and the
first question every distribution decision runs into is what "local-first" obliges
the *user's machine* to run.

## Decision Drivers

- Local-first is the product promise: the user's writing stays on the user's disk.
- The retrieval core (pgvector ANN, SQL joins between prose and embeddings, the
  whole 63-test integration corpus and 7 E2E suites) is proven against Postgres.
- No end user exists yet; packaging pain is hypothetical, a storage rewrite is not.
- The tenancy seam (spec §9) keeps single- and multi-tenant possible at the data
  layer either way.

## Options Considered

### Option A — Multi-tenant hosted service

Operated Narrare, users get accounts.

**Pros:** no local runtime at all; one deployment.
**Cons:** contradicts the product's own positioning; drags in hosted auth,
metering and ops; the local-user auth boundary would be rewritten.

### Option B — Embedded single binary (SQLite + sqlite-vec)

Swap storage so the app is one file with no server.

**Pros:** simplest possible distribution.
**Cons:** weaker ANN indexes and a weaker async SQLAlchemy story; a rewrite of
`kernel/retrieval.py` and revalidation of the entire test corpus — paid now for
a pain nobody has reported.

### Option C — Single-tenant local service on Postgres + pgvector

One backend process plus Postgres on the user's machine; the UI is the browser
against `localhost`. Postgres arrives by container today.

**Pros:** keeps the proven core and the exact dev/test/prod shape; local-first
holds by construction (the data directory belongs to the user).
**Cons:** the machine must run Postgres; how that is packaged is still work.

## Decision

**We choose Option C.** Narrare is a single-tenant local service: the user's data
lives in PostgreSQL with pgvector on their disk, served by one local backend, and
the auth boundary stays the fixed local user — that row of spec §13 is resolved,
not deferred.

Packaging ladder, each rung only when the previous one demonstrably fails:

1. **Now / alpha:** the existing compose stack (`just dev` shape) for
   self-hosting early users.
2. **Non-technical users:** an installer or launcher that runs the same stack;
   a Docker dependency is acceptable. A desktop shell (Tauri) bundling Postgres
   binaries only if the Docker requirement proves unacceptable in practice.
3. **Last resort:** Option B. The swap stays cheap because the provider
   boundaries and `kernel/retrieval.py` confine it — that is why those
   boundaries exist — but it is not taken preemptively.

## Consequences

**Positive:** one storage engine everywhere; the RAG core keeps its indexes and
its proven tests; no auth work beyond the local user.

**Negative / Tradeoffs:** local-first obliges a local Postgres; the distribution
work (installer/launcher) is deferred, not deleted.

**Constraints introduced:** schema changes keep going through the db init (see
ADR-100 era ruling, `app/kernel/db/init.py`); any capability that needs storage
uses the scoped repositories, never its own engine.

## Review Trigger

- [ ] When the first non-developer user cannot install the compose stack.
- [ ] When a distribution channel (app store, single-binary requirement) forbids
      Postgres outright.
- [ ] When a hosted/multi-tenant offering is seriously considered.
