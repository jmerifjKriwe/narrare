# ADR-058 — ProcessHistory Sliding Window Context Management

> **Status:** 🔄 Proposed
> **Date:** 2026-06-30
> **Deciders:** Architecture Agent
> **Supersedes:** —
> **Extends:** ADR-034 (adds sliding window to ProcessHistory implementation)

---

## Context

ProcessHistory (`packages/core/narrare_core/agents/process_history.py`) accumulates pydantic-ai `ModelMessage` objects without any bound. Every conversational turn appends `result.new_messages()` to the internal list, and the list grows monotonically across the lifetime of a conversation.

Root cause chain:

1. **Symptom:** Chat conversations degrade in quality and increase in latency after many turns. Eventually token limits are exceeded and the model errors.
2. **Why (1):** The `ProcessHistory.messages` list grows without bound — every turn appends new messages but nothing ever trims.
3. **Why (2):** `ProcessHistory` is a trivial dataclass with no concept of token budgets, sliding windows, or truncation. It was designed as a lightweight container and deferred all trimming to callers (which never implemented it).
4. **Design:** Token-aware sliding window management built directly into `ProcessHistory`, using usage data already flowing through `StreamEvent("done")`.

The existing trimming in `chat_service_core.py:format_history()` addresses a different concern — it trims the **DB-persisted ChatMessage list** for prompt injection (text-based, not token-aware). The pydantic-ai `message_history` (the agent-internal `ModelMessage` list) has never been trimmed and remains the unbounded growth path.

A prior evaluation of `pydantic-ai-harness` determined it was not worth adopting (pre-1.0 risk, ROI too low). However, its Context Management feature (SlidingWindow + LimitWarner) had the highest ROI for Narrare. This ADR builds a lightweight in-house equivalent.

---

## Decision Drivers

- **Must be backward compatible** — existing `ProcessHistory` consumers (`ChatService`) must work without changes. `max_tokens=None` = no trimming (current behaviour).
- **Must use token data already flowing through `StreamEvent`** — `usage.input_tokens` is already available per turn. No need to add token-counting infrastructure.
- **Must work at the `ProcessHistory` level** — not ChatService-specific. Any future conversational agent reuses the same mechanism.
- **Minimal new abstractions** — no new modules, no new capabilities, no new classes. Enhance the 63-line `ProcessHistory` directly.
- **Sliding window must drop at message-pair boundaries** — never split a user+assistant exchange. Always drop complete turns.
- **No LimitWarner in this iteration** — can be added later as a separate concern.

---

## Options Considered

### Option A — Enhance ProcessHistory directly (recommended)

Add token tracking and sliding window to the existing `ProcessHistory` dataclass.

**Pros:**
- Zero new modules, zero new imports in consumers
- Backward compatible via `max_tokens=None` default
- Single responsibility preserved (history management stays in `ProcessHistory`)
- Token data already available from `StreamEvent("done")` — no new wiring
- Sliding window algorithm is ~40 lines of straightforward logic

**Cons:**
- Token estimation is a heuristic (pydantic-ai `ModelMessage` is opaque; we use cached `_estimated_tokens` field)
- Oldest messages are dropped without warning (no LimitWarner yet)

### Option B — New `NarrareContextCapability` (ADR-026 pattern)

Follow the ADR-026 Capability injection pattern: create a `NarrareContextCapability` that wraps sliding-window logic and gets injected into all CONVERSATIONAL agents.

**Pros:**
- Follows established Capability pattern
- Could be composed with other capabilities
- Future-proof if multiple agent types become CONVERSATIONAL

**Cons:**
- Premature abstraction — only one agent type (ChatAgent) uses ProcessHistory today
- Adds a new capability file, a new registration, and a new injection path for ~40 lines of logic
- Increases complexity without proportional benefit
- Violates YAGNI — we don't need capability composition for a single 40-line algorithm
- ADR-026 capabilities are for prompt content injection, not runtime data management

### Option C — Add to base `NarrareAgent`

Add history management (max_tokens, sliding window) directly to the `NarrareAgent` base class.

**Pros:**
- All agents could benefit automatically
- Centralized management

**Cons:**
- `NarrareAgent` would grow a second responsibility (history management + LLM execution)
- RULE-06 violation (one responsibility per file)
- Task agents (NONE policy) don't need it — would add dead code
- ProcessHistory is already the correct abstraction for history management

