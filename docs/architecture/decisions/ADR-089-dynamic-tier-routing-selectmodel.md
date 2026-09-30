# ADR-089 — Dynamic Tier Routing Pilot: per-step CHAT → ANALYSE escalation via the pydantic-ai `SelectModel` capability

> **Status:** 🔄 Proposed — binding design for Tasks 7–8 of the
> pydantic-ai 2.52 upgrade plan (feature F3). Flips to ✅ when Task 8 lands
> (Gate 12: wired, tested, consumed, documented).
> **Date:** 2026-09-30
> **Deciders:** Architecture Agent; binding user decisions 2026-09-30
> (escalation target = `LLMIntent.ANALYSE`; escape hatch pre-authorized, §Escape Hatch)
> **Supersedes:** none
> **Related:** ADR-001 (single Gateway / `ModelRegistry`), ADR-015 (agents
> first-class, RULE-01b), ADR-071 (`CoreSettings`), ADR-072 (adoption
> strategy — per-capability decisions), ADR-086 (lazy model resolution —
> the first-use seam this feature builds on)
> **Amendment (2026-09-30, Task 6 review follow-up):** Decision 3 clarified —
> sequence-prompt text extraction (single-space join), `None`-prompt
> length-trigger semantics, and the repo-path base for Narrare-side
> citations — plus Decision 7's observability event pinned to the
> `Model` ABC surface. See the amendment notes under Decisions 3 and 7.

---

## Context

### The gap

Narrare resolves one model per `LLMIntent` through the user-config cascade
(`ModelRoutingResolver`: project_intent → project_category → user_intent →
user_category → user_default → `ConfigurationError`), with `INTENT_PROFILES`
as an advisory tier table. The resolution is **per conversation-agnostic**:
a chat turn gets the same model whether the user sends "ok, weiter" (turn 9)
or a 4,000-character passage asking for structural critique. The result is
an unavoidable either/or: operators pick a cheap-but-shallow default and lose
quality on heavy turns, or a capable-but-expensive default and pay it on
every turn.

**Root cause (2× Why):**
1. *Symptom:* one static model per intent regardless of per-turn complexity.
2. *Why?* Resolution happens once per conversation at the cascade level;
   there is no per-request decision point.
3. *Why is that the actual cause?* The model is injected as a frozen value
   (`PreparedModelCall.model` → `ChatAgent(model=...)`) and pydantic-ai
   historically offered no sanctioned hook between "run starts" and "model
   request is built". As of 2.52 that hook exists
   (`SelectModel`, verified below) — the defect is now addressable at the
   framework level instead of by wrapping models ourselves.

### Plan mandate and pinning requirement

This ADR is Task 6 of the pydantic-ai 2.52 upgrade plan (feature F3) and
**must precede implementation** (Tasks 7–8). The plan directed that the
design be pinned against the *installed* pydantic-ai 2.52 source so every
API claim in this ADR is verified, not recalled. The pinning produced one
material correction to the plan's working assumption — recorded immediately
below, because Tasks 7–8 consume it.

---

## Verified upstream API (pydantic-ai-slim 2.52.0, installed 2026-09-30)

Installed package: `.venv/lib/python3.14/site-packages/pydantic_ai_slim-2.52.0.dist-info/METADATA`
→ `Version: 2.52.0`. All paths below are relative to
`.venv/lib/python3.14/site-packages/`.

**Correction to the plan's assumption:** there is **no `SelectModel` in
`pydantic_ai.models`** (verified: `from pydantic_ai.models import SelectModel`
→ `ImportError`; no top-level export either). `SelectModel` in 2.52 is a
**capability**, not a `Model` wrapper:

**`SelectModel`** — `pydantic_ai/capabilities/select_model.py:10-26`
(verbatim):

