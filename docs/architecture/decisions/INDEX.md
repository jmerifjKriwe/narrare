# Architecture Decision Records — Index

> **How to use this index:**
> Load this file to get an overview. Load individual ADR files only when you need
> the full reasoning. This keeps the context window clean.
>
> Location: `docs/architecture/decisions/INDEX.md`
> Maintained by: Architecture Agent

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Accepted — in effect |
| 🔄 | Proposed — under discussion |
| ⛔ | Superseded — replaced by newer ADR |
| 🗄️ | Deprecated — no longer relevant |

---

## Decision Log

| ID | Title | Status | Date | Affects |
|----|-------|--------|------|---------|
| [ADR-001](ADR-001-llm-gateway.md) | Single LLM Gateway for all model calls | ✅ | init | `core/llm/` |
| [ADR-002](ADR-002-prompt-system.md) | Unified prompt system replacing three parallel implementations | ✅ | init | `core/prompts/` |
| [ADR-003](ADR-003-contracts-first.md) | Protocol-first development — contracts before implementation | ✅ | init | all domains |
| [ADR-004](ADR-004-file-size-limits.md) | Hard file size limits with enforcement | ✅ | init | all files |
| [ADR-005](ADR-005-directory-structure.md) | Module structure and ownership boundaries | ✅ | init | all modules |
| [ADR-006](ADR-006-tech-stack.md) | Technology choices and explicit exclusions | ✅ | init | all |
| [ADR-007](ADR-007-taskiq.md) | TaskIQ for background task processing | ✅ | init+2 | `core/tasks/` |
| [ADR-008](ADR-008-frontend-stack.md) | Frontend architecture: fetch, Tailwind v4, TanStack Query, shadcn/ui | ✅ | 2026-05-12 | `packages/web/` |
| [ADR-009](ADR-009-security-modernization.md) | Security Stack Modernization (argon2 + fastapi-limiter) | ✅ | 2026-05-12 | `auth/`, `_app/middleware.py` |
| [ADR-010](ADR-010-observability.md) | Observability Strategy (OpenTelemetry + Langfuse) | ✅ | 2026-05-12 | `core/llm/`, `_app/middleware.py`, observability |
| [ADR-011](ADR-011-content-versioning.md) | Content Versioning for Chapters | ✅ | 2026-05-12 | `chapters/`, DB schema |
| [ADR-012](ADR-012-event-driven.md) | Event-Driven Architecture (Redis Pub/Sub) | ✅ | 2026-05-12 | `core/events/`, TaskIQ integration |
| [ADR-013](ADR-013-i18n.md) | Internationalization Architecture | ✅ | 2026-05-12 | `packages/i18n/`, `packages/web/lib/i18n/` |
| [ADR-014](ADR-014-tdd-agent-workflow.md) | TDD Agent Workflow & Regression-First Fixes | ✅ | 2026-05-14 | Agent System, Testing |
| [ADR-015](ADR-015-agents-first-class.md) | Pydantic-AI Agents as First-Class Citizens | 🔄 | 2026-05-20 | `core/llm/`, `core/agents/`, RULE-01 |
| [ADR-016](ADR-016-prompt-caching.md) | Prompt Caching Strategy (Agent-Singletons + ModelSettings) | 🔄 | 2026-05-20 | `core/agents/`, `core/llm/`, Observability |
| [ADR-017](017-embedding-cascade.md) | Embedding Cascade for mem0 (4-tier fallback) | ✅ | 2026-05-21 | `core/memory/`, `packages/core/narrare_core/memory/` |
| [ADR-018](ADR-018-promptfoo-evals.md) | promptfoo Eval Framework for Prompt Quality | ✅ | 2026-05-23 | `evals/`, CI |
| [ADR-019](019-system-prompt-consistency.md) | System-Prompt Consistency for pydantic-ai Agents | ✅ | 2026-05-23 | `core/agents/`, `core/prompts/`, RULE-02 |
| [ADR-020](ADR-020-embedding-provider-abstraction.md) | Embedding Provider Abstraction | ✅ | 2026-05-27 | `core/llm/`, Q-003 |

---

## How to Create a New ADR

1. Copy `_TEMPLATE.md` to `ADR-NNN-short-title.md`
2. Fill in all sections
3. Add a row to this index
4. Reference the ADR in any related code with: `# See ADR-NNN`
5. If the decision supersedes an older one, update the old ADR's status

---

## ADR Template

See `_TEMPLATE.md` in this directory.
