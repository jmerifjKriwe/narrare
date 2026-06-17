# ADR-046 — Prompt-Path-Compliance: Resolution-Path Retrofit & Prevention

> **Status:** ✅ Implemented
> **Date:** 2026-06-13 (Proposed) → 2026-06-17 (Implemented)
> **Deciders:** Architecture Specialist
> **Related:** ADR-026 (Capability-Based Prompt Injection), ADR-002 (Unified Prompt System), ADR-025 (Feature Adoption Infrastructure), ADR-028 (Architecture Exception SSOT), ADR-038 (AI Invocation Adoption Contract), INFRA-012 (Prompt Governance Hardening), CR-02 (Prompt-Architektur Audit)
> **Supersedes:** None (extends ADR-026 enforcement)

---

## Context

ADR-026 (2026-06-01) correctly defines a three-mechanism prompt injection model:
- **Guaranteed content** → `AbstractCapability.get_instructions()`
- **Customizable content** → `PromptComposer` cascade
- **Dynamic data** → `PromptContext` / `@agent.instructions` / Deps

The CR-02 audit (`_audit/results/content-review/coherence/cr-02-system-prompt.md`)
confirmed that the main `NarrareAgent` baseline is ADR-026-conformant: every
exported production agent inherits `NarrareMeta` and `NarrareUniversalRules`, and
most feature prompts resolve through `PromptComposer`. However, **four non-primary
invocation paths bypass the approved resolution mechanisms**:

### Drift Paths (Evidence)

| ID | File | Line(s) | Drift |
|----|------|---------|-------|
| CR-AUFG-02-04 | `apps/api/narrare/chat/chat_service.py` | 167 | `full_prompt = f"{composed.system}\n\n{composed.user}"` — system prompt concatenated into user channel instead of passed as agent system/instructions |
| CR-AUFG-02-05 | `apps/api/narrare/kb/worldbuilding_analyzer.py` | 253–263 | `self._prompt_registry.resolve(category="kb", mode="worldbuilding/phase2")` — direct PromptRegistry access bypassing PromptComposer; inline fallback `"Check entity pairs for worldbuilding contradictions."` |
| CR-AUFG-02-06 | `apps/api/narrare/planning/_prompt_loader.py` | 41–74 | `importlib.resources.files()` + manual `.replace()` for template variables — app-layer prompt loader with cascade-substitution logic outside core/prompts/ |
| CR-AUFG-02-07 | `packages/core/narrare_core/agents/writing_graph_prompts.py` | 39–54, 131–141, 165–168, 282–284, 312–314, 347–349 | `composer is None` branches with inline f-string task prompts + `_get_fallback_meta()` via `MetaPromptLoader` — degraded production fallback paths |

### Root Cause Analysis (C.1–C.5)

The drift did NOT arise from missing documentation or developer indiscipline.
It arose from five systemic gaps:

**C.1 — Temporal Gap:** ADR-026 (2026-06-01) was created AFTER the drifting paths
were implemented. PLAN-004 (Timeline), KB Worldbuilding, and CHAT-001 all predate
ADR-026. The ADR described the correct state but had **no explicit Retrofit-Plan**
for existing code. ADR-026's migration plan covered only the Phases 1–3 capability
migration (meta/universal rules), not feature-prompt path compliance for existing
services.

**C.2 — Adoption Metric Gap:** ADR-025/038 adoption infrastructure tracks
infrastructure-wiring (probes, evidence-sinks) but NOT architectural pattern
conformance (PromptComposer usage vs. direct registry access). 27/27 "static
adoption" passes did not mean 27/27 ADR-026-conformant prompt paths.

**C.3 — Checker Gap:** `check_architecture.py` validates RULE-02 (no f-string/concatenation
for prompt-named variables outside `core/prompts/`) but does NOT detect:
- Direct `PromptRegistry` access outside `core/prompts/`
- App-layer prompt loaders (`_prompt_loader.py` using `importlib.resources` + `.replace()`)
- Feature prompts injected into user-channel instead of system-channel
- Inline fallback prompts < 100 characters (the worldbuilding fallback is 50 chars)
- `MetaPromptLoader` usage outside Capability context

RULE-02 enforcement is focused on the **METHOD** of prompt assembly (f-string,
concatenation), not the **PATH** of prompt resolution (which abstraction layer
resolves the prompt).

