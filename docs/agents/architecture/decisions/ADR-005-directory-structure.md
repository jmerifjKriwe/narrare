# ADR-005 — Module Structure and Ownership Boundaries

> **Status:** ✅ Accepted
> **Date:** project-init
> **Deciders:** Architecture Agent
> **Supersedes:** —

---

## Context

The previous codebase had a service layer but no clear ownership boundaries.
`writing/service.py` imported from `kb/helpers.py`, which imported from
`context/assembler.py`, which used `agents/model.py` directly.
Cross-domain imports were uncontrolled, making it impossible to understand
the impact of any change without tracing the entire import graph.

The `core/` vs `apps/api/` split existed in concept but was violated in practice:
CLI and MCP tools imported from `apps/api/` which pulled in FastAPI/SQLAlchemy.

## Decision Drivers

- Cross-domain impact of changes must be predictable
- `core/` must be usable without HTTP or database context
- MCP/A2A adapters must be addable without touching `apps/api/` internals
- Every domain module must be self-contained enough to be developed independently

## Decision

Each domain module in `apps/api/narrare/` owns its own models, schemas,
contracts, repository, service, and router. Cross-domain communication
goes through public `__init__.py` exports only — never through internal submodules.

`core/` has zero knowledge of HTTP, users, or SQLAlchemy sessions.
`apps/` has zero business logic that isn't in a service class.

Full structure in `DIRECTORY_STRUCTURE.md`.

## Consequences

**Positive:**
- Domain impact is bounded — changing `kb/` internals cannot break `writing/`
  unless the public interface changes
- `core/` is usable by MCP, CLI, or tests without pulling in the full API stack
- New domains can be added without touching existing code

**Negative / Tradeoffs:**
- Some duplication — each domain has the same file structure even if small
- Shared schemas require a decision: put in `core/schemas/` or keep per-domain

**Constraints introduced:**
- RULE-05 and RULE-06 in `CONSTRAINTS.md`

## Review Trigger

- [ ] When MCP adapter is built — verify `core/` is truly self-contained