```python
@dataclass
class SelectModel(AbstractCapability[AgentDepsT]):
    """Select a model before each logical model request step.

    The selector receives a [`ModelSelectionContext`][pydantic_ai.models.ModelSelectionContext]
    containing the run dependencies, message history, accumulated usage, and lower-precedence
    model. It may be synchronous or asynchronous and return either a model instance or model ID.
    """

    selector: ModelSelector[AgentDepsT]

    def get_model(self) -> ModelSelector[AgentDepsT]:
        return self.selector

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None
```

Public import: `from pydantic_ai.capabilities import SelectModel`
(`capabilities/__init__.py:57` import, `:146` `__all__`).

**Callback type aliases** — `pydantic_ai/capabilities/abstract.py:78-85`
(verbatim):

```python
ModelSelection: TypeAlias = 'Model | KnownModelName | str'
"""A concrete model selection, before model ID resolution."""

ModelSelector: TypeAlias = 'Callable[[ModelSelectionContext[AgentDepsT]], ModelSelection | Awaitable[ModelSelection]]'
"""A sync or async per-step model selector."""

AgentModel: TypeAlias = 'ModelSelection | ModelSelector[AgentDepsT]'
"""A static model selection or a callable evaluated for every request step."""
```

**`ModelSelectionContext`** — `pydantic_ai/models/__init__.py:373-407`
(frozen dataclass, `kw_only`; also re-exported from top-level `pydantic_ai`,
`__init__.py:144`). Constructor surface and the fields our policy consumes:

```python
@dataclass(frozen=True, kw_only=True)
class ModelSelectionContext(ModelResolutionContext[ModelContextDepsT]):
    """Context used by a capability to select the model for a request step."""

    model: Model | None
    """The lower-precedence model on the first step, then the model used for the previous step."""

    run_step: int
    """The request step being selected, starting at `1`."""

    prompt: str | Sequence[UserContent] | None = None
    """The run's user prompt, as [`RunContext.prompt`][pydantic_ai.tools.RunContext.prompt] holds it. …"""

    messages: list[ModelMessage]
    """The messages the selected model will be sent for this step, ending with the request
    being routed. … This is what [`RunContext.messages`][pydantic_ai.tools.RunContext.messages]
    holds for the step, minus what is only added once the model is selected: the request's
    [`instructions`][pydantic_ai.messages.ModelRequest.instructions] and, on a fresh run's
    first step, its system prompt parts. …"""

    usage: RunUsage
```

(`ModelResolutionContext`, `models/__init__.py:358-370`, adds `agent` and
`deps`.)

**Evaluation semantics** (verified at source):

| Fact | Where (installed source) |
|---|---|
| Step 1: selector evaluated at run preparation with `run_step=1`, the constructor default model as lower-precedence `model`, and `messages`/`prompt` built by `first_step_selection_messages` | `agent/__init__.py:1578-1594` |
| Steps ≥ 2: `_select_model` re-evaluates the selector after `run_step += 1`, guarded once per step by `model_selected_for_step` | `_agent_graph.py:1670-1672`, `:2600-2622` |
| Selector may be sync or async; a returned `str`/known name is resolved, a `Model` instance is used as-is | `agent/__init__.py:3108-3123` (`_evaluate_model_contribution`) |
| Explicit run-time `model=` or `override(model=...)` is **authoritative** — capability model contributions are ignored (`model_is_explicit = model is not None or self._override_model.get() is not None`) | `agent/__init__.py:1553-1556`, `:1900-1901` |
| With multiple model-contributing capabilities, the **last non-`None` selection wins** | `abstract.py:542-554` (`get_model` docstring) |
| Every selected `Model` instance is entered **once per run** on a shared `AsyncExitStack` (keyed by `id()`) | `agent/__init__.py:4263-4279` (`_RunModelResources.enter_model`) |
| Resuming a **suspended** `ModelResponse` with a dynamic selector raises `UserError` | `agent/__init__.py:3125-3142` (`_check_dynamic_model_resume`) |

For the chat path this means: **exactly one selector evaluation per
`run_stream()` call** (chat agents are single-step — no tool loop), seeing
the `ProcessHistory` message history plus the new user prompt.

