# ADR-049 — Prompt-Surface Identity & Path Contract Retrofit (FIND-010 + FIND-011)

> **Status:** ✅ Accepted (contract decisions); implementation deferred to Phase C
> **Date:** 2026-06-18
> **Deciders:** Architecture Specialist
> **Supersedes:** None (retrofits ADR-037 with identity/path invariants; restores ADR-024 routing for CHAT)
> **Resolves:** FIND-010 (Chat Prompt Surface Drift), FIND-011 (Timeline Analysis Inline-Prompt Bypass)
> **Related:** ADR-024, ADR-037, ADR-026, ADR-044, ADR-046, ADR-048, CONSTRAINTS.md RULE-02/02a/02b/03/22

> **Status note (updated 2026-06-25):** When this ADR was written (2026-06-18),
> ADR-048 was `🔄 Proposed`. ADR-048 is now `✅ Accepted` (2026-06-24). The
> §7 principle invoked throughout this ADR — *production code must not rely on a
> not-yet-accepted ADR's contract* — remains valid and was correctly applied to
> FIND-011 (Step 4 removed the Mode 2 reference regardless of ADR-048's later
> acceptance). The inline ADR-048 references below have been updated to reflect
> its current ✅ Accepted status; the original decision (remove the false Mode 2
> declaration — the agent owns no composition) stands regardless. ADR-049 itself
> is now `✅ Implemented` (FIND-010 + FIND-011 resolved). The three FIND-011
> *clone* services that fell outside FIND-011's scope are migrated separately by
> ADR-054.

---

## Context

This ADR retrofits the Prompt-Surface Contract (ADR-037) with two missing
identity/path invariants and migrates one service that bypassed the contract
entirely. Both findings (FIND-010, FIND-011) are different symptoms of the same
underlying weakness: ADR-037 governs *routeability*, *variables*, and *fallback
policy*, but does not enforce that the manifest template path, the route-table
identity, the frontmatter `prompt_type`, and the management prompt-id all refer
to **the same file**.

### FIND-010 — Chat Prompt Surface Drift

**Symptom.** The CHAT intent has two divergent bundled templates and three
layers disagree about which file is canonical:

| Layer | Path it points at | Frontmatter `prompt_type` |
|-------|-------------------|---------------------------|
| `route_table.py:30,53,165` | `_bundled/chat/en/system.md` (category `chat`, mode `""`) | n/a (runtime) |
| `prompt-surface-manifest.yaml:85-89` | `_bundled/writing/en/chat/system.md` (category `chat`, mode `""`) | n/a (governance) |
| `_bundled/chat/en/system.md` (on disk) | itself | `chat` ← **invalid category** |
| `_bundled/writing/en/chat/system.md` (on disk) | itself | `writing` |
| `management.py:77-88` | neither — root-mode paths (`len(parts) < 4`) are silently skipped | n/a |

The result: at runtime the Composer loads `_bundled/chat/en/system.md`
(v1.0.0, 3091 bytes), while the governance manifest, every override, and every
audit trail point at `_bundled/writing/en/chat/system.md` (v1.3.0, 3784 bytes).
The two files have **different content**. The manifest checker's PROMPT-ROUTE
gate passes because manifest and route-table agree on `category="chat"` and
`mode=""` — but neither matches the path the runtime actually loads. The
chat prompt is also invisible in the Prompt Management UI because
`management.py:77` requires `len(parts) >= 4` and the root-mode path has only
three segments.

**Root-cause chain.**

1. **Why do two templates exist?** Because ADR-024 authorised one path and an
   undocumented later change created the other.
2. **Why was the second path created without retiring the first?** Because no
   checker enforces "one routeable intent → one bundled template file", and
   because the route-table change was made without updating ADR-024 or the
   manifest's `template:` field.
3. **Why does the manifest still pass PROMPT-ROUTE?** Because ADR-037's checker
   compares manifest `(category, mode)` to route-table `(category, mode)` but
   never validates that either matches the `template:` path, and never validates
   that the `template:` path's parent directory equals
   `_bundled/{category}/{language}/{mode}/`.
4. **Why does the management layer silently drop CHAT?** Because root-mode
   (`mode=""`) produces a 3-segment path (`chat/en/system.md`) that violates the
   3-segment management-id contract (`{category}/{language}/{mode}`), and the
   file scanner silently filters it out rather than raising.
5. **Design response.** Restore ADR-024 routing as canonical (it was the
   authorised decision and remains semantically correct: CHAT is a writing-craft
   assistant per ADR-024 §Decision 3), forbid root-mode for routeable intents,
   and add four machine-checkable identity invariants that would have caught
   every link in this chain.

