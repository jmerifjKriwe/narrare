# ADR-037 — Prompt Surface Contract Manifest

> **Status:** ✅ Accepted
> **Date:** 2026-06-05
> **Deciders:** User, Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-002, ADR-025, ADR-026, ADR-032, INFRA-012, CONSTRAINTS.md RULE-02/RULE-03/RULE-20/RULE-22

---

## Context

CR-01 found that Narrare's authored prompts are mostly strong, but prompt quality
can still drift because the prompt surface is distributed across several places:
`LLMIntent` routing, bundled templates, `PromptContext` fields, variable
registries, adoption registry rules, content-review findings, and platform
checkers.

The most important gaps are not individual sentences inside templates. They are
contract gaps: routeable intents can lose a bundled target, variables can appear
without provenance/security classification, user-authored content can lose XML
boundaries, and context produced by assemblers can remain unused by the prompts
that need it.

Root-cause chain:

1. **Symptom:** Missing prompt targets, uneven variable use, inline fallback risk,
   and inconsistent context adoption appear as separate CR-01 findings.
2. **Why #1:** Prompt routes, variable requirements, context producers, and
   fallback policy are not described as one machine-checkable surface.
3. **Why #2:** Existing governance checks validate pieces of the prompt system, but
   no single manifest tells Core and Platform what each production LLM surface is
   allowed to route, require, accept optionally, or reject.
4. **Design:** Add a Prompt Surface Contract manifest as the route-level contract;
   Platform enforces it, Core conforms to it, and Docs reference it.

---

## Decision Drivers

- RULE-02/02a: customizable prompt content must flow through `core/prompts/` and
  remain distinct from ADR-026 capabilities and runtime data.
- RULE-03: cross-module contracts are specified before implementation.
- RULE-20: no half-implemented prompt governance; missing routes/fallbacks cannot
  be treated as acceptable temporary states.
- RULE-22: prompt variables require provenance, security classification, context
  precedence, and semantic-review visibility.
- ADR-025 already chose schema-driven enforcement; this ADR specializes that
  approach for the route-level prompt surface.
- ADR-026 keeps guaranteed content in capabilities; the manifest governs only
  routeable feature templates and their runtime variables.

---

## Options Considered

### Option A — Continue with scattered route/checker rules

Keep route mappings, adoption registry requirements, variable registries, and XML
checks as separate sources.

**Pros:**
- No new artifact.
- Existing checkers can be patched locally.

**Cons:**
- Preserves the root cause: no single route-level contract.
- New intents/templates can drift by satisfying one checker while missing another.
- Context producer/consumer coverage remains review-only instead of checkable.

### Option B — Add a dedicated Prompt Surface Contract manifest (chosen)

Create a machine-readable manifest that records each `LLMIntent` surface, whether
it is routeable, its category/mode/template target, required/optional variables,
variable provenance/security requirements, fallback policy, and output-language
contract.

**Pros:**
- Directly addresses the root cause.
- Reuses ADR-025's schema-driven enforcement pattern.
- Keeps Platform checks deterministic while Core remains the runtime owner.
- Makes CR-01 P0/P1 gates implementation-ready.

**Cons:**
- One more governance artifact must be maintained.
- Manifest and runtime routes require a checker to prevent drift.

### Option C — Generate the manifest only from runtime code

Derive routeability, variables, and fallback policy entirely from
`routes.py`, bundled templates, and registries at check time.

**Pros:**
- No separate manifest data to maintain.
- Lower risk of manifest/runtime mismatch.

**Cons:**
- Cannot express non-routeable rationale, optional variables, source precedence,
  or strategic deferrals cleanly.
- Turns semantic architecture policy into implicit checker heuristics.
- Harder for reviewers to see intended prompt-surface design before code changes.

---

## Decision

**We choose Option B — a dedicated Prompt Surface Contract manifest.**

The manifest lives at `scripts/architecture/prompt-surface-manifest.yaml` and is
the governance SSOT for prompt routeability. Core remains the runtime owner of
`LLMIntent`, `PromptComposer`, `routes.py`, `PromptContext`, and bundled prompt
templates. Platform reads the manifest and fails CI when runtime routes,
templates, variables, XML wrappers, or fallback behavior drift from it.

The manifest does not replace ADR-026 capabilities and does not create a new
runtime dependency from Core to `scripts/`. It is an architecture contract and CI
input, not a prompt-building mechanism.

---

## Rationale

CR-01's findings are connected by one missing abstraction: Narrare lacks a route
surface contract that says “this LLM intent is routeable to this template, with
these variables, from these sources, under this fallback/security policy.”
Patching templates alone would improve today's prompts but would not prevent the
same drift in the next AI feature.