---

## Decision Drivers

- **Gateway mediation (RULE-01b):** models come from `ModelRegistry`
  provider factories only; no provider SDK imports, no ad-hoc model
  construction. Tier switching is wiring, not a new model source.
- **Credential safety (ADR-071/ADR-001):** per-user `api_key`/`base_url`
  flow exclusively through the existing resolution → factory path; the
  per-request callback must never touch factories, env, or DB.
- **Determinism and cost (RULE-20):** the routing decision itself must not
  add an LLM call, latency, or non-determinism to every chat turn.
- **Opt-in, zero-default impact (ADR-088 activation-ladder precedent):**
  static routing is the shipped, reviewed behavior; a pilot may not change
  it for anyone who did not ask.
- **Never hard-fail chat:** an opt-in optimization must not turn a working
  conversation into a 500; degradation is loud (explicit warning) but
  non-fatal (RULE-11 — warning, not silence).
- **Contract-first (RULE-03):** the policy is a pure, tested function
  before it is wired anywhere.
- **Upstream over in-house:** prefer maintained pydantic-ai mechanics to
  hand-rolled wrappers (ADR-072 theme).

---

## Options Considered

### Option 0 — Upstream `SelectModel` capability (chosen)

Attach a `pydantic_ai.capabilities.SelectModel` capability whose selector
picks, per request step, between two eagerly-constructed `Model` instances
(base = the resolved CHAT model; escalation = the resolved `ANALYSE` model)
using a deterministic size/turn policy.

**Pros:** the selection mechanics (per-step hook, model lifecycle, context
copying, precedence) are maintained upstream; composes with
`ModelRegistry`-built `Model` instances without subclassing anything;
selector stays pure and unit-testable; off-flag path is byte-identical to
today (capability simply not attached).

**Cons:** capability (not `Model`) wiring means the attach point is agent
construction (`ChatAgent`), a seam that currently lacks a `capabilities`
passthrough (small Task 7 addition); run-level `ModelSettings` remain
base-composed in v1 (accepted trade-off, see Decision 4).

### Option (a) — LLM-judge router (rejected)

A small model classifies turn complexity first, then routes.

**Rejected:** adds one LLM round-trip of latency and cost to *every* turn
(the exact cost the feature tries to reduce); non-deterministic; needs its
own evaluation harness before it can be trusted; strictly more moving parts
for a pilot.

### Option (b) — Custom `Model` wrapper (rejected as primary; pre-authorized escape hatch)

Subclass/wrap `Model` so the wrapper dispatches internally.

**Rejected as primary:** reimplements maintained upstream logic
(request-step detection, lifecycle, context construction) inside Narrare;
every pydantic-ai release risks breaking the wrapper's assumptions.
**Pre-authorized as fallback** — see §Escape Hatch.

### Option (c) — Always-capable model (status quo) (rejected)

Route CHAT to a strong model unconditionally.

**Rejected:** no saving — the defect this feature targets is exactly the
flat cost of the capable tier on trivial turns; the status quo is the
baseline the pilot measures against, not a fix.

### Option (d) — Per-user DB-configured tier ladder (rejected for pilot)

Store a per-user (base, escalation) model pair plus thresholds in settings,
with UI.

**Rejected:** needs a settings surface + migration + UI before any signal
exists; violates the pilot's minimalness. The `ANALYSE` cascade route
already *is* user-configurable per intent, which gives us the ladder
without a new surface (binding user decision 2026-09-30).

---

## Decision

**We choose Option 0** — an opt-in dynamic tier routing pilot on the
upstream `SelectModel` capability — in seven binding decisions:

### 1. Gateway mediation (RULE-01b): `core/llm/dynamic_tiering.py`

All tier-selection logic lives in one new Core module,
`packages/core/narrare_core/llm/dynamic_tiering.py`, with this binding
surface:

- `should_escalate(*, latest_user_prompt: str | None, turn_count: int, policy: TieringPolicy) -> bool`
  — **pure** policy function, no I/O, no logging (callers log).
