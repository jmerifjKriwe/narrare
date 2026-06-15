# CR-02 Remediation — Prompt-Path-Compliance Retrofit Task Specs

> **Status:** draft — awaiting coordinator review
> **Date:** 2026-06-13
> **Author:** Architecture Specialist
> **Related ADR:** [ADR-046](../../architecture/decisions/ADR-046-prompt-path-compliance.md)
> **Source Audit:** [CR-02 System-Prompt](../../../_audit/results/content-review/coherence/cr-02-system-prompt.md)

---

## Overview

This document contains the implementation-ready task specifications for the 4
prompt-path drift issues identified in the CR-02 audit. Each spec defines the
exact migration path, acceptance criteria, and test requirements for the
Backend/Core implementation specialists.

**Implementation order** (based on dependency analysis):
1. CR-AUFG-02-07 (Writing Graph Fallbacks) — removes MetaPromptLoader, unblocks clean state
2. CR-AUFG-02-06 (Temporal Consistency) — removes _prompt_loader.py, simplest blast radius
3. CR-AUFG-02-05 (Worldbuilding Phase2) — phase1 already conformant, phase2 mirrors it
4. CR-AUFG-02-04 (Chat Prompt Injection) — most user-facing, needs careful testing

---

## CR-AUFG-02-04 — Chat Prompt Injection

### Scope

**In scope:** Fix `ChatService` to pass `composed.system` as agent system/instructions
instead of concatenating it into the user prompt.

**Out of scope:** Changes to `ChatAgent` capabilities (NarrareMeta, NarrareUniversalRules
are already correct). Changes to chat template content (CR-01 handles template tags).

### Root Cause

`ChatService._stream_agent_response()` (line 167) builds a single prompt string:

```python
full_prompt = f"{composed.system}\n\n{composed.user}" if composed.system else composed.user
```

This concatenates the feature system prompt (`chat/en/system.md`, resolved by
PromptComposer) with the user message. The LLM receives feature instructions as
user-channel text, not as system instructions. This means:
1. The feature prompt has lower instruction priority (user channel vs. system channel)
2. The LLM may treat feature instructions as user content to respond to, rather
   than as behavioral constraints
3. Prompt injection defense (from NarrareUniversalRules) protects system-channel
   content more reliably than user-channel content

### Current State (Code Evidence)

```
ChatService.ask()
  → PromptComposer.build(LLMIntent.CHAT, context)  ← CORRECT: uses PromptComposer
  → ChatService._stream_agent_response(composed, ...)
    → full_prompt = f"{composed.system}\n\n{composed.user}"  ← DRIFT: concatenation
    → agent.run_stream(prompt=full_prompt, ...)  ← system content in user channel
```

### Migration Target

```
ChatService.ask()
  → PromptComposer.build(LLMIntent.CHAT, context)  ← UNCHANGED
  → ChatService._stream_agent_response(composed, ...)
    → agent.run_stream(
        prompt=composed.user,           ← user message only
        system_prompt=composed.system,  ← system prompt as instructions
        deps=deps,
      )
```

The `ChatAgent` must accept a `system_prompt` parameter (or use
`@agent.instructions` to inject the feature prompt from `ChatDeps`). The
NarrareMeta and NarrareUniversalRules capabilities continue to provide the
guaranteed identity/rules layer.

### Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `LLMIntent.CHAT` still resolves through PromptComposer/Cascade | Unit test: mock PromptComposer, assert `.build()` called with `LLMIntent.CHAT` |
| 2 | `chat/en/system.md` content is passed as agent system/instructions | Unit test: inspect agent call, verify `system_prompt` parameter contains template body |
| 3 | User prompt does NOT contain the system template body | Unit test: inspect agent call, verify `prompt` parameter does not contain `"project-aware writing chat mode"` or similar template markers |
| 4 | NarrareMeta and NarrareUniversalRules remain capabilities | Existing test: `test_all_production_agent_classes_inherit_adr026_capabilities` (ChatAgent is covered) |
| 5 | **NEW:** Prompt-Path-Compliance test exists for ChatService | Test file: `tests/unit/api/chat/test_chat_prompt_path_compliance.py` with ≥2 assertions |
| 6 | **NEW:** No f-string concatenation of `composed.system + composed.user` | Checker: `prompt_channel.py` reports 0 violations for chat_service.py |
| 7 | **NEW:** Uses standardized XML template tags per CR-01 | If chat template is modified, variables are wrapped in XML tags |
| 8 | **NEW:** ChatService has >0 prompt-path-compliance tests | Currently 0 tests for chat_service.py path compliance |