**C.4 — Test Convention Gap:** No test convention exists for "Prompt-Path-Compliance
Tests" — tests that verify HOW a prompt was resolved (via PromptComposer), not
just WHAT it says. The existing ADR-026 capability test checks Agent construction
(capability inheritance), not Service-level prompt injection path.
`_prompt_loader.py::load_temporal_consistency_prompt` has **0 tests**.
`chat_service.py::ChatService` has **0 path-compliance tests**.

**C.5 — Cross-Feature Review Gap:** Phase 6 implemented 15+ AI features in
parallel. No prompt-path cross-feature review gate existed. The CR-Audit process
IS this review, but it operates retroactively, not proactively.

---

## Decision Drivers

- **Architectural completeness** — ADR-026's three-mechanism model must be
  uniformly adopted, not just by the primary NarrareAgent path
- **Root-cause prevention** — Fixing 4 paths without prevention infrastructure
  guarantees recurrence (same drift pattern appeared in 4 independent locations)
- **Machine-enforceability** — `check_architecture.py` is the enforcement
  backbone; rules without checker coverage are advisory, not enforced
- **No new abstractions** — The existing PromptComposer/Cascade/Capability
  stack is sufficient. The retrofit requires consistent adoption, not new design
- **ADR-026 backward compatibility** — No change to ADR-026's decision; only
  extending its enforcement surface

---

## Options Considered

### Option A — Global prepend/meta wrapper (REJECTED)

Add a global wrapper that injects meta + universal rules into every final prompt,
regardless of which path produced it.

**Pros:**
- Single fix point
- Catches all paths including future ones

**Cons:**
- Violates ADR-026 by reintroducing monolithic prompt prepending (the exact
  anti-pattern ADR-026 eliminated)
- Does not fix feature-prompt route/cascade adoption — phase2, timeline, and chat
  would still bypass PromptComposer
- Masks the drift instead of fixing it — symptoms suppressed, root causes
  remain
- Creates a parallel infrastructure alongside the Capability system

### Option B — Fix each path individually, no systemic prevention (REJECTED)

Fix the 4 paths using existing ADR-026 mechanisms. Do not add new rules, checkers,
or test conventions.

**Pros:**
- Minimal change footprint
- No new documentation or infrastructure

**Cons:**
- Addresses symptoms but not root causes C.1–C.5
- Same drift pattern WILL recur with the next feature (it appeared in 4
  independent locations already)
- No ADR-Retrofit-Plan convention → future ADRs that change prompt mechanics
  will have the same temporal gap (C.1)
- Checker gap (C.3) remains → the 4 fixes would not be detectable if regressed
- Violates the architectural-discipline mandate: "We build proper solutions.
  Not quick solutions."

### Option C — Fix each path + add prevention infrastructure (CHOSEN)

Fix the 4 paths using existing ADR-026 mechanisms AND add:
1. RULE-02b (Prompt-Resolution-Path Compliance) to CONSTRAINTS.md
2. `check_architecture.py` extension to detect path violations
3. Prompt-Path-Compliance test convention
4. ADR-Retrofit-Plan requirement for future prompt-mechanics ADRs
5. Adoption metric extension (`prompt_path_compliant`)

**Pros:**
- Fixes the root causes, not just symptoms
- Uses existing abstractions (PromptComposer, Capabilities, PromptContext) —
  no new design needed
- Prevention infrastructure catches future drift automatically
- RULE-02b creates a clear, machine-checkable boundary
- ADR-Retrofit-Plan requirement prevents C.1 from recurring
- Sustainable: the prevention infrastructure is independent of the specific
  4 fixes

**Cons:**
- More work upfront (checker extension, test convention, rule addition)
- RULE-02b requires updating CONSTRAINTS.md and all derived sources

**Why C over B:** The AI implements. "More work" is not an argument — the AI
works at the same speed for both. The difference is: Option C produces
sustainable prevention; Option B produces a one-time fix that will be
re-violated. Per the architectural-discipline standard, "We build proper
solutions. Not quick solutions."

---

## Decision

**We choose Option C — Fix paths + Prevention Infrastructure.**

This decision has three components:

### Component 1: RULE-02b — Prompt-Resolution-Path Compliance

Add RULE-02b to `docs/_shared/CONSTRAINTS.md` as a sub-rule of RULE-02
(following the RULE-02a pattern of sub-rules for distinct aspects):

