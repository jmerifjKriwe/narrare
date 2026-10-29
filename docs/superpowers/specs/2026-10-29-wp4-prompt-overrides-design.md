# WP4 — Prompt overrides (design)

> **Date:** 2026-10-29
> **Status:** draft v2 — awaiting owner approval
> **Surface decisions (owner):** docking B for `writing.continuation`;
> own `prompts` capability; one prompts page with novel filter; all four
> task keys overridable.
> **Builder-check decisions (owner, 2026-10-29):** machine markers are
> kernel variables plus a save-time contract check (1b); a template that
> cannot be honored at call time is refused by name, never cut or
> silently swapped (2a); `chat.ask` has no novel scope — `novel_id` is
> rejected for it and the page hides the novel scope (3a).
> **References:** Fahrplan §7 (`docs/superpowers/plans/2026-10-25-v2-foundation.md`),
> WP2b budget guarantee (spec: the allocator is the one context authority),
> ADR-102 (the pattern for a settings-like surface over kernel machinery).

## Intent

A user can replace the text of any bundled prompt — per novel or globally —
validated at save time, proven in the audit, without breaking the WP2b
guarantee that no context slice ever overflows. Why: writers want the machine
to speak in *their* instruction, not ours; today the instruction is code.

## Goals

- Override the four bundled task prompts — `writing.continuation`,
  `chat.ask`, `knowledge.extract-entities`, `knowledge.check-consistency` —
  as Jinja templates, novel-scoped or user-global (novel scope where the
  task has one).
- Resolution: novel-specific row → user-global row → bundled template.
- Save-time validation: a `PUT` renders with sample variables and runs the
  key's contract checks; a template that fails (syntax, unknown variable,
  include cycle, depth, missing machine marker) is refused with 422 and the
  named reason. A broken override never reaches a model call.
- Audit proof: `LlmCall.prompt_text` carries the rendered override; the E2E
  asserts it (Fahrplan §7.5).
- `{% include 'prompt.key' %}` through the registry loader, depth limit 5,
  cycle detection.
- The allocator guarantees survive: what enters a prompt (selection, cuts,
  machine markers) stays kernel-owned; slices never overflow.

## Non-goals

- File-based overrides (Fahrplan §11 "Prompt file overrides, Phase B").
- Prompt versioning or history beyond `created_at`/`updated_at`.
- User-invented new prompt keys: the overridable set is exactly the four
  bundled keys (closed set).
- Novel scoping for chat retrieval (builder-check Q3: a product change of
  its own, not part of WP4).
- Localizing prompt content: overrides are user content; only the UI chrome
  is en/de/fr.

## Anti-goals

- A central template list: bundled templates register from the owning
  capability's `prompts.py` at import time, the way routers mount.
- Any override path that can make a slice overflow silently, or that swaps
  in the bundled text while the UI shows an override as active.

## Constraints

- Jinja `SandboxedEnvironment` + `StrictUndefined`, no autoescape.
- Keys contain dots and are ordinary path segments.
- No capability imports another: the `prompts` capability reaches bundled
  content only through the kernel registry.
- `user_id` on every user-owned row; side effects only inside the request's
  transaction.
- Governance budget unchanged (spec §8).

## Approaches considered

### Where an override of `writing.continuation` docks

The continuation prompt is budget-aware packing, not text with holes: four
allocator slices (`immediate_text`, `referenced_entities`,
`recent_chapters`, `style_hints`), entity degradation, silent section
omission — and the budget is known only at call time (resolved profile →
context window). Three dockings:

- **A — whole prompt.** The template owns everything; maximal freedom. The
  kernel learns the template's contribution only after rendering; the
  never-overflow guarantee dies. Rejected.
- **B — kernel packs, template arranges.** The kernel passes pre-packed
  section strings as variables; the template owns order, glue and
  instruction; the frame's length is measured and charged to
  `immediate_text`. Guarantees survive per slice. Chosen.
- **C — named slots only.** The override replaces the instruction (maybe
  headings); too thin — it cannot reorder or revoice the prompt, and is too
  thin for the three simple prompts anyway.

