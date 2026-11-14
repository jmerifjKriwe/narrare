// @vitest-environment node
import { describe, expect, it } from "vitest";
import { murmur3_32 } from "./hash";

describe("murmur3_32", () => {
  it("matches the canonical seed-0 vectors", () => {
    expect(murmur3_32("")).toBe(0);
    expect(murmur3_32("hello")).toBe(0x248bfa47);
  });
  it("matches known-answer vectors for UTF-8 keys and non-zero seeds", () => {
    // Expected values from Python mmh3 5.3.1 (unsigned 32-bit), an independent
    // reference: they pin the UTF-8 encoding and the seed parameter in CI.
    const vectors: Array<[string, number, number]> = [
      ["Schöne Grüße", 0, 0xfb388f98],
      ["📚 Buch", 0, 0xeb249011],
      ["日本語のタイトル", 0, 0x22c831ee],
      ["hello", 1, 0xbb4abcad],
      ["Dead Signal", 42, 0x51af5ab2],
      ["Schöne Grüße", 42, 0xbc116e26],
    ];
    for (const [key, seed, expected] of vectors) {
      expect(murmur3_32(key, seed)).toBe(expected);
    }
  });
  it("is deterministic and stays an unsigned 32-bit integer", () => {
    for (const s of ["Dead Signal", "Echo", "Im Stillen Wald", "x".repeat(200)]) {
      const a = murmur3_32(s);
      expect(a).toBe(murmur3_32(s));
      expect(Number.isInteger(a)).toBe(true);
      expect(a).toBeGreaterThanOrEqual(0);
      expect(a).toBeLessThanOrEqual(0xffffffff);
    }
  });
});
