import { describe, expect, it } from "vitest";
import type {
  AIDiffMode,
  AIDiffSegment,
  AIDiffSegmentKind,
  AIDiffState,
  AIDiffViewModel,
} from "../contracts";
// Renamed aliases verify the barrel's TYPE re-exports without colliding with the
// direct contracts imports above (duplicate identifiers are a TS error).
import type {
  AIDiffMode as BarrelMode,
  AIDiffSegment as BarrelSegment,
  AIDiffState as BarrelState,
  AIDiffViewModel as BarrelViewModel,
} from "../index";
import {
  betaReaderGroundedAdapter,
  coAuthorChangeAdapter,
  isBetaReaderGrounded,
  kbEnhanceFieldAdapter,
  rewriteAdapter,
  segmentize,
} from "../index";

describe("ai-diff contracts", () => {
  it("exposes the documented AIDiffState values", () => {
    const states: AIDiffState[] = ["suggested", "accepted", "rejected", "unchanged"];
    expect(states).toHaveLength(4);
  });

  it("exposes the documented AIDiffSegmentKind values", () => {
    const kinds: AIDiffSegmentKind[] = ["added", "removed", "unchanged"];
    expect(kinds).toHaveLength(3);
  });

  it("a field-mode view model has no segments (structural invariant)", () => {
    const vm: AIDiffViewModel = {
      id: "kb-role",
      mode: "field" satisfies AIDiffMode,
      segments: [],
      originalFull: "Mentor",
      suggestedFull: "Wise mentor",
      label: "Role",
      provisional: false,
    };
    expect(vm.mode).toBe("field");
    expect(vm.segments).toHaveLength(0);
  });

  it("a segment is a readonly kind+text pair", () => {
    const seg: AIDiffSegment = { kind: "added", text: "x" };
    expect(seg.kind).toBe("added");
    expect(seg.text).toBe("x");
  });
});

describe("ai-diff barrel", () => {
  it("re-exports every public symbol", () => {
    expect(typeof segmentize).toBe("function");
    expect(typeof rewriteAdapter).toBe("function");
    expect(typeof coAuthorChangeAdapter).toBe("function");
    expect(typeof kbEnhanceFieldAdapter).toBe("function");
    expect(typeof betaReaderGroundedAdapter).toBe("function");
    expect(typeof isBetaReaderGrounded).toBe("function");
    // type-only imports from the barrel compile when it re-exports the types:
    const _types: BarrelViewModel | BarrelState | BarrelSegment | BarrelMode = "suggested";
    expect(_types).toBe("suggested");
  });
});
