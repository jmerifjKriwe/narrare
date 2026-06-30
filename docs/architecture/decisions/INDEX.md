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
| [ADR-015](ADR-015-agents-first-class.md) | Pydantic-AI Agents as First-Class Citizens | ✅ | 2026-05-20 | `core/llm/`, `core/agents/`, RULE-01b |
| [ADR-016](ADR-016-prompt-caching.md) | Prompt Caching Strategy (Agent-Singletons + ModelSettings) | ✅ | 2026-05-20 | `core/agents/`, `core/llm/`, Observability |
| [ADR-017](017-embedding-cascade.md) | Embedding Cascade for mem0 (4-tier fallback) | ⛔ | 2026-05-21 | `core/memory/`, `packages/core/narrare_core/memory/` |
| [ADR-018](ADR-018-promptfoo-evals.md) | promptfoo Eval Framework for Prompt Quality | ⛔ | 2026-05-23 | `evals/`, CI |
| [ADR-019](019-system-prompt-consistency.md) | System-Prompt Consistency for pydantic-ai Agents | ✅ | 2026-05-23 | `core/agents/`, `core/prompts/`, RULE-02 |
| [ADR-020](ADR-020-embedding-provider-abstraction.md) | Embedding Provider Abstraction | ✅ | 2026-05-27 | `core/llm/`, Q-003 |
| [ADR-021](ADR-021-deterministic-analysis-strategy.md) | Deterministic Analysis Strategy (spaCy + tiered hybrid) | ✅ | 2026-05-27 | `core/nlp/`, `core/analysis/`, ANAL-001–011, CONS-001/002, STATS-001/002 |
| [ADR-022](ADR-022-llm-wiki.md) | LLM Wiki — Precomputed Context Layer | ✅ | 2026-05-29 | `core/wiki/`, `apps/api/wiki/`, WIKI-001, INFRA-003 |
| [ADR-023](ADR-023-co-author-change-engine.md) | Co-Author Change Engine | ✅ | 2026-05-29 | `core/writing/`, `apps/api/narrare/writing/`, `packages/web/`, WRITE-006 |
| [ADR-024](ADR-024-free-form-chat.md) | Free-Form Chat for Writing Craft | ✅ | 2026-05-30 | `core/prompts/`, `core/llm/`, `apps/api/narrare/chat/`, `packages/web/`, FIND-019, CR-AUFG-02-03 |
| [ADR-025](025-feature-adoption-infrastructure.md) | Feature Adoption Infrastructure (registry, context variables, assembler centralization, inline policy, adoption score) | ✅ | 2026-05-31 | `scripts/architecture/`, `core/context/`, CR-03 |
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
| [ADR-042](ADR-042-persistent-evidence-upgrade.md) | PostgreSQL Evidence Upgrade | ✅ | 2026-06-07 | `apps/api/narrare/evidence/`, `apps/api/alembic/versions/0028_invocation_evidence.py`, CR-03 P4 |
| [ADR-043](043-ai-interaction-primitives.md) | Shared AI Interaction Primitives (`useAIOperation` hook) | ✅ Implemented | 2026-06-08 | `packages/web/lib/hooks/`, `packages/web/lib/api/`, §16 compliance, CR-07 |
| [ADR-044](ADR-044-staged-consistency.md) | Staged Multi-Agent Consistency Pipeline (FactExtractor → ConsistencyAgent) | ✅ Implemented | 2026-06-12 | `core/agents/`, `apps/api/narrare/consistency/`, `evals/`, CONS-001, FIND-009, KB-007, ANAL-005 |
| [ADR-045](ADR-045-runtime-adoption-enforcement.md) | Runtime Adoption Enforcement and Invocation Evidence Correlation | ✅ Implemented | 2026-06-19 | `core/ai_invocation/`, `evidence/`, `scripts/architecture/`, ADR-038, CR-03 P5 |
| [ADR-046](ADR-046-prompt-path-compliance.md) | Prompt-Path-Compliance: Resolution-Path Retrofit & Prevention | ✅ Implemented | 2026-06-17 | `core/prompts/`, `core/agents/`, `apps/api/`, `scripts/architecture/_checkers/`, RULE-02b, CR-02 |
| [ADR-047](ADR-047-governance-drift-automation.md) | Governance Drift Automation for Review Findings and AUFG Lifecycle | ✅ | 2026-06-24 | `docs/architecture/governance/`, `_audit/results/technical-review/`, `scripts/governance/`, CI governance gates |
| [ADR-048](ADR-048-non-writing-invocation-adapter.md) | Non-Writing Invocation Adapter (Domain-Agnostic Pipeline Composition) | ✅ | 2026-06-24 | `core/ai_invocation/`, `apps/api/`, ADR-045 Decision 7, non-writing domains |
| [ADR-049](ADR-049-prompt-surface-identity-path-contract.md) | Prompt-Surface Identity & Path Contract Retrofit (FIND-010 + FIND-011) | ✅ | 2026-06-18 | `core/prompts/`, `scripts/architecture/`, `apps/api/narrare/planning/`, ADR-024, ADR-037, RULE-02/02a/02b |
| [ADR-050](ADR-050-cross-feature-context-contracts.md) | Cross-Feature Context Contracts (KB Envelope, Ref Lifecycle, kb_pinned Governance) | ✅ | 2026-06-18 | `core/context/`, `core/profiles/`, KB, PLAN-004, PLAN-005, CONS-001, FIND-009, CR-AUFG-04 |
| [ADR-051](ADR-051-configuration-effect-adoption-contract.md) | Configuration Effect Adoption Contract | ✅ | 2026-06-20 | `settings/`, `core/llm/`, `core/writing/`, provider catalogs, Platform governance, CR-08, RULE-18b |
| [ADR-052](052-session-stop-recovery.md) | Session Stop and WebSocket Recovery | ✅ | 2026-06-22 | `apps/api/narrare/writing/` (ws_handler, ws_direction_dispatch, ws_streaming, _ws_cache, router_sessions), WebSocket session lifecycle, CR-AUFG-07-21, ADR-043, ADR-045 |
| [ADR-053](053-ai-session-lifecycle.md) | AI Session Lifecycle Pattern (WebSocket) — keep `useSessionSocket`, no separate `useAISession` hook | ✅ | 2026-06-24 | `packages/web/components/studio/editor/` (useSessionSocket, SessionReconnectBanner, SessionPanel), §16 AI-Interaction, ADR-043 (Review-Trigger #1 closed), ADR-052 |
| [ADR-054](054-inline-feature-prompt-debt-migration.md) | Inline Feature-Prompt Debt Migration (FIND-011 clones) — character_arc / timeline_extraction / merge services → PromptComposer Mode 1 | ✅ | 2026-06-25 | `core/prompts/` (route_table, _bundled planning/kb templates, manifest), `apps/api/narrare/planning/`, `apps/api/narrare/kb/merge_service.py`, `scripts/architecture/_checkers/_check_inline_feature_prompt.py`, ADR-049, ADR-048, RULE-02/02a/02b/11 |
| [ADR-055](ADR-055-character-voice-contract.md) | Character Voice Storage Contract & VOICE Prompt Surface (ANAL-008) — extend SpeechPatterns with nested voice_analysis, hybrid metrics, self-contained attribution, make LLMIntent.VOICE routeable | ✅ | 2026-06-26 | `core/kb/schemas/character.py`, `core/profiles/_voice_extraction.py`, `core/analysis/` (dialogue_parser, voice_metrics), `core/prompts/` (route_table, _bundled analysis/character_voice, manifest), `core/agents/character_voice_agent.py`, ADR-021, ADR-040, ADR-050, ADR-054, RULE-02/02b/03/22, CR-04 |
| [ADR-056](ADR-056-runtime-aware-commit-gate-true-debt-baseline.md) | Runtime-Evidence-Aware Adoption Commit Gate & True-Debt Baseline — amends ADR-045 Decision 1 enforcement-point letter (pre-commit hook + `run_checks.py` pass `--evidence-dir .evidence`); redefines `adoption_debt` baseline to track true debt | ✅ | 2026-06-29 | `.pre-commit-config.yaml` (adoption-score), `scripts/run_checks.py`, `scripts/architecture/ai-gate-baseline.json`, ADR-045, ADR-047, RULE-11/19/22 |
| [ADR-057](ADR-057-voice-check-checking-path-contract.md) | Voice-Check Checking-Path Contract & `voice_check` Prompt Surface (WRITE-010) — extend `CharacterVoiceProfile` with `voice_metrics` (closes ADR-055 Risk #1; surfaces via `VoiceProfileConsumer.assemble_for_checking`, no KB bypass); hybrid deterministic-delta + LLM scoring; new `voice_check` context_mode; module home `analysis/`; flag+score scope (no rewrites) | ✅ Implemented | 2026-06-30 | `core/profiles/models.py`, `core/profiles/_voice_extraction.py`, `core/analysis/voice_check_scoring.py`, `core/agents/character_voice_checker_agent.py`, `core/prompts/` (route_table, _bundled analysis/voice_check, manifest), `apps/api/narrare/analysis/` (voice_check service/router/contracts/schemas/dependencies), ADR-021, ADR-035, ADR-050, ADR-055, ADR-056, RULE-02/02b/03/04/06/07/11/13/22, CR-04 |
| [ADR-058](ADR-058-process-history-sliding-window.md) | ProcessHistory Sliding Window Context Management — token-aware sliding window for `ProcessHistory`, using `StreamEvent("done").usage.input_tokens`; backward compatible via `max_tokens=None`; drops at message-pair boundaries; no LimitWarner | 🔄 | 2026-06-30 | `core/agents/process_history.py`, `apps/api/narrare/chat/chat_service.py`, ADR-034, RULE-04/06/09/10/11/20 |

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
