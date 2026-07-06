# ADR-054 — Inline Feature-Prompt Debt Migration (FIND-011 Clones)

> **Status:** ✅ Accepted (contract decisions; implementation via Retrofit Plan below)
> **Date:** 2026-06-25
> **Deciders:** Architecture Specialist
> **Supersedes:** None
> **Resolves:** The three ratcheted `INLINE-FEATURE-PROMPT` baseline violations (FIND-011 clones)
> **Related:** ADR-049 (precedent — FIND-011 timeline migration), ADR-048 (Mode 1/Mode 2
> invocation contract), ADR-046 (Retrofit-Plan mandate), ADR-026 (prompt content categories),
> CONSTRAINTS.md RULE-02 / RULE-02a / RULE-02b / RULE-11 / RULE-22

---

## Context

ADR-049 Phase C migrated one inline feature-prompt service
(`timeline_analysis_service.py`, FIND-011) to PromptComposer Mode 1 and shipped
the `INLINE-FEATURE-PROMPT` gate (ADR-049 A5) in Phase D. That gate found three
*additional* services with the identical anti-pattern. Because they were not part
of FIND-011's scope and were discovered after the ADR-049 ratchet baseline was
set, they were ratcheted as known debt rather than silently absorbed:

| Service | File:line | Intent | Inline feature framing |
|---------|-----------|--------|------------------------|
| `CharacterArcService` | `apps/api/narrare/planning/character_arc_service.py:139` | `PLAN` | `f"Generate a character arc for {request.character_name} in {novel.title}"` |
| `TimelineExtractionService` | `apps/api/narrare/planning/timeline_extraction_service.py:164` | `PLAN` | `f"Extract temporal expressions from the following chapter of '{novel.title}': …"` |
| `KBMergeService` | `apps/api/narrare/kb/merge_service.py:145` | `KB_CONSISTENCY` | `f"Analyze merge candidates for '{novel.title}'.\nEntity type: …\nCandidate pairs: …"` |

These are listed in `_BASELINE_VIOLATIONS` of
`scripts/architecture/_checkers/_check_inline_feature_prompt.py:94-96`.

### Why this is a rule violation, not a stylistic choice

Each service:

1. **Assembles a feature/task prompt via f-string** (`"Generate …"`,
   `"Extract …"`, `"Analyze …"` — imperatives + task framing). That is category-1
   user-customisable content. Per RULE-02, no module outside `core/prompts/` may
   assemble a prompt via f-string/concatenation; per RULE-02a category 1, feature
   task framing MUST flow through the PromptComposer cascade.

2. **Passes it directly as `agent.run(prompt=…)`.** The three agents
   (`CharacterArcAgent`, `TemporalExtractionAgent`, `KBMergeAgent`) have **no**
   `@agent.instructions` and no internal composition — they relay whatever
   `prompt=` they receive (verified: each agent class defines only an output
   function and a validator; the docstring examples pass task framing as the run
   prompt). So the run prompt is the feature framing, delivered through the user
   channel — a RULE-02b violation 3 (feature system content concatenated into
   the user channel).

3. **Declares a `ManualInjectionDeclaration` whose `reason` is factually false.**
   Each declaration claims the agent "composes its prompt internally from
   `<Deps>`". The agents compose nothing. `compose_invocation(manual_injection=…)`
   is the ADR-048 **Mode 2** (agent-internal) contract
   (`non_writing_adapter.py:100-102`: `is_agent_internal` is `True` iff
   `manual_injection is not None`, and Mode 2 returns `composed_prompt=None` with
   the marker *"the agent owns [composition]"*). A service may only use Mode 2
   when the agent genuinely owns composition. Here the service owns it (via the
   f-string), so the Mode 2 declaration is a false cover for a RULE-02 violation.

4. **Swallows the composition error** (`except Exception: logger.warning(…)`
   around `compose_invocation`). That is a RULE-11 (No Silent Failures)
   violation: invocation-composition failure degrades silently to the inline
   f-string instead of failing fast.

### Root-cause chain

1. **Why is the prompt inline?** The three services predate governed templates
   for their use-cases and were never migrated when the prompt-surface contract
   (ADR-037) and the path-compliance contract (ADR-046) were introduced.