> **RULE-02b · Prompt-Resolution is exclusively the responsibility of
> `core/prompts/`. No app-layer module may load, resolve, substitute, or
> construct prompts directly.**

**Why a new sub-rule (RULE-02b) rather than extending RULE-02 enforcement:**

RULE-02's text already says "Prompts are built in `core/prompts/`. Nowhere else."
However, the existing checker implementation (`prompts.py`) validates the
**METHOD** of prompt assembly (no f-strings for prompt-named variables). The
drift we are fixing is about the **PATH** — which abstraction layer resolves
the prompt. These are distinct concerns:

| Aspect | Rule | What it prevents |
|--------|------|-----------------|
| Assembly METHOD | RULE-02 | f-string/concatenation prompt assembly outside core/prompts/ |
| Content CATEGORY | RULE-02a | Using the wrong injection mechanism for a content type |
| Resolution PATH | **RULE-02b (NEW)** | Direct registry access, app-layer loaders, user-channel injection, inline fallbacks |

RULE-02b makes the path-compliance requirement explicit and machine-checkable.
Without it, the checker extension has no normative basis — it would be detecting
"violations" of an unstated rule.

**What constitutes a Prompt-Path violation (RULE-02b):**

1. **Direct PromptRegistry access outside `core/prompts/`** — any module in
   `apps/`, `packages/core/narrare_core/agents/`, or `packages/core/narrare_core/*/`
   that imports and calls `PromptRegistry.resolve()` directly, instead of going
   through `PromptComposer.build()`

2. **App-layer prompt loaders** — any file in `apps/` that loads a prompt template
   from disk (`importlib.resources`, `Path.read_text()`, etc.) and performs
   template variable substitution (`.replace()`, `.format()`, f-string
   interpolation with `{{variable}}` syntax)

3. **Feature prompts injected into user-channel** — any service that resolves a
   feature system prompt via PromptComposer but then concatenates
   `composed.system` into the user prompt instead of passing it as agent
   system/instructions

4. **Inline fallback prompts in production code** — any production path that
   uses a hardcoded prompt string as a degraded fallback when PromptComposer
   fails or is unavailable. Production code must fail-fast on configuration
   errors, not degrade to an inline prompt.

5. **`MetaPromptLoader` usage outside `core/prompts/` and `core/agents/capabilities/`**
   — the `MetaPromptLoader` is a `core/prompts/` internal that must not be
   imported by agents, services, or graph helpers.

**Enforcement boundary:** `core/prompts/` is the ONLY module that may:
- Import `PromptRegistry`
- Load prompt template files from `_bundled/`
- Perform `{{variable}}` substitution via the variable engine
- Cascade-resolve prompts

**Approved exceptions:** Listed in `pyproject.toml [tool.narrare.architecture]`
with inline `# narrare: allow-prompt-path reason="..."` comments, per ADR-028.

### Component 2: Retrofit Plan (MANDATORY)

> This section addresses root cause C.1 (Temporal Gap). ADR-026 lacked a
> Retrofit-Plan for existing code. ADR-046 provides one.

See **§ Retrofit Plan** below for the full migration specification of all 4
drift paths.

### Component 3: Prevention Infrastructure

See **§ Prevention Infrastructure** below for D.1–D.5.

---

## Retrofit Plan

> The Retrofit Plan is the missing element from ADR-026. It explicitly lists all
> known non-conformant paths and their migration path. Implementation specialists
> use this as their task specification.

### Retrofit Task: CR-AUFG-02-04 — Chat Prompt Injection

**Affected files:**
- `apps/api/narrare/chat/chat_service.py` (line 167: `full_prompt = f"{composed.system}\n\n{composed.user}"`)
- `packages/core/narrare_core/chat/chat_agent.py` (accepts system_prompt)
- `packages/core/narrare_core/chat/chat_deps.py` (ChatDeps)

**Root cause:** `ChatService` correctly calls `PromptComposer.build(LLMIntent.CHAT, ...)`
but then concatenates `composed.system` + `composed.user` into a single string
passed as `prompt=` to `agent.run_stream()`. The system content lands in the user
channel, meaning the LLM sees feature instructions as user text, not as system
instructions.

**Migration target:** Pass `composed.system` as agent system/instructions (via
`@agent.instructions` or agent constructor `system_prompt` parameter), and pass
only `composed.user` (or the raw user message) as the user prompt.

**Acceptance Criteria:**

