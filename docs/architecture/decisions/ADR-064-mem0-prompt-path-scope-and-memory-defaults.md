# ADR-064 — mem0 Extraction Prompts & Default Models: RULE-02b Scope Boundary + Governed Defaults

> **Status:** ✅ Accepted
> **Date:** 2026-07-08
> **Deciders:** Architecture Specialist (review-01 architecture remediation)
> **Supersedes:** —
> **Finding:** review-01-architektur §6 / §7 / `[AUFG-01-02]`

---

## Context

`packages/core/narrare_core/memory/mem0_client.py` (375 lines) holds two module-level
constants that the technical review flagged as a RULE-02/02b "Graubereich" and a
RULE-18b drift risk respectively:

1. **`_WRITING_PREFERENCE_PROMPTS` (lines 43–68)** — language-specific extraction
   instruction strings (`en`/`de`/`fr`). They are passed as
   `config["custom_instructions"]` into `mem0.AsyncMemory.from_config(...)` (line 197).
   mem0 then feeds the string to its *own* internal LLM client to perform memory
   extraction. The string never reaches a Narrare agent, PromptComposer, the route
   table, the variable engine, or any `LLMIntent`.

2. **`_PROVIDER_DEFAULT_MODELS` (lines 28–33)** — a `provider → model_id` map
   (`anthropic→claude-haiku-4-20250414`, `openai→gpt-4.1-nano`,
   `ollama→llama3.2:3b`, `zai→glm-4-flash`) plus `_FALLBACK_MODEL`. These are the
   default *mem0-internal extraction* models, used only when a caller does not pass
   `memory_model=` (line 143: `model = memory_model or _default_memory_model(provider)`).

The review asked two questions:

- **Prompt path:** Are `_WRITING_PREFERENCE_PROMPTS` Narrare prompts subject to
  RULE-02b (and therefore required to live in `core/prompts/`), or are they a
  third-party-library config string outside RULE-02b's scope?
- **Default models:** Do `_PROVIDER_DEFAULT_MODELS` belong in the settings cascade,
  a `core/llm/` default-model table, or do they stay as governed mem0-internal
  defaults?

**Verified facts (graph-first + code read):**

- The RULE-02b checker (`scripts/architecture/_checkers/prompt_path.py`) flags only
  two patterns: `<registry>.resolve(...)` calls and `PromptRegistry` imports outside
  `core/prompts/`. `mem0_client.py` contains **neither** — it is **not** flagged.
  This matches the reviewer's note ("nicht als Verletzung gezählt") and CONSTRAINTS.md
  RULE-02b's enforcement boundary (§"What constitutes a Prompt-Path violation" —
  direct registry access, app-layer loaders, user-channel injection, inline
  production fallbacks, off-scope `MetaPromptLoader`).
- `mem0.AsyncMemory` decides when/how to call its LLM; Narrare passes the
  `custom_instructions` string opaquely as a config dict value. No `{{variable}}`
  substitution, no cascade resolution, no `PromptRegistry` involvement.
- `memory_model` override is honoured at line 143, so RULE-18b's "resolved value
  takes effect" requirement is satisfied for the override path.
- `_PROVIDER_DEFAULT_MODELS` is already admitted by
  `[tool.narrare.architecture.configurable_defaults].allowed_patterns`
  (`_PROVIDER` prefix), so the hardcoded-constants checker already treats it as a
  sanctioned pattern.

---

## Decision Drivers

- **Honesty of the rule register.** The exception register must not register a
  "violation" that the checker does not detect without saying so; equally, prompt-like
  natural-language content living outside `core/prompts/` should not rely on an
  unstated, unanchored assumption.
- **Defensive anchoring against future checker tightening.** A future RULE-02
  extension that scans for natural-language instruction literals outside
  `core/prompts/` would surface `_WRITING_PREFERENCE_PROMPTS` as an *unanchored*
  finding. Pre-emptive registration makes the scope boundary machine-readable and
  growth-controlled.
- **RULE-08 (single mem0 adapter location).** mem0 is confined to
  `core/memory/mem0_client.py`. Default extraction models are an adapter-internal
  concern; relocating them blurs the adapter boundary.
- **RULE-18b lifecycle classification.** Every material configuration value needs
  exactly one classification. These defaults are not user-facing settings.
- **Sustainability.** The decision must hold when a 2nd provider adapter or a 2nd
  memory consumer is added.

---

## Options Considered

