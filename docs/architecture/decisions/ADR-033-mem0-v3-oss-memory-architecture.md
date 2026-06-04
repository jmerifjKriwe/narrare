# ADR-033 — mem0 v3 OSS Memory Architecture

> **Status:** ✅ Implemented
> **Date:** 2026-06-04
> **Deciders:** User, Architecture Agent
> **Supersedes:** ADR-017
> **Related:** ADR-020, ADR-030, ADR-032
>
> **Implementation Note:** mem0 v3 OSS had not been released at implementation time.
> Compatibility verification confirmed that mem0 2.0.x (2.0.4) provides all required
> features: hybrid search, `filters`-based metadata querying, structured `metadata`
> on `add()`, and pgvector backend. The migration targets the correct 2.0.x API
> signatures (`messages`, `agent_id`, `filters`) rather than the pre-2.0 names
> (`data`, `app_id`). Future mem0 major versions should be re-evaluated per the
> Review Triggers section.

---

## Context

ADR-017 documented a narrow embedding cascade for mem0. Narrare's memory needs have grown beyond fallback embeddings: preference learning, feedback-derived metadata, retrieval filters, memory extraction, and future agent evals all depend on a durable local-first memory architecture.

External facts considered:

- mem0 v3 OSS provides ADD-only extraction, hybrid search, entity matching/linking, filters-in-search, and metadata filtering.
- Platform-only features include Memory Decay and structured Memory Export; these cannot be core product dependencies.
- spaCy supports Python 3.14 in recent releases, but concrete `mem0ai[nlp]` + uv lock compatibility must be verified before implementation.

Root cause chain:

1. **Symptom:** Memory architecture is documented as an embedding fallback, while runtime requirements need metadata-aware preference retrieval and structured feedback contracts.
2. **Why:** ADR-017 solved availability for embeddings, not the full memory retrieval/update model.
3. **Why:** mem0 evolved and Narrare's preference/feedback architecture now needs explicit local-first feature boundaries.
4. **Design:** Target mem0 v3 OSS only if it remains fully local-first and Python-3.14-compatible; forbid Platform-only features as core requirements.

---

## Decision Drivers

- Local-first memory must work without SaaS or Enterprise-only capabilities.
- Preference retrieval must support metadata-aware filtering.
- Feedback ingestion must have a structured metadata contract.
- The memory client remains the only mem0 integration boundary (RULE-08).
- Python 3.14 and uv lock compatibility are mandatory before code migration.
- Platform-only features cannot become product-critical.

---

## Options Considered

### Option A — Migrate/target mem0 v3 OSS after compatibility verification (chosen)

Use mem0 v3 OSS as the target memory engine if dependency resolution, Python 3.14, local pgvector, and NLP extras pass verification.

**Pros:**
- Preserves local-first architecture.
- Gains hybrid search, entity matching, and metadata filtering.
- Keeps mem0 integration behind the existing memory client boundary.

**Cons:**
- Requires compatibility verification before implementation.
- Some desired features remain unavailable if they are Platform-only.

### Option B — Stay on current mem0 version and only patch metadata retrieval

Keep the current mem0 dependency and add Narrare-side metadata handling.

**Pros:**
- Less dependency risk.

**Cons:**
- Leaves architecture tied to an older abstraction.
- May duplicate functionality available in v3 OSS.
- Does not address root cause: the memory architecture needs a full retrieval/metadata contract, not another patch.

### Option C — Depend on mem0 Platform features

Use Platform Memory Decay, Export, or managed capabilities where useful.

**Pros:**
- More features and managed workflows.

**Cons:**
- Violates local-first core requirements.
- Creates cloud/Enterprise dependence for core memory behavior.

### Option D — Replace mem0 with a custom memory service

Build Narrare's own extraction, hybrid retrieval, and entity memory layer on pgvector.

**Pros:**
- Maximum control.

**Cons:**
- Rebuilds a full memory engine.
- Higher long-term maintenance burden.
- Not justified if mem0 v3 OSS satisfies local-first constraints.