### Files to Modify

| File | Change |
|------|--------|
| `apps/api/narrare/chat/chat_service.py` | Remove line 167 concatenation; pass `composed.system` and `composed.user` separately |
| `packages/core/narrare_core/chat/chat_agent.py` | Ensure agent accepts `system_prompt` from composed prompt (via constructor or @agent.instructions reading ChatDeps) |
| `packages/core/narrare_core/chat/chat_deps.py` | Ensure ChatDeps carries the composed system prompt if needed |
| `tests/unit/api/chat/test_chat_prompt_path_compliance.py` | **NEW** — Prompt-Path-Compliance tests |

### Impact Radius

- **Callers of ChatService.ask():** Chat router (`apps/api/narrare/chat/router.py`) — no change needed, streaming interface unchanged
- **ChatAgent.run_stream():** Interface may gain `system_prompt` parameter — check all callers
- **ProcessHistory:** Unaffected — history is user-channel conversation data

---

## CR-AUFG-02-05 — Worldbuilding Phase2

### Scope

**In scope:** Replace direct `PromptRegistry.resolve()` call in phase2 with
`PromptComposer.build()`. Remove inline fallback.

**Out of scope:** Phase1 (already conformant). WorldbuildingAgent construction.

### Root Cause

`WorldbuildingAnalyzer._run_phase2()` (lines 253–263) calls:

```python
resolved = await self._prompt_registry.resolve(
    category="kb",
    language="en",
    mode="worldbuilding/phase2",
)
system_prompt = resolved.system_prompt
```

This bypasses PromptComposer's cascade resolution (user overrides ignored),
variable substitution (template variables not substituted), and prompt-context
assembly. The route table already supports this:

```python
# route_table.py line 124-129
LLMIntent.KB_WORLDBUILD: PromptRouteConfig(
    "kb",
    "worldbuilding/phase1",
    allowed_context_modes=frozenset({"worldbuilding/phase1", "worldbuilding/phase2"}),
)
```

Phase1 (`_run_phase1`, line 183) already does it correctly:
```python
composed = await self._composer.build(LLMIntent.KB_WORLDBUILD, ctx)
```

### Current State (Code Evidence)

```
WorldbuildingAnalyzer.analyze()
  → _run_phase1()
    → self._composer.build(LLMIntent.KB_WORLDBUILD, ctx)  ← CORRECT
  → _run_phase2()
    → self._prompt_registry.resolve("kb", "worldbuilding/phase2")  ← DRIFT: direct registry
    → except Exception: system_prompt = "Check entity pairs..."    ← DRIFT: inline fallback
```

### Migration Target

```
WorldbuildingAnalyzer.analyze()
  → _run_phase1()
    → self._composer.build(LLMIntent.KB_WORLDBUILD, ctx)  ← UNCHANGED
  → _run_phase2()
    → ctx.mode = "worldbuilding/phase2"
    → ctx.extra["entity_details"] = ...
    → ctx.extra["candidate_pairs"] = ...
    → composed = self._composer.build(LLMIntent.KB_WORLDBUILD, ctx)  ← FIXED
    → agent.run_phase2(prompt=composed.user, system_prompt=composed.system, ...)
```

### Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Phase2 uses `PromptComposer.build(LLMIntent.KB_WORLDBUILD, context)` with `context.mode = "worldbuilding/phase2"` | Unit test: mock PromptComposer, assert build called with correct intent + mode |
| 2 | Template variables substituted via governed variable engine (PromptContext) | Unit test: verify PromptContext.extra carries entity_details, candidate_pairs |
| 3 | No production inline fallback system prompt remains | Code review + checker: no string literal matching prompt patterns in phase2 path |
| 4 | Tests cover phase2 composed prompt resolution | Unit test: composed prompt is non-empty, contains expected template structure |
| 5 | **NEW:** `PromptRegistry` is NOT imported in `worldbuilding_analyzer.py` | Checker: `prompt_path.py` reports 0 violations for this file |
| 6 | **NEW:** Missing prompt route raises typed configuration error, not bare `except Exception` | Unit test: when composer raises, service raises typed error |
| 7 | **NEW:** Uses standardized XML template tags per CR-01 | If phase2 template is modified, user-content variables are wrapped |
| 8 | **NEW:** Phase2 path has Prompt-Path-Compliance test | Test asserts `.build()` is called, not `.resolve()` |

### Files to Modify

| File | Change |
|------|--------|
| `apps/api/narrare/kb/worldbuilding_analyzer.py` | Replace `_prompt_registry.resolve()` with `_composer.build()`; remove inline fallback; add fail-fast error |
| `apps/api/narrare/kb/worldbuilding_analyzer.py` (constructor) | Remove `_prompt_registry` injection if no longer needed |
| `tests/unit/api/kb/test_worldbuilding_prompt_path_compliance.py` | **NEW** — Prompt-Path-Compliance tests |

### Impact Radius

- **Callers of _run_phase2:** `WorldbuildingAnalyzer.analyze()` (internal) and `KBConsistencyService._run_cross_entity()` (external) — interface unchanged (returns `list[ConsistencyIssue]`)
- **WorldbuildingAgent.run_phase2():** Already accepts `system_prompt` parameter — no change needed
- **PromptRegistry import:** Check if any other code in worldbuilding_analyzer.py uses it (only phase2)

---

## CR-AUFG-02-06 — Temporal Consistency

### Scope

**In scope:** Remove `_prompt_loader.py`. Replace with PromptComposer route for
temporal consistency. Pass event context as user-channel data.

**Out of scope:** TimelineAgent construction (already uses NarrareAgent).
Timeline deterministic checks (not prompt-related).

### Root Cause

`_prompt_loader.py::load_temporal_consistency_prompt()` reimplements cascade
resolution and variable substitution in the app layer:

1. Uses `importlib.resources.files()` to load `_bundled/planning/en/temporal_consistency/system.md`
2. Performs manual `.replace("{{project_title}}", novel_title)` for each variable
3. Does NOT support user overrides (no cascade)
4. Does NOT use the governed variable engine (bypasses validation)
5. Returns empty string on failure (silent failure — RULE-11 violation)

The file exists in `apps/api/narrare/planning/` which is the wrong layer for
prompt resolution per RULE-07 (app layer delegates to core, not implements
core logic). It was "extracted to keep service files under 300-line limit"
(docstring line 3-4) — but the fix for file size is modularization, not
extracting core logic into the app layer.

### Current State (Code Evidence)

```
TimelineConsistencyService._run_llm_checks()
  → load_temporal_consistency_prompt(language, novel_title, genre, language_code)  ← DRIFT: app-layer loader
    → importlib.resources.files("narrare_core.prompts._bundled.planning")          ← DRIFT: direct file access
    → text.replace("{{project_title}}", novel_title)                               ← DRIFT: manual substitution
    → text.replace("{{genre}}", genre)                                              ← DRIFT: manual substitution
    → text.replace("{{event_context}}", "")                                         ← DRIFT: blank substitution
  → agent.run(prompt=event_context, system_prompt=system_prompt_text, deps=deps)
```

### Migration Target

Two sub-decisions:

**Decision A: Route entry.** Add temporal_consistency as a context mode under
`LLMIntent.PLAN` (since it is a planning concern and PLAN already routes to
`planning/outline`). Alternatively, if the architecture specialist determines
temporal consistency warrants its own intent, add `LLMIntent.TEMPORAL_CHECK`
to `intents.py`.

**Recommendation:** Use context mode under existing `LLMIntent.PLAN`:
```python
# route_table.py
LLMIntent.PLAN: PromptRouteConfig(
    "planning",
    "outline",
    allowed_context_modes=frozenset({"outline", "temporal_consistency"}),  # ADD
)
```

