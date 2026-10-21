# Narrare — Standing Constraints

The five rules every change obeys. The architecture authority — structure,
boundaries, the governance budget and the reasoning behind all five — is the
[v2 architecture spec](../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md).

1. **One capability is one folder** under `app/capabilities/<name>/`. A capability
   never imports another capability; shared domain lives in `app/kernel/`.
2. **A capability is done only with a green E2E** that drives the real UI, the real
   backend and the real database. The only permitted fake is the LLM provider at
   its boundary, and it is a catalog entry chosen by configuration, not a test
   branch.
3. **No side effect in the request path** beyond the request's own transaction.
4. **Every user-owned row carries `user_id`**; data access goes through the scoped
   repository base.
5. **English in code, tests and developer documentation; user-visible text in en,
   de and fr** through the i18n catalog. A missing key is a build error.

Adding a sixth rule, a registry, a check script, a hook, a required field or a
mandatory document is forbidden by default: report `NEEDS-APPROVAL` with the
failure it prevents, the effort it creates per change, and the cheaper
alternative (spec §8).
