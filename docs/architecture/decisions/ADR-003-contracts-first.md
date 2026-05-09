# ADR-003 — Protocol-First Development

> **Status:** ✅ Accepted
> **Date:** project-init
> **Deciders:** Architecture Agent
> **Supersedes:** —

---

## Context

In the previous codebase, 0 of ~60 service classes had a corresponding
Protocol definition (`contract_defined: false` for all, per GLM analysis).
This had concrete consequences:

- Tests mocked concrete classes, making mocks brittle
- MCP/A2A/CLI integration would require modifying calling code (not just
  adding adapters) because no stable interface existed
- Two services with similar responsibilities had incompatible signatures
  discovered only at integration time

## Decision Drivers

- Services must be mockable without depending on their implementation
- MCP, A2A, and CLI must be able to call services via a stable contract
- "Is this method done?" needs a concrete answer — the Protocol provides it

## Options Considered

### Option A — Protocol-first (chosen)
`contracts.py` written before `service.py` in every domain module.
Protocol defines every public method with full type signature.

### Option B — ABC (Abstract Base Classes)
Same intent, but ABCs require inheritance.
**Rejected:** Protocols enable structural subtyping — no inheritance needed,
  more flexible, more Pythonic for this use case.

### Option C — Document-only contracts
API contracts in documentation, no code enforcement.
**Rejected:** Documentation drifts. Code doesn't (when mypy checks it).

## Decision

**We choose Option A — Python Protocols.**

Every service class has a corresponding Protocol in `contracts.py`.
Written before the implementation. Verified by mypy strict.

## Consequences

**Positive:**
- Clean mocking in tests: `Mock(spec=ServiceProtocol)`
- MCP/A2A adapters call the Protocol, not the concrete class
- "Done" has a definition: every Protocol method is implemented

**Negative / Tradeoffs:**
- Every new service requires writing the Protocol first — a small overhead
- Protocol and implementation can drift if mypy is not run

**Constraints introduced:**
- RULE-03 in `CONSTRAINTS.md`

## Implementation Notes

```python
# contracts.py — written first
class ChapterServiceProtocol(Protocol):
    async def get(self, chapter_id: UUID) -> Chapter: ...
    async def update_content(self, chapter_id: UUID, content: str) -> Chapter: ...

# service.py — written after
class ChapterService:
    # mypy verifies this implicitly satisfies ChapterServiceProtocol
    async def get(self, chapter_id: UUID) -> Chapter: ...
    async def update_content(self, chapter_id: UUID, content: str) -> Chapter: ...
```

## Review Trigger

- [ ] If Python typing system introduces a better mechanism for this pattern
