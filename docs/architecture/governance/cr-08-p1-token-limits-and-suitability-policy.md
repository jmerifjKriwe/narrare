# CR-08 P1 Policy — Token Profiles, Model Limits, and Suitability

> **Status:** implemented evidence recorded for CR-08 P1; ADR-051 remains proposed
> **Applies to:** CR-AUFG-08-03, CR-AUFG-08-07, CR-AUFG-08-10, CR-AUFG-08-11 / FIND-013
> **Parent spec:** `docs/features/remediation/cr-08-configuration-effect-drift.md`
> **Constraint focus:** RULE-03, RULE-07, RULE-10, RULE-11, RULE-17, RULE-20, RULE-22

---

## Root Cause

**Symptom:** Token settings expose profiles, slider limits, and model suitability hints that
do not share one cross-layer contract.

**Why #1:** Core, Backend, and Frontend each own part of the vocabulary or caps, so UI/API
parity depends on manual synchronization.

**Why #2:** `models.dev` metadata is treated as a lookup result, not as evidence with source
freshness. Unknown/offline/stale states therefore look the same as calibrated states.

**Design:** P1 establishes a typed Core contract, Backend schema metadata, Frontend parity
tests, and explicit warning/blocking policy. No layer may imply that a setting takes effect
unless runtime enforcement and metadata evidence are present.

This document records the implemented P1 evidence. It does **not** accept ADR-051 or
make ADR-051 the active constitutional contract; ADR-051 remains proposed until the ADR
index records acceptance or supersession.

---

## Implementation Evidence (2026-06-20)

P1 implementation is complete with enforcement and cross-layer evidence. Later CR-08
P2/P3/P4 work is outside this policy and is now recorded as implemented/enforced in
the remediation spec; final CR-08 resolution still waits on ADR-051 acceptance or
supersession.

| Area | Implemented evidence |
|---|---|
| Core | `packages/core/narrare_core/llm/token_profiles.py`, `model_calibration.py`, and `model_suitability.py` define the vocabulary, calibration statuses, and suitability severities. Reported validation: 573 Core LLM tests passed, with lint/typecheck/architecture OK. |
| Backend | Token-limit validation derives from Core, rejects new `conservative`, normalizes legacy `conservative`, supports custom raw limits, and exposes profile/cap/calibration/suitability metadata. Reported validation: 2191 Backend/settings tests passed. |
| Frontend | `conservative` removed from UI types/options, custom limits above 16k supported, and calibration/suitability warnings render in settings/editor token controls. Reported validation: 30 targeted tests plus type-check, lint, and file-size check passed. |
| Platform | Cross-layer contract tests and matrix evidence gate cover profile vocabulary, cap parity, calibration metadata, and suitability warnings/blocks. Reported validation: matrix check PASS, targeted P1 suite PASS, and `just check` PASS after security dependency updates. |
| Docs | This policy and the CR-08 remediation spec distinguish implemented P1 evidence from later P2/P3/P4 evidence and from proposed-only ADR-051 status. |

---

## Decisions

### D1 — Authoritative Token Profile Vocabulary

The public token profile vocabulary is exactly:

| Profile | Public? | Preset output limit | Semantics |
|---|---:|---:|---|
| `quick` | ✅ | `500` | Short answers, names, labels, inline suggestions. |
| `balanced` | ✅ | `2000` | General chat, summaries, moderate structured output. |
| `long_texts` | ✅ | `8000` | Chapter prose, planning, extraction, longer analysis. |
| `comprehensive` | ✅ | `16000` | Cross-chapter or exhaustive reasoning output. |
| `custom` | ✅ | none | Manual raw `output_limit` mode. |
| `conservative` | ❌ | none | Legacy alias only; never emitted or accepted as a new write value. |

Implementation contract:

- Core owns the typed vocabulary in `packages/core/narrare_core/llm/token_profiles.py`.
  That module must define the enum/type, ordered public values, preset output limits, and
  custom-mode helpers. `model_config.py`, `run_limits.py`, and intent-profile validation
  must import from this module rather than maintaining local string sets.
- Backend schemas must validate against the same Core enum/values. Backend must not keep an
  independent regex that can drift.
- Frontend may keep TypeScript literals because it cannot import Python directly, but it must
  prove parity through contract tests against Backend/Core metadata. Runtime UI options should
  be populated from API metadata where practical; compile-time constants must be tested.

### D2 — `conservative` Removal and Legacy Stabilization

`conservative` is removed from the public contract.

Policy:

- New API writes with `token_profile="conservative"` must be rejected by schema validation.
- Existing persisted `conservative` values must be normalized at the Backend read boundary to
  `balanced` and must not be re-emitted to clients.
- Backend implementation must include a cleanup path for existing JSONB settings. If a data
  migration is used, it rewrites stored `conservative` to `balanced`; downgrade may be a
  documented no-op because the invalid public value is intentionally retired.
