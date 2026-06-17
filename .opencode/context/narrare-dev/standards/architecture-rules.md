<!-- Context: narrare-dev/standards/architecture-rules | Priority: critical | Version: 1.0 | Updated: 2026-05-31 -->

# Architecture Rules — Behavioral Standard

> **Purpose**: How to apply the 23 architecture rules in daily work.
> **Audience**: ALL Narrare specialists. Tier-1 reading.
> **NOT a replacement**: Always reference `docs/_shared/CONSTRAINTS.md` for full rule text.

## 1. Rule-to-Layer Mapping

Which rules are MOST relevant for which specialist layer.

| Rule | Core | Backend | Frontend | Platform |
|------|------|---------|----------|----------|
| RULE-01b (Agent/Model imports) | ✅ primary | ⚠️ aware | — | — |
| RULE-02 (Prompts in core/prompts/) | ✅ primary | — | — | — |
| RULE-03 (Contracts first) | ✅ primary | ✅ primary | ✅ aware | ✅ tests |
| RULE-04 (File size limits) | ✅ all | ✅ all | ✅ all | ✅ all |
| RULE-05 (Module boundaries) | ✅ primary | ✅ primary | ✅ aware | — |
| RULE-06 (One responsibility) | ✅ all | ✅ all | ✅ all | ✅ all |
| RULE-07 (Dependency direction) | ✅ primary | ✅ primary | — | — |
| RULE-08 (External integrations) | ✅ primary | ⚠️ aware | — | — |
| RULE-09 (Type signatures) | ✅ all | ✅ all | ✅ all | ✅ all |
| RULE-10 (Tests mandatory) | — | — | — | ✅ primary |
| RULE-11 (No silent failures) | ✅ all | ✅ all | ✅ all | ✅ all |
| RULE-12 (Service Layer = public API) | ✅ primary | ✅ primary | ✅ aware | — |
| RULE-13 (Stream + non-stream interface) | ✅ primary | ✅ primary | ✅ aware | — |
| RULE-14 (Migrations required) | — | ✅ primary | — | ✅ tests |
| RULE-15 (No middleware.ts) | — | — | ✅ primary | — |
| RULE-16 (i18n namespace registration) | — | — | ✅ primary | — |
| RULE-17 (API-Frontend contract) | — | ✅ primary | ✅ primary | ✅ tests |
| RULE-18 (No hardcoded config) | — | ✅ primary | — | — |
| RULE-19 (SessionDep not AsyncSession) | — | ✅ primary | — | — |
| RULE-20 (No half-implementations) | ✅ all | ✅ all | ✅ all | ✅ all |
| RULE-21 (Re-review on material changes) | ✅ all | ✅ all | ✅ all | ✅ all |
| RULE-22 (Cross-Feature Coherence Gate) | ✅ primary | ✅ primary | ⚠️ aware | ⚠️ aware |
| RULE-23 (No undisciplined type suppressions) | ✅ all | ✅ all | ✅ all | ✅ all |

**Roles**: ✅ primary = you own this rule; ⚠️ aware = you consume it; — = not directly applicable; ✅ all = applies to everyone; ✅ tests = relevant for test writing.

## 2. Behavioral Instructions by Category

### Cardinal Rules — Before Every Task

- **RULE-01b**: Before importing anything from `pydantic_ai`, check: am I in `core/agents/` or `core/llm/`? If not, use `NarrareAgent`.
- **RULE-02**: If you're about to write an f-string containing prompt text ("You are…", instructions, context) → STOP. Create a prompt template in `core/prompts/` instead.
- **RULE-03**: Before writing ANY service class, write the Protocol first. If the Protocol doesn't exist, the service doesn't get written.
- **RULE-04**: Watch your line count. Soft target is the real target. At soft target → plan the split. At hard limit → build fails.
- **RULE-15**: Frontend specialists: NEVER create `middleware.ts`. Edit `proxy.ts`. Period.

### Structural Rules — During Design

- **RULE-05**: Check module ownership. If you need something from another module, use its public `__init__.py` exports only.
- **RULE-06**: One role per file. Adding DB queries to a service → extract a repository. Adding business logic to a router → extract a service.
- **RULE-07**: Draw the dependency arrow. If it points UP (repository → service, service → router, core → apps), it's wrong.
- **RULE-08**: External SDK? There's an adapter for that. Use the adapter, not the SDK directly.
- **RULE-14**: Touched `models.py`? You need a migration. Same task, same commit.
- **RULE-18**: Router parameters must come from DI/settings cascade, not hardcoded strings.
- **RULE-19**: Dependency factories: `SessionDep`, not bare `AsyncSession`. Always.

### Quality Rules — During Implementation

- **RULE-09**: Every function gets a return type. No exceptions. `Any` requires an approved exception.
- **RULE-10**: Service method → unit test. Router endpoint → integration test. No test = not done.
- **RULE-11**: Every `except` block: re-raise, log, or convert. Never `pass`. Never silent.
- **RULE-16**: Added `useTranslations("X")`? → Register in `request.ts` + create `X.json` in all 3 locales.
- **RULE-17**: Changed a Pydantic response field? Update the TypeScript type in the SAME commit.
- **RULE-23**: Every `# type: ignore` needs an error code + reason comment. Naked suppressions are build failures. Use `isinstance()` or `cast()` instead of suppressing union-attr.

### Future-Compatibility — During Architecture

- **RULE-12**: Service Layer is the only public API. New client (MCP, A2A, CLI)? New adapter calling existing services.
- **RULE-13**: LLM operations support `stream=True` and `stream=False` through the same method.
- **RULE-20**: Build it properly or don't build it. No stubs, no "Phase 1 only", no deferred streaming.
- **RULE-21**: Plan changed materially after architecture review? → Re-review required.