**Decision B: Event context routing.** Event context is dynamic data — it goes
in the user prompt (as it currently does at line 238–241) or in
`PromptContext.extra`. The system prompt comes from PromptComposer.

```
TimelineConsistencyService._run_llm_checks()
  → ctx = PromptContext(language=language, mode="temporal_consistency", ...)
  → ctx.extra["novel_title"] = novel_title
  → composed = self._composer.build(LLMIntent.PLAN, ctx)  ← FIXED
  → agent.run(prompt=event_context, system_prompt=composed.system, deps=deps)
```

### Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Temporal consistency instructions resolve through PromptComposer | Unit test: mock PromptComposer, assert `.build()` called with `LLMIntent.PLAN` and `mode="temporal_consistency"` |
| 2 | Dynamic event context is in user prompt, NOT baked into system prompt | Unit test: event_context string in `prompt` parameter, not in `system_prompt` |
| 3 | Capabilities continue to supply guaranteed persona/rules | Existing NarrareAgent test covers TimelineAgent |
| 4 | Architecture checker reports no app-layer prompt-loader violations | Checker: extended `prompts.py` reports 0 for planning module |
| 5 | **NEW:** `_prompt_loader.py` is REMOVED from `apps/api/` | File does not exist; `git rm` verified |
| 6 | **NEW:** Uses standardized XML template tags per CR-01 | If temporal_consistency template is modified, variables wrapped |
| 7 | **NEW:** Temporal consistency prompt path has >0 tests (currently 0) | Test file exists with path-compliance + content assertions |
| 8 | **NEW:** No `importlib.resources` import in `timeline_consistency_service.py` for prompt loading | Code review + checker |

### Files to Modify

| File | Change |
|------|--------|
| `apps/api/narrare/planning/_prompt_loader.py` | **DELETE** — entire file removed |
| `apps/api/narrare/planning/timeline_consistency_service.py` | Replace `load_temporal_consistency_prompt()` call with `PromptComposer.build()`; add PromptComposer to constructor DI |
| `packages/core/narrare_core/prompts/route_table.py` | Add `"temporal_consistency"` to `LLMIntent.PLAN` allowed_context_modes |
| `apps/api/narrare/planning/dependencies.py` | Wire PromptComposer into TimelineConsistencyService DI |
| `tests/unit/api/planning/test_timeline_prompt_path_compliance.py` | **NEW** — Prompt-Path-Compliance tests |

### Impact Radius

- **Callers of `load_temporal_consistency_prompt`:** Only `TimelineConsistencyService._run_llm_checks` (1 caller, verified via graph)
- **TimelineConsistencyService constructor:** Gains `PromptComposer` dependency — update DI factory
- **Route table:** `LLMIntent.PLAN` gains allowed_context_mode — verify no conflict with existing "outline" mode

---

## CR-AUFG-02-07 — Writing Graph Fallbacks

### Scope

**In scope:** Remove `composer is None` fallback branches in
`writing_graph_prompts.py`. Remove `_get_fallback_meta()` and its
`MetaPromptLoader` usage. Evaluate `MetaPromptLoader` for removal.

**Out of scope:** Writing graph node logic (unchanged). WritingDeps fields
(except making composer required).

### Root Cause

`writing_graph_prompts.py` has 5 prompt-builder functions that each contain:

```python
async def get_outline_prompt(composer, deps, state):
    if composer is None:
        instruction = f"Create a chapter outline for chapter {state.chapter_id}..."
        meta = await _get_fallback_meta(deps.language)
        return (meta, instruction)
    # ... PromptComposer path ...
```

The `composer is None` branch:
1. Constructs inline f-string task prompts (RULE-02 violation)
2. Calls `_get_fallback_meta()` which uses `MetaPromptLoader` (pre-ADR-026
   mechanism, bypasses NarrareMeta Capability)
3. Silently degrades — no error, no logging at WARNING level when fallback activates
4. Is reachable in production if DI fails to wire PromptComposer