- `TieringPolicy` — frozen dataclass with `max_prompt_chars: int` and
  `min_turns: int`.
- `build_tiered_model(base_model: Model, escalation_model: Model | None, *, policy: TieringPolicy) -> SelectModel`
  — the wiring factory. It constructs the `SelectModel` capability whose
  selector closes over **two eagerly-constructed `Model` instances** and
  the policy — nothing else. `escalation_model=None` (degraded mode) yields
  a capability that always selects `base_model`, so the call site stays
  branch-free.

Both `Model` instances are built **through
`ModelRegistry.get_model` (provider registry factories)** with the per-user
`api_key`/`base_url` resolved by the routing cascade and **closed over at
construction time**. The selection callback itself never touches
factories, environment variables, or the database (credential safety,
ADR-071/ADR-001). Importing `SelectModel`/`ModelSelectionContext` *types*
in `core/llm/` is RULE-01b-clean (the rule restricts `Agent` construction
and provider SDK imports; `gateway.py` already imports upstream types).

The name `build_tiered_model` predates the pinning (the plan assumed a
`Model` wrapper); the verified 2.52 surface makes it a capability factory.
**Name retained, return type pinned to `SelectModel`** — Tasks 7–8 use this
signature.

### 2. Static routing stays the default

`INTENT_PROFILES` (advisory tiers), the `ModelRoutingResolver` cascade, and
every existing consumer are **untouched**. Dynamic selection is opt-in via
a new `CoreSettings` field (ADR-071 pattern, incl. `validation_alias` +
`populate_by_name`):

- `llm_dynamic_tiering_enabled: bool = Field(default=False, validation_alias="NARRARE_LLM_DYNAMIC_TIERING")`
- `llm_dynamic_tiering_max_prompt_chars: int = Field(default=2000, validation_alias="NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS")`
- `llm_dynamic_tiering_min_turns: int = Field(default=6, validation_alias="NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS")`

Default `False` → the capability is not constructed, no second cascade
runs, behavior is byte-identical to today (mirrors the ADR-088 default-off
activation ladder).

### 3. Escalation policy v1 is deterministic — no LLM in the routing path

Escalate when **`len(latest_user_prompt) > max_prompt_chars`** (default
2000) **OR `turn_count >= min_turns`** (default 6). Both thresholds are
operator-tunable via the env vars above (pilot evaluation knobs; RULE-18b:
each must demonstrably reach its runtime consumer — see Test Contract).

Binding definitions (both derived from `ModelSelectionContext`, both
deterministic):

- **`latest_user_prompt`** — `ctx.prompt` when it is a `str` (the chat path
  always passes `composed.user` as a string; note context blocks from
  NOTES-001 §6b are legitimately part of the effective prompt length).
  When `ctx.prompt` is `None` (history-only resume) fall back to the
  concatenated text parts of the last `ModelRequest` in `ctx.messages`;
  non-text content contributes 0.
- **`turn_count`** — the number of `ModelRequest` entries in
  `ctx.messages`. In the tool-free chat path this equals the number of
  user turns including the one being routed (verified semantics: the
  current request is present; system prompt and instructions of the
  current request are added only after selection, so they never inflate
  the count). With the default `min_turns=6`, turn 6 onward escalates.

Amendment notes (2026-09-30, Task 6 review follow-up):

- When `ctx.prompt` is a `Sequence[UserContent]`, `latest_user_prompt`
  takes the text-bearing items — plain strings and `TextContent` parts —
  and joins them with a single space (multi-modal items and cache
  points contribute nothing).
- When no prompt text exists at all (`ctx.prompt` is `None` and the
  last-`ModelRequest` fallback yields no text parts either), the length
  trigger is **false** — only `turn_count` can escalate.