- [ ] `LLMIntent.CHAT` still resolves through PromptComposer/Cascade
- [ ] `chat/en/system.md` is injected as system/instructions, NOT concatenated
      into user input
- [ ] NarrareMeta and NarrareUniversalRules remain capabilities (unchanged)
- [ ] Regression test asserts user prompt does not contain the system template body
- [ ] **NEW AC:** Prompt-Path-Compliance test verifies `ChatService` calls
      `PromptComposer.build(LLMIntent.CHAT, ...)` and passes `result.system` as
      agent instructions (not as part of user prompt)
- [ ] **NEW AC:** Uses standardized XML template tags per CR-01
- [ ] **NEW AC:** `ChatService` has >0 prompt-path-compliance tests (currently 0)

**Implementation note:** The `ChatAgent` (extends `NarrareAgent`) already inherits
`NarrareMeta` + `NarrareUniversalRules` capabilities. The feature system prompt
(`chat/en/system.md`) should be injected via `@agent.instructions` or via a
`ChatFeatureInstructions` capability that reads `composed.system` from `ChatDeps`.
The user message (`request.message`) and conversation history go as user-channel
data only.

### Retrofit Task: CR-AUFG-02-05 — Worldbuilding Phase2

**Affected files:**
- `apps/api/narrare/kb/worldbuilding_analyzer.py` (lines 253–263)
- `packages/core/narrare_core/prompts/route_table.py` (already supports `worldbuilding/phase2`)

**Root cause:** `WorldbuildingAnalyzer._run_phase2` calls
`self._prompt_registry.resolve(category="kb", mode="worldbuilding/phase2")`
directly instead of going through `PromptComposer.build()`. The route table
already declares `LLMIntent.KB_WORLDBUILD` with
`allowed_context_modes=frozenset({"worldbuilding/phase1", "worldbuilding/phase2"})`
(line 128), so PromptComposer CAN handle phase2. The direct registry access
bypasses cascade resolution, variable substitution via PromptContext, and user
overrides. The inline fallback `"Check entity pairs for worldbuilding
contradictions."` (50 chars) is too short for the inline_prompts checker (>100
threshold) and masks configuration failures.

**Migration target:** Call `PromptComposer.build(LLMIntent.KB_WORLDBUILD, context)`
with `context.mode = "worldbuilding/phase2"`. Pass candidate pairs, entity
details, relationships, and world context through `PromptContext.extra`.
Missing prompt route must fail-fast as a configuration error, not degrade to
an inline fallback.

**Acceptance Criteria:**

- [ ] Phase2 uses `PromptComposer.build(LLMIntent.KB_WORLDBUILD, context)` with
      `context.mode = "worldbuilding/phase2"`
- [ ] Template variables are substituted via governed variable engine (PromptContext)
- [ ] No production inline fallback system prompt remains
- [ ] Tests cover phase2 composed prompt resolution
- [ ] **NEW AC:** `PromptRegistry` is NOT imported outside `core/prompts/` in the
      worldbuilding path (checker-verified)
- [ ] **NEW AC:** Uses standardized XML template tags per CR-01
- [ ] **NEW AC:** Missing prompt route raises a typed configuration error, not
      a bare `except Exception` fallback

**Implementation note:** Phase1 (`_run_phase1`, line 183) already uses
`self._composer.build(LLMIntent.KB_WORLDBUILD, ctx)` — phase2 should mirror
this pattern. The `WorldbuildingDeps` already carries `entity_details` and
`candidate_pairs`; these become `PromptContext.extra` variables.

### Retrofit Task: CR-AUFG-02-06 — Temporal Consistency

**Affected files:**
- `apps/api/narrare/planning/_prompt_loader.py` (entire file — to be REMOVED)
- `apps/api/narrare/planning/timeline_consistency_service.py` (lines 248–253: calls `_prompt_loader`)
- `packages/core/narrare_core/prompts/_bundled/planning/en/temporal_consistency/system.md` (exists)

**Root cause:** `load_temporal_consistency_prompt()` uses `importlib.resources.files()`
to load a bundled prompt template directly, then performs manual `.replace()` calls
for template variables (`{{project_title}}`, `{{genre}}`, `{{language}}`, etc.).
This reimplements cascade resolution and variable substitution in the app layer.
The function has **0 tests**. The `_prompt_loader.py` file exists in `apps/api/`
which is the wrong layer for prompt resolution (RULE-07 violation: app layer
should delegate to core, not implement core logic).

