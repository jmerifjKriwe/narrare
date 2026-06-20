# CR-08 P3 — Governed Defaults Manifest

> **Status:** implemented + enforced (CR-AUFG-08-13)
> **Date:** 2026-06-20
> **Author:** Architecture Specialist
> **Spec:** `docs/features/remediation/cr-08-configuration-effect-drift.md` §P3
> **Matrix section:** P3 entries in `docs/architecture/governance/configuration-adoption-matrix.yaml`

---

## 1. Purpose

This manifest classifies every long-tail code default that is intentionally
*not* exposed as a user or operator setting. Each entry documents why the
default exists, who owns it, what review trigger would require
re-evaluation, and how to override it.

A governed default is a code default that:

1. Is intentionally *not* user/project/operator configurable.
2. Has a documented rationale (why this value, why not configurable).
3. Has a defined owner (team or role).
4. Has a review trigger (condition under which the value MUST be re-evaluated).
5. Has a test that fails if the default changes without review.
6. Has an explicit override path (env var, method parameter, or Settings field)
   when override is architecturally acceptable.

---

## 2. Manifest Schema

Each manifest entry uses the following schema:

```yaml
default_id: string
  # Stable identifier. Used by docs, tests, and the Configuration Adoption Matrix.
  # Convention: {domain}_{purpose} (e.g. embedding_similarity_threshold)

domain: string
  # Functional area: embedding, name_dedup, sse, websocket, test, etc.

description: string
  # What this default controls, in one sentence.

current_value: string | number | list
  # The actual code-default value at the time of classification.

rationale: string
  # Why this specific value was chosen.
  # Why it is NOT user/operator configurable (category justification).
  # Reference any UX research, performance targets, or architectural invariants.

owner: string
  # Role or team responsible for re-evaluation.
  # Examples: "Core Specialist", "Frontend Specialist", "Platform Specialist"

review_trigger: string
  # Condition that triggers mandatory re-evaluation.
  # See §3 for the review-trigger pattern classification.

override_path: string | null
  # How to override this default without code changes.
  # Examples: env var name, method parameter name, Settings field path.
  # null if no override path exists (intentionally immutable).

test_path: string
  # Test file(s) that prove this default is intentionally retained.
  # The test must fail if the value changes without a corresponding
  # rationale update or explicit review. Examples:
  #   - "tests/unit/.../test_<feature>_governed_defaults.py"
  #   - Assertion in existing test that the default equals the manifest value
  #   - Cross-layer contract test

discovery_path: string
  # File(s) where the code default lives.
  # Helps future specialists find and update the default.
```

---

## 3. Review-Trigger Pattern Taxonomy

Every governed default has exactly one review-trigger pattern:

| Pattern | When re-evaluation is triggered | Example |
|---------|-------------------------------|---------|
| `scale` | When a domain metric exceeds a threshold (e.g., KB size, project count, user count) | `name_dedup_context_cap` — re-evaluate for very large projects (>5000 named entities) |
| `latency_target` | When user-facing latency targets change | `sse_connect_timeout` — re-evaluate if UX latency SLAs are revised |
| `dependency_change` | When an external dependency or provider changes | `embedding_threshold` — re-evaluate if embedding provider/model changes |
| `incident_feedback` | When user reports or incidents indicate the default causes problems | Any default that generates support tickets |
| `feature_redesign` | When the consuming feature is redesigned or extended | Any default tied to a feature undergoing major revision |
| `time_bound` | Re-evaluate by a fixed calendar date | Legacy defaults, deprecated-since defaults |
| `immutable` | Never re-evaluated — the value is an architectural invariant | Provider inference prefixes (dev/debug only) |

A default may have multiple triggers (e.g., `scale` + `latency_target`).
The first matching trigger opens a re-evaluation window.

---

## 4. Governed Default Entries

### 4.1 Embedding Threshold & Search Limit

