// @vitest-environment node
import { describe, expect, it } from "vitest";
import { murmur3_32 } from "./hash";

describe("murmur3_32", () => {
  it("matches the canonical seed-0 vectors", () => {
    expect(murmur3_32("")).toBe(0);
    expect(murmur3_32("hello")).toBe(0x248bfa47);
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