- Narrare-side file citations in this ADR are repo-relative:
  LLM-module paths (`gateway.py`, `_providers/cache_settings.py`) are
  relative to `packages/core/narrare_core/llm/`, other core paths
  (`agents/base.py`, `shared/errors.py`) to `packages/core/narrare_core/`,
  and backend paths (`chat/dependencies.py`) to `apps/api/narrare/`.

### 4. Escalation target: `LLMIntent.ANALYSE` through the existing cascade

The escalation model is resolved **through the existing
`ModelRoutingResolver` cascade with `LLMIntent.ANALYSE`** — an existing,
user-configurable reasoning-tier route (`INTENT_PROFILES`:
`("balanced", "reasoning")`). No new settings surface (binding user
decision 2026-09-30); users steer the escalation tier exactly the way they
steer every other intent today.

Run-level `ModelSettings` and usage limits stay **base-composed**, exactly
as today (`registry.prepare(..., intent=LLMIntent.CHAT, ...)` +
`resolve_chat_run_limits`): v1 escalates the **model instance only**.
Accepted edge case, documented: when the base config enables Anthropic
prompt caching, the base-composed `cache_control: True` key may ride along
to a non-Anthropic escalation model (providers read only the keys they
know — benign no-op, verified: only `build_model_settings("anthropic", …)`
emits a key at all, `_providers/cache_settings.py`). The intent-aware
`thinking` key is provider-universal by design
(`_model_settings.py:48-54`). Per-tier settings composition is a Review
Trigger, not v1.

### 5. Graceful degradation — the pilot must never hard-fail chat