A dedicated manifest is the simplest correct solution because it makes review and
CI speak the same language. It also keeps the three ADR-026 content mechanisms
separate: capabilities guarantee non-customizable rules, PromptComposer handles
customizable feature templates, and runtime context provides data.

Accepted tradeoff: a manifest can drift from runtime code unless a checker exists.
Therefore the manifest checker is a blocker, not an optional documentation aid.

---

## Consequences

**Positive:**
- Routeability, variables, XML wrapping, and fallback policy become one auditable
  contract.
- New `LLMIntent` additions require explicit routeability decisions.
- Context producer/consumer expectations are visible before implementation.
- CR-01 P0 gates become machine-checkable.

**Negative / Tradeoffs:**
- Platform must maintain one additional checker and tests.
- Manifest changes require Architecture review because they are contract changes.
- Some P1/P2 quality gaps may initially be ratcheted warnings while legacy
  templates are brought into conformance; P0 gaps are blockers.

**Constraints introduced:**
- A routeable production intent without a manifest entry is a CI blocker.
- A manifest route whose bundled template is missing is a CI blocker.
- A new template variable absent from the variable taxonomy is a CI blocker.
- User-authored or mixed-provenance variables must be XML-wrapped or rejected by
  strict prompt preflight.
- Production inline fallback bodies are forbidden for manifest-routeable prompts.

---

## Implementation Notes

Required manifest shape:

```yaml
version: "1.0.0"
routes:
  - intent: EXTEND
    routeable: true
    category: writing
    mode: extend_chapter
    template: packages/core/narrare_core/prompts/_bundled/writing/en/extend_chapter/system.md
    content_type: customizable_feature_prompt
    output_language_variable: writing_language
    required_variables: [existing_content, user_preferences, avoidance_patterns]
    optional_variables: [kb_suggested, style_profile, world_context]
    variable_sources:
      existing_content: current_author_instruction
      kb_suggested: generated_suggestion
      style_profile: project_writing_profile
    security:
      xml_required: [existing_content]
      generated_suggestions_must_be_labelled: [kb_suggested]
    fallback_policy: fail_loudly_if_bundled_missing

  - intent: VOICE
    routeable: false
    rationale: "No dedicated bundled PromptComposer template yet."
```

Platform checker responsibilities:

- Compare manifest routeable entries to `packages/core/narrare_core/prompts/routes.py`.
- Verify bundled EN template paths exist for routeable default routes.
- Verify required/optional variables are registered and classified.
- Verify variables marked `xml_required` are wrapped in explicit XML tags in the
  corresponding template.
- Verify production inline fallback findings are absent for routeable targets.
- Verify new non-routeable intents have a rationale.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | Manifest governs prompt routing only; LLM calls still use approved agent/model paths. |
| RULE-02/02a | ✅ | Manifest distinguishes capability-guaranteed content from customizable feature templates and runtime variables. |
| RULE-03 | ✅ | This ADR defines the cross-module prompt-surface contract before implementation. |
| RULE-04 | ✅ | Manifest and checker are separate artifacts; no monolithic checker expansion is required. |
| RULE-05 | ✅ | Runtime ownership stays in Core; enforcement ownership stays in Platform. |
| RULE-07 | ✅ | Core does not import `scripts/`; Platform inspects Core. |
| RULE-09 | ✅ | Checker/helper APIs require typed signatures. |
| RULE-10 | ✅ | Manifest conformance gets deterministic unit tests and CI coverage. |
| RULE-11 | ✅ | Missing routeable prompts fail loudly; silent fallback is forbidden. |
| RULE-20 | ✅ | P0 manifest/route/security/fallback gates are blockers, not optional cleanups. |
| RULE-22 | ✅ | Variable provenance, context precedence, and routeability are explicit semantic-review inputs. |

---

## Sustainability Check

- **Correct in 3 months:** yes; new intents/templates must enter through the same
  manifest contract.
- **Hard-to-undo coupling:** reduced; runtime code does not depend on Platform,
  while Platform validates the architecture boundary.
- **Simplest correct solution:** yes; a manifest is smaller and clearer than
  encoding semantic policy inside checker heuristics.
- **Design intent clear:** yes; routeability, variables, security, and fallback
  policy are reviewable in one artifact.

---

## Review Trigger

- A new prompt-building mechanism is introduced beyond ADR-026's three mechanisms.
- A new class of LLM operation cannot be represented by the manifest schema.
- Project Writing Profile or multi-step workflow specs add durable context sources
  that require new provenance classes.
- Pydantic-AI changes prompt/capability composition semantics materially.
