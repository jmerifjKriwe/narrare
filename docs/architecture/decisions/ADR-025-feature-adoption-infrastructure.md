# ADR-025 — Feature Adoption Infrastructure

> **Status:** ✅ Accepted
> **Date:** 2026-05-31
> **Deciders:** Architecture Agent
> **Supersedes:** —
> **Related:** ADR-002 (Unified Prompt System), ADR-019 (System-Prompt Consistency), ADR-037 (Prompt Surface Contract Manifest), ADR-038 (AI Invocation Adoption Contract), CONSTRAINTS.md RULE-01b/02/03/04/20/22

---

## Context

A comprehensive content review audit (CR-03) identified that despite excellent core infrastructure — TokenBudget, mem0, KG-Relationships, PromptComposer, InjectionDefense — many features do not adopt it consistently. The root causes are:

1. **Passive documentation, no active enforcement.** `check_architecture.py` enforces RULE-01b–19 (technical), but NO checks exist for content/feature adoption (TokenBudget, mem0, KG, i18n).
2. **Quality Gates exist only as text.** Referenced in Coordinator prompt and now materialized as `.opencode/context/narrare-dev/processes/quality-gates.md` *(2026-10-15 correction: that path was removed in f11eb44a and the doc anchor retired by ADR-098 — each ADR states its own completeness checklist; the gate SSOT is the ci.yml header table + CONSTRAINTS.md §6.)* (Gate 1–7), but missing the Feature Adoption Gate and AI Content Review Gate.
3. **Dual Prompt paths.** Bundled (via PromptComposer) and Inline (Python strings). Changes to PromptComposer don't reach Inline prompts. Three files contain inline fallbacks: `consistency/prompt_builder.py`, `kb/extraction_service.py`, `agents/writing_graph_prompts.py`.
4. **No ContextAssembly abstraction outside Writing.** Only Writing features use the 5-tier TokenBudget (`WritingContextAssembler` + `TokenBudgetManager`). Analysis features (Beta-Reader, Story-Suggest) and KB features build context manually with no budget protection.
5. **No Health Metrics for Feature Adoption.** No automated measurement of how well features adopt core infrastructure.
6. **No Feature-Adoption Gate in CI/CD.** Nothing fails when a new feature omits `{{kb_relationships}}`.

### Root Cause Analysis

**Symptom:** Features don't consistently adopt core infrastructure.

