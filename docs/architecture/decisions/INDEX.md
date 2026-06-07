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
| [ADR-010](ADR-010-observability.md) | Observability Strategy (OpenTelemetry + Langfuse) | ⛔ | 2026-05-12 | `core/llm/`, `_app/middleware.py`, observability |
| [ADR-011](ADR-011-content-versioning.md) | Content Versioning for Chapters | ✅ | 2026-05-12 | `chapters/`, DB schema |
| [ADR-012](ADR-012-event-driven.md) | Event-Driven Architecture (Redis Pub/Sub) | ✅ | 2026-05-12 | `core/events/`, TaskIQ integration |
| [ADR-013](ADR-013-i18n.md) | Internationalization Architecture | ✅ | 2026-05-12 | `packages/i18n/`, `packages/web/lib/i18n/` |
| [ADR-014](ADR-014-tdd-agent-workflow.md) | TDD Agent Workflow & Regression-First Fixes | ✅ | 2026-05-14 | Agent System, Testing |
| [ADR-015](ADR-015-agents-first-class.md) | Pydantic-AI Agents as First-Class Citizens | 🔄 | 2026-05-20 | `core/llm/`, `core/agents/`, RULE-01 |
| [ADR-016](ADR-016-prompt-caching.md) | Prompt Caching Strategy (Agent-Singletons + ModelSettings) | ✅ | 2026-05-20 | `core/agents/`, `core/llm/`, Observability |
| [ADR-017](017-embedding-cascade.md) | Embedding Cascade for mem0 (4-tier fallback) | ⛔ | 2026-05-21 | `core/memory/`, `packages/core/narrare_core/memory/` |
| [ADR-018](ADR-018-promptfoo-evals.md) | promptfoo Eval Framework for Prompt Quality | ⛔ | 2026-05-23 | `evals/`, CI |
| [ADR-019](019-system-prompt-consistency.md) | System-Prompt Consistency for pydantic-ai Agents | ✅ | 2026-05-23 | `core/agents/`, `core/prompts/`, RULE-02 |
| [ADR-020](ADR-020-embedding-provider-abstraction.md) | Embedding Provider Abstraction | ✅ | 2026-05-27 | `core/llm/`, Q-003 |
| [ADR-021](ADR-021-deterministic-analysis-strategy.md) | Deterministic Analysis Strategy (spaCy + tiered hybrid) | ✅ | 2026-05-27 | `core/nlp/`, `core/analysis/`, ANAL-001–011, CONS-001/002, STATS-001/002 |
| [ADR-022](ADR-022-llm-wiki.md) | LLM Wiki — Precomputed Context Layer | ✅ | 2026-05-29 | `core/wiki/`, `apps/api/wiki/`, WIKI-001, INFRA-003 |
| [ADR-023](ADR-023-co-author-change-engine.md) | Co-Author Change Engine | ✅ | 2026-05-29 | `core/writing/`, `apps/api/narrare/writing/`, `packages/web/`, WRITE-006 |
| [ADR-024](ADR-024-free-form-chat.md) | Free-Form Chat for Writing Craft | ✅ | 2026-05-30 | `core/prompts/`, `core/llm/`, `apps/api/narrare/chat/`, `packages/web/`, FIND-019, CR-AUFG-02-03 |
| [ADR-025](025-feature-adoption-infrastructure.md) | Feature Adoption Infrastructure (registry, context variables, assembler centralization, inline policy, adoption score) | 🔄 | 2026-05-31 | `scripts/architecture/`, `core/context/`, CR-03 |
| [ADR-026](ADR-026-capability-prompt-injection.md) | Capability-Based Prompt Injection Pattern | ✅ | 2026-06-01 | `core/agents/capabilities/`, `core/prompts/`, RULE-02 |
| [ADR-027](ADR-027-ai-feature-stabilization-gates.md) | AI Feature Stabilization Gates | ✅ | 2026-06-02 | `core/prompts/`, `packages/web/lib/api/streaming.ts`, quality gates, agent docs |
| [ADR-028](ADR-028-architecture-exception-ssot.md) | Architecture Exception Register: Single Source of Truth | ✅ | 2026-06-03 | `pyproject.toml`, `CONSTRAINTS.md §7`, `scripts/architecture/`, all exception locations |
| [ADR-029](ADR-029-vm-first-setup-contract.md) | VM-First Setup Contract and Optional DevContainer Cleanup | ✅ | 2026-06-03 | `.devcontainer/`, `justfile`, `.github/workflows/`, Docker/Compose, release docs |
| [ADR-030](ADR-030-magicmock-migration-plan.md) | MagicMock-to-Fake Migration Plan for Memory Tests | ✅ | 2026-06-04 | `tests/unit/api/memory/`, `tests/fakes/`, `apps/api/narrare/memory/contracts.py` |
| [ADR-031](ADR-031-local-first-opentelemetry-observability.md) | Local-First OpenTelemetry Observability | ✅ | 2026-06-04 | `apps/api/narrare/_app/telemetry.py`, `core/agents/`, `core/llm/`, observability |
| [ADR-032](ADR-032-pydantic-evals-ssot.md) | Pydantic Evals as Evaluation Single Source of Truth | ✅ | 2026-06-04 | `evals/`, `core/agents/`, `core/prompts/`, CI |
| [ADR-033](ADR-033-mem0-v3-oss-memory-architecture.md) | mem0 2.0.x OSS Memory Architecture | ✅ Implemented | 2026-06-04 | `core/memory/`, `apps/api/narrare/memory/`, preference retrieval |
| [ADR-034](ADR-034-conversational-history-policy.md) | Conversational History Policy for Narrare Agents | ✅ Implemented | 2026-06-04 | `core/agents/`, chat, writing sessions, task agents |
| [ADR-035](ADR-035-agent-output-validation-policy.md) | Agent Output Validation Policy | ✅ Implemented | 2026-06-04 | `core/agents/`, structured outputs, Pydantic Evals |
| [ADR-036](ADR-036-durable-execution-boundary.md) | Durable Execution Boundary | ✅ | 2026-06-04 | TaskIQ, events, agent workflows, runtime infrastructure |
| [ADR-037](ADR-037-prompt-surface-contract-manifest.md) | Prompt Surface Contract Manifest | ✅ | 2026-06-05 | `core/prompts/`, `scripts/architecture/`, prompt governance, RULE-22 |
| [ADR-038](ADR-038-ai-invocation-adoption-contract.md) | AI Invocation Adoption Contract | ✅ | 2026-06-05 | `core/ai_invocation/`, `core/prompts/`, `apps/api/`, `scripts/adoption/`, CR-03 |
| [ADR-040](ADR-040-kg-ssot-audit-lifecycle.md) | KG Consistency / Voice Profile SSOT / Audit Lifecycle | ✅ | 2026-06-06 | `core/profiles/`, `core/ai_invocation/consistency`, `scripts/adoption/audit_report.py`, CR-03 P2 |
| [ADR-041](ADR-041-typed-manifests-drift-metrics.md) | Typed Manifests / Doc-Drift / Quality Metrics / Persistent Evidence | ✅ | 2026-06-07 | `scripts/check_registry_drift.py`, `scripts/quality/`, `scripts/doc_drift/`, `.evidence/`, CR-03 P3 |

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