The escalation resolution is consumed at first use, inside
`try/except ConfigurationError` (the cascade's documented "no provider
configured" signal, `shared/errors.py:167`): log one structured **warning**
(`dynamic_tier_degraded`) and continue with `escalation_model=None` →
always base. This is RULE-11-compliant degradation — explicit warning, not
silence — for an opt-in feature. The **base** cascade keeps its ADR-086
semantics untouched: `ConfigurationError` propagates loudly as the
pre-header 400. A selector-side exception cannot occur by construction
(the selector is pure); if a bug makes it raise, it propagates (no swallow
— that would be the actual RULE-11 violation).

### 6. Pilot scope: the `ChatService` path only

`apps/api/narrare/chat/` (`dependencies.py` → `ChatService` →
`_agent_stream.stream_agent_response`). No other service, agent, or
endpoint is wired. Widening is a Review Trigger decision backed by pilot
data, not a default.

### 7. Wiring, lifecycle, and upstream invariants (binding for Tasks 7–8)

- **Wiring seam (ADR-086 same-seam rule):** the tiered model is built at
  **first use**. `chat/dependencies.py` wires a second
  `LazyModelResolution(lambda: resolver.resolve(LLMIntent.ANALYSE,
  UUID(user_id), None))` alongside the existing CHAT resolution (same
  resolver instance, same user, no project tier — chat has no novel path
  parameter). `ChatService` consumes it idempotently in
  `ensure_resolved()` (flag on: resolve escalation inside the
  `try/except ConfigurationError`; flag off: nothing happens). When
  tiering is active, `_agent_stream` builds the escalation `Model` via
  `registry.get_model(escalation_config, api_key=…, base_url=…)` (settings
  stay base-composed per Decision 4) and attaches
  `build_tiered_model(...)` to the per-turn `ChatAgent`.
- **`ChatAgent` gains a `capabilities: list[Any] | None = None` keyword**
  forwarded to `NarrareAgent.__init__`, which already merges extra
  capabilities with the always-injected `NarrareObservability` /
  `NarrareUniversalRules` / `NarrareMeta` (`agents/base.py:85-148`).
  Verified: none of the always-injected capabilities contributes a model
  (no `get_model` in `narrare_core/agents/capabilities/`), so with
  "last non-`None` wins" our `SelectModel` is the sole model contributor.
- **The capability is authoritative only without run-time model
  overrides** (verified `model_is_explicit`): the chat path must keep
  passing the base model at `ChatAgent` construction and must not pass
  `model=` to `run_stream` (current shape — keep it; upstream ignores
  capability selections otherwise).
- **Lifecycle:** every selected `Model` is entered once per run on a
  shared `AsyncExitStack` (upstream); registry-built provider models
  satisfy this as `Model` subclasses. Eager construction + per-turn
  selection is safe.
- **Suspended responses:** upstream rejects resuming a *suspended*
  `ModelResponse` with a dynamic selector (`UserError`). Chat never
  suspends responses (plain `run_stream`); if a future chat feature adds
  suspension, that path must pass `model=` explicitly. Out of pilot scope,
  documented here so it cannot surprise anyone.

**Observability:** the selector's wiring logs one structured
`dynamic_tier_escalation` event per escalated turn (`reason` ∈
{`prompt_chars`, `min_turns`}, `prompt_chars`, `turn_count`, both
thresholds, base/escalation provider+model ids) — the pilot's evaluation
signal; no message content is logged.

Amendment note (2026-09-30, implementation pin): the per-turn event
carries the model ids via `Model.model_name`; provider attribution stays
with the Task 8 wiring layer, which holds the `ResolvedModelConfig`s —
the pydantic-ai `Model` ABC exposes no provider name (verified against
2.52).

---

## Rationale

The defect is the absence of a per-request decision point; 2.52 ships that
decision point as a maintained capability. Using it means Narrare owns only
what is genuinely product policy — *when* to escalate and *to which route* —
while request-step detection, context construction, model lifecycle, and
precedence stay upstream. Every alternative either pays the cost it aims to
save (a, c), re-implements the framework (b), or drags in a settings surface
before there is data to justify one (d).

Escalating to the `ANALYSE` cascade route is the pivotal simplification:
the escalation target inherits user configurability, credentials,
provider plumbing, and governance for free, and remains steerable per user
and per project without a single new setting. The deterministic policy
trades optimality for auditability — appropriate for a pilot whose job is
to generate the evidence a smarter policy would need.

The conscious trade-offs: settings stay base-composed in v1 (per-tier
settings need a second per-step capability — deferred); a single global
policy serves all users initially; and the escalation model is constructed
even for conversations that never escalate (flag on), which costs one
object construction per conversation, not per turn — negligible relative
to an LLM call.

---

## Consequences

**Positive:**

- Opt-in cost/quality lever on the highest-volume conversational path with
  zero impact when off (default) and no new user-facing surface.
- Escalation tier is user-steerable through existing per-intent routing.
- A pure, deterministic policy function that is trivially testable and
  cheap to replace once pilot data exists.
- Upstream-maintained selection mechanics; no `Model` subclass in
  Narrare; RULE-01b boundary unchanged.

**Negative / Trade-offs:**

- `ChatAgent` constructor grows a passthrough parameter (Task 7).
- With the flag on, every conversation constructs a second `Model` at
  first use even if it never escalates.
- Base-composed `ModelSettings` apply to the escalation model (Decision 4
  edge case — benign no-op cache key; per-tier settings deferred).
- The thresholds are global, not per-user (pilot decision; option (d) is
  the escalation path if data demands it).

**Constraints introduced / touched:**

- RULE-01b — models exclusively via `ModelRegistry`; capability types in
  `core/llm/` are wiring, not a new model source.
- RULE-03 — policy contract (`should_escalate`, `TieringPolicy`) specified
  before implementation (this ADR).
- RULE-04/06 — one new module (`dynamic_tiering.py`, policy + factory);
  chat wiring stays split across the existing `dependencies.py` /
  `chat_service.py` / `_agent_stream.py` responsibilities.
- RULE-11 — degradation is a loud warning; base-cascade failures and
  selector bugs propagate.
- RULE-13 — tiering composes below the run/stream split; both paths
  inherit it, no new interface.
- RULE-18/18b — env knobs resolve via `CoreSettings` (no hardcoded config)
  and each must have effect evidence (changing the value changes the
  behavior, or emits the documented warning).
- RULE-20 — pilot ships complete: flag, policy, wiring, degradation,
  logging, tests, docs.

---

## Implementation Notes

**Task 7 (Core):** `dynamic_tiering.py` (`TieringPolicy`, `should_escalate`,
prompt/turn derivation helpers, `build_tiered_model` returning the
`SelectModel` capability whose selector picks `escalation_model` iff
`should_escalate(...)` else `base_model`, short-circuiting to base when
`escalation_model is None`); three `CoreSettings` fields; `ChatAgent`
`capabilities` passthrough. Selector is **sync** (needs no I/O — upstream
accepts sync or async).

**Task 8 (Backend):** escalation `LazyModelResolution` in
`chat/dependencies.py`; idempotent consumption in `ChatService`
(`ensure_resolved` extension, degradation per Decision 5); capability
attach in `_agent_stream.stream_agent_response` (flag-gated;
`registry.get_model` for the escalation instance); escalation logging.

**Test Contract (binding, incl. RULE-18b evidence):**

- Pure policy: both triggers, boundaries (`>` vs `>=`, off-by-one),
  `None` prompt, degraded short-circuit.
- Derivation: synthesized `ModelMessage` histories → `turn_count`;
  `str`/`None` prompts → `latest_user_prompt`.
- Effect evidence per knob (RULE-18b): toggling
  `NARRARE_LLM_DYNAMIC_TIERING` flips capability attach; changing
  `…_MAX_PROMPT_CHARS` / `…_MIN_TURNS` flips the escalation decision.
  Tests mutate env + `get_core_settings.cache_clear()` (ADR-071 §8
  pattern).
- Degradation: escalation resolver raising `ConfigurationError` → one
  warning, base model used; base-cascade error still propagates
  (ADR-086 L12 regression node must stay green).
- Flag off: existing chat integration suite unchanged (byte-identical
  wiring assertion).
- Selection: two `TestModel` instances with distinct outputs prove the
  escalated turn actually used the escalation model.

**ADR Implementation Completeness Gate (Gate 12):** before marking ✅
Implemented, verify the Gate 12 checklist at
`.opencode/context/narrare-dev/processes/quality-gates.md` — wired (flag on
produces escalations), tested (Test Contract above), consumed (chat path
only, per Decision 6), documented (this ADR + settings reference).

---

## Escape Hatch (pre-authorized fallback — dormant)

**Binding user decision 2026-09-30:** if the installed 2.52 `SelectModel`
API proved unsuitable for our Gateway boundary, F3 degrades to a *minimal
custom `Model` wrapper* (a thin dispatcher over the same two pre-built
models) instead of aborting.

**Pinning verdict: SUITABLE — hatch not triggered.** The capability
composes with `ModelRegistry`-built `Model` instances without subclassing,
its selector contract is pure with full context, and lifecycle/precedence
are managed upstream. The only deviations from the plan's assumption are
recording-level (import path `pydantic_ai.capabilities`, capability instead
of wrapper) — both are corrections of our assumptions, not API defects.
The hatch stays pre-authorized for the one scenario pinning cannot rule
out: a *future* pydantic-ai release changing capability model-contribution
semantics (see Review Trigger). Implementing the wrapper then requires an
ADR amendment, not a new ADR.

---

## Review Trigger

- [ ] After the pilot evaluation window (once `dynamic_tier_escalation`
      telemetry supports a decision): revisit the policy (thresholds,
      per-tier `ModelSettings` via a companion per-step
      `get_model_settings` capability, LLM-judge router) and scope
      (beyond chat).
- [ ] When pydantic-ai changes capability/model-selection semantics
      (watch `SelectModel` / `get_model` / `model_is_explicit` in release
      notes): re-pin this ADR's API table; if broken, activate the Escape
      Hatch via amendment.
- [ ] When chat gains suspended-response continuation: that path must pass
      `model=` explicitly (upstream `UserError` on dynamic-selector resume).
- [ ] When users ask to steer tiers per user/project: evaluate option (d)
      (DB-configured ladder) with pilot data in hand.