**Migration target:** Add a route entry for temporal consistency (either under
`LLMIntent.PLAN` with a `temporal_consistency` context mode, or a dedicated
intent if architecture approves). Pass event context as user/runtime data
through `PromptContext.extra` or `TimelineDeps`, not baked into system prompt
construction. Remove `_prompt_loader.py` entirely.

**Acceptance Criteria:**

- [ ] User-customizable temporal consistency instructions resolve through
      PromptComposer
- [ ] Dynamic event context is NOT baked into system prompt construction (goes
      through `PromptContext.extra` or agent deps as user-channel data)
- [ ] Capabilities continue to supply guaranteed persona/rules
- [ ] Architecture checker no longer needs an app-layer prompt-loader exception
- [ ] **NEW AC:** `_prompt_loader.py` is REMOVED from `apps/api/` — no app-layer
      prompt loader exists
- [ ] **NEW AC:** Uses standardized XML template tags per CR-01
- [ ] **NEW AC:** The temporal consistency prompt path has >0 tests (currently 0)

**Implementation note:** The `timeline_consistency_service.py::_run_llm_checks`
method already builds `event_context` as a user prompt (line 238–241). This is
correct — event context is dynamic data and belongs in the user channel. The
fix is to replace the `load_temporal_consistency_prompt()` call with
`PromptComposer.build()` for the system prompt, keeping the event context as
the user prompt. The temporal consistency prompt template already exists at
`_bundled/planning/en/temporal_consistency/system.md`; it needs a route entry.

### Retrofit Task: CR-AUFG-02-07 — Writing Graph Fallbacks

**Affected files:**
- `packages/core/narrare_core/agents/writing_graph_prompts.py` (lines 39–54, 131–141, 165–168, 282–284, 312–314, 347–349)
- `packages/core/narrare_core/prompts/meta.py` (`MetaPromptLoader` — to be evaluated for removal)

**Root cause:** `writing_graph_prompts.py` has 5 functions
(`get_outline_prompt`, `get_draft_prompt`, `get_review_prompt`,
`get_revise_prompt`, `get_summary_prompt`) that each contain
`if composer is None:` branches with inline f-string task prompts. When
`composer is None`, they call `_get_fallback_meta()` which uses
`MetaPromptLoader` to load the meta-prompt — bypassing the NarrareMeta
Capability. These are degraded production paths: if DI fails to wire
PromptComposer, the graph silently runs with inline prompts and no
Capability-injected identity/rules.

**Migration target:** The `composer is None` branches must be replaced with
fail-fast configuration errors in production. If the writing graph needs a
bare-bones test mode (e.g., for graph-level integration tests that use
TestModel), that mode must be explicitly test-scoped and documented — not a
silent production fallback.

**MetaPromptLoader decision:** REMOVE from production paths.
`MetaPromptLoader` (`core/prompts/meta.py`) was the pre-ADR-026 mechanism for
loading meta-prompt content. ADR-026 Phase 3 replaced it with the
`NarrareMeta` Capability (commit `45b7395`). The `MetaPromptLoader` is now
only used by `_get_fallback_meta()` in `writing_graph_prompts.py`, which is
itself a `composer is None` fallback. Once the fallback paths are removed,
`MetaPromptLoader` has no remaining callers and should be removed (or, if any
remaining test references exist, marked `@deprecated` with a removal date).

**Acceptance Criteria:**

- [ ] `composer is None` paths are replaced with fail-fast `ConfigurationError`
      in production code
- [ ] No overridable meta/user task prompts loaded as degraded production path
- [ ] **NEW AC:** `MetaPromptLoader` is either removed entirely or marked
      `@deprecated` with a removal date and removed from all production paths
- [ ] **NEW AC:** Any remaining test-only fallback is covered by a test that
      documents it as intentionally non-production (assert it cannot be reached
      by production DI wiring)
- [ ] **NEW AC:** `writing_graph_prompts.py` does not import `MetaPromptLoader`
      (checker-verified after MetaPromptLoader removal)
- [ ] **NEW AC:** `_get_fallback_meta()` is removed (no remaining callers)

**Implementation note:** The writing graph receives `WritingDeps` which contains
a `composer: PromptComposer | None` field. The fix is to make `composer` required
(non-None) in production `WritingDeps`. Test-only configurations that genuinely
need bare agents should use `TestModel` with explicit capability-free agent
construction, documented as test-only.

