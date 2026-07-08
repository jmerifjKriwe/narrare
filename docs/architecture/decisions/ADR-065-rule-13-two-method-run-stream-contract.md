# ADR-065 — RULE-13 Two-Method run/stream Contract Reconciliation

> **Status:** ✅ Accepted
> **Date:** 2026-07-08
> **Deciders:** Architecture Specialist (review-01 architecture remediation)
> **Supersedes:** — (reconciles the RULE-13 *text* in CONSTRAINTS.md to the realised
> architecture; does not supersede any ADR)
> **Finding:** review-01-architektur §5 / §7 / `[AUFG-01-04]`

---

## Context

CONSTRAINTS.md RULE-13 prescribes a **single** method signature for streaming and
non-streaming LLM operations:

```python
async def run(self, ..., stream: bool = False) -> LLMResult | AsyncIterator[str]: ...
```

The realised implementation in `packages/core/narrare_core/llm/gateway.py`
(`ModelRegistry`) exposes **two** methods instead:

- `run(...)` (gateway.py:132) — non-streaming, returns `T` (the agent output).
- `stream(...)` (gateway.py:217) — streaming, `async def ... -> AsyncIterator[StreamChunk]`.

Both share the same provider-resolution and model-settings path (`get_model` /
`build_runtime_model_settings`), so they are functionally equivalent to the rule's
*intent* (MCP/A2A can use a non-streaming call against the same registry that
streaming clients use). But the literal signature does not match the documented
`stream: bool` single-method form.

This discrepancy is a latent inconsistency between the constitution (CONSTRAINTS.md)
and the code: reviewers reading RULE-13 expect one method and find two, which breeds
confusion and false-positive "violation" reports. The review asked us to reconcile —
either adapt the rule to the two-method architecture, or unify the signatures.

**Verified facts (code read + graph-first caller analysis):**

- `ModelRegistry.run(...)` returns `T`; `ModelRegistry.stream(...)` returns
  `AsyncIterator[StreamChunk]`. The return *types* differ structurally (a value vs an
  async iterator of chunks), and token-usage handling differs (`result.usage` vs a
  final `StreamChunk(is_final=True, usage=...)`).
- Caller blast radius of a unification (option B): `registry.stream(` is consumed in
  `writing/suggest_service.py:191`, `writing/_interview_draft.py:166`,
  `writing/ws_turn_service.py:159`; `registry.run(` / `ModelRegistry.run` is consumed
  in `generation/name_service.py:132` and `kb/consistency_analyzer.py:178`.
  Unifying would force every caller to narrow a `T | AsyncIterator[StreamChunk]`
  union.
- **No checker currently validates RULE-13's signature shape.** CONSTRAINTS.md §6
  (Enforcement Summary) has no RULE-13 row, and `scripts/` contains no RULE-13
  signature assertion. The streaming checker (`check_streaming_compliance.py`,
  RULE-20) validates frontend `connectSSE()` coverage for backend SSE endpoints —
  a different concern. So RULE-13 is, today, enforced only by PR review.

---

## Decision Drivers

- **Typing clarity (RULE-09 / RULE-23).** A single method returning
  `LLMResult | AsyncIterator[str]` is a union return type. Every caller must narrow
  it (`isinstance`/`cast`/`# type: ignore`), which is exactly the undisciplined
  suppression RULE-23 forbids and the type-safety RULE-09 requires.
- **MCP/A2A interoperability (the actual goal of RULE-13).** MCP/A2A need a
  non-streaming call against the *same registry* that streaming clients use. Two
  methods on one registry satisfy this; a single method is not required for it.
- **Framework alignment.** pydantic-ai itself splits `agent.run()` and
  `agent.run_stream()`. The two-method pattern mirrors the underlying framework.
- **Minimal blast radius.** Reconciling the *rule text* to the code touches docs
  only; unifying signatures rewrites 5 call sites and adds narrowing everywhere.
- **"documented = implemented".** The constitution must describe the real contract.

---

## Options Considered

### Option A — Reconcile the rule to reality: declare the two-method signature as the RULE-13 standard  ✅ CHOSEN

Write an ADR declaring `run()` (non-streaming `T`) + `stream()`
(`AsyncIterator[StreamChunk]`) as the standard contract; update CONSTRAINTS.md
RULE-13 text, code example, and add an enforcement-summary row.

**Pros:**
- Preserves precise per-method return types — no union, no narrowing, no RULE-23
  tension.
