<!-- Context: narrare-dev/lookup/adr-index | Priority: medium | Source: docs/architecture/decisions/INDEX.md | Updated: 2026-06-24 -->

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
| ADR-015 | Pydantic-AI Agents as First-Class Citizens | ✅ | 2026-05-20 | `core/llm/`, `core/agents/`, RULE-01b |
| ADR-016 | Prompt Caching Strategy (Agent-Singletons + ModelSettings) | ✅ | 2026-05-20 | `core/agents/`, `core/llm/`, Observability |
| ADR-017 | Embedding Cascade for mem0 (4-tier fallback) | ⛔ | 2026-05-21 | `core/memory/`, `packages/core/narrare_core/memory/` |
| ADR-018 | promptfoo Eval Framework for Prompt Quality | ⛔ | 2026-05-23 | `evals/`, CI |
| ADR-019 | System-Prompt Consistency for pydantic-ai Agents | ✅ | 2026-05-23 | `core/agents/`, `core/prompts/`, RULE-02 |
| ADR-020 | Embedding Provider Abstraction | ✅ | 2026-05-27 | `core/llm/`, Q-003 |
| ADR-021 | Deterministic Analysis Strategy (spaCy + tiered hybrid) | ✅ | 2026-05-27 | `core/nlp/`, `core/analysis/`, ANAL-001–011, CONS-001/002, STATS-001/002 |
| ADR-022 | LLM Wiki — Precomputed Context Layer | ✅ | 2026-05-29 | `core/wiki/`, `apps/api/wiki/`, WIKI-001, INFRA-003 |
| ADR-023 | Co-Author Change Engine | ✅ | 2026-05-29 | `core/writing/`, `apps/api/narrare/writing/`, `packages/web/`, WRITE-006 |
| ADR-024 | Free-Form Chat for Writing Craft | ✅ | 2026-05-30 | `core/prompts/`, `core/llm/`, `apps/api/narrare/chat/`, `packages/web/`, FIND-019, CR-AUFG-02-03 |
| ADR-025 | Feature Adoption Infrastructure (registry, context variables, assembler centralization, inline policy, adoption score) | ✅ | 2026-05-31 | `scripts/architecture/`, `core/context/`, CR-03 |
| ADR-026 | Capability-Based Prompt Injection Pattern | ✅ | 2026-06-01 | `core/agents/capabilities/`, `core/prompts/`, RULE-02 |
| ADR-027 | AI Feature Stabilization Gates | ✅ | 2026-06-02 | `core/prompts/`, `packages/web/lib/api/streaming.ts`, quality gates |
| ADR-028 | Architecture Exception Register: Single Source of Truth | ✅ | 2026-06-03 | `pyproject.toml`, `CONSTRAINTS.md §7`, `scripts/architecture/`, all exception locations |
| ADR-029 | VM-First Setup Contract and Optional DevContainer Cleanup | ✅ | 2026-06-03 | `.devcontainer/`, `justfile`, `.github/workflows/`, Docker/Compose, release docs |
| ADR-030 | MagicMock-to-Fake Migration Plan for Memory Tests | ✅ | 2026-06-04 | `tests/unit/api/memory/`, `tests/fakes/`, `apps/api/narrare/memory/contracts.py` |
| ADR-031 | Local-First OpenTelemetry Observability | ✅ | 2026-06-04 | `apps/api/narrare/_app/telemetry.py`, `core/agents/`, `core/llm/`, observability |
| ADR-032 | Pydantic Evals as Evaluation Single Source of Truth | ✅ | 2026-06-04 | `evals/`, `core/agents/`, `core/prompts/`, CI |
| ADR-033 | mem0 2.0.x OSS Memory Architecture | ✅ | 2026-06-04 | `core/memory/`, `apps/api/narrare/memory/`, preference retrieval |
| ADR-034 | Conversational History Policy for Narrare Agents | ✅ | 2026-06-04 | `core/agents/`, chat, writing sessions, task agents |
| ADR-035 | Agent Output Validation Policy | ✅ | 2026-06-04 | `core/agents/`, structured outputs, Pydantic Evals |
| ADR-036 | Durable Execution Boundary | ✅ | 2026-06-04 | TaskIQ, events, agent workflows, runtime infrastructure |
| ADR-037 | Prompt Surface Contract Manifest | ✅ | 2026-06-05 | `core/prompts/`, `scripts/architecture/`, prompt governance, RULE-22 |
| ADR-038 | AI Invocation Adoption Contract | ✅ | 2026-06-05 | `core/ai_invocation/`, `core/prompts/`, `apps/api/`, `scripts/adoption/`, CR-03 |
| ADR-040 | KG Consistency / Voice Profile SSOT / Audit Lifecycle | ✅ | 2026-06-06 | `core/profiles/`, `core/ai_invocation/consistency`, `scripts/adoption/audit_report.py`, CR-03 P2 |
| ADR-041 | Typed Manifests / Doc-Drift / Quality Metrics / Persistent Evidence | ✅ | 2026-06-07 | `scripts/check_registry_drift.py`, `scripts/quality/`, `scripts/doc_drift/`, `.evidence/`, CR-03 P3 |
| ADR-042 | PostgreSQL Evidence Upgrade | ✅ | 2026-06-07 | `apps/api/narrare/evidence/`, `apps/api/alembic/versions/0028_invocation_evidence.py`, CR-03 P4 |
| ADR-043 | Shared AI Interaction Primitives (`useAIOperation` hook) | ✅ | 2026-06-08 | `packages/web/lib/hooks/`, `packages/web/lib/api/`, §16 compliance, CR-07 |
| ADR-044 | Staged Multi-Agent Consistency Pipeline (FactExtractor → ConsistencyAgent) | ✅ | 2026-06-12 | `core/agents/`, `apps/api/narrare/consistency/`, `evals/`, CONS-001, FIND-009, KB-007, ANAL-005 |
| ADR-045 | Runtime Adoption Enforcement and Invocation Evidence Correlation | ✅ | 2026-06-19 | `core/ai_invocation/`, `evidence/`, `scripts/architecture/`, ADR-038, CR-03 P5 |
| ADR-046 | Prompt-Path-Compliance: Resolution-Path Retrofit & Prevention | ✅ | 2026-06-17 | `core/prompts/`, `core/agents/`, `apps/api/`, `scripts/architecture/_checkers/`, RULE-02b, CR-02 |
| ADR-047 | Governance Drift Automation for Review Findings and AUFG Lifecycle | 🗄️ | 2026-06-24 | `docs/architecture/governance/`, `_audit/results/technical-review/`, `scripts/governance/`, CI governance gates |
| ADR-048 | Non-Writing Invocation Adapter (Domain-Agnostic Pipeline Composition) | ✅ | 2026-06-24 | `core/ai_invocation/`, `apps/api/`, ADR-045 Decision 7, non-writing domains |
| ADR-049 | Prompt-Surface Identity & Path Contract Retrofit (FIND-010 + FIND-011) | ✅ | 2026-06-18 | `core/prompts/`, `scripts/architecture/`, `apps/api/narrare/planning/`, ADR-024, ADR-037, RULE-02/02a/02b |
| ADR-050 | Cross-Feature Context Contracts (KB Envelope, Ref Lifecycle, kb_pinned Governance) | ✅ | 2026-06-18 | `core/context/`, `core/profiles/`, KB, PLAN-004, PLAN-005, CONS-001, FIND-009, CR-AUFG-04 |
| ADR-051 | Configuration Effect Adoption Contract | 🗄️ | 2026-06-20 | `settings/`, `core/llm/`, `core/writing/`, provider catalogs, Platform governance, CR-08, RULE-18b |

## Creating a New ADR

1. Copy `_TEMPLATE.md` → `ADR-NNN-short-title.md`
2. Fill all sections
3. Add row to this index
4. Reference in code: `# See ADR-NNN`
5. If superseding older ADR, update old status

**Related**: `narrare-dev/lookup/feature-index`, `narrare-dev/concepts/project-vision`