---

## Prevention Infrastructure

> Addresses root causes C.2–C.5. Without prevention, the same drift pattern will
> recur with the next feature. It already appeared in 4 independent locations.

### D.1 — Prompt-Path-Compliance Test Convention

**What:** A test category that verifies HOW a prompt was resolved, not just
WHAT it says. Existing tests check prompt content (does the template have the
right variables?). Prompt-Path-Compliance tests check the resolution path
(does the service call PromptComposer, not PromptRegistry directly?).

**Where:** `tests/unit/core/prompts/test_prompt_path_compliance.py` (shared
convention test) + per-service path-compliance assertions in existing service
test files.

**What they assert:**

1. **Service-level path assertion:** The service calls `PromptComposer.build()`,
   not `PromptRegistry.resolve()` directly. Verified by mocking PromptComposer
   and asserting `.build()` was called, or by inspecting the prompt resolution
   chain.

2. **Channel assertion:** For services that pass both system and user prompts
   to an agent, the system prompt is passed as agent system/instructions, NOT
   concatenated into the user prompt. Verified by asserting the agent's
   `system_prompt` parameter or `@agent.instructions` output contains the
   feature template body, while the user prompt does not.

3. **No-fallback assertion:** Production service methods do not contain inline
   fallback prompt strings. Verified by asserting that when PromptComposer
   raises, the service raises (not falls back to an inline string).

**Convention:**

```python
# tests/unit/api/chat/test_chat_prompt_path_compliance.py

async def test_chat_service_resolves_via_prompt_composer(
    chat_service: ChatService,
    mock_composer: MockPromptComposer,
) -> None:
    """Prompt-Path-Compliance: ChatService must use PromptComposer.build()."""
    mock_composer.reset()
    await collect(chat_service.ask(sample_request, user_id=TEST_USER_ID))

    assert mock_composer.build_called
    assert mock_composer.last_intent == LLMIntent.CHAT


async def test_chat_system_prompt_not_in_user_channel(
    chat_service: ChatService,
) -> None:
    """Prompt-Path-Compliance: system content must not appear in user prompt."""
    # Inspect the agent call to verify system prompt is separate from user prompt
    agent_call = chat_service._last_agent_call
    assert "project-aware writing chat mode" not in agent_call.user_prompt
    assert agent_call.system_prompt is not None
```

**Coverage requirement:** Every production service that resolves prompts
(chat, worldbuilding, timeline, writing graph, generation, analysis) must have
at least one Prompt-Path-Compliance test.

### D.2 — check_architecture.py Extension

**What:** Three new checker modules to detect RULE-02b violations at CI time.

**Module 1: `scripts/architecture/_checkers/prompt_path.py`**

Detects direct `PromptRegistry` access outside `core/prompts/`:

```python
# AST scan: find `import PromptRegistry` or `PromptRegistry.resolve()` calls
# in files NOT under packages/core/narrare_core/prompts/
# Exception: core/agents/capabilities/ may use registry loaders that go
# through core/prompts/ internally
```

Checks:
- `from narrare_core.prompts.registry import PromptRegistry` in any file outside
  `packages/core/narrare_core/prompts/`
- `PromptRegistry.resolve(` calls in any file outside `packages/core/narrare_core/prompts/`
- `prompt_registry.resolve(` attribute access in any file outside
  `packages/core/narrare_core/prompts/`

**Module 2: Extension to `scripts/architecture/_checkers/prompts.py`**

Detects app-layer prompt loaders:

```python
# Pattern: files matching *_prompt_loader.py or _prompt_*.py in apps/
# that import importlib.resources or pathlib.Path and read .md files
# from _bundled/ directories
```

Checks:
- Any file in `apps/` that imports `importlib.resources` AND references
  `_bundled` in a string literal
- Any file in `apps/` that calls `.replace("{{` (manual template variable
  substitution)
- Any file in `apps/` that reads a `.md` file from `prompts/_bundled/` path

**Module 3: `scripts/architecture/_checkers/prompt_channel.py`**

Detects feature-prompt-in-user-channel injection:

```python
# Pattern: string concatenation of composed.system + composed.user
# AST scan: find `f"...{composed.system}...{composed.user}..."` or
# `composed.system + composed.user` or similar patterns
# in files outside core/prompts/ and test directories
```

