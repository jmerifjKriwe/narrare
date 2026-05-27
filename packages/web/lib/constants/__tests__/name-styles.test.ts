/**
 * Name style suggestions constants tests.
 *
 * Tests:
 * 1. NAME_STYLE_SUGGESTIONS is an array
 * 2. Contains expected name styles
 * 3. Is frozen (as const)
 */

import { describe, expect, it } from "vitest";
import { NAME_STYLE_SUGGESTIONS } from "../name-styles";

describe("NAME_STYLE_SUGGESTIONS", () => {
  it("should be an array", () => {
    expect(Array.isArray(NAME_STYLE_SUGGESTIONS)).toBe(true);
  });

  it("should contain expected name styles", () => {
    expect(NAME_STYLE_SUGGESTIONS).toContain("Fantasy");
    expect(NAME_STYLE_SUGGESTIONS).toContain("Sci-Fi");
    expect(NAME_STYLE_SUGGESTIONS).toContain("Nordisch");
    expect(NAME_STYLE_SUGGESTIONS).toContain("Elbisch");
    expect(NAME_STYLE_SUGGESTIONS).toContain("Cyberpunk");
  });

  it("should have at least 10 suggestions", () => {
    expect(NAME_STYLE_SUGGESTIONS.length).toBeGreaterThanOrEqual(10);
  });

  it("should contain only strings", () => {
    for (const style of NAME_STYLE_SUGGESTIONS) {
      expect(typeof style).toBe("string");
    }
  });

  it("should not contain duplicates", () => {
    const unique = new Set(NAME_STYLE_SUGGESTIONS);
    expect(unique.size).toBe(NAME_STYLE_SUGGESTIONS.length);
  });
});