**Root Cause (Why #1):** Developers (AI and human) don't know which infrastructure a feature must adopt.

**Root Cause (Why #2):** There is no machine-readable definition of feature→infrastructure requirements, and no CI gate to enforce it.

**Root Cause (Why #3):** The architecture is documented in prose (CONSTRAINTS.md, ADRs) but not operationalized as a schema that can be validated automatically. Documentation is passive — it informs but does not enforce.

**Design Principle:** The solution must be a **schema-driven enforcement layer**, not more documentation.

---

## Decision 1: Adoption Registry (ADR)

### Problem

No machine-readable definition maps which features MUST adopt which core infrastructure.

### Options Considered

#### Option A — YAML Registry File (chosen)

A single `adoption-registry.yaml` in `scripts/architecture/` defining feature→infrastructure requirements.

```yaml
# scripts/architecture/adoption-registry.yaml
version: "1.0.0"

features:
  writing:
    modes: [new_chapter, extend, extend_chapter, rewrite, rewrite_selection]
    required_infrastructure:
      token_budget: required
      prompt_composer: required
      mem0_preferences: required
      kb_entities: required          # at least characters + locations
      kb_relationships: required     # ← catches the missing {{kb_relationships}} gap
      injection_defense: required
      meta_prompt: required
      i18n: required
    context_variables:
      must: [user_preferences, avoidance_patterns, kb_characters, kb_locations,
             kb_factions, kb_relationships, culture_guidelines]
      should: [character_voice_profiles, wiki_summaries]

  analysis:
    modes: [beta_read, story_suggest, consistency_check]
    required_infrastructure:
      token_budget: required
      prompt_composer: required
      mem0_preferences: required
      kb_entities: partial          # context-dependent
      injection_defense: required
      meta_prompt: required
      i18n: required
    context_variables:
      must: [user_preferences, avoidance_patterns]
      should: [kb_characters, kb_locations, kb_factions]

  kb:
    modes: [create, edit, extract, interview]
    required_infrastructure:
      token_budget: partial         # extract/interview need it, simple CRUD doesn't
      prompt_composer: required
      injection_defense: required
      meta_prompt: required
      i18n: required
    context_variables:
      must: [user_preferences, avoidance_patterns]

  generation:
    modes: [names, chapter_titles, outlines]
    required_infrastructure:
      prompt_composer: required
      meta_prompt: required
      i18n: required
    context_variables:
      must: [user_preferences, avoidance_patterns]

infrastructure_definitions:
  token_budget:
    description: "TokenBudgetManager with tier allocation"
    evidence: "uses TokenBudgetManager or ContextAssembler with budget"
  prompt_composer:
    description: "PromptComposer.build() for system prompt"
    evidence: "calls composer.build() or uses bundled prompt file"
  mem0_preferences:
    description: "User preferences from memory layer"
    evidence: "includes {{user_preferences}} variable"
  kb_entities:
    description: "KB entity context injection"
    evidence: "includes {{kb_characters}}, {{kb_locations}}, {{kb_factions}}"
  kb_relationships:
    description: "KB relationship graph injection"
    evidence: "includes {{kb_relationships}} variable"
  injection_defense:
    description: "User content wrapped in XML tags"
    evidence: "all UNSAFE_USER_VARS wrapped in <tag>...</tag>"
  meta_prompt:
    description: "Narrare identity meta-prompt guaranteed by ADR-026 Capability"
    evidence: "uses PromptComposer or has agent inheriting NarrareAgent (Capabilities auto-injected per ADR-026)"
  i18n:
    description: "Bundled prompt exists in en/de/fr"
    evidence: "system.md in all 3 locale directories"
```

**Pros:**
- Machine-readable, CI-validatable, human-editable
- New features added without code changes — just edit the YAML
- Supports tiered requirements: required / partial / optional
- Supports mode-specific overrides within a feature
- Single source of truth for adoption expectations

**Cons:**
- New file to maintain
- Must be kept in sync with actual feature implementation
- YAML parsing adds complexity to CI checks

#### Option B — Python Dataclass in a Module

Define the registry as typed Python dataclasses in `scripts/architecture/registry.py`.

**Pros:**
- Type-safe at import time
- IDE autocomplete
- Python-native, no YAML parser needed

**Cons:**
- Adding a new feature requires code changes (editing Python)
- More boilerplate for the same information
- Harder for non-Python tools to consume
- Violates the principle: "extensible without code changes"

#### Option C — TOML in pyproject.toml

Extend the existing `[tool.narrare.architecture]` section.

**Pros:**
- Co-located with existing architecture config
- Already loaded by `helpers.py`

**Cons:**
- pyproject.toml is already a dumping ground — adding a full adoption registry makes it unwieldy
- TOML lacks the hierarchical expressiveness of YAML for this data shape
- Harder to review in PRs (one massive file)

### Decision

**We choose Option A — YAML Registry File.**

The registry lives at `scripts/architecture/adoption-registry.yaml`. It is loaded by the adoption checker and by `check_prompt_structure.py` for context-variable validation. Adding a new feature requires editing one YAML file — no code changes.

### Integration with CI

A new checker module `scripts/architecture/_checkers/adoption.py` reads the registry and validates:

1. **Prompt-level check**: Every bundled prompt in `_bundled/{category}/` has the `must` variables listed in the registry for that category.
2. **Feature-level check**: Every service in `apps/api/narrare/{domain}/` uses the required infrastructure.
3. **Gap detection**: The registry lists what's required; the checker reports what's missing.

### RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02 | ✅ | Registry tracks whether prompts go through PromptComposer |
| RULE-03 | ✅ | Contract defined: registry YAML schema is the contract |
| RULE-04 | ✅ | YAML file is pure data, checker is a separate module |
| RULE-05 | ✅ | Registry in `scripts/architecture/`, co-located with existing checkers |

---

## Decision 2: Context-Variable-Map (Architecture Note)

### Problem

`REQUIRED_VARS_BY_CATEGORY` in `prompt_checks.py` (lines 51-58) only defines `user_preferences` and `avoidance_patterns` as required for all categories. It does not cover:
- KB relationship variables (`kb_relationships` — currently MISSING from all Writing prompts)
- Tiered requirements (MUST vs SHOULD)
- Mode-specific requirements (e.g., `extend_chapter` needs `existing_content`, `new_chapter` doesn't)

### Options Considered

#### Option A — Expand `REQUIRED_VARS_BY_CATEGORY` (chosen)

Extend the existing data structure in `prompt_checks.py` with tiered requirements:

```python
# In prompt_checks.py — expand REQUIRED_VARS_BY_CATEGORY
REQUIRED_VARS_BY_CATEGORY: dict[str, set[str]] = {
    "writing": {
        "user_preferences", "avoidance_patterns",
        "kb_characters", "kb_locations", "kb_factions",
        "kb_relationships",  # ← NEW: catches the gap
        "culture_guidelines",
    },
    "kb": {"user_preferences", "avoidance_patterns"},
    "analysis": {"user_preferences", "avoidance_patterns"},
    "planning": {"user_preferences", "avoidance_patterns", "culture_guidelines"},
    "generation": {"user_preferences", "avoidance_patterns"},
    "chat": {"user_preferences", "avoidance_patterns"},
}

# NEW: Mode-specific additions (added on top of category requirements)
MODE_REQUIRED_VARS: dict[str, dict[str, set[str]]] = {
    "writing": {
        "extend_chapter": {"existing_content"},
        "extend": {"existing_content"},
        "rewrite_selection": {"selection_text", "context_before", "context_after"},
    },
}

# NEW: Tiered variables (SHOULD level — warns, doesn't fail)
SHOULD_VARS_BY_CATEGORY: dict[str, set[str]] = {
    "writing": {"character_voice_profiles", "kb_suggested"},
    "analysis": {"kb_characters", "kb_locations"},
}
```

**Pros:**
- Minimal change to existing infrastructure
- Leverages existing `_check_required_vars()` function
- Tiered: MUST vars → FAIL, SHOULD vars → WARN
- Mode-specific: extends category requirements per mode

**Cons:**
- Python dataclass, not YAML — requires code changes to add new categories
- Duplicated between `prompt_checks.py` and `adoption-registry.yaml`

#### Option B — Single Source from Adoption Registry

Read variable requirements from the adoption registry YAML instead of hardcoding in Python.

**Pros:**
- Single source of truth (the YAML registry)

**Cons:**
- `check_prompt_structure.py` would need to load YAML
- The prompt check pipeline is currently pure Python with no file I/O beyond .md parsing
- Over-engineering for the current scope
- Breaks the separation: `check_prompt_structure.py` validates prompt FILES, the adoption registry validates FEATURE adoption

#### Option C — Separate Variable Map YAML

A dedicated `context-variables.yaml` file.

**Pros:**
- Machine-readable

**Cons:**
- Yet another config file for overlapping concerns
- The `REQUIRED_VARS_BY_CATEGORY` approach already works — just needs expansion

### Decision

**We choose Option A — Expand `REQUIRED_VARS_BY_CATEGORY`.**

The existing `REQUIRED_VARS_BY_CATEGORY` is the right place — it's already loaded by `check_prompt_structure.py` and used by `_check_required_vars()`. We extend it with:

1. **More variables per category** (especially `kb_relationships` for writing)
2. **`MODE_REQUIRED_VARS`** for mode-specific additions
3. **`SHOULD_VARS_BY_CATEGORY`** for tiered warnings

The adoption registry (Decision 1) remains the high-level feature→infrastructure map. The variable map in `prompt_checks.py` remains the detailed prompt-level validator. Both reference the same variable names, but serve different validation scopes.

### Key Gap Fixed

This immediately fixes the identified gap: Writing prompts will be REQUIRED to include `{{kb_relationships}}`. The next run of `check_prompt_structure.py --strict` will FAIL until the variable is added to all writing system.md files.

### RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-04 | ✅ | New constants added to existing module, no file size issue |
| RULE-10 | ✅ | Tests verify new required variables trigger warnings |

---

## Decision 3: ContextAssembler Centralization (ADR)

### Problem

`WritingContextAssembler` (342 lines) is the ONLY feature that uses the 5-tier `TokenBudgetManager` (264 lines). Analysis features (Beta-Reader, Story-Suggest, Consistency) and KB features build context manually with no budget protection.

Two context data models exist:
- `PromptContext` (generic, in `core/prompts/context.py`) — flat field model with `as_variables()`
- `WritingContext` (specific, in `core/writing/models.py`) — tier-aware with `to_prompt_variables()`

### Options Considered

#### Option A — Generic `ContextAssembler` Base + Feature-Specific Subclasses (chosen)

Create an abstract `ContextAssembler` base class in `core/context/assembler.py` that defines the tier-based assembly contract. `WritingContextAssembler` becomes the first concrete implementation. New assemblers (`AnalysisContextAssembler`, `KBContextAssembler`) share the same `TokenBudgetManager` but define their own tier schemas.

```
core/context/                     ← NEW: generic context assembly
├── __init__.py                   ← exports ContextAssembler, TokenBudgetManager
├── assembler.py                  ← abstract ContextAssembler base class
├── budget.py                     ← TokenBudgetManager (MOVED from writing/budget.py)
└── types.py                      ← shared types: TierBudget, ContextTier

core/writing/context_assembler.py ← WritingContextAssembler(ContextAssembler)
core/analysis/assembler.py        ← NEW: AnalysisContextAssembler(ContextAssembler)
core/kb/assembler.py              ← NEW: KBContextAssembler(ContextAssembler) (future)
```

**Pros:**
- Every feature type gets token budget protection
- `TokenBudgetManager` is generic (it already uses generic tier names)
- Clear contract: `assemble() -> dict[str, str]` (prompt variables)
- Writing stays as-is — no changes to `WritingContextAssembler` beyond inheritance
- Follows existing pattern: base in `core/`, specific in feature module

**Cons:**
- Requires moving `budget.py` from `writing/` to `context/` — import path change
- New abstract class needs Protocol + implementation
- Analysis and KB assemblers are future work (not implemented in this ADR)

#### Option B — Extend `WritingContextAssembler` to Support Non-Writing

Add an `assembly_mode` parameter to `WritingContextAssembler` that switches tier schemas between WRITING, ANALYSIS, KB.

**Pros:**
- No new classes, no moves

**Cons:**
- Violates RULE-06 (one responsibility per file)
- `WritingContextAssembler` becomes a god class
- Writing-specific tiers (kb_characters, kb_factions, kb_locations) don't apply to Analysis
- Analysis has different tier priorities (no "recent chapters" concept)
- Fails the sustainability check — this class will keep growing

#### Option C — Per-Feature Assemblers Without Base Class

Each feature gets its own assembler class, no shared base. `TokenBudgetManager` stays in `writing/` and is imported by other features.

**Pros:**
- Minimal refactoring
- Each assembler is independent

**Cons:**
- No contract — each assembler has a different API
- No guarantee that new assemblers use TokenBudgetManager
- Violates RULE-03 (contract before implementation) — no Protocol
- The adoption registry can't validate "uses ContextAssembler" because there's no base type

### Decision

**We choose Option A — Generic `ContextAssembler` Base + Feature-Specific Subclasses.**

The base class defines the contract:

```python
# core/context/contracts.py
class ContextAssemblerProtocol(Protocol):
    async def assemble(self, **kwargs: Any) -> dict[str, str]: ...
    @property
    def total_budget(self) -> int: ...
    def get_tier_allocation(self) -> dict[str, TierBudget]: ...
```

`TokenBudgetManager` moves from `writing/budget.py` to `context/budget.py` (note: the GLOSSARY already references `core/context/budget.py` — this was always the intended location). Backward-compatible re-export stays in `writing/budget.py`.

`WritingContextAssembler` gains the base class but its public API does not change. Its `assemble()` method continues to return `WritingContext` (which has `to_prompt_variables()`). New assemblers return `dict[str, str]` directly.

### Migration Path

1. **Phase 1**: Create `core/context/` with base class + moved `TokenBudgetManager`. Re-export from `writing/budget.py`.
2. **Phase 2**: `WritingContextAssembler` inherits from `ContextAssembler` base. No API change.
3. **Phase 3**: Create `AnalysisContextAssembler` for Beta-Reader and Story-Suggest features.
4. **Phase 4**: Create `KBContextAssembler` for extraction and interview features.

Each phase is complete and self-contained.

### RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | `ContextAssemblerProtocol` defined before implementation |
| RULE-04 | ✅ | Each file < 300 lines. Base class ~80 lines. |
| RULE-05 | ✅ | `core/context/` owns the abstraction. Feature modules own implementations. |
| RULE-06 | ✅ | One responsibility: base defines contract, features define tiers |
| RULE-07 | ✅ | Dependency: feature module → core/context/ (correct direction) |

---

## Decision 4: Inline-Fallback Policy (ADR)

### Problem

Three locations contain hardcoded inline prompts that bypass PromptComposer:

| File | Lines | Pattern |
|------|-------|---------|
| `apps/api/narrare/consistency/prompt_builder.py` | 33–65 | `CONSISTENCY_SYSTEM_PROMPT` with `get_system_prompt()` (meta injected by NarrareMeta Capability per ADR-026) |
| `apps/api/narrare/kb/extraction_service.py` | 40–57 | `_DEFAULT_SYSTEM_PROMPT` with 3-tier cascade |
| `packages/core/narrare_core/agents/writing_graph_prompts.py` | multiple | Fallback when `composer is None` |

These follow a documented 2-tier approach: PromptComposer → Inline fallback. Meta-prompt is injected automatically by NarrareMeta Capability (ADR-026).

### Options Considered

#### Option A — Inline Fallbacks Allowed with Mandatory Registration (chosen)

Inline prompts are NOT banned — they serve a valid purpose as last-resort fallbacks when PromptComposer has no bundled prompt for a feature. However, they MUST be:

1. **Registered** in the adoption registry with `inline_fallback: true`
2. **Documented** with a comment referencing the ADR and explaining why no bundled prompt exists
3. **Detected** by `check_architecture.py` — inline prompts without registry entry = FAIL
4. **Tracked** for migration — each inline fallback has a target bundled prompt path

```yaml
# In adoption-registry.yaml
inline_fallbacks:
  - file: "apps/api/narrare/consistency/prompt_builder.py"
    lines: "33-65"
    variable: "CONSISTENCY_SYSTEM_PROMPT"
    status: registered
    migration_target: "prompts/_bundled/consistency/en/system.md"
    reason: "Consistency bundled prompt not yet authored (CONS-001)"
  - file: "apps/api/narrare/kb/extraction_service.py"
    lines: "40-57"
    variable: "_DEFAULT_SYSTEM_PROMPT"
    status: registered
    migration_target: "prompts/_bundled/kb/en/extract/system.md"
    reason: "Extraction bundled prompt not yet authored (KB-007)"
```

**Pros:**
- Pragmatic: inline fallbacks serve a real purpose during development
- Trackable: every inline prompt is registered with a migration target
- CI-enforced: unregistered inline prompts fail the build
- Gradual: migrate to bundled prompts on a feature-by-feature basis

**Cons:**
- Inline prompts still exist in the codebase until migration
- Registry tracking requires manual updates

#### Option B — Ban All Inline Prompts (FAIL on Detection)

`check_architecture.py` fails if ANY inline prompt string > 50 characters is found outside `core/prompts/`.

**Pros:**
- Zero tolerance — guarantees all prompts go through PromptComposer
- Simple rule to enforce

**Cons:**
- Blocks legitimate development: when writing a new agent, you need a prompt before you have a bundled file
- WritingGraph fallbacks (when `composer is None`) are needed for test ergonomics
- The 3-tier cascade (ADR-019) was explicitly designed to support this pattern
- Overly strict — forces prompt files to exist before agent development can proceed

#### Option C — Mandatory Logging Guard Only

Allow inline prompts but require `logger.warning("inline_prompt_used", ...)` at every usage site.

**Pros:**
- Minimal enforcement
- Runtime visibility

**Cons:**
- No CI enforcement — warnings don't fail builds
- Doesn't address the structural issue (changes to PromptComposer don't reach inline)
- Not trackable

### Decision

**We choose Option A — Inline Fallbacks Allowed with Mandatory Registration.**

Inline fallbacks are a legitimate development tool (ADR-019 explicitly supports the PromptComposer → MetaPrompt → Inline cascade). Banning them would block agent development workflows. Instead, we make them **trackable and CI-enforced**:

1. Every inline prompt > 100 characters outside `core/prompts/` must be registered in the adoption registry.
2. Unregistered inline prompts are detected by `check_architecture.py` and cause a FAIL.
3. Each registered inline prompt has a migration target — a bundled prompt path that, once created, eliminates the need for the inline fallback.
4. The adoption score (Decision 5) penalizes registered inline fallbacks.

### Detection Mechanism

A new checker in `scripts/architecture/_checkers/inline_prompts.py`:

```python
def check_inline_prompts(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    registered_fallbacks: list[dict[str, str]],
) -> list[Violation]:
    """RULE-INLINE: Inline prompt strings >100 chars must be registered.

    Detects:
    - String literals containing prompt-like patterns (>100 chars, contains
      "You are" / "Your job" / "Your task" / similar role assignment)
    - String assignments to module-level variables
    - f-string prompt construction outside core/prompts/
    """
```

This checker integrates into the existing `scan_file()` pipeline in `_checkers/__init__.py`.

### RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02 | ✅ | Registered inline prompts are tracked exceptions to RULE-02 |
| RULE-11 | ✅ | Unregistered inline prompts are detected and reported (not silent) |

---

## Decision 5: Adoption Score in CI (Architecture Note)

### Problem

No automated metric measures how well features adopt core infrastructure.

### Options Considered

#### Option A — Weighted Ratio from Registry (chosen)

Score = Σ(weight × adopted) / Σ(weight × applicable), where:

- `required` infrastructure: weight = 1.0
- `partial` infrastructure: weight = 0.5 (adopted = 0.5 if missing, 1.0 if present)
- `should` variables: weight = 0.3
- `must` variables: weight = 1.0
- `inline_fallback` registered: weight = -0.1 per fallback (slight penalty)

**Threshold:**
- Score ≥ 0.85 → PASS (CI continues)
- Score 0.70–0.85 → WARN (CI continues, but reports gaps)
- Score < 0.70 → FAIL (CI stops)
- NEW features (not in registry yet) → automatic WARN until registered

**Implementation:**

A new script `scripts/check_adoption.py` that:

1. Reads `adoption-registry.yaml`
2. Scans bundled prompts for variable presence
3. Scans service files for infrastructure usage (heuristic: import analysis)
4. Computes per-feature and overall scores
5. Outputs JSON + human-readable summary
6. Exits 0/1/2 based on thresholds

#### Option B — Simple Binary Pass/Fail

Every feature must adopt ALL required infrastructure. One miss = FAIL.

**Rejected:** Too strict for partial infrastructure (e.g., KB features don't need full entity injection). The tiered approach (required/partial) exists precisely because not all infrastructure applies equally.

#### Option C — External Dashboard (Logfire)

Ship adoption metrics to Logfire for visualization.

**Rejected as primary mechanism.** Logfire is excellent for runtime observability, but adoption is a CI-time concern — it should be validated before code is merged, not after deployment. Logfire can be added later as a supplementary visualization.

### Decision

**We choose Option A — Weighted Ratio from Registry.**

The score is computed by `scripts/check_adoption.py`, which reads the adoption registry and validates against the codebase. It integrates into CI as a new step between `check_architecture.py` and `check_prompt_structure.py`.

### CI Pipeline Update

```
1. ruff format + lint
2. check_architecture.py        (RULE enforcement)
3. check_adoption.py             ← NEW: adoption score
4. check_prompt_structure.py     (prompt variable validation)
5. mypy --strict + pyright
6. pytest -m unit
7. pytest -m integration
8. pnpm test
9. bandit
```

### Output Format

```
Feature Adoption Score: 0.82 (WARN)

  writing:       0.91 ✅  (missing: kb_relationships in 2 prompts)
  analysis:      0.73 ⚠️  (missing: token_budget, kb_entities partial)
  kb:            0.85 ✅  (1 inline fallback registered)
  generation:    1.00 ✅

Overall: WARN (threshold: 0.85, actual: 0.82)
See: scripts/architecture/adoption-registry.yaml
```

### RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-10 | ✅ | Adoption checker has its own unit tests |
| RULE-04 | ✅ | `check_adoption.py` stays under 200 lines; heavy lifting in `adoption/` module |

---

## Decision 6: Quality Gates as Files (Architecture Note)

### Problem

Quality gates exist at `.opencode/context/narrare-dev/processes/quality-gates.md` *(path removed f11eb44a; retired by ADR-098)* (Gates 1–7), but two gates are missing:

1. **Feature Adoption Gate** — validates that new features adopt required infrastructure
2. **AI Content Review Gate** — the CR-06 checklist for content quality

### Decision

**Add two new gates to the existing quality-gates.md.** Do NOT create separate files.

#### Gate 8: Feature Adoption Gate (NEW)

```markdown
## Gate 8: Feature Adoption Gate

Runs `scripts/check_adoption.py` in CI.
- Reads adoption registry
- Validates feature→infrastructure mapping
- Computes adoption score

Thresholds:
  - Score ≥ 0.85: PASS
  - Score 0.70–0.85: WARN
  - Score < 0.70: FAIL

When adding a new feature:
1. Register it in `scripts/architecture/adoption-registry.yaml`
2. Include all required infrastructure
3. Verify `check_adoption.py` scores ≥ 0.85
```

#### Gate 9: AI Content Review Gate (NEW)

```markdown
## Gate 9: AI Content Review Gate

Applies to features that involve prompt engineering, LLM interaction,
or user-facing AI output.

Checklist (per feature):
- [ ] Prompt uses PromptComposer (not inline, unless registered)
- [ ] All MUST variables present (check_prompt_structure.py passes)
- [ ] Meta-prompt included (ADR-019)
- [ ] Injection defense: user content XML-wrapped
- [ ] i18n: prompt files in en/de/fr
- [ ] Token budget enforced (ContextAssembler used)
- [ ] Memory layer: {{user_preferences}} and {{avoidance_patterns}} included
- [ ] Error handling: LLM failures don't crash (RULE-11)
- [ ] Streaming: SSE where backend supports it (RULE-13)

Validated by: check_adoption.py + check_prompt_structure.py + check_architecture.py
```

These gates are CI-enforced. Gate 8 is automated via `check_adoption.py`. Gate 9 is partially automated (items 1–7 are machine-checked; items 8–9 are validated by existing architecture checks).

### RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-20 | ✅ | No half-implementations — Gate 8 catches missing infrastructure |
| RULE-10 | ✅ | Coverage minimums are Gate 2; adoption is Gate 8 |

---

## Decision 7: Pattern Library for Feature Development (Architecture Note)

### Problem

New features need templates that ensure automatic adoption of core infrastructure.

### Options Considered

#### Option A — Base Classes + Contracts + Checklist (chosen)

Three components:

1. **`ContextAssembler` base class** (Decision 3) — provides the tier-based assembly pattern
2. **`FeatureContracts` template** — a reference `contracts.py` showing required protocols
3. **Pre-implementation checklist** — in the adoption registry, per feature type

```yaml
# In adoption-registry.yaml
feature_templates:
  writing_feature:
    extends: writing
    required_files:
      - "core/writing/{feature}/contracts.py"
      - "core/writing/{feature}/assembler.py"
      - "apps/api/narrare/writing/{feature}_service.py"
    must_use:
      - "ContextAssembler (or WritingContextAssembler)"
      - "PromptComposer.build()"
      - "TokenBudgetManager"
    checklist:
      - "Register in adoption-registry.yaml"
      - "Create bundled prompt in _bundled/writing/{lang}/{mode}/system.md"
      - "Add context variables from writing.must list"
      - "Add unit tests with >90% coverage"
      - "Verify check_adoption.py scores ≥ 0.85"
```

**Pros:**
- Lightweight — no code generation, no cookiecutter
- Base class enforces the pattern (can't skip TokenBudget)
- Checklist is CI-referenceable
- Adapts to each feature type

**Cons:**
- Requires developer discipline to follow the checklist
- Not as automated as code generation

#### Option B — Cookiecutter Template

A full project template that generates the feature scaffold.

**Rejected:** Over-engineering for the current team size (AI agents + one developer). Cookiecutter adds maintenance burden — templates drift from actual code patterns. The base class approach is more sustainable because the pattern is in the code itself, not in a separate template.

#### Option C — Documentation Templates Only

Markdown templates that describe what to build.

**Rejected:** Passive documentation is the root cause of the current problem (see Root Cause Analysis). Documentation-only templates are insufficient — they inform but do not enforce.

### Decision

**We choose Option A — Base Classes + Contracts + Checklist.**

The enforcement comes from three layers:

1. **Structural**: `ContextAssembler` base class makes it impossible to skip token budget (constructor requires it)
2. **CI**: Adoption registry + checker validates against the checklist
3. **Process**: Feature pipeline (Stage 2: Specification) references the adoption registry for requirements

No cookiecutter, no documentation-only templates. The pattern is **in the code** and **enforced by CI**.

---

## Implementation Roadmap

### Dependency Graph

```
Decision 1 (Adoption Registry)
    ├── Decision 2 (Context-Variable-Map) — reads registry for variable requirements
    ├── Decision 4 (Inline-Fallback Policy) — registry tracks inline fallbacks
    ├── Decision 5 (Adoption Score) — reads registry for scoring
    └── Decision 7 (Pattern Library) — registry defines feature templates

Decision 3 (ContextAssembler Centralization)
    └── Independent — can be implemented in parallel

Decision 6 (Quality Gates)
    └── Depends on Decisions 1 + 5 (references check_adoption.py)
```

### Phased Implementation

#### Phase 1: Foundation (Decisions 1 + 2) — No code changes to production

| Step | What | Files |
|------|------|-------|
| 1.1 | Create `adoption-registry.yaml` | `scripts/architecture/adoption-registry.yaml` (NEW) |
| 1.2 | Expand `REQUIRED_VARS_BY_CATEGORY` | `scripts/prompt_checks.py` (MODIFY) |
| 1.3 | Add `MODE_REQUIRED_VARS` + `SHOULD_VARS_BY_CATEGORY` | `scripts/prompt_checks.py` (MODIFY) |
| 1.4 | Add mode-aware variable check to `_check_required_vars()` | `scripts/prompt_checks.py` (MODIFY) |
| 1.5 | Write unit tests for expanded checks | `tests/unit/scripts/test_prompt_checks.py` (NEW) |

**Verification:** `python scripts/check_prompt_structure.py --strict` now catches the missing `{{kb_relationships}}` gap.

#### Phase 2: Enforcement (Decisions 4 + 5)

| Step | What | Files |
|------|------|-------|
| 2.1 | Add inline fallback entries to adoption registry | `scripts/architecture/adoption-registry.yaml` (MODIFY) |
| 2.2 | Create `inline_prompts.py` checker | `scripts/architecture/_checkers/inline_prompts.py` (NEW) |
| 2.3 | Integrate into `scan_file()` | `scripts/architecture/_checkers/__init__.py` (MODIFY) |
| 2.4 | Create `check_adoption.py` | `scripts/check_adoption.py` (NEW) |
| 2.5 | Create `adoption/` module for score computation | `scripts/adoption/scorer.py` (NEW) |
| 2.6 | Write unit tests for adoption checker | `tests/unit/scripts/test_check_adoption.py` (NEW) |
| 2.7 | Update CI pipeline | CI config (MODIFY) |

**Verification:** `python scripts/check_adoption.py` outputs adoption scores and exits non-zero below threshold.

#### Phase 3: Architecture (Decision 3) — Can run in parallel with Phase 2

| Step | What | Files |
|------|------|-------|
| 3.1 | Create `core/context/` package | `packages/core/narrare_core/context/__init__.py` (NEW) |
| 3.2 | Move `TokenBudgetManager` to `core/context/budget.py` | `core/context/budget.py` (NEW), `core/writing/budget.py` (re-export) |
| 3.3 | Create `ContextAssemblerProtocol` | `core/context/contracts.py` (NEW) |
| 3.4 | Create abstract `ContextAssembler` base | `core/context/assembler.py` (NEW) |
| 3.5 | Update `WritingContextAssembler` to inherit | `core/writing/context_assembler.py` (MODIFY) |
| 3.6 | Update all imports | All files importing from `writing/budget.py` |
| 3.7 | Write unit tests for base class | `tests/unit/core/context/test_assembler.py` (NEW) |

**Verification:** All existing tests pass. `WritingContextAssembler` API unchanged.

#### Phase 4: Documentation (Decisions 6 + 7)

| Step | What | Files |
|------|------|-------|
| 4.1 | Add Gate 8 (Feature Adoption Gate) | `.opencode/context/narrare-dev/processes/quality-gates.md` *(path removed f11eb44a; retired by ADR-098)* (MODIFY) |
| 4.2 | Add Gate 9 (AI Content Review Gate) | `.opencode/context/narrare-dev/processes/quality-gates.md` *(path removed f11eb44a; retired by ADR-098)* (MODIFY) |
| 4.3 | Add feature templates to adoption registry | `scripts/architecture/adoption-registry.yaml` (MODIFY) |
| 4.4 | Update feature pipeline to reference adoption registry | `.opencode/context/narrare-dev/processes/feature-pipeline.md` (MODIFY) |
| 4.5 | Update ADR INDEX | `docs/architecture/decisions/INDEX.md` (MODIFY) |

**Verification:** Quality gates document references `check_adoption.py`. Feature pipeline references adoption registry.

#### Phase 5: Future (Analysis ContextAssembler)

| Step | What | Files |
|------|------|-------|
| 5.1 | Create `AnalysisContextAssembler` | `core/analysis/assembler.py` (NEW) |
| 5.2 | Define analysis tier schema | `core/analysis/tiers.py` (NEW) |
| 5.3 | Integrate with Beta-Reader and Story-Suggest services | `apps/api/narrare/analysis/` (MODIFY) |
| 5.4 | Register analysis assembler in adoption registry | `scripts/architecture/adoption-registry.yaml` (MODIFY) |

**This phase is NOT part of the current ADR scope.** It is documented here to show the intended evolution path.

---

## RULE-XX Compliance Matrix

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | Registry tracks agent/model import compliance (indirect) |
| RULE-02 | ✅ | Registry tracks PromptComposer usage; inline prompts must be registered |
| RULE-03 | ✅ | `ContextAssemblerProtocol` defined before implementation (Decision 3) |
| RULE-04 | ✅ | Each new file respects limits. `adoption-registry.yaml` is pure data. |
| RULE-05 | ✅ | New `core/context/` package owns the assembly abstraction |
| RULE-06 | ✅ | One responsibility: registry = data, checker = validation, scorer = computation |
| RULE-07 | ✅ | Dependency: checkers → registry (correct). context/ ← writing/ (correct). |
| RULE-08 | ✅ | Not directly affected. Infrastructure adapters unchanged. |
| RULE-09 | ✅ | All new public functions have type annotations |
| RULE-10 | ✅ | Every new module has corresponding tests |
| RULE-11 | ✅ | No silent failures — unregistered inline prompts are detected |
| RULE-12 | ✅ | Not directly affected. Service layer pattern unchanged. |
| RULE-13 | ✅ | Not directly affected. Streaming interface unchanged. |
| RULE-14 | ✅ | Not affected. No DB schema changes. |
| RULE-20 | ✅ | Gate 8 catches missing infrastructure — no half-implementations |

---

## Consequences

### Positive

1. **Machine-enforced adoption** — CI fails when features don't adopt required infrastructure
2. **Gap detection** — `{{kb_relationships}}` missing from Writing prompts would be caught immediately
3. **Extensible** — New features added by editing YAML, no code changes
4. **Token budget for all features** — Analysis and KB features get the same budget protection as Writing
5. **Trackable inline prompts** — Every inline fallback is registered with a migration target
6. **Adoption scoring** — Quantifiable metric for infrastructure adoption health

### Negative / Trade-offs

1. **New YAML file to maintain** — The adoption registry must be kept in sync with actual features
2. **Moving TokenBudgetManager** — Import path change requires updates across the codebase
3. **Inline prompts still exist** — We chose tracking over banning; migration is gradual
4. **Score thresholds are subjective** — 0.85 threshold is a starting point, may need adjustment
5. **No automated "does service use PromptComposer?" check** — The adoption checker uses heuristic import analysis, not precise usage tracking

---

## Review Trigger

### Runtime Evidence Addendum (ADR-038)

ADR-025 defines the static adoption registry and scoring direction. ADR-038 adds the
runtime contract required before an adoption claim can be marked adopted: a feature
mode must prove that its production invocation path enriched or explicitly injected
required context, built the prompt through `PromptComposer`, validated the final
prompt, resolved an intent/mode output budget, and recorded privacy-safe evidence.

Therefore, a passing adoption score or prompt/template check is `static_verified`,
not `adopted`, until runtime evidence exists. ADR-037 remains the route-level prompt
surface contract; ADR-038 governs the request-to-model invocation path.

- [ ] After Phase 2 complete — verify adoption score thresholds are calibrated correctly
- [ ] When a new feature category is added — update registry and verify CI catches it
- [ ] After 3 months — audit whether inline fallback migration targets have been met
- [ ] When `AnalysisContextAssembler` is built (Phase 5) — verify base class contract is sufficient
- [ ] When pydantic-ai v2 is released — verify ContextAssembler still fits the agent lifecycle

---

## Open Questions (Need User Input)

1. **`{{kb_relationships}}` gap priority**: Should we add `{{kb_relationships}}` to all Writing prompts as part of Phase 1, or handle it as a separate task? (Recommendation: include in Phase 1 — it's the immediate gap this ADR addresses.)

2. **Adoption score threshold**: Is 0.85 the right PASS threshold? Should it be higher (0.90) for stricter enforcement, or lower (0.80) for gradual adoption? (Recommendation: start at 0.85, adjust after 1 month of CI data.)

3. **`TokenBudgetManager` move impact**: Moving `budget.py` from `writing/` to `context/` affects all imports. Should we do the move immediately (Phase 3) or defer until `AnalysisContextAssembler` is needed? (Recommendation: Phase 3 — the GLOSSARY already references `core/context/budget.py`, suggesting this was always intended.)

4. **Inline prompt character threshold**: 100 characters is the proposed detection threshold for "prompt-like" strings. Is this appropriate, or should it be higher? (Recommendation: 100 characters — catches all current inline prompts while allowing short error messages.)

5. **Should `writing_graph_prompts.py` fallbacks be registered?** These are developer/test ergonomics (fallback when `composer is None`), not production paths. They arguably don't need registration. (Recommendation: register them — consistency is valuable, and the registration documents the intent.)

---

> **Maintained by:** Architecture Agent
> **Review cycle:** After Phase 2 complete, then every major milestone