2. **Why was a `ManualInjectionDeclaration` added instead of a template?**
   Because ADR-048 Mode 2 was treated as an "agent composes internally" escape
   hatch. Mode 2 lets a service skip PromptComposer composition *provided the
   agent genuinely owns the prompt*. These agents do not — the declaration is a
   mis-categorisation (ADR-048 Q1 audit category A: "mislabeled Mode 1 →
   migrate"). The agents have no `@agent.instructions`, so the framing leaks into
   the service f-string.
3. **Why did the gate not block them at the time?** Because they were discovered
   after the ADR-049 ratchet baseline was fixed and were ratcheted rather than
   fixed inline (out of FIND-011 scope). That was a deliberate, documented
   deferral — see `CURRENT_STATE.md` "CR-04 Follow-up Debt" table. This ADR
   retires that deferral.
4. **Design response.** Migrate all three to **Mode 1** (PromptComposer-bundled
   template via `compose_invocation(composer=…)`), exactly as FIND-011 did. The
   services already call `compose_invocation` — this is a **mode switch**, not a
   new integration. No new variables are required (verified: every variable is
   already in `SYSTEM_VARS` / `FEATURE_DYNAMIC_VARS`).

---

## Decision Drivers

- **RULE-02 / 02a / 02b.** Feature/task framing must be built by PromptComposer;
  services may not assemble it via f-string; feature system content must not be
  delivered through the user channel. These three services violate all three.
- **RULE-11.** Invocation composition must not fail silently. The current
  `except Exception: logger.warning` masking must be removed.
- **ADR-049 precedent.** FIND-011 established the migration pattern:
  intent + `context_mode` + governed template + Mode 1, reusing the existing
  `_resolve_context_mode_route()` helper and `allowed_context_modes` mechanism.
  ADR-054 applies that exact pattern three more times. Consistency with the
  resolved precedent is itself a driver.
- **ADR-048 Mode contract.** Mode 2 requires the agent to own composition. These
  agents do not. Migrating to Mode 1 removes the false declarations and the
  reliance on a Mode-2 escape hatch that does not apply.
- **RULE-22 items 3/4.** New context-modes must have no semantic overlap with
  existing modes, and their variables must be registered (they are).
- **ADR-046 §D.4 Retrofit-Plan mandate.** This ADR changes prompt mechanics, so
  a Retrofit Plan is mandatory.
- **Debt retirement, not concealment.** `CURRENT_STATE.md` explicitly disclosed
  these three as ratcheted baseline debt. This ADR retires them rather than
  leaving them as permanent approved exceptions.

---

## Options Considered

### Option A — Mode 1: PromptComposer-bundled template via `context_mode` (chosen)

For each service: add a context-mode to the intent's `allowed_context_modes`,
create a governed `_bundled/<category>/<lang>/<mode>/system.md` template, inject
`PromptComposer`, call `compose_invocation(composer=…, prompt_context=…, intent=…)`
and pass `composed.system`/`composed.user` to the agent. Delete the false
`ManualInjectionDeclaration`. Remove the error-swallowing `try/except`.

**Pros:**
- Identical to the resolved FIND-011 precedent (ADR-049 D7–D10) — zero new
  mechanism, only repetition of a proven pattern.
- RULE-02/02a/02b compliant: feature framing flows through the cascade and
  becomes user-overridable (project/user/bundled).
- Removes the false Mode 2 declarations and the RULE-11 error masking in one
  move.
- All template variables already registered — no taxonomy churn.
- The services already call `compose_invocation`, so the diff is a mode switch,
  not a new integration.

**Cons:**
- Three new governed templates must be authored (en first; de/fr follow).
- `PLAN` and `KB_CONSISTENCY` route/manifest entries gain context-modes
  (additive, backward-compatible).

### Option B — Make Mode 2 genuine via `@agent.instructions`

Add `@agent.instructions` to each agent that builds the task framing from `Deps`,
keep Mode 2, delete the service f-string.

**Pros:**
- Service-side prompt construction disappears.

**Cons:**
- **Moves the RULE-02a violation, does not fix it.** The task framing ("Generate
  a character arc", "Extract temporal expressions", "Analyze merge candidates")
  is category-1 user-customisable content. RULE-02a explicitly reserves
  `@agent.instructions` for category-3 *dynamic per-invocation data* (KB data,
  style/voice profiles) — "data, not instructions". Baking task framing into the
  agent makes it non-overridable and trades a service-level RULE-02 violation for
  an agent-level RULE-02a violation. ADR-049 rejected this for FIND-011 (Option 3
  there) for the same reason.
- Hides feature content from the Prompt Management UI and overrides.
- Keeps the false Mode 2 framing alive in spirit.

**Rejected** because it trades one violation for another and removes user
overridability.

### Option C — New dedicated intents

Add `LLMIntent.CHARACTER_ARC`, `LLMIntent.TIMELINE_EXTRACTION`,
`LLMIntent.KB_MERGE`, each with its own category/mode, manifest entry, route
table row, and model-routing classification.

**Pros:**
- Maximally explicit per surface.

**Cons:**
- **Intent-enum inflation.** The established pattern (ADR-049 Decision D7, the
  PLAN docstring itself) is one `PLAN` intent with `context_modes`, not one
  intent per planning sub-task. Adding three intents silently contradicts that.
- Far more ceremony (enum member + route + manifest + model-routing + tests) for
  use-cases the `context_mode` mechanism was built to handle.
- Inconsistent with the just-resolved FIND-011 precedent.

**Rejected** because context-mode is the established, lower-ceremony pattern.

### Selection: Option A

It is the only option simultaneously RULE-02/02a/02b/RULE-11 compliant,
consistent with the resolved FIND-011 precedent, user-overridable, and free of
enum inflation.

---

## Decision

### D1 — `CharacterArcService` migrates to Mode 1, context-mode `character_arc`

The service injects `PromptComposer`, builds a `PromptContext(language=…,
mode="character_arc", project_title=…, genre=…, character_name=…,
character_current_state=…, character_goal_state=…)`, and calls
`compose_invocation(composer=…, prompt_context=ctx, intent=LLMIntent.PLAN,
invocation_context=…)`. The agent receives `composed.system` as its system prompt
and `composed.user` (minimal/empty — the character data lives in `Deps`) as the
run prompt. The inline f-string and `_CHARACTER_ARC_INJECTION` are deleted.

### D2 — `TimelineExtractionService` migrates to Mode 1, context-mode `timeline_extraction`

Same Mode 1 flow with `intent=LLMIntent.PLAN`, `mode="timeline_extraction"`. The
template carries the extraction task framing + novel metadata variables
(`project_title`, `genre`, `writing_language`). The per-chapter **content** is
category-3 runtime data and stays the run prompt (`composed.user` = chapter
title/position/content) — only the *framing* moves into the template.
`_TIMELINE_EXTRACTION_INJECTION` is deleted.

> **Note on naming.** This `timeline_extraction` mode is distinct from ADR-049's
> `timeline` mode (RULE-22 item 3): `timeline` *generates a chronological
> timeline from chapter summaries* (via `TimelineAgent`/
> `timeline_analysis_service.py`); `timeline_extraction` *extracts temporal
> expressions from individual chapters* (via `TemporalExtractionAgent`/
> `timeline_extraction_service.py`). Different agent, different task, different
> service. No semantic overlap.

### D3 — `KBMergeService` migrates to Mode 1, context-mode `merge`

Same Mode 1 flow with `intent=LLMIntent.KB_CONSISTENCY`, `mode="merge"`. The
template carries the merge-analysis framing + `entity_type`/`genre`/
`writing_language`/`project_title`. The candidate-pairs text is category-3
runtime data and stays the run prompt. `_MERGE_MANUAL_INJECTION` is deleted.

### D4 — `PLAN` gains `character_arc` and `timeline_extraction` context-modes

`ROUTE_CONFIGS[LLMIntent.PLAN].allowed_context_modes` becomes
`frozenset({"outline", "temporal_consistency", "timeline", "character_arc",
"timeline_extraction"})`. Route-table-only change; `_resolve_context_mode_route()`
already overrides the template mode from `context_mode`.

### D5 — `KB_CONSISTENCY` gains `merge` context-mode

`ROUTE_CONFIGS[LLMIntent.KB_CONSISTENCY]` gains
`allowed_context_modes=frozenset({"consistency", "merge"})` (it currently has
none; default mode `"consistency"` is preserved). The `merge` mode resolves to
`_bundled/kb/<lang>/merge/system.md`.

### D6 — Three governed templates created (en first)

| Template | Frontmatter `prompt_type` | Required vars | Optional vars |
|----------|---------------------------|---------------|---------------|
| `_bundled/planning/en/character_arc/system.md` | `planning` | `character_name`, `character_current_state`, `character_goal_state` | `project_title`, `genre`, `writing_language` |
| `_bundled/planning/en/timeline_extraction/system.md` | `planning` | — | `project_title`, `genre`, `writing_language` |
| `_bundled/kb/en/merge/system.md` | `kb` | — | `project_title`, `entity_type`, `genre`, `writing_language` |

Each template's frontmatter: `prompt_type: <category>`, `prompt_language: en`,
`prompt_version: "1.0.0"`. The body encodes the task framing currently inlined in
the service f-string (per ADR-049 D8's model). Runtime data (chapter content,
candidate-pairs text) is **not** baked into the templates — it is the run prompt.
All variables are pre-registered in `SYSTEM_VARS` / `FEATURE_DYNAMIC_VARS`
(verified). **de/fr locales** are produced as a follow-up (en is the v1 cut);
`output_language_variable` is `writing_language`.

### D7 — Delete the three false `ManualInjectionDeclaration`s

`_CHARACTER_ARC_INJECTION`, `_TIMELINE_EXTRACTION_INJECTION`, and
`_MERGE_MANUAL_INJECTION` are deleted along with their `manual_injection=`
kwargs. Mode 1 does not use `ManualInjectionDeclaration`. This also retires the
ADR-048 Q1-audit category-A mislabel on these three.

### D8 — Stop swallowing invocation-composition errors (RULE-11)

Each service currently wraps `compose_invocation` in
`except Exception: logger.warning(…)`. That masks a configuration/pipeline
failure and silently degrades to the inline f-string. The `try/except` is
removed; composition failures propagate (the existing `NotFoundError` /
`ConfigurationError` pre-checks remain). This is the RULE-11 half of the fix and
must ship together with D1–D3 — migrating the prompt path while keeping the
silent-failure masking would reintroduce the exact anti-pattern RULE-11 forbids.

### D9 — Manifest `context_modes` extended

The prompt-surface manifest (`scripts/architecture/prompt-surface-manifest.yaml`)
is extended (additive, ADR-049 D11 shape):
- `PLAN` entry: add `character_arc` and `timeline_extraction` sub-entries under
  the existing `context_modes:` list.
- `KB_CONSISTENCY` entry: gains a `context_modes:` list with `consistency` (the
  existing default template) and `merge`.

### D10 — Checker baseline retired

`_BASELINE_VIOLATIONS` in `_check_inline_feature_prompt.py` is emptied (the three
entries removed) once all three services are migrated. After migration the ratchet
floor is zero: any *new* inline feature-prompt is blocking, and there is no
approved debt baseline left. The `is_approved_exception` baseline path remains in
the checker for future temporary ratchets, but is empty.

---

## Rationale

The resolved precedent (ADR-049 / FIND-011) already proved that the correct fix
for an inline feature-prompt service is *intent + context-mode + governed
template + Mode 1*. ADR-054 is the deliberate application of that exact fix three
more times to retire explicitly-disclosed debt. There is no architectural novelty
here and no reason to invent one: the simplest *correct* solution (KISS) is to
repeat the proven pattern, not to introduce `@agent.instructions` framing
(Option B, which re-violates RULE-02a) or new intents (Option C, which inflates
the enum and contradicts the PLAN intent's own documentation).

Crucially, the services already call `compose_invocation`. The migration is a
**mode switch** (`manual_injection=` → `composer=`/`prompt_context=`/`intent=`),
not a new integration. The only genuinely new artefacts are three governed
templates and two route/manifest context-mode additions — all of which use
pre-registered variables.

---

## Consequences

**Positive:**
- `INLINE-FEATURE-PROMPT` baseline debt fully retired (3 → 0). The gate now has
  no approved debt floor.
- Three services become RULE-02/02a/02b/RULE-11 compliant and their prompts
  become user-overridable via the cascade.
- Three false `ManualInjectionDeclaration`s removed; ADR-048 Q1-audit category-A
  mislabels on these services retired.
- `PLAN`'s `context_modes` pattern extends cleanly (5 modes); `KB_CONSISTENCY`
  gains the same shape, consistent with `KB_WORLDBUILD`'s phase1/phase2 model.

**Negative / Trade-offs:**
- Three new governed templates to author and translate (en first; de/fr follow).
- `KB_CONSISTENCY` moves from a single-template intent to a context-mode intent —
  additive, but the manifest checker must already support `context_modes`
  sub-entries (it does, per ADR-049 D11 / PROMPT-CONTEXT-MODES).
- Removing the error-swallowing `try/except` means a real pipeline/config
  failure now surfaces as an error on these endpoints rather than a silent
  inline fallback. That is the desired RULE-11 behaviour.

**Constraints introduced:**
- **RULE-02/02a/02b:** reinforced on three more services.
- **RULE-11:** invocation-composition failures fail fast on these services.
- **RULE-22 items 3/4:** `character_arc`, `timeline_extraction`, `merge`
  context-modes are checked for semantic overlap (none — see D2 note and the
  table below) and use only pre-registered variables.

---

## Retrofit Plan (ADR-046 §D.4 mandatory)

This ADR changes prompt route identity (adds routeable context-modes) and
migrates prompt construction. Per
`.opencode/context/narrare-dev/processes/adr-process.md` §D.4, this Retrofit Plan
is mandatory.

### 1. Inventory of affected paths

| Path | Symbol | Current state | Action |
|------|--------|---------------|--------|
| `packages/core/narrare_core/prompts/route_table.py:161-168` | `ROUTE_CONFIGS[PLAN].allowed_context_modes` | `{outline, temporal_consistency, timeline}` | → add `character_arc`, `timeline_extraction` (D4) |
| `packages/core/narrare_core/prompts/route_table.py:146` | `ROUTE_CONFIGS[KB_CONSISTENCY]` | `("kb", "consistency")`, no modes | → add `allowed_context_modes={consistency, merge}` (D5) |
| `packages/core/narrare_core/prompts/_bundled/planning/en/character_arc/system.md` | n/a | does not exist | CREATE (D6) |
| `packages/core/narrare_core/prompts/_bundled/planning/en/timeline_extraction/system.md` | n/a | does not exist | CREATE (D6) |
| `packages/core/narrare_core/prompts/_bundled/kb/en/merge/system.md` | n/a | does not exist | CREATE (D6) |
| `scripts/architecture/prompt-surface-manifest.yaml:308-351` | PLAN `context_modes` | outline / temporal_consistency / timeline | → add `character_arc`, `timeline_extraction` (D9) |
| `scripts/architecture/prompt-surface-manifest.yaml:204-216` | KB_CONSISTENCY | single template, no `context_modes` | → add `context_modes:` list (consistency + merge) (D9) |
| `apps/api/narrare/planning/character_arc_service.py:27-42` | `_CHARACTER_ARC_INJECTION` | false Mode 2 declaration | DELETE (D7) |
| `apps/api/narrare/planning/character_arc_service.py:127-142` | `generate_character_arc` body | Mode 2 + swallowed error + f-string at :139 | → Mode 1, remove `try/except`, delete f-string (D1/D8) |
| `apps/api/narrare/planning/timeline_extraction_service.py:37-47` | `_TIMELINE_EXTRACTION_INJECTION` | false Mode 2 declaration | DELETE (D7) |
| `apps/api/narrare/planning/timeline_extraction_service.py:144-173` | `stream_extraction` body | Mode 2 + swallowed error + f-string at :164 | → Mode 1, remove `try/except`, chapter content stays run prompt (D2/D8) |
| `apps/api/narrare/kb/merge_service.py:32-41` | `_MERGE_MANUAL_INJECTION` | false Mode 2 declaration | DELETE (D7) |
| `apps/api/narrare/kb/merge_service.py:119-152` | `analyze_merge_candidates` body | Mode 2 + swallowed error + f-string at :145 | → Mode 1, remove `try/except`, candidate pairs stay run prompt (D3/D8) |
| `scripts/architecture/_checkers/_check_inline_feature_prompt.py:88-98` | `_BASELINE_VIOLATIONS` | 3 entries (139/164/145) | → empty after migration (D10) |

> Each service also needs a `PromptComposer` constructor dependency wired through
> its DI factory (the same injection already used by the FIND-011 service).

### 2. Migration steps per path (ordered, atomic, independently testable)

**Step 1 (Core, CI-safe):** Update `route_table.py` — `PLAN` gains `character_arc`
+ `timeline_extraction`; `KB_CONSISTENCY` gains `allowed_context_modes`. CI-safe
because no service yet routes through the new modes (templates are created next).

**Step 2 (Core):** Create the three templates (`character_arc`,
`timeline_extraction`, `merge`) with the D6 frontmatter and the task framing
currently inlined. Until Step 3 these templates are orphan (not loaded) —
acceptable for an atomic slice.

**Step 3 (Backend):** Rewrite each service to Mode 1: inject `PromptComposer`,
build `PromptContext(mode=…)`, call `compose_invocation(composer=…,
prompt_context=…, intent=…)`, pass `composed.system`/`composed.user` to the agent,
delete the `ManualInjectionDeclaration` + `manual_injection=` kwarg, delete the
f-string, and remove the error-swallowing `try/except` (RULE-11). After this step
all three services are RULE-02/02a/02b/RULE-11 compliant.

**Step 4 (Platform, manifest):** Extend `prompt-surface-manifest.yaml` — PLAN
`context_modes` gains `character_arc` + `timeline_extraction`; KB_CONSISTENCY
gains a `context_modes:` list (consistency + merge). Backward-compatible.

**Step 5 (Platform, checker):** Empty `_BASELINE_VIOLATIONS` in
`_check_inline_feature_prompt.py` (D10). The ratchet floor is now zero.

**Step 6 (Locales, follow-up):** Author de/fr variants of the three templates.

### 3. Breaking-change assessment

- **Route-table (Step 1):** No external API change. The default modes (`outline`,
  `consistency`) are unchanged; the new modes are opt-in via `context_mode`.
- **Service internals (Step 3):** Public service signatures unchanged. Internal
  prompt construction changes from f-string to `composer.build`. `agent.run`
  now receives `composed.user` instead of the f-string; the agents' `prompt: str`
  contract is unchanged. The new `PromptComposer` dependency is added to each
  service constructor (DI factory updated).
- **RULE-11 behaviour change (Step 3):** A previously-swallowed pipeline failure
  now raises. This is the intended behaviour; any test that relied on the silent
  fallback must be updated to assert the error propagates.
- **`ManualInjectionDeclaration` removal (Step 3):** If any test asserts the
  declaration object exists, that test must be updated. No production caller
  depends on the declaration.
- **Manifest `context_modes` (Step 4):** Additive; the checker handles both
  old-style (no `context_modes`) and new-style entries.

### 4. Checker update plan

| Checker module | Change | New baseline |
|----------------|--------|--------------|
| `scripts/architecture/_checkers/_check_inline_feature_prompt.py` | Empty `_BASELINE_VIOLATIONS` (D10) once all three services migrated | **Zero** — no approved debt floor remains |
| `scripts/architecture/_checkers/_check_prompt_surface.py` (PROMPT-CONTEXT-MODES, ADR-049 A3/A6) | No code change required — already validates `context_modes` sub-entries; simply gains three new sub-entries (character_arc, timeline_extraction, merge) to validate | No new debt — all three templates must exist and match their declared category |

No new checker is introduced. ADR-049's Phase D gate already covers both the
inline-prompt surface (A5) and the context-mode/manifest surface (A3/A6); this
ADR only retires baseline entries within them.

### 5. Test update plan

- `tests/unit/api/planning/test_character_arc_service.py` — assert
  `compose_invocation(composer=…, intent=LLMIntent.PLAN, prompt_context(mode="character_arc"))`
  is called; agent receives `composed.user`, not an f-string; no
  `manual_injection=` kwarg; composition failure propagates (not swallowed).
- `tests/unit/api/planning/test_timeline_extraction_service.py` — assert Mode 1
  with `mode="timeline_extraction"`; the chapter content is passed as the run
  prompt (category-3 data), framing is not inlined.
- `tests/unit/api/kb/test_merge_service.py` — assert Mode 1 with
  `mode="merge"`; candidate-pairs text is the run prompt.
- `tests/unit/core/prompts/test_routes.py` — assert
  `resolve_prompt_route(LLMIntent.PLAN, context_mode="character_arc")` and
  `"timeline_extraction"` resolve to the new templates; assert
  `KB_CONSISTENCY` + `context_mode="merge"` resolves to `kb/<lang>/merge/system.md`.
- `tests/unit/architecture/test_prompt_path_checker.py` — confirm the three
  files are no longer in the `INLINE-FEATURE-PROMPT` baseline and that a
  synthetic f-string feature prompt is still flagged.
- Existing parametrized composer/route-table tests that iterate intents/modes
  are extended to cover the new context-modes.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | No agent/model import changes; the three agents' usage is unchanged. |
| RULE-02 | ✅ | Feature-prompt assembly moves from service f-strings to PromptComposer for all three services. |
| RULE-02a | ✅ | Task framing (category-1 content) flows through the cascade; runtime data (chapter content, candidate pairs) stays as run-prompt data (category-3). |
| RULE-02b | ✅ | Services stop using `manual_injection=` Mode 2; resolution path is PromptComposer only. No feature framing in the user channel. |
| RULE-03 | ✅ | No new public contract; existing `PromptComposer`/`compose_invocation`/route contracts reused. |
| RULE-04 | ✅ | Service files stay well under limits; route-table/manifest edits are configuration, not logic. |
| RULE-05 | ✅ | Templates/route-table/manifest stay in their owned modules; no cross-domain `_internal` imports. |
| RULE-06 | ✅ | Each file keeps one responsibility; services delegate framing to the composer. |
| RULE-07 | ✅ | Core owns templates/route-table/manifest; Platform owns checkers. No Core→apps imports. |
| RULE-09 | ✅ | No new public APIs; existing typed signatures preserved. |
| RULE-10 | ✅ | Regression tests specified per service + route + checker (§5). |
| RULE-11 | ✅ | The error-swallowing `try/except` around `compose_invocation` is removed (D8); composition failures fail fast. |
| RULE-20 | ✅ | No half-implementation: governance (this ADR + Retrofit Plan) and implementation (Steps 1–5) are both fully specified. |
| RULE-22 | ✅ | `character_arc`, `timeline_extraction`, `merge` checked for semantic overlap (none — see D2 note); all variables pre-registered. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. Mode 1 + context-mode is the established,
   proven pattern (ADR-049). Retiring the baseline to zero means the gate has no
   debt floor to drift on.
2. **Hard-to-undo coupling?** No. Context-mode additions are additive and
   backward-compatible (default modes preserved). The templates are standard
   governed templates, removable without architectural impact.
3. **Simplest correct solution?** Yes. The simplest *correct* fix is to repeat
   the resolved FIND-011 pattern — not to introduce `@agent.instructions`
   framing (Option B re-violates RULE-02a) or new intents (Option C inflates the
   enum and contradicts the PLAN docstring).
4. **Design intent clear?** Yes. The three services are FIND-011 clones; the fix
   is the FIND-011 fix, three times, with the INLINE-FEATURE-PROMPT baseline
   emptied as the acceptance criterion.

---

## Review Trigger

- [ ] When a fourth inline feature-prompt is discovered — confirm the
      `INLINE-FEATURE-PROMPT` gate is still CI-blocking with a zero baseline
      (D10).
- [ ] When `de`/`fr` locales for the three templates are authored — confirm the
      manifest/variable parity holds across locales.
- [ ] When ADR-048 Mode 2 usage is next audited — confirm these three services
      are recorded as migrated to Mode 1 (Q1-audit category A retired).
- [ ] After 3 months — audit whether any of the three services has regressed to
      an inline f-string or re-added an error-swallowing `try/except`.

---

## ADR Implementation Completeness Gate (Gate 12)

This ADR is **Accepted** for its decisions (D1–D10). It will be marked
"✅ Implemented" only when:

- [ ] Step 1 applied: `route_table.py` — PLAN + KB_CONSISTENCY context-modes.
- [ ] Step 2 applied: three governed templates created (en).
- [ ] Step 3 applied: three services migrated to Mode 1; three false
      `ManualInjectionDeclaration`s deleted; error-swallowing `try/except`
      removed (RULE-11).
- [ ] Step 4 applied: manifest `context_modes` extended (PLAN + KB_CONSISTENCY).
- [ ] Step 5 applied: `_BASELINE_VIOLATIONS` emptied (zero floor).
- [ ] All regression tests in §5 pass.
- [ ] `just check` (architecture + prompt gates) green with zero
      `INLINE-FEATURE-PROMPT` baseline.
- [ ] No workarounds or shortcuts in any step.
