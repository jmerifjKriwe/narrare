<!-- Context: narrare-dev/standards/tier1-compact-rules | Priority: critical | Max: 150 lines | Updated: 2026-06-04 -->

# Tier-1 Rules — Mandatory for ALL Agents

> **This is the MINIMUM rule set every agent must know.**
> For details, see the referenced docs. Ignorance of these rules is not an excuse.

## Architecture Rules (docs/_shared/CONSTRAINTS.md)

| Rule | One-Line Summary | Common Violation |
|------|-----------------|------------------|
| RULE-01b | Agents in `core/agents/`, Models from `core/llm/` only | `import openai` outside core/llm/ |
| RULE-02 | Prompts built in `core/prompts/` only | f-string prompts in services |
| RULE-02a | Capabilities for guaranteed, cascade for customizable, `@agent.instructions` for dynamic | f-string in `get_instructions()` |
| RULE-02b | Prompt-Resolution is exclusively `core/prompts/` — no app-layer loaders, no direct registry, no user-channel injection, no inline fallbacks | `PromptRegistry.resolve()` in apps/; `importlib.resources`+`.replace()` loader in apps/ |
| RULE-03 | Protocol/Contract before implementation | Service without contracts.py |
| RULE-04 | Split at soft target (250 lines), fail at hard limit (400) | Removing comments to fit limit |
| RULE-05 | Module boundaries are ownership boundaries — no `_internal` imports | `from narrare.writing._internal import X` |
| RULE-06 | One responsibility per file | Business logic in router.py |
| RULE-07 | router → service → repository → DB only (one-way) | Repository importing service |
| RULE-09 | Every public function typed, no bare Any | `def process(data):` |
| RULE-10 | Every service method has a unit test | New method without test |
| RULE-11 | No silent failures, no bare except:pass | `except Exception: pass` |
| RULE-14 | Every model column needs a migration | Column in models.py without migration |
| RULE-15 | No `middleware.ts` — use `proxy.ts` only | Creating `middleware.ts` |
| RULE-16 | i18n namespace registered in `request.ts` + all locale files | `useTranslations("X")` not in namespaces |
| RULE-17 | Backend schema fields match frontend types exactly | Backend `id` but frontend reads `prompt_id` |
| RULE-18 | No hardcoded config in routers — use DI/settings | `provider_name="anthropic"` default |
| RULE-19 | Use `SessionDep`, not bare `AsyncSession` | `session: AsyncSession` in dependencies.py |
| RULE-20 | No half-implementations. Build properly or don't build | REST-only when SSE endpoint exists |
| RULE-22 | Cross-feature coherence gate before merge | New feature reads KB without integration contract |
| RULE-23 | No naked `# type: ignore` — must have error code + reason | `# type: ignore` without error code or reason |

## Testing Rules (docs/development/testing-standards.md)

| Rule | One-Line Summary |
|------|-----------------|
| RULE-TEST-01 | Fake classes instead of MagicMock. TestModel for LLM. No bare MagicMock(). |
| RULE-TEST-02 | Post-assertion: verify DB state after mutations |
| RULE-TEST-03 | Auto-tagging by directory (unit/integration/e2e) |
| RULE-TEST-04 | No snapshots for dynamic content |

**Coverage minimums:** `core/` ≥90%, `apps/api/` ≥80%. CI: `--cov-fail-under=60` (hard), 80% (target).
**Test location:** `tests/unit/`, `tests/integration/`, `tests/e2e/` — never in source packages.
**DB in tests:** Unit = no DB. Integration = real Alembic migrations, never `create_all()`.

## Quality Gates (10 gates, ALL must pass)

| Gate | What |
|------|------|
| G1 | Tests pass (unit + integration + e2e) |
| G2 | Coverage thresholds met |
| G3 | Architecture check (`check_architecture.py`) |
| G4 | Fake conformance (`isinstance(fake, Protocol)`) |
| G5 | Cross-layer contracts (API ↔ frontend field names) |
| G6 | Type checking (`pyright`) |
| G7 | CI pipeline green |
| G8 | Feature adoption (registry + context variables) |
| G9 | AI content review (no "As an AI..." in outputs) |
| G10 | Semantic review (cross-feature coherence) |

## Agent Routing (AGENTS.md)

| Task | Delegate to |
|------|------------|
| Architecture, specs, ADRs | NarrareArchitectureSpecialist |
| FastAPI, services, DB | NarrareBackendSpecialist |
| LLM, prompts, agents | NarrareCoreSpecialist |
| React, TipTap, UI | NarrareFrontendSpecialist |
| Testing, CI/CD, Docker | NarrarePlatformSpecialist |
| Feature docs, help texts | NarrareDocsSpecialist |

## Red Flags — STOP and escalate

- "I'll just add a special case..."
- "Quick fix, refactor later..."
- "This bypasses [abstraction] but..."
- "Let's start without streaming..."
- Any TODO/FIXME/HACK without concrete resolution date
- `MagicMock()` without `spec=` for a domain dependency
- `# type: ignore` without a reason comment
- `# type: ignore` without an error code (naked suppression)

## Context Loading Order

1. **THIS FILE** (always loaded)
2. **CONSTRAINTS.md** (for architecture tasks — authoritative rule source)
3. **testing-standards.md** (for test tasks — authoritative test source)
4. Domain-specific docs (only as needed)

## Exception Handling

Architecture exceptions are dual-registered in `pyproject.toml` (SSOT) + inline `# narrare: allow`
comments. Adding an exception requires updating BOTH. See ADR-028.
