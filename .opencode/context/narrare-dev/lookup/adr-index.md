<!-- Context: narrare-dev/lookup/adr-index | Priority: medium | Source: docs/architecture/decisions/INDEX.md | Updated: 2026-05-30 -->

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
| ADR-008 | Frontend: fetch, Tailwind v4, TanStack Query, shadcn/ui | ✅ | 2026-05-12 | `packages/web/` |
| ADR-009 | Security Stack Modernization (argon2 + fastapi-limiter) | ✅ | 2026-05-12 | `auth/`, middleware |
| ADR-010 | Observability Strategy (OpenTelemetry + Langfuse) | ✅ | 2026-05-12 | `core/llm/`, observability |
| ADR-011 | Content Versioning for Chapters | ✅ | 2026-05-12 | `chapters/`, DB schema |
| ADR-012 | Event-Driven Architecture (Redis Pub/Sub) | ✅ | 2026-05-12 | `core/events/`, TaskIQ |
| ADR-013 | Internationalization Architecture | ✅ | 2026-05-12 | `packages/i18n/`, web |
| ADR-014 | TDD Agent Workflow & Regression-First Fixes | ✅ | 2026-05-14 | Agent System, Testing |
| ADR-015 | Pydantic-AI Agents as First-Class Citizens | 🔄 | 2026-05-20 | `core/llm/`, `core/agents/` |
| ADR-016 | Prompt Caching (Agent-Singletons + ModelSettings) | ✅ | 2026-05-20 | `core/agents/`, `core/llm/` |
| ADR-017 | Embedding Cascade for mem0 (4-tier fallback) | ✅ | 2026-05-21 | `core/memory/` |
| ADR-018 | promptfoo Eval Framework for Prompt Quality | ✅ | 2026-05-23 | `evals/`, CI |
| ADR-019 | System-Prompt Consistency for pydantic-ai Agents | ✅ | 2026-05-23 | `core/agents/`, `core/prompts/` |
| ADR-020 | Embedding Provider Abstraction | ✅ | 2026-05-27 | `core/llm/` |
| ADR-021 | Deterministic Analysis Strategy (spaCy + tiered hybrid) | ✅ | 2026-05-27 | `core/nlp/`, `core/analysis/` |
| ADR-022 | LLM Wiki — Precomputed Context Layer | ✅ | 2026-05-29 | `core/wiki/`, WIKI-001 |

## Creating a New ADR

1. Copy `_TEMPLATE.md` → `ADR-NNN-short-title.md`
2. Fill all sections
3. Add row to this index
4. Reference in code: `# See ADR-NNN`
5. If superseding older ADR, update old status

**Related**: `narrare-dev/lookup/feature-index`, `narrare-dev/concepts/project-vision`