- Frontend removes labels/options/tests for `conservative`.

Rationale: `conservative` never had a canonical output-limit preset in Core and currently
creates false cross-layer vocabulary. Mapping the legacy alias to `balanced` is the safest
stabilization because `balanced` is the existing default and avoids silently shortening user
outputs to `quick`.

### D3 — Exact `custom` Semantics

`custom` is a manual raw output-limit mode, not an independent preset.

Rules:

- `custom` has no entry in preset output-limit maps.
- When `token_profile == "custom"`, the effective requested output limit comes from
  `output_limit` / `ResolvedModelConfig.max_tokens` / `OutputBudgetDecision.budget.max_tokens`.
- When a preset profile is selected, Backend returns the preset output limit unless an explicit
  request also sets `output_limit` and `token_profile="custom"`.
- Updating `output_limit` without a preset profile switches the resolved profile to `custom`.
- Runtime limit resolution still applies model-ceiling calibration before invoking the model.

### D4 — Slider/API Max Parity

There are two distinct caps:

| Cap | Value/source | Meaning | UI policy |
|---|---|---|---|
| Absolute API hard max | `131072` from a named Backend/Core contract constant | Largest value accepted by API before provider calibration. | Frontend must not impose a lower hard cap without exposing full custom input. |
| UX recommended slider range | `16000`, equal to `comprehensive` preset | Comfortable preset-scale range. | Allowed only if labelled as recommended/UX-protective, not as model maximum. |
| Model-derived max | `models.dev` output limit when known and fresh/stale-labelled | Provider/model ceiling used for runtime cap/warnings. | May cap the UI only when source is known; stale/offline/unknown must show warning labels. |

Frontend may keep a 16k slider as a UX-protective recommended range only if the UI also offers
custom numeric entry up to the effective hard max and labels the slider accordingly. A 16k-only
control that hides API/model capacity is not P1-compliant.

### D5 — Model-Limit Calibration Policy

Core must expose a typed limit-resolution result instead of only `ModelLimits | None`.

Required statuses:

| Status | Meaning | Effective behaviour | User/API evidence |
|---|---|---|---|
| `known_fresh` | Model found in fresh cache or fresh remote fetch. | Cap requested output to provider output max. | Show calibrated max and source timestamp. |
| `known_stale` | Model found in stale cache after refresh failed/unavailable. | Cap to stale provider max, but mark stale. | Warning: calibration may be outdated. |
| `unknown_model` | Metadata source available, but selected model has no limits. | Do not claim calibration; use requested value up to absolute API max. | Warning: model limit unknown. |
| `offline_no_cache` | Remote unavailable and no usable cache. | Do not claim calibration; runtime uses requested value up to absolute API max. | Warning: offline/unverified. |
| `invalid_metadata` | Cache/remote data malformed for the limit fields. | Treat as uncalibrated; no silent fallback to a fake ceiling. | Warning and structured log/evidence. |

Known too-high requested limits are capped at the model boundary and exposed as warnings/effective
limits. Unknown/offline/stale states must never be displayed as calibrated.

### D6 — Model Suitability Policy

Suitability is evaluated per invocation intent using `get_intent_profile(intent)` plus model
metadata. It is not a routing override by itself.

Minimum viable output floors:

| Intent output profile | Recommended output | Minimum viable floor |
|---|---:|---:|
| `quick` | `500` | `128` |
| `balanced` | `2000` | `512` |
| `long_texts` | `8000` | `2048` |
| `comprehensive` | `16000` | `4096` |

Severity boundaries:

| Severity | Conditions | Behaviour |
|---|---|---|
| Advisory | Model metadata is adequate, but the model's known/declared capability tier is below the intent recommendation or unknown for non-critical intents. | Allow call; expose recommendation in API/UI. |
| Warning | Metadata is stale/offline/unknown; requested limit exceeds known output ceiling but remains above the minimum floor after cap; context/output may truncate quality. | Allow call; expose warning and effective cap. |
| Hard block | Provider/key/model cannot be used; model is known not to support text generation; known output max is below the minimum viable floor for the intent; context window cannot hold required input plus minimum output. | Block before the model call with typed error. |

Hard blocks are limited to impossible or unsafe calls. Unknown capability alone is never a hard
block; it is warning/advisory depending on the intent and metadata status.

---

## Alternatives Considered

| Option | Description | Pros | Cons | Decision |
|---|---|---|---|---|
| A | Keep `conservative` as a public profile and add missing Core mapping. | Lowest visible migration work. | Preserves stale vocabulary and invents semantics for a profile that never had a canonical output contract. | Rejected. |
| B | Expose only presets and remove raw custom output limit. | Simple UI and fewer caps. | Removes a real user control delivered by P0 and cannot support long-output models. | Rejected. |
| C | One Core vocabulary plus Backend metadata and Frontend parity tests. | Fixes drift at the contract boundary; supports UI and API clients; preserves custom power-user path. | Requires cross-layer implementation and contract tests. | Chosen. |
| D | Hard-reject every request above current selected model max. | Avoids provider failures. | Too strict for global settings and stale metadata; blocks valid future/model-switch scenarios. | Rejected. Cap+warn is chosen except impossible/unsafe calls. |

