# Architecture Decision Records — Index

> One-time architecture decisions, newest first. Standing rules live in
> [`docs/_shared/CONSTRAINTS.md`](../../_shared/CONSTRAINTS.md); the architecture
> authority is the [v2 spec](../../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md).
> New records follow [`_TEMPLATE.md`](_TEMPLATE.md) and are numbered from 100 up.

| ADR | Decision | Status | Date |
|-----|----------|--------|------|
| [ADR-102](ADR-102-provider-profiles-and-key-storage.md) | Providers are per-user profiles with per-task assignment and two key-storage tiers — the hand-edited catalog is gone | 🔄 | 2026-10-28 |
| [ADR-101](ADR-101-local-service.md) | Local-first means a local service on Postgres + pgvector — single-tenant, fixed local user, packaging ladder; SQLite+sqlite-vec is the last resort | ✅ | 2026-10-22 |
| [ADR-100](ADR-100-v2-greenfield-rebuild.md) | v2 greenfield rebuild — old app, tests and gates deleted in one cutover; the spec is the authority; supersedes ADR-001–099 | ✅ | 2026-10-21 |
