import { describe, expect, it } from "vitest";
import nextConfig from "../next.config";

// Coupling guard: the Next.js proxy body-clone buffer
// (experimental.proxyClientMaxBodySize) must stay >= the import API total
// guard MAX_TOTAL_BYTES (apps/api/narrare/importing/constants.py, 25 MiB)
// plus the multipart envelope headroom (1 MiB) => floor is 26 MiB.
// If the API guard MAX_TOTAL_BYTES changes, update this floor in the same PR.
const MIN_BODY_BYTES = 27_262_976; // 26 MiB = 25 MiB MAX_TOTAL_BYTES + 1 MiB envelope

const UNIT_MULTIPLIERS: Record<string, number> = {
  b: 1,
  kb: 1024,
  mb: 1024 ** 2,
  gb: 1024 ** 3,
};

function toBytes(size: number | string): number {
  if (typeof size === "number") {
    return size;
  }
  const match = size.trim().match(/^([\d.]+)\s*([a-z]+)$/iu);
  if (!match) {
    throw new Error(`Unparseable size limit: ${String(size)}`);
  }
  const value = Number.parseFloat(match[1] as string);
  const unit = (match[2] as string).toLowerCase();
  const multiplier = UNIT_MULTIPLIERS[unit];
  if (multiplier === undefined) {
    throw new Error(`Unknown size unit: ${unit}`);
  }
  return value * multiplier;
}

describe("next.config proxy body size (ADR-091)", () => {
  it("defines experimental.proxyClientMaxBodySize", () => {
    expect(nextConfig.experimental?.proxyClientMaxBodySize).toBeDefined();
  });

  it("proxy body cap is >= 26 MiB (MAX_TOTAL_BYTES 25 MiB + envelope)", () => {
    const configured = nextConfig.experimental?.proxyClientMaxBodySize;
    expect(configured).toBeDefined();
    const bytes = toBytes(configured as number | string);
    expect(bytes).toBeGreaterThanOrEqual(MIN_BODY_BYTES);
  });
});
