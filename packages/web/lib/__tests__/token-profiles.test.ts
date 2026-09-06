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
  getPresetOutputLimit,
  isCustomTokenProfile,
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
    // long_texts raised 8000 → 16000 with Core (structured extraction on
    // thinking models hit the old ceiling before generating output), then
    // 16000 → 32000 with Core (benchmark: ch-11 KB extraction on the densest
    // reveal chapter exhausted the 16000 ceiling), then 32000 → 64000 with
    // Core (extraction retries=3 count against the cumulative pydantic-ai
    // output_tokens_limit; the growing entity-ID roster inflates payloads).
    expect(PROFILE_OUTPUT_LIMITS).toEqual({
      quick: 500,
      balanced: 2000,
      long_texts: 64000,
      comprehensive: 64000,
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

  describe("getPresetOutputLimit", () => {
    it("returns null for null/undefined input", () => {
      expect(getPresetOutputLimit(null)).toBeNull();
      expect(getPresetOutputLimit(undefined)).toBeNull();
    });

    it("returns the output limit for known preset profiles", () => {
      expect(getPresetOutputLimit("quick")).toBe(500);
      expect(getPresetOutputLimit("balanced")).toBe(2000);
      expect(getPresetOutputLimit("long_texts")).toBe(64000);
      expect(getPresetOutputLimit("comprehensive")).toBe(64000);
    });

    it("returns null for custom or unknown profiles", () => {
      expect(getPresetOutputLimit("custom")).toBeNull();
      expect(getPresetOutputLimit("nonexistent")).toBeNull();
    });
  });

  describe("isCustomTokenProfile", () => {
    it("returns true only for the 'custom' profile", () => {
      expect(isCustomTokenProfile("custom")).toBe(true);
      expect(isCustomTokenProfile("quick")).toBe(false);
      expect(isCustomTokenProfile(null)).toBe(false);
      expect(isCustomTokenProfile(undefined)).toBe(false);
    });
  });
});