- Zero call-site changes; docs-only reconciliation.
- Mirrors pydantic-ai's own `run`/`run_stream` split.
- Honest: the constitution then matches the code (closes the "documented ≠
  implemented" gap).

**Cons:**
- RULE-13's literal "one method" phrasing is relaxed to "one registry interface".
  The ADR must make clear the *intent* (MCP/A2A parity) is preserved.

### Option B — Unify to a single `run(self, ..., stream: bool = False)` method

Collapse `run` and `stream` into one method returning `T | AsyncIterator[StreamChunk]`;
rewrite all callers.

**Pros:**
- Literal compliance with the current RULE-13 wording.

**Cons:**
- **Typing downgrade.** Forces a union return type narrowed at every call site →
  RULE-23 friction (`# type: ignore[union-attr]` / `cast`), contradicting RULE-09.
- **Large blast radius for a downgrade:** 5 call sites rewritten + narrowing logic.
- Token-usage handling (batch `result.usage` vs final-chunk `usage`) must be
  unified inside one method, obscuring two genuinely different control flows
  (return vs yield).
- Adds an adapter layer over pydantic-ai's already-split API for no benefit.

---

## Decision

**We choose Option A: declare the two-method `run()` / `stream()` signature as the
RULE-13 standard and reconcile CONSTRAINTS.md to the realised architecture.**

RULE-13's intent — *every streaming-capable LLM operation also has a non-streaming
counterpart on the same registry/service, so MCP/A2A (which may not support
streaming) need no parallel implementation* — is fully preserved. The mechanism is
two named methods sharing one provider/model-settings path, rather than one method
with a `stream: bool` flag. CONSTRAINTS.md RULE-13 (§5), its code example, and the
§6 Enforcement Summary are updated in this ADR's commit.

**Why two methods, not one `stream: bool`:** a single method returning
`LLMResult | AsyncIterator[str]` imposes a union return type that every caller must
narrow — a direct RULE-23 hazard and a RULE-09 type-safety loss — and conflates two
structurally different control flows (batch return with `result.usage` vs incremental
`yield` with a final usage chunk). Two named methods give precise return types,
mirror pydantic-ai's own `agent.run()` / `agent.run_stream()` split, and keep the
"same interface" guarantee at the registry level — which is what MCP/A2A
interoperability actually requires.

---

## Rationale

The *purpose* of RULE-13 is interoperability, not signature uniformity for its own
sake. MCP and A2A clients need to obtain a non-streaming result from the same
service object that streaming web clients use; they do not care whether that is
expressed as one method or two. The single-method prescription in the constitution
pre-dated the realisation that a union return type fights Python's type system
(RULE-09/RULE-23) and pydantic-ai's own API shape. Reconciling the rule to the
two-method reality removes a false-positive generator (reviewers flagging a
"RULE-13 violation" that is actually the correct pattern) without sacrificing the
interoperability guarantee.

Option B was rejected because it trades a documentation fix for a typing downgrade
across 5 call sites — the definition of treating the symptom (literal text mismatch)
rather than the root cause (the prescription was wrong).

**Tradeoff accepted:** RULE-13 now permits two methods. The ADR and the rewritten
rule text carry the burden of communicating that the interoperability *intent* is
unchanged and that both methods must share the provider/model-settings path.

---

## Consequences

**Positive:**
- CONSTRAINTS.md RULE-13 now matches the code; no more false-positive "two methods
  = violation" reviews.
- Precise return types preserved (`T`, `AsyncIterator[StreamChunk]`); no RULE-23
  narrowing burden.
- Zero production-code changes required for the reconciliation.

**Negative / Tradeoffs:**
- RULE-13's prescription is broader (two methods permitted); relies on PR review +
  the proposed regression test to keep both methods present and sharing one path.
- Until the Phase-D regression test ships, RULE-13's signature shape is enforced
  only by PR review (a known gap, now explicit).

**Constraints introduced:**
- RULE-13 (reconciled): streaming-capable LLM operations expose both `run()` and
  `stream()` on the same registry/service, sharing the provider/model-settings path.
  A single `stream: bool` union-return method is **not** required and is discouraged
  where it would force union narrowing.

---

## RULE-XX Compliance

| Rule | Status | Notes |
|------|--------|-------|
| RULE-09 | ✅ | Two methods preserve precise return types; no `Any`. |
| RULE-13 | ✅ (reconciled) | Two-method contract declared standard; intent (MCP/A2A parity) preserved. |
| RULE-20 | ✅ | Unaffected — frontend SSE coverage (RULE-20) is a separate concern from the registry signature shape (RULE-13). |
| RULE-23 | ✅ | No union narrowing / type suppressions introduced; unification (Option B) would have *created* RULE-23 friction. |

---

## Implementation Notes

This ADR is a **pure documentation/governance reconciliation** — no production code
changes. CONSTRAINTS.md edits land in this ADR's commit:

- **§5 RULE-13** — rewritten text + two-method code example + "why two methods" note
  referencing ADR-065.
- **§6 Enforcement Summary** — new RULE-13 row pointing at PR review + the Phase-D
  signature-shape assertion.

The current `check_streaming_compliance.py` (RULE-20) is **not** affected: it
validates frontend `connectSSE()` coverage for backend SSE endpoints, which is
orthogonal to the `ModelRegistry` method shape.

**ADR Implementation Completeness Gate (Gate 12):** the CONSTRAINTS.md reconciliation
is documentation and lands now; the Phase-D regression test is the enforcement step
that moves RULE-13 from "PR-review-only" toward `enforced`. This ADR is
`✅ Accepted` (decisions in effect); it reaches `✅ Implemented` when the Phase-D
regression test ships.

---

## Phase D — Enforcement (closure path to `✅ Resolved`)

RULE-13 currently has **no machine enforcement** (no §6 row, no checker). This ADR
adds the §6 row and proposes a structural regression test as the enforcement anchor:

1. **§6 Enforcement Summary row (this commit):** documents that RULE-13 is enforced
   by PR review + the Phase-D signature-shape assertion. ✅
2. **Signature-shape regression test (Core handoff):** a unit test in
   `tests/unit/core/llm/` that introspects `ModelRegistry` and asserts:
   - `ModelRegistry.run` is an `async` function/coroutine method whose return type
     is the output value (not an async iterator);
   - `ModelRegistry.stream` is an async generator method returning
     `AsyncIterator[StreamChunk]`;
   - both exist on the same class (the "one registry interface" guarantee).
   This seals RULE-13 against silent drift (e.g. someone deleting `run` or
   collapsing the two methods). ⏳ deferred to Core specialist.

   *Note on scope:* this is a runtime `inspect`/signature assertion, not an AST
   architecture checker — appropriate because it validates a single class's public
   surface. If RULE-13 later needs to cover *service-layer* run/stream pairs beyond
   `ModelRegistry`, a proper `_checkers/` module can generalise it; that
   generalisation is out of scope for this finding.

---

## Implementation Handoff (executing specialist: Core)

**Core specialist (Phase D enforcement):**
1. `tests/unit/core/llm/test_model_registry.py` (or a new `test_rule13_contract.py`)
   — add a regression test that:
   - asserts `hasattr(ModelRegistry, "run")` and `hasattr(ModelRegistry, "stream")`;
   - asserts `inspect.iscoroutinefunction(ModelRegistry.run)` and that
     `ModelRegistry.stream` is an async generator
     (`inspect.isasyncgenfunction(ModelRegistry.stream)` or
     `inspect.iscoroutinefunction` with an `AsyncIterator` return annotation);
   - asserts the `stream` return annotation is `AsyncIterator`/`AsyncGenerator` of
     `StreamChunk` (via `typing.get_type_hints`), and `run`'s is **not** an async
     iterator.
   This test failing must block CI (it is a unit test under the `test-unit` job).
2. No change to `gateway.py` signatures is required — they already match this
   contract.

**Exact enforcement the specialist must leave green:**
- `just test-unit` (new regression test passes).
- `just check-architecture` (unaffected; no new architecture exception).

**Out of scope:** generalising RULE-13 to service-layer run/stream pairs beyond
`ModelRegistry`; rewriting the (already-correct) `gateway.py` signatures.

---

## Review Trigger

- [ ] When MCP or A2A adapters land (`apps/mcp/`, `apps/a2a/`) → verify they call
      `ModelRegistry.run()` for non-streaming and that the two-method contract holds
      at the adapter boundary.
- [ ] When pydantic-ai changes its `run`/`run_stream` API → re-validate the
      two-method mirroring still holds.
- [ ] When a service beyond `ModelRegistry` needs a RULE-13 contract → consider
      generalising the regression test into an architecture checker.