### Option D — External dependency (`pydantic-ai-harness`)

Adopt `pydantic-ai-harness` for its Context Management features.

**Pros:**
- Battle-tested sliding window and LimitWarner
- Community maintained
- Additional features beyond context management

**Cons:**
- Pre-1.0 package with API instability risk
- Already evaluated and rejected (too low ROI vs risks)
- Adds a dependency for ~40 lines of in-house logic
- Integration cost (new adapter, new tests, new failure modes)

---

## Decision

**We choose Option A: enhance `ProcessHistory` directly.**

Token tracking and sliding window management belong in the `ProcessHistory` class itself. It already owns the message list — extending it with token awareness and automatic trimming keeps the responsibility boundary intact. The implementation is compact (~40 lines of new logic), backward compatible by default, and consumes token data that already flows through the system.

Options B and C create new abstractions for the sake of pattern purity, when the simpler fix (enhance the owning class) is architecturally cleaner and more sustainable.

---

## Rationale

1. **ProcessHistory already owns the responsibility.** Adding token tracking to the class that manages history is not scope creep — it's completing the design.

2. **Backward compatibility is trivial.** `max_tokens=None` (the default) reproduces current behaviour exactly. No consumer needs to change.

3. **Token data is already available.** `StreamEvent("done").usage["input_tokens"]` is populated by the agent runtime. `ChatService` already has `event.usage` in the `_stream_agent_response` method. Wiring is a one-line change in the `ChatService` event handler.

4. **No new modules or capabilities needed.** The sliding window algorithm fits in ~40 lines within process_history.py, keeping the module boundary intact.

5. **Pair-boundary dropping is architecturally correct.** Dropping at user+assistant boundaries preserves conversational coherence. No partial turns are ever dropped.

6. **The Alternative-B (Capability) pattern would be premature.** ADR-026 Capabilities are designed for prompt content injection, not runtime data management. Using them for ProcessHistory would be a category error.

7. **The review trigger handles future complexity.** If multiple agent types become CONVERSATIONAL, we re-evaluate whether the Capability pattern is needed. Until then, keep it simple.

---

## Consequences

**Positive:**
- Token-aware automatic trimming prevents context-window overflow
- Backward compatible — all existing consumers work unmodified
- Single-line consumer change to wire token data (ChatService passes `usage.input_tokens` to `history.add()`)
- No new modules, no new dependencies, minimal new code
- Sliding window drops at message-pair boundaries — preserves conversational coherence
- Default `max_tokens=128_000` works out of the box for Claude-class models

**Negative / Tradeoffs:**
- Token estimation is a heuristic (pydantic-ai `ModelMessage` is opaque to us)
  - Mitigation: we cache `_estimated_tokens` per message on the first `add()` call
  - Fallback: if estimation is impossible, count each message as 1 token (conservative: trims more aggressively)
- Oldest messages are dropped without user notification
  - Acceptable for now — LimitWarner is deferred