### Option A — Migrate `_WRITING_PREFERENCE_PROMPTS` into `core/prompts/_bundled/memory/{locale}/system.md` and resolve via the PromptComposer cascade

**Pros:**
- Maximally consistent with the literal "all prompts live in `core/prompts/`" reading.

**Cons:**
- **Conceptually wrong.** These are not Narrare prompts: they are a config value for
  a third-party library's internal extraction LLM. They are not bound to any
  `LLMIntent`, not split into system/user channels, and never resolved by the
  cascade. Routing them through PromptComposer implies they are a feature prompt
  surface, dragging in manifest registration, route-table entries, intent mapping,
  and variable-engine obligations — machinery that does not fit a single config
  string passed opaquely to `AsyncMemory`.
- Couples a library's internal instructions to Narrare's cascade architecture,
  increasing maintenance for zero functional gain.
- Fails the sustainability check: a 2nd memory consumer using a *different* library
  would need yet another cascade contortion.

### Option B — Register `_WRITING_PREFERENCE_PROMPTS` as a governed RULE-02b exception (scope-boundary clarification)  ✅ CHOSEN

Register a governed exception (`pyproject.toml` + CONSTRAINTS.md §7 mirror +
`ai-gate-baseline.json` ratchet + inline marker) whose reason explicitly states the
*scope boundary*: mem0's `custom_instructions` is a third-party-library config string,
not a Narrare prompt-resolution path.

**Pros:**
- **Honest.** The ADR records that RULE-02b does not strictly apply (the checker
  does not flag it) while still anchoring the boundary machine-readably.
- **Ratcheted.** `check_exception_baseline.py` makes the entry inventory-queryable
  and blocks silent growth (a 2nd such string elsewhere, or replication of the
  pattern, surfaces as a new fingerprint requiring an ADR).
- **Low-cost, reversible.** If mem0 later exposes a Narrare-native extraction path,
  the exception is removed and the prompts migrated — no caller rewrite needed.