## 3. Common Violations and Prevention

| Violation | Prevention |
|-----------|-----------|
| f-string prompt in service | Use `PromptComposer` — if tempted, it's a RULE-02 violation |
| `PromptRegistry.resolve()` in apps/ or agents/ | Route through `PromptComposer.build()` only — RULE-02b |
| App-layer prompt loader (`importlib.resources` + `.replace()`) | Move loader into `core/prompts/`, add a route — RULE-02b |
| Feature system prompt concatenated into user channel | Pass `composed.system` as agent instructions, `composed.user` as user prompt — RULE-02b |
| Inline production fallback prompt string | Fail-fast on config error; remove degraded fallback — RULE-02b |
| `MetaPromptLoader` outside `core/prompts/` + capabilities/ | Use `NarrareMeta` Capability instead — RULE-02b |
| Service without Protocol | Write `contracts.py` FIRST — RULE-03 |
| Bare `AsyncSession` in deps | Always use `SessionDep` — RULE-19 |
| Hardcoded provider in router | Use settings cascade — RULE-18 |
| Missing migration for model change | Check: did I touch `models.py`? → create migration — RULE-14 |
| `middleware.ts` created | Edit `proxy.ts` instead — RULE-15 |
| File approaching 400 lines | Plan the split NOW, don't compress — RULE-04 |
| `Any` return type without exception | All functions need typed returns — RULE-09 |
| Silent `except: pass` | Re-raise, log, or convert — RULE-11 |
| Naked `# type: ignore` without error code | Always specify error code + reason — RULE-23 |
| `# type: ignore[union-attr]` instead of narrowing | Use `isinstance()` or `cast()` — RULE-23 |
| `# type: ignore[arg-type]` for Mocks | Implement the real Protocol — RULE-23 |

## 4. Enforcement Quick Reference

| Mechanism | Rules Enforced |
|-----------|---------------|
| **check_architecture.py** (pre-commit + CI) | RULE-01b, 02, 02b, 04, 06, 09, 11, 15, 19, 23 |
| **check_adoption.py** + **check_prompt_structure.py** (CI) | RULE-22 (prompt variable checks) |
| **Type system** (mypy --strict + pyright) | RULE-09 |
| **Coverage gates** (pytest --cov) | RULE-10 |
| **Contract tests** (backend-frontend field validation) | RULE-17 |
| **PR review** (Architecture Agent) | All rules |
| **Exceptions** (`# narrare: allow-*` inline comment) | Must be justified in PR |

## 5. Cross-Feature Rules

Rules that apply when a feature shares data with other features.

### Integration Contract Template

When Feature A consumes data from Feature B:

```markdown
### Integration Contract: Feature A ↔ Feature B

**Shared data source:** [KB entities | Storyboard | Frontmatter | wiki | memory | settings | …]

**Data direction:** Feature A → reads ← Feature B writes

**On data change (Feature B updates an entity):**
- [ ] Feature A sees the update immediately (direct DB read)
- [ ] Feature A uses a cached snapshot (TTL: [N] seconds)
- [ ] Feature A must be explicitly notified (via event bus)
- [ ] Feature A is NOT affected (reads different subset)

**On data deletion (Feature B deletes an entity):**
- [ ] Feature A handles gracefully (shows "not found", skips, uses fallback)
- [ ] Feature A crashes/errors — must be fixed in Feature A before deletion
- [ ] Deletion is blocked until Feature A is updated

**Expected schema/version:** [e.g., KB entity v2 with template_fields dict]
```

### Example: Storyboard ↔ KB Integration Contract

```markdown
### Integration Contract: Storyboard ↔ KB

**Shared data source:** KB entities (characters, locations, factions)
**Data direction:** Storyboard → reads ← KB writes

**On data change** (KB entity updated):
- Storyboard reads KB entities fresh on every access (no cache)
- Storyboard shows current KB entity name + summary + status
- If KB entity is status=archived, Storyboard shows "(archived)" suffix

**On data deletion** (KB entity deleted):
- Storyboard still shows the entity reference but with "(deleted)" marker
- Storyboard does NOT cascade delete — keeps reference with tombstone

**Expected schema:** KB entity v2 with: id, name, type, status, summary
```

### Variable Naming Convention

- **`writing_language`** is the canonical variable for output/writing language.
- **`language`** is a deprecated alias — do not use in new templates.
- **`explanation_language`** is a distinct variable (name meaning explanations), not an alias.
- See `variable_registry.py` → `VARIABLE_ALIASES` for the complete mapping.

### RULE-22 Quick Reference

- **What**: Cross-Feature Coherence Gate — mandatory validation before merging
  any feature that shares data with other features.
- **Who**: Architecture Specialist (Stage 2.5 — Semantic Review)
- **When**: During Stage 2 (Specification), before Stage 3 (Implementation)
- **Enforcement**: Checklist in feature spec. Verified during Semantic Review.
- **Source**: `docs/_shared/CONSTRAINTS.md` — RULE-22
- **Prompt variable governance**: new template variables are classified as
  user-authored, system-generated, or feature-dynamic before use; unregistered
  new variables are CI failures.
- **Context precedence**: current author instruction > explicit project writing
  profile/manual override > current scene/storyboard/timeline > curated KB >
  learned memory/mem0 > generated suggestions; high-impact conflicts are
  surfaced, not silently resolved.

## Related Files

- `constraints/rules.md` — tabular rule reference (109 lines)
- `standards/architectural-discipline.md` — principles: no shortcuts, root cause, sustainability
- `docs/_shared/CONSTRAINTS.md` — full rule text with rationale and examples (766 lines, source of truth)