- A single oversized message that exceeds `max_tokens` alone is kept (can't trim further)
  - Acceptable — prevents dropping the current turn mid-conversation

**Constraints introduced:**
- `ProcessHistory.add()` now accepts optional `input_tokens: int` parameter
- `ProcessHistory(max_tokens: int | None = None)` — `None` means unlimited (backward compat)
- Default max_tokens for new code: `128_000` (Claude context window; configurable per agent)

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | No new LLM imports — token data comes from existing StreamEvent |
| RULE-02 | ✅ | No prompt changes — history is runtime data, not prompt content |
| RULE-03 | ✅ | `ProcessHistory` Protocol extended before implementation (this ADR + updated signature) |
| RULE-04 | ✅ | ProcessHistory remains under 150 lines (63 → ~110 after enhancement) |
| RULE-05 | ✅ | Changes stay within `core/agents/` module boundary |
| RULE-06 | ✅ | ProcessHistory keeps single responsibility: history management |
| RULE-07 | ✅ | No cross-layer dependencies — core change only |
| RULE-09 | ✅ | All public methods fully typed |
| RULE-10 | ✅ | Unit tests for: token tracking, trim at boundary, trim with single oversized message, backward compat with max_tokens=None |
| RULE-11 | ✅ | No silent failures — trimming is deterministic and logged |
| RULE-13 | ✅ | Streaming/non-streaming both use the same ProcessHistory (no interface change) |
| RULE-20 | ✅ | Full implementation — no stubs, no TODOs, no deferred streaming |
| RULE-22 | ✅ | Only consumer is ChatService — single integration point |

---

## Implementation Notes

### Where changes land

| File | Change |
|------|--------|
| `packages/core/narrare_core/agents/process_history.py` | Add `max_tokens`, `_usage_tokens`, token tracking, sliding window trim |
| `apps/api/narrare/chat/chat_service.py` | Wire `event.usage["input_tokens"]` → `history.add(new_messages, input_tokens=...)` |
| `tests/unit/api/chat/test_chat_service_history.py` | Add sliding window tests |

No changes to `base.py`, `chat_agent.py`, `chat_service_core.py`, `contracts.py`, or `StreamEvent`.

### How token tracking works

`StreamEvent("done")` already carries `usage: dict[str, int] | None` with `input_tokens` populated by pydantic-ai:

```python
# In NarrareAgent.run_stream() — base.py line 223-230:
usage_obj = result.usage
if usage_obj:
    usage = {
        "input_tokens": usage_obj.input_tokens or 0,   # ← per-turn input tokens
        "output_tokens": usage_obj.output_tokens or 0,
        "total_tokens": usage_obj.total_tokens or 0,
    }
```

**Token counting approach:**
- `input_tokens` from `StreamEvent("done")` represents the tokens consumed by the **request** (prompt + message_history) for that turn.
- We do NOT re-count tokens from scratch. We use `input_tokens` as an approximation of the message pair's cost.
- Each message in `new_messages` is tagged with an estimated token count via a private `_estimated_tokens` attribute (set on the `ModelMessage` object using `object.__setattr__` or tracked in a parallel `_message_tokens: dict[int, int]` map using the message's `id()`).

**Edge case — using `id()` mapping**: Since pydantic-ai `ModelMessage` is an opaque type that may be a frozen dataclass, we cannot set attributes on it. Instead, maintain `_message_tokens: dict[int, int]` keyed by `id(message)`. On `clear()`, clear this map too.

### Sliding window algorithm

```
def _trim(self) -> None:
    """Drop oldest message-pairs until under max_tokens."""
    if self._max_tokens is None:
        return  # no trimming

    # Sum estimated tokens for all messages
    total = sum(self._message_tokens.get(id(m), 1) for m in self.messages)

    while total > self._max_tokens and len(self.messages) >= 4:
        # Drop the oldest user+assistant pair (2 messages)
        # messages[0] = oldest user message
        # messages[1] = oldest assistant message
        id0 = id(self.messages[0])
        id1 = id(self.messages[1])
        total -= self._message_tokens.get(id0, 1)
        total -= self._message_tokens.get(id1, 1)
        del self._message_tokens[id0]
        del self._message_tokens[id1]
        self.messages = self.messages[2:]

        logger.info(
            "process_history_trimmed_pair",
            remaining_messages=len(self.messages),
            remaining_estimate=total,
        )
```

**Why `len(self.messages) >= 4`?** — We never drop the current turn (the last user+assistant exchange). A conversation needs at minimum the current exchange to be coherent. The `>= 4` guard means we keep at least 2 turns (the current turn + one prior turn for context). If a single turn (2 messages) exceeds `max_tokens`, we keep it anyway.

### API design

```python
@dataclass
class ProcessHistory:
    messages: list[Any] = field(default_factory=list)
    _max_tokens: int | None = 128_000  # None = no trimming
    _message_tokens: dict[int, int] = field(default_factory=dict)  # id(message) → estimated_tokens
    _usage_tokens: int = 0  # cumulative input_tokens across all turns

    def add(
        self,
        new_messages: list[Any],
        *,
        input_tokens: int | None = None,
    ) -> None:
        """Append new messages and trigger trim if max_tokens is set.

        Args:
            new_messages: Messages from StreamEvent.new_messages().
            input_tokens: The input_tokens value from StreamEvent("done").usage.
                Distributed evenly across new_messages as estimated tokens.
        """

    def trim(self) -> None:
        """Explicitly trigger sliding window trim.

        Useful when called from outside the add() path.
        """

    def clear(self) -> None:
        """Clear all stored history and token tracking."""

    @property
    def token_estimate(self) -> int:
        """Sum of estimated tokens across all stored messages."""

    @property
    def usage_tokens(self) -> int:
        """Cumulative input_tokens consumed across all turns."""

    @property
    def is_empty(self) -> bool:
        """Whether history contains no messages."""
```

### Consumer wiring (ChatService)

Currently in `chat_service.py` (lines 234-238):

```python
elif event.type == "done":
    if event.new_messages:
        history.add(event.new_messages)
        self._histories[conv_id] = history
```

After change:

```python
elif event.type == "done":
    if event.new_messages:
        input_tokens = event.usage.get("input_tokens") if event.usage else None
        history.add(event.new_messages, input_tokens=input_tokens)
        self._histories[conv_id] = history
```

### Default max_tokens value

`128_000` (Claude Sonnet 4.5 / Claude 4 Opus context window). This is a sensible default that prevents context-window overflow for most models. If an agent uses a smaller-context model, the caller configures `ProcessHistory(max_tokens=model_context_window)` explicitly.

The `ProcessHistory` default in the `__init__` signature is `max_tokens: int | None = 128000`. For `max_tokens=None` (backward compat), the consumer explicitly passes `ProcessHistory(max_tokens=None)` or uses the helper `ProcessHistory.unlimited()`:

```python
@staticmethod
def unlimited() -> ProcessHistory:
    """Create a ProcessHistory with no token limit (backward compatibility)."""
    return ProcessHistory(max_tokens=None)
```

### Unit test scenarios

| Test | Scenario |
|------|----------|
| `test_token_tracking` | Verify `usage_tokens` accumulates correctly across multiple `add()` calls |
| `test_trim_at_pair_boundary` | Verify sliding window drops oldest user+assistant pair when exceeding `max_tokens` |
| `test_trim_preserves_current_turn` | Verify the last pair is never dropped (minimum 4 messages = 2 turns) |
| `test_single_oversized_message` | Verify a single pair exceeding `max_tokens` is kept |
| `test_backward_compat_no_max_tokens` | Verify `max_tokens=None` never trims |
| `test_unlimited_helper` | Verify `ProcessHistory.unlimited()` creates unlimited history |
| `test_clear_resets_tokens` | Verify `clear()` resets both messages and token state |
| `test_token_estimate_property` | Verify `token_estimate` returns correct sum |

### What is NOT in this iteration

- **LimitWarner**: Not implemented. Could be added later as a separate callback or event. Falls into the "nice to have" category — the sliding window handles the functional requirement silently.
- **Per-agent max_tokens configuration**: Not yet. The single default of 128k covers all current use cases. Per-agent tuning can be added when multiple CONVERSATIONAL agents exist.
- **Token re-counting on existing messages**: We store estimated tokens once on `add()`. Re-counting would be more accurate but adds complexity without proportional benefit for a sliding window.

---

## Review Trigger

- [x] When `pydantic-ai-harness` reaches 1.0 — evaluate if switching from in-house sliding window is worth the dependency
- [x] When multiple agent types become `CONVERSATIONAL` — re-evaluate if a Capability pattern or per-agent token budget is needed
- [x] When a model with a significantly different context window becomes primary — reconsider the 128k default
- [ ] After 3 months — review if the `id()`-based token mapping causes any issues with message identity stability across pydantic-ai versions

---

## Sustainability Check

1. **Correct in 3 months?** Yes. Backward compatible by default. Token tracking uses data already flowing through `StreamEvent`.
2. **Hard-to-undo coupling?** None. ProcessHistory is already a standalone dataclass with one consumer (ChatService).
3. **Simplest correct solution?** Yes. ~40 lines in the owning class. No new modules, capabilities, or dependencies.
4. **Design intent clear?** Yes. "ProcessHistory manages its own memory budget" is a natural extension of "ProcessHistory stores messages."

---

## ADR Implementation Completeness Gate (Gate 12)

Before marking this ADR as "✅ Implemented":

- [ ] `ProcessHistory` updated with `max_tokens`, `_message_tokens`, sliding window trim
- [ ] `ChatService` wires `event.usage.input_tokens` → `history.add(..., input_tokens=...)`
- [ ] Backward compat verified: `ProcessHistory(max_tokens=None)` = old behaviour
- [ ] All unit tests pass (token tracking, trim boundary, oversized message, backward compat)
- [ ] Integration test: chat with 20+ turns triggers trimming
- [ ] No new dependencies, no new modules, no half-implementations
