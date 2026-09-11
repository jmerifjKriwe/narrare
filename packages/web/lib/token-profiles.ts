/**
 * Frontend compile-time token-profile contract (CR-08 P1).
 *
 * Mirrors `packages/core/narrare_core/llm/token_profiles.py`. The frontend
 * cannot import Python directly, so it keeps these literals and proves parity
 * through `lib/__tests__/token-profiles.test.ts` (and Platform's cross-layer
 * contract tests). Any add/remove/rename here MUST be reflected in Core and
 * Backend and will fail the parity tests otherwise.
 *
 * Policy: docs/architecture/governance/cr-08-p1-token-limits-and-suitability-policy.md
 *
 * Runtime UI options should prefer the API `metadata.catalogue` payload
 * (see `TokenLimitsResponse.metadata`); these constants are the
 * compile-time fallback and the parity anchor.
 */

import type { TokenLimitProfile } from "@/types";

/**
 * Largest raw output limit accepted by the API before provider calibration.
 * (CR-08 P1 D4 — Absolute API hard max.)
 */
export const TOKEN_OUTPUT_ABSOLUTE_MAX = 131072 as const;

/**
 * Recommended UX slider range. NOT a provider or API hard maximum.
 * (CR-08 P1 D4 — UX recommended slider range.)
 */
export const TOKEN_OUTPUT_UX_RECOMMENDED_MAX = 16000 as const;

/**
 * Ordered public profile vocabulary. `conservative` is intentionally absent —
 * it is a retired legacy alias normalized to `balanced` at the Backend read
 * boundary and never emitted to clients. (CR-08 P1 D1/D2.)
 */
export const TOKEN_PROFILE_VALUES: readonly TokenLimitProfile[] = [
  "quick",
  "balanced",
  "long_texts",
  "comprehensive",
  "custom",
] as const;

/**
 * Profiles that carry a fixed preset output limit. `custom` is a raw manual
 * mode and is intentionally absent. (CR-08 P1 D3.)
 */
export const TOKEN_PRESET_PROFILE_VALUES: readonly TokenLimitProfile[] = [
  "quick",
  "balanced",
  "long_texts",
  "comprehensive",
] as const;

/**
 * Preset output-token limits for non-custom profiles. (CR-08 P1 D1 table.)
 * `custom` has no entry — its effective limit comes from `output_limit`.
 */
export const PROFILE_OUTPUT_LIMITS: Readonly<Record<string, number>> = {
  quick: 500,
  balanced: 2000,
  // Raised 8000 → 16000 with Core (structured extraction on thinking models
  // hit the old ceiling before generating output), then 16000 → 32000 with
  // Core (benchmark: ch-11 KB extraction on the densest reveal chapter
  // exhausted the 16000 ceiling), then 32000 → 64000 with Core (extraction
  // retries=3 count against the cumulative pydantic-ai output_tokens_limit;
  // the growing entity-ID roster inflates each structured payload).
  long_texts: 64000,
  comprehensive: 64000,
} as const;

/**
 * Return the preset output limit for a non-custom profile, or `null` for
 * `custom` / unknown values. Mirrors Core's `get_preset_output_limit`.
 */
export function getPresetOutputLimit(profile: string | undefined | null): number | null {
  if (profile == null) return null;
  const value = PROFILE_OUTPUT_LIMITS[profile];
  return typeof value === "number" ? value : null;
}

/**
 * True when the profile selects the raw manual output-limit mode.
 * (CR-08 P1 D3.)
 */
export function isCustomTokenProfile(profile: string | undefined | null): boolean {
  return profile === "custom";
}
