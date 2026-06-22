import { describe, expect, it } from "vitest";
import type { BetaFeedbackItem } from "@/lib/api/analysis";
import { betaReaderGroundedAdapter, isBetaReaderGrounded } from "../../adapters/beta-reader";

const item: BetaFeedbackItem = {
  category: "pacing",
  severity: "moderate",
  location: "para 3",
  title: "Slow middle",
  description: "The middle drags.",
  suggestion: "Consider tightening the description.",
  text_excerpt: "The long winding road stretched...",
};

describe("betaReaderGroundedAdapter", () => {
  it("returns null for current-schema feedback (no grounded A->B pair)", () => {
    expect(betaReaderGroundedAdapter(item)).toBeNull();
  });

  it("isBetaReaderGrounded is false for current schema", () => {
    expect(isBetaReaderGrounded(item)).toBe(false);
  });

  it("returns null even when suggestion + text_excerpt are both present", () => {
    // suggestion is prose advice, NOT a verbatim replacement — must NOT be
    // treated as a grounded revision (CR-AUFG-07-18 out-of-scope: fabrication).
    expect(betaReaderGroundedAdapter(item)).toBeNull();
  });

  it("returns null for a minimal feedback item too", () => {
    const minimal: BetaFeedbackItem = {
      category: "prose",
      severity: "minor",
      location: null,
      title: "Wordy",
      description: "Verbose sentence.",
      suggestion: null,
      text_excerpt: null,
    };
    expect(betaReaderGroundedAdapter(minimal)).toBeNull();
  });
});
