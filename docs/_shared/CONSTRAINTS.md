# Narrare — Standing Constraints

The five rules every change obeys, the shape of a capability, and where to read
what. The architecture authority — reasoning, boundaries and the governance
budget — is the [v2 architecture spec](../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md).

## The five rules

1. **One capability is one folder** under `app/capabilities/<name>/`. A capability
   never imports another capability; shared domain lives in `app/kernel/`.
2. **A capability is done only with a green E2E** that drives the real UI, the real
   backend and the real database. The only permitted fake is the LLM provider at
   its boundary: a provider profile of kind `fake`, chosen by configuration, never
   a test branch.
3. **No side effect in the request path** beyond the request's own transaction.
4. **Every user-owned row carries `user_id`**; data access goes through the scoped
   repository base.
5. **English in code, tests and developer documentation; user-visible text in en,
   de and fr** through the i18n catalog. A missing key is a build error.

## The shape of a capability

- Its facts are in `capability.yaml` — `id`, `title`, `path`, `needs`, `nav` — and
  a field exists only while two generated views read it. Views are written by
  `just generate` and never edited by hand.
- Its code is `router.py` (delegates immediately), `service.py` (the logic),
  `repository.py` where it owns tables, `schemas.py`, `tests/`, `e2e/`, and its UI in
  `web/` with the `routes.tsx` the shell mounts.
- Imports point one way: `api → capabilities → kernel`. A capability reaches the
  shell through `@shell/*` — the shared UI lives there; the shell reaches a
  capability only through the generated tables.
- A provider is a profile row (`fake` or `openai-chat`), assigned per user and task
  in `/settings`. A new vendor on that API shape needs no code; a new API shape is
  an adapter plus one `PROFILE_KINDS` value. Keys and their two storage tiers are
  decided in [ADR-102](../architecture/decisions/ADR-102-provider-profiles-and-key-storage.md).
- A second data store, a global store or a migration tool crosses a boundary and
  needs the product owner's explicit approval (spec §8). The migration tool's
  approval exists: it is recorded in
  [ADR-103](../architecture/decisions/ADR-103-schema-migrations.md).

## Read this in this order

1. [`README.md`](../../README.md) — what the product is, and how to run it.
2. This page — the rules and the shape.
3. One capability folder end to end: `app/capabilities/setup/` (the smallest), then
   `app/capabilities/writing/` for the prompt and streaming path.
4. [`TESTING.md`](../../TESTING.md) — the layers, the gates and how to run them.
5. The [architecture spec](../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md)
   — why, not how — then the [ADRs](../architecture/decisions/INDEX.md) for the
   choices that are expensive to reverse. The dated designs under
   `docs/superpowers/specs/` are the records of finished work packages; read one
   only when a comment points at it.

## Changing a rule

Adding a sixth rule, a registry, a check script, a hook, a required field or a
mandatory document is forbidden by default: report `NEEDS-APPROVAL` with the
failure it prevents, the effort it creates per change, and the cheaper
alternative (spec §8).
