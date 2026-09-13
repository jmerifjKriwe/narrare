# ADR-088 — `kb_suggested` Dormancy: Document the Staged-but-Inert KB-Suggested Enricher (AdoptionPolicy Ruling, Option B)

> **Status:** ✅ Accepted (documentation ADR — no code change)
> **Date:** 2026-09-13
> **Deciders:** User (ruling: option b) · Architecture Agent
> **Related:** ADR-038 (AI Invocation Adoption Contract — `AdoptionPolicy`,
> `KBSuggestedRequirement`, evidence schema), ADR-045 (runtime adoption
> enforcement — program closed around the dormant producer),
> ADR-048 (Q3 structured return — overstatement finding, §Findings 1),
> ADR-067 (reusable KB-context provider — chat seam deferred `kb_suggested`
> to this ruling), INFRA-013, RULE-11/18

---

## Context

### Status quo (verified 2026-09-13)

- `KBSuggestedContextEnricher` is **production-wired exactly once**:
  `apps/api/narrare/_app/dependencies_pipeline.py:86-87` constructs
  `KBSuggestedProviderImpl(session_factory=…)` and appends the enricher to
  the singleton `InvocationPipeline`.
- The enricher is **gated on `AdoptionPolicy`**: the pipeline only requests
  KB-suggested context when `PromptInvocationContext.adoption_policy` is
  non-`None` (`packages/core/narrare_core/ai_invocation/models.py:152`,
  `adoption_policy: AdoptionPolicy | None = None`).
- **No production site constructs an `AdoptionPolicy`.** `rg "AdoptionPolicy\("`
  over `apps/`, `packages/`, `scripts/` (production trees) yields only the
  class definition itself (`models.py:78`). Dormancy is *dormancy by absent
  policy producer* — not a feature flag, not a setting, simply a value no
  caller ever supplies.
- **Effect:** `{{kb_suggested}}` renders empty in all bundled writing modes
  that declare it (10 verified: chat, interactive_session, story_suggest,
  scene_by_scene, extend_chapter, interview, new_chapter, inline_suggest,
  rewrite_selection, co_author). Evidence records carry the default
  `kb_suggested_status`. Degradation is silent and graceful
  (RULE-11-compatible by construction).
- **Staging history:** the enricher landed with the INFRA-013 invocation
  adoption program — `be1a6d46` (P0 invocation adoption pipeline) and
  `9a392cdf` (P1 mode-specific adoption registry and kb_suggested
  enrichment).
- **Program status:** INFRA-013 itself is *complete* — P3 fully implemented
  (`docs/features/infra/INFRA-013-ai-invocation-adoption-contract.md:609-613`),
  P5 27/27 modes adopted (`0863886d`), ADR-045 reports all modes
  `runtime_verified` + `adopted`. The policy producer was never among the
  closing work; the dormant enricher outlived the program that staged it.
- **This ADR is the ruling those markers awaited:** the "ruling pending"
  comments at `apps/api/narrare/chat/_context.py:161` and
  `packages/core/narrare_core/chat/chat_service_core.py:62-63` resolve here.

### Root cause (2× Why)

1. *Symptom:* the `kb_suggested` slot is inert in every mode.
2. *Why?* The enricher runs but no-ops because `adoption_policy` is always
   `None` — no producer exists.
3. *Why is there no producer?* Because activation semantics cannot be
   expressed by the current contract: `KBSuggestedRequirement` offers
   `PROVIDED | BUDGET_REJECTED | NOT_APPLICABLE`
   (`ai_invocation/_enums.py:90-95`) — there is no best-effort level, and
   `PROVIDED` hard-blocks on empty KB (runtime validator Check 3,
   `ai_invocation/validators/runtime.py:102-118`). Building a producer
   before fixing the enum would ship the wrong semantics, so none was built.

### Why a ruling was needed

ADR-067's chat-seam integration deliberately kept `kb_suggested` out of the
KB bundle slots pending an AdoptionPolicy ruling: activate (requires a
producer + expressible semantics) or document dormancy. This ADR records
the decision and the pre-specified activation path.

---

## Decision Drivers

- **Contract expressiveness before activation** — a producer built on an
  enum that cannot say "best-effort" would hard-fail empty-KB projects.
- **RULE-11 (graceful degradation)** — an optional context tier must not
  block invocations when its source is empty.
- **RULE-18 (config in settings, not routers)** — any future activation
  toggle belongs on the settings surface, never hardcoded at a call site.
- **Staged-investment preservation** — the ADR-038/INFRA-013 substrate
  (enricher, registry, checker, evidence schema) is complete and tested;
  inertia is free, deletion is churn.
- **Proportionate ceremony** — a dormant, undesired feature warrants a
  documentation ruling, not code change.

---

## Options Considered

### Option A — Enable now (construct `AdoptionPolicy` with `kb_suggested_requirement=PROVIDED`)

**Rejected.** Runtime validator Check 3
(`ai_invocation/validators/runtime.py:102-118`) fails the whole invocation
when `kb_suggested` is empty under `PROVIDED` — projects with an empty or
sparse KB would hard-block on every writing call. The contract cannot
express best-effort delivery (no `OPTIONAL` level), contradicting both
RULE-11's degradation posture and INFRA-013's own characterization of
`kb_suggested` as "optional/budget-aware"
(`docs/features/infra/INFRA-013-ai-invocation-adoption-contract.md:472`).

### Option B — Document dormancy (chosen)

Accept and record the staged-but-inert state as deliberate; pre-specify the
activation ladder (§ below) so a future enablement is a planned change, not
an archaeology project.