**Evidence that the drift contradicts the authorised decision.**
ADR-024 line 593 (Implementation Status): *"Prompt routing: `LLMIntent.CHAT →
category: "writing", mode: "chat"`"*. ADR-024 line 832: *"the file exists at
`core/prompts/_bundled/writing/{lang}/chat/system.md`"*. The route-table drift
to `category="chat", mode=""` was made without an ADR-024 amendment, without a
superseding ADR, and without updating the manifest `template:` field. Per
CONSTRAINTS.md §8 and RULE-21, that change is invalid.

### FIND-011 — Timeline Analysis Inline-Prompt Bypass

**Symptom.** `apps/api/narrare/planning/timeline_analysis_service.py:151-159`
assembles a feature/task prompt via f-string and passes it directly to
`TimelineAgent.run(prompt=...)`:

```python
result = await agent.run(
    prompt=(
        f"Analyze the timeline for '{novel.title}'.\n\n"
        f"Genre: {novel.genre or 'Unspecified'}\n"
        f"Language: {novel.writing_language or 'en'}\n\n"
        f"Chapters:\n{chapter_context}"
    ),
    deps=deps,
)
```

This violates RULE-02 (no f-string prompt assembly outside `core/prompts/`),
RULE-02a category 1 (user-customisable feature content must flow through the
PromptComposer cascade), and RULE-02b violation 3 (feature system content
delivered through the user channel). The service also declares
`_TIMELINE_ANALYSIS_INJECTION` as an "ADR-048 Mode 2 declaration"
(`timeline_analysis_service.py:38-47`) — a premature invocation of ADR-048's
Mode 2 contract (ADR-048 was `🔄 Proposed` when written; it is now ✅ Accepted).
Step 4 removes the reference regardless, because the agent owns no composition
and Mode 2 never applied (see status note).

**Root-cause chain.**

1. **Why is the prompt inline?** Because the service predates the governed
   template for this use-case and nobody migrated it when the prompt-surface
   contract (ADR-037) was introduced.
2. **Why was a ManualInjectionDeclaration added instead of a template?** Because
   ADR-048 Mode 2 was treated as if it were already in effect, and Mode 2 lets a
   service skip PromptComposer composition by declaring that the agent composes
   internally. At the time ADR-048 was `🔄 Proposed`, so the declaration was
   premature (ADR-048 is now ✅ Accepted, 2026-06-24; the declaration remains
   false — the agent composes nothing — and is removed by Step 4).
3. **Why does the PLAN intent not cover this use-case?** Because PLAN's
   `default_mode="outline"` routes to `_bundled/planning/en/outline/system.md`,
   which is for outline/scene-structure generation — a different task than
   chronological timeline extraction from chapter summaries.
4. **Design response.** Timeline analysis is a planning sub-mode, not a new
   domain. PLAN already supports `allowed_context_modes`; the
   `_resolve_context_mode_route()` helper in `routes.py:76-91` already overrides
   the template mode from `context_mode`. Add a `timeline` context-mode to PLAN,
   create the governed template, and route the service through PromptComposer
   (Mode 1) — which also removes the premature ADR-048 Mode 2 reference.

**Evidence correction.** The task brief states that
`_bundled/planning/en/timeline/system.md` "exists, is governed, but is unused
by the runtime". That file does **not** exist. `ls` of
`_bundled/planning/en/` shows only `outline/system.md` and
`temporal_consistency/system.md`. The `temporal_consistency/system.md` template
is for **conflict detection on existing timeline events** (per its first line:
*"identify subtle temporal inconsistencies in timeline events"*), which is a
different task than the service's **timeline generation from chapter
summaries**. FIND-011 therefore requires a new governed template, not the
reuse of an existing one.

---

## Decision Drivers

- **ADR-024 authority.** ADR-024 is the accepted decision for CHAT routing
  (`category="writing", mode="chat"`). The current route-table value is an
  undocumented deviation; RULE-21 (architecture review invalidated by material
  plan changes) makes the deviation invalid until either reverted or
  superseded by a new ADR.
- **ADR-037 scope gap.** The manifest checker validates `(category, mode)`
  parity but not path identity. The same drift will recur for any future
  intent unless path identity is checked.
- **RULE-02 / 02a / 02b.** Feature/task prompts must be built by PromptComposer;
  services may not assemble them via f-string; feature system content must not
  be injected through the user channel.
- **RULE-03.** Contract (Protocol) before implementation. The prompt-surface
  identity contract must be specified before the checkers are written.
- **RULE-22 items 3 and 4.** New prompt modes require (a) a check that no
  existing intent/mode has the same ID with a different semantic scope, and
  (b) registration of new template variables.
- **`prompt-standards.md:42`.** The canonical rule is
  `prompt_type: <category>` where `<category>` is one of
  `writing | kb | analysis | planning | meta | generation | wiki | universal`.
  "chat" is **not** a valid category, which independently confirms the drift.
- **ADR-048 status discipline.** Production code must not depend on a
  not-yet-accepted ADR's contract (a general principle; ADR-048 was `🔄
  Proposed` when this ADR was written and is now ✅ Accepted, 2026-06-24). The
  `_TIMELINE_ANALYSIS_INJECTION` reference to "ADR-048 Mode 2" is removed in
  Step 4 regardless, because the agent owns no composition — Mode 2 never
  applied.
- **ADR-044 status note.** The task brief instructs that ADR-044 be treated as
  Proposed. The ADR file and INDEX mark it "✅ Implemented" with a Gate-12
  checklist dated 2026-06-13. This ADR makes no assumption about ADR-044's
  implementation state: the FIND-011 decision works identically whether
  ADR-044 is Implemented or Proposed, because timeline generation and the
  FactExtractor/Consistency staged pipeline are separate concerns. The
  ADR-044 status discrepancy is flagged for the coordinator in the handoff.

---

## Options Considered

### FIND-010 — Canonical CHAT path

#### Option A — Restore ADR-024 routing (`writing/chat`)

Revert `route_table.py` to `PromptRouteConfig("writing", "chat")`, keep
`_bundled/writing/en/chat/system.md` as canonical, retire
`_bundled/chat/en/system.md`, and leave the manifest unchanged (it already
points at the ADR-024 path).

**Pros:**
- Restores the authorised decision (ADR-024 §Decision 3 + line 593).
- Manifest already correct — zero manifest churn.
- `prompt_type: writing` already matches category `writing` (per
  `prompt-standards.md:42`).
- 3-segment management-id `writing/en/chat` works with `management.py:77`
  out of the box.
- No new abstraction, no root-mode support needed.

**Cons:**
- Reverts a route-table change that someone deliberately made; requires
  documenting why the revert is correct (this ADR serves that purpose).
- "chat" as a standalone category has intuitive appeal (chat is not prose
  generation), but that intuition was never authorised and "chat" is not in
  the valid `prompt_type` enumeration.

#### Option B — Make the drift official (`chat/""` root-mode)

Accept `category="chat", mode=""` as canonical, create a root-mode identity
model so `management.py` can list `chat/en/system.md`, retire
`_bundled/writing/en/chat/system.md`, and amend ADR-024.

**Pros:**
- "chat" as a top-level category matches the mental model of some contributors.
- Makes the current runtime behaviour governance-official.

**Cons:**
- Requires amending or superseding ADR-024 — high ceremony for no architectural
  benefit.
- Requires inventing a root-mode identity model: every layer that assumes
  `{category}/{language}/{mode}` 3-segment ids (`management.py`,
  `composer.py:143` `prompt_id`, cascade paths in `registry.py:155`) must gain
  a special case. Root-mode is a generalisation created to justify one drift.
- `prompt_type: chat` is invalid per `prompt-standards.md:42`; would require
  adding "chat" to the canonical enumeration — a CONSTRAINTS-level change.
- Treats the symptom (no management id for root-mode) as a problem to solve,
  rather than the root cause (root-mode shouldn't exist for routeable intents).

#### Option C — New standalone category `chat` with a non-empty mode

Add `category="chat", mode="default"` (or similar), creating a 4-segment path
`_bundled/chat/en/default/system.md`.

**Pros:**
- Avoids the root-mode problem.
- Gives chat its own category.

**Cons:**
- Same ADR-024 amendment cost as Option B.
- `mode="default"` is meaningless naming — chat has no sub-modes.
- `prompt_type: chat` still invalid per `prompt-standards.md:42`.
- Pure renaming of Option A's outcome with more churn.

**Selection: Option A.** It is the only option that respects the authorised
decision (ADR-024), requires no new abstraction, and needs no CONSTRAINTS
enumeration change. Options B and C both require amending ADR-024 and adding
"chat" to the canonical `prompt_type` list to justify a category split that
ADR-024 explicitly rejected (ADR-024 §Decision 3 places chat under `writing`).

### FIND-011 — Timeline analysis prompt path

#### Option 1 — New intent `LLMIntent.PLAN_TIMELINE`

Add a new intent with `category="planning", mode="timeline"`, a manifest entry,
a route-table row, and a new template. The service calls
`composer.build(LLMIntent.PLAN_TIMELINE, ctx)`.

**Pros:**
- Maximally explicit; each planning sub-task is its own surface.
- Straightforward management-id `planning/en/timeline`.

**Cons:**
- **Contradicts the PLAN intent's own documentation.** `intents.py:267-269`
  states: *"NOT: Timeline analysis (no dedicated intent — uses PLAN)."* Adding
  `PLAN_TIMELINE` silently invalidates that docstring.
- Adds ceremony (new enum member, new route, new manifest entry, new
  model-routing classification) for a use-case that PLAN's
  `allowed_context_modes` mechanism was built to handle.
- Creates a precedent that every planning sub-task becomes its own intent,
  inflating the intent enum.

#### Option 2 — PLAN + `context_mode="timeline"` (chosen)

Add `"timeline"` to PLAN's `allowed_context_modes`, create the governed
template `_bundled/planning/en/timeline/system.md`, and have the service call
`composer.build(LLMIntent.PLAN, ctx_with_mode="timeline")`. The existing
`_resolve_context_mode_route()` helper (`routes.py:76-91`) already overrides
the template mode from `context_mode`, so no runtime change is needed beyond
the route-table addition and the new template.

**Pros:**
- **Honours the PLAN intent's documentation.** `intents.py:267-269` says
  timeline analysis "uses PLAN" — this option makes that statement true.
- **Reuses existing infrastructure.** `allowed_context_modes` and
  `_resolve_context_mode_route()` already exist and already handle
  `temporal_consistency` the same way.
- **RULE-02 compliant.** The service delegates to PromptComposer; no f-string.
- **Removes the premature ADR-048 Mode 2 reference.** The service becomes
  Mode 1 (composer-driven); `_TIMELINE_ANALYSIS_INJECTION` is deleted.
- **ADR-044-independent.** Works whether ADR-044 is Implemented or Proposed.
- **Extensible.** Future planning sub-modes (e.g. `story_structure`,
  `character_arc`) follow the same pattern without new intents.

**Cons:**
- Requires extending the manifest schema to model `context_modes` per intent,
  because ADR-037's manifest has one template per intent and PLAN currently
  declares only `outline`. This is a backward-compatible extension (entries
  without `context_modes` keep using the top-level template).
- `context_mode` overriding the template mode is a subtle behaviour that must
  be documented (it already works; this ADR makes it governed).

#### Option 3 — Mark template non-routeable + `@agent.instructions`

Keep the timeline logic inside the agent via ADR-026's dynamic-instruction
mechanism (`@agent.instructions` or `Capability.for_run()`), mark any template
non-routeable, and do not route through PromptComposer.

**Pros:**
- Minimal route-table churn.

**Cons:**
- **Violates RULE-02a category 1.** The current inline prompt contains a
  feature/task instruction ("Analyze the timeline for …"), which is
  user-customisable content that MUST flow through the PromptComposer cascade.
  `@agent.instructions` is reserved for dynamic per-invocation data
  (RULE-02a category 3: KB data, style profiles), not for feature task framing.
- **Wastes the existing `temporal_consistency` governed template.** Marking
  planning templates non-routeable orphans governed content.
- **Does not fix the RULE-02 violation.** The f-string would move from the
  service into the agent, but it would still be f-string assembly of feature
  content outside `core/prompts/`.
- **Rejected** because it trades one RULE-02 violation for another.

**Selection: Option 2.** It is the only option that is simultaneously
RULE-02-compliant, consistent with the PLAN intent's own documentation,
reusable for future planning sub-modes, and independent of ADR-044/048 status.

---

## Decision

### FIND-010 — Restore ADR-024 CHAT routing + add four identity invariants

**D1. Canonical CHAT path is `_bundled/writing/en/chat/system.md`.** This is
the ADR-024-authorised path. The route table reverts to
`PromptRouteConfig("writing", "chat")`.

**D2. Retire the orphan duplicate.** `_bundled/chat/en/system.md` and the
`_bundled/chat/` directory are deleted in Phase C. They are not loaded by the
Composer after D1 takes effect and are not referenced by any manifest entry.

**D3. Root-mode is forbidden for routeable intents.** No routeable
`PromptRouteConfig` may have `default_mode=""` (empty string). Root-mode breaks
the 3-segment management-id contract, the `composer.py:143` `prompt_id`, and
the cascade path derivation in `registry.py:155`. The only legitimate
root-mode-style intents are aggregate flows (`KB_CREATE`, `EXTRACT`) which use
`default_mode=None` and `fallback_policy: raise_route_not_configured` — those
are exempt because they never resolve a template.

**D4. Manifest template path must be derivable from category/mode/language.**
For every routeable manifest entry, the declared `template:` path MUST equal
`packages/core/narrare_core/prompts/_bundled/{category}/{language}/{mode}/system.md`.
This is the path identity invariant. It catches FIND-010-class drift
automatically.

**D5. Frontmatter `prompt_type` must equal the manifest category.** Every
bundled template's frontmatter `prompt_type` MUST equal the `category` of the
manifest entry that governs it, and MUST be one of the canonical categories in
`prompt-standards.md:42` (`writing | kb | analysis | planning | meta |
generation | wiki | universal`).

**D6. Management-id derivability.** Every routeable manifest entry's
`(category, language, mode)` MUST produce a 3-segment management-id
`{category}/{language}/{mode}` that `management.py` can list. This is implied
by D3 (no root-mode) and D4 (path derivability) but stated explicitly because
`management.py:77`'s silent skip is what hid FIND-010 from the UI.

### FIND-011 — PLAN `context_mode="timeline"` + governed template + Mode 1

**D7. Add `"timeline"` to PLAN's `allowed_context_modes`.** PLAN's route
config becomes
`PromptRouteConfig("planning", "outline", allowed_context_modes=frozenset({"outline", "temporal_consistency", "timeline"}))`.
This is a route-table-only change; `_resolve_context_mode_route()` already
handles the template-mode override.

**D8. Create governed template `_bundled/planning/en/timeline/system.md`.**
Phase C creates this template with frontmatter
`prompt_type: planning, prompt_language: en, prompt_version: "1.0.0"` and the
variables the service currently inlines: `{{project_title}}`, `{{genre}}`,
`{{writing_language}}`, `{{chapter_summaries}}` (all already registered in
`SYSTEM_VARS`). The template body encodes the task framing currently in the
f-string ("Analyse the timeline … produce chronological events, conflicts,
coverage gaps").

**D9. Migrate `timeline_analysis_service.py` to Mode 1 (composer-driven).**
The service calls
`composer.build(LLMIntent.PLAN, ctx_with_mode="timeline", user_prompt=chapter_context_user_message)`
and passes `composed.system` as the agent's system prompt and `composed.user`
(or the chapter summaries) as the run prompt. The f-string feature framing is
removed from the service.

**D10. Remove the false ADR-048 Mode 2 reference.**
`_TIMELINE_ANALYSIS_INJECTION` and its `manual_injection=` kwarg are deleted
from the service. (ADR-048 was `🔄 Proposed` when this was written; it is now
✅ Accepted, 2026-06-24.) The removal stands regardless: the declaration was
false — the agent composes nothing, so Mode 2 never applied. A service that
genuinely needs Mode 2 must register a *truthful* declaration at that time;
no declaration may retroactively justify a RULE-02 bypass.

**D11. Manifest schema extension: optional `context_modes` list.** ADR-037's
manifest schema is extended with an optional `context_modes:` list per entry.
Each list item declares `{mode, template, content_type, required_variables,
optional_variables, security, fallback_policy}`. Entries without
`context_modes` are unchanged (the top-level template applies to all
context-modes). Phase C adds `context_modes` to the PLAN entry covering
`outline`, `temporal_consistency`, and `timeline`. KB_WORLDBUILD has the same
shape (`worldbuilding/phase1` default + `worldbuilding/phase2` context-mode)
and should be retrofitted in a follow-up — out of scope for this ADR.

---

## Rationale

### Why restore ADR-024 instead of ratifying the drift (FIND-010)

ADR-024 is the accepted SSOT for CHAT routing. The route-table change to
`category="chat", mode=""` was made without an amendment, a superseding ADR,
or a CONSTRAINTS update — it is precisely the "material plan change without
re-review" that RULE-21 forbids. Ratifying it now (Option B/C) would require
amending ADR-024, adding "chat" to the canonical `prompt_type` enumeration
(a CONSTRAINTS §1 change), and inventing a root-mode identity model — all to
preserve an unauthorised change. Restoring ADR-024 is cheaper, correct, and
eliminates the root-mode problem entirely rather than papering over it.

### Why context-mode over a new intent (FIND-011)

The PLAN intent's own docstring (`intents.py:267-269`) explicitly states that
timeline analysis "uses PLAN". The `allowed_context_modes` mechanism and the
`_resolve_context_mode_route()` helper already exist and already serve
`temporal_consistency` for PLAN. Option 2 honours the intent's documentation,
reuses existing infrastructure, and avoids enum inflation. Option 1
(`PLAN_TIMELINE`) would require updating the PLAN docstring to remove the
"uses PLAN" note — a silent documentation invalidation. Option 3
(non-routeable + `@agent.instructions`) would trade a service-level RULE-02
violation for an agent-level RULE-02a violation, because feature/task framing
is category-1 content that must flow through PromptComposer.

### Why the four identity invariants (D3–D6)

FIND-010 survived every existing checker because each checker validates one
slice (route-table vs manifest category/mode; template variable registration;
XML wrapping) but no checker validates that all slices refer to the same file.
D3–D6 close that gap by making path identity, frontmatter identity, and
management-id derivability first-class checked invariants. They are all
mechanical, deterministic, and cheap to check.

---

## Consequences

**Positive:**
- FIND-010 resolved: one canonical CHAT template, manifest-route-runtime
  agreement, chat visible in the Prompt Management UI.
- FIND-011 resolved: timeline analysis is RULE-02-compliant, governed, and
  uses Mode 1 (no premature ADR-048 dependency).
- Four new machine-checkable invariants (D3–D6) prevent FIND-010-class drift
  for every future intent.
- PLAN's `context_modes` pattern is reusable for future planning sub-modes
  without intent-enum inflation.
- ADR-024 routing authority restored; RULE-21 discipline reinforced.

**Negative / Trade-offs:**
- Phase C must delete `_bundled/chat/` and create
  `_bundled/planning/en/timeline/system.md` — small, well-scoped work.
- The manifest schema gains an optional `context_modes` field; the manifest
  checker must be extended to validate context-mode entries (Phase D).
- KB_WORLDBUILD has the same one-template-per-intent manifest gap and is not
  retrofitted by this ADR; it is flagged as a follow-up.
- The `_TIMELINE_ANALYSIS_INJECTION` removal means the service no longer
  declares its variables via `ManualInjectionDeclaration`. This is correct
  (Mode 1 does not need it) but means the adoption registry loses one
  declared exception — which is the desired outcome.

**Constraints introduced:**
- **RULE-02/02a/02b:** reinforced. Timeline service is now cascade-compliant.
- **RULE-03:** the prompt-surface identity contract (D3–D6) is specified in
  this ADR before the Phase D checkers are written.
- **RULE-22 items 3/4:** the new `timeline` context-mode is checked for
  semantic overlap (none — `outline` = structure, `temporal_consistency` =
  conflict detection on existing events, `timeline` = generation from chapter
  summaries) and its variables are all pre-registered.
- **ADR-037:** retrofitted with identity invariants D3–D6 and the
  `context_modes` schema extension D11.

---

## Retrofit Plan (D.4 mandatory — prompt-mechanics ADR)

This ADR changes prompt route identity, adds a routeable context-mode, and
extends the manifest schema. Per
`.opencode/context/narrare-dev/processes/adr-process.md` §D.4, a Retrofit Plan
is mandatory.

### 1. Inventory of affected paths

| Path | Symbol | Current state | Action |
|------|--------|---------------|--------|
| `packages/core/narrare_core/prompts/route_table.py:30` | `INTENT_TO_CATEGORY[CHAT]` | `"chat"` | → `"writing"` |
| `packages/core/narrare_core/prompts/route_table.py:53` | `INTENT_TO_MODE[CHAT]` | `""` | → `"chat"` |
| `packages/core/narrare_core/prompts/route_table.py:165` | `ROUTE_CONFIGS[CHAT]` | `PromptRouteConfig("chat", "")` | → `PromptRouteConfig("writing", "chat")` |
| `packages/core/narrare_core/prompts/route_table.py:141` | `ROUTE_CONFIGS[PLAN].allowed_context_modes` | `{"outline", "temporal_consistency"}` | → add `"timeline"` |
| `packages/core/narrare_core/prompts/_bundled/chat/en/system.md` | orphan duplicate | loaded by runtime (drift) | DELETE (Phase C) |
| `packages/core/narrare_core/prompts/_bundled/chat/` | directory | orphan | DELETE if empty (Phase C) |
| `packages/core/narrare_core/prompts/_bundled/writing/en/chat/system.md` | ADR-024 canonical | governance-only (drift) | becomes runtime canonical |
| `packages/core/narrare_core/prompts/_bundled/planning/en/timeline/system.md` | n/a | does not exist | CREATE (Phase C) |
| `scripts/architecture/prompt-surface-manifest.yaml:85-97` | CHAT entry | `template:` already correct; `category/mode` drift | `category: writing, mode: chat` (Phase C) |
| `scripts/architecture/prompt-surface-manifest.yaml:289-301` | PLAN entry | single template | add `context_modes:` list (Phase C) |
| `apps/api/narrare/planning/timeline_analysis_service.py:38-47` | `_TIMELINE_ANALYSIS_INJECTION` | premature ADR-048 Mode 2 | DELETE (Phase C) |
| `apps/api/narrare/planning/timeline_analysis_service.py:117-159` | `generate_timeline` body | f-string prompt + manual_injection | rewrite to Mode 1 (Phase C) |

### 2. Migration steps per path (ordered, atomic, independently testable)

**Step 1 (Core, FIND-010, CI-safe):** Update `route_table.py` — CHAT reverts
to `writing/chat` in all three dicts; PLAN gains `"timeline"` in
`allowed_context_modes`. After this step the Composer loads
`_bundled/writing/en/chat/system.md` (which exists) for CHAT, and the
`chat/` orphan is no longer reachable. CI-safe because the ADR-024 template
exists and the manifest's CHAT `template:` already points at it.

**Step 2 (Core, FIND-010, CI-safe):** Delete `_bundled/chat/en/system.md` and
the `_bundled/chat/` directory. Safe after Step 1 because nothing loads it.

**Step 3 (Core, FIND-011):** Create `_bundled/planning/en/timeline/system.md`
with the frontmatter and variables specified in D8. Until Step 4, this
template is orphan (not loaded); that is acceptable for an atomic slice.

**Step 4 (Backend, FIND-011):** Rewrite `timeline_analysis_service.py` to
Mode 1: inject `PromptComposer`, build a `PromptContext` with
`mode="timeline"`, call `composer.build(LLMIntent.PLAN, ctx)`, pass
`composed.system` to the agent and `composed.user` (or chapter summaries) as
the run prompt. Delete `_TIMELINE_ANALYSIS_INJECTION` and the
`manual_injection=` kwarg. After this step the service is RULE-02-compliant
and no longer references ADR-048 Mode 2.

**Step 5 (Platform, manifest):** Update `prompt-surface-manifest.yaml` —
CHAT entry `category: writing, mode: chat`; PLAN entry gains a
`context_modes:` list with `outline`, `temporal_consistency`, `timeline`
sub-entries (each pointing at its template). Backward-compatible: entries
without `context_modes` are unchanged.

**Step 6 (Platform, checkers):** Implement the Phase D checkers (see
"Checker Acceptance Criteria" below).

### 3. Breaking-change assessment

- **CHAT route revert (Step 1):** No external API change. The Composer's
  output for CHAT changes from the v1.0.0 `chat/en/system.md` content to the
  v1.3.0 `writing/en/chat/system.md` content — the latter is the
  ADR-024-authorised, more complete prompt. Any project-level override at
  `.narrare/prompts/chat/en/system.md` (root-mode) would have been silently
  broken already (management.py never listed it); after Step 1 the correct
  override path is `.narrare/prompts/writing/en/chat/system.md`.
- **PLAN `context_mode="timeline"` (Step 4):** The `generate_timeline` service
  signature is unchanged externally; only its internal prompt construction
  changes. `TimelineAgent` continues to accept `prompt: str` — it now receives
  `composed.user` instead of the f-string.
- **`_TIMELINE_ANALYSIS_INJECTION` removal (Step 4):** The
  `ManualInjectionDeclaration` is deleted from the service. If any test
  asserts its presence, that test must be updated. No production caller
  depends on the declaration object.
- **Manifest `context_modes` extension (Step 5):** Additive; the checker must
  handle both old-style (no `context_modes`) and new-style entries.

### 4. Checker update plan

| Checker module | Change | New baseline |
|----------------|--------|--------------|
| `scripts/architecture/_checkers/_check_prompt_surface.py` | Add PROMPT-IDENTITY gate (D4 path derivability, D5 frontmatter match, D6 management-id derivability) | No new debt — all current entries must pass |
| `scripts/architecture/_checkers/_check_prompt_surface.py` | Add PROMPT-ROOT-MODE gate (D3: no routeable intent with `default_mode=""`) | No new debt — CHAT fix removes the only violator |
| `scripts/architecture/_checkers/_check_prompt_surface.py` | Add PROMPT-CONTEXT-MODES gate (D11: validate `context_modes` entries; each context-mode template must exist and match its declared category) | No new debt — PLAN is the first entry to use it |
| `scripts/architecture/_checkers/_check_prompt_path.py` (ADR-046) | Add INLINE-FEATURE-PROMPT gate (A5: service-layer f-string feature/task prompts to `agent.run(prompt=...)` are forbidden when a governed template exists for the intent) | Ratchet from current state; timeline service is the first migration |
| `scripts/architecture/_checkers/_check_prompt_surface.py` | Add ORPHAN-TEMPLATE gate (A6: every `system.md` under `_bundled/` must be reachable by a manifest entry or explicitly exempted) | Ratchet; `_bundled/chat/` deletion removes the current orphan |

### 5. Test update plan

- `tests/unit/core/prompts/test_composer.py:128-146` — the
  `@pytest.mark.parametrize("intent", sorted(_INTENT_TO_MODE, key=str))` test
  iterates intents and asserts category/mode. After Step 1, CHAT's expected
  values change to `category="writing", mode="chat"`. Update the parametrized
  expectations (the test already covers CHAT via the parametrize).
- `tests/unit/core/llm/test_generation_intents.py` — asserts
  `_INTENT_TO_CATEGORY` / `_INTENT_TO_MODE` mappings; CHAT entry must be
  updated to the reverted values.
- `tests/unit/architecture/test_prompt_surface_checker.py` — add cases for
  PROMPT-IDENTITY, PROMPT-ROOT-MODE, PROMPT-CONTEXT-MODES, ORPHAN-TEMPLATE.
- `tests/unit/api/planning/test_timeline_analysis_service.py` — rewrite to
  assert `composer.build(LLMIntent.PLAN, ctx_with_mode="timeline")` is called
  and that no `manual_injection=` is passed. Assert the agent receives
  `composed.user`, not an f-string.
- `tests/unit/core/prompts/test_management.py` — add a case asserting CHAT
  appears in `list_prompts()` with id `writing/en/chat` (it currently does
  not appear at all, which is the FIND-010 management symptom).

---

## Checker Acceptance Criteria (Phase D)

The Phase D (Platform) checkers must satisfy the following acceptance criteria.
Each criterion is phrased as a test the checker must pass.

### A1 — Prompt-Surface Identity E2E

For every routeable manifest entry, the checker asserts the full identity
chain:

1. `manifest.template` exists on disk.
2. `manifest.template` path equals
   `_bundled/{manifest.category}/{lang}/{manifest.mode}/system.md` for at
   least one declared language (D4).
3. `route_table[intent].category == manifest.category` AND
   `route_table[intent].default_mode == manifest.mode` (existing PROMPT-ROUTE,
   retained).
4. The template's frontmatter `prompt_type == manifest.category` (D5).
5. The management-id `{manifest.category}/{lang}/{manifest.mode}` is
   list-able by `management.py` (i.e., 3 non-empty segments — D6).
6. The Composer, when called with `(intent, context.mode=manifest.mode)`,
   resolves to `manifest.template` (path-identity end-to-end).

**Acceptance:** A1 fails if any link breaks. After FIND-010 fix, CHAT passes
all six links.

### A2 — Root-Mode Prohibition (D3)

No routeable `PromptRouteConfig` has `default_mode == ""` (empty string).
Aggregate flows use `default_mode = None` with
`fallback_policy: raise_route_not_configured` and are exempt.

**Acceptance:** A2 fails on any routeable intent with `default_mode == ""`.
After FIND-010 fix, no routeable intent violates A2.

### A3 — Manifest-Template Path Derivability (D4)

For every routeable manifest entry with a non-null `template`, the template
path's parent directory (relative to `_bundled/`) equals
`{category}/{lang}/{mode}` for the declared `language` (default `en`), or —
when `context_modes` is declared — equals
`{category}/{lang}/{context_mode.mode}` for each context-mode entry.

**Acceptance:** A3 fails if a manifest entry's `template:` points outside its
`{category}/{lang}/{mode}/` directory. This is the invariant that would have
caught FIND-010.

### A4 — Frontmatter Category Match (D5)

Every bundled `system.md` loaded by a manifest entry has frontmatter
`prompt_type` equal to the manifest entry's `category`, and `prompt_type` is
in the canonical enumeration (`writing | kb | analysis | planning | meta |
generation | wiki | universal`).

**Acceptance:** A4 fails on any `prompt_type` mismatch or any non-canonical
value (e.g. `prompt_type: chat`).

### A5 — Inline Feature-Prompt Gate (FIND-011 prevention)

No service-layer file (`apps/api/**/*.py`) may pass an f-string or string
concatenation containing feature/task framing (imperatives like "Analyse",
"Generate", "Summarise", role descriptions, or task instructions) to
`agent.run(prompt=...)` or `agent.run_stream(prompt=...)` when a governed
template exists for the call's intent. Runtime data (chapter text, user
message text, extracted entities) MAY be passed as the run prompt — only
feature/task framing is forbidden.

**Detection heuristic:** flag `agent.run(prompt=f"...")` and
`agent.run(prompt="..." + ...)` call sites where the f-string/concatenation
contains feature-framing verbs or role/task nouns AND the intent has a
routeable manifest entry. Pure-runtime-data prompts (e.g.
`agent.run(prompt=chapter.text)`) are allowed.

**Acceptance:** A5 flags `timeline_analysis_service.py` before the Phase C
migration and passes after it. The ratchet baseline is set post-migration.

### A6 — Orphan Template Check (D2 + D11)

Every `system.md` under `_bundled/{category}/{lang}/{mode}/` must be reachable
by either:
- a manifest entry whose `(category, mode)` matches, OR
- a manifest `context_modes` sub-entry whose `mode` matches, OR
- an explicit exemption list (for capability-loaded templates like
  `meta/`, `universal/`, `wiki/` that are not routeable but are loaded by
  Capabilities per ADR-026).

**Acceptance:** A6 flags `_bundled/chat/en/system.md` before deletion and
passes after. Capability-loaded templates (`meta/`, `universal/`, `wiki/`)
are listed in a documented exemption table.

---

## Regression Test Requirements (for Phase C and Phase D)

These are acceptance criteria for the implementation phases, not tests this
architecture phase writes.

### Core (Phase C)
- `tests/unit/core/prompts/test_composer.py` — CHAT composes from
  `_bundled/writing/en/chat/system.md`; the composed system prompt contains
  the v1.3.0 content, not the v1.0.0 content.
- `tests/unit/core/prompts/test_management.py` — `list_prompts(category="writing")`
  includes `writing/en/chat` with `has_override` check working.
- `tests/unit/core/prompts/test_routes.py` —
  `resolve_prompt_route(LLMIntent.PLAN, context_mode="timeline")` returns
  `PromptRoute(category="planning", mode="timeline")` and resolves to
  `_bundled/planning/en/timeline/system.md`.
- `tests/unit/core/prompts/test_route_table.py` — no routeable intent has
  `default_mode == ""` (A2).

### Backend (Phase C)
- `tests/unit/api/planning/test_timeline_analysis_service.py` — service calls
  `composer.build(LLMIntent.PLAN, ctx_with_mode="timeline")`; agent receives
  `composed.user` as the run prompt; no `manual_injection=` kwarg; no f-string
  feature framing in the call site.
- `tests/integration/planning/test_timeline_analysis_endpoint.py` —
  end-to-end timeline generation still returns
  `{timeline_events, temporal_conflicts, coverage_gaps, overall_assessment}`
  with the same shape (the migration must not change the response schema).

### Platform (Phase D)
- `tests/unit/architecture/test_prompt_surface_checker.py` — cases for
  PROMPT-IDENTITY (A1), PROMPT-ROOT-MODE (A2), PROMPT-PATH-DERIVABILITY (A3),
  PROMPT-FRONTMATTER-MATCH (A4), ORPHAN-TEMPLATE (A6).
- `tests/unit/architecture/test_prompt_path_checker.py` — case for
  INLINE-FEATURE-PROMPT (A5): a synthetic service file with an f-string
  feature prompt to `agent.run(prompt=...)` is flagged; a pure-runtime-data
  prompt is not.

---

## Implementation Notes

### Manifest schema extension (D11)

```yaml
- intent: PLAN
  routeable: true
  category: planning
  mode: outline                      # default mode (context_mode="" uses this)
  template: packages/core/narrare_core/prompts/_bundled/planning/en/outline/system.md
  content_type: customizable_feature_prompt
  # ... existing fields ...
  context_modes:                     # OPTIONAL — new in ADR-049
    - mode: outline
      template: packages/core/narrare_core/prompts/_bundled/planning/en/outline/system.md
      content_type: customizable_feature_prompt
      required_variables: []
      optional_variables: []
      security: {xml_required: [], generated_suggestions_must_be_labelled: []}
      fallback_policy: fail_loudly_if_bundled_missing
    - mode: temporal_consistency
      template: packages/core/narrare_core/prompts/_bundled/planning/en/temporal_consistency/system.md
      content_type: customizable_feature_prompt
      required_variables: []
      optional_variables: [project_title, genre, writing_language]
      security: {xml_required: [], generated_suggestions_must_be_labelled: []}
      fallback_policy: fail_loudly_if_bundled_missing
    - mode: timeline
      template: packages/core/narrare_core/prompts/_bundled/planning/en/timeline/system.md
      content_type: customizable_feature_prompt
      required_variables: [chapter_summaries]
      optional_variables: [project_title, genre, writing_language]
      security: {xml_required: [], generated_suggestions_must_be_labelled: []}
      fallback_policy: fail_loudly_if_bundled_missing