Checks:
- Any assignment or function call that concatenates `.system` and `.user`
  attributes of a `ComposedPrompt` (or variable typed as `ComposedPrompt`)
- Any `agent.run(prompt=f"{...system...}")` where the prompt parameter
  receives system-channel content

**Baseline handling:** Pre-existing violations (the 4 drift paths) are tracked
as ratcheted baseline debt. After retrofit, the baseline drops to 0. New
violations are CI failures.

### D.3 — Post-Implementation Prompt-Path Review Gate

**What:** A dedicated `check_prompt_path_compliance.py` script is NOT needed.
The D.2 checker modules (`prompt_path.py`, extended `prompts.py`,
`prompt_channel.py`) run as part of the existing `check_architecture.py`
pre-commit + CI pipeline. No new script, no new gate.

**Rationale:** The existing `check_architecture.py` already has a modular
checker architecture (`scripts/architecture/_checkers/`). Adding new checkers
to this pipeline is the correct extension point. A separate script would
fragment enforcement and create a "which checker do I run?" problem.

**Exception:** If the AST-based checks prove insufficient (e.g., dynamic prompt
construction that evades static analysis), a targeted runtime probe may be
needed. This is evaluated post-implementation.

### D.4 — ADR-Retrofit-Plan Requirement

**What:** A process requirement that any future ADR which changes prompt
mechanics MUST include a Retrofit-Plan section.

**Scope:** Applies to any ADR that:
- Adds, modifies, or removes a prompt injection mechanism
- Changes how PromptComposer resolves prompts
- Introduces a new `LLMIntent` or route
- Modifies the Capability system
- Changes template variable substitution

**Retrofit-Plan section must contain:**
1. **Inventory of affected paths:** List of all existing code paths that use
   the mechanism being changed
2. **Migration steps per path:** What changes in each file, in what order
3. **Breaking-change assessment:** Which paths break during migration, how
   backward compatibility is maintained
4. **Checker update plan:** How `check_architecture.py` is updated to enforce
   the new mechanism
5. **Test update plan:** How existing tests are updated to verify the new path

**Enforcement:** Architecture Specialist verifies the Retrofit-Plan exists
during ADR review (Stage 5 — Validate). An ADR without a Retrofit-Plan for
prompt mechanics changes is rejected.

**This addresses root cause C.1 directly:** The temporal gap occurred because
ADR-026 described the correct state without listing what needed to change.
Future ADRs will not repeat this mistake.

### D.5 — Adoption Metric Extension

**What:** Add `prompt_path_compliant: bool` to the ADR-038 AI Invocation
Adoption Contract evidence schema.

**Current state (ADR-038):** The adoption contract tracks:
- `static_adoption`: Infrastructure-wiring (probes, evidence-sinks)
- `runtime_adoption`: Runtime evidence that preferences, context, and output
  language reached the invocation path
- `intent_mode_output_budget`: Token budget evidence

**Extension:** Add `prompt_path_compliant` as a per-intent adoption criterion:

```yaml
# In adoption-registry.yaml per-intent entry:
LLMIntent.CHAT:
  static_adoption: true
  runtime_adoption: true
  prompt_path_compliant: true  # NEW — verified by D.1 tests + D.2 checker
```

**Verification:** `prompt_path_compliant: true` requires:
1. At least one Prompt-Path-Compliance test exists for the service that handles
   this intent (D.1)
2. `check_architecture.py` reports 0 RULE-02b violations for files in the
   service's module (D.2)

**This addresses root cause C.2 directly:** 27/27 "static adoption" passes did
not mean 27/27 ADR-026-conformant prompt paths. The new metric makes path
comformance a first-class adoption criterion.

---

## Consequences

**Positive:**
- RULE-02b creates a clear, machine-checkable boundary for prompt resolution
- The 4 drift paths are fixed using existing abstractions (no new design)
- Prevention infrastructure (checker + tests + metric + ADR-Retrofit-Plan
  requirement) catches future drift automatically
- `MetaPromptLoader` removal eliminates dead pre-ADR-026 infrastructure
- `_prompt_loader.py` removal eliminates app-layer prompt resolution logic
- The adoption metric extension makes path-comformance auditable per-intent

**Negative / Trade-offs:**
- RULE-02b adds a new constraint to CONSTRAINTS.md — all derived sources must
  be updated
