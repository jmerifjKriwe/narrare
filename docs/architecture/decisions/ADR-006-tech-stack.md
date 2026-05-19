# ADR-006 — Technology Stack

> **Status:** ✅ Accepted
> **Date:** project-init
> **Deciders:** Architecture Agent
> **Supersedes:** —

---

## Context

A complete rewrite requires explicit technology choices. Several choices from
the previous codebase are retained; some are changed; some are new.
The full rationale lives in `TECH_STACK.md`. This ADR records the key
decisions that had real alternatives considered.

---

## Key Decisions

### Python 3.14 (not 3.12 or 3.13)

3.14 is stable as of April 2026. New typing features (`TypeVar` defaults,
`@override`) reduce boilerplate. No reason to use an older version for a
new project. Risk: some stubs not yet updated — mitigated by
`reportMissingTypeStubs = false` in pyright config.

### pyright (not mypy)

pyright is faster, has better inference for modern Python typing patterns,
and is the type checker used by the VS Code Python extension — meaning
developers see errors inline without running a separate command.
mypy is mature but slower and less accurate on Python 3.14+ type features.

### TipTap v3 (not ProseMirror directly, not Slate, not Lexical)

TipTap wraps ProseMirror with a React-friendly extension API. The extension
model is exactly what we need for plugging in AI features without modifying
the core editor. Slate has a good API but less mature extension ecosystem.
Lexical (Meta) is newer and less proven for our use case.

### pydantic-ai (not LangChain, not raw SDK)

LangChain has too many abstractions that we don't need and a history of
breaking changes. Raw SDK calls have no type safety, no retry, no structured
output. pydantic-ai gives us structured output via Pydantic models,
multi-provider support, and a clean async API — without the LangChain overhead.

### PostgreSQL + pgvector (not separate vector DB)

We already need PostgreSQL for relational data. pgvector gives us semantic
search without a second database to operate, back up, and monitor.
At our expected scale, pgvector performance is more than sufficient.
If we outgrow it, migration to a dedicated vector DB is possible — but
we should not add operational complexity speculatively.

### release-please (not semantic-release, not manual)

release-please integrates with GitHub Actions, uses Conventional Commits
(which we already require), and produces clean changelogs automatically.
It opens a PR for each release rather than pushing directly to main —
giving one last review opportunity before a version is cut.

### Conventional Commits (enforced)

Enforced via pre-commit hook (`check_commit_message.py`).
Required for release-please to work. Also produces a readable git log
that agents can parse when understanding project history.

---

## What Was Explicitly Rejected

| Technology | Rejected because |
|-----------|-----------------|
| LangChain | Too much magic, version churn, abstractions we don't need |
| SQLModel | Conflates ORM models with Pydantic schemas — confusing at boundaries |
| mypy | Slower than pyright, weaker on modern Python typing |
| Separate vector DB | Operational overhead not justified at our scale |
| Go | No pydantic-ai, no mem0, no pgvector ecosystem — too much lost |
| MongoDB | Our data is relational; forcing it into documents creates problems |

## Review Trigger

- [ ] When pydantic-ai hits v2.0 (evaluate breaking changes)
- [ ] When TipTap v4 releases (evaluate migration)
- [ ] At 6-month mark — reassess pgvector performance
