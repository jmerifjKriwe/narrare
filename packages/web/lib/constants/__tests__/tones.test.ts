/**
 * Bundled tones constants tests.
 *
 * Tests:
 * 1. BUNDLED_TONES is an array
 * 2. Each tone has value and label
 * 3. Labels follow i18n key pattern
 * 4. BundledToneValue type covers all values
 */

import { describe, expect, it } from "vitest";
import type { BundledToneValue } from "../tones";
import { BUNDLED_TONES } from "../tones";

describe("BUNDLED_TONES", () => {
  it("should be an array", () => {
    expect(Array.isArray(BUNDLED_TONES)).toBe(true);
  });

  it("should have at least 5 tones", () => {
    expect(BUNDLED_TONES.length).toBeGreaterThanOrEqual(5);
  });

  it("should have value and label for each tone", () => {
    for (const tone of BUNDLED_TONES) {
      expect(tone).toHaveProperty("value");
      expect(tone).toHaveProperty("label");
      expect(typeof tone.value).toBe("string");
      expect(typeof tone.label).toBe("string");
    }
  });

  it("should have labels following i18n key pattern (tones.X)", () => {
    for (const tone of BUNDLED_TONES) {
      expect(tone.label).toMatch(/^tones\./);
    }
  });

  it("should contain expected tone values", () => {
    const values = BUNDLED_TONES.map((t) => t.value);
    expect(values).toContain("balanced");
    expect(values).toContain("dramatic");
    expect(values).toContain("humorous");
    expect(values).toContain("suspenseful");
    expect(values).toContain("dark");
  });

  it("should have unique values", () => {
    const values = BUNDLED_TONES.map((t) => t.value);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
  });

  it("BundledToneValue should match tone values", () => {
    // Type-level check — values are assignable to BundledToneValue
    const values: BundledToneValue[] = BUNDLED_TONES.map((t) => t.value);
    expect(values.length).toBe(BUNDLED_TONES.length);
  });
});