- The checker extension (D.2) uses AST-based static analysis which has false
  positive/negative risk — needs tuning with baseline
- `composer is None` removal in writing_graph_prompts.py may require updating
  test fixtures that pass `None` as composer
- MetaPromptLoader removal requires verifying no hidden callers remain
- Adoption metric extension requires updating adoption-registry.yaml for all
  existing intents

**Constraints introduced / updated:**
- RULE-02b added to CONSTRAINTS.md
- `check_architecture.py` gains 3 new checker modules
- ADR-038 adoption contract gains `prompt_path_compliant` field
- ADR-026 gains a retroactive Retrofit-Plan cross-reference to this ADR

---

## RULE-XX Compliance Matrix

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-02 | ✅ | All 4 retrofit paths move prompt assembly to core/prompts/ via PromptComposer |
| RULE-02a | ✅ | Content categories respected: customizable → PromptComposer, guaranteed → Capabilities, dynamic → PromptContext/deps |
| **RULE-02b** | ✅ **NEW** | Prompt-Resolution exclusively in core/prompts/. No app-layer loaders, no direct registry access, no user-channel injection |
| RULE-03 | ✅ | Contracts checked before implementation (ChatService, WorldbuildingAnalyzer, TimelineConsistencyService contracts exist) |
| RULE-04 | ✅ | `_prompt_loader.py` removal reduces file count; no file exceeds limits |
| RULE-05 | ✅ | Module boundaries: prompt resolution is core/prompts/ ownership, not app-layer |
| RULE-06 | ✅ | `_prompt_loader.py` removal eliminates mixed responsibility in planning module |
| RULE-07 | ✅ | Dependency direction: apps/ delegates to core/prompts/, not vice versa |
| RULE-09 | ✅ | All new checker code fully type-annotated |
| RULE-10 | ✅ | Prompt-Path-Compliance tests (D.1) add test coverage; current 0-test paths get tests |
| RULE-11 | ✅ | Inline fallbacks replaced with fail-fast errors (no silent degradation) |
| RULE-20 | ✅ | No half-implementations: all 4 paths fully retrofitted, prevention infrastructure fully built |
| RULE-22 | ✅ | Cross-feature coherence: prompt-path compliance is consistent across chat, KB, planning, writing |

---

## Compliance Checklist

- [ ] RULE-02b text added to CONSTRAINTS.md §1 (Cardinal Rules)
- [ ] CONSTRAINTS.md §6 (Enforcement Summary) updated with RULE-02b row
- [ ] `check_architecture.py` extended with `prompt_path.py` checker module
- [ ] `prompts.py` checker extended with app-layer-loader detection
- [ ] `prompt_channel.py` checker module added for user-channel detection
- [ ] Adoption registry (`adoption-registry.yaml`) updated with
      `prompt_path_compliant` field per intent
- [ ] ADR-Retrofit-Plan requirement documented in ADR process
      (`.opencode/context/narrare-dev/processes/adr-process.md`)
- [ ] All 4 retrofit tasks (CR-AUFG-02-04 through 02-07) implemented and tested
- [ ] MetaPromptLoader removed or deprecated with removal date
- [ ] `_prompt_loader.py` removed from apps/api/
- [ ] INDEX.md updated with ADR-046 entry
- [ ] ADR-026 cross-references ADR-046 for the Retrofit-Plan

---

## Review Trigger

- [ ] After CR-AUFG-02-04 implementation: Verify ChatService passes system
      prompt as agent instructions, not user-channel concatenation
- [ ] After CR-AUFG-02-05 implementation: Verify worldbuilding phase2 uses
      PromptComposer.build(), no direct registry access
- [ ] After CR-AUFG-02-06 implementation: Verify _prompt_loader.py is removed,
      timeline uses PromptComposer
- [ ] After CR-AUFG-02-07 implementation: Verify composer-None paths are
      fail-fast, MetaPromptLoader removed from production
- [ ] After D.2 checker implementation: Run checker on full codebase, verify
      0 false positives (baseline = the 4 known drift paths, which are now fixed)
- [ ] When adding a new prompt-resolving service: Verify it has a
      Prompt-Path-Compliance test (D.1)
- [ ] When creating an ADR that changes prompt mechanics: Verify it has a
      Retrofit-Plan section (D.4)
- [ ] pydantic-ai v2: Verify PromptComposer.build() and Capability
      get_instructions() contracts unchanged
