<!-- Context: narrare-dev/constraints/rules | Priority: critical | Source: docs/_shared/CONSTRAINTS.md | Updated: 2026-05-30 -->

# Architecture Constraints — Rules Summary

**Core Idea**: 22 machine-enforced rules governing all Narrare code. Enforced via `scripts/check_architecture.py` (pre-commit + CI). Changes require ADR + PR approval.

**Reference**: `docs/_shared/CONSTRAINTS.md` (766 lines, full rationale + examples)

---

## Cardinal Rules (No exceptions without documented ADR)

### RULE-01b: Agents via NarrareAgent, Models via ModelRegistry
- `pydantic_ai.Agent` only in `core/agents/`
- Model/provider classes only in `core/llm/`
- No direct `openai`/`anthropic` imports anywhere
- Everywhere else: `from narrare_core.agents.base import NarrareAgent`

### RULE-02: Prompts built only in `core/prompts/`
- No f-string prompt assembly outside `core/prompts/`
- Use `PromptComposer.build(intent=..., context=...)` everywhere else

### RULE-03: Contracts before implementation
- Every service needs a `Protocol` in `contracts.py` or `_types.py` FIRST
- Enables mocking, testing, client-switching (MCP/A2A/CLI)

### RULE-04: Split before you squeeze — hard file limits

| File type | Hard limit | Soft target |
|-----------|-----------|-------------|
| Any Python module | 400 lines | 250 lines |
| Router file | 150 lines | 80 lines |
| Service file | 300 lines | 200 lines |
| Agent definition | 200 lines | 150 lines |
| Test file | 400 lines | 300 lines |
| Config / schema | 200 lines | 150 lines |

Approaching limit → extract a new module. NEVER compress code to fit.

### RULE-15: No `middleware.ts` — use `proxy.ts`
- Next.js 16+ uses `packages/web/proxy.ts` exclusively
- `middleware.ts` causes hard build failure

---

## Structural Rules

| Rule | Summary |
|------|---------|
| RULE-05 | Module boundaries = ownership boundaries. No cross-domain `_internal` imports |
| RULE-06 | One responsibility per file (router/service/repository/schema/contract/model/agent/config/utils) |
| RULE-07 | Dependency direction: router → service → repository → database. One-way only |
| RULE-08 | All external integrations abstracted (PostgreSQL, Redis, pgvector, mem0, SMTP, etc.) |
| RULE-14 | Every model column needs a matching Alembic migration in the same task |
| RULE-18 | No hardcoded config in routers — resolve via DI or settings cascade |
| RULE-19 | Dependency factories use `SessionDep`, not bare `AsyncSession` (causes 422) |

---

## Quality Rules

| Rule | Summary |
|------|---------|
| RULE-09 | Every public function has type signature. `Any` forbidden except approved adapters |
| RULE-10 | Tests mandatory: services → unit test, endpoints → integration test. Core: 90%, API: 80% |
| RULE-11 | No silent failures. `except` must re-raise, log with structlog, or convert to domain error |
| RULE-16 | i18n: every `useTranslations("X")` needs namespace in `request.ts` + all 3 locale files |
| RULE-17 | API-Frontend contract: Pydantic field names must match TypeScript interface names exactly |

---

## Implementation Quality

| Rule | Summary |
|------|---------|
| RULE-20 | No half-implementations. Build properly or don't build. Each increment must be complete |
| RULE-21 | Architecture review invalidated by material plan changes. Must re-review |

---

## Future-Compatibility

| Rule | Summary |
|------|---------|
| RULE-12 | Service Layer is the only public API. WebUI/MCP/A2A/CLI are all clients |
| RULE-13 | Streaming and non-streaming share one interface (`stream: bool = False`) |

---

## Enforcement

- **Automated**: `scripts/check_architecture.py` (RULE-01b, 02, 04, 06, 09, 11, 15, 19)
- **Type system**: `mypy --strict` + `pyright` (RULE-09)
- **Coverage**: `pytest --cov` with minimum thresholds (RULE-10)
- **Contract tests**: Backend-frontend field name validation (RULE-17)
- **PR review**: Architecture Agent reviews all rules
- **Exceptions**: Listed in `pyproject.toml [tool.narrare.architecture]` with inline `# narrare: allow-*` comment

---

## Approved Exceptions (3)

1. **RULE-01** in `core/memory/mem0_client.py` — mem0 AsyncMemory needs own LLM client
2. **RULE-01b** in `core/llm/gateway.py` — Gateway._make_agent() is approved boundary crossing
3. **RULE-01b** in `apps/api/narrare/setup/provider_service.py` — Setup-phase credential validation

---

**Related**: `lookup/adr-index.md`, `lookup/current-state.md`