```yaml
default_id: embedding_similarity_threshold
domain: embedding
description: >-
  Similarity threshold (0.7) and result limit (20) for vector similarity
  search in KB embedding lookups.
current_value:
  threshold: 0.7
  search_limit: 20
rationale: >-
  Threshold 0.7 was chosen as a reasonable default precision/recall balance
  for novel-worldbuilding KBs (dense embeddings, typically sentence-transformers
  all-MiniLM-L6-v2). 20 results covers typical KB entity lookups without
  flooding the prompt context. NOT user-configurable because changing the
  threshold changes recall behavior silently — wrong threshold leads to
  irrelevant KB context in prompts, not just missing results. Method-parameter
  override exists for programmatic callers that need different recall.
owner: Core Specialist
review_trigger: >-
  scale + dependency_change: re-evaluate if large KBs (>5000 entries) show
  degraded recall/precision, or if the embedding provider/model is changed
  (different distance distributions).
override_path: >-
  Method parameters: search_threshold, search_limit on embedding service
  methods. No env var or Settings override (intentionally code-default with
  caller override).
discovery_path: apps/api/narrare/embeddings/service.py
test_path: tests/unit/api/embeddings/test_embedding_search_defaults.py
```

### 4.2 Name Dedup Context Cap

```yaml
default_id: name_dedup_context_cap
domain: name_dedup
description: >-
  Page size (1000) and token cap (500) for existing-names context assembly
  during name generation deduplication.
current_value:
  page_size: 1000
  token_cap: 500
rationale: >-
  1000 entries per page covers >99% of projects (most novels have <500 named
  entities). 500 token cap limits context to a reasonable batch for name
  generation — prevents prompt flooding while providing enough existing names
  for meaningful dedup. NOT user-configurable because these are performance
  budgets (prompt context, DB query size), not creative preferences.
owner: Backend Specialist (generation domain)
review_trigger: >-
  scale: re-evaluate for very large projects (>5000 named entities, >1000
  distinct generated names) where dedup may miss collisions or context cap
  may suppress relevant names.
override_path: null
  # Intentionally immutable — method-parameter override would be added if
  # scale trigger fires. Until then, keeping it simple prevents scope creep.
discovery_path: apps/api/narrare/generation/name_service.py
test_path: tests/unit/api/generation/test_name_dedup_defaults.py
```

### 4.3 SSE Connect & Retry Defaults

```yaml
default_id: sse_connect_retry_defaults
domain: sse
description: >-
  Frontend SSE connect timeout (30000ms), connection-loss timeout (15000ms),
  and WritingSessionSocket reconnect defaults for streaming AI operations.
current_value:
  connect_timeout_ms: 30000
  connection_loss_timeout_ms: 15000
  # reconnect: exponential backoff, 5 attempts, 1s base delay
rationale: >-
  30s connect timeout is generous for local-first/single-user deployments
  where AI providers may have cold-start latency. 15s connection-loss timeout
  allows transient network issues to resolve without showing the user a
  disconnected state. These are UX-protective defaults — too short causes
  false failures, too long causes perceived hangs. NOT user-configurable
  because they are UX runtime defaults; callers can override via hook options.
owner: Frontend Specialist
review_trigger: >-
  latency_target: re-evaluate if UX latency SLAs are revised (e.g., if
  Narrare targets a managed hosting profile with tighter timeout
  guarantees). incident_feedback: re-evaluate if users report spurious
  disconnection or excessive hang-on-failure.
override_path: >-
  Caller option override via useAIOperation hook options
  (connectTimeoutMs, connectionLossTimeoutMs) and
  WritingSessionSocket constructor options.
discovery_path: >-
  packages/web/lib/hooks/useAIOperation.ts (constants);
  packages/web/components/studio/editor/useSessionSocket.ts (reconnect defaults)
test_path: >-
  packages/web/components/studio/editor/__tests__/useSessionSocket.test.tsx
  (connect timeout, connection-loss timeout, and reconnect default assertions)
```

---

## 5. Enforcement Pattern

For each governed default, the enforcement test MUST:

1. **Assert the current value** matches the manifest. If the code default
   changes, this test fails, forcing the developer to update the manifest
   and rationale.

2. **Assert the override path works** (if one exists). If a method parameter
   or hook option exists, prove that passing a different value actually
   changes behavior.

3. **Assert the review trigger is documented.** The test reads
   `review_trigger` from this manifest or the Configuration Adoption Matrix
   and fails if it is missing or stale.

---

### Example Test Template

