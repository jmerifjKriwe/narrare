# ADR-100 — v2 greenfield rebuild

> **Status:** ✅ Accepted
> **Date:** 2026-10-21
> **Deciders:** Product owner
> **Supersedes:** ADR-001 through ADR-099 (all prior ADRs; archived in git history)

---

## Context

By 2026-10-21 the v1 application had grown to 321,912 source lines under `apps/`
and `packages/`, 95 just recipes, 43 pre-commit hook ids, 33 check scripts, 100
ADRs and 23 architecture rules. The effort of shipping a feature scaled with the
governance mass around it, not with the feature. Porting that mass would have
carried the disease into the rebuild.

## Decision Drivers

- Effort per feature must not scale with governance mass.
- Only four capabilities earn their keep today: writing, knowledge base, chat,
  setup. Everything else is deferred with a reason (spec §11).
- Enforcement is social, not technical (spec §8).

## Decision

Rebuild as Narrare v2 on a kernel with four capabilities under the authority of
the [v2 architecture spec](../../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md),
and cut over in one commit (`48e7d7d4`): the old application, its tests and its
gates are deleted with no shim. Git history is the archive. The new budget: 22
just recipes, 6 git hooks, 1 check script, at most 5 standing rules
(`docs/_shared/CONSTRAINTS.md`), at most 15 ADRs — this record is the first of
the new series.

All prior ADRs are superseded: their subjects either lost their subject matter in
the cutover (mem0, TaskIQ, Redis, pyrefly, series, stats, VRT, adoption and
drift gates) or are re-decided by the spec itself. `docs/features/` remains as
the product-history record of the v1 era; its links to ADRs point into git
history.

## Consequences

- The v2 spec, not any ADR, is the single architecture authority.
- A decision that outlives the spec's own text gets a new ADR, numbered from 100
  upward, following `_TEMPLATE.md`.
- The old ADR corpus stays readable at `48e7d7d4^`.
