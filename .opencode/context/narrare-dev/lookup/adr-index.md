<!-- Context: narrare-dev/lookup/adr-index | Priority: medium | Source: docs/architecture/decisions/INDEX.md | Updated: 2026-06-03 -->

# Architecture Decision Records — Index

> Complete reference: `docs/architecture/decisions/INDEX.md`
> Load individual ADR files only when full reasoning is needed.

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Accepted — in effect |
| 🔄 | Proposed — under discussion |
| ⛔ | Superseded — replaced by newer ADR |
| 🗄️ | Deprecated — no longer relevant |

## Decision Log

| ID | Title | Status | Date | Affects |
|----|-------|--------|------|---------|
| ADR-001 | Single LLM Gateway for all model calls | ✅ | init | `core/llm/` |
| ADR-002 | Unified prompt system replacing three parallel implementations | ✅ | init | `core/prompts/` |
| ADR-003 | Protocol-first development — contracts before implementation | ✅ | init | all domains |
| ADR-004 | Hard file size limits with enforcement | ✅ | init | all files |
| ADR-005 | Module structure and ownership boundaries | ✅ | init | all modules |
| ADR-006 | Technology choices and explicit exclusions | ✅ | init | all |
| ADR-007 | TaskIQ for background task processing | ✅ | init+2 | `core/tasks/` |
| ADR-008 | Frontend architecture: fetch, Tailwind v4, TanStack Query, shadcn/ui | ✅ | 2026-05-12 | `packages/web/` |
| ADR-009 | Security Stack Modernization (argon2 + fastapi-limiter) | ✅ | 2026-05-12 | `auth/`, `_app/middleware.py` |
| ADR-010 | Observability Strategy (OpenTelemetry + Langfuse) | ⛔ | 2026-05-12 | `core/llm/`, `_app/middleware.py`, observability |
| ADR-011 | Content Versioning for Chapters | ✅ | 2026-05-12 | `chapters/`, DB schema |
| ADR-012 | Event-Driven Architecture (Redis Pub/Sub) | ✅ | 2026-05-12 | `core/events/`, TaskIQ integration |
| ADR-013 | Internationalization Architecture | ✅ | 2026-05-12 | `packages/i18n/`, `packages/web/lib/i18n/` |
| ADR-014 | TDD Agent Workflow & Regression-First Fixes | ✅ | 2026-05-14 | Agent System, Testing |
| ADR-015 | Pydantic-AI Agents as First-Class Citizens | 🔄 | 2026-05-20 | `core/llm/`, `core/agents/`, RULE-01 |
| ADR-016 | Prompt Caching Strategy (Agent-Singletons + ModelSettings) | ✅ | 2026-05-20 | `core/agents/`, `core/llm/`, Observability |
| ADR-017 | Embedding Cascade for mem0 (4-tier fallback) | ⛔ | 2026-05-21 | `core/memory/`, `packages/core/narrare_core/memory/` |
| ADR-018 | promptfoo Eval Framework for Prompt Quality | ⛔ | 2026-05-23 | `evals/`, CI |
| ADR-019 | System-Prompt Consistency for pydantic-ai Agents | ✅ | 2026-05-23 | `core/agents/`, `core/prompts/`, RULE-02 |
| ADR-020 | Embedding Provider Abstraction | ✅ | 2026-05-27 | `core/llm/`, Q-003 |
| ADR-021 | Deterministic Analysis Strategy (spaCy + tiered hybrid) | ✅ | 2026-05-27 | `core/nlp/`, `core/analysis/`, ANAL-001–011, CONS-001/002, STATS-001/002 |
| ADR-022 | LLM Wiki — Precomputed Context Layer | ✅ | 2026-05-29 | `core/wiki/`, `apps/api/wiki/`, WIKI-001, INFRA-003 |
| ADR-023 | Co-Author Change Engine | ✅ | 2026-05-29 | `core/writing/`, `apps/api/narrare/writing/`, `packages/web/`, WRITE-006 |
| ADR-024 | Free-Form Chat for Writing Craft | 🔄 | 2026-05-30 | `core/prompts/`, `core/llm/`, `apps/api/narrare/chat/`, `packages/web/`, FIND-019, CR-AUFG-02-03 |
| ADR-025 | Feature Adoption Infrastructure (registry, context variables, assembler centralization, inline policy, adoption score) | 🔄 | 2026-05-31 | `scripts/architecture/`, `core/context/`, CR-03 |
| ADR-026 | Capability-Based Prompt Injection Pattern | ✅ | 2026-06-01 | `core/agents/capabilities/`, `core/prompts/`, RULE-02 |
| ADR-027 | AI Feature Stabilization Gates | ✅ | 2026-06-02 | `core/prompts/`, `packages/web/lib/api/streaming.ts`, quality gates |
| ADR-028 | Architecture Exception Register: Single Source of Truth | ✅ | 2026-06-03 | `pyproject.toml`, `CONSTRAINTS.md §7`, `scripts/architecture/` |
| ADR-029 | VM-First Setup Contract and Optional DevContainer Cleanup | ✅ | 2026-06-03 | `.devcontainer/`, `justfile`, `.github/workflows/`, Docker/Compose, release docs |
| ADR-030 | MagicMock-to-Fake Migration Plan for Memory Tests | ✅ | 2026-06-04 | `tests/unit/api/memory/`, `tests/fakes/`, `apps/api/narrare/memory/contracts.py` |
| ADR-031 | Local-First OpenTelemetry Observability | ✅ | 2026-06-04 | `apps/api/narrare/_app/telemetry.py`, `core/agents/`, `core/llm/`, observability |
| ADR-032 | Pydantic Evals as Evaluation Single Source of Truth | ✅ | 2026-06-04 | `evals/`, `core/agents/`, `core/prompts/`, CI |
| ADR-033 | mem0 v3 OSS Memory Architecture | ✅ | 2026-06-04 | `core/memory/`, `apps/api/narrare/memory/`, preference retrieval |
| ADR-034 | Conversational History Policy for Narrare Agents | ✅ | 2026-06-04 | `core/agents/`, chat, writing sessions, task agents |
| ADR-035 | Agent Output Validation Policy | ✅ | 2026-06-04 | `core/agents/`, structured outputs, Pydantic Evals |
| ADR-036 | Durable Execution Boundary | ✅ | 2026-06-04 | TaskIQ, events, agent workflows, runtime infrastructure |

## Creating a New ADR

1. Copy `_TEMPLATE.md` → `ADR-NNN-short-title.md`
2. Fill all sections
3. Add row to this index
4. Reference in code: `# See ADR-NNN`
5. If superseding older ADR, update old status

**Related**: `narrare-dev/lookup/feature-index`, `narrare-dev/concepts/project-vision`
