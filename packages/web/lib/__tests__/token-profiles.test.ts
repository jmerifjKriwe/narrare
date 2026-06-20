/**
 * Frontend token-profile contract parity test (CR-08 P1 D1/D3/D4).
 *
 * The frontend cannot import Python directly, so it keeps compile-time
 * TypeScript literals that mirror `packages/core/narrare_core/llm/token_profiles.py`.
 * This test pins those literals to the policy table so any independent
 * add/remove/rename is caught. Platform adds the cross-layer assertion.
 *
 * Policy: docs/architecture/governance/cr-08-p1-token-limits-and-suitability-policy.md
 */

import {
  PROFILE_OUTPUT_LIMITS,
  TOKEN_OUTPUT_ABSOLUTE_MAX,
  TOKEN_OUTPUT_UX_RECOMMENDED_MAX,
  TOKEN_PRESET_PROFILE_VALUES,
  TOKEN_PROFILE_VALUES,
} from "@/lib/token-profiles";

describe("frontend token-profile contract (CR-08 P1)", () => {
  it("exposes exactly the five public profile values in policy order", () => {
    expect([...TOKEN_PROFILE_VALUES]).toEqual([
      "quick",
      "balanced",
      "long_texts",
      "comprehensive",
      "custom",
    ]);
  });

  it("never includes the retired conservative alias", () => {
    expect([...TOKEN_PROFILE_VALUES]).not.toContain("conservative");
  });

  it("lists exactly the four preset profiles (custom excluded)", () => {
    expect([...TOKEN_PRESET_PROFILE_VALUES]).toEqual([
      "quick",
      "balanced",
      "long_texts",
      "comprehensive",
    ]);
    expect([...TOKEN_PRESET_PROFILE_VALUES]).not.toContain("custom");
  });

  it("maps preset profiles to the policy output limits", () => {
    expect(PROFILE_OUTPUT_LIMITS).toEqual({
      quick: 500,
      balanced: 2000,
      long_texts: 8000,
      comprehensive: 16000,
    });
    // custom is a raw mode and has NO preset entry
    expect(PROFILE_OUTPUT_LIMITS).not.toHaveProperty("custom");
    expect(PROFILE_OUTPUT_LIMITS).not.toHaveProperty("conservative");
  });

  it("exposes the absolute API hard max (131072)", () => {
    expect(TOKEN_OUTPUT_ABSOLUTE_MAX).toBe(131072);
  });

  it("exposes the UX recommended slider range (16000)", () => {
    expect(TOKEN_OUTPUT_UX_RECOMMENDED_MAX).toBe(16000);
  });
});