---

## Sustainability Check

1. **Correct in 3 months:** Yes — vocabulary is typed and parity-tested; metadata source status is explicit.
2. **Avoids hard-to-undo coupling:** Yes — Core owns domain policy, Backend exposes service/API metadata, Frontend consumes and verifies parity.
3. **Simplest correct solution:** Yes — no new dependency; adds contracts/tests where drift occurred.
4. **Design intent visible:** Yes — warnings/caps distinguish requested, effective, and calibrated values.

---

## Implementation Handoff

### Core

1. Add `packages/core/narrare_core/llm/token_profiles.py` with:
   - `TokenLimitProfile` enum or literal contract for the five public profiles.
   - Ordered public values: `quick`, `balanced`, `long_texts`, `comprehensive`, `custom`.
   - Preset output map excluding `custom`.
   - Constants: `TOKEN_OUTPUT_ABSOLUTE_MAX = 131072`, `TOKEN_OUTPUT_UX_RECOMMENDED_MAX = 16000`.
   - Helpers for preset/custom resolution and legacy normalization.
2. Refactor `model_config.py`, `run_limits.py`, and `intent_profiles.py` to consume the contract.
3. Replace `get_model_limits`-only semantics with a typed calibration result while preserving existing callers through a compatibility wrapper if needed.
4. Add `model_suitability.py` evaluator using intent profile + limit metadata + requested/effective output.

Core DoD/tests:

- Unit tests prove profile values and preset limits exactly match policy.
- `custom` uses raw output limit and has no preset entry.
- `conservative` is not a valid public profile; legacy normalization maps it to `balanced` only at compatibility boundaries.
- Calibration tests cover known cap, stale warning, unknown model, offline no-cache, invalid metadata.
- Suitability tests cover advisory, warning, hard block, unknown/offline, and provider-too-small cases.

### Backend

1. Update token-limit contracts/schemas to import/derive valid profiles from Core rather than regex duplication.
2. Reject new `conservative` writes; normalize existing persisted `conservative` reads to `balanced` and do not emit it.
3. Add/update response metadata so clients can see:
   - public profile values and preset limits,
   - absolute max and UX recommended max,
   - requested vs effective output limit,
   - calibration status/source timestamp,
   - suitability warnings/blocks where applicable.
4. Apply cleanup for persisted legacy `conservative` data if implementation discovers stored rows in current JSONB settings.
5. Keep service-layer API as the public boundary; no Frontend-specific router logic.

Backend DoD/tests:

- Schema validation rejects `conservative` and accepts exactly the five public values.
- Resolved limits never emit `conservative`.
- Updating `output_limit` makes the resolved profile `custom` unless a preset request explicitly overrides it.
- API contract tests compare schema/profile metadata with Frontend constants/types.
- Integration tests cover calibration metadata and warning exposure for unknown/offline/provider-too-small states.

### Frontend

1. Remove `conservative` from `TokenLimitProfile`, option lists, labels, and tests.
2. Consume token settings metadata from Backend or prove constants match via contract tests.
3. Represent `custom` as manual raw output-limit mode.
4. Replace 16k hard-only slider semantics with:
   - labelled recommended slider range up to 16k, and
   - custom numeric entry up to API/model effective max, or a model-derived slider max when known.
5. Display calibration/suitability labels. Stale/offline/unknown must not look calibrated.

Frontend DoD/tests:

- Token profile options equal exactly `quick`, `balanced`, `long_texts`, `comprehensive`, `custom`.
- UI tests prove custom manual limits above 16k are possible up to the exposed hard/effective max.
- Warning labels render for stale/offline/unknown/provider-too-small metadata.
- No test expects `conservative`.

### Platform

1. Add cross-layer contract tests for Core profile values, Backend schema/metadata, and Frontend constants.
2. Add regression tests for model calibration source statuses and suitability severity boundaries.
3. Keep Configuration Adoption Matrix P1 entries as `formal_finding` until implementation-on-disk plus enforcement evidence exists.
4. Run normal gates; do not bypass hooks.

Platform DoD/tests:

- Contract test fails if any layer adds/removes/renames a token profile independently.
- Contract test fails if Frontend hard caps drift from Backend/Core metadata without UX-protective label evidence.
- Governance matrix remains valid and P1 entries move to `adopted` only with evidence paths.

### Docs

1. Update user/developer docs only after implementation evidence exists.
2. Do not mark CR-AUFG-08-03/07/10/11 resolved until implementation, enforcement tests, and cross-layer evidence are present.

Docs DoD:

- P1 closure references concrete files/tests, not this policy alone.
- Status language distinguishes requested limit, effective cap, and calibration source.