`_get_fallback_meta()` (lines 39–54):
```python
async def _get_fallback_meta(language: str = "en") -> str:
    global _meta_loader, _cached_meta
    if _meta_loader is None:
        _meta_loader = MetaPromptLoader()  # ← pre-ADR-026 mechanism
    _cached_meta[language] = await _meta_loader.load(language)
    return _cached_meta[language]
```

This uses global mutable state (`_meta_loader`, `_cached_meta`) and bypasses
the NarrareMeta Capability that every NarrareAgent already injects.

### Current State (Code Evidence)

```
get_outline_prompt(composer=None, ...) → inline f-string + _get_fallback_meta()
get_draft_prompt(composer=None, ...)   → inline f-string + _get_fallback_meta()
get_review_prompt(composer=None, ...)  → inline f-string + _get_fallback_meta()
get_revise_prompt(composer=None, ...)  → inline f-string + _get_fallback_meta()
get_summary_prompt(composer=None, ...) → inline f-string + _get_fallback_meta()

_get_fallback_meta() → MetaPromptLoader().load()  ← bypasses NarrareMeta Capability
```

### Migration Target

1. **Remove `composer is None` branches:** Replace with fail-fast
   `ConfigurationError("PromptComposer is required for writing graph production paths")`.

2. **Make `WritingDeps.composer` required:** Change from `composer: PromptComposer | None`
   to `composer: PromptComposer`. Update all WritingDeps construction sites.

3. **Remove `_get_fallback_meta()`:** No remaining callers after step 1.

4. **Remove or deprecate `MetaPromptLoader`:**
   - Check all callers of `MetaPromptLoader` (graph: `_get_fallback_meta` is the only production caller)
   - If no remaining callers: remove `MetaPromptLoader` from `meta.py`
   - If test-only callers remain: mark `@deprecated("Removed per ADR-046. Use NarrareMeta Capability.")`

### Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `composer is None` paths replaced with fail-fast `ConfigurationError` | Unit test: passing `composer=None` raises `ConfigurationError` |
| 2 | No overridable meta/user task prompts loaded as degraded production path | Code review: no `_get_fallback_meta` calls in production code |
| 3 | **NEW:** `MetaPromptLoader` is removed from `meta.py` OR marked `@deprecated` with removal date | Code review: `grep MetaPromptLoader packages/core/` shows 0 production callers |
| 4 | **NEW:** `writing_graph_prompts.py` does not import `MetaPromptLoader` | Checker + code review |
| 5 | **NEW:** `_get_fallback_meta()` is removed | Code review: function does not exist |
| 6 | **NEW:** Any test-only fallback is documented as intentionally non-production | Test docstring asserts it cannot be reached by production DI |
| 7 | **NEW:** `WritingDeps.composer` is typed as `PromptComposer` (not `PromptComposer | None`) | mypy/pyright: field is non-Optional |
| 8 | **NEW:** Writing graph production tests use real PromptComposer (mocked or TestModel) | Test review: no test constructs WritingDeps with `composer=None` for production path testing |

### Files to Modify

| File | Change |
|------|--------|
| `packages/core/narrare_core/agents/writing_graph_prompts.py` | Remove `_get_fallback_meta()`; remove all `composer is None` branches; add fail-fast error; remove MetaPromptLoader import |
| `packages/core/narrare_core/agents/writing_graph_deps.py` (or wherever WritingDeps is defined) | Make `composer` field required (non-Optional) |
| `packages/core/narrare_core/prompts/meta.py` | Remove `MetaPromptLoader` class (if no remaining callers) OR add `@deprecated` decorator |
| All WritingDeps construction sites | Ensure `composer` is always provided |
| `tests/unit/core/agents/test_writing_graph_prompts.py` | Update tests: remove `composer=None` test cases or convert to "raises ConfigurationError" tests |

### Impact Radius