- Passes the sustainability check: a 2nd memory consumer re-using mem0 is covered by
  the same exception; a consumer using a different library triggers a fresh decision
  (correct — each library's internal prompts need their own boundary).

**Cons:**
- Registers a RULE-02b entry for a case the checker does not currently flag. The ADR
  text and exception reason mitigate this by framing it explicitly as a scope
  boundary, not a conceded violation.

### Option C — Pure scope-clarifying ADR, no exception entry

Document that RULE-02b does not apply, with no machine anchor.

**Pros:**
- Most minimal; no register inflation.

**Cons:**
- **No enforcement anchor.** A future checker tightening would re-surface the strings
  as unanchored findings; nothing machine-blocks the pattern spreading to other
  `core/memory/` files.
- Weaker than Option B on the "documented ≠ enforced" lesson (architectural-discipline
  §7): a prose-only scope statement is regressable debt.

---

## Decision

**For the prompt strings, we choose Option B: register `_WRITING_PREFERENCE_PROMPTS`
as a governed RULE-02b exception, framed explicitly as a scope-boundary clarification.**

RULE-02b governs the **Narrare prompt-resolution path** (`PromptRegistry.resolve()`,
`PromptComposer.build()`, `_bundled/` loading, `{{variable}}` substitution, cascade
resolution). A config string passed opaquely to a third-party library
(`mem0.AsyncMemory`) that performs its *own* internal LLM calls is **not** a Narrare
prompt-resolution path and is therefore outside RULE-02b's enforcement boundary. The
current `prompt_path.py` checker correctly excludes it. We register the exception
*defensively* to (a) make the boundary machine-readable and auditable, and (b) ratchet
it against silent growth, rather than relying on an unstated assumption.

**For the default models, we choose Option (iii): classify
`_PROVIDER_DEFAULT_MODELS` / `_FALLBACK_MODEL` as RULE-18b `governed_default`s that
stay in `core/memory/mem0_client.py`** (the single mem0 adapter, RULE-08), with an
owner, rationale, and review trigger recorded in the configuration adoption matrix.
They are **not** moved to the settings cascade (they are not user-facing settings;
the `memory_model` override is the user/project surface and is already honoured) and
**not** moved to `core/llm/` (they are mem0-internal extraction models, distinct from
generation models; mixing them blurs the adapter boundary).

---

## Rationale

**Why Option B over A for the prompts.** The PURPOSE of `core/prompts/` is to own the
resolution of *Narrare* prompts — content that flows through Narrare agents and the
cascade, where user overrides, variable substitution, and capability injection must
apply. mem0's `custom_instructions` satisfies none of these: mem0 owns the call,
mem0 owns the model, mem0 owns the substitution. Forcing these strings through the
Narrare cascade would assert a ownership the cascade does not actually have, and would
impose manifest/route-table/variable obligations on a library config value. The
governed-exception approach keeps the conceptual boundary honest (mem0 config ≠
Narrare prompt) while still giving us a ratcheted, auditable anchor — directly
applying the "documented ≠ enforced" lesson by making the boundary both documented
*and* machine-anchored.

**Why governed defaults over settings cascade for the models.** RULE-18 governs
*router* hardcoding; this is `core/`, and the values are adapter-internal fallbacks.
RULE-18b requires that any material configuration value be classified and that
resolved values take effect — both satisfied: the classification is
`governed_default`, and the `memory_model` override demonstrably takes effect at
line 143. Exposing these as user settings would create false-control surface area
(users configuring "mem0's internal extraction model" as if it were a generation
setting). The drift risk the reviewer flagged (model IDs changing, e.g.
`claude-haiku-4` → `claude-haiku-5`) is real but **location-independent** — it is
mitigated by a recorded review trigger ("when provider model IDs change"), not by
relocating the constants.

**Tradeoff accepted:** the RULE-02b exception register gains an entry that the
checker does not currently flag. We accept this because the alternative (Option C,
prose-only) leaves the boundary unanchored, and the register's stated purpose (ADR-028)
is exactly to make approved deviations queryable and growth-controlled.

---

## Consequences

**Positive:**
- The RULE-02b scope boundary ("third-party-library config strings are out of scope")
  is now documented in an ADR and machine-anchored in the exception register.
- `_WRITING_PREFERENCE_PROMPTS` is ratcheted: proliferation triggers a new fingerprint
  → ADR required.
- `_PROVIDER_DEFAULT_MODELS` gets a RULE-18b classification with owner + review
  trigger, closing the "unclassified material configuration value" gap.
- No production code changes required for the decision itself (only config +
  docs + one inline marker).

**Negative / Tradeoffs:**
- The exception register grows by one entry that the checker does not detect; the
  ADR text must be read to understand it is a scope clarification, not a conceded
  violation.
- The governed-default classification for the model IDs does not by itself prevent
  ID drift; it relies on the review trigger being honoured.

**Constraints introduced:**
- RULE-02b (scope clarification): third-party-library config strings fed to a
  library that performs its own internal LLM calls are out of RULE-02b's scope;
  such strings may live in the owning adapter module under a governed exception.
- RULE-18b: `_PROVIDER_DEFAULT_MODELS` is a `governed_default` (owner: mem0 adapter;
  review trigger: provider model-ID change).

---

## RULE-XX Compliance

| Rule | Status | Notes |
|------|--------|-------|
| RULE-02 | ✅ | No f-string/concat prompt assembly; `_WRITING_PREFERENCE_PROMPTS` are static module constants, not assembled prompts. |
| RULE-02a | ✅ | N/A — these are not Narrare prompt content categories (not Capability, not Cascade, not `@agent.instructions`). |
| RULE-02b | ✅ (scope-clarified) | `custom_instructions` is a third-party-library config string, not a Narrare prompt-resolution path; registered as governed exception. |
| RULE-08 | ✅ | mem0 confined to `core/memory/mem0_client.py`; defaults stay in the adapter. |
| RULE-18 | ✅ | Not a router; no router hardcoding. |
| RULE-18b | ✅ | `_PROVIDER_DEFAULT_MODELS` classified `governed_default` with owner + rationale + review trigger; `memory_model` override takes effect (line 143). |
| RULE-23 | ✅ | No type suppressions introduced. |

---

## Implementation Notes

This ADR is a decision + governance-config change. Production code is touched only
for one inline documentation marker (delegated to Core). The exception is
**dual-registered** per ADR-028: `pyproject.toml` (machine SSOT) ↔ CONSTRAINTS.md §7
(human-readable mirror), kept in sync by `check_exception_baseline.py --check-sync`,
and ratcheted by the default-mode baseline gate.

**Exception reason (must be identical across pyproject.toml, CONSTRAINTS.md §7, and
`ai-gate-baseline.json`):**

> `mem0 custom_instructions is a third-party-library config string for mem0's internal extraction LLM, not a Narrare prompt-resolution path (RULE-02b scope boundary).`

The baseline fingerprint is therefore:

> `pyproject | RULE-02b | packages/core/narrare_core/memory/mem0_client.py | mem0 custom_instructions is a third-party-library config string for mem0's internal extraction LLM, not a Narrare prompt-resolution path (RULE-02b scope boundary).`

**ADR Implementation Completeness Gate (Gate 12):** opened — implementation is
deferred to the Core specialist (inline marker) and Platform/governance (matrix row).
See the Implementation Handoff below for the closure path. This ADR is `✅ Accepted`
(decisions in effect); it is **not** `✅ Implemented` until the Phase-D enforcement
ships.

---

## Phase D — Enforcement (closure path to `✅ Resolved`)

The finding (`[AUFG-01-02]`) reaches `✅ Resolved` only with **Implementation +
Enforcement** (finding-lifecycle §2). The enforcement anchors are:

1. **Ratchet gate (this ADR's commit):** `check_exception_baseline.py` (default mode)
   counts the new RULE-02b fingerprint against `ai-gate-baseline.json`. Growth beyond
   this single entry fails the gate until a new ADR/baseline update lands. ✅ wired in
   this commit.
2. **Sync gate (this ADR's commit):** `check_exception_baseline.py --check-sync`
   requires the CONSTRAINTS.md §7 row to match the pyproject.toml entry. ✅ wired in
   this commit.
3. **RULE-18b classification (Core/Platform handoff):** the
   `_PROVIDER_DEFAULT_MODELS` `governed_default` row in the configuration adoption
   matrix, with owner + rationale + review trigger. CI validates matrix
   completeness (ADR-051). ⏳ deferred to specialist.
4. **Regression anchor (Core handoff):** a unit test asserting
   `prompt_path.check_prompt_registry_access(...)` does **not** flag
   `mem0_client.py` (locks the scope boundary against a checker regression). ⏳
   deferred to specialist.

---

## Implementation Handoff (executing specialist: Core, with one Platform step)

**Core specialist:**
1. `packages/core/narrare_core/memory/mem0_client.py` — add an inline documentation
   marker at the `_WRITING_PREFERENCE_PROMPTS` definition (line ~43) and at the
   `custom_instructions` assignment (line ~144/197):
   `# narrare: allow-prompt-path reason="mem0-internal config, not Narrare prompt resolution (ADR-064)"`
   (This is documentation/consistency only — `prompt_path.py` does not flag this file;
   the marker aligns the site with the registered exception per ADR-028.)
2. `tests/unit/core/memory/` (new or existing test) — add a regression test that
   calls `prompt_path.check_prompt_registry_access(rel_path, tree, source_lines)` on
   `mem0_client.py` and asserts it returns `[]` (scope boundary locked).
3. `configuration-adoption-matrix.yaml` (with Platform if schema-owned) — add a
   `governed_default` row for `_PROVIDER_DEFAULT_MODELS`:
   `setting_id`/`file` = `packages/core/narrare_core/memory/mem0_client.py`,
   `classification` = `governed_default`, `owner` = `core/memory (mem0 adapter)`,
   `rationale` = "small/cheap mem0-internal extraction models per provider;
   user-overridable via `memory_model` (honoured at line 143)",
   `review_trigger` = "when a provider's default extraction model ID changes or a
   new provider is added to mem0".

**Exact enforcement the specialist must leave green:**
- `just check-exceptions` (ratchet: 12 current / 12 baseline / 0 new after this ADR's
  baseline line is merged).
- `just check-architecture` (no new violation; the new pyproject entry has no inline
  marker to validate — `_validate_exception_consistency` is one-way).
- `just check` full suite.

**Out of scope for this ADR (other specialists' tasks):** the `intents.py` /
`integration_contracts.py` RULE-04 splits (`[AUFG-01-03]`, `[AUFG-01-05]`) and the
`prompt_loader.py` OSError logging (`[AUFG-01-06]`).

---

## Review Trigger

- [ ] When mem0 exposes a Narrare-native extraction path (agent/composer-based) →
      remove the exception and migrate the prompts into `core/prompts/`.
- [ ] When a second memory consumer using a *different* library is added → make a
      fresh scope-boundary decision for that library's config strings.
- [ ] When `prompt_path.py` (RULE-02b checker) is extended to scan for prompt-like
      literals → re-validate that this exception is still the correct anchor.
- [ ] When a provider's default extraction model ID changes → update
      `_PROVIDER_DEFAULT_MODELS` and the matrix review-trigger evidence.