```python
# tests/unit/api/embeddings/test_embedding_search_defaults.py
"""Governed defaults: embedding threshold and search limit."""

from narrare.embeddings.service import DEFAULT_SEARCH_THRESHOLD, DEFAULT_SEARCH_LIMIT

class TestEmbeddingGovernedDefaults:
    """Tests that fail if embedding search defaults change without review."""

    def test_default_threshold_matches_manifest(self):
        """Rationale: 0.7 balances precision/recall for novel KBs.
        Review trigger: scale (large KBs) or dependency_change (provider/model change).
        Override: method parameter; no env var."""
        assert DEFAULT_SEARCH_THRESHOLD == 0.7, (
            f"Threshold changed to {DEFAULT_SEARCH_THRESHOLD}. "
            "Update manifest rationale + review trigger before changing."
        )

    def test_default_search_limit_matches_manifest(self):
        """Rationale: 20 results covers typical lookups without flooding context.
        Review trigger: scale (large KBs).
        Override: method parameter; no env var."""
        assert DEFAULT_SEARCH_LIMIT == 20, (
            f"Limit changed to {DEFAULT_SEARCH_LIMIT}. "
            "Update manifest rationale + review trigger before changing."
        )

    def test_method_parameter_overrides_default(self):
        """Prove the override path works."""
        service = EmbeddingService(...)
        # Default behavior:
        result_default = await service.search("query")
        assert len(result_default) == 20
        # Override via parameter:
        result_overridden = await service.search("query", search_limit=5)
        assert len(result_overridden) == 5
```

---

## 6. Matrix Status

The P3 matrix entries have been updated and now carry concrete enforcement and
cross-layer evidence. Keep this section synchronized with
`docs/architecture/governance/configuration-adoption-matrix.yaml` whenever a
governed default changes.

### `embedding_threshold_search_limit`

```yaml
embedding_threshold_search_limit:
  lifecycle: governed_default    # was: governed_default (same, now with evidence)
  enforcement_evidence:
    - "tests/unit/api/embeddings/test_embedding_search_defaults.py"
  cross_layer_evidence:
    - "docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md §4.1"
  phase: P3
```

### `name_dedup_context_cap`

```yaml
name_dedup_context_cap:
  lifecycle: governed_default    # was: governed_default (same, now with evidence)
  enforcement_evidence:
    - "tests/unit/api/generation/test_name_dedup_defaults.py"
  cross_layer_evidence:
    - "docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md §4.2"
  phase: P3
```

### `sse_connect_retry_defaults`

```yaml
sse_connect_retry_defaults:
  lifecycle: governed_default    # was: governed_default (same, now with evidence)
  enforcement_evidence:
    - "packages/web/components/studio/editor/__tests__/useSessionSocket.test.tsx"
  cross_layer_evidence:
    - "docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md §4.3"
  phase: P3
```

### `governed_defaults_manifest`

```yaml
governed_defaults_manifest:
  lifecycle: governed_default
  enforcement_evidence:
    - "docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md"
    - "tests/unit/api/embeddings/test_embedding_search_defaults.py"
    - "tests/unit/api/generation/test_name_dedup_defaults.py"
    - "packages/web/components/studio/editor/__tests__/useSessionSocket.test.tsx"
  cross_layer_evidence:
    - All P3 entries reference this manifest as cross_layer_evidence
  phase: P3
```

---

## 7. Future Defaults

Any new code default added after this manifest is implemented MUST:

1. Be classified in the Configuration Adoption Matrix.
2. Have a corresponding governed-default entry in this manifest (if
   `lifecycle=governed_default`) OR have an adopted source→resolver→consumer
   chain (if `lifecycle=adopted`).
3. Follow the review-trigger taxonomy (§3).
4. Have a failing-if-changed-without-review test.

The Platform governance checker rejects unclassified matrix entries and, via
CR-AUFG-08-14, rejects future structured material P0/P1 configuration/effect
review findings that are not referenced by the matrix.

---

## 8. RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | Manifest documentiert Entscheidung vor Implementation |
| RULE-10 | ✅ | Jeder Eintrag definiert Test-Pfad; Test-Vorlage vorhanden |
| RULE-11 | ✅ | Keine stillen Defaults — jeder Eintrag hat rationale + review trigger |
| RULE-20 | ✅ | Keine false controls — governed defaults sind explizit nicht user-konfigurierbar |
| ADR-051 | ✅ | Manifest folgt ADR-051 Classification: lifecycle=governed_default |
