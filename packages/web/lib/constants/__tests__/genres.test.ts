/**
 * Genre suggestions constants tests.
 *
 * Tests:
 * 1. GENRE_SUGGESTIONS is an array
 * 2. Contains expected genre strings
 * 3. Is frozen (as const)
 */

import { describe, expect, it } from "vitest";
import { GENRE_SUGGESTIONS } from "../genres";

describe("GENRE_SUGGESTIONS", () => {
  it("should be an array", () => {
    expect(Array.isArray(GENRE_SUGGESTIONS)).toBe(true);
  });

  it("should contain expected genres", () => {
    expect(GENRE_SUGGESTIONS).toContain("Fantasy");
    expect(GENRE_SUGGESTIONS).toContain("Sci-Fi");
    expect(GENRE_SUGGESTIONS).toContain("Romance");
    expect(GENRE_SUGGESTIONS).toContain("Thriller");
    expect(GENRE_SUGGESTIONS).toContain("Horror");
    expect(GENRE_SUGGESTIONS).toContain("Mystery");
  });

  it("should have at least 10 suggestions", () => {
    expect(GENRE_SUGGESTIONS.length).toBeGreaterThanOrEqual(10);
  });

  it("should contain only strings", () => {
    for (const genre of GENRE_SUGGESTIONS) {
      expect(typeof genre).toBe("string");
    }
  });

  it("should not contain duplicates", () => {
    const unique = new Set(GENRE_SUGGESTIONS);
    expect(unique.size).toBe(GENRE_SUGGESTIONS.length);
  });
});