### Option C — Remove the enricher and slot

**Rejected.** Destroys staged ADR-038/INFRA-013 infrastructure with a wide
blast radius: 10 bundled writing templates carrying `{{kb_suggested}}`, the
adoption registry + checker/scorer wiring
(`scripts/architecture/adoption-registry.yaml`,
`scripts/adoption/scorer_modes.py`), the prompt-surface manifest, and the
persistent evidence schema (`kb_suggested_status` column —
`apps/api/alembic/versions/0028_invocation_evidence.py:53`,
`apps/api/narrare/evidence/models.py:43`, `_mappers.py`). Large removal
churn to delete something that costs nothing while inert.

---

## Decision

**We choose Option B.**

Dormancy is the deliberate, documented state: `KBSuggestedContextEnricher`
is production-wired, policy-gated, and has zero producers. Nothing activates
it by construction. It is staged infrastructure awaiting the ladder below —
and unless/until that ladder is walked, the correct runtime behavior is
exactly what ships today: empty slot, default evidence status, no failures.

---

## Enabling-Precondition Ladder (activation path, strictly in order)

- **P1 — `OPTIONAL` enum level + validator/evidence semantics.**
  `KBSuggestedRequirement` currently conflates requirement levels with
  runtime outcomes (§Findings 2). Add `OPTIONAL` with defined semantics:
  validator does *not* run Check 3 for it (no hard block on empty);
  evidence distinguishes "not attempted (optional, absent)" from
  `MISSING`/`NOT_APPLICABLE`.
- **P2 — mode→policy producer keyed off `adoption-registry.yaml`.**
  A producer that constructs `AdoptionPolicy` from per-mode registry state
  (which modes want `kb_suggested`, at which level). No producer, no
  activation — P1 without P2 changes nothing at runtime.
- **P3 — settings surface: `ai_invocation.kb_suggested` ∈ off · optional ·
  required, default `off`.** RULE-18-governed setting in the same class as
  the `kb_characters` KB-slot family — never hardcoded at a router or
  factory call site. Default `off` preserves today's behavior until a
  deliberate operator/user choice changes it.
- **P4 — latency/quality eval before any writing-default.** Before flipping
  any default away from `off`, measure the per-invocation cost of the extra
  KB fetch + enrichment pass and the output-quality delta. The enricher
  adds a read-only DB query per invocation (`dependencies_pipeline.py:83-85`)
  — that price must be shown to buy quality before it becomes default.

---

## Findings Recorded (verified during this ruling)

1. **`kb_suggested_structured` has no consumer.** `KB_STRUCTURED_KEY`
   (`ai_invocation/enrichers/kb_suggested.py:49`) is written into
   `dynamic_inputs` and read by nothing outside `kb_suggested.py` itself.
   ADR-048 Q3 (:896-910 — "enables precise budget decisions and improves
   evidence correlation quality") and the module docstring overstate
   current value: the structured payload is staged for *future* budget/
   evidence use only.
2. **`BUDGET_REJECTED` enum conflation.** `KBSuggestedStatus`
   (`_enums.py:31`, a delivery *status*) and `KBSuggestedRequirement`
   (`_enums.py:94`, a *requirement level*) share the `BUDGET_REJECTED`
   value — a runtime outcome encoded as a requirement. This is the root of
   the P1 expressiveness gap; ADR-038:247 bakes `budget_rejected` into the
   evidence Literal. Resolving it is P1 work, *not* an independent cleanup
   to do out of order.
3. **Registry static-target vs runtime gap is intentional.** Checker/report
   vocabulary deliberately separates `static_verified` / `runtime_verified`
   / `adopted` (Review-03 semantics refresh, INFRA-013 doc :616-618). Do
   **not** "fix" the gap by tightening static targets to runtime semantics.
4. **Ruling-package corrections (recorded for audit trail):** the delivered
   ruling said "INFRA-013 P3 outstanding" and "~7 template modes"; the
   verified record shows INFRA-013 P3 + P5 complete (`0863886d`, feature
   doc :609-615) and **10** bundled modes carrying `{{kb_suggested}}`.
   Substance is recorded with the verified numbers.

---

## Consequences

**Positive:**

- Dormancy is an auditable decision instead of an unexplained accident.
- The activation path (P1–P4) is pre-specified with the root-cause fix
  (enum semantics) ordered first.
- The ADR-048 Q3 overstatement and the enum conflation are on record with
  file:line evidence.
- Zero code churn; zero RULE-XX impact; no behavior change.

**Negative / Tradeoffs:**

- The enum conflation and the consumer-less structured payload persist
  until P1/a consumer materializes — accepted, because fixing them now
  would be activation work without an activation demand.
- "Ruling pending" comments (`chat/_context.py:161`,
  `chat_service_core.py:62-63`) now resolve to this ADR; update them
  opportunistically on next touch (deliberately *not* in this docs-only
  ruling).

**Constraints introduced:** none to CONSTRAINTS.md. RULE-11 and RULE-18 are
referenced as governing the future P1/P3 semantics; no rule text changes.

---

## Review Triggers

- [ ] When a user/product demand asks for KB-suggested context in prompts —
      start the ladder at P1; do not skip to a producer.
- [ ] When a budget resolver or evidence consumer starts reading
      `kb_suggested_structured` — re-verify Findings 1 and update ADR-048 Q3.
- [ ] When an enum-cleanup PR touches `ai_invocation/_enums.py` — fold the
      P1 `OPTIONAL` level in *only if* activation is on the roadmap.
- [ ] 2026-12-13 (3-month check): dormancy still intentional? Re-affirm or
      schedule the ladder.