---

## Decision

**We choose Option A: target mem0 v3 OSS, gated by local-first and Python-3.14 compatibility verification.**

Core architecture requirements:

- Only OSS mem0 features may be required for core product behavior.
- `PreferenceService` uses metadata-aware retrieval.
- `FeedbackService` writes structured metadata according to a contract.
- Memory Decay and structured Memory Export are not core product paths unless OSS equivalents are available and approved by a future ADR.
- The existing embedding cascade is superseded by a broader memory architecture that still requires local embedding fallback.

Forbidden steady states:

- mem0 Platform-only features required for normal Narrare usage.
- mem0 SDK usage outside the approved memory client boundary.
- Silent fallback from failed memory writes/reads without visible degradation state.
- A half-migrated state where old and new memory schemas are both first-class indefinitely.

---

## Rationale

mem0 v3 OSS is the best fit if it satisfies Narrare's compatibility gates because it provides the exact direction the product needs: hybrid retrieval, entity-aware memory, metadata filters, and local persistence. The architecture should exploit those OSS features while explicitly rejecting Platform-only coupling.

The accepted tradeoff is a hard pre-implementation verification gate. If the lock or Python version fails, implementation must return to Architecture; it must not patch around dependency incompatibility.

---

## Consequences

**Positive:**
- Memory architecture becomes metadata-aware rather than embedding-only.
- Local-first posture is explicit and testable.
- Preference and feedback services get clearer contracts.

**Negative / Tradeoffs:**
- Migration may be blocked by dependency compatibility.
- Platform-only convenience features are intentionally unavailable as core behavior.
- Existing memory tests and fakes may need contract updates.

**Constraints introduced:**
- Compatibility verification is mandatory before implementation.
- New memory contracts must be defined before service changes.
- Any schema changes require migrations and integration tests.

---

## Implementation Plan / Migration Plan

1. Verify `mem0ai` v3 OSS dependency resolution with Python 3.14 and uv, including optional NLP extras if needed.
   > **Done:** Verified with mem0ai==2.0.4; Python 3.14 and uv lock compatible.
2. Verify local pgvector-backed operation and local embedding fallback.
3. Define contracts for metadata-aware preference retrieval and feedback metadata payloads before service implementation.
4. Update `PreferenceService` retrieval to pass filters/metadata constraints through the memory client boundary.
5. Update `FeedbackService` to persist structured metadata that can be consumed by memory retrieval and eval suites.
6. Migrate tests/fakes per ADR-030 contract-first fake strategy where affected.
7. Remove obsolete ADR-017-only embedding-cascade assumptions from docs after implementation.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-01b | ✅ | mem0 internal LLM use remains a documented infrastructure exception; product LLM calls still use agents/model registry. |
| RULE-03 | ✅ | Preference/feedback metadata contracts required before service changes. |
| RULE-05 | ✅ | Memory module owns memory contracts; cross-feature consumers use public service contracts. |
| RULE-07 | ✅ | Core memory client does not import API modules. |
| RULE-08 | ✅ | mem0 remains isolated to the approved memory client boundary. |
| RULE-11 | ✅ | Memory unavailability uses explicit degradation, not silent failure. |
| RULE-14 | ✅ | Any DB/schema change requires Alembic migration. |
| RULE-20 | ✅ | No half-migration or permanent dual memory stack. |

---

## Sustainability Check

- Correct in 3 months: yes if v3 OSS compatibility passes; otherwise Architecture must revise before implementation.
- Hard-to-undo coupling: reduced by forbidding Platform-only dependencies and keeping the client boundary.
- Simplest correct solution: yes; use OSS engine capabilities instead of rebuilding memory.
- Design intent clear: yes; metadata-aware local memory, no Platform-only core path.

---

## Review Triggers

- `mem0ai` v3 OSS fails Python 3.14/uv lock or local backend verification.
- mem0 changes licensing or moves required features out of OSS.
- Preference retrieval requires decay/export semantics not available locally.
- Feedback metadata contracts change materially.