- **Callers of `_get_fallback_meta()`:** 5 functions in writing_graph_prompts.py (all internal)
- **Callers of `MetaPromptLoader`:** `_get_fallback_meta()` (production), possibly tests
- **WritingDeps construction sites:** All places that create `WritingDeps` — search for `WritingDeps(` across codebase
- **Writing graph nodes:** Node functions call `get_*_prompt()` — interface unchanged (returns `tuple[str, str]`), but now requires non-None composer
- **Test fixtures:** Tests that construct WritingDeps with `composer=None` must be updated

---

## Prevention Infrastructure Implementation Tasks

> These tasks implement D.1–D.5 from ADR-046. They are Platform-layer tasks
> (scripts, CI infrastructure) and can run in parallel with the retrofit tasks.

### D.1 — Prompt-Path-Compliance Test Convention

**Task:** Create `tests/unit/core/prompts/test_prompt_path_compliance.py` as a
convention/documentation test that:
1. Scans all services that resolve prompts
2. Asserts each has a corresponding `test_*_prompt_path_compliance.py` file
3. Documents the convention for future services

**Per-service test files to create (as part of retrofit tasks):**
- `tests/unit/api/chat/test_chat_prompt_path_compliance.py`
- `tests/unit/api/kb/test_worldbuilding_prompt_path_compliance.py`
- `tests/unit/api/planning/test_timeline_prompt_path_compliance.py`
- `tests/unit/core/agents/test_writing_graph_prompt_path_compliance.py`

### D.2 — check_architecture.py Extension

**Task:** Create three checker modules:

1. `scripts/architecture/_checkers/prompt_path.py`:
   - Detect `PromptRegistry` imports outside `core/prompts/`
   - Detect `PromptRegistry.resolve()` / `prompt_registry.resolve()` calls outside `core/prompts/`
   - Baseline: 0 violations after retrofit

2. Extension to `scripts/architecture/_checkers/prompts.py`:
   - Detect `importlib.resources` usage + `_bundled` references in `apps/`
   - Detect `.replace("{{` pattern (manual template substitution) in `apps/`
   - Baseline: 0 violations after retrofit

3. `scripts/architecture/_checkers/prompt_channel.py`:
   - Detect `composed.system` + `composed.user` concatenation patterns
   - Detect `f"...{composed.system}..."` in `prompt=` parameter context
   - Baseline: 0 violations after retrofit

### D.3 — No additional script needed

The D.2 modules run within the existing `check_architecture.py` pipeline. No
separate `check_prompt_path_compliance.py` script.

### D.4 — ADR-Retrofit-Plan Requirement

**Task:** Update `.opencode/context/narrare-dev/processes/adr-process.md` to
require a Retrofit-Plan section for any ADR that changes prompt mechanics.

### D.5 — Adoption Metric Extension

**Task:** Update `scripts/architecture/adoption-registry.yaml` to add
`prompt_path_compliant: bool` field per intent entry. Update the adoption
checker to verify this field.

---

## RULE-XX Compliance Matrix (All Tasks)

| Rule | CR-02-04 | CR-02-05 | CR-02-06 | CR-02-07 |
|------|----------|----------|----------|----------|
| RULE-02 | ✅ Removes f-string concat | ✅ Removes direct registry | ✅ Removes app-layer loader | ✅ Removes inline f-strings |
| RULE-02a | ✅ System→system, user→user | ✅ Customizable→Composer | ✅ Customizable→Composer | ✅ Customizable→Composer |
| **RULE-02b** | ✅ No user-channel injection | ✅ No direct registry access | ✅ No app-layer loader | ✅ No fallback paths |
| RULE-03 | ✅ ChatService contract exists | ✅ Analyzer contract exists | ✅ Service contract exists | ✅ Graph contracts exist |
| RULE-07 | ✅ app→core delegation | ✅ app→core delegation | ✅ Removes app-layer core logic | ✅ core internal fix |
| RULE-10 | ✅ Adds tests (0→N) | ✅ Adds tests | ✅ Adds tests (0→N) | ✅ Updates tests |
| RULE-11 | ✅ No silent concat | ✅ Fail-fast, no bare except | ✅ No silent empty return | ✅ No silent fallback |
| RULE-20 | ✅ Full fix, no half-impl | ✅ Full fix | ✅ Full fix + file removal | ✅ Full fix + loader removal |