```

Entries without `context_modes` are unchanged: the top-level `template` applies
to all context-modes, and the existing PROMPT-ROUTE gate validates the default
mode. The new PROMPT-CONTEXT-MODES gate validates each `context_modes`
sub-entry the same way.

### Timeline template requirements (D8, for Phase C)

`_bundled/planning/en/timeline/system.md` frontmatter:

```yaml
---
prompt_type: planning
prompt_language: en
prompt_version: "1.0.0"
---
```

Body must encode the task framing the service currently inlines:

- Role: temporal-analysis specialist for narrative fiction.
- Task: produce a chronological timeline from chapter summaries — extract
  events, order them, detect temporal conflicts and coverage gaps, and
  summarise overall assessment.
- Variables: `{{project_title}}`, `{{genre}}`, `{{writing_language}}`,
  `{{chapter_summaries}}` (all registered in `SYSTEM_VARS`).
- Output contract: the agent's `TimelineOutput` schema (events, conflicts,
  gaps, assessment) — already enforced by `TimelineAgent._validate_output`.

The chapter summaries themselves are runtime data (category-3 per RULE-02a)
and are passed as the run prompt (`composed.user`), not baked into the
template.

### Route-table changes (this phase applies Step 1)

This phase applies Step 1 of the Retrofit Plan (route-table only) because it
is CI-safe and makes the governance contract concrete. Steps 2–6 are Phase C.

### ADR-044 status discrepancy (flagged for coordinator)

The task brief states ADR-044 is "Proposed — do not treat as implemented".
The ADR-044 file and `INDEX.md` both mark it "✅ Implemented" with a Gate-12
checklist dated 2026-06-13 and per-slice validation notes. This ADR makes no
assumption about ADR-044's true state: FIND-011's decision is identical
either way. The coordinator should reconcile the ADR-044 status (either
confirm Implemented and update the task brief, or investigate the Gate-12
claims and downgrade if warranted). This is a documentation-governance issue,
not an architecture-decision issue.

### ADR-048 Mode 2 reference (resolved)

`timeline_analysis_service.py:38` referenced "ADR-048 Mode 2" for
`_TIMELINE_ANALYSIS_INJECTION`. (ADR-048 was `🔄 Proposed` when this ADR was
written; it is now ✅ Accepted, 2026-06-24.) Step 4 of the Retrofit Plan
removed the reference regardless, because the declaration was false — the
agent owns no composition, so Mode 2 never applied. Three further clone
services with the same false declaration (character_arc, timeline_extraction,
kb/merge) are migrated to Mode 1 by ADR-054.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | No agent/model import changes; TimelineAgent usage unchanged. |
| RULE-02 | ✅ | FIND-011 migration moves feature-prompt assembly from service f-string to PromptComposer. |
| RULE-02a | ✅ | Timeline task framing (category-1 content) flows through cascade; chapter summaries (category-3) stay as run-prompt data. |
| RULE-02b | ✅ | Timeline service no longer uses `manual_injection=` (ADR-048 Mode 2 bypass); resolution path is PromptComposer only. |
| RULE-03 | ✅ | Identity invariants D3–D6 and manifest schema D11 are specified in this ADR before Phase D checkers. |
| RULE-04 | ✅ | No file exceeds limits; route-table edits are configuration, not logic. |
| RULE-05 | ✅ | Route-table, manifest, and templates stay in their owned modules; no cross-domain `_internal` imports. |
| RULE-06 | ✅ | Each file keeps one responsibility; timeline service remains a service, composer remains the composer. |
| RULE-07 | ✅ | Core owns route-table/templates/manifest schema; Platform owns checkers. No Core→apps imports. |
| RULE-09 | ✅ | No new public APIs; existing typed signatures preserved. |
| RULE-10 | ✅ | Regression tests specified per layer (Core, Backend, Platform). |
| RULE-11 | ✅ | Root-mode and orphan templates fail loudly via checkers; no silent skips. |
| RULE-20 | ✅ | No half-implementation: governance contract (this ADR) and implementation (Phase C) are both fully specified. |
| RULE-21 | ✅ | This ADR documents the material change (CHAT routing revert) and re-reviews it; no silent plan change. |
| RULE-22 | ✅ | New `timeline` context-mode checked for semantic overlap (none); variables pre-registered in `SYSTEM_VARS`. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. The four identity invariants (D3–D6) make
   FIND-010-class drift impossible for any future intent. The `context_modes`
   pattern (D11) scales to any planning/KB sub-mode without intent-enum
   inflation.
2. **Hard-to-undo coupling?** No. The route-table revert restores ADR-024
   exactly. The manifest `context_modes` extension is additive and
   backward-compatible. The timeline template is a standard governed
   template, removable without architectural impact.
3. **Simplest correct solution?** Yes. FIND-010's simplest correct fix is to
   restore the authorised routing rather than invent a root-mode identity
   model. FIND-011's simplest correct fix is the existing `context_mode`
   mechanism rather than a new intent or a capability bypass.
4. **Design intent clear?** Yes. The identity invariants are named (D3–D6),
   checkable (A1–A6), and motivated by a concrete drift case (FIND-010). The
   `context_modes` schema is documented with a worked example (PLAN).

---

## Review Trigger

- [ ] When a second intent needs the `context_modes` manifest pattern beyond
      PLAN and KB_WORLDBUILD — audit whether the schema scales or needs
      generalisation.
- [x] **(Triggered 2026-06-24 — ADR-048 ✅ Accepted.)** Audited services that
  removed `ManualInjectionDeclaration` references (this ADR's Step 4): the
  timeline service correctly stays Mode 1 (the agent composes nothing). The
  three FIND-011 clones (character_arc, timeline_extraction, kb/merge) are
  migrated to Mode 1 by ADR-054 — none re-adopts Mode 2, because none of their
  agents owns composition.
- [ ] When ADR-024 is next amended — ensure the CHAT routing decision (D1)
      is carried forward or explicitly superseded.
- [ ] When a new `prompt_type` value is proposed — update
  `prompt-standards.md:42` and A4's canonical enumeration together.
- [ ] After 3 months — audit whether any routeable intent has accumulated a
      root-mode or path-identity violation (the checkers should prevent this,
      but a manual audit confirms the checkers are running in CI).

---

## ADR Implementation Completeness Gate (Gate 12)

This ADR is **Accepted** for its contract decisions (D1–D11). Implementation
is deferred to Phase C (Steps 1–5 of the Retrofit Plan) and Phase D (checkers
A1–A6). The ADR will be marked "✅ Implemented" only when:

- [ ] Step 1 applied: route-table CHAT reverted; PLAN `allowed_context_modes`
      extended.
- [ ] Step 2 applied: `_bundled/chat/` deleted.
- [ ] Step 3 applied: `_bundled/planning/en/timeline/system.md` created.
- [ ] Step 4 applied: `timeline_analysis_service.py` migrated to Mode 1;
      `_TIMELINE_ANALYSIS_INJECTION` deleted.
- [ ] Step 5 applied: manifest CHAT entry corrected; PLAN `context_modes`
      added.
- [ ] Phase D checkers A1–A6 implemented and passing in CI.
- [ ] All regression tests in "Regression Test Requirements" pass.
- [ ] No workarounds or shortcuts in any step.