For the other three prompts the template is the whole prompt over
kernel-fed variables (selection, cuts and machine markers stay
kernel-side: passage list with its `SOURCE:` prefixes, the `PURPOSE:` line,
`body[:BODY_LIMIT]`). Same principle as B: **the kernel owns what enters,
the template owns how it reads.**

### Where the surface lives

- **Own `prompts` capability** (chosen): router + service + one web page;
  keys span three capabilities, `settings` stays provider-themed. Mounting
  is convention (`router.py` found automatically, `capability.yaml`
  registered).
- In `settings`: no new folder, but settings would carry writing/chat/
  knowledge prompt text — the wrong owner.

### UI scope

One `PromptsPage` with a novel filter covers both scopes at one address
(chosen); embedding editing per novel would need a second place for the
global scope. `chat.ask` is global-only on that page (builder-check 3a).

### Keys in scope

All four (chosen): one mechanism, and the §7.4 smoke snapshots cover every
bundled prompt anyway.

## The design

### Kernel: `app/kernel/prompts/`

- `PromptRegistry`: `register(key, template, sample_vars, *, contract,
  novel_scopable)` called at import time from the owning capability's
  `prompts.py`; no central list. Each registration carries the bundled
  template string (Jinja), a sample-variable factory (save-time validation,
  smoke tests, the editor's variable legend), an optional contract
  predicate over the rendered sample, and whether the key may carry a
  novel scope.
- Jinja environment: `SandboxedEnvironment`, `StrictUndefined`, no
  autoescape. The environment's loader resolves
  `{% include 'prompt.key' %}` through the **effective** chain
  (novel row → user-global row → bundled) for the rendering's novel scope;
  depth limit 5; cycle detection via the render-time include stack.
- `render(session, user_id, key, variables, *, novel_id=None)` — resolves,
  renders, returns the text; on any failure raises `PromptRenderError`
  with a named reason (see runtime policy). Callers: the four prompt call
  sites and the save-time validation.
- The model and repository live here too (`PromptTemplate`,
  `PromptTemplateRepository`) — the `ProviderProfile` precedent: kernel
  machinery under `kernel/`, the user-facing surface as a capability on
  top.

### Machine markers and the save-time contract (builder-check 1b)

The fake provider — the default tier, not only a test device — parses
`PURPOSE:` and `SOURCE:` lines out of the prompt to choose its answer
shape; the structured parser expects them. These markers are therefore
**kernel-fed variables** (`purpose_line`, passages already prefixed), not
template prose. A template may still drop them, so each marker-bearing key
registers a **contract**: the rendered sample must contain the marker (the
knowledge keys their `PURPOSE:` line, `chat.ask` the `SOURCE:` prefixes).
`PUT` runs sample render + contract and refuses with 422 and the named
failed check. `writing.continuation` carries no contract (its fake answer
is free text).

### Runtime policy (builder-check 2a)

A saved-valid template can still fail at call time: a runtime budget too
small for its frame, an else-branch StrictUndefined gap, an include chain
broken by a later save of the included key. **Every such failure is a
named refusal** — `PromptRenderError` with the reason — mapped like
`BudgetImpossibleError` today: the continuation's error frame, a failed
knowledge job row, chat's error frame. No silent fallback to the bundled
template; no post-render mangling; no eager re-validation graph of include
dependents (the call-time refusal covers them; `PUT` validates the saved
key at sample scope, includes included).

### Budget mechanism for `writing.continuation` (the B docking)

- The kernel packs `entities_section`, `predecessors_section`,
  `style_section` exactly as today, each within its slice, headings
  included; a zero/undersized slice omits its section whole.
- The template receives them as opaque strings plus `novel_title`,
  `chapter_title`, `tail` (the chapter tail) and owns the frame: header,
  glue, instruction.
- Two-pass render: pass 1 renders with the full remaining tail as a probe;
  the kernel measures the frame (rendered total minus tail minus sections)
  and re-cuts the tail to `immediate_text − frame`; pass 2 renders final.
  If pass 2 still does not fit — a template whose glue grows when the tail
  shrinks — at most one more pass; a frame that keeps growing after the
  bounded passes is the named refusal above (`PromptRenderError`, budget
  reason), never a cut. Sections are never cut; a stable frame that
  exceeds a degenerate window ships with an empty tail — today's scaffold
  floor, with only cuttable content obeying the slices.

### Data model

```
PromptTemplate
  id, user_id, novel_id?, prompt_key, content,
  created_at, updated_at
```

Kernel-owned (above). Global rows (`novel_id IS NULL`) are unique per
`(user_id, prompt_key)` via a partial unique index (`postgresql_where`,
the `ProviderProfile.is_default` pattern); novel rows unique per
`(user_id, novel_id, prompt_key)`. `prompt_key` validates against the
registry's closed key set; a `novel_id` on a key registered
`novel_scopable=False` (today only `chat.ask`) is 422, named.

### API (`app/capabilities/prompts/router.py`)

- `GET /prompts?novel_id=` — the four keys: bundled summary, override
  presence per scope (global / this novel), `scopes` the key allows.
- `GET /prompts/{key}?novel_id=` — bundled content, the variable legend
  (from the sample factory), and the effective override content for that
  scope.
- `PUT /prompts/{key}` — body: `content`, optional `novel_id`; renders the
  sample and runs the contract; 422 with the named reason on failure.
- `DELETE /prompts/{key}?novel_id=` — resets that scope's row to bundled.
- `GET /prompts/{key}/diff?novel_id=` — raw `bundled_content` +
  `override_content`; the frontend renders the diff.

### Call-site integration (the four sites stay owners of their variables)

- `app/capabilities/writing/service.py:170` — packs sections, calls
  `render(...)` with the two-pass flow.
- `app/capabilities/chat/service.py:26` — builds question + prefixed
  passages, calls `render(...)`; no novel scope.
- `app/capabilities/knowledge/jobs.py:318,478` — extraction and
  consistency likewise, with their `PURPOSE:` line as a variable.

Bundled prompt functions become Jinja template constants + sample-var
factories in each `prompts.py`, registered at import.

### Frontend (`app/capabilities/prompts/web/`)

`PromptsPage`: novel filter; per key a card with **two scope chips —
Global / Dieser Roman** (the novel chip only for keys that allow it). An
empty novel scope shows "erbt: <global state>" and an explicit create
action that opens the editor prefilled with the effective text — saving
never silently forks a scope. `DELETE` acts on the scope named on the
chip. Editor shows the variable legend, save-time 422 reasons, reset, and
a diff view (client-side, dependency-free, side-by-side). i18n en/de/fr
for chrome only.

### Interchange archive

Overrides do **not** ride the archive: they are user configuration, like
provider profiles, not novel content. The format's closed file set is
unchanged; an import-side test asserts a novel with stored overrides
round-trips byte-identically with none exported.

### Verification (Fahrplan §12 unchanged, plus the new gates)

- §7.4 smoke: every bundled prompt renders with its sample variables,
  snapshot-compared.
- §7.5 E2E: override `writing.continuation` → run a continuation →
  `LlmCall.prompt_text` contains the override; reset → bundled back; broken
  template → 422 at save.
- Builder-check gates: an override dropping a machine marker is 422 at
  save (contract); a template that cannot fit its runtime budget is a
  named refusal at call time (continuation error frame / failed job row /
  chat error frame); `PUT` with `novel_id` on `chat.ask` is 422; the
  archive round-trip ignores stored overrides.
- `just check` per commit; `just verify` + the capability E2E to close.

## My calls (settled here, flagged for owner review)

1. Kernel owns `PromptTemplate`, the repository and `render` — the
   `ProviderProfile` precedent; the capability stays a thin surface.
2. The two-scope-chip page contract: explicit create-from-effective, no
   silent forking; delete acts on the named scope.
3. Overrides stay out of the interchange archive.
4. `GET` responses carry the `variables` legend from the sample factory,
   so the editor cannot drift from reality.
5. `{% include %}` resolves through the effective chain, not bundled-only —
   one place to override a key, includes follow; broken chains are covered
   by the call-time refusal.
6. Closed key set: no user-invented keys.
7. Global uniqueness via partial index, mirroring `is_default`.
8. Diff computed client-side, no new dependency.

## Left to the builder

- Exact template variable names per prompt (kept close to today's function
  parameters).
- The `PromptRenderError` reason vocabulary (render / budget / include
  depth / cycle), mirroring the existing error-frame naming style.
- Editor/diff component structure within the existing web patterns.
- Test file layout; where the smoke snapshots live.
